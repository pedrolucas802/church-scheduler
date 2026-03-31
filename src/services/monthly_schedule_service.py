from __future__ import annotations

from datetime import datetime

from src.db import get_assignments_for_service, list_services_in_month, list_volunteers
from src.services.evolution_api_service import (
    EvolutionAPIService,
    normalize_whatsapp_number,
)

ROLE_PT = {"OBS": "OBS", "FIXED": "CÂMERA FIXA", "MOBILE": "CÂMERA MÓVEL"}
ROLE_EN = {"OBS": "OBS", "FIXED": "FIXED CAMERA", "MOBILE": "MOBILE CAMERA"}
MONTHS_PT = [
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
DOW_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
DOW_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def role_label(role: str, lang: str = "pt") -> str:
    labels = ROLE_PT if lang == "pt" else ROLE_EN
    return labels.get(role, role)


def month_year_label(year: int, month: int, lang: str = "pt") -> str:
    names = MONTHS_PT if lang == "pt" else MONTHS_EN
    return f"{names[month - 1]}/{year}" if lang == "pt" else f"{names[month - 1]} {year}"


def collect_month_schedule_notifications(year: int, month: int):
    phone_by_id: dict[int, str | None] = {}
    for vid, _name, _email, phone, *_rest in list_volunteers(active_only=False):
        phone_by_id[int(vid)] = phone

    buckets: dict[int, dict] = {}

    for service_id, dt_iso in list_services_in_month(year, month):
        service_dt = datetime.fromisoformat(dt_iso)
        for role, volunteer_id, volunteer_name in get_assignments_for_service(service_id):
            if volunteer_id is None or not volunteer_name:
                continue

            volunteer_id = int(volunteer_id)
            if volunteer_id not in buckets:
                buckets[volunteer_id] = {
                    "volunteer_id": volunteer_id,
                    "volunteer_name": volunteer_name,
                    "phone": phone_by_id.get(volunteer_id),
                    "items": [],
                }

            buckets[volunteer_id]["items"].append(
                {
                    "service_dt_iso": dt_iso,
                    "service_dt": service_dt,
                    "role": role,
                }
            )

    return sorted(buckets.values(), key=lambda bucket: bucket["volunteer_name"].lower())


def build_month_schedule_whatsapp_text(
    vol_name: str,
    year: int,
    month: int,
    items: list[dict],
    lang: str = "pt",
) -> str:
    items_sorted = sorted(items, key=lambda item: item["service_dt_iso"])
    dow_names = DOW_PT if lang == "pt" else DOW_EN
    lines = "\n".join(
        (
            f"- {dow_names[item['service_dt'].weekday()]} "
            f"{item['service_dt'].strftime('%d/%m %H:%M')} — {role_label(item['role'], lang)}"
        )
        if lang == "pt"
        else (
            f"- {dow_names[item['service_dt'].weekday()]} "
            f"{item['service_dt'].strftime('%Y-%m-%d %H:%M')} — {role_label(item['role'], lang)}"
        )
        for item in items_sorted
    )

    if lang == "pt":
        return (
            f"Olá, {vol_name}!\n\n"
            f"Segue sua escala de transmissão de {month_year_label(year, month, lang)}.\n\n"
            "Confira os cultos e horários abaixo:\n\n"
            f"{lines}\n\n"
            "Se perceber qualquer conflito ou imprevisto, avise o quanto antes para conseguirmos ajustar.\n\n"
            "Obrigado por servir."
        )

    return (
        f"Hi {vol_name}!\n\n"
        f"Here is your streaming schedule for {month_year_label(year, month, lang)}.\n\n"
        "Please check the services and times below:\n\n"
        f"{lines}\n\n"
        "If you notice any conflict or issue, please let us know as soon as possible so we can adjust it.\n\n"
        "Thanks for serving."
    )


def send_month_schedule_alerts(year: int, month: int, lang: str = "pt"):
    recipients = collect_month_schedule_notifications(year, month)
    if not recipients:
        return {
            "total_recipients": 0,
            "sent_messages": 0,
            "skipped_no_phone": 0,
            "failed_messages": 0,
        }

    service = EvolutionAPIService.from_env()
    if service is None:
        missing = ", ".join(EvolutionAPIService.missing_env_vars())
        raise RuntimeError(f"Missing Evolution API config: {missing}")

    sent_messages = 0
    skipped_no_phone = 0
    failed_messages = 0

    for recipient in recipients:
        destination_number = normalize_whatsapp_number(recipient["phone"])
        if not destination_number:
            skipped_no_phone += 1
            continue

        response = service.send_text(
            number=destination_number,
            text=build_month_schedule_whatsapp_text(
                vol_name=recipient["volunteer_name"],
                year=year,
                month=month,
                items=recipient["items"],
                lang=lang,
            ),
        )
        if response.success:
            sent_messages += 1
            continue

        failed_messages += 1
        print(
            "[SCHEDULE ALERTS][WARN] Failed WhatsApp send "
            f"to {recipient['volunteer_name']} ({recipient['phone']}): {response.error}"
        )

    return {
        "total_recipients": len(recipients),
        "sent_messages": sent_messages,
        "skipped_no_phone": skipped_no_phone,
        "failed_messages": failed_messages,
    }
