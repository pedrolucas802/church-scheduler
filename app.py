from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.auth.admin_gate import admin_gate, is_admin
from src.auth.kc import require_login, account_screen

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

# -----------------------
# Helpers
# -----------------------
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

# -----------------------
# Auth gate (before DB/scheduler)
# -----------------------
require_login()

# -----------------------
# DB + scheduler
# -----------------------
init_db()
start_scheduler_once()

# -----------------------
# UI: language + navigation
# -----------------------
language_selector()

# Keep your admin access UI (still in sidebar for now)
st.sidebar.write("")
st.sidebar.divider()
st.sidebar.write("")

with st.sidebar.expander(t("nav.admin_access"), expanded=False):
    admin_gate()

admin_enabled = is_admin()

# Your existing pages
pages = [
    st.Page(path, title=f"{icon} {t(key)}")
    for path, key, icon in nav_pages(admin_enabled=admin_enabled)
]

# Add an actual Account screen page
# (This is a "function page": Streamlit supports callables in st.Page)
pages.append(st.Page(account_screen, title="👤 Account"))

APP_VERSION = get_app_version()
st.navigation(pages).run()

st.sidebar.caption(f"Version: {APP_VERSION}")