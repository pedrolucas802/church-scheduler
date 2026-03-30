import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from importlib import import_module

from src.auth.admin_gate import is_admin
from src.i18n import t, get_lang
from src.emailer import send_email


# ======================
# Robust DB function loader (no direct `from src.db import ...`)
# ======================
def _import_fn(paths: list[str], fn_name: str):
    last_err = None
    for p in paths:
        try:
            mod = import_module(p)
            fn = getattr(mod, fn_name)
            return fn
        except Exception as e:
            last_err = e
    raise ImportError(f"Could not import {fn_name} from any of: {paths}. Last error: {last_err}")


# Core functions (try src.db first, then common repo modules)
list_volunteers = _import_fn(
    ["src.db", "src.db.repos.volunteers", "src.db.repos.users"],
    "list_volunteers",
)

list_schedule_between = _import_fn(
    ["src.db", "src.db.repos.schedule"],
    "list_schedule_between",
)

get_assignment_details = _import_fn(
    ["src.db", "src.db.repos.schedule"],
    "get_assignment_details",
)

# Your schedule repo uses set_assignment_user_by_id in the snippet you shared.
# Your page was calling set_assignment_volunteer_by_id, so we map it safely:
try:
    set_assignment_volunteer_by_id = _import_fn(
        ["src.db", "src.db.repos.schedule"],
        "set_assignment_volunteer_by_id",
    )
except ImportError:
    # fallback to the actual name in repo
    set_assignment_user_by_id = _import_fn(
        ["src.db", "src.db.repos.schedule"],
        "set_assignment_user_by_id",
    )

    def set_assignment_volunteer_by_id(assignment_id: int, volunteer_id):
        return set_assignment_user_by_id(assignment_id, volunteer_id)


# Swaps / requests
create_swap_request = _import_fn(
    [
        "src.db",
        "src.db.repos.swap_requests",
        "src.db.repos.swaps",
        "src.db.repos.schedule",
    ],
    "create_swap_request",
)

list_swap_requests = _import_fn(
    [
        "src.db",
        "src.db.repos.swap_requests",
        "src.db.repos.swaps",
    ],
    "list_swap_requests",
)

resolve_swap_request = _import_fn(
    [
        "src.db",
        "src.db.repos.swap_requests",
        "src.db.repos.swaps",
    ],
    "resolve_swap_request",
)

rebuild_reminders_for_month = _import_fn(
    [
        "src.db",
        "src.db.repos.reminders",
        "src.db.repos.reminder_jobs",
        "src.db.repos.schedule",
    ],
    "rebuild_reminders_for_month",
)


# ======================
# Page UI
# ======================
lang = get_lang()
st.title(
    t("edit.title")
    if t("edit.title") != "edit.title"
    else ("Editar / Trocas" if lang == "pt" else "Edit / Swaps")
)

ROLE_PT = {"OBS": "OBS", "FIXED": "CÂMERA FIXA", "MOBILE": "CÂMERA MÓVEL"}
ROLE_EN = {"OBS": "OBS", "FIXED": "FIXED CAMERA", "MOBILE": "MOBILE CAMERA"}


def role_label(role: str) -> str:
    return ROLE_PT.get(role, role) if lang == "pt" else ROLE_EN.get(role, role)


def dow_label(dt: datetime) -> str:
    if lang == "pt":
        return ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][dt.weekday()]
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]


def pretty_date(dt: datetime) -> str:
    return f"{dow_label(dt)} {dt.strftime('%d/%m/%Y')}" if lang == "pt" else dt.strftime("%b %d, %Y")


def pretty_dt(dt: datetime) -> str:
    return f"{pretty_date(dt)} {dt.strftime('%H:%M')}"


def toast_ok(msg: str):
    st.toast(msg, icon="✅")


def toast_warn(msg: str):
    st.toast(msg, icon="⚠️")


def toast_err(msg: str):
    st.toast(msg, icon="❌")


def safe(s):
    return (s or "").strip()


