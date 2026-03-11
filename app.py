"""
Qualtrics Dashboard Translator — Streamlit App
================================================
Polished internal government analytics tool interface.
Minimalist, centered, dark-mode compatible.
Modular render functions. All backend logic preserved.
"""

from __future__ import annotations

import io
import os
from typing import Optional

import pandas as pd
import streamlit as st

from processor.classifier import CellType
from processor.detector import FileType, detect_file_type, find_locale_columns
from processor.file_loader import load_file
from processor.pipeline import PipelineConfig, PipelineResult, run_pipeline
from processor.reference_memory import TranslationMemory, build_memory_from_reference
from processor.rules import Provenance


# ═══════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Qualtrics Dashboard Translator",
    page_icon="🍁",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Simple red maple leaf silhouette — flat, minimal, centered
MAPLE_LEAF_SVG = (
    '<svg width="44" height="44" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">'
    '<path fill="#D52B1E" d="M256 32l32 96 48-32-12 64 72-12-44 52 '
    '80 12-76 40 48 64-88-24 12 76-72-64-72 64 12-76-88 24 '
    '48-64-76-40 80-12-44-52 72 12-12-64 48 32z"/>'
    '</svg>'
)


# ═══════════════════════════════════════════════════════════════════════════
#  CSS DESIGN SYSTEM
#  ─ Light mode + Dark mode via CSS custom properties
#  ─ Canada government inspired palette
#  ─ All spacing, radii, typography per spec
# ═══════════════════════════════════════════════════════════════════════════

def inject_css():
    """Inject the complete CSS design system."""
    st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════════
   FONT IMPORT
   ═══════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ═══════════════════════════════════════════════════════════════
   CSS CUSTOM PROPERTIES — LIGHT MODE (default)
   Colors: Canada government palette
   ═══════════════════════════════════════════════════════════════ */
:root {
    /* Backgrounds */
    --bg:           #FFFFFF;
    --bg-card:      #F7F7F7;
    --bg-elevated:  #F4F4F4;
    --bg-hover:     #EBEBEB;
    /* Text */
    --text:         #111111;
    --text-sub:     #444444;
    --text-dim:     #888888;
    /* Borders */
    --border:       #E3E3E3;
    --border-hover: #1C3D5A;
    /* Accent */
    --red:          #D52B1E;
    --red-hover:    #B8231A;
    --red-glow:     rgba(213, 43, 30, 0.18);
    --red-soft:     rgba(213, 43, 30, 0.06);
    --blue:         #1C3D5A;
    --blue-light:   #2B5C85;
    --blue-soft:    rgba(28, 61, 90, 0.08);
    /* Success / Warning */
    --green:        #1A7742;
    --green-soft:   rgba(26, 119, 66, 0.10);
    --amber:        #C27803;
    --amber-soft:   rgba(194, 120, 3, 0.10);
    /* Shadows */
    --shadow:       0 1px 3px rgba(0,0,0,0.05);
    --shadow-md:    0 4px 16px rgba(0,0,0,0.06);
    --shadow-up:    0 6px 24px rgba(0,0,0,0.09);
    /* Radii */
    --r:            14px;
    --r-card:       16px;
    --r-btn:        24px;
    --r-full:       999px;
    /* Transitions */
    --ease:         150ms ease;
}

/* ═══════════════════════════════════════════════════════════════
   CSS CUSTOM PROPERTIES — DARK MODE
   Triggered by OS preference or Streamlit dark theme
   ═══════════════════════════════════════════════════════════════ */
@media (prefers-color-scheme: dark) {
    :root {
        --bg:           #0F172A;
        --bg-card:      #1E293B;
        --bg-elevated:  #1E293B;
        --bg-hover:     #334155;
        --text:         #F3F4F6;
        --text-sub:     #CBD5E1;
        --text-dim:     #94A3B8;
        --border:       #334155;
        --border-hover: #60A5FA;
        --red:          #EF4444;
        --red-hover:    #DC2626;
        --red-glow:     rgba(239, 68, 68, 0.25);
        --red-soft:     rgba(239, 68, 68, 0.10);
        --blue:         #60A5FA;
        --blue-light:   #93C5FD;
        --blue-soft:    rgba(96, 165, 250, 0.12);
        --green:        #34D399;
        --green-soft:   rgba(52, 211, 153, 0.12);
        --amber:        #FBBF24;
        --amber-soft:   rgba(251, 191, 36, 0.12);
        --shadow:       0 1px 3px rgba(0,0,0,0.30);
        --shadow-md:    0 4px 16px rgba(0,0,0,0.35);
        --shadow-up:    0 6px 24px rgba(0,0,0,0.40);
    }
}

