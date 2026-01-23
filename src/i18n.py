import streamlit as st

TRANSLATIONS = {
    "pt": {
        "app.title": "Escala CN Maraponga",
        "app.caption": "MVP: voluntários, geração de escala, edição, trocas e fila de lembretes.",
        "nav.admin_access": "Acesso de Admin",
        "common.admin_required": "Acesso de admin necessário.",
        "common.save": "Salvar",
        "common.refresh": "Atualize a página para ver as mudanças.",
        "lang.label": "Idioma",
        "lang.pt": "Português (BR)",
        "lang.en": "English",

        "vol.title": "👥 Voluntários",
        "vol.add_update": "Adicionar / Atualizar voluntário (pelo nome)",
        "vol.name": "Nome",
        "vol.phone": "Telefone (opcional, futuro WhatsApp)",
        "vol.active": "Ativo",
        "vol.thu": "Disponível às Quintas",
        "vol.sun": "Disponível aos Domingos",
        "vol.can_obs": "Faz OBS",
        "vol.can_fixed": "Faz Câmera Fixa",
        "vol.can_mobile": "Faz Câmera Móvel",
        "vol.quick_toggle": "Ativar/Desativar rápido",
        "vol.volunteer_id": "ID do voluntário",
        "vol.set_active_to": "Definir ativo como",

        "sched.title": "📅 Escala",
        "sched.start": "Data inicial",
        "sched.end": "Data final (exclusiva)",
        "sched.no_services": "Sem cultos nesse período. Gere o mês primeiro.",
        "sched.filter": "Filtrar por nome do voluntário (opcional)",
        "sched.filtered": "Filtrado",

        "gen.title": "⚙️ Gerar Escala",
        "gen.year": "Ano",
        "gen.month": "Mês",
        "gen.seed": "Seed (muda para embaralhar empates)",
        "gen.prefer_mobile": "Tentar preencher CÂMERA MÓVEL quando possível",
        "gen.generate_overwrite": "Gerar (substitui o mês inteiro)",
        "gen.done": "Escala gerada + fila de lembretes reconstruída para o mês.",

        "edit.title": "✏️ Editar Escala",
        "edit.select_service": "Selecione o culto",
        "edit.current": "Atual",
        "edit.set": "Definir escala",
        "edit.save_rebuild": "Salvar alterações + reconstruir lembretes do mês",
        "edit.saved": "Salvo. Lembretes reconstruídos.",

        "swap.title": "🔁 Trocas",
        "swap.request": "Solicitar troca (voluntário)",
        "swap.pick": "Selecione a escala",
        "swap.reason": "Motivo (opcional)",
        "swap.submit": "Enviar solicitação de troca",
        "swap.submitted": "Solicitação enviada.",
        "swap.admin_pending": "Admin: solicitações pendentes",
        "swap.none": "Não há solicitações pendentes.",
        "swap.resolve": "Resolver",
        "swap.reject": "REJEITAR",
        "swap.approve_manual": "APROVAR (ajuste manual na página Editar)",
        "swap.rejected": "Rejeitado.",
        "swap.approved": "Aprovado. Não esqueça de ajustar a escala na página Editar.",

        "rem.title": "⏰ Fila de Lembretes",
        "rem.filter": "Filtro",
        "rem.simulate": "Marcar como ENVIADO (simular)",
        "rem.admin_note": "MVP: simular envio marcando como ENVIADO. Depois: worker + WhatsApp.",

        "home.quick_actions": "Ações rápidas",
        "home.open_schedule": "Ver escala",
        "home.open_schedule_desc": "Veja a escala do mês em formato de calendário.",
        "home.open_schedule_btn": "📅 Abrir escala",
        "home.request_swap": "Solicitar troca",
        "home.request_swap_desc": "Peça uma troca informando solicitante, substituto e motivo. O admin aprova.",
        "home.request_swap_btn": "🔁 Solicitar troca",
        "home.how_it_works": "Como funciona",

        "nav.title": "Navegação",
        "nav.home": "Início",
        "nav.schedule": "Escala",
        "nav.edit": "Editar / Trocas",
        "nav.volunteers": "Voluntários",
        "nav.generate": "Gerar escala",
        "nav.reminders": "Lembretes",
    },
    "en": {
        "app.title": "Church Streaming Scheduler — MVP",
        "app.caption": "Local MVP: volunteers, schedule generation, editing, swaps, and reminders queue.",
        "nav.admin_access": "Admin access",
        "common.admin_required": "Admin required.",
        "common.save": "Save",
        "common.refresh": "Refresh the page to see changes.",
        "lang.label": "Language",
        "lang.pt": "Português (BR)",
        "lang.en": "English",

        "vol.title": "👥 Volunteers",
        "vol.add_update": "Add / Update volunteer (by name)",
        "vol.name": "Name",
        "vol.phone": "Phone (optional, future WhatsApp)",
        "vol.active": "Active",
        "vol.thu": "Available Thursdays",
        "vol.sun": "Available Sundays",
        "vol.can_obs": "Can OBS",
        "vol.can_fixed": "Can FIXED camera",
        "vol.can_mobile": "Can MOBILE camera",
        "vol.quick_toggle": "Quick activate/deactivate",
        "vol.volunteer_id": "Volunteer ID",
        "vol.set_active_to": "Set active to",

        "sched.title": "📅 Schedule",
        "sched.start": "Start date",
        "sched.end": "End date (exclusive)",
        "sched.no_services": "No services in this range yet. Generate the month first.",
        "sched.filter": "Filter by volunteer name contains (optional)",
        "sched.filtered": "Filtered",

        "gen.title": "⚙️ Generate Schedule",
        "gen.year": "Year",
        "gen.month": "Month",
        "gen.seed": "Seed (change to reshuffle ties)",
        "gen.prefer_mobile": "Try to fill MOBILE when possible",
        "gen.generate_overwrite": "Generate (overwrites month)",
        "gen.done": "Generated schedule + rebuilt reminder jobs for the month.",

        "edit.title": "✏️ Edit Schedule",
        "edit.select_service": "Select service",
        "edit.current": "Current",
        "edit.set": "Set assignments",
        "edit.save_rebuild": "Save changes + rebuild reminders for month",
        "edit.saved": "Saved. Reminders rebuilt.",

        "swap.title": "🔁 Swap Requests",
        "swap.request": "Request a swap (volunteer)",
        "swap.pick": "Select assignment",
        "swap.reason": "Reason (optional)",
        "swap.submit": "Submit swap request",
        "swap.submitted": "Swap request submitted.",
        "swap.admin_pending": "Admin: Pending requests",
        "swap.none": "No pending swap requests.",
        "swap.resolve": "Resolve",
        "swap.reject": "REJECT",
        "swap.approve_manual": "APPROVE (manual adjust in Edit page)",
        "swap.rejected": "Rejected.",
        "swap.approved": "Approved. Make sure you changed the assignment in Edit page.",

        "rem.title": "⏰ Reminders Queue",
        "rem.filter": "Filter",
        "rem.simulate": "Mark as SENT (simulate)",
        "rem.admin_note": "MVP: simulate sending by marking as SENT. Later: worker + WhatsApp provider.",

        "home.quick_actions": "Quick actions",
        "home.open_schedule": "Open schedule",
        "home.open_schedule_desc": "See the monthly calendar view of the schedule.",
        "home.open_schedule_btn": "📅 Open schedule",
        "home.request_swap": "Request swap",
        "home.request_swap_desc": "Request a change with requester, replacement and reason. Admin approves.",
        "home.request_swap_btn": "🔁 Request swap",
        "home.how_it_works": "How it works",

        "nav.title": "Navigation",
        "nav.home": "Home",
        "nav.schedule": "Schedule",
        "nav.edit": "Edit / Swaps",
        "nav.volunteers": "Volunteers",
        "nav.generate": "Generate schedule",
        "nav.reminders": "Reminders",
    },
}

def get_lang() -> str:
    return st.session_state.get("lang", "pt")

def t(key: str) -> str:
    lang = get_lang()
    return TRANSLATIONS.get(lang, {}).get(key, key)

def language_selector():
    # Create the widget once per run (no persistent guard)
    # Use a stable label so it doesn't "shift" when the language changes
    st.sidebar.markdown("### Language / Idioma")

    # Keep the selected value directly in session_state["lang"]
    st.sidebar.radio(
        label="",
        options=["pt", "en"],
        key="lang",  # <-- single source of truth
        format_func=lambda x: TRANSLATIONS["pt"]["lang.pt"] if x == "pt" else TRANSLATIONS["en"]["lang.en"],
    )