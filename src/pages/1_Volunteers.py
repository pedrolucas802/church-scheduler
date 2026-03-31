import os
import re
import streamlit as st
import pandas as pd

from src.db import list_volunteers, upsert_volunteer, set_volunteer_active
from src.auth import is_admin
from src.i18n import t, get_lang
from src.emailer import send_email  # send pending + approved emails
from src.services.ui_action_service import clear_page_action, consume_page_action, is_page_action_busy, queue_page_action

st.title(t("vol.title"))
lang = get_lang()
PAGE_KEY = "volunteers_page"

# ======================================================
# Option 1 (Invite link): only people with ?invite=CODE
# ======================================================
INVITE_CODE = (os.getenv("VOLUNTEER_INVITE_CODE") or "").strip()
DEBUG_EMAIL = (os.getenv("DEBUG_EMAIL") or "").strip().lower() in ("1", "true", "yes", "on")

def tr(key: str, pt_fallback: str, en_fallback: str) -> str:
    val = t(key)
    if val == key:
        return pt_fallback if lang == "pt" else en_fallback
    return val

qp = st.query_params
invite = (qp.get("invite") or "").strip()
has_invite = bool(INVITE_CODE) and invite == INVITE_CODE

# =========================
# Helpers
# =========================
def toast_ok(msg: str):
    st.toast(msg, icon="✅")

def toast_warn(msg: str):
    st.toast(msg, icon="⚠️")

def toast_info(msg: str):
    st.toast(msg, icon="ℹ️")

def toast_err(msg: str):
    st.toast(msg, icon="❌")

def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return None

    if digits.startswith("55") and len(digits) >= 12:
        return "+" + digits
    if len(digits) in (10, 11):
        return "+55" + digits
    if len(digits) == 9:
        return digits
    return "+" + digits if len(digits) >= 12 else digits


def parse_bulk_list(text: str):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        cleaned = (
            line.replace("—", "-")
            .replace("–", "-")
            .replace("\u202a", "")
            .replace("\u202c", "")
            .replace("\u200e", "")
            .replace("\u200f", "")
        )

        if "-" not in cleaned:
            name = cleaned.strip()
            phone = None
        else:
            parts = cleaned.split("-", 1)
            name = parts[0].strip()
            phone = parts[1].strip()

        if name:
            out.append((name, normalize_phone(phone) if phone else None))
    return out


def safe_bool_icon(v) -> str:
    return "✅" if bool(v) else "—"


def pretty_active(v) -> str:
    if lang == "pt":
        return "🟢 Ativo" if bool(v) else "🟠 Pendente"
    return "🟢 Active" if bool(v) else "🟠 Pending"


def bump(key: str):
    st.session_state[key] = int(st.session_state.get(key, 0)) + 1


def is_valid_email(email: str) -> bool:
    e = (email or "").strip()
    return ("@" in e) and ("." in e) and (len(e) >= 6)


def get_volunteer_by_id(vol_id: int):
    try:
        rows2 = list_volunteers(active_only=False)
    except Exception:
        return None

    for r in rows2:
        try:
            rid = int(r[0])
        except Exception:
            continue
        if rid == int(vol_id):
            name = (r[1] or "").strip()
            phone = (r[2] or "").strip() if r[2] else ""
            email = (r[3] or "").strip() if r[3] else ""
            active = int(r[4]) if r[4] is not None else 0
            return {"id": rid, "name": name, "phone": phone, "email": email, "active": active}
    return None


def find_existing_volunteer(email: str | None, name: str | None):
    """
    Finds an existing volunteer (to detect pending->active transition) using:
      1) exact email match (preferred)
      2) exact name match (fallback)
    """
    email = (email or "").strip().lower()
    name = (name or "").strip()

    try:
        rows2 = list_volunteers(active_only=False)
    except Exception:
        return None

    by_email = None
    by_name = None

    for r in rows2:
        rid = int(r[0]) if r[0] is not None else None
        r_name = (r[1] or "").strip()
        r_phone = (r[2] or "").strip() if r[2] else ""
        r_email = (r[3] or "").strip().lower() if r[3] else ""
        r_active = int(r[4]) if r[4] is not None else 0

        item = {"id": rid, "name": r_name, "phone": r_phone, "email": r_email, "active": r_active}

        if email and r_email and r_email == email:
            by_email = item
            break

        if name and r_name == name:
            by_name = item

    return by_email or by_name


