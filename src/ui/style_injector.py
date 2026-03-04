from __future__ import annotations

from pathlib import Path
import streamlit as st


def inject_global_css(css_path: str | Path) -> None:
    path = Path(css_path)
    css = path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)