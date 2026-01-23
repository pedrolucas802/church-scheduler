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
from src.emailer import send_email  # <-- NEW

lang = get_lang()

st.title(t("edit.title"))

def dow_label(dt: datetime) -> str:
    if lang == "pt":
        return ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][dt.weekday()]
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]

def pretty_dt(dt: datetime) -> str:
    if lang == "pt":
        return f"{dow_label(dt)}, {dt.strftime('%d/%m/%Y')} — {dt.strftime('%H:%M')}"
    return f"{dow_label(dt)}, {dt.strftime('%b %d, %Y')} — {dt.strftime('%H:%M')}"

ROLE_PT = {"OBS": "OBS", "FIXED": "CÂMERA FIXA", "MOBILE": "CÂMERA MÓVEL"}
ROLE_EN = {"OBS": "OBS", "FIXED": "FIXED CAMERA", "MOBILE": "MOBILE CAMERA"}

def role_label(role: str) -> str:
    return (ROLE_PT.get(role, role) if lang == "pt" else ROLE_EN.get(role, role))

vols = list_volunteers(active_only=True)

# Map name->id and id->name
vol_by_name = {"": None}
for vid, name, phone, active, thu_ok, sun_ok, can_obs, can_fixed, can_mobile in vols:
    vol_by_name[name] = int(vid)

vol_names = list(vol_by_name.keys())
vol_names_nonempty = [n for n in vol_names if n != ""]

st.write("")
st.write("")

st.subheader(t("swap.request") if "swap.request" else ("Solicitar troca" if lang == "pt" else "Request a swap"))
st.caption(
    "Faça seu pedido aqui. O admin aprova e aplica a troca."
    if lang == "pt"
    else "Submit your request here. Admin will approve and apply the swap."
)

start = datetime.now()
end = datetime.now() + timedelta(days=30)

rows = list_schedule_between(start.isoformat(), end.isoformat())

assignments = []
for service_id, dt_iso, assignment_id, role, volunteer_name in rows:
    if assignment_id and role:
        dt = datetime.fromisoformat(dt_iso)
        label = f"{pretty_dt(dt)} — {role_label(role)} — {volunteer_name or '—'} (assignment_id={assignment_id})"
        assignments.append((label, int(assignment_id)))

if not assignments:
    st.info(
        "Sem escalas encontradas nos próximos 30 dias. Gere a escala primeiro."
        if lang == "pt"
        else "No assignments found in the next 30 days. Generate the schedule first."
    )
else:
    assign_label = st.selectbox(
        t("swap.pick") if "swap.pick" else ("Selecione a escala" if lang == "pt" else "Pick assignment"),
        [a[0] for a in assignments]
    )
    assignment_id = [a[1] for a in assignments if a[0] == assign_label][0]

    requester = st.selectbox(
        "Quem está pedindo a troca? / Who is requesting?",
        vol_names_nonempty,
    )
    requester_id = vol_by_name.get(requester)

    replacement = st.selectbox(
        "Quem vai substituir? / Who will sub?",
        vol_names_nonempty,
    )
    replacement_id = vol_by_name.get(replacement)

    reason = st.text_area(
        t("swap.reason") if "swap.reason" else ("Motivo / Reason",),
        placeholder=("Ex: vou viajar / I’ll be traveling") if lang != "pt" else "Ex: vou viajar"
    )

    if st.button(t("swap.submit") if "swap.submit" else ("Enviar pedido" if lang == "pt" else "Submit request")):
        if requester_id == replacement_id:
            st.error(
                "Solicitante e substituto não podem ser a mesma pessoa."
                if lang == "pt" else
                "Requester and replacement cannot be the same person."
            )
        else:
            # Create request in DB
            create_swap_request(assignment_id, requester_id, replacement_id, (reason or "").strip())

            # Build email using assignment details
            details = get_assignment_details(int(assignment_id))
            if details:
                _aid, _sid, dt_iso, role, _vol_id, assigned_name = details
                service_dt = datetime.fromisoformat(dt_iso)

                subject = (
                    f"🔁 Pedido de troca — {service_dt.strftime('%d/%m %H:%M')}"
                    if lang == "pt" else
                    f"🔁 Swap request — {service_dt.strftime('%b %d %H:%M')}"
                )

                body = (
                    f"Novo pedido de troca:\n\n"
                    f"📅 Culto: {service_dt.strftime('%d/%m/%Y %H:%M')}\n"
                    f"🎛️ Função: {role_label(role)}\n"
                    f"👤 Escalado atual: {assigned_name or '—'}\n"
                    f"🙋 Quem pede: {requester}\n"
                    f"✅ Substituto: {replacement}\n"
                    f"📝 Motivo: {(reason or '—').strip()}\n\n"
                    f"Acesse o sistema para aprovar/rejeitar."
                ) if lang == "pt" else (
                    f"New swap request:\n\n"
                    f"📅 Service: {service_dt.strftime('%b %d, %Y %H:%M')}\n"
                    f"🎛️ Role: {role_label(role)}\n"
                    f"👤 Currently assigned: {assigned_name or '—'}\n"
                    f"🙋 Requester: {requester}\n"
                    f"✅ Replacement: {replacement}\n"
                    f"📝 Reason: {(reason or '—').strip()}\n\n"
                    f"Open the system to approve/reject."
                )

                try:
                    send_email(subject, body, to_email="plsb802@gmail.com")
                    st.success(
                        "Pedido enviado! E-mail notificado."
                        if lang == "pt" else
                        "Request submitted! Email sent."
                    )
                except Exception as e:
                    st.warning(
                        f"Pedido criado, mas falhou ao enviar e-mail: {e}"
                        if lang == "pt" else
                        f"Request created, but failed to send email: {e}"
                    )
            else:
                st.success(t("swap.submitted") if "swap.submitted" else ("Pedido enviado!" if lang == "pt" else "Request submitted!"))

