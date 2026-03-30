# src/auth/kc.py
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, urlunparse

import jwt
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
    # Streamlit needs one run to initialize cookies
    st.stop()

_COOKIE_STATE_KEY = "kc_state"
_COOKIE_VERIFIER_KEY = "kc_verifier"

_SESSION_KEY = "_kc_session"
_TEMP_STATE_KEY = "_kc_state"
_TEMP_VERIFIER_KEY = "_kc_verifier"

# -----------------------
# Role names (realm roles)
# -----------------------
ROLE_SUPER_ADMIN = os.getenv("KC_ROLE_SUPER_ADMIN", "super_admin")
ROLE_MINISTRY_ADMIN = os.getenv("KC_ROLE_MINISTRY_ADMIN", "ministry_admin")
ROLE_VOLUNTEER = os.getenv("KC_ROLE_VOLUNTEER", "volunteer")


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
    """
    Server/container -> Keycloak base.
    Prefer KC_BASE_URL, but allow KC_OIDC_BASE_URL fallback.
    """
    v = os.getenv("KC_BASE_URL") or os.getenv("KC_OIDC_BASE_URL")
    if not v or v.strip() == "":
        raise RuntimeError("Missing env var: KC_BASE_URL (or KC_OIDC_BASE_URL)")
    return v.rstrip("/")


def _kc_public_base() -> str:
    """Browser -> Keycloak base (what the user opens)."""
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


def _with_base(url: str, base: str) -> str:
    """
    Force any OIDC endpoint URL to use the given base (scheme+host+port),
    keeping path/query/fragment. This fixes cases like:
      - Keycloak returns http://localhost/realms/... (missing :8081)
      - Keycloak returns internal hostnames
    """
    pu = urlparse(url)
    pb = urlparse(base)
    return urlunparse((pb.scheme, pb.netloc, pu.path, pu.params, pu.query, pu.fragment))


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
# Session helpers
# -----------------------
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
    sess = st.session_state.get(_SESSION_KEY) or {}
    access_token = sess.get("access_token")
    if not access_token:
        return []
    try:
        payload = jwt.decode(access_token, options={"verify_signature": False})
    except Exception:
        return []
    roles: list[str] = []

    realm_access = payload.get("realm_access") or {}
    r = realm_access.get("roles") or []
    if isinstance(r, list):
        roles.extend([str(x) for x in r])

    ra = payload.get("resource_access") or {}
    client = ra.get(_client_id()) or {}
    cr = client.get("roles") or []
    if isinstance(cr, list):
        roles.extend([str(x) for x in cr])

    return sorted(set(roles))


def get_username() -> str:
    """Best-effort display name for the currently signed-in user."""
    u = get_userinfo()
    return str(
        u.get("preferred_username")
        or u.get("email")
        or u.get("name")
        or u.get("sub")
        or "-"
    )


def has_role(role: str) -> bool:
    return role in set(get_roles())


def has_any_role(*roles: str) -> bool:
    current = set(get_roles())
    return any(r in current for r in roles if r)


def is_super_admin() -> bool:
    return is_logged_in() and has_role(ROLE_SUPER_ADMIN)


def is_ministry_admin() -> bool:
    # Scope (which ministry) is handled by the DB membership model.
    return is_logged_in() and has_any_role(ROLE_SUPER_ADMIN, ROLE_MINISTRY_ADMIN)


def is_volunteer_user() -> bool:
    return is_logged_in() and has_any_role(ROLE_SUPER_ADMIN, ROLE_MINISTRY_ADMIN, ROLE_VOLUNTEER)


