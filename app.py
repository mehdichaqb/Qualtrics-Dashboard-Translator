"""
Qualtrics Dashboard Translator — Streamlit App
==============================================
Polished internal government analytics tool interface.
Minimalist, centered, dark-mode aware, modular UI.
Backend pipeline preserved.
"""
from __future__ import annotations
import hashlib
import io
import os
from typing import Optional
import pandas as pd
import streamlit as st
from processor.detector import FileType
from processor.file_loader import load_file
from processor.pipeline import PipelineConfig, PipelineResult, run_pipeline
from processor.reference_memory import TranslationMemory, build_memory_from_reference
from processor.rules import Provenance
# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Qualtrics Dashboard Translator",
    page_icon="🍁",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
MAPLE_LEAF_SVG = """
<svg width="28" height="28" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path fill="#D52B1E" d="M31.9 6l4.2 10.6 7-3.6-1.8 8.2 9-1.3-5.9 7.1 8.8 2.7-8 4.5 5 8-9-2.3.8 9.2-9.2-7.6-9.2 7.6.8-9.2-9 2.3 5-8-8-4.5 8.8-2.7-5.9-7.1 9 1.3-1.8-8.2 7 3.6z"/>
</svg>
"""
CURVED_ARROW_SVG = """
<svg width="88" height="56" viewBox="0 0 88 56" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M8 10 C 28 10, 26 40, 56 40 L 70 40" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M62 32 L 74 40 L 62 48" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""
# ═══════════════════════════════════════════════════════════════════════════
# CSS — All 8 UI bugs fixed
# ═══════════════════════════════════════════════════════════════════════════
def inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ══════════════════════════════════════════════════════════
   LIGHT MODE — default variables
   FIX #8: More color accents in light mode
   ══════════════════════════════════════════════════════════ */
:root {
    --bg: #FFFFFF;
    --bg-soft: #F7F7F7;
    --bg-elevated: #F0F0F0;
    --bg-hover: #E8E8E8;
    --text: #111111;
    --text-sub: #333333;
    --text-dim: #6B7280;
    --border: #D9D9D9;
    --border-strong: #C0C0C0;
    /* FIX #8: accent borders for cards in light mode */
    --border-accent: rgba(28, 61, 90, 0.18);
    --red: #D52B1E;
    --red-hover: #B82219;
    --red-soft: rgba(213, 43, 30, 0.08);
    --red-glow: rgba(213, 43, 30, 0.20);
    --blue: #1C3D5A;
    --blue-2: #2B5C85;
    --blue-soft: rgba(28, 61, 90, 0.10);
    --green: #1A7742;
    --green-soft: rgba(26, 119, 66, 0.10);
    --amber: #B56F00;
    --amber-soft: rgba(181, 111, 0, 0.10);
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
    --shadow-md: 0 8px 24px rgba(0,0,0,0.08);
    --r-sm: 12px;
    --r-md: 16px;
    --r-lg: 24px;
    --r-pill: 999px;
    --transition: 150ms ease;
    /* FIX #8: divider accent in light mode */
    --divider-color: #D9D9D9;
}

/* ══════════════════════════════════════════════════════════
   DARK MODE — via OS preference
   FIX #1: All text explicitly light
   FIX #2: Cards/buttons use dark marine blue
   FIX #6: Background is dark grey, not pure black
   ══════════════════════════════════════════════════════════ */
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #1A1A1A;
        --bg-soft: #1C2E4A;
        --bg-elevated: #223754;
        --bg-hover: #2A4060;
        --text: #F3F4F6;
        --text-sub: #D1D5DB;
        --text-dim: #9CA3AF;
        --border: #2D4A6A;
        --border-strong: #3B5C82;
        --border-accent: rgba(96, 165, 250, 0.20);
        --red: #EF4444;
        --red-hover: #DC2626;
        --red-soft: rgba(239, 68, 68, 0.14);
        --red-glow: rgba(239, 68, 68, 0.28);
        --blue: #60A5FA;
        --blue-2: #93C5FD;
        --blue-soft: rgba(96, 165, 250, 0.16);
        --green: #34D399;
        --green-soft: rgba(52, 211, 153, 0.14);
        --amber: #FBBF24;
        --amber-soft: rgba(251, 191, 36, 0.14);
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.40);
        --shadow-md: 0 10px 28px rgba(0,0,0,0.45);
        --divider-color: #2D4A6A;
    }
}

/* ══════════════════════════════════════════════════════════
   DARK MODE — via Streamlit internal theme
   Duplicated to catch Streamlit's own dark mode toggle
   ══════════════════════════════════════════════════════════ */
.stApp[data-theme="dark"],
[data-theme="dark"],
[data-testid="stAppViewContainer"][style*="background-color: rgb(14"],
[data-testid="stAppViewContainer"][style*="background-color: rgb(0"] {
    --bg: #1A1A1A;
    --bg-soft: #1C2E4A;
    --bg-elevated: #223754;
    --bg-hover: #2A4060;
    --text: #F3F4F6;
    --text-sub: #D1D5DB;
    --text-dim: #9CA3AF;
    --border: #2D4A6A;
    --border-strong: #3B5C82;
    --border-accent: rgba(96, 165, 250, 0.20);
    --red: #EF4444;
    --red-hover: #DC2626;
    --red-soft: rgba(239, 68, 68, 0.14);
    --red-glow: rgba(239, 68, 68, 0.28);
    --blue: #60A5FA;
    --blue-2: #93C5FD;
    --blue-soft: rgba(96, 165, 250, 0.16);
    --green: #34D399;
    --green-soft: rgba(52, 211, 153, 0.14);
    --amber: #FBBF24;
    --amber-soft: rgba(251, 191, 36, 0.14);
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.40);
    --shadow-md: 0 10px 28px rgba(0,0,0,0.45);
    --divider-color: #2D4A6A;
}

/* ══════════════════════════════════════════════════════════
   GLOBAL TYPOGRAPHY
   ══════════════════════════════════════════════════════════ */
html, body, .stApp, [data-testid="stAppViewContainer"],
.stMarkdown, div, p, span, label, button, h1, h2, h3 {
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

/* FIX #7: Hide GitHub icon / toolbar buttons */
[data-testid="stToolbar"],
[data-testid="stDecoration"],
.stDeployButton,
#MainMenu,
header [data-testid="stToolbar"] {
    display: none !important;
    visibility: hidden !important;
}

/* Centered container */
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 1100px !important;
    padding-top: 1.2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* Hide default file uploader labels */
[data-testid="stFileUploader"] > label {
    display: none !important;
}

/* ══════════════════════════════════════════════════════════
   HEADER
   FIX #5: Title ~76px, split onto two lines
   FIX #1: Title uses var(--text) for dark mode
   FIX #8: Leaf circle has red border accent in light mode
   ══════════════════════════════════════════════════════════ */
.app-header {
    text-align: center;
    padding-top: 32px;
}
.app-header .leaf {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--red-soft);
    border: 2px solid rgba(213, 43, 30, 0.15);
    box-shadow: var(--shadow-sm);
    margin-bottom: 16px;
}
.app-header h1 {
    margin: 0;
    color: var(--text) !important;
    font-size: 76px;
    font-weight: 800;
    line-height: 1.04;
    letter-spacing: -0.04em;
}
.app-header p {
    margin: 14px 0 32px 0;
    color: var(--text-sub) !important;
    font-size: 18px;
    font-weight: 400;
}
/* FIX #8: Divider uses subtle red accent in light mode */
.app-divider {
    width: 100%;
    max-width: 800px;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--red) 30%, var(--red) 70%, transparent);
    opacity: 0.2;
    border: 0;
    margin: 0 auto;
}

/* ══════════════════════════════════════════════════════════
   SECTIONS
   FIX #1: All section text uses CSS vars for dark mode
   FIX #4: Centered description text
   ══════════════════════════════════════════════════════════ */
.section-wrap {
    margin-top: 56px;
    text-align: center;
    width: 100%;
}
.section-wrap h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    font-weight: 600;
    color: var(--text) !important;
    text-align: center;
}
/* FIX #4: ensure description is truly centered */
.section-wrap p {
    margin: 0 auto 28px auto;
    max-width: 660px;
    font-size: 15px;
    color: var(--text-dim) !important;
    text-align: center;
    display: block;
    width: 100%;
}
/* FIX #8: Section divider uses blue accent */
.section-divider {
    width: 100%;
    max-width: 800px;
    height: 1px;
    background: var(--divider-color);
    border: 0;
    margin: 56px auto 0 auto;
}

/* ══════════════════════════════════════════════════════════
   CARDS
   FIX #2: Uses --bg-soft which becomes dark marine blue
   ══════════════════════════════════════════════════════════ */
.soft-card {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 28px;
    box-shadow: var(--shadow-sm);
}

/* ══════════════════════════════════════════════════════════
   REFERENCE UPLOAD CARDS
   FIX #1: All text uses CSS vars
   FIX #2: Cards use --bg-soft (dark marine blue in dark mode)
   FIX #8: Light mode cards have accent border
   ══════════════════════════════════════════════════════════ */
.ref-caption {
    text-align: center;
    margin-bottom: 12px;
}
.ref-caption .title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text) !important;
    margin-bottom: 4px;
}
.ref-caption .drag {
    font-size: 15px;
    color: var(--text-sub) !important;
    margin-bottom: 4px;
}
.ref-caption .detail {
    font-size: 13px;
    color: var(--text-dim) !important;
    line-height: 1.4;
}

/* File uploader styled as drop zone card */
.uploader-wrap {
    margin-top: 8px;
}
.uploader-wrap [data-testid="stFileUploader"] {
    width: 100%;
}
/* FIX #2: uploader section bg uses --bg-soft (marine blue in dark) */
/* FIX #8: dashed border uses accent color in light mode */
.uploader-wrap [data-testid="stFileUploader"] section {
    min-height: 160px !important;
    background: var(--bg-soft) !important;
    border: 2px dashed var(--border-accent) !important;
    border-radius: 16px !important;
    padding: 18px 20px !important;
    transition: border-color var(--transition), box-shadow var(--transition), transform var(--transition) !important;
}
.uploader-wrap [data-testid="stFileUploader"] section:hover {
    border-color: var(--blue) !important;
    box-shadow: var(--shadow-md) !important;
    transform: translateY(-1px);
}
/* FIX #1: small text inside uploader */
.uploader-wrap [data-testid="stFileUploader"] small {
    display: block !important;
    text-align: center !important;
    color: var(--text-dim) !important;
    font-size: 12px !important;
}
/* FIX #1: browse button text color */
.uploader-wrap [data-testid="stFileUploader"] button {
    border-radius: 999px !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-elevated) !important;
    color: var(--text) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 8px 22px !important;
    transition: all var(--transition) !important;
}
.uploader-wrap [data-testid="stFileUploader"] button:hover {
    border-color: var(--blue) !important;
    background: var(--blue-soft) !important;
    color: var(--blue) !important;
}
/* FIX #1: file uploader drag-over text */
.uploader-wrap [data-testid="stFileUploader"] section div,
.uploader-wrap [data-testid="stFileUploader"] section span,
.uploader-wrap [data-testid="stFileUploader"] section p {
    color: var(--text-dim) !important;
}

/* ══════════════════════════════════════════════════════════
   STATUS PILLS
   ══════════════════════════════════════════════════════════ */
.status-row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    margin-top: 24px;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 9px 18px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 600;
}
.status-pill.ok {
    background: var(--green-soft);
    color: var(--green);
}
.status-pill.warn {
    background: var(--amber-soft);
    color: var(--amber);
}

/* ══════════════════════════════════════════════════════════
   MEMORY BOX
   FIX #2: Uses --bg-soft (marine blue in dark mode)
   FIX #1: Label text uses --text-dim
   FIX #8: Red border accent in light mode
   ══════════════════════════════════════════════════════════ */
.memory-box {
    margin: 20px auto 0 auto;
    max-width: 220px;
    text-align: center;
    background: var(--bg-soft);
    border: 1px solid var(--border-accent);
    border-radius: 14px;
    padding: 20px;
    box-shadow: var(--shadow-sm);
}
.memory-box .value {
    font-size: 36px;
    font-weight: 700;
    color: var(--red);
    line-height: 1;
}
.memory-box .label {
    margin-top: 5px;
    font-size: 13px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim) !important;
}

/* ══════════════════════════════════════════════════════════
   FILE TYPE SELECTOR BUTTONS
   FIX #2: Secondary buttons use --bg-soft (marine blue in dark)
   FIX #1: Button text explicitly set
   FIX #8: Hover borders use blue accent
   ══════════════════════════════════════════════════════════ */
.stButton > button {
    min-height: 58px !important;
    border-radius: 24px !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 16px 34px !important;
    transition: all var(--transition) !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    text-align: center !important;
    margin: 0 auto !important;
}
.stButton > button[kind="primary"] {
    background: var(--red) !important;
    border: 0 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 20px var(--red-glow) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--red-hover) !important;
    transform: scale(1.03) !important;
    box-shadow: 0 8px 24px var(--red-glow) !important;
}
/* FIX #2: Secondary uses --bg-soft for dark marine blue in dark mode */
.stButton > button[kind="secondary"] {
    background: var(--bg-soft) !important;
    color: var(--text) !important;
    border: 2px solid var(--border) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: var(--blue) !important;
    background: var(--blue-soft) !important;
    color: var(--blue) !important;
    transform: scale(1.03) !important;
}

/* ══════════════════════════════════════════════════════════
   DOWNLOAD BUTTONS
   ══════════════════════════════════════════════════════════ */
.stDownloadButton > button {
    min-height: 58px !important;
    border-radius: 24px !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 16px 34px !important;
    background: var(--red) !important;
    color: #FFFFFF !important;
    border: 0 !important;
    box-shadow: 0 4px 20px var(--red-glow) !important;
    transition: all var(--transition) !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    text-align: center !important;
    margin: 0 auto !important;
}
.stDownloadButton > button:hover {
    background: var(--red-hover) !important;
    transform: scale(1.03) !important;
    box-shadow: 0 8px 24px var(--red-glow) !important;
}

/* ══════════════════════════════════════════════════════════
   TRANSLATE PANEL
   FIX #1: hint text uses CSS vars
   ══════════════════════════════════════════════════════════ */
.panel-card {
    max-width: 720px;
    margin: 0 auto;
}
.panel-hint {
    text-align: center;
    font-size: 15px;
    color: var(--text-dim) !important;
    margin-bottom: 18px;
}
.panel-hint strong {
    color: var(--text) !important;
}
.panel-hint code {
    background: var(--blue-soft);
    color: var(--blue);
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
}

/* ══════════════════════════════════════════════════════════
   STATS ROW
   FIX #1: value/label text uses vars
   FIX #8: accent border in light mode
   ══════════════════════════════════════════════════════════ */
.stats-row {
    display: flex;
    justify-content: center;
    gap: 14px;
    flex-wrap: wrap;
    margin: 22px auto 0 auto;
    max-width: 560px;
}
.stat-card {
    flex: 1;
    min-width: 150px;
    background: var(--bg-soft);
    border: 1px solid var(--border-accent);
    border-radius: 14px;
    padding: 18px 14px;
    text-align: center;
}
.stat-card .value {
    font-size: 22px;
    font-weight: 700;
    color: var(--text) !important;
    line-height: 1;
}
.stat-card .label {
    margin-top: 5px;
    font-size: 12px;
    color: var(--text-dim) !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
}

/* ══════════════════════════════════════════════════════════
   PROCESSING CARD
   FIX #1: text colors
   ══════════════════════════════════════════════════════════ */
.processing-card {
    max-width: 720px;
    margin: 24px auto 0 auto;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px 24px 18px 24px;
    text-align: center;
}
.processing-card .title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text) !important;
    margin-bottom: 4px;
}
.processing-card .sub {
    font-size: 14px;
    color: var(--text-dim) !important;
    margin-bottom: 18px;
}

/* ══════════════════════════════════════════════════════════
   PROVENANCE METRICS
   FIX #1: text colors
   FIX #8: accent border
   ══════════════════════════════════════════════════════════ */
.prov-row {
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
    margin: 24px auto;
    max-width: 700px;
}
.prov-card {
    flex: 1;
    min-width: 125px;
    background: var(--bg-soft);
    border: 1px solid var(--border-accent);
    border-radius: 14px;
    padding: 16px 12px;
    text-align: center;
}
.prov-card .value {
    font-size: 22px;
    font-weight: 700;
    color: var(--text) !important;
}
.prov-card .label {
    margin-top: 4px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim) !important;
    font-weight: 500;
}

/* ══════════════════════════════════════════════════════════
   DOWNLOAD / DONE AREA
   FIX #1: text colors
   FIX #3: arrow icon uses SVG (already correct)
   ══════════════════════════════════════════════════════════ */
.done-area {
    text-align: center;
    margin: 34px auto 0 auto;
    max-width: 620px;
}
.done-area .done-arrow {
    color: var(--red);
    display: inline-flex;
    margin-bottom: 6px;
    animation: floatArrow 1.5s ease-in-out infinite;
}
@keyframes floatArrow {
    0%,100% { transform: translateY(0px); }
    50% { transform: translateY(-6px); }
}
.done-area h3 {
    margin: 0 0 6px 0;
    color: var(--text) !important;
    font-size: 22px;
    font-weight: 700;
}
.done-area p {
    margin: 0 0 20px 0;
    color: var(--text-dim) !important;
    font-size: 15px;
}
.secondary-downloads {
    max-width: 420px;
    margin: 18px auto 0 auto;
}

/* ══════════════════════════════════════════════════════════
   PROGRESS BAR
   ══════════════════════════════════════════════════════════ */
.stProgress > div > div > div > div {
    background: var(--red) !important;
    border-radius: 999px !important;
}

/* ══════════════════════════════════════════════════════════
   ALERTS + EXPANDERS
   ══════════════════════════════════════════════════════════ */
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: 14px !important;
}
details {
    border-radius: 14px !important;
}
.streamlit-expanderHeader {
    font-size: 15px !important;
    font-weight: 600 !important;
}

/* ══════════════════════════════════════════════════════════
   FOOTER
   FIX #1: text color
   FIX #8: red dot accent
   ══════════════════════════════════════════════════════════ */
.app-footer {
    text-align: center;
    font-size: 13px;
    color: var(--text-dim) !important;
    padding: 56px 0 24px 0;
}

/* ══════════════════════════════════════════════════════════
   SIDEBAR
   FIX #1: sidebar text colors
   ══════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: var(--bg-soft) !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] p {
    color: var(--text) !important;
}

/* ══════════════════════════════════════════════════════════
   DARK MODE EXPLICIT OVERRIDES
   Final safety net: force light text on all custom elements
   when Streamlit applies dark background
   ══════════════════════════════════════════════════════════ */
@media (prefers-color-scheme: dark) {
    .app-header h1,
    .section-wrap h2,
    .ref-caption .title,
    .stat-card .value,
    .prov-card .value,
    .processing-card .title,
    .done-area h3,
    .memory-box .label,
    .panel-hint strong {
        color: #F3F4F6 !important;
    }
    .app-header p,
    .ref-caption .drag,
    .section-wrap p,
    .ref-caption .detail,
    .stat-card .label,
    .prov-card .label,
    .processing-card .sub,
    .done-area p,
    .panel-hint,
    .app-footer {
        color: #9CA3AF !important;
    }
    /* FIX #6: Force Streamlit's own background to dark grey */
    .stApp,
    [data-testid="stAppViewContainer"] {
        background-color: #1A1A1A !important;
    }
}
</style>
""",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def file_signature(uploaded_file) -> Optional[str]:
    """Create a stable signature for an uploaded file."""
    if uploaded_file is None:
        return None
    data = uploaded_file.getvalue()
    return hashlib.sha256(uploaded_file.name.encode("utf-8") + b"::" + data).hexdigest()


