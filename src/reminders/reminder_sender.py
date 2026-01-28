from collections import defaultdict
from datetime import datetime
from src.db import list_due_reminders_for_email, mark_reminders_sent
from src.emailer import send_email

def _service_day_key(service_dt_iso: str) -> str:
    dt = datetime.fromisoformat(service_dt_iso)
    return dt.strftime("%Y-%m-%d")

def send_due_reminder_emails(lang: str = "en"):
    rows = list_due_reminders_for_email()

    # group by volunteer + day
    buckets = defaultdict(list)
    for rid, send_at_iso, service_dt, role, vid, name, email in rows:
        if not email:
            # no email -> skip for now (or mark FAILED later if you prefer)
            continue
        key = (int(vid), _service_day_key(service_dt))
        buckets[key].append((int(rid), service_dt, role, name, email))

    sent_ids: list[int] = []

    for (vid, day), items in buckets.items():
        # sort services within the day
        items_sorted = sorted(items, key=lambda x: x[1])

        # recipient info (same for all items)
        _, _, _, name, email = items_sorted[0]

        # build one consolidated message
        lines = []
        for _, service_dt, role, *_ in items_sorted:
            dt = datetime.fromisoformat(service_dt)
            lines.append(f"- {dt.strftime('%d/%m %H:%M')} — {role}")

        if lang == "pt":
            subject = f"📺 Lembrete de escala — {day}"
            body = (
                f"Olá, {name}!\n\n"
                f"Você está escalado(a) para os cultos de amanhã:\n\n"
                + "\n".join(lines) +
                "\n\nSe tiver algum impedimento, avise o quanto antes para tentarmos trocar.\n"
            )
        else:
            subject = f"📺 Schedule reminder — {day}"
            body = (
                f"Hi {name}!\n\n"
                f"You are scheduled for tomorrow’s services:\n\n"
                + "\n".join(lines) +
                "\n\nIf you can’t make it, please notify us ASAP so we can arrange a swap.\n"
            )

        send_email(subject, body, to_email=email)

        # mark all reminders in this bucket as sent
        sent_ids.extend([rid for rid, *_ in items_sorted])

    mark_reminders_sent(sent_ids)

    return {"due_rows": len(rows), "sent_reminders": len(sent_ids), "sent_emails": len(buckets)}