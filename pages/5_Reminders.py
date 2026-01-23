import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

from src.db import list_reminders, mark_reminder_sent, list_schedule_between
from src.auth import is_admin
from src.i18n import t, get_lang
from src.emailer import send_email  # <-- NEW

st.title(t("rem.title"))

lang = get_lang()

status = st.selectbox(t("rem.filter"), ["PENDING", "SENT", "FAILED", "CANCELLED", "ALL"])
rows = list_reminders(status=None if status == "ALL" else status)

df = pd.DataFrame(
    rows,
    columns=[
        "id", "status", "send_at_iso", "attempts",
        "last_error", "service_dt", "role", "name", "phone"
    ]
)
st.dataframe(df, use_container_width=True)

st.caption(t("rem.admin_note"))

if not is_admin():
    st.warning(t("common.admin_required"))
    st.stop()

# Build a map so we can lookup reminder details by id
rem_by_id = {int(r[0]): r for r in rows}

# =========================
# Admin: Send reminder email now
# =========================
st.subheader("📧 Enviar lembrete por e-mail" if lang == "pt" else "📧 Send reminder by email")

rid = st.number_input("Reminder ID", min_value=1, step=1)

def reminder_email_subject(service_dt: datetime, role: str) -> str:
    if lang == "pt":
        return f"📺 Lembrete de escala — {service_dt.strftime('%d/%m %H:%M')} ({role})"
    return f"📺 Schedule reminder — {service_dt.strftime('%b %d %H:%M')} ({role})"

def reminder_email_body(service_dt: datetime, role: str, name: str, phone: str | None) -> str:
    if lang == "pt":
        return (
            f"Olá!\n\n"
            f"Lembrete da escala de transmissão:\n\n"
            f"📅 Data/Hora: {service_dt.strftime('%d/%m/%Y %H:%M')}\n"
            f"🎛️ Função: {role}\n"
            f"👤 Voluntário: {name or '—'}\n"
            f"📞 Telefone: {phone or '—'}\n\n"
            f"Obs: Este e-mail foi gerado manualmente pela aba de Reminders.\n"
        )
    return (
        f"Hello!\n\n"
        f"Streaming schedule reminder:\n\n"
        f"📅 Date/Time: {service_dt.strftime('%b %d, %Y %H:%M')}\n"
        f"🎛️ Role: {role}\n"
        f"👤 Volunteer: {name or '—'}\n"
        f"📞 Phone: {phone or '—'}\n\n"
        f"Note: This email was manually generated from the Reminders tab.\n"
    )

c1, c2 = st.columns(2)

with c1:
    if st.button("📨 Enviar e marcar como SENT" if lang == "pt" else "📨 Send & mark as SENT"):
        if int(rid) not in rem_by_id:
            st.error("Reminder ID inválido para o filtro atual." if lang == "pt" else "Invalid Reminder ID for current filter.")
        else:
            _id, _status, _send_at, _attempts, _err, _service_dt, _role, _name, _phone = rem_by_id[int(rid)]
            service_dt = datetime.fromisoformat(_service_dt)

            try:
                subject = reminder_email_subject(service_dt, _role)
                body = reminder_email_body(service_dt, _role, _name, _phone)
                send_email(subject, body, to_email="plsb802@gmail.com")
                mark_reminder_sent(int(rid))
                st.success("E-mail enviado e reminder marcado como SENT." if lang == "pt" else "Email sent and reminder marked as SENT.")
            except Exception as e:
                st.error(f"Falha ao enviar e-mail: {e}" if lang == "pt" else f"Failed to send email: {e}")

with c2:
    if st.button(t("rem.simulate")):
        mark_reminder_sent(int(rid))
        st.success("OK.")

# =====================================================
# Generate next service reminder (group message) + email
# =====================================================
st.divider()
st.subheader(
    "📣 Gerar lembrete do próximo culto (para grupo)"
    if lang == "pt" else
    "📣 Generate next service reminder (for group)"
)

LOOKAHEAD_DAYS = 14