/* Streamlit's internal dark mode detection */
[data-testid="stAppViewContainer"][style*="background-color: rgb(14"],
[data-testid="stAppViewContainer"][style*="background-color: rgb(0"],
.stApp[data-theme="dark"],
[data-theme="dark"] {
    --bg:           #0F172A;
    --bg-card:      #1E293B;
    --bg-elevated:  #1E293B;
    --bg-hover:     #334155;
    --text:         #F3F4F6;
    --text-sub:     #CBD5E1;
    --text-dim:     #94A3B8;
    --border:       #334155;
    --border-hover: #60A5FA;
    --red:          #EF4444;
    --red-hover:    #DC2626;
    --red-glow:     rgba(239, 68, 68, 0.25);
    --red-soft:     rgba(239, 68, 68, 0.10);
    --blue:         #60A5FA;
    --blue-light:   #93C5FD;
    --blue-soft:    rgba(96, 165, 250, 0.12);
    --green:        #34D399;
    --green-soft:   rgba(52, 211, 153, 0.12);
    --amber:        #FBBF24;
    --amber-soft:   rgba(251, 191, 36, 0.12);
    --shadow:       0 1px 3px rgba(0,0,0,0.30);
    --shadow-md:    0 4px 16px rgba(0,0,0,0.35);
    --shadow-up:    0 6px 24px rgba(0,0,0,0.40);
}

/* ═══════════════════════════════════════════════════════════════
   GLOBAL RESET & TYPOGRAPHY
   Font: Inter, system-ui, -apple-system, Segoe UI, Roboto
   Body text 15px, line-height 1.5
   ═══════════════════════════════════════════════════════════════ */
html, body, .stApp, .stApp *,
.stMarkdown, .stMarkdown *,
[data-testid="stAppViewContainer"] * {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif !important;
}
.stApp {
    color: var(--text);
    font-size: 15px;
    line-height: 1.5;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}

/* ═══════════════════════════════════════════════════════════════
   CENTERED CONTENT CONTAINER
   max-width 1100px, auto margins
   ═══════════════════════════════════════════════════════════════ */
[data-testid="stMainBlockContainer"],
.block-container {
    max-width: 1100px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* ═══════════════════════════════════════════════════════════════
   HEADER — Logo + Title + Subtitle
   ═══════════════════════════════════════════════════════════════ */
.hdr {
    text-align: center;
    padding: 52px 0 0 0;
}
.hdr svg {
    display: inline-block;
    margin-bottom: 14px;
}
.hdr-title {
    font-size: 40px;
    font-weight: 700;
    color: var(--text);
    margin: 0;
    letter-spacing: -0.03em;
    line-height: 1.1;
    text-align: center;
}
.hdr-sub {
    font-size: 18px;
    font-weight: 400;
    color: var(--text-sub);
    margin: 10px 0 32px 0;
    text-align: center;
}
.hdr-line {
    border: none;
    border-top: 1px solid var(--border);
    margin: 0 auto;
    max-width: 800px;
}

/* ═══════════════════════════════════════════════════════════════
   SECTION SPACING & TITLES
   56px vertical spacing between major sections
   Section title: 24px / 600
   ═══════════════════════════════════════════════════════════════ */
.section {
    margin-top: 56px;
    text-align: center;
}
.section-title {
    font-size: 24px;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 8px 0;
    text-align: center;
}
.section-desc {
    font-size: 15px;
    font-weight: 400;
    color: var(--text-dim);
    margin: 0 auto 28px auto;
    max-width: 600px;
    line-height: 1.5;
    text-align: center;
}

/* ═══════════════════════════════════════════════════════════════
   UPLOAD CARDS — Drop zone style
   min-height 160px, dashed border, 16px radius
   Hover: blue border + slight shadow lift (150ms)
   "Browse Files" button hidden; whole card is drop zone
   ═══════════════════════════════════════════════════════════════ */
.upload-card {
    background: var(--bg-card);
    border: 2px dashed var(--border);
    border-radius: var(--r-card);
    min-height: 160px;
    padding: 32px 20px 16px 20px;
    text-align: center;
    transition: border-color var(--ease), box-shadow var(--ease);
    cursor: default;
}
.upload-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
}
.upload-card .uc-icon {
    font-size: 28px;
    margin-bottom: 10px;
    color: var(--text-dim);
    display: block;
}
.upload-card .uc-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 6px 0;
}
.upload-card .uc-drag {
    font-size: 15px;
    color: var(--text-dim);
    margin: 0 0 4px 0;
}
.upload-card .uc-detail {
    font-size: 13px;
    color: var(--text-dim);
    margin: 0;
    line-height: 1.4;
}

