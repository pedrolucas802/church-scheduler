from datetime import datetime

import pandas as pd
import streamlit as st

from src.auth import is_admin
from src.db import list_reminders, list_sent_reminders, mark_reminder_sent
from src.i18n import get_lang, t
from src.reminders.runner import (
    now_in_fortaleza_naive,
    role_label,
    send_due_whatsapp_reminders,
)
from src.reminders.scheduler import (
    apply_scheduler_setting,
    scheduler_enabled,
    scheduler_running,
    set_scheduler_enabled,
)
from src.services.evolution_api_service import EvolutionAPIService, normalize_whatsapp_number
from src.services.ui_action_service import clear_page_action, consume_page_action, is_page_action_busy, queue_page_action

st.title(t("rem.title"))
lang = get_lang()
PAGE_KEY = "reminders_page"


def _single_reminder_message(service_dt: datetime, role: str, name: str) -> str:
    if lang == "pt":
        return (
            f"Olá, {name}!\n\n"
            "Passando para lembrar da sua escala de transmissão.\n\n"
            f"Data e horário: {service_dt.strftime('%d/%m/%Y %H:%M')}\n"
            f"Função: {role_label(role, lang)}\n\n"
            "Se surgir qualquer imprevisto, avise o quanto antes para conseguirmos ajustar.\n\n"
            "Obrigado por servir."
        )

    return (
        f"Hi {name}!\n\n"
        "Just a quick reminder about your streaming schedule.\n\n"
        f"Date and time: {service_dt.strftime('%Y-%m-%d %H:%M')}\n"
        f"Role: {role_label(role, lang)}\n\n"
        "If anything comes up, please let us know as soon as possible so we can adjust it.\n\n"
        "Thanks for serving."
    )


def _friendly_send_error(error: str | None) -> str:
    if not error:
        return "Falha desconhecida." if lang == "pt" else "Unknown failure."
    if error.startswith("instance_not_open:"):
        state = error.split(":", 1)[1] or "unknown"
        return (
            f"O WhatsApp do Evolution não está conectado. Estado atual: {state}."
            if lang == "pt"
            else f"Evolution WhatsApp is not connected. Current state: {state}."
        )
    if error == "invalid_number":
        return "Número de WhatsApp inválido." if lang == "pt" else "Invalid WhatsApp number."
    if error == "timeout":
        return "A requisição ao Evolution expirou." if lang == "pt" else "Evolution request timed out."
    return f"Falha ao enviar: {error}" if lang == "pt" else f"Failed to send: {error}"


status = st.selectbox(t("rem.filter"), ["PENDING", "SENT", "FAILED", "CANCELLED", "ALL"])
rows = list_reminders(status=None if status == "ALL" else status)

cols_10 = ["id", "status", "send_at_iso", "attempts", "last_error", "service_dt", "role", "name", "email", "phone"]
cols_9 = ["id", "status", "send_at_iso", "attempts", "last_error", "service_dt", "role", "name", "email"]

if rows:
    width = len(rows[0])
else:
    width = 10

if width == 9:
    df = pd.DataFrame(rows, columns=cols_9)
elif width == 10:
    df = pd.DataFrame(rows, columns=cols_10)
else:
    df = pd.DataFrame(rows)
    st.warning(
        f"Schema inesperado em list_reminders(): {width} colunas. Ajuste a função ou esta página."
        if lang == "pt"
        else f"Unexpected schema from list_reminders(): {width} columns. Update the function or this page."
    )

st.dataframe(df, use_container_width=True)
st.caption(t("rem.admin_note"))

if not is_admin():
    st.warning(t("common.admin_required"))
    st.stop()

st.divider()
st.subheader("🤖 " + ("Automação de reminders" if lang == "pt" else "Reminder automation"))

automation_enabled = scheduler_enabled()
automation_running = scheduler_running()

if automation_enabled:
    st.success(
        (
            "Automação ligada. O scheduler de reminders está habilitado."
            if lang == "pt"
            else "Automation is on. The reminder scheduler is enabled."
        )
        + (" (running)" if automation_running and lang != "pt" else (" (rodando)" if automation_running else ""))
    )
else:
    st.warning(
        "Automação desligada. Nenhum reminder automatico será enviado."
        if lang == "pt"
        else "Automation is off. No automatic reminders will be sent."
    )

toggle_col1, toggle_col2 = st.columns(2)
with toggle_col1:
    st.button(
        "🟢 " + ("Ligar automação" if lang == "pt" else "Enable automation"),
        disabled=is_page_action_busy(PAGE_KEY) or automation_enabled,
        on_click=queue_page_action,
        args=(PAGE_KEY, "enable_scheduler"),
        use_container_width=True,
    )
with toggle_col2:
    st.button(
        "⏸️ " + ("Desligar automação" if lang == "pt" else "Disable automation"),
        disabled=is_page_action_busy(PAGE_KEY) or (not automation_enabled),
        on_click=queue_page_action,
        args=(PAGE_KEY, "disable_scheduler"),
        use_container_width=True,
    )

