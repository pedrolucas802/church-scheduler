# src/services/n8n_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests


@dataclass(frozen=True)
class N8NResponse:
    success: bool
    url: str
    status_code: Optional[int] = None
    data: Any = None
    error: Optional[str] = None


class N8NService:
    """
    Small client for calling n8n webhooks behind your Nginx reverse proxy.

    base_url example:
      http://76.13.161.163/n8n
    """

    def __init__(self, base_url: str, timeout_seconds: int = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    def send_test_webhook(self, path: str, payload: Dict[str, Any]) -> N8NResponse:
        """
        Calls /webhook-test/<path> in n8n
        """
        return self._post(f"/webhook-test/{path.lstrip('/')}", payload)

    def send_prod_webhook(self, path: str, payload: Dict[str, Any]) -> N8NResponse:
        """
        Calls /webhook/<path> in n8n
        Workflow must be ACTIVE.
        """
        return self._post(f"/webhook/{path.lstrip('/')}", payload)

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> N8NResponse:
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.post(url, json=payload, timeout=self.timeout)
            return N8NResponse(
                success=r.ok,
                url=url,
                status_code=r.status_code,
                data=self._safe_json(r),
                error=None if r.ok else f"HTTP {r.status_code}",
            )
        except requests.exceptions.Timeout:
            return N8NResponse(success=False, url=url, error="timeout")
        except requests.exceptions.RequestException as e:
            return N8NResponse(success=False, url=url, error=f"request_exception: {e}")

    @staticmethod
    def _safe_json(r: requests.Response) -> Any:
        try:
            return r.json()
        except ValueError:
            return r.text