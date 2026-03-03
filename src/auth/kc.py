# src/auth/kc.py
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager


# -----------------------
# Cookies (persist state across Streamlit reruns / session resets)
# -----------------------
_cookies = EncryptedCookieManager(
    prefix="churchsched/",
    password=os.getenv("COOKIE_SECRET", "dev-cookie-secret-change-me"),
)

if not _cookies.ready():
    st.stop()

_COOKIE_STATE_KEY = "kc_state"
_COOKIE_VERIFIER_KEY = "kc_verifier"


def _cookie_set_temp(state: str, verifier: str) -> None:
    _cookies[_COOKIE_STATE_KEY] = state
    _cookies[_COOKIE_VERIFIER_KEY] = verifier
    _cookies.save()


def _cookie_get_temp() -> tuple[Optional[str], Optional[str]]:
    return _cookies.get(_COOKIE_STATE_KEY), _cookies.get(_COOKIE_VERIFIER_KEY)


def _cookie_clear_temp() -> None:
    _cookies.pop(_COOKIE_STATE_KEY, None)
    _cookies.pop(_COOKIE_VERIFIER_KEY, None)
    _cookies.save()


# -----------------------
# Query params helpers
# -----------------------
def _qp_first(name: str) -> Optional[str]:
    v = st.query_params.get(name)
    if v is None:
        return None
    if isinstance(v, list):
        return v[0] if v else None
    return str(v)


# -----------------------
# Config helpers
# -----------------------
def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if v is None or v.strip() == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _kc_internal_base() -> str:
    # Container -> Keycloak
    # Prefer KC_BASE_URL, but allow KC_OIDC_BASE_URL as fallback (your .env.local uses it sometimes)
    v = os.getenv("KC_BASE_URL") or os.getenv("KC_OIDC_BASE_URL")
    if not v or v.strip() == "":
        raise RuntimeError("Missing env var: KC_BASE_URL (or KC_OIDC_BASE_URL)")
    return v.rstrip("/")


def _kc_public_base() -> str:
    # Browser -> Keycloak
    return _env("KC_PUBLIC_BASE_URL").rstrip("/")


def _realm() -> str:
    return _env("KC_REALM")


def _client_id() -> str:
    return _env("KC_CLIENT_ID")


def _client_secret() -> str:
    return _env("KC_CLIENT_SECRET")


def _app_base_url() -> str:
    return _env("APP_BASE_URL").rstrip("/")


def _redirect_uri() -> str:
    # must match Keycloak client redirect URI
    return os.getenv("KC_REDIRECT_URI", _app_base_url()).rstrip("/")


def _swap_base(url: str, from_base: str, to_base: str) -> str:
    if url.startswith(from_base):
        return to_base + url[len(from_base) :]
    return url


# -----------------------
# OIDC discovery (cached)
# -----------------------
@st.cache_data(show_spinner=False, ttl=3600)
def _oidc_config(internal_base: str, realm: str) -> Dict[str, Any]:
    url = f"{internal_base}/realms/{realm}/.well-known/openid-configuration"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


# -----------------------
# PKCE helpers
# -----------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _pkce_verifier() -> str:
    return _b64url(secrets.token_bytes(32))


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return _b64url(digest)


# -----------------------
# Session
# -----------------------
_SESSION_KEY = "_kc_session"


def _now() -> float:
    return time.time()


def is_logged_in() -> bool:
    sess = st.session_state.get(_SESSION_KEY)
    if not sess:
        return False
    try:
        expires_at = float(sess["expires_at"])
        return _now() < (expires_at - 10)
    except Exception:
        return False


def get_userinfo() -> Dict[str, Any]:
    sess = st.session_state.get(_SESSION_KEY) or {}
    return sess.get("userinfo") or {}


def get_roles() -> list[str]:
    u = get_userinfo()
    roles: list[str] = []

    realm_access = u.get("realm_access") or {}
    r = realm_access.get("roles") or []
    if isinstance(r, list):
        roles.extend([str(x) for x in r])

    ra = u.get("resource_access") or {}
    client = ra.get(_client_id()) or {}
    cr = client.get("roles") or []
    if isinstance(cr, list):
        roles.extend([str(x) for x in cr])

    return sorted(set(roles))


