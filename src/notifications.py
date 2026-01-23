from datetime import datetime

from src.emailer import send_email


def send_reminder_email(service_dt: datetime, role: str, volunteer_name: str):
    subject = f"📺 Lembrete de escala — {service_dt.strftime('%d/%m %H:%M')}"
    body = (
        f"Olá!\n\n"
        f"Este é um lembrete da escala de transmissão:\n\n"
        f"📅 Data/Hora: {service_dt.strftime('%d/%m/%Y %H:%M')}\n"
        f"🎛️ Função: {role}\n"
        f"👤 Responsável: {volunteer_name}\n\n"
        f"Caso não possa comparecer, solicite troca com antecedência.\n\n"
        f"— Sistema de Escalas"
    )
    send_email(subject, body)