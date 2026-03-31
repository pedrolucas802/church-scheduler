import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.i18n import get_lang, t
from src.services.evolution_api_service import EvolutionAPIService, normalize_whatsapp_number
from src.services.ui_action_service import clear_page_action, consume_page_action, is_page_action_busy, queue_page_action


lang = get_lang()
PAGE_KEY = "checklist_page"
FORTALEZA_TZ = ZoneInfo("America/Fortaleza")


def tr(key: str, pt_fallback: str, en_fallback: str) -> str:
    value = t(key)
    if value == key:
        return pt_fallback if lang == "pt" else en_fallback
    return value


CHECKLIST_SECTIONS = [
    {
        "id": "before",
        "title": {"pt": "Antes do culto", "en": "Before the service"},
        "items": [
            {
                "id": "open_obs_youtube",
                "number": 1,
                "pt": "Ligar computador, abrir: OBS e YouTube",
                "en": "Turn on the computer and open OBS + YouTube",
            },
            {
                "id": "position_camera",
                "number": 2,
                "pt": "Ligar e posicionar câmera",
                "en": "Turn on and position the camera",
            },
            {
                "id": "connect_camera_cables",
                "number": 3,
                "pt": "Conectar cabo de energia e de captura da câmera",
                "en": "Connect the camera power and capture cables",
            },
            {
                "id": "turn_on_projectors",
                "number": 4,
                "pt": "Ligar projetores",
                "en": "Turn on the projectors",
            },
            {
                "id": "send_image_to_projectors",
                "number": 5,
                "pt": "Passar imagem para os projetores",
                "en": "Send the image to the projectors",
            },
            {
                "id": "update_cn_news",
                "number": 6,
                "pt": "Atualizar CN News",
                "en": "Update CN News",
            },
            {
                "id": "check_extra_video",
                "number": 7,
                "pt": "Checar se precisa de algum vídeo extra",
                "en": "Check whether any extra video is needed",
            },
            {
                "id": "test_gcs",
                "number": 8,
                "pt": "Testar GCs (Dizmo, consolidar, etc.) em ambas: câmera fixa e móvel",
                "en": "Test GCs (Dizmo, follow-up, etc.) on both fixed and mobile cameras",
            },
            {
                "id": "test_fixed_camera",
                "number": 9,
                "pt": "Testar câmera fixa",
                "en": "Test the fixed camera",
            },
            {
                "id": "test_mobile_camera",
                "number": 10,
                "pt": "Testar câmera móvel",
                "en": "Test the mobile camera",
            },
            {
                "id": "check_audio_to_obs",
                "number": 11,
                "pt": "Verificar se o áudio da mesa está chegando no OBS",
                "en": "Check whether mixer audio is reaching OBS",
            },
            {
                "id": "schedule_youtube",
                "number": 12,
                "pt": "Programar YouTube",
                "en": "Schedule the YouTube stream",
            },
            {
                "id": "update_youtube_title_cover",
                "number": 13,
                "pt": "Atualizar título e capa do YouTube",
                "en": "Update the YouTube title and thumbnail",
            },
            {
                "id": "check_youtube_public",
                "number": 14,
                "pt": 'Checar se a transmissão do YouTube está "Pública"',
                "en": 'Check whether the YouTube stream is set to "Public"',
            },
            {
                "id": "copy_key_start_youtube",
                "number": 15,
                "pt": "Copiar chave e iniciar transmissão no YouTube",
                "en": "Copy the key and start the stream on YouTube",
            },
            {
                "id": "copy_key_start_obs",
                "number": 16,
                "pt": "Copiar chave da transmissão no OBS e iniciar",
                "en": "Copy the stream key into OBS and start it",
            },
        ],
    },
    {
        "id": "during",
        "title": {"pt": "Durante o culto", "en": "During the service"},
        "items": [
            {
                "id": "monitor_audio_other_device",
                "number": 17,
                "pt": "Checar áudio da transmissão através de outro dispositivo ao decorrer do culto",
                "en": "Monitor stream audio from another device during the service",
            },
        ],
    },
    {
        "id": "after",
        "title": {"pt": "Depois do culto", "en": "After the service"},
        "items": [
            {
                "id": "store_radios",
                "number": 18,
                "pt": "Guardar rádios",
                "en": "Put the radios away",
            },
            {
                "id": "store_headphones",
                "number": 19,
                "pt": "Guardar fones",
                "en": "Put the headphones away",
            },
            {
                "id": "store_camera_and_cables",
                "number": 20,
                "pt": "Guardar câmera e cabos",
                "en": "Put the camera and cables away",
            },
            {
                "id": "turn_off_projectors",
                "number": 21,
                "pt": "Desligar os projetores",
                "en": "Turn off the projectors",
            },
            {
                "id": "turn_off_pc",
                "number": 22,
                "pt": "Desligar o computador",
                "en": "Turn off the PC",
            },
        ],
    },
]