# =========================
# Email templates
# =========================
def pending_subject() -> str:
    return tr(
        "vol.email.pending_subject",
        "✅ Cadastro recebido — aguardando aprovação",
        "✅ Registration received — awaiting approval",
    )

def pending_body(name: str) -> str:
    return tr(
        "vol.email.pending_body",
        f"Olá, {name}!\n\nRecebemos seu cadastro como voluntário(a) da transmissão.\n"
        "Seu cadastro está como *PENDENTE* e precisa ser aprovado por um admin.\n\n"
        "Assim que for aprovado, você receberá outro e-mail.\n\n"
        "Obrigado! 🙌\n",
        f"Hi, {name}!\n\nWe received your volunteer registration for the streaming team.\n"
        "Your registration is currently *PENDING* and needs admin approval.\n\n"
        "Once approved, you'll receive another email.\n\n"
        "Thank you! 🙌\n",
    )

def approved_subject() -> str:
    return tr(
        "vol.email.approved_subject",
        "🎉 Cadastro aprovado — bem-vindo(a) ao time!",
        "🎉 Approved — welcome to the team!",
    )

def approved_body(name: str) -> str:
    return tr(
        "vol.email.approved_body",
        f"Olá, {name}!\n\nSeu cadastro foi *APROVADO* ✅\n"
        "Agora você já pode aparecer na lista de voluntários ativos e ser escalado(a).\n\n"
        "Obrigado por servir! 🙌\n",
        f"Hi, {name}!\n\nYour registration has been *APPROVED* ✅\n"
        "You can now appear in the active volunteers list and be scheduled.\n\n"
        "Thanks for serving! 🙌\n",
    )