/* Hide Streamlit uploader chrome inside upload cards */
.upload-zone [data-testid="stFileUploader"] {
    margin-top: 10px;
}
.upload-zone [data-testid="stFileUploader"] label {
    display: none !important;
}
.upload-zone [data-testid="stFileUploader"] section {
    border: none !important;
    background: transparent !important;
    padding: 6px 0 0 0 !important;
}
.upload-zone [data-testid="stFileUploader"] section > div {
    display: flex;
    justify-content: center;
}
/* Style the browse button as a subtle centered pill */
.upload-zone [data-testid="stFileUploader"] button {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-dim) !important;
    border-radius: var(--r-full) !important;
    padding: 8px 24px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    transition: all var(--ease) !important;
    cursor: pointer !important;
}
.upload-zone [data-testid="stFileUploader"] button:hover {
    background: var(--bg-hover) !important;
    color: var(--text) !important;
}
.upload-zone [data-testid="stFileUploader"] small {
    text-align: center !important;
    display: block !important;
    color: var(--text-dim) !important;
    font-size: 12px !important;
}

/* ═══════════════════════════════════════════════════════════════
   STATUS PILLS — centered row
   ═══════════════════════════════════════════════════════════════ */
.status-row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    margin: 24px 0 0 0;
}
.pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 20px;
    border-radius: var(--r-full);
    font-size: 14px;
    font-weight: 600;
}
.pill-green { background: var(--green-soft); color: var(--green); }
.pill-amber { background: var(--amber-soft); color: var(--amber); }

/* Memory counter */
.mem-box {
    text-align: center;
    margin: 20px auto 0 auto;
    padding: 20px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    max-width: 220px;
}
.mem-box .val {
    font-size: 36px;
    font-weight: 700;
    color: var(--red);
    line-height: 1;
}
.mem-box .lbl {
    font-size: 13px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    margin-top: 4px;
}

/* ═══════════════════════════════════════════════════════════════
   FILE TYPE SELECTOR BUTTONS — Step 2
   Large centered buttons with 24px radius
   Hover: scale 1.03, color shift, 150ms
   ═══════════════════════════════════════════════════════════════ */
.file-btn-row {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin: 0 auto 8px auto;
    max-width: 520px;
}
.file-btn {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 16px 36px;
    border-radius: 24px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 150ms ease;
    border: 2px solid var(--border);
    background: var(--bg-card);
    color: var(--text);
    text-align: center;
    min-height: 64px;
    text-decoration: none;
}
.file-btn:hover {
    border-color: var(--border-hover);
    transform: scale(1.03);
    box-shadow: var(--shadow-md);
}
.file-btn.active {
    border-color: var(--red);
    background: var(--red-soft);
    color: var(--red);
    box-shadow: 0 0 0 3px var(--red-glow);
}
.file-btn .fb-icon {
    font-size: 22px;
    margin-bottom: 4px;
}
.file-btn .fb-label {
    font-size: 16px;
    font-weight: 600;
}

/* ═══════════════════════════════════════════════════════════════
   TRANSLATE PANEL — inside expanded file type
   ═══════════════════════════════════════════════════════════════ */
