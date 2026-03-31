import os
import time
from datetime import datetime, timedelta

import bcrypt
import streamlit as st

from src.db import (
    get_admin_user,
    admin_record_failed_login,
    admin_reset_failures,
)
from src.services.ui_action_service import clear_page_action, consume_page_action, is_page_action_busy, queue_page_action

SESSION_TTL_MINUTES = int(os.getenv("ADMIN_SESSION_TTL_MINUTES", "60"))
MAX_FAILED_ATTEMPTS = int(os.getenv("ADMIN_MAX_FAILED_ATTEMPTS", "8"))
LOCKOUT_MINUTES = int(os.getenv("ADMIN_LOCKOUT_MINUTES", "15"))
AUTH_PAGE_KEY = "auth_admin_gate"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _touch_session():
    st.session_state["admin_expires_at"] = _utcnow() + timedelta(minutes=SESSION_TTL_MINUTES)


def disable_admin():
    st.session_state["admin_enabled"] = False
    st.session_state.pop("admin_expires_at", None)
    # Important: reset nav selection so Streamlit doesn't hold a now-invalid page
    st.session_state.pop("st_nav_selection", None)


def is_admin() -> bool:
    if not st.session_state.get("admin_enabled", False):
        return False

    exp = st.session_state.get("admin_expires_at")
    if not exp:
        disable_admin()
        return False

    if _utcnow() >= exp:
        disable_admin()
        return False

    return True


def _verify_bcrypt(password_hash: str, plain: str) -> bool:
    try:
        if not password_hash or not plain:
            return False
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def admin_gate():
    """
    Admin login UI for single admin user 'admin'
    Session keys:
      - admin_enabled: bool
      - admin_expires_at: datetime
    """
    st.session_state.setdefault("admin_enabled", False)

    if is_admin():
        _touch_session()
        st.success("Admin enabled for this session.")
        c1, c2 = st.columns([1, 1])
        with c1:
            st.caption(f"Session expires in ~{SESSION_TTL_MINUTES} min (rolling).")
        with c2:
            st.button(
                "Disable admin",
                key="admin_disable_btn",
                disabled=is_page_action_busy(AUTH_PAGE_KEY),
                on_click=queue_page_action,
                args=(AUTH_PAGE_KEY, "disable_admin"),
            )
        if consume_page_action(AUTH_PAGE_KEY, "disable_admin") is not None:
            clear_page_action(AUTH_PAGE_KEY)
            disable_admin()
            st.rerun()
        return

    row = get_admin_user("admin")
    if not row:
        st.error("No admin user found in DB. Run the setup script to create admin credentials.")
        return

    _id, username, password_hash, active, failed_attempts, locked_until = row

    if not active:
        st.error("Admin account is disabled.")
        return

    if locked_until:
        try:
            lu = datetime.fromisoformat(locked_until)
            if _utcnow() < lu:
                remaining = int((lu - _utcnow()).total_seconds() // 60) + 1
                st.error(f"Too many attempts. Locked for ~{remaining} minutes.")
                return
        except Exception:
            pass

    pwd = st.text_input("Admin password", type="password", key="admin_pwd_input")
    time.sleep(0.05)

    st.button(
        "Submit",
        key="admin_submit_btn",
        disabled=is_page_action_busy(AUTH_PAGE_KEY),
        on_click=queue_page_action,
        args=(AUTH_PAGE_KEY, "submit_admin_login", {"password": pwd}),
    )

    action = consume_page_action(AUTH_PAGE_KEY, "submit_admin_login")
    if action is not None:
        clear_page_action(AUTH_PAGE_KEY)
        pwd_to_check = str(action.get("password", ""))
        ok = _verify_bcrypt(password_hash, pwd_to_check)

        if not ok:
            new_failed = int(failed_attempts or 0) + 1
            locked_until_iso = None
            if new_failed >= MAX_FAILED_ATTEMPTS:
                locked_until_iso = (_utcnow() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()

            admin_record_failed_login("admin", new_failed, locked_until_iso)
            st.error("Wrong password.")
            return

        admin_reset_failures("admin")
        st.session_state["admin_enabled"] = True
        _touch_session()

        # Reset selection so nav rebuild doesn't keep an invalid page selected
        st.session_state.pop("st_nav_selection", None)

        st.rerun()