enable_scheduler_action = consume_page_action(PAGE_KEY, "enable_scheduler")
if enable_scheduler_action is not None:
    try:
        with st.spinner("Ligando automação..." if lang == "pt" else "Enabling automation..."):
            set_scheduler_enabled(True)
            apply_scheduler_setting()
        st.toast(
            "Automação de reminders ligada."
            if lang == "pt"
            else "Reminder automation enabled.",
            icon="✅",
        )
        st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

disable_scheduler_action = consume_page_action(PAGE_KEY, "disable_scheduler")
if disable_scheduler_action is not None:
    try:
        with st.spinner("Desligando automação..." if lang == "pt" else "Disabling automation..."):
            set_scheduler_enabled(False)
            apply_scheduler_setting()
        st.toast(
            "Automação de reminders desligada."
            if lang == "pt"
            else "Reminder automation disabled.",
            icon="⏸️",
        )
        st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

sent_log_rows = list_sent_reminders(limit=50)
st.caption(
    "Últimos reminders enviados."
    if lang == "pt"
    else "Most recent sent reminders."
)
if sent_log_rows:
    sent_df = pd.DataFrame(
        sent_log_rows,
        columns=["id", "sent_at", "send_at_iso", "service_dt", "role", "name", "phone", "attempts"],
    )
    sent_df["role"] = sent_df["role"].apply(lambda role: role_label(role, lang))
    sent_df = sent_df.rename(
        columns={
            "id": "ID",
            "sent_at": "Enviado em" if lang == "pt" else "Sent at",
            "send_at_iso": "Previsto" if lang == "pt" else "Scheduled at",
            "service_dt": "Culto" if lang == "pt" else "Service",
            "role": "Função" if lang == "pt" else "Role",
            "name": "Nome" if lang == "pt" else "Name",
            "phone": "Telefone" if lang == "pt" else "Phone",
            "attempts": "Tentativas" if lang == "pt" else "Attempts",
        }
    )
    st.dataframe(sent_df, use_container_width=True, hide_index=True)
else:
    st.info(
        "Nenhum reminder foi enviado ainda."
        if lang == "pt"
        else "No reminders have been sent yet."
    )

rem_by_id = {int(row[0]): row for row in rows}

st.divider()
st.subheader(
    "💬 "
    + (
        "Enviar lembrete por WhatsApp (1 reminder)"
        if lang == "pt"
        else "Send WhatsApp reminder (1 reminder)"
    )
)

rid = st.number_input("Reminder ID", min_value=1, step=1)

c1, c2 = st.columns(2)

with c1:
    st.button(
        "📲 " + ("Enviar e marcar como SENT" if lang == "pt" else "Send & mark as SENT"),
        disabled=is_page_action_busy(PAGE_KEY),
        on_click=queue_page_action,
        args=(PAGE_KEY, "send_single_reminder", {"rid": int(rid)}),
    )

with c2:
    st.button(
        t("rem.simulate"),
        disabled=is_page_action_busy(PAGE_KEY),
        on_click=queue_page_action,
        args=(PAGE_KEY, "simulate_single_reminder", {"rid": int(rid)}),
    )

single_send_action = consume_page_action(PAGE_KEY, "send_single_reminder")
if single_send_action is not None:
    try:
        if int(single_send_action["rid"]) not in rem_by_id:
            st.toast("ID inválido para o filtro atual." if lang == "pt" else "Invalid ID for current filter.", icon="⚠️")
        else:
            row = rem_by_id[int(single_send_action["rid"])]
            if len(row) == 9:
                _id, _status, _send_at, _attempts, _err, _service_dt, _role, _name, _email = row
                _phone = None
            else:
                _id, _status, _send_at, _attempts, _err, _service_dt, _role, _name, _email, _phone = row

            if not _phone:
                st.toast(
                    "Sem número de WhatsApp cadastrado." if lang == "pt" else "No WhatsApp number set.",
                    icon="⚠️",
                )
            else:
                service = EvolutionAPIService.from_env()
                if service is None:
                    missing = ", ".join(EvolutionAPIService.missing_env_vars())
                    st.toast(
                        (
                            f"Configuração do Evolution incompleta: {missing}"
                            if lang == "pt"
                            else f"Evolution config is incomplete: {missing}"
                        ),
                        icon="⚠️",
                    )
                else:
                    service_dt = datetime.fromisoformat(_service_dt)
                    destination_number = normalize_whatsapp_number(_phone)
                    if not destination_number:
                        st.toast(
                            "Sem número de WhatsApp válido para envio."
                            if lang == "pt"
                            else "No valid WhatsApp number for delivery.",
                            icon="⚠️",
                        )
                    else:
                        with st.spinner("Enviando lembrete..." if lang == "pt" else "Sending reminder..."):
                            response = service.send_text(
                                number=destination_number,
                                text=_single_reminder_message(service_dt=service_dt, role=_role, name=_name),
                            )
                        if response.success:
                            mark_reminder_sent(int(single_send_action["rid"]))
                            st.toast(
                                "WhatsApp enviado ✅ e marcado como SENT."
                                if lang == "pt"
                                else "WhatsApp sent ✅ and marked SENT.",
                                icon="📲",
                            )
                            st.rerun()
                        else:
                            st.toast(_friendly_send_error(response.error), icon="❌")
    finally:
        clear_page_action(PAGE_KEY)

