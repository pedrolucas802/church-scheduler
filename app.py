from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# -----------------------
# Env (load before app imports)
# -----------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# -----------------------
# App imports (after env)
# -----------------------
from src.db import init_db
from src.auth import admin_gate, is_admin
from src.i18n import t, language_selector
from src.nav import nav_pages
from src.reminders.scheduler import start_scheduler

# -----------------------
# Helpers
# -----------------------
def get_app_version() -> str:
    """
    Reads VERSION file at repo root (same folder as app.py).
    Falls back gracefully.
    """
    try:
        v = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
        return v or "dev"
    except Exception:
        return "dev"

def start_scheduler_once():
    """
    Streamlit reruns the script a lot.
    Ensure scheduler is started only once per process.
    """
    if not st.session_state.get("_scheduler_started", False):
        start_scheduler()
        st.session_state["_scheduler_started"] = True

# -----------------------
# Streamlit config + DB
# -----------------------
st.set_page_config(
    page_title=f"Church Scheduler v{get_app_version()}",
    layout="wide",
)

init_db()

# Start background scheduler (once)
start_scheduler_once()

# -----------------------
# UI: language + sidebar
# -----------------------
language_selector()

# Avoid unsafe_allow_html just for spacing
st.sidebar.write("")
st.sidebar.divider()
st.sidebar.write("")

with st.sidebar.expander(t("nav.admin_access"), expanded=False):
    admin_gate()

admin_enabled = is_admin()

pages = [
    st.Page(path, title=f"{icon} {t(key)}")
    for path, key, icon in nav_pages(admin_enabled=admin_enabled)
]

APP_VERSION = get_app_version()

st.navigation(pages).run()

st.sidebar.caption(f"Version: {APP_VERSION}")