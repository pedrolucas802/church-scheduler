import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from src.auth import is_admin
from src.db import (
    list_volunteers,
    list_schedule_between,
    create_swap_request,
    list_swap_requests,
    resolve_swap_request,
    get_assignment_details,
    set_assignment_volunteer_by_id,
    list_services_in_month,
    get_assignments_for_service,
    rebuild_reminders_for_month,
)
from src.i18n import t, get_lang
from src.services.admin_alert_service import send_pending_edit_alert
from src.services.ui_action_service import clear_page_action, consume_page_action, is_page_action_busy, queue_page_action

lang = get_lang()
PAGE_KEY = "edit_page"
st.title(t("edit.title") if t("edit.title") != "edit.title" else ("Editar / Trocas" if lang == "pt" else "Edit / Swaps"))

# ======================
# Helpers
# ======================
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

# ======================
# Volunteers (ACTIVE)
# ======================
# DB returns: (id, name, email, phone, active, thu_ok, sun_ok, can_obs, can_fixed, can_mobile)
vols = list_volunteers(active_only=True)

vol_by_name: dict[str, int] = {}
vol_email_by_name: dict[str, str] = {}
for vid, name, email, phone, active, *_ in vols:
    if not name:
        continue
    vol_by_name[name] = int(vid)
    vol_email_by_name[name] = (email or "")

vol_names = sorted(vol_by_name.keys())

# ======================
# SWAP REQUEST (PUBLIC)
# ======================
st.subheader((t("swap.request") if t("swap.request") != "swap.request" else ("Solicitar troca" if lang == "pt" else "Request swap")))

start = datetime.now()
end = datetime.now() + timedelta(days=30)

rows = list_schedule_between(start.isoformat(), end.isoformat())
if not rows:
    st.info("Nenhuma escala encontrada." if lang == "pt" else "No schedules found.")
    st.stop()

# Build structured index: date → hour → role → assignment
schedule: dict = {}
for service_id, dt_iso, assignment_id, role, volunteer_name in rows:
    if not assignment_id or not role:
        continue

    dt = datetime.fromisoformat(dt_iso)
    date_key = dt.date()
    hour_key = dt.strftime("%H:%M")

    schedule.setdefault(date_key, {})
    schedule[date_key].setdefault(hour_key, {})
    schedule[date_key][hour_key][role] = {
        "assignment_id": int(assignment_id),
        "volunteer_name": volunteer_name,
        "dt": dt,
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

    st.button(
        "📨 " + ("Enviar pedido" if lang == "pt" else "Submit request"),
        disabled=is_page_action_busy(PAGE_KEY),
        on_click=queue_page_action,
        args=(
            PAGE_KEY,
            "submit_swap_request",
            {
                "assignment_id": int(assignment_id),
                "requester": requester,
                "replacement": replacement,
                "requester_id": int(vol_by_name[requester]),
                "replacement_id": int(vol_by_name[replacement]),
                "reason": reason.strip(),
                "dt_iso": dt.isoformat(),
                "role": picked_role,
                "current_volunteer": current_volunteer,
            },
        ),
    )

swap_request_action = consume_page_action(PAGE_KEY, "submit_swap_request")
if swap_request_action is not None:
    try:
        if swap_request_action["requester"] == swap_request_action["replacement"]:
            st.error("Solicitante e substituto não podem ser a mesma pessoa." if lang == "pt" else "Requester and replacement cannot be the same.")
        else:
            with st.spinner("Enviando pedido..." if lang == "pt" else "Submitting request..."):
                create_swap_request(
                    assignment_id=int(swap_request_action["assignment_id"]),
                    requested_by_volunteer_id=int(swap_request_action["requester_id"]),
                    replacement_volunteer_id=int(swap_request_action["replacement_id"]),
                    reason=str(swap_request_action["reason"]),
                )

                alert_result = send_pending_edit_alert(
                    service_dt=datetime.fromisoformat(str(swap_request_action["dt_iso"])),
                    role=str(swap_request_action["role"]),
                    current_volunteer=str(swap_request_action["current_volunteer"]),
                    requester=str(swap_request_action["requester"]),
                    replacement=str(swap_request_action["replacement"]),
                    reason=str(swap_request_action["reason"]),
                    lang=lang,
                )
            if alert_result["total_recipients"] == 0:
                toast_warn(
                    "Pedido criado, mas nenhum numero de admin foi configurado para alerta."
                    if lang == "pt"
                    else "Request created, but no admin alert numbers are configured yet."
                )
            elif alert_result["failed_messages"] > 0:
                toast_warn(
                    (
                        f"Pedido criado, mas {alert_result['failed_messages']} alerta(s) falharam."
                        if lang == "pt"
                        else f"Request created, but {alert_result['failed_messages']} alert(s) failed."
                    )
                )
            else:
                toast_ok("Pedido enviado ✅" if lang == "pt" else "Request sent ✅")
    except Exception as e:
        toast_warn(
            ("Pedido criado, mas falhou o alerta no WhatsApp: " if lang == "pt" else "Request created, but the WhatsApp alert failed: ")
            + str(e)
        )
    finally:
        clear_page_action(PAGE_KEY)

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
    index=0
)

