from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

import requests


def normalize_whatsapp_number(raw: str | None) -> str | None:
    if not raw:
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    if "@" in cleaned:
        return cleaned

    digits = re.sub(r"\D+", "", cleaned)
    return digits or None


def get_whatsapp_test_override_number(env_var: str = "REMINDER_TEST_WHATSAPP_NUMBER") -> str | None:
    raw = (os.getenv(env_var) or "").strip()
    return normalize_whatsapp_number(raw)


def resolve_whatsapp_destination_number(
    original_number: str | None,
    env_var: str = "REMINDER_TEST_WHATSAPP_NUMBER",
) -> str | None:
    return get_whatsapp_test_override_number(env_var=env_var) or normalize_whatsapp_number(original_number)


def prepend_whatsapp_test_banner(
    text: str,
    recipient_label: str,
    original_number: str | None,
    lang: str = "pt",
    env_var: str = "REMINDER_TEST_WHATSAPP_NUMBER",
) -> str:
    override = get_whatsapp_test_override_number(env_var=env_var)
    if not override:
        return text

    if lang == "pt":
        header = (
            "[TESTE INTERNO]\n"
            f"Destino real: {recipient_label} ({original_number or 'sem numero'})\n"
            f"Mensagem redirecionada para: {override}\n\n"
        )
    else:
        header = (
            "[INTERNAL TEST]\n"
            f"Original destination: {recipient_label} ({original_number or 'no number'})\n"
            f"Message rerouted to: {override}\n\n"
        )

    return header + text


@dataclass(frozen=True)
class EvolutionAPIResponse:
    success: bool
    url: str
    status_code: Optional[int] = None
    data: Any = None
    error: Optional[str] = None


class EvolutionAPIService:
    def __init__(self, base_url: str, instance: str, api_key: str, timeout_seconds: int = 15):
        self.base_url = base_url.rstrip("/")
        self.instance = instance.strip()
        self.api_key = api_key.strip()
        self.timeout = timeout_seconds

    @classmethod
    def from_env(cls) -> "EvolutionAPIService | None":
        base_url = (os.getenv("EVOLUTION_API_BASE_URL") or "").strip()
        instance = (os.getenv("EVOLUTION_API_INSTANCE") or "").strip()
        api_key = (os.getenv("EVOLUTION_API_KEY") or "").strip()

        if not all([base_url, instance, api_key]):
            return None

        return cls(base_url=base_url, instance=instance, api_key=api_key)

    @staticmethod
    def missing_env_vars() -> list[str]:
        required = {
            "EVOLUTION_API_BASE_URL": (os.getenv("EVOLUTION_API_BASE_URL") or "").strip(),
            "EVOLUTION_API_INSTANCE": (os.getenv("EVOLUTION_API_INSTANCE") or "").strip(),
            "EVOLUTION_API_KEY": (os.getenv("EVOLUTION_API_KEY") or "").strip(),
        }
        return [name for name, value in required.items() if not value]

    def send_text(
        self,
        number: str,
        text: str,
        delay_ms: int = 0,
        link_preview: bool = False,
    ) -> EvolutionAPIResponse:
        normalized_number = normalize_whatsapp_number(number)
        if not normalized_number:
            return EvolutionAPIResponse(
                success=False,
                url=self._send_text_url(),
                error="invalid_number",
            )

        state_response = self.connection_state()
        state = self._extract_connection_state(state_response.data)
        if not state_response.success:
            return EvolutionAPIResponse(
                success=False,
                url=self._send_text_url(),
                status_code=state_response.status_code,
                data=state_response.data,
                error=f"state_check_failed:{state_response.error or 'unknown'}",
            )
        if state != "open":
            return EvolutionAPIResponse(
                success=False,
                url=self._send_text_url(),
                data=state_response.data,
                error=f"instance_not_open:{state or 'unknown'}",
            )

        payload = {
            "number": normalized_number,
            "text": text,
            "linkPreview": bool(link_preview),
        }
        if delay_ms > 0:
            payload["delay"] = int(delay_ms)

        try:
            response = requests.post(
                self._send_text_url(),
                headers={
                    "Content-Type": "application/json",
                    "apikey": self.api_key,
                },
                json=payload,
                timeout=self.timeout,
            )
            return EvolutionAPIResponse(
                success=response.ok,
                url=self._send_text_url(),
                status_code=response.status_code,
                data=self._safe_json(response),
                error=None if response.ok else f"HTTP {response.status_code}",
            )
        except requests.exceptions.Timeout:
            return EvolutionAPIResponse(
                success=False,
                url=self._send_text_url(),
                error="timeout",
            )
        except requests.exceptions.RequestException as exc:
            return EvolutionAPIResponse(
                success=False,
                url=self._send_text_url(),
                error=f"request_exception: {exc}",
            )

    def connection_state(self) -> EvolutionAPIResponse:
        try:
            response = requests.get(
                self._connection_state_url(),
                headers={"apikey": self.api_key},
                timeout=min(self.timeout, 5),
            )
            return EvolutionAPIResponse(
                success=response.ok,
                url=self._connection_state_url(),
                status_code=response.status_code,
                data=self._safe_json(response),
                error=None if response.ok else f"HTTP {response.status_code}",
            )
        except requests.exceptions.Timeout:
            return EvolutionAPIResponse(
                success=False,
                url=self._connection_state_url(),
                error="timeout",
            )
        except requests.exceptions.RequestException as exc:
            return EvolutionAPIResponse(
                success=False,
                url=self._connection_state_url(),
                error=f"request_exception: {exc}",
            )

    def _send_text_url(self) -> str:
        return f"{self.base_url}/message/sendText/{self.instance}"

    def _connection_state_url(self) -> str:
        return f"{self.base_url}/instance/connectionState/{self.instance}"

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def _extract_connection_state(data: Any) -> str | None:
        if not isinstance(data, dict):
            return None
        instance = data.get("instance")
        if not isinstance(instance, dict):
            return None
        state = instance.get("state")
        return state if isinstance(state, str) else None
