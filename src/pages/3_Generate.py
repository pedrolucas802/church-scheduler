import random
from collections import Counter, defaultdict
from datetime import datetime

import streamlit as st

from src.auth import is_admin
from src.db import (
    list_volunteers,
    clear_month_services,
    ensure_service,
    upsert_assignment,
    rebuild_reminders_for_month,
)
from src.scheduler import month_services, generate_assignments
from src.services.monthly_schedule_service import send_month_schedule_alerts
from src.services.ui_action_service import clear_page_action, consume_page_action, is_page_action_busy, queue_page_action
from src.i18n import t, get_lang


lang = get_lang()
PAGE_KEY = "generate_page"


def _label(pt: str, en: str) -> str:
    return pt if lang == "pt" else en


def is_sunday_1500_obs_only(dt_iso: str) -> bool:
    """
    Rule: Sunday 15:00 service needs OBS only (no FIXED/MOBILE).
    """
    dt = datetime.fromisoformat(dt_iso)
    return (dt.weekday() == 6) and (dt.strftime("%H:%M") == "15:00")


def required_roles_for_service(dt_iso: str) -> list[str]:
    return ["OBS"] if is_sunday_1500_obs_only(dt_iso) else ["OBS", "FIXED", "MOBILE"]


st.title(t("gen.title") if t("gen.title") != "gen.title" else _label("⚙️ Gerar Escala", "⚙️ Generate Schedule"))

if not is_admin():
    st.warning(t("common.admin_required") if t("common.admin_required") != "common.admin_required" else _label("Acesso de admin necessário.", "Admin required."))
    st.stop()

# Seed
if "gen_seed" not in st.session_state:
    st.session_state["gen_seed"] = random.randint(1, 1_000_000_000)

seed_bar1, seed_bar2 = st.columns([1, 0.25])
with seed_bar1:
    st.caption(
        _label(
            "Dica: se o Seed for o mesmo, o resultado será exatamente igual. Mude o Seed para embaralhar.",
            "Tip: if Seed is the same, the result will be identical. Change Seed to reshuffle.",
        )
    )
with seed_bar2:
    if st.button(
        "🎲 " + _label("Novo seed", "New seed"),
        key="gen_new_seed_btn",
        disabled=is_page_action_busy(PAGE_KEY),
    ):
        st.session_state["gen_seed"] = random.randint(1, 1_000_000_000)
        st.toast(_label("Seed atualizado.", "Seed updated."), icon="🎲")
        st.rerun()

c1, c2, c3 = st.columns(3)
with c1:
    year = st.number_input(
        t("gen.year") if t("gen.year") != "gen.year" else _label("Ano", "Year"),
        min_value=2020,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="gen_year",
    )
with c2:
    month = st.number_input(
        t("gen.month") if t("gen.month") != "gen.month" else _label("Mês", "Month"),
        min_value=1,
        max_value=12,
        value=datetime.now().month,
        step=1,
        key="gen_month",
    )
with c3:
    seed = st.number_input(
        t("gen.seed") if t("gen.seed") != "gen.seed" else _label("Seed (muda para embaralhar)", "Seed (change to reshuffle)"),
        min_value=1,
        value=int(st.session_state["gen_seed"]),
        step=1,
        key="gen_seed_input",
    )
    st.session_state["gen_seed"] = int(seed)

st.markdown("")

c4, c5, c6 = st.columns(3)
with c4:
    prefer_mobile = st.checkbox(
        t("gen.prefer_mobile") if t("gen.prefer_mobile") != "gen.prefer_mobile" else _label("Tentar preencher CÂMERA MÓVEL quando possível", "Try to fill MOBILE when possible"),
        value=True,
        key="gen_prefer_mobile",
    )
with c5:
    ensure_everyone = st.checkbox(
        _label("Garantir que todos sirvam ao menos 1x (se possível)", "Ensure everyone serves at least once (if possible)"),
        value=True,
        key="gen_ensure_everyone",
        help=_label(
            "Se não for possível por disponibilidade/capacidades, o sistema mostra quem ficou de fora.",
            "If impossible due to availability/capabilities, the app will show who couldn't be placed.",
        ),
    )