def rebuild_reference_memory(ref_labels_file, ref_data_file) -> TranslationMemory:
    """
    Always rebuild memory from the current uploaded reference files.
    This avoids stale session-state flags when users replace files.
    """
    memory = TranslationMemory()
    if ref_labels_file is not None:
        label_df = load_file(io.BytesIO(ref_labels_file.getvalue()), file_name=ref_labels_file.name)
        build_memory_from_reference(label_df, memory, "EN", "FR-CA")
        build_memory_from_reference(label_df, memory, "EN", "FR")
    if ref_data_file is not None:
        data_df = load_file(io.BytesIO(ref_data_file.getvalue()), file_name=ref_data_file.name)
        build_memory_from_reference(data_df, memory, "EN", "FR-CA")
        build_memory_from_reference(data_df, memory, "EN", "FR")
    return memory


def reset_result_for(tab_key: str) -> None:
    result_key = f"result_{tab_key}"
    if result_key in st.session_state:
        del st.session_state[result_key]


# ═══════════════════════════════════════════════════════════════════════════
# RENDERERS
# ═══════════════════════════════════════════════════════════════════════════

def render_header() -> None:
    """FIX #5: Title is ~76px, split onto two lines with <br>."""
    st.markdown(
        f"""
<div class="app-header">
    <div class="leaf">{MAPLE_LEAF_SVG}</div>
    <h1>Qualtrics Dashboard<br>Translator</h1>
    <p>Translate Qualtrics Data and Label files between English and French (Canada)</p>
    <div class="app-divider"></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[bool, str, str]:
    with st.sidebar:
        st.markdown("### Advanced Settings")
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
        else:
            provider = "mock"
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


def render_reference_upload() -> TranslationMemory:
    st.markdown(
        """
<div class="section-wrap">
    <h2>Upload Your Reference Files</h2>
    <p>
        Reference files allow the system to reuse existing translations
        before generating new ones.
    </p>
</div>
""",
        unsafe_allow_html=True,
    )
    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        st.markdown(
            """
<div class="ref-caption">
    <div class="title">Reference Label Files</div>
    <div class="drag">Drag and drop file here</div>
    <div class="detail">
        Previously translated Qualtrics label files with EN / FR / FR-CA locale values
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="uploader-wrap">', unsafe_allow_html=True)
        ref_labels_file = st.file_uploader(
            "Reference Label Files",
            type=["csv", "xlsx"],
            key="ref_labels_file",
            label_visibility="collapsed",
            help="Optional translation memory source for label files.",
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with col_right:
        st.markdown(
            """
<div class="ref-caption">
    <div class="title">Reference Data Files</div>
    <div class="drag">Drag and drop file here</div>
    <div class="detail">
        Previously translated Qualtrics data files using the default value column as source
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="uploader-wrap">', unsafe_allow_html=True)
        ref_data_file = st.file_uploader(
            "Reference Data Files",
            type=["csv", "xlsx"],
            key="ref_data_file",
            label_visibility="collapsed",
            help="Optional translation memory source for data files.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    label_sig = file_signature(ref_labels_file)
    data_sig = file_signature(ref_data_file)
    combined_sig = f"{label_sig}|{data_sig}"
    if st.session_state.get("reference_memory_signature") != combined_sig:
        try:
            st.session_state["memory"] = rebuild_reference_memory(ref_labels_file, ref_data_file)
            st.session_state["reference_memory_signature"] = combined_sig
        except Exception as exc:
            st.error(f"Error building reference memory: {exc}")
            st.session_state["memory"] = TranslationMemory()

    memory: TranslationMemory = st.session_state.get("memory", TranslationMemory())
    labels_ok = ref_labels_file is not None
    data_ok = ref_data_file is not None
    total_entries = memory.data_file_entries + memory.label_file_entries

    status_html = f"""
<div class="status-row">
    <span class="status-pill {'ok' if labels_ok else 'warn'}">
        {'&#10003;' if labels_ok else '&#9675;'} Label references {'loaded' if labels_ok else 'not loaded'}
    </span>
    <span class="status-pill {'ok' if data_ok else 'warn'}">
        {'&#10003;' if data_ok else '&#9675;'} Data references {'loaded' if data_ok else 'not loaded'}
    </span>
</div>
<div class="memory-box">
    <div class="value">{total_entries:,}</div>
    <div class="label">Memory Entries</div>
</div>
"""
    st.markdown(status_html, unsafe_allow_html=True)
    return memory


def render_file_selection(use_bom: bool, provider: str, api_key: str) -> None:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="section-wrap">
    <h2>Select the File You Want to Translate</h2>
    <p>
        Choose whether you are translating a Qualtrics Label File or a Qualtrics Data File.
    </p>
</div>
""",
        unsafe_allow_html=True,
    )

    if "active_panel" not in st.session_state:
        st.session_state["active_panel"] = "label"

    selector_col_left, selector_col_mid, selector_col_right = st.columns([1, 2, 1])
    with selector_col_mid:
        left_btn_col, right_btn_col = st.columns(2, gap="medium")
        with left_btn_col:
            if st.button(
                "Label File",
                key="select_label_file",
                type="primary" if st.session_state["active_panel"] == "label" else "secondary",
                use_container_width=True,
            ):
                st.session_state["active_panel"] = "label"
                reset_result_for("label")
                st.rerun()
        with right_btn_col:
            if st.button(
                "Data File",
                key="select_data_file",
                type="primary" if st.session_state["active_panel"] == "data" else "secondary",
                use_container_width=True,
            ):
                st.session_state["active_panel"] = "data"
                reset_result_for("data")
                st.rerun()

    active = st.session_state["active_panel"]
    if active == "label":
        _render_translate_panel(
            panel_key="label",
            file_type=FileType.LABEL_FILE,
            source_col_override=None,
            source_display="EN",
            hint_html=(
                'Source from <code>EN</code> column &#10132; translated into '
                '<strong>FR</strong> and <strong>FR-CA</strong>'
            ),
            use_bom=use_bom,
            provider=provider,
            api_key=api_key,
        )
    elif active == "data":
        _render_translate_panel(
            panel_key="data",
            file_type=FileType.DATA_FILE,
            source_col_override="default value",
            source_display="default value",
            hint_html=(
                'Source from <code>default value</code> column &#10132; translated into '
                '<strong>FR</strong> and <strong>FR-CA</strong>'
            ),
            use_bom=use_bom,
            provider=provider,
            api_key=api_key,
        )


def _render_translate_panel(
    panel_key: str,
    file_type: FileType,
    source_col_override: Optional[str],
    source_display: str,
    hint_html: str,
    use_bom: bool,
    provider: str,
    api_key: str,
) -> None:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    # FIX #3: Use Unicode arrow &#10132; instead of any text-based icon
    st.markdown(
        f"""
<div class="panel-card">
    <p class="panel-hint">{hint_html}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="panel-card"><div class="uploader-wrap">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        f"Upload {panel_key} file to translate",
        type=["csv", "xlsx"],
        key=f"{panel_key}_main_file",
        label_visibility="collapsed",
        help=f"Upload the main {panel_key} file you want translated.",
    )
    st.markdown("</div></div>", unsafe_allow_html=True)
    if uploaded_file is None:
        return
    try:
        preview_df = load_file(io.BytesIO(uploaded_file.getvalue()), file_name=uploaded_file.name)
    except Exception as exc:
        st.error(f"Error loading file: {exc}")
        return
    all_cols = list(preview_df.columns)
    target_cols = [c for c in all_cols if c.strip().upper() in ("FR", "FR-CA")]
    st.markdown(
        f"""
<div class="stats-row">
    <div class="stat-card">
        <div class="value">{len(preview_df):,}</div>
        <div class="label">Rows</div>
    </div>
    <div class="stat-card">
        <div class="value">{len(all_cols)}</div>
        <div class="label">Columns</div>
    </div>
    <div class="stat-card">
        <div class="value">{source_display}</div>
        <div class="label">Source</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.expander("Preview first 8 rows"):
        st.dataframe(preview_df.head(8), use_container_width=True, hide_index=True)
    render_translation_controls(
        uploaded_file=uploaded_file,
        file_type=file_type,
        source_col_override=source_col_override,
        target_cols=target_cols,
        panel_key=panel_key,
        use_bom=use_bom,
        provider=provider,
        api_key=api_key,
    )


def render_translation_controls(
    uploaded_file,
    file_type: FileType,
    source_col_override: Optional[str],
    target_cols: list[str],
    panel_key: str,
    use_bom: bool,
    provider: str,
    api_key: str,
) -> None:
    st.markdown(
        """
<div class="section-wrap" style="margin-top:32px;">
    <h2>Run Translation</h2>
</div>
""",
        unsafe_allow_html=True,
    )
    translate_clicked = st.button(
        "Translate File",
        key=f"translate_button_{panel_key}",
        type="primary",
        use_container_width=True,
    )
    if translate_clicked:
        config = PipelineConfig(
            file_type_override=file_type,
            source_lang="EN",
            target_lang="FR-CA",
            target_columns=target_cols if target_cols else ["FR", "FR-CA"],
            source_column_override=source_col_override,
            use_bom=use_bom,
            provider=provider,
            api_key=api_key if api_key else None,
        )
        render_processing_ui(uploaded_file, config, panel_key)

    result_key = f"result_{panel_key}"
    if result_key not in st.session_state:
        return

    result: PipelineResult = st.session_state[result_key]
    if result.validation.passed:
        st.success("Validation passed. File structure and integrity were preserved.")
    else:
        st.error("Validation failed.")
        for issue in result.validation.issues:
            st.warning(issue)

    prov_counts: dict[str, int] = {}
    for item in result.translations:
        prov_counts[item.provenance.value] = prov_counts.get(item.provenance.value, 0) + 1
    ref_count = prov_counts.get("reference_exact_match", 0) + prov_counts.get("reference_normalized_match", 0)
    cache_count = prov_counts.get("session_cache", 0)
    fresh_count = prov_counts.get("fresh_translation", 0)
    skipped_count = sum(v for k, v in prov_counts.items() if "skipped" in k)

    st.markdown(
        f"""
<div class="prov-row">
    <div class="prov-card">
        <div class="value">{ref_count}</div>
        <div class="label">Reference</div>
    </div>
    <div class="prov-card">
        <div class="value">{cache_count}</div>
        <div class="label">Cache</div>
    </div>
    <div class="prov-card">
        <div class="value">{fresh_count}</div>
        <div class="label">Fresh</div>
    </div>
    <div class="prov-card">
        <div class="value">{skipped_count}</div>
        <div class="label">Skipped</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.expander("Translation Preview"):
        interesting = [
            t
            for t in result.translations
            if t.provenance
            not in (
                Provenance.SKIPPED_EMPTY,
                Provenance.SKIPPED_NUMERIC,
                Provenance.SKIPPED_INTERNAL,
                Provenance.SKIPPED_PROTECTED,
            )
        ][:40]
        if interesting:
            preview_rows = [
                {
                    "Row": t.row_index,
                    "Provenance": t.provenance.value.replace("_", " ").title(),
                    "Original": t.original[:80],
                    "Translated": t.translated[:80],
                }
                for t in interesting
            ]
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
    with st.expander("Diagnostics & Notes"):
        for k, v in sorted(result.diagnostics.items()):
            st.text(f"{k}: {v}")
        st.divider()
        st.dataframe(result.notes_df, use_container_width=True, hide_index=True)
    render_download_section(result, panel_key)


def render_processing_ui(uploaded_file, config: PipelineConfig, panel_key: str) -> None:
    status_box = st.empty()
    progress_box = st.empty()
    status_box.markdown(
        """
<div class="processing-card">
    <div class="title">Processing translation</div>
    <div class="sub">Loading files, building memory, translating content, and exporting the result.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    progress = progress_box.progress(0, text="Loading files...")

    def update_progress(step: str, pct: float) -> None:
        progress.progress(min(max(pct, 0.0), 1.0), text=step)

    try:
        result = run_pipeline(
            main_file=io.BytesIO(uploaded_file.getvalue()),
            main_filename=uploaded_file.name,
            config=config,
            memory=st.session_state.get("memory"),
            progress_callback=update_progress,
        )
        st.session_state[f"result_{panel_key}"] = result
        progress.progress(1.0, text="Exporting result...")
        progress_box.empty()
        status_box.empty()
    except Exception as exc:
        progress_box.empty()
        status_box.empty()
        st.error(f"Translation error: {exc}")


def render_download_section(result: PipelineResult, panel_key: str) -> None:
    st.markdown(
        f"""
<div class="done-area">
    <div class="done-arrow">{CURVED_ARROW_SVG}</div>
    <h3>Download Translated File</h3>
    <p>Your translated file is ready for Qualtrics import.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    dl_col_left, dl_col_mid, dl_col_right = st.columns([1, 2, 1])
    with dl_col_mid:
        st.download_button(
            label="Download Translated File",
            data=result.translated_csv_bytes,
            file_name=result.translated_filename,
            mime="text/csv",
            key=f"download_translated_{panel_key}",
            use_container_width=True,
        )
    with st.expander("Optional downloads and full output"):
        st.markdown('<div class="secondary-downloads">', unsafe_allow_html=True)
        st.download_button(
            label="Download Notes Report",
            data=result.notes_csv_bytes,
            file_name=result.notes_filename,
            mime="text/csv",
            key=f"download_notes_{panel_key}",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()
        st.dataframe(result.translated_df, use_container_width=True, hide_index=True)


def render_footer() -> None:
    st.markdown(
        """
<div class="app-footer">
    Qualtrics Dashboard Translator &middot; Powered by Argos Translate &middot; Free &amp; Offline
</div>
""",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════════
def main() -> None:
    inject_css()
    render_header()
    use_bom, provider, api_key = render_sidebar()
    render_reference_upload()
    render_file_selection(use_bom, provider, api_key)
    render_footer()


main()