def parse_dt(dt_iso: str) -> datetime:
    # Handles both naive and aware ISO strings.
    return datetime.fromisoformat(dt_iso)


# ======================
# Volunteers (ACTIVE)
# ======================
vols = list_volunteers(active_only=True)

vol_by_name: dict[str, int] = {}
vol_email_by_name: dict[str, str] = {}
for row in vols:
    # expected: (id, name, email, phone, active, ...)
    vid = row[0]
    name = row[1]
    email = row[2] if len(row) > 2 else ""
    if not name:
        continue
    vol_by_name[str(name)] = int(vid)
    vol_email_by_name[str(name)] = (email or "")

vol_names = sorted(vol_by_name.keys())


# ======================
# SWAP REQUEST (PUBLIC)
# ======================
st.subheader(
    (t("swap.request") if t("swap.request") != "swap.request" else ("Solicitar troca" if lang == "pt" else "Request swap"))
)

start = datetime.now()
end = start + timedelta(days=30)

rows = list_schedule_between(start.isoformat(), end.isoformat())
if not rows:
    st.info("Nenhuma escala encontrada." if lang == "pt" else "No schedules found.")
    st.stop()

# Build structured index: date → hour → role → assignment
schedule: dict = {}
for service_id, dt_iso, assignment_id, role, volunteer_name in rows:
    if not assignment_id or not role:
        continue

    dt = parse_dt(dt_iso)
    date_key = dt.date()
    hour_key = dt.strftime("%H:%M")

    schedule.setdefault(date_key, {})
    schedule[date_key].setdefault(hour_key, {})
    schedule[date_key][hour_key][role] = {
        "assignment_id": int(assignment_id),
        "volunteer_name": volunteer_name,
        "dt": dt,
        "dt_iso": dt_iso,
    }

date_options = sorted(schedule.keys())
date_labels = {d: pretty_date(datetime.combine(d, datetime.min.time())) for d in date_options}

picked_date = st.selectbox(
    "📅 " + ("Data do culto" if lang == "pt" else "Service date"),
    options=date_options,
    format_func=lambda d: date_labels[d],
)

hours_for_date = sorted(schedule[picked_date].keys())
picked_hour = st.selectbox(("Horário" if lang == "pt" else "Hour"), hours_for_date)

roles_for_slot = sorted(schedule[picked_date][picked_hour].keys())
picked_role = st.selectbox(
    ("Função" if lang == "pt" else "Role"),
    roles_for_slot,
    format_func=role_label,
)

slot = schedule[picked_date][picked_hour][picked_role]
assignment_id = slot["assignment_id"]
current_volunteer = slot["volunteer_name"] or "—"
dt = slot["dt"]

st.info(
    (f"Escalado atual: **{current_volunteer}**" if lang == "pt" else f"Currently assigned: **{current_volunteer}**")
)

if not vol_names:
    st.warning("Nenhum voluntário ativo encontrado." if lang == "pt" else "No active volunteers found.")