with c6:
    avoid_role_repeat = st.checkbox(
        _label("Evitar repetir o mesmo papel no mês", "Avoid repeating the same role across the month"),
        value=True,
        key="gen_avoid_role_repeat",
        help=_label(
            "Best-effort: pode repetir se não houver opções suficientes.",
            "Best-effort: may repeat if there aren’t enough options.",
        ),
    )

use_auto_random = st.checkbox(
    _label("Sempre embaralhar automaticamente ao gerar", "Always reshuffle automatically when generating"),
    value=False,
    key="gen_auto_random",
    help=_label(
        "Se marcado, o app usa um seed novo toda vez que você clica em Gerar.",
        "If checked, the app uses a new seed every time you click Generate.",
    ),
)

# NOTE ABOUT THE SPECIAL RULE
st.info(
    _label(
        "Regra especial: **Domingo 15:00** precisa **apenas OBS** (sem câmera fixa/móvel).",
        "Special rule: **Sunday 15:00** needs **OBS only** (no fixed/mobile camera).",
    )
)

action_col1, action_col2 = st.columns(2)
with action_col1:
    st.button(
        t("gen.generate_overwrite") if t("gen.generate_overwrite") != "gen.generate_overwrite" else _label("Gerar (substitui o mês inteiro)", "Generate (overwrites month)"),
        type="primary",
        key="gen_go",
        disabled=is_page_action_busy(PAGE_KEY),
        on_click=queue_page_action,
        args=(
            PAGE_KEY,
            "generate_schedule",
            {
                "year": int(year),
                "month": int(month),
                "seed": int(seed),
                "prefer_mobile": bool(prefer_mobile),
                "use_auto_random": bool(use_auto_random),
            },
        ),
    )
with action_col2:
    st.button(
        _label("Enviar escala do mes por WhatsApp", "Send month schedule by WhatsApp"),
        key="gen_send_month_schedule",
        disabled=is_page_action_busy(PAGE_KEY),
        on_click=queue_page_action,
        args=(PAGE_KEY, "send_month_alerts", {"year": int(year), "month": int(month)}),
        help=_label(
            "Envia uma mensagem por voluntario com todos os cultos dele no mes selecionado.",
            "Sends one message per volunteer with all of their services in the selected month.",
        ),
    )

send_month_alerts_action = consume_page_action(PAGE_KEY, "send_month_alerts")
if send_month_alerts_action is not None:
    try:
        with st.spinner(_label("Enviando escala do mes...", "Sending month schedule...")):
            result = send_month_schedule_alerts(
                int(send_month_alerts_action["year"]),
                int(send_month_alerts_action["month"]),
                lang=lang,
            )
        if result["total_recipients"] == 0:
            st.warning(
                _label(
                    "Nao ha voluntarios escalados nesse mes para enviar.",
                    "There are no scheduled volunteers in this month to notify.",
                )
            )
        else:
            st.toast(
                _label(
                    f"WhatsApps enviados: {result['sent_messages']} | Sem numero: {result['skipped_no_phone']} | Falhas: {result['failed_messages']}",
                    f"WhatsApps sent: {result['sent_messages']} | No phone: {result['skipped_no_phone']} | Failures: {result['failed_messages']}",
                ),
                icon="📲",
            )
    except Exception as exc:
        st.toast(f"Falha: {exc}" if lang == "pt" else f"Failed: {exc}", icon="❌")
    finally:
        clear_page_action(PAGE_KEY)