.translate-panel {
    max-width: 640px;
    margin: 0 auto;
    text-align: center;
}
.translate-panel [data-testid="stFileUploader"] section {
    border-radius: var(--r-card) !important;
    border: 2px dashed var(--border) !important;
    padding: 28px 20px !important;
    background: var(--bg-card) !important;
    transition: border-color var(--ease) !important;
}
.translate-panel [data-testid="stFileUploader"] section:hover {
    border-color: var(--border-hover) !important;
}
.translate-panel [data-testid="stFileUploader"] button {
    border-radius: var(--r-full) !important;
    padding: 8px 24px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
}
.panel-hint {
    font-size: 15px;
    color: var(--text-dim);
    margin: 8px auto 20px auto;
    text-align: center;
    line-height: 1.5;
    max-width: 540px;
}
.panel-hint code {
    background: var(--blue-soft);
    color: var(--blue);
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 14px;
}
.panel-hint strong {
    color: var(--text);
}

/* ═══════════════════════════════════════════════════════════════
   STATS ROW — 3 boxes centered
   ═══════════════════════════════════════════════════════════════ */
.stats-row {
    display: flex;
    justify-content: center;
    gap: 14px;
    margin: 24px auto;
    max-width: 480px;
}
.stat-card {
    flex: 1;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 18px 14px;
    text-align: center;
}
.stat-card .val {
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
    line-height: 1;
}
.stat-card .lbl {
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
    margin-top: 4px;
}

/* ═══════════════════════════════════════════════════════════════
   ALL BUTTONS — big, rounded, centered text
   16px semibold, 16px vertical / 34px horizontal padding
   ═══════════════════════════════════════════════════════════════ */
.stButton > button {
    border-radius: var(--r-btn) !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 16px 34px !important;
    min-height: 58px !important;
    transition: all 150ms ease !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    margin: 0 auto !important;
}
/* Primary (Translate) — red, prominent, glow */
.stButton > button[kind="primary"] {
    background: var(--red) !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 20px var(--red-glow) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--red-hover) !important;
    box-shadow: 0 6px 28px var(--red-glow) !important;
    transform: scale(1.03) !important;
}
.stButton > button[kind="primary"]:active {
    transform: scale(0.98) !important;
}
/* Secondary */
.stButton > button[kind="secondary"] {
    background: var(--bg-card) !important;
    border: 2px solid var(--border) !important;
    color: var(--text) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--border-hover) !important;
    background: var(--bg-hover) !important;
    transform: scale(1.03) !important;
}

/* ═══════════════════════════════════════════════════════════════
   DOWNLOAD BUTTONS — same style as primary
   ═══════════════════════════════════════════════════════════════ */
.stDownloadButton > button {
    border-radius: var(--r-btn) !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 16px 34px !important;
    min-height: 58px !important;
    background: var(--red) !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 20px var(--red-glow) !important;
    transition: all 150ms ease !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    margin: 0 auto !important;
}
.stDownloadButton > button:hover {
    background: var(--red-hover) !important;
    box-shadow: 0 6px 28px var(--red-glow) !important;
    transform: scale(1.03) !important;
}

/* ═══════════════════════════════════════════════════════════════
   PROVENANCE METRICS — 4 boxes, centered
   ═══════════════════════════════════════════════════════════════ */
.prov-row {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin: 24px auto;
    max-width: 560px;
    flex-wrap: wrap;
}
.prov-card {
    flex: 1;
    min-width: 110px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 16px 12px;
    text-align: center;
}
.prov-card .val {
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
}
.prov-card .lbl {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
    font-weight: 500;
    margin-top: 3px;
}

/* ═══════════════════════════════════════════════════════════════
   DONE BANNER — checkmark + download area
   Curved arrow animation
   ═══════════════════════════════════════════════════════════════ */
.done-area {
    text-align: center;
    margin: 32px auto;
    max-width: 480px;
}
.done-arrow {
    font-size: 36px;
    color: var(--red);
    animation: arrow-bounce 1.2s ease-in-out infinite;
    margin-bottom: 12px;
}
@keyframes arrow-bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}
.done-area h3 {
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
    margin: 0 0 4px 0;
}
.done-area p {
    font-size: 15px;
    color: var(--text-dim);
    margin: 0 0 20px 0;
}