else:
    requester = st.selectbox(("Quem está pedindo?" if lang == "pt" else "Requester"), vol_names)
    replacement = st.selectbox(("Quem vai substituir?" if lang == "pt" else "Replacement"), vol_names)

    reason = st.text_area(
        ("Motivo" if lang == "pt" else "Reason"),
        placeholder=("Ex: viagem" if lang == "pt" else "e.g., travel"),
    )

    if st.button("📨 " + ("Enviar pedido" if lang == "pt" else "Submit request")):
        if requester == replacement:
            st.error(
                "Solicitante e substituto não podem ser a mesma pessoa."
                if lang == "pt"
                else "Requester and replacement cannot be the same."
            )
        else:
            try:
                create_swap_request(
                    assignment_id=int(assignment_id),
                    requested_by_volunteer_id=int(vol_by_name[requester]),
                    replacement_volunteer_id=int(vol_by_name[replacement]),
                    reason=safe(reason),
                )
            except Exception as e:
                toast_err(("Falha ao criar pedido: " if lang == "pt" else "Failed to create request: ") + str(e))
                st.stop()

            subject = (
                f"🔁 Pedido de troca — {dt.strftime('%d/%m %H:%M')}"
                if lang == "pt"
                else f"🔁 Swap request — {dt.strftime('%b %d %H:%M')}"
            )

            body = (
                f"""Novo pedido de troca:

📅 Culto: {dt.strftime('%d/%m/%Y %H:%M')}
🎛️ Função: {role_label(picked_role)}
👤 Atual: {current_volunteer}
🙋 Solicitante: {requester}
✅ Substituto: {replacement}
📝 Motivo: {safe(reason) or '—'}
"""
                if lang == "pt"
                else f"""New swap request:

📅 Service: {dt.strftime('%b %d, %Y %H:%M')}
🎛️ Role: {role_label(picked_role)}
👤 Current: {current_volunteer}
🙋 Requester: {requester}
✅ Replacement: {replacement}
📝 Reason: {safe(reason) or '—'}
"""
            )

            try:
                send_email(subject, body, to_email="plsb802@gmail.com")
                toast_ok("Pedido enviado ✅" if lang == "pt" else "Request sent ✅")
            except Exception as e:
                toast_warn(
                    ("Pedido criado, mas falhou o e-mail: " if lang == "pt" else "Request created, but email failed: ")
                    + str(e)
                )

# ======================
# STOP for non-admins
# ======================
if not is_admin():
    st.stop()

# =====================================================
# ADMIN AREA
# =====================================================
st.divider()
st.header("🛠️ " + ("Área do Admin" if lang == "pt" else "Admin Area"))

# ----------------------
# Admin: Approve / Reject swap requests
# ----------------------
st.subheader("🔁 " + ("Pedidos de troca" if lang == "pt" else "Swap requests"))

status_filter = st.selectbox(
    ("Filtro" if lang == "pt" else "Filter"),
    ["PENDING", "APPROVED", "REJECTED", "ALL"],
    index=0,
)

try:
    req_rows = list_swap_requests(status=None if status_filter == "ALL" else status_filter)
except Exception as e:
    st.error(("Falha ao listar pedidos: " if lang == "pt" else "Failed to list requests: ") + str(e))
    req_rows = []

if not req_rows:
    st.info("Nenhum pedido encontrado." if lang == "pt" else "No requests found.")
