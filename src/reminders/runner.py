from _pydatetime import _format_time
from datetime import datetime

from src.db import mark_reminders_sent, list_due_reminders_for_email
from src.emailer import send_email
from src.i18n import get_lang


def run_reminders_job():
    try:
        now = datetime.utcnow()
        result = send_due_emails_deduped(now=now)

        print(
            f"[REMINDERS] {now.isoformat()} | "
            f"sent={result['sent_emails']} "
            f"marked={result['marked_sent']} "
            f"skipped={result['skipped_no_email']}"
        )
    except Exception as e:
        print(f"[REMINDERS][ERROR] {e}")

def send_due_emails_deduped(now: datetime | None = None):
    """
    Sends emails for due reminders.
    Dedup rule: one email per (volunteer_id, service_day).
    Marks all reminders in that bucket as SENT.
    """
    due = list_due_reminders_for_email(now=now)
    if not due:
        return {"sent_emails": 0, "marked_sent": 0, "skipped_no_email": 0}

    buckets: dict[tuple[int, str], dict] = {}
    skipped_no_email = 0

    for (
        reminder_id,
        send_at_iso,
        service_dt_iso,
        role,
        volunteer_id,
        volunteer_name,
        volunteer_email,
        volunteer_phone,
    ) in due:
        if not volunteer_email:
            skipped_no_email += 1
            continue

        service_dt = datetime.fromisoformat(service_dt_iso)
        key = (int(volunteer_id), _day_key(service_dt))

        if key not in buckets:
            buckets[key] = {
                "volunteer_name": volunteer_name,
                "volunteer_email": volunteer_email,
                "day_dt": service_dt,
                "items": [],
                "reminder_ids": [],
            }

        buckets[key]["items"].append(
            {
                "service_dt_iso": service_dt_iso,
                "time_str": _format_time(service_dt),
                "role": role,
            }
        )
        buckets[key]["reminder_ids"].append(int(reminder_id))

    sent_emails = 0
    marked_sent = 0

    for _, bucket in buckets.items():
        vol_name = bucket["volunteer_name"]
        vol_email = bucket["volunteer_email"]
        day_dt = bucket["day_dt"]
        items = bucket["items"]
        reminder_ids = bucket["reminder_ids"]

        subject = reminder_email_subject(day_dt)
        body = reminder_email_body_for_day(vol_name, day_dt, items)

        send_email(subject, body, to_email=vol_email)
        sent_emails += 1

        mark_reminders_sent(reminder_ids)
        marked_sent += len(reminder_ids)

    return {"sent_emails": sent_emails, "marked_sent": marked_sent, "skipped_no_email": skipped_no_email}


def reminder_email_subject(service_dt: datetime) -> str:
    if get_lang() == "pt":
        return f"🚨Lembrete de escala — {service_dt.strftime('%d/%m')} (amanhã)"
    return f"🚨 Schedule reminder — {service_dt.strftime('%b %d')} (tomorrow)"

def reminder_email_body_for_day(vol_name: str, day: datetime, items: list[dict]) -> str:
    items_sorted = sorted(items, key=lambda x: x["service_dt_iso"])
    lines = "\n".join([f"- {it['time_str']} — {it['role']}" for it in items_sorted])

    if get_lang() == "pt":
        return (
            f"Olá, {vol_name}!\n\n"
            f"Você está escalado(a) para *amanhã* ({day.strftime('%d/%m/%Y')}):\n\n"
            f"{lines}\n\n"
            f"Se tiver algum impedimento, avise o quanto antes para tentarmos trocar.\n"
        )

    return (
        f"Hi {vol_name}!\n\n"
        f"You are scheduled for *tomorrow* ({day.strftime('%Y-%m-%d')}):\n\n"
        f"{lines}\n\n"
        f"If you can’t make it, please notify us ASAP so we can arrange a swap.\n"
    )

def _day_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")
