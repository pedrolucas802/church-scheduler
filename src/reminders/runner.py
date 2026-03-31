from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.db import list_due_reminders_for_whatsapp, mark_reminders_sent
from src.services.evolution_api_service import EvolutionAPIService, normalize_whatsapp_number

FORTALEZA_TZ = ZoneInfo("America/Fortaleza")

ROLE_PT = {"OBS": "OBS", "FIXED": "CÂMERA FIXA", "MOBILE": "CÂMERA MÓVEL"}
ROLE_EN = {"OBS": "OBS", "FIXED": "FIXED CAMERA", "MOBILE": "MOBILE CAMERA"}


def now_in_fortaleza_naive() -> datetime:
    return datetime.now(FORTALEZA_TZ).replace(tzinfo=None)


def run_reminders_job():
    now = now_in_fortaleza_naive()

    try:
        result = send_due_whatsapp_reminders(now=now, lang="pt")
        print(
            f"[REMINDERS] {now.isoformat()} | "
            f"sent_whatsapp={result['sent_messages']} "
            f"marked={result['marked_sent']} "
            f"skipped_no_phone={result['skipped_no_phone']} "
            f"failed={result['failed_messages']}"
        )
    except Exception as exc:
        print(f"[REMINDERS][ERROR] {exc}")


def send_due_whatsapp_reminders(now: datetime | None = None, lang: str = "pt"):
    due = list_due_reminders_for_whatsapp(now=now or now_in_fortaleza_naive())
    if not due:
        return {
            "sent_messages": 0,
            "marked_sent": 0,
            "skipped_no_phone": 0,
            "failed_messages": 0,
        }

    service = EvolutionAPIService.from_env()
    if service is None:
        missing = ", ".join(EvolutionAPIService.missing_env_vars())
        raise RuntimeError(f"Missing Evolution API config: {missing}")

    buckets: dict[tuple[int, str], dict] = {}
    skipped_no_phone = 0

    for (
        reminder_id,
        _send_at_iso,
        service_dt_iso,
        role,
        volunteer_id,
        volunteer_name,
        volunteer_phone,
    ) in due:
        if not volunteer_phone:
            skipped_no_phone += 1
            continue

        service_dt = datetime.fromisoformat(service_dt_iso)
        key = (int(volunteer_id), _day_key(service_dt))

        if key not in buckets:
            buckets[key] = {
                "volunteer_name": volunteer_name,
                "volunteer_phone": volunteer_phone,
                "day_dt": service_dt,
                "items": [],
                "reminder_ids": [],
            }

        buckets[key]["items"].append(
            {
                "service_dt_iso": service_dt_iso,
                "time_str": service_dt.strftime("%H:%M"),
                "role": role,
            }
        )
        buckets[key]["reminder_ids"].append(int(reminder_id))

    sent_messages = 0
    marked_sent = 0
    failed_messages = 0

    for bucket in buckets.values():
        destination_number = normalize_whatsapp_number(bucket["volunteer_phone"])
        if not destination_number:
            skipped_no_phone += 1
            continue

        text = build_reminder_whatsapp_text(
            vol_name=bucket["volunteer_name"],
            day=bucket["day_dt"],
            items=bucket["items"],
            lang=lang,
        )
        response = service.send_text(number=destination_number, text=text)
        if not response.success:
            failed_messages += 1
            print(
                "[REMINDERS][WARN] Failed WhatsApp send "
                f"to {bucket['volunteer_name']} "
                f"({destination_number}): {response.error}"
            )
            continue

        sent_messages += 1
        mark_reminders_sent(bucket["reminder_ids"])
        marked_sent += len(bucket["reminder_ids"])

    return {
        "sent_messages": sent_messages,
        "marked_sent": marked_sent,
        "skipped_no_phone": skipped_no_phone,
        "failed_messages": failed_messages,
    }


def build_reminder_whatsapp_text(vol_name: str, day: datetime, items: list[dict], lang: str = "pt") -> str:
    items_sorted = sorted(items, key=lambda item: item["service_dt_iso"])
    lines = "\n".join(
        f"- {item['time_str']} — {role_label(item['role'], lang)}"
        for item in items_sorted
    )

    if lang == "pt":
        return (
            f"Olá, {vol_name}!\n\n"
            "Passando para lembrar da sua escala de transmissão.\n\n"
            f"Data: {day.strftime('%d/%m/%Y')}\n"
            "Você está escalado nestes horários:\n\n"
            f"{lines}\n\n"
            "Se surgir qualquer imprevisto, avise o quanto antes para conseguirmos ajustar.\n\n"
            "Obrigado por servir."
        )

    return (
        f"Hi {vol_name}!\n\n"
        "Just a quick reminder about your streaming schedule.\n\n"
        f"Date: {day.strftime('%Y-%m-%d')}\n"
        "You are scheduled for:\n\n"
        f"{lines}\n\n"
        "If anything comes up, please let us know as soon as possible so we can adjust it.\n\n"
        "Thanks for serving."
    )


def role_label(role: str, lang: str = "pt") -> str:
    labels = ROLE_PT if lang == "pt" else ROLE_EN
    return labels.get(role, role)


def _day_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")