simulate_action = consume_page_action(PAGE_KEY, "simulate_single_reminder")
if simulate_action is not None:
    try:
        mark_reminder_sent(int(simulate_action["rid"]))
        st.toast("OK ✅", icon="✅")
        st.rerun()
    finally:
        clear_page_action(PAGE_KEY)

st.divider()
st.subheader(
    "📝 "
    + (
        "Enviar mensagem manual por WhatsApp"
        if lang == "pt"
        else "Send custom WhatsApp message"
    )
)
st.caption(
    (
        "Use este bloco para testar envios ou mandar uma mensagem manual para qualquer número."
        if lang == "pt"
        else "Use this section to test sends or deliver a manual message to any number."
    )
)

manual_number = st.text_input(
    "Número de destino" if lang == "pt" else "Destination number",
    placeholder="5585999999999",
    key="manual_whatsapp_number",
)
manual_text = st.text_area(
    "Mensagem" if lang == "pt" else "Message",
    placeholder=(
        "Olá! Esta é uma mensagem manual enviada pelo Church Scheduler."
        if lang == "pt"
        else "Hello! This is a manual message sent from Church Scheduler."
    ),
    height=140,
    key="manual_whatsapp_text",
)

st.button(
    "📨 " + ("Enviar mensagem manual" if lang == "pt" else "Send custom message"),
    disabled=is_page_action_busy(PAGE_KEY),
    on_click=queue_page_action,
    args=(
        PAGE_KEY,
        "send_manual_whatsapp",
        {
            "number": manual_number,
            "text": manual_text,
        },
    ),
)

manual_send_action = consume_page_action(PAGE_KEY, "send_manual_whatsapp")
if manual_send_action is not None:
    try:
        raw_number = str(manual_send_action.get("number") or "").strip()
        raw_text = str(manual_send_action.get("text") or "").strip()

        destination_number = normalize_whatsapp_number(raw_number)
        if not destination_number:
            st.toast(
                "Informe um número de WhatsApp válido."
                if lang == "pt"
                else "Enter a valid WhatsApp number.",
                icon="⚠️",
            )
        elif not raw_text:
            st.toast(
                "Digite uma mensagem antes de enviar."
                if lang == "pt"
                else "Enter a message before sending.",
                icon="⚠️",
            )
        else:
            service = EvolutionAPIService.from_env()
            if service is None:
                missing = ", ".join(EvolutionAPIService.missing_env_vars())
                st.toast(
                    (
                        f"Configuração do Evolution incompleta: {missing}"
                        if lang == "pt"
                        else f"Evolution config is incomplete: {missing}"
                    ),
                    icon="⚠️",
                )
            else:
                with st.spinner("Enviando mensagem..." if lang == "pt" else "Sending message..."):
                    response = service.send_text(number=destination_number, text=raw_text)
                if response.success:
                    st.toast(
                        "Mensagem enviada com sucesso."
                        if lang == "pt"
                        else "Message sent successfully.",
                        icon="📨",
                    )
                else:
                    st.toast(_friendly_send_error(response.error), icon="❌")
    finally:
        clear_page_action(PAGE_KEY)

st.divider()
st.subheader(
    "⏱️ "
    + (
        "Enviar lembretes vencidos no WhatsApp (sem duplicar no mesmo dia)"
        if lang == "pt"
        else "Send due WhatsApp reminders (dedup same-day)"
    )
)

st.button(
    "🚀 " + ("Enviar agora" if lang == "pt" else "Send now"),
    disabled=is_page_action_busy(PAGE_KEY),
    on_click=queue_page_action,
    args=(PAGE_KEY, "send_due_reminders"),
)

send_due_action = consume_page_action(PAGE_KEY, "send_due_reminders")
if send_due_action is not None:
    try:
        with st.spinner("Enviando lembretes..." if lang == "pt" else "Sending reminders..."):
            result = send_due_whatsapp_reminders(now=now_in_fortaleza_naive(), lang=lang)
        st.toast(
            (
                f"WhatsApps enviados: {result['sent_messages']} | "
                f"Marcados SENT: {result['marked_sent']} | "
                f"Sem número: {result['skipped_no_phone']} | "
                f"Falhas: {result['failed_messages']}"
            )
            if lang == "pt"
            else (
                f"WhatsApps sent: {result['sent_messages']} | "
                f"Marked SENT: {result['marked_sent']} | "
                f"No phone: {result['skipped_no_phone']} | "
                f"Failures: {result['failed_messages']}"
            ),
            icon="📲",
        )
        st.rerun()
    except Exception as exc:
        st.toast(f"Falha: {exc}" if lang == "pt" else f"Failed: {exc}", icon="❌")
    finally:
        clear_page_action(PAGE_KEY)
