from datetime import datetime
from src.pages_helpers.reminders_sender import send_due_emails_deduped

if __name__ == "__main__":
    # Use UTC to match your DB timestamps if you store ISO in UTC
    now = datetime.utcnow()
    result = send_due_emails_deduped(now=now)
    print(
        f"[{now.isoformat()}] sent_emails={result['sent_emails']} "
        f"marked_sent={result['marked_sent']} skipped_no_email={result['skipped_no_email']}"
    )