from dotenv import load_dotenv
from pathlib import Path
import os
import smtplib
from email.message import EmailMessage

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

host = os.getenv("SMTP_HOST")
port = int(os.getenv("SMTP_PORT", "587"))
user = os.getenv("SMTP_USER")
pwd  = os.getenv("SMTP_PASSWORD")
to   = os.getenv("NOTIFY_EMAIL")

msg = EmailMessage()
msg["Subject"] = "Church Scheduler SMTP test"
msg["From"] = user
msg["To"] = to
msg.set_content("If you received this, SMTP is working ✅")

with smtplib.SMTP(host, port) as s:
    s.starttls()
    s.login(user, pwd)
    s.send_message(msg)

print("Sent ✅")