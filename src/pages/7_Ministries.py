import streamlit as st
import pandas as pd
from importlib import import_module

from src.i18n import t, get_lang
from src.auth.kc import is_logged_in, get_roles


def _import_fn(paths: list[str], fn_name: str):
    last_err = None
    for p in paths:
        try:
            mod = import_module(p)
            return getattr(mod, fn_name)
        except Exception as e:
            last_err = e
    raise ImportError(f"Could not import {fn_name} from {paths}. Last error: {last_err}")


def is_super_admin() -> bool:
    if not is_logged_in():
        return False
    roles = set(get_roles())
    print("roles ---->",roles)
    return "super_admin" in roles


list_ministries = _import_fn(
    ["src.db", "src.db.repos.ministries"],
    "list_ministries",
)

upsert_ministry = _import_fn(
    ["src.db", "src.db.repos.ministries"],
    "upsert_ministry",
)

list_ministry_leaders = _import_fn(
    ["src.db", "src.db.repos.ministries"],
    "list_ministry_leaders",
)

set_ministry_leader = _import_fn(
    ["src.db", "src.db.repos.ministries"],
    "set_ministry_leader",
)

list_users = _import_fn(
    ["src.db", "src.db.repos.users", "src.db.repos.volunteers"],
    "list_users",
)


lang = get_lang()
title = t("ministries.title")
if title == "ministries.title":
    title = "Administração de Ministérios" if lang == "pt" else "Ministry Administration"

st.title("🏛️ " + title)

if not is_super_admin():
    st.warning(
        "Apenas super admins podem acessar esta página."
        if lang == "pt"
        else "Only super admins can access this page."
    )
    st.stop()


def safe(v) -> str:
    return (v or "").strip()


def toast_ok(msg: str):
    st.toast(msg, icon="✅")


def toast_warn(msg: str):
    st.toast(msg, icon="⚠️")


def toast_err(msg: str):
    st.toast(msg, icon="❌")


# =========================
# Load ministries
# =========================
try:
    ministries_rows = list_ministries()
except Exception as e:
    st.error(
        ("Falha ao carregar ministérios: " if lang == "pt" else "Failed to load ministries: ") + str(e)
    )
    st.stop()

ministries_df = pd.DataFrame(
    ministries_rows,
    columns=["id", "slug", "name", "created_at", "updated_at"][: len(ministries_rows[0])]
    if ministries_rows
    else ["id", "slug", "name"]
)

st.subheader("📋 " + ("Ministérios cadastrados" if lang == "pt" else "Registered ministries"))

if ministries_df.empty:
    st.info("Nenhum ministério cadastrado." if lang == "pt" else "No ministries registered.")
else:
    st.dataframe(ministries_df, use_container_width=True, hide_index=True)

st.divider()

# =========================
# Create / Edit ministry
# =========================
st.subheader("✍️ " + ("Criar ou editar ministério" if lang == "pt" else "Create or edit ministry"))

selected_ministry_id = None
if not ministries_df.empty:
    options = ["— " + ("Novo ministério" if lang == "pt" else "New ministry")]
    ministry_map = {}

    for _, row in ministries_df.iterrows():
        label = f"{row['name']} ({row['slug']})"
        options.append(label)
        ministry_map[label] = int(row["id"])

    picked = st.selectbox(
        ("Selecionar" if lang == "pt" else "Select"),
        options,
    )

    if picked.startswith("—"):
        selected_ministry = None
    else:
        selected_ministry_id = ministry_map[picked]
        selected_ministry = ministries_df[ministries_df["id"] == selected_ministry_id].iloc[0]
else:
    selected_ministry = None

default_name = safe(selected_ministry["name"]) if selected_ministry is not None else ""
default_slug = safe(selected_ministry["slug"]) if selected_ministry is not None else ""

with st.form("ministry_form"):
    ministry_name = st.text_input(
        "Nome" if lang == "pt" else "Name",
        value=default_name,
    ).strip()

    ministry_slug = st.text_input(
        "Slug",
        value=default_slug,
        help=("Ex: transmissao, louvor, infantil" if lang == "pt" else "Example: media, worship, kids"),
    ).strip().lower()

    submitted = st.form_submit_button(
        "💾 " + ("Salvar ministério" if lang == "pt" else "Save ministry"),
        use_container_width=True,
    )