def item_text(item: dict) -> str:
    return item["pt"] if lang == "pt" else item["en"]


all_items = [item for section in CHECKLIST_SECTIONS for item in section["items"]]
legacy_status_key = "service_checklist_status_v2"


def checkbox_key(item_id: str) -> str:
    return f"checklist_{item_id}"


legacy_status = st.session_state.get(legacy_status_key, {})
for item in all_items:
    key = checkbox_key(item["id"])
    if key not in st.session_state:
        st.session_state[key] = bool(legacy_status.get(item["id"], False))


def set_items(item_ids: list[str], value: bool):
    for item_id in item_ids:
        st.session_state[checkbox_key(item_id)] = value


def section_counts(section: dict) -> tuple[int, int]:
    items = section["items"]
    done = sum(1 for item in items if st.session_state.get(checkbox_key(item["id"]), False))
    return done, len(items)


def next_pending_item() -> dict | None:
    for item in all_items:
        if not st.session_state.get(checkbox_key(item["id"]), False):
            return item
    return None


def whatsapp_notify_number() -> str | None:
    return normalize_whatsapp_number(os.getenv("CHECKLIST_CONFIRM_WHATSAPP_NUMBER"))


def in_fortaleza(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=FORTALEZA_TZ)
    return dt.astimezone(FORTALEZA_TZ)


def now_in_fortaleza() -> datetime:
    return datetime.now(FORTALEZA_TZ)


def format_dt_for_message(dt: datetime) -> str:
    localized = in_fortaleza(dt)
    return localized.strftime("%d/%m/%Y %H:%M") if lang == "pt" else localized.strftime("%Y-%m-%d %H:%M")


def build_confirmation_message(sent_at: datetime) -> str:
    section_lines = []
    for section in CHECKLIST_SECTIONS:
        done, total_in_section = section_counts(section)
        section_title = section["title"]["pt"] if lang == "pt" else section["title"]["en"]
        section_lines.append(f"- {section_title}: {done}/{total_in_section}")

    if lang == "pt":
        return (
            "✅ Checklist da transmissão confirmada\n\n"
            f"Data/Hora: {format_dt_for_message(sent_at)}\n"
            f"Itens concluídos: {completed}/{total}\n"
            "Resumo:\n"
            + "\n".join(section_lines)
        )

    return (
        "✅ Streaming checklist confirmed\n\n"
        f"Date/Time: {format_dt_for_message(sent_at)}\n"
        f"Completed items: {completed}/{total}\n"
        "Summary:\n"
        + "\n".join(section_lines)
    )


