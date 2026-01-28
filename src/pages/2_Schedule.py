import streamlit as st
from datetime import datetime, timedelta, date
import calendar
from collections import defaultdict
from io import BytesIO

import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from src.db import list_schedule_between, list_volunteers
from src.i18n import t, get_lang

st.title(t("sched.title"))
lang = get_lang()
st.markdown(
    """
    <style>
      .block-container {
        padding-top: 3rem;
        padding-bottom: 2rem;
        max-width: 98% !important;
      }

      /* Cards */
      .k-card {
        border: 1px solid rgba(120,120,120,0.22);
        border-radius: 12px;
        padding: 6px 8px;
        margin: 6px 0;
        background: rgba(255,255,255,0.02);
      }
      .k-time { font-weight: 800; font-size: 0.86rem; margin-bottom: 2px; }
      .k-role { font-size: 0.80rem; line-height: 1.25; display:flex; gap:.35rem; align-items:baseline; }

      .k-role b { font-weight: 800; }

      /* Role color dots */
      .k-dot { display:inline-block; width: .55rem; height: .55rem; border-radius: 999px; margin-top: .1rem; flex: 0 0 auto; }
      .k-dot-obs { background: rgba(88, 166, 255, 0.95); }    /* blue */
      .k-dot-fixed { background: rgba(255, 193, 7, 0.95); }   /* amber */
      .k-dot-mobile { background: rgba(0, 200, 140, 0.95); }  /* green */

      /* Calendar headers + cells */
      .k-gridHeader {
        text-align:center;
        font-weight:700;
        font-size: 0.85rem;
        opacity:.9;
        padding-bottom: 4px;
      }
      .k-dayCell {
        border: 1px solid rgba(120,120,120,0.15);
        border-radius: 14px;
        padding: 6px;
        min-height: 92px;
      }
      .k-day { font-weight: 800; font-size: 0.92rem; margin-bottom: 4px; }
      .k-dim { opacity: 0.45; }

      /* Agenda headers */
      .k-dayHeader {
        padding: .45rem .6rem;
        border-radius: 12px;
        border: 1px solid rgba(120,120,120,0.20);
        background: rgba(255,255,255,0.02);
        margin: 0.4rem 0 0.3rem 0;
      }

      /* Next service highlight */
      .k-nextDay {
        border: 2px solid rgba(0, 200, 140, 0.75) !important;
        background: rgba(0, 200, 140, 0.08) !important;
        box-shadow: 0 0 0 3px rgba(0, 200, 140, 0.12);
      }
      .k-nextLabel {
        display:inline-block;
        padding: 1px 6px;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 800;
        border: 1px solid rgba(0, 200, 140, 0.65);
        background: rgba(0, 200, 140, 0.12);
        margin-left: 4px;
      }

      /* Hover hint */
      .k-person {
        text-decoration: underline dotted rgba(180,180,180,0.45);
        text-underline-offset: 2px;
      }

      @media (max-width: 900px) {
        .k-dayCell { min-height: 120px; }
      }
    </style>
    """,
    unsafe_allow_html=True
)

def dow_label(d: date) -> str:
    if lang == "pt":
        return ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][d.weekday()]
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()]

def fmt_day_header(d: date) -> str:
    dt = datetime(d.year, d.month, d.day)
    if lang == "pt":
        return f"{dow_label(d)}, {dt.strftime('%d/%m/%Y')}"
    return f"{dow_label(d)}, {dt.strftime('%b %d, %Y')}"

def safe(s: str | None) -> str:
    return (s or "").strip()

def person_span(name: str, phone: str | None) -> str:
    n = safe(name) or "—"
    p = safe(phone)
    if n == "—":
        return "—"
    if not p:
        return f"<span class='k-person' title=''>{n}</span>"
    # Tooltip shows phone and "tap to copy" hint
    tip = p
    return f"<span class='k-person' title='{tip}'>{n}</span>"

