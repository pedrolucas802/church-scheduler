import streamlit as st
from src.i18n import t, get_lang
from src.auth.kc import is_logged_in, get_roles


def is_super_admin() -> bool:
    if not is_logged_in():
        return False
    roles = set(get_roles())
    print("roles ---->",roles)
    return "super_admin" in roles


def nav_pages(admin_enabled: bool = False):
    base = [
        ("src/pages/0_Home.py", "nav.home", "🏠"),
        ("src/pages/1_Volunteers.py", "nav.volunteers", "👥"),
        ("src/pages/2_Schedule.py", "nav.schedule", "📅"),
        ("src/pages/4_Edit.py", "nav.edit", "✏️"),
        ("src/pages/6_Account.py", "nav.account", "👤"),
    ]

    admin_only = [
        ("src/pages/3_Generate.py", "nav.generate", "⚙️"),
        ("src/pages/5_Reminders.py", "nav.reminders", "⏰"),
    ]

    super_admin_only = [
        ("src/pages/7_Ministries.py", "nav.ministries", "🏛️"),
    ]

    pages = list(base)

    if admin_enabled:
        pages.extend(admin_only)

    if is_super_admin():
        pages.extend(super_admin_only)

    return pages


def nav_sidebar():
    """
    Sidebar navigation that reflects selected language.
    Returns the selected page path.
    """
    lang = get_lang()

    title = t("nav.title")
    if title == "nav.title":
        title = "Navegação" if lang == "pt" else "Navigation"

    st.sidebar.markdown("### " + title)

    pages = nav_pages()
    labels = [f"{icon} {t(key) if t(key) != key else _fallback_nav_label(key, lang)}" for (path, key, icon) in pages]
    path_by_label = {
        f"{icon} {t(key) if t(key) != key else _fallback_nav_label(key, lang)}": path
        for (path, key, icon) in pages
    }

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


def _fallback_nav_label(key: str, lang: str) -> str:
    mapping_pt = {
        "nav.home": "Início",
        "nav.volunteers": "Voluntários",
        "nav.schedule": "Escala",
        "nav.edit": "Editar / Trocas",
        "nav.generate": "Gerar",
        "nav.reminders": "Lembretes",
        "nav.account": "Conta",
        "nav.ministries": "Ministérios",
    }

    mapping_en = {
        "nav.home": "Home",
        "nav.volunteers": "Volunteers",
        "nav.schedule": "Schedule",
        "nav.edit": "Edit / Swaps",
        "nav.generate": "Generate",
        "nav.reminders": "Reminders",
        "nav.account": "Account",
        "nav.ministries": "Ministries",
    }

    return mapping_pt.get(key, key) if lang == "pt" else mapping_en.get(key, key)