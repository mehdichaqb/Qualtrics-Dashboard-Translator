"""
Qualtrics Dashboard Translator — Streamlit App
Clean, centered, dark-mode UI.
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

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Qualtrics Translator",
    page_icon="🍁",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── SVG maple leaf (pure red, simple) ────────────────────────────────────
MAPLE_SVG = """<svg width="48" height="48" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M18 2L20.5 9.5L24 7L23 12L29 11L25.5 15L32 16L26 19L30 24L23 22L24 28L18 23L12 28L13 22L6 24L10 19L4 16L10.5 15L7 11L13 12L12 7L15.5 9.5L18 2Z" fill="#DC2626"/>
</svg>"""

# ══════════════════════════════════════════════════════════════════════════
#  COMPLETE CSS — from scratch
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* ── Light mode defaults ──────────────────────────── */
    :root {
        --bg: #FAFAFA;
        --bg-card: #FFFFFF;
        --bg-muted: #F4F4F5;
        --bg-hover: #E4E4E7;
        --text: #18181B;
        --text-sub: #71717A;
        --text-dim: #A1A1AA;
        --border: #E4E4E7;
        --red: #DC2626;
        --red-dark: #B91C1C;
        --red-glow: rgba(220,38,38,0.2);
        --red-soft: rgba(220,38,38,0.07);
        --green: #16A34A;
        --green-soft: rgba(22,163,74,0.1);
        --amber: #D97706;
        --amber-soft: rgba(217,119,6,0.1);
        --r: 20px;
        --r-sm: 14px;
        --r-full: 999px;
        --shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03);
        --shadow-lg: 0 10px 40px rgba(0,0,0,0.06);
    }

    /* ── Dark mode ────────────────────────────────────── */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #09090B;
            --bg-card: #18181B;
            --bg-muted: #27272A;
            --bg-hover: #3F3F46;
            --text: #FAFAFA;
            --text-sub: #A1A1AA;
            --text-dim: #71717A;
            --border: #27272A;
            --red-glow: rgba(220,38,38,0.3);
            --red-soft: rgba(220,38,38,0.12);
            --green-soft: rgba(22,163,74,0.15);
            --amber-soft: rgba(217,119,6,0.15);
            --shadow: 0 1px 3px rgba(0,0,0,0.3);
            --shadow-lg: 0 10px 40px rgba(0,0,0,0.4);
        }
    }
    [data-testid="stAppViewContainer"][style*="background-color: rgb(14"],
    [data-testid="stAppViewContainer"][style*="background-color: rgb(0"],
    .stApp[data-theme="dark"] {
        --bg: #09090B;
        --bg-card: #18181B;
        --bg-muted: #27272A;
        --bg-hover: #3F3F46;
        --text: #FAFAFA;
        --text-sub: #A1A1AA;
        --text-dim: #71717A;
        --border: #27272A;
        --red-glow: rgba(220,38,38,0.3);
        --red-soft: rgba(220,38,38,0.12);
        --green-soft: rgba(22,163,74,0.15);
        --amber-soft: rgba(217,119,6,0.15);
        --shadow: 0 1px 3px rgba(0,0,0,0.3);
        --shadow-lg: 0 10px 40px rgba(0,0,0,0.4);
    }

    /* ── Reset & base ─────────────────────────────────── */
    .stApp, .stApp *, .stMarkdown, .stMarkdown * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    header[data-testid="stHeader"] { background: transparent !important; }

    /* ── Centered wrapper ─────────────────────────────── */
    .center-wrap {
        max-width: 720px;
        margin: 0 auto;
        text-align: center;
    }

    /* ── Logo + Title ─────────────────────────────────── */
    .logo-area {
        text-align: center;
        padding: 56px 0 16px 0;
    }
    .logo-area svg { display: inline-block; }
    .app-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 900;
        color: var(--text);
        letter-spacing: -0.04em;
        margin: 8px 0 0 0;
        line-height: 1;
    }
    .app-sub {
        text-align: center;
        font-size: 1.1rem;
        color: var(--text-sub);
        font-weight: 400;
        margin: 10px 0 0 0;
    }

    /* ── Thin divider ─────────────────────────────────── */
    .sep {
        border: none;
        border-top: 1px solid var(--border);
        margin: 40px auto;
        max-width: 720px;
    }

    /* ── Step heading (centered) ──────────────────────── */
    .step-h {
        text-align: center;
        margin-bottom: 8px;
    }
    .step-h .num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px; height: 30px;
        border-radius: var(--r-full);
        background: var(--red);
        color: #fff;
        font-size: 0.8rem;
        font-weight: 700;
        margin-right: 10px;
        vertical-align: middle;
    }
    .step-h .txt {
        font-size: 1.5rem;
        font-weight: 800;
        color: var(--text);
        letter-spacing: -0.02em;
        vertical-align: middle;
    }
    .step-sub {
        text-align: center;
        color: var(--text-sub);
        font-size: 0.95rem;
        margin: 0 auto 28px auto;
        max-width: 560px;
        line-height: 1.55;
    }

    /* ── Drop zone cards ──────────────────────────────── */
    .drop-card {
        background: var(--bg-card);
        border: 2px dashed var(--border);
        border-radius: var(--r);
        padding: 36px 24px 20px;
        text-align: center;
        transition: border-color 0.2s, box-shadow 0.2s;
        cursor: default;
    }
    .drop-card:hover {
        border-color: var(--red);
        box-shadow: 0 0 0 3px var(--red-glow);
    }
    .drop-card .dc-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text);
        margin: 0 0 4px 0;
    }
    .drop-card .dc-drag {
        font-size: 0.95rem;
        color: var(--text-dim);
        margin: 0 0 2px 0;
    }
    .drop-card .dc-detail {
        font-size: 0.8rem;
        color: var(--text-dim);
        margin: 0;
    }

    /* Style the Streamlit uploader INSIDE drop cards to be invisible/minimal */
    .clean-uploader [data-testid="stFileUploader"] {
        margin-top: 8px;
    }
    .clean-uploader [data-testid="stFileUploader"] label { display: none !important; }
    .clean-uploader [data-testid="stFileUploader"] section {
        border: none !important;
        background: transparent !important;
        padding: 8px 0 0 0 !important;
    }
    .clean-uploader [data-testid="stFileUploader"] section > div {
        display: flex;
        justify-content: center;
    }
    .clean-uploader [data-testid="stFileUploader"] button {
        background: var(--bg-muted) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-sub) !important;
        border-radius: var(--r-full) !important;
        padding: 10px 28px !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 0.15s !important;
    }
    .clean-uploader [data-testid="stFileUploader"] button:hover {
        background: var(--bg-hover) !important;
        color: var(--text) !important;
    }
    .clean-uploader [data-testid="stFileUploader"] small {
        text-align: center !important;
        display: block !important;
        color: var(--text-dim) !important;
        font-size: 0.75rem !important;
    }

    /* ── Status pills (centered) ──────────────────────── */
    .status-row {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
        margin: 20px 0 0 0;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 20px;
        border-radius: var(--r-full);
        font-size: 0.88rem;
        font-weight: 600;
    }
    .pill-green { background: var(--green-soft); color: var(--green); }
    .pill-amber { background: var(--amber-soft); color: var(--amber); }
    .pill-ghost {
        background: var(--bg-muted);
        color: var(--text-sub);
    }

    /* ── Memory counter ───────────────────────────────── */
    .mem-num {
        text-align: center;
        margin: 16px 0 0 0;
    }
    .mem-num .big {
        font-size: 3rem;
        font-weight: 900;
        color: var(--red);
        line-height: 1;
    }
    .mem-num .lbl {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-dim);
        font-weight: 600;
        margin-top: 2px;
    }

    /* ── Tabs (pill style) ────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        justify-content: center;
        gap: 6px;
        background: var(--bg-muted);
        border-radius: var(--r-full);
        padding: 5px;
        display: inline-flex;
        margin: 0 auto;
    }
    /* Center the tab list container */
    .stTabs > div:first-child {
        display: flex;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--r-full);
        padding: 12px 32px;
        font-weight: 700;
        font-size: 1.05rem;
        color: var(--text-sub);
        background: transparent;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background: var(--red) !important;
        color: #fff !important;
        box-shadow: 0 2px 10px var(--red-glow);
    }
    .stTabs [data-baseweb="tab-border"],
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* ── Tab inner description ─────────────────────────── */
    .tab-info {
        text-align: center;
        color: var(--text-sub);
        font-size: 0.95rem;
        margin: 8px auto 20px auto;
        max-width: 520px;
        line-height: 1.5;
    }
    .tab-info code {
        background: var(--red-soft);
        color: var(--red);
        padding: 2px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.88rem;
    }

    /* ── Translate file uploader (inside tabs) ─────────── */
    .tab-uploader {
        max-width: 520px;
        margin: 0 auto;
    }
    .tab-uploader [data-testid="stFileUploader"] section {
        border-radius: var(--r) !important;
        border: 2px dashed var(--border) !important;
        padding: 28px 20px !important;
        background: var(--bg-card) !important;
        transition: border-color 0.2s !important;
    }
    .tab-uploader [data-testid="stFileUploader"] section:hover {
        border-color: var(--red) !important;
    }
    .tab-uploader [data-testid="stFileUploader"] button {
        border-radius: var(--r-full) !important;
        padding: 10px 28px !important;
        font-weight: 600 !important;
    }

    /* ── Stats (3-col centered) ────────────────────────── */
    .stats-row {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin: 20px auto;
        max-width: 500px;
    }
    .stat-box {
        flex: 1;
        background: var(--bg-muted);
        border-radius: var(--r-sm);
        padding: 18px 12px;
        text-align: center;
    }
    .stat-box .val {
        font-size: 1.6rem;
        font-weight: 800;
        color: var(--text);
        line-height: 1;
    }
    .stat-box .lbl {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-dim);
        font-weight: 600;
        margin-top: 4px;
    }

    /* ── BIG translate button ─────────────────────────── */
    .stButton > button {
        border-radius: var(--r-full) !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        padding: 18px 48px !important;
        min-height: 62px !important;
        transition: all 0.2s ease !important;
        letter-spacing: -0.01em !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 auto !important;
        text-align: center !important;
    }
    .stButton > button[kind="primary"] {
        background: var(--red) !important;
        border: none !important;
        color: #fff !important;
        box-shadow: 0 4px 20px var(--red-glow) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--red-dark) !important;
        box-shadow: 0 6px 28px var(--red-glow) !important;
        transform: translateY(-2px) !important;
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(0px) !important;
    }

    /* secondary buttons */
    .stButton > button[kind="secondary"] {
        background: var(--bg-muted) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: var(--bg-hover) !important;
    }

    /* ── Download buttons ─────────────────────────────── */
    .stDownloadButton {
        text-align: center;
    }
    .stDownloadButton > button {
        border-radius: var(--r-full) !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        padding: 16px 40px !important;
        min-height: 58px !important;
        background: var(--red) !important;
        border: none !important;
        color: #fff !important;
        box-shadow: 0 4px 20px var(--red-glow) !important;
        transition: all 0.2s ease !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        margin: 0 auto !important;
    }
    .stDownloadButton > button:hover {
        background: var(--red-dark) !important;
        box-shadow: 0 6px 28px var(--red-glow) !important;
        transform: translateY(-2px) !important;
    }

    /* ── Provenance metrics ────────────────────────────── */
    .prov-row {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin: 20px auto;
        max-width: 540px;
        flex-wrap: wrap;
    }
    .prov-box {
        flex: 1;
        min-width: 110px;
        background: var(--bg-muted);
        border-radius: var(--r-sm);
        padding: 16px 10px;
        text-align: center;
    }
    .prov-box .val {
        font-size: 1.5rem;
        font-weight: 800;
        color: var(--text);
    }
    .prov-box .lbl {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--text-dim);
        font-weight: 600;
        margin-top: 2px;
    }

    /* ── Done banner ──────────────────────────────────── */
    .done-banner {
        text-align: center;
        padding: 32px 20px;
        margin: 24px auto;
        max-width: 480px;
        background: var(--bg-muted);
        border-radius: var(--r);
    }
    .done-banner .check {
        font-size: 2.4rem;
        line-height: 1;
        margin-bottom: 8px;
    }
    .done-banner h3 {
        font-size: 1.3rem;
        font-weight: 800;
        color: var(--text);
        margin: 0;
    }
    .done-banner p {
        font-size: 0.92rem;
        color: var(--text-sub);
        margin: 4px 0 0 0;
    }

    /* ── Expander ─────────────────────────────────────── */
    details {
        border-radius: var(--r-sm) !important;
    }
    .streamlit-expanderHeader {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }

    /* ── Progress bar ─────────────────────────────────── */
    .stProgress > div > div > div > div {
        background: var(--red) !important;
        border-radius: var(--r-full) !important;
    }

    /* ── Alerts ───────────────────────────────────────── */
    .stSuccess, .stError, .stWarning, .stInfo {
        border-radius: var(--r-sm) !important;
        font-size: 0.95rem !important;
        text-align: center !important;
    }

    /* ── Footer ───────────────────────────────────────── */
    .foot {
        text-align: center;
        color: var(--text-dim);
        font-size: 0.82rem;
        padding: 48px 0 24px;
    }

    /* ── Sidebar ──────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: var(--bg-card) !important;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  LOGO + TITLE
# ══════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="logo-area">{MAPLE_SVG}</div>
<h1 class="app-title">Qualtrics Translator</h1>
<p class="app-sub">English &rarr; French (Canada) &middot; Free &amp; Offline</p>
""", unsafe_allow_html=True)


