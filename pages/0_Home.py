import streamlit as st
from dotenv import load_dotenv

from src.db import init_db
from src.i18n import t

load_dotenv()

st.set_page_config(page_title="Church Scheduler", layout="wide")
init_db()

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.8rem; padding-bottom: 2rem; }

      div.stButton > button {
        padding: 0.75rem 1rem;
        border-radius: 0.9rem;
        margin-top: 0.5rem;
        font-weight: 600;
      }

      .k-card {
        border: 1px solid rgba(49, 51, 63, 0.2);
        border-radius: 1.2rem;
        padding: 1.8rem 1.8rem;
        min-height: 200px;
        background: rgba(255,255,255,0.02);
      }

      @media (min-width: 1100px) {
        .k-wrap { max-width: 1000px; margin: 0 auto; }
      }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Welcome / Hero
# ----------------------------
st.markdown('<div class="k-wrap">', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="k-card">
      <h2 style="margin:0 0 .25rem 0;">{t("app.title")}</h2>
      <p style="margin:0; opacity:.9;">{t("app.caption")}</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")  # spacing

# ----------------------------
# Quick actions (Schedule + Swap Request)
# ----------------------------
# st.subheader("🚀 " + (t("home.quick_actions") if "home.quick_actions" else ("Ações rápidas" if st.session_state.get("lang","pt")=="pt" else "Quick actions")))

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown(
        f"""
        <div class="k-card">
          <h4 style="margin:0 0 .25rem 0;">📅 {t("home.open_schedule") if "home.open_schedule" else ("Ver escala" if st.session_state.get("lang","pt")=="pt" else "Open schedule")}</h4>
          <p style="margin:0 0 1rem 0; opacity:.85;">
            {t("home.open_schedule_desc") if "home.open_schedule_desc" else ("Veja a escala do mês em formato de calendário." if st.session_state.get("lang","pt")=="pt" else "See the monthly calendar view of the schedule.")}
          </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    if st.button(
        t("home.open_schedule_btn") if "home.open_schedule_btn" else ("📅 Abrir escala" if st.session_state.get("lang","pt")=="pt" else "📅 Open schedule"),
        use_container_width=True
    ):
        # Adjust the filename to match your schedule page
        # Example: pages/3_Schedule.py
        st.switch_page("pages/2_Schedule.py")

with c2:
    st.markdown(
        f"""
        <div class="k-card">
          <h4 style="margin:0 0 .25rem 0;">🔁 {t("home.request_swap") if "home.request_swap" else ("Solicitar troca" if st.session_state.get("lang","pt")=="pt" else "Request swap")}</h4>
          <p style="margin:0 0 1rem 0; opacity:.85;">
            {t("home.request_swap_desc") if "home.request_swap_desc" else ("Peça uma troca informando substituto e motivo. O admin aprova." if st.session_state.get("lang","pt")=="pt" else "Request a change with replacement + reason. Admin approves.")}
          </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    if st.button(
        t("home.request_swap_btn") if "home.request_swap_btn" else ("🔁 Solicitar troca" if st.session_state.get("lang","pt")=="pt" else "🔁 Request swap"),
        use_container_width=True
    ):
        # If you want a dedicated swap page, point here.
        # If swap requests live inside Edit page, point to it:
        st.switch_page("pages/4_Edit.py")

st.write("")

# ----------------------------
# Helpful tips
# ----------------------------
with st.expander("ℹ️ " + (t("home.how_it_works") if "home.how_it_works" else ("Como funciona" if st.session_state.get("lang","pt")=="pt" else "How it works"))):
    if st.session_state.get("lang","pt") == "pt":
        st.markdown(
            """
- **Escala/Calendário:** consulte os cultos e quem está escalado em cada função.
- **Solicitar troca:** informe quem está pedindo, quem vai substituir e o motivo.
- **Admin:** aprova/rejeita pedidos, edita a escala e gera lembretes.
            """
        )
    else:
        st.markdown(
            """
- **Schedule/Calendar:** see services and assigned volunteers by role.
- **Request swap:** choose requester, replacement, and reason.
- **Admin:** approve/reject requests, edit schedule, and rebuild reminders.
            """
        )


st.info("Use o menu lateral para navegar / Use the sidebar to navigate.")
st.markdown("</div>", unsafe_allow_html=True)