def try_send_email(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    to_email = (to_email or "").strip()
    if not is_valid_email(to_email):
        return False, tr("common.invalid_email", "E-mail inválido.", "Invalid email.")

    try:
        if DEBUG_EMAIL:
            toast_info(f"[DEBUG] send_email(to_email={to_email})")
        send_email(subject, body, to_email=to_email)
        return True, tr("common.email_sent", "E-mail enviado.", "Email sent.")
    except Exception as e:
        return False, str(e)

def send_pending_email(to_email: str, name: str) -> tuple[bool, str]:
    return try_send_email(to_email, pending_subject(), pending_body(name))

def send_approved_email(to_email: str, name: str) -> tuple[bool, str]:
    return try_send_email(to_email, approved_subject(), approved_body(name))


# =========================
# Load data
# =========================
admin = is_admin()

rows = list_volunteers(active_only=False)
df_all = pd.DataFrame(
    rows,
    columns=[
        "id", "name", "phone", "email", "active",
        "thu_ok", "sun_ok", "can_obs", "can_fixed", "can_mobile"
    ],
)

# =========================
# Public area (non-admin)
# =========================
if not admin:
    if not has_invite:
        st.warning(
            tr(
                "vol.public.invite_required",
                "Para cadastrar voluntário, você precisa do link de convite.",
                "To join as a volunteer, you need an invite link.",
            )
        )
    else:
        st.success(
            tr(
                "vol.public.invite_ok",
                "Convite válido ✅ Você pode preencher o formulário abaixo.",
                "Invite valid ✅ You can fill the form below.",
            )
        )

    if has_invite:
        st.subheader(t("vol.public.join_title"))
        st.caption(t("vol.public.join_caption"))

        pub_ver = int(st.session_state.get("pub_form_ver", 0))
        pub_form_key = f"public_volunteer_form_v{pub_ver}"

        with st.form(pub_form_key, clear_on_submit=False):
            name = st.text_input(t("vol.name"), value="").strip()
            email = st.text_input(t("vol.email"), value="").strip()
            phone = st.text_input(t("vol.phone"), value="").strip()

            c1, c2 = st.columns(2)
            with c1:
                thu_ok = st.checkbox(t("vol.thu"), value=True)
                sun_ok = st.checkbox(t("vol.sun"), value=True)
            with c2:
                can_obs = st.checkbox(t("vol.can_obs"), value=True)
                can_fixed = st.checkbox(t("vol.can_fixed"), value=True)
                can_mobile = st.checkbox(t("vol.can_mobile"), value=True)

            b1, b2 = st.columns(2)
            with b1:
                st.form_submit_button(
                    t("vol.public.submit"),
                    use_container_width=True,
                    disabled=is_page_action_busy(PAGE_KEY),
                    on_click=queue_page_action,
                    args=(
                        PAGE_KEY,
                        "public_submit",
                        {
                            "name": name,
                            "email": email,
                            "phone": phone,
                            "thu_ok": bool(thu_ok),
                            "sun_ok": bool(sun_ok),
                            "can_obs": bool(can_obs),
                            "can_fixed": bool(can_fixed),
                            "can_mobile": bool(can_mobile),
                        },
                    ),
                )
            with b2:
                cleared = st.form_submit_button(
                    "🧹 Limpar" if lang == "pt" else "🧹 Clear",
                    use_container_width=True,
                    disabled=is_page_action_busy(PAGE_KEY),
                )

        if cleared:
            toast_info("Formulário limpo." if lang == "pt" else "Form cleared.")
            bump("pub_form_ver")
            st.rerun()

        public_submit_action = consume_page_action(PAGE_KEY, "public_submit")
        if public_submit_action is not None:
            try:
                toast_info("Enviando..." if lang == "pt" else "Submitting...")
                action_name = str(public_submit_action.get("name", "")).strip()
                action_email = str(public_submit_action.get("email", "")).strip()
                action_phone = str(public_submit_action.get("phone", "")).strip()
                if not action_name:
                    toast_err(t("common.name_required"))
                    st.error(t("common.name_required"))
                elif not is_valid_email(action_email):
                    toast_err(t("common.invalid_email"))
                    st.error(t("common.invalid_email"))
                else:
                    with st.spinner("Enviando cadastro..." if lang == "pt" else "Submitting registration..."):
                        upsert_volunteer({
                            "name": action_name,
                            "email": action_email,
                            "phone": normalize_phone(action_phone) if action_phone else None,
                            "active": 0,
                            "thu_ok": 1 if public_submit_action.get("thu_ok") else 0,
                            "sun_ok": 1 if public_submit_action.get("sun_ok") else 0,
                            "can_obs": 1 if public_submit_action.get("can_obs") else 0,
                            "can_fixed": 1 if public_submit_action.get("can_fixed") else 0,
                            "can_mobile": 1 if public_submit_action.get("can_mobile") else 0,
                        })
                        toast_ok("Cadastro salvo (pendente)." if lang == "pt" else "Saved (pending).")

                        ok, msg = send_pending_email(action_email, action_name)
                    if ok:
                        toast_ok("E-mail enviado (aguardando aprovação)." if lang == "pt" else "Pending email sent.")
                    else:
                        toast_warn(("Cadastro salvo, mas falhou ao enviar e-mail: " if lang == "pt" else "Saved, but failed to send email: ") + msg)
                        st.warning(("Cadastro salvo, mas falhou ao enviar e-mail: " if lang == "pt" else "Saved, but failed to send email: ") + msg)

                    st.success(t("vol.public.submitted_ok"))
                    bump("pub_form_ver")
                    st.rerun()
            finally:
                clear_page_action(PAGE_KEY)

    st.divider()
    st.subheader(t("vol.public.list_title"))
    st.caption(t("vol.public.list_caption"))

    df_public = df_all.copy()
    df_public = df_public[df_public["active"].astype(bool)]

    for col in ["phone", "email", "id"]:
        if col in df_public.columns:
            df_public.drop(columns=[col], inplace=True)

    if "active" in df_public.columns:
        df_public["active"] = df_public["active"].apply(pretty_active)

    for col in ["thu_ok", "sun_ok", "can_obs", "can_fixed", "can_mobile"]:
        if col in df_public.columns:
            df_public[col] = df_public[col].apply(safe_bool_icon)

    df_public.rename(
        columns={
            "name": "Nome" if lang == "pt" else "Name",
            "active": "Status",
            "thu_ok": "Qui" if lang == "pt" else "Thu",
            "sun_ok": "Dom" if lang == "pt" else "Sun",
            "can_obs": "OBS",
            "can_fixed": "Fixa" if lang == "pt" else "Fixed",
            "can_mobile": "Móvel" if lang == "pt" else "Mobile",
        },
        inplace=True,
    )

    if st.button(
        "🔄 Recarregar" if lang == "pt" else "🔄 Refresh",
        disabled=is_page_action_busy(PAGE_KEY),
    ):
        toast_info("Atualizando..." if lang == "pt" else "Refreshing...")
        st.rerun()

    st.dataframe(df_public, use_container_width=True)
    st.stop()


# =========================
# Admin area
# =========================
st.subheader(t("vol.admin.section"))

df_admin = df_all.copy()
if "active" in df_admin.columns:
    df_admin["active"] = df_admin["active"].apply(pretty_active)

for col in ["thu_ok", "sun_ok", "can_obs", "can_fixed", "can_mobile"]:
    if col in df_admin.columns:
        df_admin[col] = df_admin[col].apply(safe_bool_icon)

df_admin.rename(
    columns={
        "name": "Nome" if lang == "pt" else "Name",
        "phone": "Telefone" if lang == "pt" else "Phone",
        "email": "Email",
        "active": "Status",
        "thu_ok": "Qui" if lang == "pt" else "Thu",
        "sun_ok": "Dom" if lang == "pt" else "Sun",
        "can_obs": "OBS",
        "can_fixed": "Fixa" if lang == "pt" else "Fixed",
        "can_mobile": "Móvel" if lang == "pt" else "Mobile",
    },
    inplace=True,
)

top_left, top_right = st.columns([3, 1])
with top_left:
    st.caption(t("vol.admin.caption"))
with top_right:
    if st.button(
        "🔄 Recarregar" if lang == "pt" else "🔄 Refresh",
        use_container_width=True,
        disabled=is_page_action_busy(PAGE_KEY),
    ):
        toast_info("Atualizando..." if lang == "pt" else "Refreshing...")
        st.rerun()

st.dataframe(df_admin, use_container_width=True)

# -------- Bulk import --------
st.subheader(t("vol.bulk.title"))
st.caption(t("vol.bulk.caption"))

bulk_text = st.text_area(
    t("vol.bulk.list_label"),
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

st.button(
    t("vol.bulk.import_btn"),
    disabled=is_page_action_busy(PAGE_KEY),
    on_click=queue_page_action,
    args=(
        PAGE_KEY,
        "bulk_import",
        {
            "bulk_text": bulk_text,
            "default_thu_ok": bool(default_thu_ok),
            "default_sun_ok": bool(default_sun_ok),
            "default_can_obs": bool(default_can_obs),
            "default_can_fixed": bool(default_can_fixed),
            "default_can_mobile": bool(default_can_mobile),
        },
    ),
)

bulk_import_action = consume_page_action(PAGE_KEY, "bulk_import")
if bulk_import_action is not None:
    try:
        toast_info("Importando..." if lang == "pt" else "Importing...")
        items = parse_bulk_list(str(bulk_import_action.get("bulk_text", "")))
        if not items:
            toast_err(t("vol.bulk.nothing"))
            st.error(t("vol.bulk.nothing"))
        else:
            imported = 0
            with st.spinner("Importando..." if lang == "pt" else "Importing..."):
                for name, phone in items:
                    upsert_volunteer({
                        "name": name,
                        "phone": phone,
                        "active": 1,
                        "thu_ok": 1 if bulk_import_action.get("default_thu_ok") else 0,
                        "sun_ok": 1 if bulk_import_action.get("default_sun_ok") else 0,
                        "can_obs": 1 if bulk_import_action.get("default_can_obs") else 0,
                        "can_fixed": 1 if bulk_import_action.get("default_can_fixed") else 0,
                        "can_mobile": 1 if bulk_import_action.get("default_can_mobile") else 0,
                    })
                    imported += 1

            toast_ok((f"Importados: {imported}." if lang == "pt" else f"Imported: {imported}."))
            st.success(f"{t('vol.bulk.done_en')}: {imported}. {t('common.refresh')}")
            st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

st.divider()

# -------- Single add/update (Admin) --------
st.subheader(t("vol.add_update"))

adm_ver = int(st.session_state.get("adm_form_ver", 0))
adm_form_key = f"vol_form_admin_v{adm_ver}"

with st.form(adm_form_key, clear_on_submit=False):
    name = st.text_input(t("vol.name"), value="").strip()
    email = st.text_input(t("vol.email"), value="").strip()
    phone = st.text_input(t("vol.phone"), value="").strip()

    c1, c2 = st.columns(2)
    with c1:
        active = st.checkbox(t("vol.active"), value=True)
        thu_ok = st.checkbox(t("vol.thu"), value=True)
        sun_ok = st.checkbox(t("vol.sun"), value=True)
    with c2:
        can_obs = st.checkbox(t("vol.can_obs"), value=True)
        can_fixed = st.checkbox(t("vol.can_fixed"), value=True)
        can_mobile = st.checkbox(t("vol.can_mobile"), value=True)

    b1, b2 = st.columns(2)
    with b1:
        st.form_submit_button(
            t("common.save"),
            use_container_width=True,
            disabled=is_page_action_busy(PAGE_KEY),
            on_click=queue_page_action,
            args=(
                PAGE_KEY,
                "admin_save_volunteer",
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "active": bool(active),
                    "thu_ok": bool(thu_ok),
                    "sun_ok": bool(sun_ok),
                    "can_obs": bool(can_obs),
                    "can_fixed": bool(can_fixed),
                    "can_mobile": bool(can_mobile),
                },
            ),
        )
    with b2:
        cleared = st.form_submit_button(
            "🧹 Limpar" if lang == "pt" else "🧹 Clear",
            use_container_width=True,
            disabled=is_page_action_busy(PAGE_KEY),
        )

if cleared:
    toast_info("Formulário limpo." if lang == "pt" else "Form cleared.")
    bump("adm_form_ver")
    st.rerun()

admin_save_action = consume_page_action(PAGE_KEY, "admin_save_volunteer")
if admin_save_action is not None:
    try:
        toast_info("Salvando..." if lang == "pt" else "Saving...")
        action_name = str(admin_save_action.get("name", "")).strip()
        action_email = str(admin_save_action.get("email", "")).strip()
        action_phone = str(admin_save_action.get("phone", "")).strip()
        if not action_name:
            toast_err(t("common.name_required"))
            st.error(t("common.name_required"))
        elif action_email and not is_valid_email(action_email):
            toast_err(t("common.invalid_email"))
            st.error(t("common.invalid_email"))
        else:
            prev = find_existing_volunteer(email=action_email or None, name=action_name or None)
            prev_active = int(prev["active"]) if prev else None
            new_active = 1 if admin_save_action.get("active") else 0

            with st.spinner("Salvando..." if lang == "pt" else "Saving..."):
                upsert_volunteer({
                    "name": action_name,
                    "email": action_email or None,
                    "phone": normalize_phone(action_phone) if action_phone else None,
                    "active": new_active,
                    "thu_ok": 1 if admin_save_action.get("thu_ok") else 0,
                    "sun_ok": 1 if admin_save_action.get("sun_ok") else 0,
                    "can_obs": 1 if admin_save_action.get("can_obs") else 0,
                    "can_fixed": 1 if admin_save_action.get("can_fixed") else 0,
                    "can_mobile": 1 if admin_save_action.get("can_mobile") else 0,
                })

            toast_ok("Salvo." if lang == "pt" else "Saved.")

            if prev_active == 0 and new_active == 1:
                if is_valid_email(action_email):
                    toast_info("Aprovado ✅ enviando e-mail..." if lang == "pt" else "Approved ✅ sending email...")
                    ok, msg = send_approved_email(action_email, action_name)
                    if ok:
                        toast_ok("E-mail de aprovação enviado." if lang == "pt" else "Approval email sent.")
                        st.info(
                            (f"E-mail de aprovação enviado para {action_email}." if lang == "pt" else f"Approval email sent to {action_email}.")
                        )
                    else:
                        toast_err(("Falha ao enviar e-mail: " if lang == "pt" else "Failed to send email: ") + msg)
                        st.error(
                            ("Falha ao enviar e-mail de aprovação: " if lang == "pt" else "Failed to send approval email: ")
                            + msg
                        )
                else:
                    toast_warn(
                        "Aprovado, mas sem e-mail válido para notificar."
                        if lang == "pt" else
                        "Approved, but no valid email to notify."
                    )
                    st.warning(
                        "Aprovado, mas o voluntário não possui e-mail válido para receber notificação."
                        if lang == "pt" else
                        "Approved, but the volunteer has no valid email to notify."
                    )

            st.success(t("common.refresh"))
            bump("adm_form_ver")
            st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

# -------- Quick toggle (Admin) --------
st.subheader(t("vol.quick_toggle"))
id_to_toggle = st.number_input(t("vol.volunteer_id"), min_value=1, step=1)
toggle_active = st.selectbox(t("vol.set_active_to"), [True, False])

st.button(
    "Apply / Aplicar",
    disabled=is_page_action_busy(PAGE_KEY),
    on_click=queue_page_action,
    args=(PAGE_KEY, "quick_toggle_volunteer", {"volunteer_id": int(id_to_toggle), "toggle_active": bool(toggle_active)}),
)

quick_toggle_action = consume_page_action(PAGE_KEY, "quick_toggle_volunteer")
if quick_toggle_action is not None:
    try:
        vid = int(quick_toggle_action["volunteer_id"])
        new_active_state = bool(quick_toggle_action["toggle_active"])
        toast_info(("Aplicando..." if lang == "pt" else "Applying...") + f" (ID {vid})")

        before = get_volunteer_by_id(vid)
        if not before:
            toast_err("ID não encontrado." if lang == "pt" else "ID not found.")
            st.error("ID não encontrado." if lang == "pt" else "ID not found.")
        else:
            before_active = int(before["active"])
            before_email = (before.get("email") or "").strip()
            before_name = (before.get("name") or f"#{vid}").strip()

            with st.spinner("Aplicando..." if lang == "pt" else "Applying..."):
                set_volunteer_active(vid, new_active_state)

            after = get_volunteer_by_id(vid)
            after_email = (after.get("email") or before_email).strip() if after else before_email
            after_name = (after.get("name") or before_name).strip() if after else before_name

            if (before_active == 0) and new_active_state:
                toast_info("Ativado ✅ enviando e-mail..." if lang == "pt" else "Activated ✅ sending email...")
                if not is_valid_email(after_email):
                    toast_warn(
                        "Ativado, mas sem e-mail válido para notificar."
                        if lang == "pt" else
                        "Activated, but no valid email to notify."
                    )
                    st.warning(
                        "Ativado, mas o voluntário não possui e-mail válido para receber notificação."
                        if lang == "pt" else
                        "Activated, but the volunteer has no valid email to notify."
                    )
                else:
                    ok, msg = send_approved_email(after_email, after_name)
                    if ok:
                        toast_ok(
                            f"E-mail de aprovação enviado: {after_email}"
                            if lang == "pt" else
                            f"Approval email sent: {after_email}"
                        )
                        st.info(
                            f"E-mail de aprovação enviado para {after_email}."
                            if lang == "pt" else
                            f"Approval email sent to {after_email}."
                        )
                    else:
                        toast_err(("Falha ao enviar e-mail: " if lang == "pt" else "Failed to send email: ") + msg)
                        st.error(
                            ("Falha ao enviar e-mail de aprovação: " if lang == "pt" else "Failed to send approval email: ")
                            + msg
                        )

            if (before_active == 1) and (not new_active_state):
                toast_ok("Desativado." if lang == "pt" else "Deactivated.")

            toast_ok(t("common.refresh"))
            st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

st.caption(t("vol.note.upsert_key"))
