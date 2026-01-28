import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from src.auth import is_admin
from src.db import (
    list_services_in_month,
    list_volunteers,
    upsert_assignment,
    rebuild_reminders_for_month,
    get_assignments_for_service,
    list_swap_requests,
    resolve_swap_request,
    get_assignment_details,
    set_assignment_volunteer_by_id,
    list_schedule_between,
    create_swap_request,
)
from src.i18n import t, get_lang
from src.emailer import send_email

lang = get_lang()

st.title(t("edit.title"))

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

# ======================
# Volunteers
# ======================
vols = list_volunteers(active_only=True)
vol_by_name = {}
for vid, name, phone, email, active, *_ in vols:
    vol_by_name[name] = int(vid)

vol_names = list(vol_by_name.keys())

# ======================
# SWAP REQUEST (PUBLIC)
# ======================
st.subheader((t("swap.request") if t("swap.request") != "swap.request" else "Solicitar troca"))

start = datetime.now()
end = datetime.now() + timedelta(days=30)

rows = list_schedule_between(start.isoformat(), end.isoformat())
if not rows:
    st.info("Nenhuma escala encontrada." if lang == "pt" else "No schedules found.")
    st.stop()

# ------------------------------------------------
# Build structured index: date → hour → role → assignment
# ------------------------------------------------
schedule = {}
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

# -----------------------------
# STEP 1 — Date
# -----------------------------
date_options = sorted(schedule.keys())
date_labels = {
    d: pretty_date(datetime.combine(d, datetime.min.time()))
    for d in date_options
}

picked_date = st.selectbox(
    "📅 " + ("Data do culto" if lang == "pt" else "Service date"),
    options=date_options,
    format_func=lambda d: date_labels[d],
)

# -----------------------------
# STEP 2 — Hour
# -----------------------------
hours_for_date = sorted(schedule[picked_date].keys())
picked_hour = st.selectbox(
    ("Horário" if lang == "pt" else "Hour"),
    hours_for_date,
)

# -----------------------------
# STEP 3 — Role
# -----------------------------
roles_for_slot = schedule[picked_date][picked_hour].keys()
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
    (
        f"Escalado atual: **{current_volunteer}**"
        if lang == "pt"
        else f"Currently assigned: **{current_volunteer}**"
    )
)

# -----------------------------
# Swap form
# -----------------------------
requester = st.selectbox(
    ("Quem está pedindo?" if lang == "pt" else "Requester"),
    vol_names,
)

replacement = st.selectbox(
    ("Quem vai substituir?" if lang == "pt" else "Replacement"),
    vol_names,
)

reason = st.text_area(
    ("Motivo" if lang == "pt" else "Reason"),
    placeholder="Ex: viagem / traveling",
)

if st.button("📨 " + ("Enviar pedido" if lang == "pt" else "Submit request")):
    if requester == replacement:
        st.error("Solicitante e substituto não podem ser a mesma pessoa.")
    else:
        create_swap_request(
            assignment_id,
            vol_by_name[requester],
            vol_by_name[replacement],
            reason.strip(),
        )

        subject = (
            f"🔁 Pedido de troca — {dt.strftime('%d/%m %H:%M')}"
            if lang == "pt"
            else f"🔁 Swap request — {dt.strftime('%b %d %H:%M')}"
        )

        body = (
            f"""
Novo pedido de troca:

📅 Culto: {dt.strftime('%d/%m/%Y %H:%M')}
🎛️ Função: {role_label(picked_role)}
👤 Atual: {current_volunteer}
🙋 Solicitante: {requester}
✅ Substituto: {replacement}
📝 Motivo: {reason or '—'}
"""
            if lang == "pt"
            else f"""
New swap request:

📅 Service: {dt.strftime('%b %d, %Y %H:%M')}
🎛️ Role: {role_label(picked_role)}
👤 Current: {current_volunteer}
🙋 Requester: {requester}
✅ Replacement: {replacement}
📝 Reason: {reason or '—'}
"""
        )

        try:
            send_email(subject, body, to_email="plsb802@gmail.com")
            st.toast("Pedido enviado✅")
        except Exception as e:
            st.warning(f"Pedido criado, mas falhou o e-mail: {e}")

# ======================
# STOP for non-admins
# ======================
if not is_admin():
    st.stop()

# =====================================================
# ADMIN PART (unchanged below)
# =====================================================
st.divider()
st.subheader("⚙️ " + ("Admin — Editar escala" if lang == "pt" else "Admin — Edit schedule"))

# 👉 You can keep the rest of your admin logic exactly as-is
# (service picker, edit assignments, approve swaps, etc.)