def format_next_service_message(service_dt: datetime, roles: dict[str, str]) -> str:
    obs = roles.get("OBS") or "—"
    fixed = roles.get("FIXED") or "—"
    mobile = roles.get("MOBILE") or "—"

    if lang == "pt":
        dow = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][service_dt.weekday()]
        return (
            f"⏰ *LEMBRETE — Próximo culto*\n"
            f"📅 *{dow}, {service_dt.strftime('%d/%m/%Y')} — {service_dt.strftime('%H:%M')}*\n\n"
            f"🎛️ *OBS:* {obs}\n"
            f"📷 *CÂMERA FIXA:* {fixed}\n"
            f"📱 *CÂMERA MÓVEL:* {mobile}\n\n"
            f"✅ Confirmem presença reagindo com 👍.\n"
            f"Se alguém tiver impedimento, solicite troca com antecedência."
        )
    else:
        dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][service_dt.weekday()]
        return (
            f"⏰ *REMINDER — Next service*\n"
            f"📅 *{dow}, {service_dt.strftime('%b %d, %Y')} — {service_dt.strftime('%H:%M')}*\n\n"
            f"🎛️ *OBS:* {obs}\n"
            f"📷 *FIXED CAMERA:* {fixed}\n"
            f"📱 *MOBILE CAMERA:* {mobile}\n\n"
            f"✅ Please confirm by replying or reacting with 👍.\n"
            f"If you can’t make it, request a swap as soon as possible."
        )

def get_next_service_with_roles():
    now = datetime.now()
    end = now + timedelta(days=LOOKAHEAD_DAYS)

    sched = list_schedule_between(now.isoformat(), end.isoformat())
    if not sched:
        return None, None

    services = defaultdict(lambda: {"OBS": "", "FIXED": "", "MOBILE": ""})

    for service_id, dt_iso, assignment_id, role, volunteer_name in sched:
        if role:
            services[dt_iso][role] = volunteer_name or ""

    for dt_iso in sorted(services.keys()):
        dt = datetime.fromisoformat(dt_iso)
        if dt >= now:
            return dt, services[dt_iso]

    return None, None

# Keep message in session state so user can email after generating
if "next_group_msg" not in st.session_state:
    st.session_state["next_group_msg"] = ""
if "next_group_dt" not in st.session_state:
    st.session_state["next_group_dt"] = None

cA, cB = st.columns(2)

with cA:
    if st.button("⚡ Gerar agora" if lang == "pt" else "⚡ Generate now"):
        service_dt, roles = get_next_service_with_roles()
        if not service_dt:
            st.warning(
                "Nenhum culto encontrado nos próximos dias. Gere a escala primeiro."
                if lang == "pt" else
                "No upcoming service found. Generate the schedule first."
            )
        else:
            msg = format_next_service_message(service_dt, roles)
            st.session_state["next_group_msg"] = msg
            st.session_state["next_group_dt"] = service_dt
            st.success(
                "Mensagem gerada! Copie e cole no grupo, ou envie por e-mail para você."
                if lang == "pt" else
                "Message generated! Copy/paste it into the group, or email it to yourself."
            )

with cB:
    if st.button("📧 Enviar por e-mail para mim" if lang == "pt" else "📧 Email it to me"):
        msg = st.session_state.get("next_group_msg") or ""
        dtv = st.session_state.get("next_group_dt")
        if not msg or not dtv:
            st.warning("Gere a mensagem primeiro." if lang == "pt" else "Generate the message first.")
        else:
            try:
                subj = (
                    f"📣 Mensagem para grupo — {dtv.strftime('%d/%m %H:%M')}"
                    if lang == "pt"
                    else f"📣 Group message — {dtv.strftime('%b %d %H:%M')}"
                )
                send_email(subj, msg, to_email="plsb802@gmail.com")
                st.success("E-mail enviado!" if lang == "pt" else "Email sent!")
            except Exception as e:
                st.error(f"Falha ao enviar e-mail: {e}" if lang == "pt" else f"Failed to send email: {e}")

st.text_area(
    "Mensagem / Message",
    value=st.session_state.get("next_group_msg", ""),
    height=260
)

st.caption(
    "Dica: se aparecer '—', aquela função ainda não foi atribuída."
    if lang == "pt" else
    "Tip: if you see '—', that role is not assigned yet."
)