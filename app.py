import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from src.db import init_db
from src.auth import admin_gate, is_admin
from src.i18n import t, language_selector
from src.nav import nav_pages

st.set_page_config(page_title="Church Scheduler MVP", layout="wide")
init_db()

# Language selector (only once, in app.py)
language_selector()

# Sidebar spacing
st.sidebar.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
st.sidebar.divider()
st.sidebar.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# Admin gate
with st.sidebar.expander(t("nav.admin_access"), expanded=False):
    admin_gate()

admin_enabled = is_admin()

# Build translated nav
pages = [st.Page(path, title=f"{icon} {t(key)}") for path, key, icon in nav_pages(admin_enabled=admin_enabled)]
pg = st.navigation(pages)
pg.run()