generate_action = consume_page_action(PAGE_KEY, "generate_schedule")
if generate_action is not None:
    try:
        with st.spinner(_label("Gerando escala...", "Generating schedule...")):
            run_seed = int(generate_action["seed"])
            if bool(generate_action["use_auto_random"]):
                run_seed = random.randint(1, 1_000_000_000)
                st.session_state["gen_seed"] = run_seed

            clear_month_services(int(generate_action["year"]), int(generate_action["month"]))

            # Load volunteers (FIX: now includes email column)
            vols = []
            for (vid, name, email, phone, active, thu_ok, sun_ok, can_obs, can_fixed, can_mobile) in list_volunteers(active_only=False):
                vols.append(
                    {
                        "id": int(vid),
                        "name": name,
                        "email": email,
                        "phone": phone,
                        "active": bool(active),
                        "thu_ok": bool(thu_ok),
                        "sun_ok": bool(sun_ok),
                        "can_obs": bool(can_obs),
                        "can_fixed": bool(can_fixed),
                        "can_mobile": bool(can_mobile),
                    }
                )

            # Shuffle volunteer input order too (seeded)
            random.Random(run_seed).shuffle(vols)

            # Month services (dt_iso strings)
            services = month_services(int(generate_action["year"]), int(generate_action["month"]))
            if not services:
                st.warning(_label("Nenhum culto encontrado para esse mês.", "No services found for this month."))
                st.stop()

            assignments = generate_assignments(
                vols,
                services,
                seed=run_seed,
                prefer_mobile=bool(generate_action["prefer_mobile"]),
            )

            for dt_iso in list(assignments.keys()):
                if is_sunday_1500_obs_only(dt_iso):
                    assignments[dt_iso] = {"OBS": assignments[dt_iso].get("OBS")}

            for dt_iso, roles in assignments.items():
                sid = ensure_service(dt_iso)
                for role, vol_id in roles.items():
                    upsert_assignment(sid, role, vol_id)

            rebuild_reminders_for_month(int(generate_action["year"]), int(generate_action["month"]))

        id_to_name = {v["id"]: v["name"] for v in vols}
        active_ids = [v["id"] for v in vols if v["active"]]

        served_count = Counter()
        role_count = defaultdict(Counter)
        unfilled_slots = 0
        total_slots = 0

        for dt_iso, roles in assignments.items():
            required = required_roles_for_service(dt_iso)
            total_slots += len(required)

            for role in required:
                vid = roles.get(role)
                if vid is None:
                    unfilled_slots += 1
                    continue
                served_count[vid] += 1
                role_count[vid][role] += 1

        missing = [vid for vid in active_ids if served_count.get(vid, 0) == 0]

        st.success(_label("Escala gerada e lembretes reconstruídos.", "Generated schedule + rebuilt reminder jobs for the month."))
        st.toast(_label("Concluído ✅", "Done ✅"), icon="✅")
        st.caption(_label(f"Seed usado: {run_seed}", f"Seed used: {run_seed}"))

        a1, a2, a3, a4 = st.columns(4)
        a1.metric(_label("Cultos", "Services"), str(len(assignments)))
        a2.metric(_label("Slots totais", "Total slots"), str(total_slots))
        a3.metric(_label("Slots vazios", "Empty slots"), str(unfilled_slots))
        a4.metric(_label("Voluntários ativos", "Active volunteers"), str(len(active_ids)))

        if ensure_everyone and missing:
            st.warning(
                _label(
                    "Alguns voluntários ativos não conseguiram ser escalados (provável conflito de disponibilidade/capacidade):",
                    "Some active volunteers could not be scheduled (likely availability/capability constraints):",
                )
            )
            st.write(", ".join(id_to_name.get(vid, str(vid)) for vid in missing))

        if avoid_role_repeat:
            repeats = []
            for vid, c in role_count.items():
                for role, n in c.items():
                    if n >= 2:
                        repeats.append((id_to_name.get(vid, str(vid)), role, n))
            if repeats:
                st.info(
                    _label(
                        "Aviso: houve repetição de papel para alguns voluntários (best-effort).",
                        "Note: some volunteers repeated roles (best-effort).",
                    )
                )
                st.dataframe(
                    [{"volunteer": v, "role": r, "times": n} for (v, r, n) in repeats],
                    use_container_width=True,
                    hide_index=True,
                )

        st.caption(
            _label(
                "Se quiser outra distribuição, clique em 'Novo seed' ou marque 'Sempre embaralhar automaticamente'.",
                "If you want a different distribution, click 'New seed' or enable 'Always reshuffle automatically'.",
            )
        )
    finally:
        clear_page_action(PAGE_KEY)
