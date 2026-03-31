from __future__ import annotations

import os
import re
from datetime import datetime

from src.services.evolution_api_service import (
    EvolutionAPIService,
    normalize_whatsapp_number,
)

ROLE_PT = {"OBS": "OBS", "FIXED": "CÂMERA FIXA", "MOBILE": "CÂMERA MÓVEL"}
ROLE_EN = {"OBS": "OBS", "FIXED": "FIXED CAMERA", "MOBILE": "MOBILE CAMERA"}
DOW_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
DOW_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def admin_edit_alert_numbers_from_env() -> list[str]:
    raw = (os.getenv("ADMIN_EDIT_ALERT_WHATSAPP_NUMBERS") or "").strip()
    if not raw:
        return []

    numbers: list[str] = []
    seen: set[str] = set()
    for piece in re.split(r"[\s,;]+", raw):
        normalized = normalize_whatsapp_number(piece)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        numbers.append(normalized)
    return numbers


def role_label(role: str, lang: str = "pt") -> str:
    labels = ROLE_PT if lang == "pt" else ROLE_EN
    return labels.get(role, role)


def pretty_dt(dt: datetime, lang: str = "pt") -> str:
    dow_names = DOW_PT if lang == "pt" else DOW_EN
    if lang == "pt":
        return f"{dow_names[dt.weekday()]} {dt.strftime('%d/%m/%Y %H:%M')}"
    return f"{dow_names[dt.weekday()]} {dt.strftime('%Y-%m-%d %H:%M')}"


def build_pending_edit_alert_text(
    service_dt: datetime,
    role: str,
    current_volunteer: str,
    requester: str,
    replacement: str,
    reason: str,
    lang: str = "pt",
) -> str:
    if lang == "pt":
        return (
            "Olá! Chegou um novo pedido de alteração na escala.\n\n"
            "Resumo para revisão:\n"
            f"Culto: {pretty_dt(service_dt, lang)}\n"
            f"Função: {role_label(role, lang)}\n"
            f"Escalado atual: {current_volunteer}\n"
            f"Solicitante: {requester}\n"
            f"Substituto sugerido: {replacement}\n"
            f"Motivo: {reason or '—'}\n\n"
            "Abra a página Editar / Trocas para aprovar ou rejeitar."
        )

    return (
        "Hello. A new schedule change request has come in.\n\n"
        "Review summary:\n"
        f"Service: {pretty_dt(service_dt, lang)}\n"
        f"Role: {role_label(role, lang)}\n"
        f"Currently assigned: {current_volunteer}\n"
        f"Requester: {requester}\n"
        f"Suggested replacement: {replacement}\n"
        f"Reason: {reason or '—'}\n\n"
        "Open the Edit / Swaps page to approve or reject it."
    )


def send_pending_edit_alert(
    service_dt: datetime,
    role: str,
    current_volunteer: str,
    requester: str,
    replacement: str,
    reason: str,
    lang: str = "pt",
):
    recipients = admin_edit_alert_numbers_from_env()
    if not recipients:
        return {
            "total_recipients": 0,
            "sent_messages": 0,
            "failed_messages": 0,
        }

    service = EvolutionAPIService.from_env()
    if service is None:
        missing = ", ".join(EvolutionAPIService.missing_env_vars())
        raise RuntimeError(f"Missing Evolution API config: {missing}")

    sent_messages = 0
    failed_messages = 0
    text = build_pending_edit_alert_text(
        service_dt=service_dt,
        role=role,
        current_volunteer=current_volunteer,
        requester=requester,
        replacement=replacement,
        reason=reason,
        lang=lang,
    )

    for recipient in recipients:
        destination_number = normalize_whatsapp_number(recipient)
        if not destination_number:
            failed_messages += 1
            continue

        response = service.send_text(
            number=destination_number,
            text=text,
        )
        if response.success:
            sent_messages += 1
            continue

        failed_messages += 1
        print(
            "[ADMIN ALERTS][WARN] Failed WhatsApp send "
            f"to {recipient}: {response.error}"
        )

    return {
        "total_recipients": len(recipients),
        "sent_messages": sent_messages,
        "failed_messages": failed_messages,
    }