req_rows = list_swap_requests(status=None if status_filter == "ALL" else status_filter)

if not req_rows:
    st.info("Nenhum pedido encontrado." if lang == "pt" else "No requests found.")
else:
    df_req = pd.DataFrame(
        req_rows,
        columns=[
            "req_id", "status", "reason", "created_at",
            "assignment_id", "role", "dt_iso",
            "assigned_to", "requested_by",
            "replacement_id", "replacement_name",
        ],
    )
    df_req["when"] = df_req["dt_iso"].apply(lambda x: pretty_dt(datetime.fromisoformat(x)))
    df_req["role"] = df_req["role"].apply(role_label)

    st.dataframe(
        df_req[["req_id", "status", "when", "role", "assigned_to", "requested_by", "replacement_name", "reason", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### " + ("Aprovar/Rejeitar" if lang == "pt" else "Approve/Reject"))
    req_id = st.number_input("Request ID", min_value=1, step=1)

    cA, cB = st.columns(2)
    with cA:
        st.button(
            "✅ " + ("Aprovar" if lang == "pt" else "Approve"),
            use_container_width=True,
            disabled=is_page_action_busy(PAGE_KEY),
            on_click=queue_page_action,
            args=(PAGE_KEY, "approve_swap_request", {"req_id": int(req_id)}),
        )

    with cB:
        st.button(
            "❌ " + ("Rejeitar" if lang == "pt" else "Reject"),
            use_container_width=True,
            disabled=is_page_action_busy(PAGE_KEY),
            on_click=queue_page_action,
            args=(PAGE_KEY, "reject_swap_request", {"req_id": int(req_id)}),
        )

approve_action = consume_page_action(PAGE_KEY, "approve_swap_request")
if approve_action is not None:
    try:
        row = next((r for r in req_rows if int(r[0]) == int(approve_action["req_id"])), None)
        if not row:
            st.error("Request ID inválido." if lang == "pt" else "Invalid request ID.")
        else:
            _req_id, _status, _reason, _created_at, assignment_id, role, dt_iso, assigned_to, requested_by, replacement_id, replacement_name = row
            if not replacement_id:
                st.error("Pedido não tem substituto definido." if lang == "pt" else "Request has no replacement.")
            else:
                with st.spinner("Aprovando..." if lang == "pt" else "Approving..."):
                    set_assignment_volunteer_by_id(int(assignment_id), int(replacement_id))
                    resolve_swap_request(int(approve_action["req_id"]), status="APPROVED", resolved_by_admin="admin")
                toast_ok("Aprovado e aplicado ✅" if lang == "pt" else "Approved and applied ✅")
                st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

reject_action = consume_page_action(PAGE_KEY, "reject_swap_request")
if reject_action is not None:
    try:
        row = next((r for r in req_rows if int(r[0]) == int(reject_action["req_id"])), None)
        if not row:
            st.error("Request ID inválido." if lang == "pt" else "Invalid request ID.")
        else:
            with st.spinner("Rejeitando..." if lang == "pt" else "Rejecting..."):
                resolve_swap_request(int(reject_action["req_id"]), status="REJECTED", resolved_by_admin="admin")
            toast_ok("Rejeitado ❌" if lang == "pt" else "Rejected ❌")
            st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

# ----------------------
# Admin: Edit a service slot (manual assignment change)
# ----------------------
st.divider()
st.subheader("🗓️ " + ("Editar escala (manual)" if lang == "pt" else "Edit schedule (manual)"))

# reuse next 30 days
admin_rows = rows

# build a list of (label, assignment_id)
admin_options = []
admin_map = {}
for service_id, dt_iso, assignment_id, role, volunteer_name in admin_rows:
    if not assignment_id or not role:
        continue
    dt2 = datetime.fromisoformat(dt_iso)
    label = f"{pretty_dt(dt2)} — {role_label(role)} — {(volunteer_name or '—')}"
    admin_options.append(label)
    admin_map[label] = int(assignment_id)

picked = st.selectbox(("Selecionar slot" if lang == "pt" else "Pick slot"), admin_options)
aid = admin_map[picked]

details = get_assignment_details(aid)
if details:
    _aid, _service_id, _dt_iso, _role, _vid, _vname = details
    st.caption(
        (f"Atual: **{_vname or '—'}** | {pretty_dt(datetime.fromisoformat(_dt_iso))} | {role_label(_role)}"
         if lang == "pt"
         else f"Current: **{_vname or '—'}** | {pretty_dt(datetime.fromisoformat(_dt_iso))} | {role_label(_role)}")
    )

new_name = st.selectbox(("Novo voluntário" if lang == "pt" else "New volunteer"), ["—"] + vol_names)
new_vid = None if new_name == "—" else vol_by_name[new_name]

st.button(
    "💾 " + ("Salvar alteração" if lang == "pt" else "Save change"),
    disabled=is_page_action_busy(PAGE_KEY),
    on_click=queue_page_action,
    args=(PAGE_KEY, "save_assignment_change", {"assignment_id": int(aid), "new_vid": new_vid}),
)

save_assignment_action = consume_page_action(PAGE_KEY, "save_assignment_change")
if save_assignment_action is not None:
    try:
        with st.spinner("Salvando alteração..." if lang == "pt" else "Saving change..."):
            set_assignment_volunteer_by_id(int(save_assignment_action["assignment_id"]), save_assignment_action["new_vid"])
        toast_ok("Atualizado ✅" if lang == "pt" else "Updated ✅")
        st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

# ----------------------
# Admin: Rebuild reminders for a month
# ----------------------
st.divider()
st.subheader("⏰ " + ("Reminders (rebuild do mês)" if lang == "pt" else "Reminders (rebuild month)"))

now = datetime.now()
col1, col2 = st.columns(2)
with col1:
    year = st.number_input("Year", min_value=2020, max_value=2100, value=now.year, step=1)
with col2:
    month = st.number_input("Month", min_value=1, max_value=12, value=now.month, step=1)

st.button(
    "🔁 " + ("Recriar reminders do mês" if lang == "pt" else "Rebuild month reminders"),
    disabled=is_page_action_busy(PAGE_KEY),
    on_click=queue_page_action,
    args=(PAGE_KEY, "rebuild_month_reminders", {"year": int(year), "month": int(month)}),
)

rebuild_action = consume_page_action(PAGE_KEY, "rebuild_month_reminders")
if rebuild_action is not None:
    try:
        with st.spinner("Recriando reminders..." if lang == "pt" else "Rebuilding reminders..."):
            rebuild_reminders_for_month(int(rebuild_action["year"]), int(rebuild_action["month"]))
        toast_ok("Reminders recriados ✅" if lang == "pt" else "Reminders rebuilt ✅")
        st.rerun()
    finally:
        clear_page_action(PAGE_KEY)