def build_pdf_bytes(year: int, month: int, by_day: dict[date, list[tuple[str, dict]]], title: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    x = 1.5 * cm
    y = height - 1.6 * cm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, title)
    y -= 0.9 * cm

    c.setFont("Helvetica", 9)
    c.drawString(x, y, f"{'Gerado em' if lang == 'pt' else 'Generated at'}: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 0.9 * cm

    c.setFont("Helvetica", 10)

    days = [d for d in sorted(by_day.keys()) if d.month == month and by_day[d]]
    if not days:
        c.drawString(x, y, "Sem dados." if lang == "pt" else "No data.")
        c.showPage()
        c.save()
        return buf.getvalue()

    for d in days:
        # Page break
        if y < 3.0 * cm:
            c.showPage()
            y = height - 1.6 * cm
            c.setFont("Helvetica", 10)

        header = fmt_day_header(d)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, header)
        y -= 0.5 * cm

        c.setFont("Helvetica", 10)
        for dt_iso, svc in by_day[d]:
            dt = datetime.fromisoformat(dt_iso)
            obs = safe(svc.get("OBS")) or "—"
            fixed = safe(svc.get("FIXED")) or "—"
            mobile = safe(svc.get("MOBILE")) or "—"

            line1 = f"{dt.strftime('%H:%M')}  |  OBS: {obs}  |  FIXED: {fixed}  |  MOBILE: {mobile}"
            c.drawString(x, y, line1[:140])
            y -= 0.45 * cm

        y -= 0.25 * cm

    c.showPage()
    c.save()
    return buf.getvalue()

def build_sundays_png_bytes(year: int, month: int, by_day: dict[date, list[tuple[str, dict]]]) -> bytes:
    # Create a simple “WhatsApp-friendly” image: Sundays only, big readable lines
    sundays = [d for d in sorted(by_day.keys()) if d.month == month and d.weekday() == 6 and by_day[d]]
    lines: list[str] = []

    month_name = calendar.month_name[month] if lang != "pt" else [
        "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
    ][month - 1]

    title = f"{'Escala de Domingos' if lang=='pt' else 'Sunday Schedule'} — {month_name} {year}"
    lines.append(title)
    lines.append("")

    for d in sundays:
        lines.append(f"{fmt_day_header(d)}")
        for dt_iso, svc in by_day[d]:
            dt = datetime.fromisoformat(dt_iso)
            obs = safe(svc.get("OBS")) or "—"
            fixed = safe(svc.get("FIXED")) or "—"
            mobile = safe(svc.get("MOBILE")) or "—"
            lines.append(f"  {dt.strftime('%H:%M')}  OBS: {obs} | FIXED: {fixed} | MOBILE: {mobile}")
        lines.append("")

    if len(lines) <= 2:
        lines = [title, "", "— " + ("Sem cultos neste mês." if lang == "pt" else "No services this month.")]

    # Render with matplotlib
    fig = plt.figure(figsize=(10.5, max(6, 0.28 * len(lines))))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    # Title a bit bigger
    y = 0.98
    for i, text in enumerate(lines):
        fs = 16 if i == 0 else (12 if text and not text.startswith("  ") else 11)
        ax.text(0.02, y, text, fontsize=fs, va="top", family="DejaVu Sans")
        y -= 0.03 if i == 0 else 0.022

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

current_year = datetime.now().year
YEAR = st.selectbox(
    ("Ano" if lang == "pt" else "Year"),
    options=list(range(current_year - 1, current_year + 3)),
    index=1
)

month_names_pt = [
    "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
]
month_names_en = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]
month_names = month_names_pt if lang == "pt" else month_names_en

default_month = datetime.now().month if datetime.now().year == YEAR else 1
selected_month_name = st.selectbox(
    ("Mês" if lang == "pt" else "Month"),
    month_names,
    index=max(0, min(11, default_month - 1))
)
month = month_names.index(selected_month_name) + 1

name_filter = st.text_input(t("sched.filter")).strip().lower()

# View toggle (includes Sunday zoom mode)
view = st.segmented_control(
    ("Visualização" if lang == "pt" else "View"),
    options=[
        ("📅 " + ("Calendário" if lang == "pt" else "Calendar")),
        ("📋 " + ("Agenda" if lang == "pt" else "Agenda")),
        ("🔎 " + ("Domingos" if lang == "pt" else "Sundays")),
    ],
    default=("📋 " + ("Agenda" if lang == "pt" else "Agenda"))
)

start_dt = datetime(YEAR, month, 1)
last_day = calendar.monthrange(YEAR, month)[1]
end_dt = datetime(YEAR, month, last_day, 23, 59, 59)

rows = list_schedule_between(start_dt.isoformat(), end_dt.isoformat())

# Map volunteer -> phone for hover tooltips
vol_rows = list_volunteers(active_only=False)
name_to_phone: dict[str, str] = {}
for _vid, vname, vphone, *_rest in vol_rows:
    if vname:
        name_to_phone[str(vname).strip()] = (str(vphone).strip() if vphone else "")

services_map = defaultdict(lambda: {"OBS": "", "FIXED": "", "MOBILE": ""})
for _, dt_iso, _, role, name in rows:
    if role:
        services_map[dt_iso][role] = name or ""

if not services_map:
    st.info(t("sched.no_services"))
    st.stop()

