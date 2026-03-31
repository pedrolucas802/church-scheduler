from __future__ import annotations

from typing import Any

import streamlit as st


def _action_key(page_key: str) -> str:
    return f"_ui_action:{page_key}"


def _payload_key(page_key: str) -> str:
    return f"_ui_action_payload:{page_key}"


def is_page_action_busy(page_key: str) -> bool:
    return bool(st.session_state.get(_action_key(page_key)))


def queue_page_action(page_key: str, action: str, payload: dict[str, Any] | None = None):
    if is_page_action_busy(page_key):
        return

    st.session_state[_action_key(page_key)] = action
    st.session_state[_payload_key(page_key)] = payload or {}


def consume_page_action(page_key: str, action: str) -> dict[str, Any] | None:
    current = st.session_state.get(_action_key(page_key))
    if current != action:
        return None
    payload = st.session_state.get(_payload_key(page_key), {})
    return payload if isinstance(payload, dict) else {}


def clear_page_action(page_key: str):
    st.session_state.pop(_action_key(page_key), None)
    st.session_state.pop(_payload_key(page_key), None)
