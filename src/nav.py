import streamlit as st
from src.i18n import t, get_lang
def nav_pages(admin_enabled: bool = False):
    base = [
        ("pages/0_Home.py", "nav.home", "🏠"),
        ("pages/2_Schedule.py", "nav.schedule", "📅"),
        ("pages/4_Edit.py", "nav.edit", "✏️"),
    ]

    admin_only = [
        ("pages/1_Volunteers.py", "nav.volunteers", "👥"),
        ("pages/3_Generate.py", "nav.generate", "⚙️"),
        ("pages/5_Reminders.py", "nav.reminders", "⏰"),
    ]

    return base + (admin_only if admin_enabled else [])

def nav_sidebar():
    """
    Sidebar navigation that reflects selected language.
    Returns the selected page path.
    """
    lang = get_lang()  # ensures session state exists

    st.sidebar.markdown("### " + (t("nav.title") if "nav.title" else ("Navegação" if lang == "pt" else "Navigation")))

    pages = nav_pages()
    labels = [f"{icon} {t(key)}" for (path, key, icon) in pages]
    path_by_label = {f"{icon} {t(key)}": path for (path, key, icon) in pages}

    # Keep selection stable across reruns
    current = st.session_state.get("nav_selected", labels[0])
    if current not in labels:
        current = labels[0]

    choice = st.sidebar.radio(
        label="",
        options=labels,
        index=labels.index(current),
    )
    st.session_state["nav_selected"] = choice
    return path_by_label[choice]