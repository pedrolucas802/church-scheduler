from src.reminders.runner import send_due_whatsapp_reminders


def send_due_reminder_emails(lang: str = "pt"):
    return send_due_whatsapp_reminders(lang=lang)


def send_due_reminder_whatsapp(lang: str = "pt"):
    return send_due_whatsapp_reminders(lang=lang)