st.markdown(
    """
    <style>
      .checklist-chip {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid rgba(0, 160, 120, 0.35);
        background: rgba(0, 160, 120, 0.10);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("✅ " + tr("checklist.title", "Checklist da Transmissão", "Streaming Checklist"))
st.caption(
    tr(
        "checklist.caption",
        "Use esta página como um preflight da transmissão para não esquecer nada antes, durante e depois do culto.",
        "Use this page like a streaming preflight so nothing is forgotten before, during, or after the service.",
    )
)

completed = sum(1 for item in all_items if st.session_state.get(checkbox_key(item["id"]), False))
total = len(all_items)
remaining = total - completed
progress = (completed / total) if total else 0.0
next_item = next_pending_item()
page_busy = is_page_action_busy(PAGE_KEY)

summary_col1, summary_col2, summary_col3 = st.columns(3)
with summary_col1:
    st.metric(tr("checklist.completed", "Concluídos", "Completed"), f"{completed}/{total}")
with summary_col2:
    st.metric(tr("checklist.remaining", "Pendentes", "Remaining"), str(remaining))
with summary_col3:
    st.metric(
        tr("checklist.next_item", "Próximo item", "Next item"),
        (
            f"{next_item['number']}. {item_text(next_item)}"
            if next_item
            else tr("checklist.next_item_done", "Tudo concluído", "All done")
        ),
    )

st.progress(progress)

top_actions_col1, top_actions_col2 = st.columns(2)
with top_actions_col1:
    if st.button(
        tr("checklist.mark_all", "✅ Marcar tudo", "✅ Mark all"),
        use_container_width=True,
        disabled=page_busy,
    ):
        set_items([item["id"] for item in all_items], True)
        st.rerun()

with top_actions_col2:
    if st.button(
        tr("checklist.clear_all", "🧹 Limpar checklist", "🧹 Clear checklist"),
        use_container_width=True,
        disabled=page_busy,
    ):
        set_items([item["id"] for item in all_items], False)
        st.rerun()

st.divider()

for section in CHECKLIST_SECTIONS:
    done, section_total = section_counts(section)
    item_ids = [item["id"] for item in section["items"]]
    section_progress = (done / section_total) if section_total else 0.0

    with st.container(border=True):
        header_col1, header_col2, header_col3 = st.columns([2.5, 1, 1])
        with header_col1:
            st.subheader(section["title"]["pt"] if lang == "pt" else section["title"]["en"])
            st.markdown(
                f"<span class='checklist-chip'>{done}/{section_total}</span>",
                unsafe_allow_html=True,
            )
        with header_col2:
            if st.button(
                tr("checklist.mark_section", "Marcar seção", "Mark section"),
                key=f"mark_{section['id']}",
                use_container_width=True,
                disabled=page_busy,
            ):
                set_items(item_ids, True)
                st.rerun()
        with header_col3:
            if st.button(
                tr("checklist.clear_section", "Limpar seção", "Clear section"),
                key=f"clear_{section['id']}",
                use_container_width=True,
                disabled=page_busy,
            ):
                set_items(item_ids, False)
                st.rerun()

        st.progress(section_progress)

        for item in section["items"]:
            label = f"{item['number']}. {item_text(item)}"
            st.checkbox(label, key=checkbox_key(item["id"]), disabled=page_busy)

pending_items = [item for item in all_items if not st.session_state.get(checkbox_key(item["id"]), False)]

st.divider()
st.subheader(tr("checklist.pending_title", "Pendências", "Pending items"))
if pending_items:
    for item in pending_items:
        st.write(f"- {item['number']}. {item_text(item)}")
else:
    st.success(
        tr(
            "checklist.done_message",
            "Checklist completa. Tudo certo para encerrar.",
            "Checklist complete. Everything is ready to wrap up.",
        )
    )

st.divider()
st.subheader(tr("checklist.confirm_title", "Confirmação final", "Final confirmation"))
st.caption(
    tr(
        "checklist.confirm_caption",
        "Quando tudo estiver concluído, envie uma confirmação para o WhatsApp configurado.",
        "Once everything is complete, send a confirmation to the configured WhatsApp contact.",
    )
)

evolution_service = EvolutionAPIService.from_env()
notify_number = whatsapp_notify_number()
missing_config = EvolutionAPIService.missing_env_vars()
if not notify_number:
    missing_config.append("CHECKLIST_CONFIRM_WHATSAPP_NUMBER")

confirmation_disabled = (completed != total) or bool(missing_config)
last_sent_key = "checklist_last_confirmation_sent_at"

if completed != total:
    st.info(
        tr(
            "checklist.confirm_requires_complete",
            "Complete todos os itens para liberar a confirmação final.",
            "Complete every item to enable the final confirmation.",
        )
    )
elif missing_config:
    st.warning(
        tr(
            "checklist.confirm_missing_config",
            "Configure estas variáveis de ambiente para enviar no WhatsApp:",
            "Configure these environment variables to send via WhatsApp:",
        )
        + " "
        + ", ".join(missing_config)
    )

if st.button(
    tr(
        "checklist.confirm_button",
        "📲 Confirmar checklist e enviar no WhatsApp",
        "📲 Confirm checklist and send via WhatsApp",
    ),
    type="primary",
    use_container_width=True,
    disabled=confirmation_disabled or page_busy,
    on_click=queue_page_action,
    args=(PAGE_KEY, "send_checklist_confirmation"),
):
    pass

confirm_action = consume_page_action(PAGE_KEY, "send_checklist_confirmation")
if confirm_action is not None:
    try:
        sent_at = now_in_fortaleza()
        with st.spinner("Enviando confirmação..." if lang == "pt" else "Sending confirmation..."):
            response = evolution_service.send_text(
                number=notify_number,
                text=build_confirmation_message(sent_at),
            )

        if response.success:
            st.session_state[last_sent_key] = sent_at.isoformat()
            st.success(
                tr(
                    "checklist.confirm_success",
                    "Confirmação enviada no WhatsApp com sucesso.",
                    "Confirmation sent to WhatsApp successfully.",
                )
            )
        else:
            if response.error and response.error.startswith("instance_not_open:"):
                state = response.error.split(":", 1)[1]
                st.error(
                    tr(
                        "checklist.confirm_not_connected",
                        "O WhatsApp ainda não está conectado no Evolution. Gere e escaneie um QR válido antes de enviar a confirmação.",
                        "WhatsApp is not connected in Evolution yet. Generate and scan a valid QR code before sending the confirmation.",
                    )
                    + f" ({state})"
                )
            else:
                st.error(
                    tr(
                        "checklist.confirm_failed",
                        "Falha ao enviar a confirmação no WhatsApp.",
                        "Failed to send the WhatsApp confirmation.",
                    )
                    + f" ({response.error})"
                )
    finally:
        clear_page_action(PAGE_KEY)

last_sent_iso = st.session_state.get(last_sent_key)
if last_sent_iso:
    try:
        last_sent_dt = datetime.fromisoformat(last_sent_iso)
        st.caption(
            tr(
                "checklist.confirm_last_sent",
                "Última confirmação enviada em:",
                "Last confirmation sent at:",
            )
            + f" {format_dt_for_message(in_fortaleza(last_sent_dt))}"
        )
    except ValueError:
        pass