# If not admin, stop here (they can only request swaps)
if not is_admin():
    st.divider()
    st.info(
        "Você pode solicitar trocas acima. Apenas admins podem editar a escala e aprovar pedidos."
        if lang == "pt"
        else "You can submit swap requests above. Only admins can edit schedules and approve requests."
    )
    st.stop()

# =====================================================
# ADMIN: Edit Schedule
# =====================================================
st.write("")
st.write("")

st.divider()
st.subheader(("⚙️ Admin — Editar escala" if lang == "pt" else "⚙️ Admin — Edit schedule"))

c1, c2 = st.columns(2)
with c1:
    year = st.number_input(t("gen.year"), min_value=2020, max_value=2100, value=datetime.now().year, step=1)
with c2:
    month = st.number_input(t("gen.month"), min_value=1, max_value=12, value=datetime.now().month, step=1)

services = list_services_in_month(int(year), int(month))
if not services:
    st.info("Sem cultos neste mês / No services this month. Generate first.")
    st.stop()

def pretty_service_label(service_id: int, dt_iso: str) -> str:
    dt = datetime.fromisoformat(dt_iso)
    return f"{pretty_dt(dt)}  (id={service_id})"

service_map = {pretty_service_label(sid, dt_iso): int(sid) for sid, dt_iso in services}
labels = list(service_map.keys())

selected_label = st.selectbox(t("edit.select_service"), labels)
sid = service_map[selected_label]

current = get_assignments_for_service(sid)
cur_map = {role: (vol_id, (vol_name or "")) for role, vol_id, vol_name in current}

# Ensure all roles exist
for r in ["OBS", "FIXED", "MOBILE"]:
    cur_map.setdefault(r, (None, ""))

st.subheader("👥 Time atual" if lang == "pt" else "👥 Current team")

obs_name = cur_map["OBS"][1] or "—"
fix_name = cur_map["FIXED"][1] or "—"
mob_name = cur_map["MOBILE"][1] or "—"

cc1, cc2, cc3 = st.columns(3)
with cc1:
    st.markdown("### 🎛️ OBS")
    st.markdown(f"**{obs_name}**")
with cc2:
    st.markdown("### 📷 " + ("CÂMERA FIXA" if lang == "pt" else "FIXED"))
    st.markdown(f"**{fix_name}**")
with cc3:
    st.markdown("### 📱 " + ("CÂMERA MÓVEL" if lang == "pt" else "MOBILE"))
    st.markdown(f"**{mob_name}**")

team_df = pd.DataFrame([
    {"Role": role_label("OBS"), "Volunteer": obs_name},
    {"Role": role_label("FIXED"), "Volunteer": fix_name},
    {"Role": role_label("MOBILE"), "Volunteer": mob_name},
])
st.dataframe(team_df, use_container_width=True, hide_index=True)