# -----------------------
# Auth flow
# -----------------------
def _authorize_url(state: str, code_challenge: str) -> str:
    internal = _kc_internal_base()
    public = _kc_public_base()
    cfg = _oidc_config(internal, _realm())

    authorize = cfg["authorization_endpoint"]
    # ensure browser uses public base
    authorize = _swap_base(authorize, internal, public)

    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": _redirect_uri(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{authorize}?{urlencode(params)}"


def _exchange_code(code: str, verifier: str) -> Dict[str, Any]:
    internal = _kc_internal_base()
    public = _kc_public_base()
    cfg = _oidc_config(internal, _realm())

    token_url = cfg["token_endpoint"]
    # ensure server-to-server uses internal base
    token_url = _swap_base(token_url, public, internal)

    data = {
        "grant_type": "authorization_code",
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "code": code,
        "redirect_uri": _redirect_uri(),
        "code_verifier": verifier,
    }
    r = requests.post(token_url, data=data, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_userinfo(access_token: str) -> Dict[str, Any]:
    internal = _kc_internal_base()
    public = _kc_public_base()
    cfg = _oidc_config(internal, _realm())

    userinfo_url = cfg.get("userinfo_endpoint")
    if not userinfo_url:
        return {}

    # ensure server-to-server uses internal base
    userinfo_url = _swap_base(userinfo_url, public, internal)

    r = requests.get(
        userinfo_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _browser_redirect(url: str) -> None:
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="0; url={url}">
        <script>
          window.top.location.href = "{url}";
        </script>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


def handle_callback_if_present() -> None:
    code = _qp_first("code")
    state = _qp_first("state")

    if not code or not state:
        return

    expected_state = st.session_state.get("_kc_state")
    verifier = st.session_state.get("_kc_verifier")

    if not expected_state or not verifier:
        c_state, c_verifier = _cookie_get_temp()
        expected_state = expected_state or c_state
        verifier = verifier or c_verifier

    if not expected_state or not verifier or state != expected_state:
        st.error("Login failed (invalid state). Please try again.")
        st.query_params.clear()
        st.session_state.pop("_kc_state", None)
        st.session_state.pop("_kc_verifier", None)
        _cookie_clear_temp()
        st.stop()

    tokens = _exchange_code(code=code, verifier=verifier)

    access_token = tokens["access_token"]
    id_token = tokens.get("id_token", "")
    refresh_token = tokens.get("refresh_token")
    expires_in = float(tokens.get("expires_in", 300))
    expires_at = _now() + expires_in

    userinfo = _fetch_userinfo(access_token)

    st.session_state[_SESSION_KEY] = {
        "access_token": access_token,
        "id_token": id_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "userinfo": userinfo,
    }

    st.session_state.pop("_kc_state", None)
    st.session_state.pop("_kc_verifier", None)
    _cookie_clear_temp()

    st.query_params.clear()
    st.rerun()


def logout() -> None:
    internal = _kc_internal_base()
    public = _kc_public_base()

    sess = st.session_state.get(_SESSION_KEY) or {}
    id_token = sess.get("id_token", "")

    st.session_state.pop(_SESSION_KEY, None)

    cfg = _oidc_config(internal, _realm())
    end_session = cfg.get("end_session_endpoint")
    if not end_session:
        st.rerun()

    end_session = _swap_base(end_session, internal, public)

    params = {"post_logout_redirect_uri": _redirect_uri()}
    if id_token:
        params["id_token_hint"] = id_token

    _browser_redirect(f"{end_session}?{urlencode(params)}")


# -----------------------
# Screens
# -----------------------
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


def account_screen() -> None:
    require_login()

    u = get_userinfo()
    roles = get_roles()

    st.title("Account")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Profile")
        st.write(f"**Username:** {u.get('preferred_username') or '-'}")
        st.write(f"**Email:** {u.get('email') or '-'}")
        st.write(f"**Name:** {u.get('name') or '-'}")
        st.write(f"**User ID:** {u.get('sub') or '-'}")

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