import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

from src.db import (
    list_reminders,
    mark_reminder_sent,
    list_schedule_between,
    engine,
    volunteers,
    services,
    assignments,
    reminder_jobs,
)
from src.auth import is_admin
from src.i18n import t, get_lang
from src.emailer import send_email

from sqlalchemy import select, update

from src.reminders.runner import send_due_emails_deduped

st.title(t("rem.title"))
lang = get_lang()

# =========================
# Helpers
# =========================

def _format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


# =========================
# Query due reminders (join)
# =========================
def list_due_reminders_for_email(now: datetime | None = None):
    """
    PENDING reminders whose send_at_iso <= now, joined with service + volunteer info.
    Returns rows:
      (reminder_id, send_at_iso, service_dt_iso, role, volunteer_id, volunteer_name, volunteer_email, volunteer_phone)
    """
    now = now or datetime.utcnow()
    now_iso = now.isoformat()

    stmt = (
        select(
            reminder_jobs.c.id.label("reminder_id"),
            reminder_jobs.c.send_at_iso,
            services.c.dt_iso.label("service_dt_iso"),
            assignments.c.role,
            volunteers.c.id.label("volunteer_id"),
            volunteers.c.name.label("volunteer_name"),
            volunteers.c.email.label("volunteer_email"),
            volunteers.c.phone.label("volunteer_phone"),
        )
        .select_from(
            reminder_jobs
            .join(assignments, assignments.c.id == reminder_jobs.c.assignment_id)
            .join(services, services.c.id == assignments.c.service_id)
            .join(volunteers, volunteers.c.id == assignments.c.volunteer_id)
        )
        .where(reminder_jobs.c.status == "PENDING")
        .where(reminder_jobs.c.send_at_iso <= now_iso)
        .order_by(services.c.dt_iso.asc())
    )

    with engine().connect() as conn:
        return conn.execute(stmt).fetchall()


def mark_reminders_sent(reminder_ids: list[int]):
    if not reminder_ids:
        return
    with engine().begin() as conn:
        conn.execute(
            update(reminder_jobs)
            .where(reminder_jobs.c.id.in_(reminder_ids))
            .values(status="SENT", sent_at=datetime.utcnow().isoformat())
        )


# =========================
# Table / Filters (FIX: 9 vs 10 cols)
# =========================
status = st.selectbox(t("rem.filter"), ["PENDING", "SENT", "FAILED", "CANCELLED", "ALL"])
rows = list_reminders(status=None if status == "ALL" else status)

# Detect schema by row length
cols_10 = ["id", "status", "send_at_iso", "attempts", "last_error", "service_dt", "role", "name", "email", "phone"]
cols_9  = ["id", "status", "send_at_iso", "attempts", "last_error", "service_dt", "role", "name", "email"]

if rows:
    width = len(rows[0])
else:
    width = 10  # default

if width == 9:
    df = pd.DataFrame(rows, columns=cols_9)
elif width == 10:
    df = pd.DataFrame(rows, columns=cols_10)
else:
    # fallback: create generic columns
    df = pd.DataFrame(rows)
    st.warning(
        f"Schema inesperado em list_reminders(): {width} colunas. Ajuste a função ou este arquivo."
        if lang == "pt" else
        f"Unexpected schema from list_reminders(): {width} columns. Update the function or this file."
    )

st.dataframe(df, use_container_width=True)
st.caption(t("rem.admin_note"))

# =========================
# Non-admin stop
# =========================
if not is_admin():
    st.warning(t("common.admin_required"))
    st.stop()

rem_by_id = {int(r[0]): r for r in rows}

# =========================
# Admin: Send ONE reminder email (single reminder id)
# =========================
st.divider()
st.subheader("📧 " + ("Enviar lembrete por e-mail (1 reminder)" if lang == "pt" else "Send reminder by email (1 reminder)"))

rid = st.number_input("Reminder ID", min_value=1, step=1)

