import re
import streamlit as st
import pandas as pd
from src.db import list_volunteers, upsert_volunteer, set_volunteer_active
from src.auth import is_admin
from src.i18n import t, get_lang

st.title(t("vol.title"))

def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return None

    # if already has country code 55
    if digits.startswith("55") and len(digits) >= 12:
        return "+" + digits

    # if user pasted just DDD+number (10 or 11 digits)
    if len(digits) in (10, 11):
        return "+55" + digits

    # if someone pasted only 9 digits etc -> keep as best-effort with +55 if plausible
    if len(digits) == 9:
        # missing DDD, we can't guess; keep raw digits without country code
        return digits

    return "+" + digits if len(digits) >= 12 else digits


def parse_bulk_list(text: str):
    """
    Accept lines like:
      NAME - PHONE
      NAME – PHONE
      NAME — PHONE
    Also handles weird unicode dashes and invisible chars.
    Returns list of (name, phone).
    """
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # replace common unicode separators with hyphen
        cleaned = (
            line.replace("—", "-")
                .replace("–", "-")
                .replace("-", "-")
                .replace("\u202a", "")
                .replace("\u202c", "")
                .replace("\u200e", "")
                .replace("\u200f", "")
        )

        # split on first hyphen
        if "-" not in cleaned:
            # if no separator, treat entire line as name
            name = cleaned.strip()
            phone = None
        else:
            parts = cleaned.split("-", 1)
            name = parts[0].strip()
            phone = parts[1].strip()

        if name:
            out.append((name, normalize_phone(phone) if phone else None))
    return out


# -------- Table view --------
rows = list_volunteers(active_only=False)
df = pd.DataFrame(
    rows,
    columns=["id", "name", "phone", "active", "thu_ok", "sun_ok", "can_obs", "can_fixed", "can_mobile"]
)
st.dataframe(df, use_container_width=True)

if not is_admin():
    st.warning(t("common.admin_required"))
    st.stop()

lang = get_lang()

# -------- Bulk import --------
st.subheader("Importar em massa / Bulk import")
st.caption(
    "Cole a lista no formato 'NOME - TELEFONE' (uma linha por pessoa). "
    if lang == "pt"
    else "Paste the list as 'NAME - PHONE' (one per line)."
)

bulk_text = st.text_area(
    "Lista / List",
    height=220,
    placeholder="Ex:\nPedro - +55 85 99999-0000\nMaria - 85999990000"
)

c1, c2 = st.columns(2)
with c1:
    default_thu_ok = st.checkbox(t("vol.thu"), value=True, key="bulk_thu_ok")
    default_sun_ok = st.checkbox(t("vol.sun"), value=True, key="bulk_sun_ok")
with c2:
    default_can_obs = st.checkbox(t("vol.can_obs"), value=True, key="bulk_can_obs")
    default_can_fixed = st.checkbox(t("vol.can_fixed"), value=True, key="bulk_can_fixed")
    default_can_mobile = st.checkbox(t("vol.can_mobile"), value=True, key="bulk_can_mobile")

if st.button("Importar / Import"):
    items = parse_bulk_list(bulk_text)
    if not items:
        st.error("Nada para importar / Nothing to import.")
    else:
        imported = 0
        for name, phone in items:
            upsert_volunteer({
                "name": name,
                "phone": phone,
                "active": 1,
                "thu_ok": 1 if default_thu_ok else 0,
                "sun_ok": 1 if default_sun_ok else 0,
                "can_obs": 1 if default_can_obs else 0,
                "can_fixed": 1 if default_can_fixed else 0,
                "can_mobile": 1 if default_can_mobile else 0,
            })
            imported += 1

        st.success(
            (f"Importados/atualizados: {imported}. {t('common.refresh')}")
            if lang == "pt" else
            (f"Imported/updated: {imported}. {t('common.refresh')}")
        )

st.divider()

# -------- Single add/update (kept) --------
st.subheader(t("vol.add_update"))

with st.form("vol_form"):
    name = st.text_input(t("vol.name")).strip()
    phone = st.text_input(t("vol.phone")).strip()

    c1, c2 = st.columns(2)
    with c1:
        active = st.checkbox(t("vol.active"), value=True)
        thu_ok = st.checkbox(t("vol.thu"), value=True)
        sun_ok = st.checkbox(t("vol.sun"), value=True)
    with c2:
        can_obs = st.checkbox(t("vol.can_obs"), value=True)
        can_fixed = st.checkbox(t("vol.can_fixed"), value=True)
        can_mobile = st.checkbox(t("vol.can_mobile"), value=True)

    submit = st.form_submit_button(t("common.save"))
    if submit:
        if not name:
            st.error("Nome é obrigatório / Name is required.")
        else:
            upsert_volunteer({
                "name": name,
                "phone": normalize_phone(phone) if phone else None,
                "active": 1 if active else 0,
                "thu_ok": 1 if thu_ok else 0,
                "sun_ok": 1 if sun_ok else 0,
                "can_obs": 1 if can_obs else 0,
                "can_fixed": 1 if can_fixed else 0,
                "can_mobile": 1 if can_mobile else 0,
            })
            st.success(t("common.refresh"))

st.subheader(t("vol.quick_toggle"))
id_to_toggle = st.number_input(t("vol.volunteer_id"), min_value=1, step=1)
toggle_active = st.selectbox(t("vol.set_active_to"), [True, False])

if st.button("Apply / Aplicar"):
    set_volunteer_active(int(id_to_toggle), bool(toggle_active))
    st.success(t("common.refresh"))