# -----------------------
# OIDC flow
# -----------------------
def _authorize_url(state: str, code_challenge: str) -> str:
    internal = _kc_internal_base()
    public = _kc_public_base()
    cfg = _oidc_config(internal, _realm())

    authorize = cfg["authorization_endpoint"]
    authorize = _with_base(authorize, public)  # ensure browser uses PUBLIC base

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
    cfg = _oidc_config(internal, _realm())

    token_url = cfg["token_endpoint"]
    token_url = _with_base(token_url, internal)  # ensure server uses INTERNAL base

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
    cfg = _oidc_config(internal, _realm())

    userinfo_url = cfg.get("userinfo_endpoint")
    if not userinfo_url:
        return {}

    userinfo_url = _with_base(userinfo_url, internal)  # server -> internal
    r = requests.get(
        userinfo_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _browser_redirect(url: str) -> None:
    # Top-level redirect (not iframe). Keeps same tab.
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
    """
    Always call this near the top of app/pages.
    If the URL has ?code=...&state=..., it will finalize the login.
    """
    code = _qp_first("code")
    state = _qp_first("state")

    if not code or not state:
        return

    expected_state = st.session_state.get(_TEMP_STATE_KEY)
    verifier = st.session_state.get(_TEMP_VERIFIER_KEY)

    # fallback to cookie if session reset
    if not expected_state or not verifier:
        c_state, c_verifier = _cookie_get_temp()
        expected_state = expected_state or c_state
        verifier = verifier or c_verifier

    if not expected_state or not verifier or state != expected_state:
        st.error("Login failed (invalid state). Please try again.")
        st.query_params.clear()
        st.session_state.pop(_TEMP_STATE_KEY, None)
        st.session_state.pop(_TEMP_VERIFIER_KEY, None)
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

    # cleanup temp auth data
    st.session_state.pop(_TEMP_STATE_KEY, None)
    st.session_state.pop(_TEMP_VERIFIER_KEY, None)
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

    end_session = _with_base(end_session, public)

    params = {"post_logout_redirect_uri": _redirect_uri()}
    if id_token:
        params["id_token_hint"] = id_token

    _browser_redirect(f"{end_session}?{urlencode(params)}")

def start_login() -> None:
    state = secrets.token_urlsafe(24)
    verifier = _pkce_verifier()
    challenge = _pkce_challenge(verifier)

    st.session_state[_TEMP_STATE_KEY] = state
    st.session_state[_TEMP_VERIFIER_KEY] = verifier
    _cookie_set_temp(state, verifier)

    url = _authorize_url(state=state, code_challenge=challenge)
    _browser_redirect(url)

def auth_widget(where: str = "top") -> None:
    """
    Small “gate-style” widget.
    Shows Login/Logout + roles, but DOES NOT block navigation.
    """
    handle_callback_if_present()

    if is_logged_in():
        roles = get_roles()
        st.caption(f"✅ {get_username()}")
        if roles:
            st.caption("Roles: " + ", ".join(roles))

        if st.button("Logout", key=f"kc_logout_{where}", use_container_width=True):
            logout()
        return

    st.caption("⚪ Not signed in")
    if st.button(
        "Sign in with Keycloak",
        key=f"kc_login_{where}",
        type="primary",
        use_container_width=True,
    ):
        start_login()

def _get_admin_token() -> str:
    """Get admin access token for Keycloak admin API."""
    internal = _kc_internal_base()
    token_url = f"{internal}/realms/master/protocol/openid-connect/token"
    
    data = {
        "client_id": "admin-cli",
        "username": os.getenv("KC_ADMIN_USER", "admin"),
        "password": os.getenv("KC_ADMIN_PASSWORD", "admin"),
        "grant_type": "password",
    }
    
    r = requests.post(token_url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def create_user_in_keycloak(username: str, email: str, first_name: str, last_name: str, password: str, roles: list[str] = None) -> str | None:
    """Create a user in Keycloak and assign roles. Returns the user ID (kc_sub) if successful."""
    try:
        admin_token = _get_admin_token()
        internal = _kc_internal_base()
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        
        # Create user
        user_data = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }
        
        create_url = f"{internal}/admin/realms/{_realm()}/users"
        r = requests.post(create_url, json=user_data, headers=headers, timeout=10)
        if r.status_code == 409:
            # User already exists
            print(f"User {username} already exists in Keycloak")
            # Try to get existing user ID
            users_url = f"{internal}/admin/realms/{_realm()}/users?username={username}"
            r2 = requests.get(users_url, headers=headers, timeout=10)
            if r2.status_code == 200:
                users_data = r2.json()
                if users_data:
                    return users_data[0]["id"]
            return None
        r.raise_for_status()
        
        # Get user ID from Location header
        location = r.headers.get("Location")
        if location:
            user_id = location.split("/")[-1]
            return user_id
        
        return None
    except Exception as e:
        print(f"Failed to create user in Keycloak: {e}")
        return None
