from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reminders.runner import now_in_fortaleza_naive, send_due_whatsapp_reminders

if __name__ == "__main__":
    now = now_in_fortaleza_naive()
    result = send_due_whatsapp_reminders(now=now, lang="pt")
    print(
        f"[{now.isoformat()}] sent_whatsapp={result['sent_messages']} "
        f"marked_sent={result['marked_sent']} "
        f"skipped_no_phone={result['skipped_no_phone']} "
        f"failed_messages={result['failed_messages']}"
    )
