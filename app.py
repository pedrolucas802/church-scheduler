from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import streamlit as st
from src.db import init_db
from src.auth import admin_gate, is_admin
from src.i18n import t, language_selector
from src.nav import nav_pages
from src.reminders.scheduler import start_scheduler

# Start background scheduler ASAP (runs alongside Streamlit process)
start_scheduler()

# -----------------------
# Streamlit config + DB
# -----------------------
st.set_page_config(page_title="Church Scheduler MVP", layout="wide")
init_db()

# -----------------------
# UI: language + sidebar
# -----------------------
language_selector()

st.sidebar.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
st.sidebar.divider()
st.sidebar.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

with st.sidebar.expander(t("nav.admin_access"), expanded=False):
    admin_gate()

admin_enabled = is_admin()

pages = [
    st.Page(path, title=f"{icon} {t(key)}")
    for path, key, icon in nav_pages(admin_enabled=admin_enabled)
]

st.navigation(pages).run()