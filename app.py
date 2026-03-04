# app.py
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.auth.admin_gate import is_admin
from src.auth.kc import (
    auth_widget,
    handle_callback_if_present,
)
from src.ui.style_injector import inject_global_css

# -----------------------
# Env (load before app imports)
# -----------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# -----------------------
# App imports (after env)
# -----------------------
from src.db import init_db
from src.i18n import t, language_selector
from src.nav import nav_pages
from src.reminders.scheduler import start_scheduler


def get_app_version() -> str:
    try:
        v = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
        return v or "dev"
    except Exception:
        return "dev"


def start_scheduler_once():
    if not st.session_state.get("_scheduler_started", False):
        start_scheduler()
        st.session_state["_scheduler_started"] = True


# -----------------------
# Streamlit config
# -----------------------
st.set_page_config(
    page_title=f"Church Scheduler v{get_app_version()}",
    layout="wide",
)

inject_global_css(BASE_DIR / "src" / "ui" / "styles.css")

# -----------------------
# Handle Keycloak callback early
# -----------------------
handle_callback_if_present()

# -----------------------
# DB + scheduler
# -----------------------
init_db()
start_scheduler_once()

# -----------------------
# UI: language
# -----------------------
language_selector()

# -----------------------
# Sidebar "navbar": Auth widget (replaces old admin_gate UI)
# -----------------------
with st.sidebar.container():
    auth_widget(where="sidebar")  # <-- this is the replacement

st.sidebar.divider()

# Admin check (role-based; and/or password gate if you keep it in is_admin)
admin_enabled = is_admin()

# -----------------------
# Pages
# -----------------------
pages = [
    st.Page(path, title=f"{icon} {t(key)}")
    for path, key, icon in nav_pages(admin_enabled=admin_enabled)
]

APP_VERSION = get_app_version()
st.navigation(pages).run()

st.sidebar.caption(f"Version: {APP_VERSION}")