def single_reminder_subject(service_dt: datetime, role: str) -> str:
    if lang == "pt":
        return f"🚨 Lembrete de escala — {service_dt.strftime('%d/%m %H:%M')} ({role})"
    return f"🚨 Schedule reminder — {service_dt.strftime('%b %d %H:%M')} ({role})"

def single_reminder_body(service_dt: datetime, role: str, name: str, email: str | None, phone: str | None) -> str:
    if lang == "pt":
        return (
            f"Olá, {name}!\n\n"
            f"Lembrete da escala de transmissão:\n\n"
            f"📅 Data/Hora: {service_dt.strftime('%d/%m/%Y %H:%M')}\n"
            f"🎛️ Função: {role}\n"
            f"📧 Email: {email or '—'}\n"
            f"📞 Telefone: {phone or '—'}\n\n"
            f"Obs: Este e-mail foi gerado manualmente pela aba de Reminders.\n"
        )
    return (
        f"Hello, {name}!\n\n"
        f"Streaming schedule reminder:\n\n"
        f"📅 Date/Time: {service_dt.strftime('%b %d, %Y %H:%M')}\n"
        f"🎛️ Role: {role}\n"
        f"📧 Email: {email or '—'}\n"
        f"📞 Phone: {phone or '—'}\n\n"
        f"Note: This email was manually generated from the Reminders tab.\n"
    )

c1, c2 = st.columns(2)

with c1:
    if st.button("📨 " + ("Enviar e marcar como SENT" if lang == "pt" else "Send & mark as SENT")):
        if int(rid) not in rem_by_id:
            st.toast("ID inválido para o filtro atual." if lang == "pt" else "Invalid ID for current filter.", icon="⚠️")
        else:
            row = rem_by_id[int(rid)]
            # row can be 9 or 10 cols
            if len(row) == 9:
                _id, _status, _send_at, _attempts, _err, _service_dt, _role, _name, _email = row
                _phone = None
            else:
                _id, _status, _send_at, _attempts, _err, _service_dt, _role, _name, _email, _phone = row

            service_dt = datetime.fromisoformat(_service_dt)

            if not _email:
                st.toast("Sem e-mail cadastrado." if lang == "pt" else "No email set.", icon="⚠️")
            else:
                try:
                    subject = single_reminder_subject(service_dt, _role)
                    body = single_reminder_body(service_dt, _role, _name, _email, _phone)
                    send_email(subject, body, to_email=_email)
                    mark_reminder_sent(int(rid))
                    st.toast("Enviado ✅ e marcado como SENT." if lang == "pt" else "Sent ✅ and marked SENT.", icon="📧")
                    st.rerun()
                except Exception as e:
                    st.toast(f"Falha ao enviar: {e}" if lang == "pt" else f"Failed: {e}", icon="❌")

with c2:
    if st.button(t("rem.simulate")):
        mark_reminder_sent(int(rid))
        st.toast("OK ✅", icon="✅")
        st.rerun()

# =========================
# Admin: Send DUE reminders now (DEDUP per volunteer/day)
# =========================
st.divider()
st.subheader("⏱️ " + ("Enviar lembretes vencidos (sem duplicar no mesmo dia)" if lang == "pt" else "Send due reminders (dedup same-day)"))

if st.button("🚀 " + ("Enviar agora" if lang == "pt" else "Send now")):
    try:
        result = send_due_emails_deduped(now=datetime.utcnow())
        st.toast(
            (
                f"Enviado: {result['sent_emails']} | Marcados SENT: {result['marked_sent']} | Sem e-mail: {result['skipped_no_email']}"
            )
            if lang == "pt"
            else
            (
                f"Sent: {result['sent_emails']} | Marked SENT: {result['marked_sent']} | No email: {result['skipped_no_email']}"
            ),
            icon="📨",
        )
        st.rerun()
    except Exception as e:
        st.toast(f"Falha: {e}" if lang == "pt" else f"Failed: {e}", icon="❌")