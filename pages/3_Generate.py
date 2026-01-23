import streamlit as st
from datetime import datetime
from collections import Counter, defaultdict
import random

from src.auth import is_admin
from src.db import (
    list_volunteers,
    clear_month_services,
    ensure_service,
    upsert_assignment,
    rebuild_reminders_for_month,
)
from src.scheduler import month_services, generate_assignments

try:
    from src.i18n import t
except Exception:
    def t(key: str) -> str:
        return key


def _label(pt: str, en: str) -> str:
    lang = st.session_state.get("lang", "en")
    return pt if lang == "pt" else en


st.title(_label("⚙️ Gerar Escala", "⚙️ Generate Schedule"))

if not is_admin():
    st.warning(_label("Acesso de admin necessário.", "Admin required."))
    st.stop()


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
    if st.button("🎲 " + _label("Novo seed", "New seed"), key="gen_new_seed_btn"):
        st.session_state["gen_seed"] = random.randint(1, 1_000_000_000)
        st.rerun()


c1, c2, c3 = st.columns(3)
with c1:
    year = st.number_input(
        _label("Ano", "Year"),
        min_value=2020,
        max_value=2100,
        value=datetime.now().year,
        step=1,
        key="gen_year",
    )
with c2:
    month = st.number_input(
        _label("Mês", "Month"),
        min_value=1,
        max_value=12,
        value=datetime.now().month,
        step=1,
        key="gen_month",
    )
with c3:
    seed = st.number_input(
        _label("Seed (muda para embaralhar)", "Seed (change to reshuffle)"),
        min_value=1,
        value=int(st.session_state["gen_seed"]),
        step=1,
        key="gen_seed_input",
    )
    # keep session in sync (so it persists)
    st.session_state["gen_seed"] = int(seed)

st.markdown("")

c4, c5, c6 = st.columns(3)
with c4:
    prefer_mobile = st.checkbox(
        _label("Tentar preencher CÂMERA MÓVEL quando possível", "Try to fill MOBILE when possible"),
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


if st.button(_label("Gerar (substitui o mês inteiro)", "Generate (overwrites month)"), type="primary", key="gen_go"):
    run_seed = int(seed)
    if use_auto_random:
        run_seed = random.randint(1, 1_000_000_000)
        st.session_state["gen_seed"] = run_seed  # show what was used

    clear_month_services(int(year), int(month))

    # Load volunteers
    vols = []
    for (vid, name, phone, active, thu_ok, sun_ok, can_obs, can_fixed, can_mobile) in list_volunteers(active_only=False):
        vols.append(
            {
                "id": vid,
                "name": name,
                "active": bool(active),
                "thu_ok": bool(thu_ok),
                "sun_ok": bool(sun_ok),
                "can_obs": bool(can_obs),
                "can_fixed": bool(can_fixed),
                "can_mobile": bool(can_mobile),
            }
        )

    # EXTRA: shuffle input volunteer order too (seeded)
    random.Random(run_seed).shuffle(vols)

    services = month_services(int(year), int(month))

    if not services:
        st.warning(_label("Nenhum culto encontrado para esse mês.", "No services found for this month."))
        st.stop()

    # Generate assignments
    # (If you later add ensure_everyone/avoid_role_repeat args to scheduler, wire them here.)
    assignments = generate_assignments(
        vols,
        services,
        seed=run_seed,
        prefer_mobile=prefer_mobile,
    )

    # Persist services + assignments
    for dt_iso, roles in assignments.items():
        sid = ensure_service(dt_iso)
        for role, vol_id in roles.items():
            upsert_assignment(sid, role, vol_id)

    rebuild_reminders_for_month(int(year), int(month))


    id_to_name = {v["id"]: v["name"] for v in vols}
    active_ids = [v["id"] for v in vols if v["active"]]

    served_count = Counter()
    role_count = defaultdict(Counter)  # vid -> Counter(role)
    unfilled_slots = 0

    for _, roles in assignments.items():
        for role, vid in roles.items():
            if vid is None:
                unfilled_slots += 1
                continue
            served_count[vid] += 1
            role_count[vid][role] += 1

    missing = [vid for vid in active_ids if served_count.get(vid, 0) == 0]

    st.success(_label("Escala gerada e lembretes reconstruídos.", "Generated schedule + rebuilt reminder jobs for the month."))
    st.caption(_label(f"Seed usado: {run_seed}", f"Seed used: {run_seed}"))

    a1, a2, a3 = st.columns(3)
    a1.metric(_label("Cultos", "Services"), str(len(assignments)))
    a2.metric(_label("Slots vazios", "Empty slots"), str(unfilled_slots))
    a3.metric(_label("Voluntários ativos", "Active volunteers"), str(len(active_ids)))

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
            )

    st.caption(
        _label(
            "Se quiser outra distribuição, clique em 'Novo seed' ou marque 'Sempre embaralhar automaticamente'.",
            "If you want a different distribution, click 'New seed' or enable 'Always reshuffle automatically'.",
        )
    )