if submitted:
    if not ministry_name:
        st.error("Nome é obrigatório." if lang == "pt" else "Name is required.")
    elif not ministry_slug:
        st.error("Slug é obrigatório." if lang == "pt" else "Slug is required.")
    else:
        try:
            upsert_ministry(
                {
                    "id": selected_ministry_id,
                    "name": ministry_name,
                    "slug": ministry_slug,
                }
            )
            toast_ok("Ministério salvo com sucesso." if lang == "pt" else "Ministry saved successfully.")
            st.rerun()
        except Exception as e:
            toast_err(("Falha ao salvar ministério: " if lang == "pt" else "Failed to save ministry: ") + str(e))

st.divider()

# =========================
# Leaders management
# =========================
st.subheader("👑 " + ("Líderes do ministério" if lang == "pt" else "Ministry leaders"))

if ministries_df.empty:
    st.info("Cadastre um ministério primeiro." if lang == "pt" else "Create a ministry first.")
    st.stop()

leader_ministry_options = {
    f"{row['name']} ({row['slug']})": int(row["id"])
    for _, row in ministries_df.iterrows()
}

leader_ministry_label = st.selectbox(
    ("Ministério" if lang == "pt" else "Ministry"),
    list(leader_ministry_options.keys()),
)
leader_ministry_id = leader_ministry_options[leader_ministry_label]

try:
    leaders_rows = list_ministry_leaders(leader_ministry_id)
except Exception as e:
    st.error(
        ("Falha ao carregar líderes: " if lang == "pt" else "Failed to load leaders: ") + str(e)
    )
    leaders_rows = []

leaders_df = pd.DataFrame(
    leaders_rows,
    columns=["user_id", "username", "email", "full_name"][: len(leaders_rows[0])]
    if leaders_rows
    else ["user_id", "username", "email", "full_name"]
)

if leaders_df.empty:
    st.info("Nenhum líder definido para este ministério." if lang == "pt" else "No leaders defined for this ministry.")
else:
    st.dataframe(leaders_df, use_container_width=True, hide_index=True)

st.markdown("### " + ("Definir líder" if lang == "pt" else "Set leader"))

try:
    users_rows = list_users()
except Exception as e:
    st.error(("Falha ao carregar usuários: " if lang == "pt" else "Failed to load users: ") + str(e))
    st.stop()

user_labels = []
user_map = {}

for row in users_rows:
    user_id = int(row[0])
    username = safe(row[2]) if len(row) > 2 else ""
    email = safe(row[3]) if len(row) > 3 else ""
    full_name = safe(row[4]) if len(row) > 4 else ""

    label = full_name or username or email or f"User #{user_id}"
    details = " | ".join([x for x in [username, email] if x])
    final_label = f"{label} — {details}" if details else label

    user_labels.append(final_label)
    user_map[final_label] = user_id

picked_user = st.selectbox(
    ("Usuário" if lang == "pt" else "User"),
    user_labels,
)

c1, c2 = st.columns(2)

with c1:
    if st.button("➕ " + ("Definir como líder" if lang == "pt" else "Set as leader"), use_container_width=True):
        try:
            set_ministry_leader(leader_ministry_id, user_map[picked_user], True)
            toast_ok("Líder definido com sucesso." if lang == "pt" else "Leader set successfully.")
            st.rerun()
        except Exception as e:
            toast_err(("Falha ao definir líder: " if lang == "pt" else "Failed to set leader: ") + str(e))

with c2:
    if st.button("➖ " + ("Remover liderança" if lang == "pt" else "Remove leader"), use_container_width=True):
        try:
            set_ministry_leader(leader_ministry_id, user_map[picked_user], False)
            toast_ok("Liderança removida." if lang == "pt" else "Leader removed.")
            st.rerun()
        except Exception as e:
            toast_err(("Falha ao remover liderança: " if lang == "pt" else "Failed to remove leader: ") + str(e))