else:
    df_req = pd.DataFrame(
        req_rows,
        columns=[
            "req_id",
            "status",
            "reason",
            "created_at",
            "assignment_id",
            "role",
            "dt_iso",
            "assigned_to",
            "requested_by",
            "replacement_id",
            "replacement_name",
        ],
    )

    df_req["when"] = df_req["dt_iso"].apply(lambda x: pretty_dt(parse_dt(x)))
    df_req["role"] = df_req["role"].apply(role_label)

    st.dataframe(
        df_req[
            [
                "req_id",
                "status",
                "when",
                "role",
                "assigned_to",
                "requested_by",
                "replacement_name",
                "reason",
                "created_at",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### " + ("Aprovar/Rejeitar" if lang == "pt" else "Approve/Reject"))
    req_id = st.number_input("Request ID", min_value=1, step=1)

    cA, cB = st.columns(2)
    with cA:
        if st.button("✅ " + ("Aprovar" if lang == "pt" else "Approve"), use_container_width=True):
            row = next((r for r in req_rows if int(r[0]) == int(req_id)), None)
            if not row:
                st.error("Request ID inválido." if lang == "pt" else "Invalid request ID.")
            else:
                (
                    _req_id,
                    _status,
                    _reason,
                    _created_at,
                    _assignment_id,
                    _role,
                    _dt_iso,
                    _assigned_to,
                    _requested_by,
                    replacement_id,
                    replacement_name,
                ) = row

                if not replacement_id:
                    st.error("Pedido não tem substituto definido." if lang == "pt" else "Request has no replacement.")
                else:
                    try:
                        set_assignment_volunteer_by_id(int(_assignment_id), int(replacement_id))
                        resolve_swap_request(int(req_id), status="APPROVED", resolved_by_admin="admin")
                        toast_ok("Aprovado e aplicado ✅" if lang == "pt" else "Approved and applied ✅")
                        st.rerun()
                    except Exception as e:
                        toast_err(("Falha ao aprovar/aplicar: " if lang == "pt" else "Failed to approve/apply: ") + str(e))

    with cB:
        if st.button("❌ " + ("Rejeitar" if lang == "pt" else "Reject"), use_container_width=True):
            row = next((r for r in req_rows if int(r[0]) == int(req_id)), None)
            if not row:
                st.error("Request ID inválido." if lang == "pt" else "Invalid request ID.")
            else:
                try:
                    resolve_swap_request(int(req_id), status="REJECTED", resolved_by_admin="admin")
                    toast_ok("Rejeitado ❌" if lang == "pt" else "Rejected ❌")
                    st.rerun()
                except Exception as e:
                    toast_err(("Falha ao rejeitar: " if lang == "pt" else "Failed to reject: ") + str(e))

# ----------------------
# Admin: Edit a service slot (manual assignment change)
# ----------------------
st.divider()
st.subheader("🗓️ " + ("Editar escala (manual)" if lang == "pt" else "Edit schedule (manual)"))

admin_options = []
admin_map = {}
for service_id, dt_iso, assignment_id, role, volunteer_name in rows:
    if not assignment_id or not role:
        continue
    dt2 = parse_dt(dt_iso)
    label = f"{pretty_dt(dt2)} — {role_label(role)} — {(volunteer_name or '—')}"
    admin_options.append(label)
    admin_map[label] = int(assignment_id)

if not admin_options:
    st.info("Sem slots editáveis no período." if lang == "pt" else "No editable slots in this period.")
else:
    picked = st.selectbox(("Selecionar slot" if lang == "pt" else "Pick slot"), admin_options)
    aid = admin_map[picked]

    details = get_assignment_details(aid)
    if details:
        _aid, _service_id, _dt_iso, _role, _vid, _vname = details
        st.caption(
            (f"Atual: **{_vname or '—'}** | {pretty_dt(parse_dt(_dt_iso))} | {role_label(_role)}"
             if lang == "pt"
             else f"Current: **{_vname or '—'}** | {pretty_dt(parse_dt(_dt_iso))} | {role_label(_role)}")
        )

    new_name = st.selectbox(("Novo voluntário" if lang == "pt" else "New volunteer"), ["—"] + vol_names)
    new_vid = None if new_name == "—" else vol_by_name[new_name]

    if st.button("💾 " + ("Salvar alteração" if lang == "pt" else "Save change")):
        try:
            set_assignment_volunteer_by_id(int(aid), (int(new_vid) if new_vid is not None else None))
            toast_ok("Atualizado ✅" if lang == "pt" else "Updated ✅")
            st.rerun()
        except Exception as e:
            toast_err(("Falha ao salvar: " if lang == "pt" else "Failed to save: ") + str(e))

# ----------------------
# Admin: Rebuild reminders for a month
# ----------------------
st.divider()
st.subheader("⏰ " + ("Reminders (rebuild do mês)" if lang == "pt" else "Reminders (rebuild month)"))

now2 = datetime.now()
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("Year", min_value=2020, max_value=2100, value=now2.year, step=1)
with col2:
    month_num = st.number_input("Month", min_value=1, max_value=12, value=now2.month, step=1)

if st.button("🔁 " + ("Recriar reminders do mês" if lang == "pt" else "Rebuild month reminders")):
    try:
        rebuild_reminders_for_month(int(year), int(month_num))
        toast_ok("Reminders recriados ✅" if lang == "pt" else "Reminders rebuilt ✅")
    except Exception as e:
        toast_err(("Falha ao recriar reminders: " if lang == "pt" else "Failed to rebuild reminders: ") + str(e))