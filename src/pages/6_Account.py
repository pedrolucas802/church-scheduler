import secrets
import streamlit as st
from importlib import import_module

from src.auth.kc import (
    handle_callback_if_present,
    is_logged_in,
    get_userinfo,
    get_roles,
    logout,
    _SESSION_KEY,
    _now,
    _pkce_verifier,
    _pkce_challenge,
    _cookie_set_temp,
    _authorize_url,
    _browser_redirect,
)


def _import_fn(paths: list[str], fn_name: str):
    last_err = None
    for p in paths:
        try:
            mod = import_module(p)
            return getattr(mod, fn_name)
        except Exception as e:
            last_err = e
    raise ImportError(f"Could not import {fn_name} from {paths}. Last error: {last_err}")


upsert_user_from_kc = _import_fn(
    ["src.db", "src.db.repos.users"],
    "upsert_user_from_kc",
)

get_user_by_kc_sub = _import_fn(
    ["src.db", "src.db.repos.users"],
    "get_user_by_kc_sub",
)

update_user_profile = _import_fn(
    ["src.db", "src.db.repos.users"],
    "update_user_profile",
)


def login_screen() -> None:
    st.title("Church Scheduler")
    st.write("Sign in to continue.")

    if st.button("Sign in with Keycloak", type="primary", use_container_width=True):
        state = secrets.token_urlsafe(24)
        verifier = _pkce_verifier()
        challenge = _pkce_challenge(verifier)

        st.session_state["_kc_state"] = state
        st.session_state["_kc_verifier"] = verifier
        _cookie_set_temp(state, verifier)

        url = _authorize_url(state=state, code_challenge=challenge)
        _browser_redirect(url)

    st.caption("If you don't have an account, ask an admin to create one.")


def require_login() -> None:
    handle_callback_if_present()

    if is_logged_in():
        return

    login_screen()
    st.stop()


def _safe(v) -> str:
    return (v or "").strip()


def _valid_email(email: str) -> bool:
    email = _safe(email)
    return ("@" in email) and ("." in email) and (len(email) >= 6)


def account_screen() -> None:
    require_login()

    u = get_userinfo()
    roles = get_roles()
    kc_sub = _safe(u.get("sub"))

    # Keep local mirror synced with KC on login/view
    local_user = None
    if kc_sub:
        try:
            upsert_user_from_kc(u)
            local_user = get_user_by_kc_sub(kc_sub)
        except Exception as e:
            st.warning(f"Could not sync local profile: {e}")

    local_name = _safe(local_user.get("full_name")) if local_user else ""
    local_email = _safe(local_user.get("email")) if local_user else ""

    display_username = _safe(u.get("preferred_username")) or "-"
    display_email = local_email or _safe(u.get("email")) or "-"
    display_name = local_name or _safe(u.get("name")) or "-"

    st.title("Account")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Profile")
        st.write(f"**Username:** {display_username}")
        st.write(f"**Email:** {display_email}")
        st.write(f"**Name:** {display_name}")
        st.write(f"**User ID:** {kc_sub or '-'}")

        st.subheader("Edit profile")

        with st.form("account_profile_form"):
            new_name = st.text_input("Name", value=display_name if display_name != "-" else "")
            new_email = st.text_input("Email", value=display_email if display_email != "-" else "")

            submitted = st.form_submit_button("Save profile", use_container_width=True)

        if submitted:
            new_name = _safe(new_name)
            new_email = _safe(new_email).lower()

            if not new_name:
                st.error("Name is required.")
            elif not _valid_email(new_email):
                st.error("Please enter a valid email.")
            elif not kc_sub:
                st.error("Missing Keycloak user id.")
            else:
                try:
                    update_user_profile(
                        kc_sub=kc_sub,
                        full_name=new_name,
                        email=new_email,
                    )

                    # refresh local values immediately in UI
                    local_user = get_user_by_kc_sub(kc_sub)
                    st.success("Profile updated successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update profile: {e}")

        st.caption(
            "This updates your profile inside Church Scheduler. "
            "It does not change your Keycloak account data."
        )

        st.subheader("Roles")
        if roles:
            st.write(", ".join(roles))
        else:
            st.info("No roles found in userinfo.")

    with col2:
        st.subheader("Session")
        sess = st.session_state.get(_SESSION_KEY) or {}
        exp = sess.get("expires_at")
        if exp:
            seconds = max(0, int(float(exp) - _now()))
            st.write(f"**Expires in:** ~{seconds}s")

        if st.button("Logout", type="primary", use_container_width=True):
            logout()


st.set_page_config(page_title="Account", layout="wide")
account_screen()