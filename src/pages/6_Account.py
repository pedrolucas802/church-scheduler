import streamlit as st

from src.auth.kc import handle_callback_if_present, is_logged_in, get_userinfo, get_roles, logout, _SESSION_KEY, _now, \
    _pkce_verifier, _pkce_challenge, _cookie_set_temp, _authorize_url, _browser_redirect

def login_screen() -> None:
    st.title("Church Scheduler")
    st.write("Sign in to continue.")

    if st.button("Sign in with Keycloak", type="primary", use_container_width=True):
        state = st.secrets.token_urlsafe(24)
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


st.set_page_config(page_title="Account", layout="wide")
account_screen()