# ── Sidebar: Settings ────────────────────────────────────────────────────
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
    st.caption("Token protection & HTML preservation always on.")


# ══════════════════════════════════════════════════════════════════════════
#  STEP 1 — Reference Files
# ══════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="sep">', unsafe_allow_html=True)

st.markdown("""
<div class="step-h">
    <span class="num">1</span>
    <span class="txt">Reference Files</span>
</div>
<p class="step-sub">
    Upload previously translated files to build translation memory.
    Known translations are reused automatically. Optional but recommended.
</p>
""", unsafe_allow_html=True)

ref_col1, ref_col2 = st.columns(2)

with ref_col1:
    st.markdown("""
    <div class="drop-card">
        <div class="dc-title">Reference Labels File</div>
        <div class="dc-drag">Drag and drop file here</div>
        <div class="dc-detail">Previously translated data-translations CSV or XLSX</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="clean-uploader">', unsafe_allow_html=True)
    ref_labels_file = st.file_uploader(
        "ref labels",
        type=["csv", "xlsx"],
        key="ref_labels",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

with ref_col2:
    st.markdown("""
    <div class="drop-card">
        <div class="dc-title">Reference Data File</div>
        <div class="dc-drag">Drag and drop file here</div>
        <div class="dc-detail">Previously translated dashboard-translations CSV or XLSX</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="clean-uploader">', unsafe_allow_html=True)
    ref_data_file = st.file_uploader(
        "ref data",
        type=["csv", "xlsx"],
        key="ref_data",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)


# Build translation memory
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

# Status pills + memory count
labels_ok = st.session_state.get("ref_labels_loaded", False)
data_ok = st.session_state.get("ref_data_loaded", False)
total_entries = memory.data_file_entries + memory.label_file_entries

labels_pill = (
    '<span class="pill pill-green">&#10003; Labels loaded</span>'
    if labels_ok else
    '<span class="pill pill-amber">&#9675; No labels reference</span>'
)
data_pill = (
    '<span class="pill pill-green">&#10003; Data loaded</span>'
    if data_ok else
    '<span class="pill pill-amber">&#9675; No data reference</span>'
)

st.markdown(f"""
<div class="status-row">
    {labels_pill}
    {data_pill}
</div>
<div class="mem-num">
    <div class="big">{total_entries:,}</div>
    <div class="lbl">Memory Entries</div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  STEP 2 — Translate
# ══════════════════════════════════════════════════════════════════════════
st.markdown('<hr class="sep">', unsafe_allow_html=True)

st.markdown("""
<div class="step-h">
    <span class="num">2</span>
    <span class="txt">Translate</span>
</div>
<p class="step-sub">
    Pick your file type, upload, and translate.
    Output fills both FR and FR-CA columns.
</p>
""", unsafe_allow_html=True)

tab_labels, tab_data = st.tabs(["Labels File", "Data File"])


def _run_translation(
    uploaded_file,
    file_type: FileType,
    source_col_override: Optional[str],
    tab_key: str,
):
    """Shared translation logic for both tabs."""
    if uploaded_file is None:
        return

    try:
        preview_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        preview_df = load_file(io.BytesIO(preview_bytes), file_name=uploaded_file.name)

        all_cols = list(preview_df.columns)
        target_cols = [c for c in all_cols if c.strip().upper() in ("FR", "FR-CA")]

        src_display = source_col_override or "EN"
        st.markdown(
            f'<div class="stats-row">'
            f'  <div class="stat-box"><div class="val">{len(preview_df):,}</div><div class="lbl">Rows</div></div>'
            f'  <div class="stat-box"><div class="val">{len(all_cols)}</div><div class="lbl">Columns</div></div>'
            f'  <div class="stat-box"><div class="val">{src_display}</div><div class="lbl">Source</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Preview first 8 rows"):
            st.dataframe(preview_df.head(8), use_container_width=True)

    except Exception as e:
        st.error(f"Error loading file: {e}")
        return

    st.markdown("")
    if st.button(
        "Translate Now",
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

        progress_bar = st.progress(0, text="Initializing...")

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
            return

    # ── Results ──────────────────────────────────────────────────────
    result_key = f"result_{tab_key}"
    if result_key in st.session_state:
        result: PipelineResult = st.session_state[result_key]

        if result.validation.passed:
            st.success("Validation passed — file integrity preserved")
        else:
            st.error("Validation failed")
            for issue in result.validation.issues:
                st.warning(issue)

        # Provenance
        prov_counts: dict[str, int] = {}
        for t in result.translations:
            prov_counts[t.provenance.value] = prov_counts.get(t.provenance.value, 0) + 1

        ref_count = prov_counts.get("reference_exact_match", 0) + prov_counts.get("reference_normalized_match", 0)
        cache_count = prov_counts.get("session_cache", 0)
        fresh_count = prov_counts.get("fresh_translation", 0)
        skip_count = sum(v for k, v in prov_counts.items() if "skipped" in k)

        st.markdown(
            f'<div class="prov-row">'
            f'  <div class="prov-box"><div class="val">{ref_count}</div><div class="lbl">Reference</div></div>'
            f'  <div class="prov-box"><div class="val">{cache_count}</div><div class="lbl">Cache</div></div>'
            f'  <div class="prov-box"><div class="val">{fresh_count}</div><div class="lbl">Fresh</div></div>'
            f'  <div class="prov-box"><div class="val">{skip_count}</div><div class="lbl">Skipped</div></div>'
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

        # Done banner
        st.markdown("""
        <div class="done-banner">
            <div class="check">&#10003;</div>
            <h3>Translation Complete</h3>
            <p>Ready for Qualtrics import</p>
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


# ── Labels File Tab ──────────────────────────────────────────────────────
with tab_labels:
    st.markdown(
        '<p class="tab-info">'
        'Source from <code>default value</code> column &rarr; '
        'translated into <strong>FR</strong> + <strong>FR-CA</strong>'
        '</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="tab-uploader">', unsafe_allow_html=True)
    labels_upload = st.file_uploader(
        "Upload Labels File",
        type=["csv", "xlsx"],
        key="labels_main",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    _run_translation(labels_upload, FileType.DATA_FILE, "default value", "labels")


# ── Data File Tab ────────────────────────────────────────────────────────
with tab_data:
    st.markdown(
        '<p class="tab-info">'
        'Source from <code>EN</code> column &rarr; '
        'translated into <strong>FR</strong> + <strong>FR-CA</strong>'
        '</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="tab-uploader">', unsafe_allow_html=True)
    data_upload = st.file_uploader(
        "Upload Data File",
        type=["csv", "xlsx"],
        key="data_main",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)
    _run_translation(data_upload, FileType.LABEL_FILE, None, "data")


# ── Footer ───────────────────────────────────────────────────────────────
st.markdown("""
<p class="foot">
    Qualtrics Translator &middot; Powered by Argos Translate &middot; Free &amp; Offline
</p>
""", unsafe_allow_html=True)
