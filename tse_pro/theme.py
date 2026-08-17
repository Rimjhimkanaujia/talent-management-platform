"""Shared CSS loader + component helpers for Talent Management Platform — Pro edition."""
import streamlit as st
from pathlib import Path

_CSS_PATH = Path(__file__).parent / "styles.css"


def load_css():
    if _CSS_PATH.exists():
        st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)


def page_header(icon, title, subtitle=""):
    st.markdown(
        f"""<div class="ts-section">
              <div class="ts-section-title">{icon} {title}</div>
              <div class="ts-section-subtitle">{subtitle}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def hero(title, subtitle=""):
    st.markdown(
        f"""<div class="ts-hero">
              <div class="ts-hero-title">{title}</div>
              <div class="ts-hero-subtitle">{subtitle}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def metric(label, value):
    st.markdown(
        f"""<div class="ts-metric">
              <div class="ts-metric-value">{value}</div>
              <div class="ts-metric-label">{label}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def badge(text, kind="mid"):
    return f'<span class="ts-badge ts-badge-{kind}">{text}</span>'


ROLE_BADGE = {"admin": "high", "trainee": "mid"}


def sidebar_identity():
    """Renders the 'Talent Management Platform — user — role badge' block used in the sidebar."""
    import auth
    u = auth.current_user()
    if not u:
        return
    st.markdown(
        f"""<div style="padding:0.5rem 0 0.75rem;">
              <div style="font-weight:700;font-size:1rem;">🚀 Talent <span style="color:#0A66C2;">Management Platform</span></div>
              <div style="color:var(--ls-text-secondary,#666);font-size:0.85rem;margin-top:2px;">
                {u['name']} · {badge(u['role'].upper(), ROLE_BADGE.get(u['role'], 'mid'))}
              </div>
            </div>""",
        unsafe_allow_html=True,
    )


def app_footer():
    import config
    st.markdown(
        f"""<div style="margin-top:3rem;padding-top:1rem;border-top:1px solid #E0DFDC;
                    color:#8a8a8a;font-size:0.8rem;text-align:center;">
              {config.APP_NAME} {config.APP_EDITION} · v{config.APP_VERSION} ·
              AI features powered by Claude
            </div>""",
        unsafe_allow_html=True,
    )