def service_matches_filter(svc: dict) -> bool:
    if not name_filter:
        return True
    return any(name_filter in safe(svc.get(r)).lower() for r in ["OBS", "FIXED", "MOBILE"])

# Next service day (true “next service”, not “next day”)
now = datetime.now()
GRACE_MINUTES = 180
threshold = now - timedelta(minutes=GRACE_MINUTES)
service_dts = sorted({datetime.fromisoformat(dt_iso) for dt_iso in services_map.keys()})
next_service_dt = next((d for d in service_dts if d >= threshold), None)
next_service_day = next_service_dt.date() if next_service_dt else None

# Group by day
by_day = defaultdict(list)
for dt_iso, svc in services_map.items():
    dt = datetime.fromisoformat(dt_iso)
    by_day[dt.date()].append((dt_iso, svc))
for d in by_day:
    by_day[d].sort(key=lambda x: x[0])

st.markdown(
    f"#### {selected_month_name} {YEAR}",
)
c_export1, c_export2 = st.columns([1, 1])
with c_export1:
    pdf_bytes = build_pdf_bytes(
        YEAR,
        month,
        {d: [(dt_iso, svc) for (dt_iso, svc) in items if service_matches_filter(svc)] for d, items in by_day.items()},
        title=f"{'Escala do Ministério' if lang=='pt' else 'Ministry Schedule'} — {selected_month_name} {YEAR}",
    )
    st.download_button(
        label=("📄 Baixar PDF (WhatsApp)" if lang == "pt" else "📄 Download PDF (WhatsApp)"),
        data=pdf_bytes,
        file_name=f"schedule_{YEAR}_{month:02d}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
with c_export2:
    png_bytes = build_sundays_png_bytes(
        YEAR,
        month,
        {d: [(dt_iso, svc) for (dt_iso, svc) in items if service_matches_filter(svc)] for d, items in by_day.items()},
    )
    st.download_button(
        label=("🖼️ Baixar imagem (Domingos)" if lang == "pt" else "🖼️ Download image (Sundays)"),
        data=png_bytes,
        file_name=f"sundays_{YEAR}_{month:02d}.png",
        mime="image/png",
        use_container_width=True,
    )

st.divider()

if "Agenda" in view:
    shown_any = False
    for d in sorted(by_day.keys()):
        if d.month != month:
            continue

        day_items = [(dt_iso, svc) for (dt_iso, svc) in by_day[d] if service_matches_filter(svc)]
        if not day_items:
            continue

        shown_any = True
        is_next = (next_service_day == d)
        tag = f"<span class='k-nextLabel'>{'PRÓXIMO' if lang=='pt' else 'NEXT'}</span>" if is_next else ""
        header_class = "k-dayHeader k-nextDay" if is_next else "k-dayHeader"
        st.markdown(f"<div class='{header_class}'><b>{fmt_day_header(d)}</b> {tag}</div>", unsafe_allow_html=True)

        for dt_iso, svc in day_items:
            dt = datetime.fromisoformat(dt_iso)

            obs_name = safe(svc.get("OBS"))
            fixed_name = safe(svc.get("FIXED"))
            mobile_name = safe(svc.get("MOBILE"))

            obs_html = person_span(obs_name, name_to_phone.get(obs_name))
            fixed_html = person_span(fixed_name, name_to_phone.get(fixed_name))
            mobile_html = person_span(mobile_name, name_to_phone.get(mobile_name))

            st.markdown(
                f"""
                <div class="k-card">
                  <div class="k-time">⏰ {dt.strftime("%H:%M")}</div>

                  <div class="k-role">
                    <span class="k-dot k-dot-obs"></span>
                    <b>OBS:</b> {obs_html}
                  </div>

                  <div class="k-role">
                    <span class="k-dot k-dot-fixed"></span>
                    <b>FIXED:</b> {fixed_html}
                  </div>

                  <div class="k-role">
                    <span class="k-dot k-dot-mobile"></span>
                    <b>MOBILE:</b> {mobile_html}
                  </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    if not shown_any:
        st.info("Nada encontrado com esse filtro." if lang == "pt" else "Nothing matched this filter.")

elif "Domingos" in view or "Sundays" in view:
    sundays = [d for d in sorted(by_day.keys()) if d.month == month and d.weekday() == 6]
    if not sundays:
        st.info("Sem domingos neste mês." if lang == "pt" else "No Sundays this month.")
    else:
        for d in sundays:
            day_items = [(dt_iso, svc) for (dt_iso, svc) in by_day.get(d, []) if service_matches_filter(svc)]
            is_next = (next_service_day == d)
            tag = f"<span class='k-nextLabel'>{'PRÓXIMO' if lang=='pt' else 'NEXT'}</span>" if is_next else ""
            header_class = "k-dayHeader k-nextDay" if is_next else "k-dayHeader"
            st.markdown(f"<div class='{header_class}'><b>{fmt_day_header(d)}</b> {tag}</div>", unsafe_allow_html=True)

            if not day_items:
                st.caption("—")
                continue

            # Bigger, clearer per service block
            for dt_iso, svc in day_items:
                dt = datetime.fromisoformat(dt_iso)

                obs_name = safe(svc.get("OBS"))
                fixed_name = safe(svc.get("FIXED"))
                mobile_name = safe(svc.get("MOBILE"))

                obs_html = person_span(obs_name, name_to_phone.get(obs_name))
                fixed_html = person_span(fixed_name, name_to_phone.get(fixed_name))
                mobile_html = person_span(mobile_name, name_to_phone.get(mobile_name))

                st.markdown(
                    f"""
                    <div class="k-card" style="padding:10px 10px;">
                      <div class="k-time" style="font-size:1.05rem;">⏰ {dt.strftime("%H:%M")}</div>

                      <div class="k-role" style="font-size:0.95rem;">
                        <span class="k-dot k-dot-obs"></span>
                        <b>OBS:</b> {obs_html}
                      </div>

                      <div class="k-role" style="font-size:0.95rem;">
                        <span class="k-dot k-dot-fixed"></span>
                        <b>FIXED:</b> {fixed_html}
                      </div>

                      <div class="k-role" style="font-size:0.95rem;">
                        <span class="k-dot k-dot-mobile"></span>
                        <b>MOBILE:</b> {mobile_html}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

else:
    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdatescalendar(YEAR, month)

    dow_pt = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    dow_en = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    dow = dow_pt if lang == "pt" else dow_en

    header_cols = st.columns(7)
    for i, dname in enumerate(dow):
        header_cols[i].markdown(f"<div class='k-gridHeader'>{dname}</div>", unsafe_allow_html=True)

    any_visible = False

    for week in weeks:
        cols = st.columns(7, gap="small")
        for i, day in enumerate(week):
            with cols[i]:
                if day.month != month:
                    st.markdown(f"<div class='k-dim'>{day.day}</div>", unsafe_allow_html=True)
                    continue

                is_next = (next_service_day == day)
                cls = "k-dayCell k-nextDay" if is_next else "k-dayCell"
                tag = f"<span class='k-nextLabel'>{'PRÓXIMO' if lang=='pt' else 'NEXT'}</span>" if is_next else ""
                st.markdown(f"<div class='k-day'>{day.day} {tag}</div>", unsafe_allow_html=True)

                # services
                day_items = [(dt_iso, svc) for (dt_iso, svc) in by_day.get(day, []) if service_matches_filter(svc)]
                if not day_items:
                    st.caption("—")
                    st.markdown("</div>", unsafe_allow_html=True)
                    continue

                any_visible = True

                for dt_iso, svc in day_items:
                    dt = datetime.fromisoformat(dt_iso)

                    obs_name = safe(svc.get("OBS"))
                    fixed_name = safe(svc.get("FIXED"))
                    mobile_name = safe(svc.get("MOBILE"))

                    obs_html = person_span(obs_name, name_to_phone.get(obs_name))
                    fixed_html = person_span(fixed_name, name_to_phone.get(fixed_name))
                    mobile_html = person_span(mobile_name, name_to_phone.get(mobile_name))

                    st.markdown(
                        f"""
                        <div class="k-card" style="margin:6px 0 0 0;">
                          <div class="k-time">{dt.strftime("%H:%M")}</div>

                          <div class="k-role">
                            <span class="k-dot k-dot-obs"></span>
                            <b>OBS:</b> {obs_html}
                          </div>

                          <div class="k-role">
                            <span class="k-dot k-dot-fixed"></span>
                            <b>FIXED:</b> {fixed_html}
                          </div>

                          <div class="k-role">
                            <span class="k-dot k-dot-mobile"></span>
                            <b>MOBILE:</b> {mobile_html}
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.markdown("</div>", unsafe_allow_html=True)

    if name_filter and not any_visible:
        st.info("Nada encontrado com esse filtro." if lang == "pt" else "Nothing matched this filter.")

st.caption(
    ("Dica: passe o mouse no nome para ver o telefone. (No celular, o tooltip pode não aparecer.)"
     if lang == "pt"
     else "Tip: hover a name to see the phone. (On mobile, tooltips may not show.)")
)