missing = [r for r in ["OBS", "FIXED", "MOBILE"] if (cur_map[r][1] or "").strip() == ""]
if missing:
    st.warning(
        ("Faltando atribuição para: " + ", ".join([role_label(r) for r in missing]))
        if lang == "pt"
        else ("Missing assignments for: " + ", ".join([role_label(r) for r in missing]))
    )

def index_for(role: str) -> int:
    current_name = cur_map.get(role, (None, ""))[1]
    return vol_names.index(current_name) if current_name in vol_names else 0

st.subheader(t("edit.set"))

new_obs = st.selectbox("OBS", vol_names, index=index_for("OBS"))
new_fix = st.selectbox("FIXED", vol_names, index=index_for("FIXED"))
new_mob = st.selectbox("MOBILE", vol_names, index=index_for("MOBILE"))

if st.button(t("edit.save_rebuild")):
    upsert_assignment(sid, "OBS", vol_by_name[new_obs])
    upsert_assignment(sid, "FIXED", vol_by_name[new_fix])
    upsert_assignment(sid, "MOBILE", vol_by_name[new_mob])

    rebuild_reminders_for_month(int(year), int(month))
    st.success(t("edit.saved"))

# =====================================================
# ADMIN: Pending swap requests (approve/apply/reject)
# =====================================================
st.write("")
st.write("")

st.divider()
st.subheader("🔁 Solicitações de troca pendentes" if lang == "pt" else "🔁 Pending swap requests")

pending = list_swap_requests(status="PENDING")
if not pending:
    st.info("Nenhuma solicitação pendente." if lang == "pt" else "No pending requests.")
else:
    df = pd.DataFrame(
        pending,
        columns=[
            "req_id", "status", "reason", "created_at",
            "assignment_id", "role", "dt_iso",
            "assigned_to", "requested_by",
            "replacement_id", "replacement_name",
        ]
    )
    st.dataframe(df, use_container_width=True)

    # select a request
    req_labels = []
    req_map = {}
    for r in pending:
        req_id, _status, reason, created_at, assignment_id, role, dt_iso, assigned_to, requested_by, replacement_id, replacement_name = r
        dt = datetime.fromisoformat(dt_iso)
        label = f"#{req_id} — {pretty_dt(dt)} — {role_label(role)} — {assigned_to or '—'} → {replacement_name or '—'}"
        req_labels.append(label)
        req_map[label] = int(req_id)

    selected_req_label = st.selectbox("Selecione uma solicitação / Pick a request", req_labels)
    selected_req_id = req_map[selected_req_label]

    selected_row = next(r for r in pending if int(r[0]) == int(selected_req_id))
    req_id, _status, reason, created_at, assignment_id, role, dt_iso, assigned_to, requested_by, replacement_id, replacement_name = selected_row

    st.caption(
        (f"Motivo: {reason or '—'} | Solicitante: {requested_by or '—'} | Substituto: {replacement_name or '—'}")
        if lang == "pt" else
        (f"Reason: {reason or '—'} | Requested by: {requested_by or '—'} | Replacement: {replacement_name or '—'}")
    )

    details = get_assignment_details(int(assignment_id))
    if not details:
        st.error("Assignment não encontrado no banco / Assignment not found.")
        st.stop()

    _aid, _service_id, _dt_iso, _role, _vol_id, _vol_name = details
    service_dt = datetime.fromisoformat(_dt_iso)

    # Admin can override replacement, but default is the requested replacement
    default_name = replacement_name or (_vol_name or "")
    default_index = vol_names.index(default_name) if default_name in vol_names else 0

    replacement_override = st.selectbox(
        ("Substituto (padrão = solicitado)" if lang == "pt" else "Replacement (default = requested)"),
        vol_names,
        index=default_index
    )
    replacement_override_id = vol_by_name.get(replacement_override)

    cA, cB = st.columns(2)
    with cA:
        if st.button("✅Aprovar e aplicar troca" if lang == "pt" else "✅ Approve & apply swap"):
            set_assignment_volunteer_by_id(int(assignment_id), replacement_override_id)
            resolve_swap_request(int(req_id), "APPROVED", "admin")
            rebuild_reminders_for_month(service_dt.year, service_dt.month)
            st.success("Troca aplicada e aprovada!" if lang == "pt" else "Swap applied and approved!")

    with cB:
        if st.button("❌Rejeitar" if lang == "pt" else "❌ Reject"):
            resolve_swap_request(int(req_id), "REJECTED", "admin")
            st.success("Solicitação rejeitada." if lang == "pt" else "Request rejected.")