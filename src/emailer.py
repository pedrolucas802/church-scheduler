import os
import smtplib
from email.message import EmailMessage
from datetime import datetime


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL")


def send_email(subject: str, body: str, to_email: str | None = None):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        raise RuntimeError("SMTP is not configured")

    to_email = to_email or NOTIFY_EMAIL
    if not to_email:
        raise RuntimeError("No destination email")

    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)