/* ═══════════════════════════════════════════════════════════════
   PROGRESS BAR
   ═══════════════════════════════════════════════════════════════ */
.stProgress > div > div > div > div {
    background: var(--red) !important;
    border-radius: var(--r-full) !important;
}

/* ═══════════════════════════════════════════════════════════════
   ALERTS — rounded
   ═══════════════════════════════════════════════════════════════ */
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: var(--r) !important;
    font-size: 15px !important;
    text-align: center !important;
}

/* ═══════════════════════════════════════════════════════════════
   EXPANDERS
   ═══════════════════════════════════════════════════════════════ */
details {
    border-radius: var(--r) !important;
}
.streamlit-expanderHeader {
    font-size: 15px !important;
    font-weight: 600 !important;
}

/* ═══════════════════════════════════════════════════════════════
   DIVIDERS
   ═══════════════════════════════════════════════════════════════ */
.sep {
    border: none;
    border-top: 1px solid var(--border);
    margin: 56px auto 0 auto;
    max-width: 800px;
}

/* ═══════════════════════════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: var(--bg-card) !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stTextInput label {
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* ═══════════════════════════════════════════════════════════════
   FOOTER
   ═══════════════════════════════════════════════════════════════ */
.footer {
    text-align: center;
    color: var(--text-dim);
    font-size: 13px;
    padding: 56px 0 24px 0;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
#  RENDER FUNCTIONS — Modular UI sections
# ═══════════════════════════════════════════════════════════════════════════

def render_header():
    """Render the top header: maple leaf icon, title, subtitle, divider."""
    st.markdown(f"""
    <div class="hdr">
        {MAPLE_LEAF_SVG}
        <h1 class="hdr-title">Qualtrics Dashboard Translator</h1>
        <p class="hdr-sub">Translate Qualtrics Data and Label files between English and French (Canada)</p>
        <hr class="hdr-line">
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render sidebar with advanced settings (encoding, engine, API key)."""
    with st.sidebar:
        st.markdown("### Settings")

        encoding_choice = st.selectbox(
            "Export Encoding",
            options=["UTF-8 with BOM (recommended)", "UTF-8"],
            index=0,
        )
        use_bom = "BOM" in encoding_choice

        st.divider()

        provider_choice = st.selectbox(
            "Translation Engine",
            options=[
                "Argos Translate — Offline (Recommended)",
                "Anthropic API (requires key)",
                "Mock (for testing)",
            ],
            index=0,
        )
        if "Argos" in provider_choice:
            provider = "argos"
        elif "Anthropic" in provider_choice:
            provider = "anthropic"
        elif "Mock" in provider_choice:
            provider = "mock"
        else:
            provider = "auto"

        api_key = ""
        if provider == "anthropic":
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                value=os.environ.get("ANTHROPIC_API_KEY", ""),
            )

        st.divider()
        st.caption("Token protection and HTML preservation are always enabled.")

    return use_bom, provider, api_key


def render_reference_upload():
    """
    STEP 1 — Upload Reference Files.
    Two centered upload cards with drag-and-drop zones.
    Builds shared TranslationMemory in session state.
    Returns the memory object.
    """
    st.markdown("""
    <div class="section">
        <h2 class="section-title">Upload Your Reference Files</h2>
        <p class="section-desc">
            Reference files allow the system to reuse existing translations
            before generating new ones.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Two upload cards side by side
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="upload-card">
            <span class="uc-icon">&#128196;</span>
            <div class="uc-title">Reference Label Files</div>
            <div class="uc-drag">Drag and drop file here</div>
            <div class="uc-detail">Previously translated data-translations CSV or XLSX</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="upload-zone">', unsafe_allow_html=True)
        ref_labels_file = st.file_uploader(
            "ref_labels", type=["csv", "xlsx"], key="ref_labels",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="upload-card">
            <span class="uc-icon">&#128202;</span>
            <div class="uc-title">Reference Data Files</div>
            <div class="uc-drag">Drag and drop file here</div>
            <div class="uc-detail">Previously translated dashboard-translations CSV or XLSX</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div class="upload-zone">', unsafe_allow_html=True)
        ref_data_file = st.file_uploader(
            "ref_data", type=["csv", "xlsx"], key="ref_data",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Build translation memory ────────────────────────────────────
    if "memory" not in st.session_state:
        st.session_state["memory"] = TranslationMemory()

    memory: TranslationMemory = st.session_state["memory"]

    if ref_labels_file is not None and "ref_labels_loaded" not in st.session_state:
        try:
            ref_bytes = ref_labels_file.read()
            ref_labels_file.seek(0)
            ref_df = load_file(io.BytesIO(ref_bytes), file_name=ref_labels_file.name)
            build_memory_from_reference(ref_df, memory, "EN", "FR-CA")
            build_memory_from_reference(ref_df, memory, "EN", "FR")
            st.session_state["ref_labels_loaded"] = True
            st.session_state["memory"] = memory
        except Exception as e:
            st.error(f"Error loading reference labels file: {e}")

    if ref_data_file is not None and "ref_data_loaded" not in st.session_state:
        try:
            ref_bytes = ref_data_file.read()
            ref_data_file.seek(0)
            ref_df = load_file(io.BytesIO(ref_bytes), file_name=ref_data_file.name)
            build_memory_from_reference(ref_df, memory, "EN", "FR-CA")
            build_memory_from_reference(ref_df, memory, "EN", "FR")
            st.session_state["ref_data_loaded"] = True
            st.session_state["memory"] = memory
        except Exception as e:
            st.error(f"Error loading reference data file: {e}")

    # ── Status pills + memory counter ───────────────────────────────
    labels_ok = st.session_state.get("ref_labels_loaded", False)
    data_ok = st.session_state.get("ref_data_loaded", False)
    total_entries = memory.data_file_entries + memory.label_file_entries

    lbl_pill = (
        '<span class="pill pill-green">&#10003; Labels reference loaded</span>'
        if labels_ok else
        '<span class="pill pill-amber">&#9675; No labels reference</span>'
    )
    dat_pill = (
        '<span class="pill pill-green">&#10003; Data reference loaded</span>'
        if data_ok else
        '<span class="pill pill-amber">&#9675; No data reference</span>'
    )

    st.markdown(f"""
    <div class="status-row">{lbl_pill}{dat_pill}</div>
    <div class="mem-box">
        <div class="val">{total_entries:,}</div>
        <div class="lbl">Memory Entries</div>
    </div>
    """, unsafe_allow_html=True)

    return memory


def render_file_selection(use_bom: bool, provider: str, api_key: str):
    """
    STEP 2 — Select file type + STEP 3 — Run Translation.
    Two large buttons (Label File / Data File).
    Only one panel open at a time via session state.
    Each panel contains upload + translate + results.
    """
    st.markdown('<hr class="sep">', unsafe_allow_html=True)
    st.markdown("""
    <div class="section">
        <h2 class="section-title">Select the File You Want to Translate</h2>
        <p class="section-desc">
            Choose the file type below. The translated output fills
            both FR and FR-CA columns automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── File type selector buttons ──────────────────────────────────
    if "active_panel" not in st.session_state:
        st.session_state["active_panel"] = None

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button(
            "Label File",
            use_container_width=True,
            key="btn_label",
            type="primary" if st.session_state["active_panel"] == "label" else "secondary",
        ):
            st.session_state["active_panel"] = (
                None if st.session_state["active_panel"] == "label" else "label"
            )
            st.rerun()
    with btn_col2:
        if st.button(
            "Data File",
            use_container_width=True,
            key="btn_data",
            type="primary" if st.session_state["active_panel"] == "data" else "secondary",
        ):
            st.session_state["active_panel"] = (
                None if st.session_state["active_panel"] == "data" else "data"
            )
            st.rerun()

    # ── Expanded panel ──────────────────────────────────────────────
    active = st.session_state["active_panel"]

    if active == "label":
        _render_translate_panel(
            file_type=FileType.DATA_FILE,
            source_col_override="default value",
            tab_key="labels",
            hint_html=(
                'Source from <code>default value</code> column &rarr; '
                'translated into <strong>FR</strong> + <strong>FR-CA</strong>'
            ),
            use_bom=use_bom,
            provider=provider,
            api_key=api_key,
        )

    elif active == "data":
        _render_translate_panel(
            file_type=FileType.LABEL_FILE,
            source_col_override=None,
            tab_key="data",
            hint_html=(
                'Source from <code>EN</code> column &rarr; '
                'translated into <strong>FR</strong> + <strong>FR-CA</strong>'
            ),
            use_bom=use_bom,
            provider=provider,
            api_key=api_key,
        )


def _render_translate_panel(
    file_type: FileType,
    source_col_override: Optional[str],
    tab_key: str,
    hint_html: str,
    use_bom: bool,
    provider: str,
    api_key: str,
):
    """Render the upload + translate + results panel for one file type."""

    st.markdown('<hr class="sep">', unsafe_allow_html=True)

    st.markdown(f'<p class="panel-hint">{hint_html}</p>', unsafe_allow_html=True)

    st.markdown('<div class="translate-panel">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        f"Upload {tab_key} file",
        type=["csv", "xlsx"],
        key=f"{tab_key}_main",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file is None:
        return

    # ── File stats ──────────────────────────────────────────────────
    try:
        preview_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        preview_df = load_file(io.BytesIO(preview_bytes), file_name=uploaded_file.name)

        all_cols = list(preview_df.columns)
        target_cols = [c for c in all_cols if c.strip().upper() in ("FR", "FR-CA")]

        src_display = source_col_override or "EN"
        st.markdown(
            f'<div class="stats-row">'
            f'<div class="stat-card"><div class="val">{len(preview_df):,}</div>'
            f'<div class="lbl">Rows</div></div>'
            f'<div class="stat-card"><div class="val">{len(all_cols)}</div>'
            f'<div class="lbl">Columns</div></div>'
            f'<div class="stat-card"><div class="val">{src_display}</div>'
            f'<div class="lbl">Source</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Preview first 8 rows"):
            st.dataframe(preview_df.head(8), use_container_width=True)

    except Exception as e:
        st.error(f"Error loading file: {e}")
        return

    # ── STEP 3: Translate button ────────────────────────────────────
    render_translation_controls(
        uploaded_file, file_type, source_col_override, target_cols,
        tab_key, use_bom, provider, api_key,
    )


def render_translation_controls(
    uploaded_file, file_type, source_col_override, target_cols,
    tab_key, use_bom, provider, api_key,
):
    """STEP 3 — Run Translation. Big centered Translate button + processing UI."""

    st.markdown("""
    <div class="section" style="margin-top: 32px;">
        <h2 class="section-title">Run Translation</h2>
    </div>
    """, unsafe_allow_html=True)

    if st.button(
        "Translate File",
        type="primary",
        use_container_width=True,
        key=f"translate_{tab_key}",
    ):
        config = PipelineConfig(
            file_type_override=file_type,
            source_lang="EN",
            target_lang="FR-CA",
            target_columns=target_cols if target_cols else ["FR-CA"],
            source_column_override=source_col_override,
            use_bom=use_bom,
            provider=provider,
            api_key=api_key if api_key else None,
        )

        # ── Processing UI ───────────────────────────────────────────
        render_processing_ui(uploaded_file, config, tab_key)

    # ── Results ─────────────────────────────────────────────────────
    result_key = f"result_{tab_key}"
    if result_key in st.session_state:
        result: PipelineResult = st.session_state[result_key]

        # Validation
        if result.validation.passed:
            st.success("Validation passed — file integrity preserved")
        else:
            st.error("Validation failed")
            for issue in result.validation.issues:
                st.warning(issue)

        # Provenance metrics
        prov_counts: dict[str, int] = {}
        for t in result.translations:
            prov_counts[t.provenance.value] = prov_counts.get(t.provenance.value, 0) + 1

        ref_count = (
            prov_counts.get("reference_exact_match", 0)
            + prov_counts.get("reference_normalized_match", 0)
        )
        cache_count = prov_counts.get("session_cache", 0)
        fresh_count = prov_counts.get("fresh_translation", 0)
        skip_count = sum(v for k, v in prov_counts.items() if "skipped" in k)

        st.markdown(
            f'<div class="prov-row">'
            f'<div class="prov-card"><div class="val">{ref_count}</div>'
            f'<div class="lbl">Reference</div></div>'
            f'<div class="prov-card"><div class="val">{cache_count}</div>'
            f'<div class="lbl">Cache</div></div>'
            f'<div class="prov-card"><div class="val">{fresh_count}</div>'
            f'<div class="lbl">Fresh</div></div>'
            f'<div class="prov-card"><div class="val">{skip_count}</div>'
            f'<div class="lbl">Skipped</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Translation Preview"):
            interesting = [
                t for t in result.translations
                if t.provenance not in (
                    Provenance.SKIPPED_EMPTY, Provenance.SKIPPED_NUMERIC,
                    Provenance.SKIPPED_INTERNAL, Provenance.SKIPPED_PROTECTED,
                )
            ][:40]
            if interesting:
                preview_rows = [
                    {
                        "Row": t.row_index,
                        "Source": t.provenance.value.replace("_", " ").title(),
                        "Original": t.original[:60],
                        "Translated": t.translated[:60],
                    }
                    for t in interesting
                ]
                st.dataframe(
                    pd.DataFrame(preview_rows),
                    use_container_width=True,
                    hide_index=True,
                )

        with st.expander("Diagnostics & Notes"):
            for k, v in sorted(result.diagnostics.items()):
                st.text(f"{k}: {v}")
            st.divider()
            st.dataframe(result.notes_df, use_container_width=True, hide_index=True)

        # ── STEP 4: Download Result ─────────────────────────────────
        render_download_section(result, tab_key)


def render_processing_ui(uploaded_file, config: PipelineConfig, tab_key: str):
    """Show spinner, progress bar, and step status during translation."""
    progress_bar = st.progress(0, text="Loading files...")

    def update_progress(step: str, pct: float) -> None:
        progress_bar.progress(min(pct, 1.0), text=step)

    try:
        uploaded_file.seek(0)
        result = run_pipeline(
            main_file=io.BytesIO(uploaded_file.read()),
            main_filename=uploaded_file.name,
            config=config,
            memory=st.session_state.get("memory"),
            progress_callback=update_progress,
        )
        st.session_state[f"result_{tab_key}"] = result
        progress_bar.empty()
    except Exception as e:
        st.error(f"Translation error: {e}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())


def render_download_section(result: PipelineResult, tab_key: str):
    """STEP 4 — Download result with curved arrow animation."""
    st.markdown("""
    <div class="done-area">
        <div class="done-arrow">&#8595;</div>
        <h3>Download Translated File</h3>
        <p>Your file is ready for Qualtrics import</p>
    </div>
    """, unsafe_allow_html=True)

    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            label="Download Translated CSV",
            data=result.translated_csv_bytes,
            file_name=result.translated_filename,
            mime="text/csv",
            use_container_width=True,
            key=f"dl_csv_{tab_key}",
        )
    with dl2:
        st.download_button(
            label="Download Notes",
            data=result.notes_csv_bytes,
            file_name=result.notes_filename,
            mime="text/csv",
            use_container_width=True,
            key=f"dl_notes_{tab_key}",
        )

    with st.expander("View full translated file"):
        st.dataframe(result.translated_df, use_container_width=True)


def render_footer():
    """Render centered footer."""
    st.markdown("""
    <div class="footer">
        Qualtrics Dashboard Translator &middot;
        Powered by Argos Translate &middot;
        Free &amp; Offline
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN APP — Assemble all sections
# ═══════════════════════════════════════════════════════════════════════════

def main():
    # 1. Inject CSS design system
    inject_css()

    # 2. Header: maple leaf + title + subtitle + divider
    render_header()

    # 3. Sidebar: settings (encoding, engine, API key)
    use_bom, provider, api_key = render_sidebar()

    # 4. Step 1: Reference file upload + translation memory
    memory = render_reference_upload()

    # 5. Steps 2-4: File selection → Translation → Download
    render_file_selection(use_bom, provider, api_key)

    # 6. Footer
    render_footer()


if __name__ == "__main__":
    main()
else:
    # Streamlit runs the file directly, not as __main__
    main()
