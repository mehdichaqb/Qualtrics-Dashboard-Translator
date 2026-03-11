"""
Qualtrics Dashboard Translator — Streamlit App

Government of Canada themed UI for translating Qualtrics survey/dashboard
CSV/XLSX files between English and French (Canada).
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
    page_title="Qualtrics Dashboard Translator",
    page_icon="🍁",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Canada Government Theme CSS ──────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Header bar */
    .gov-header {
        background: #26374A;
        padding: 16px 32px;
        border-bottom: 4px solid #AF3C43;
        margin: -1rem -1rem 2rem -1rem;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .gov-header h1 {
        color: #FFFFFF;
        font-size: 1.6rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.01em;
    }
    .gov-header .maple { font-size: 1.8rem; }
    .gov-subtitle {
        color: #CFD1D5;
        font-size: 0.9rem;
        margin-top: 2px;
    }

    /* Step cards */
    .step-card {
        background: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .step-number {
        display: inline-block;
        background: #26374A;
        color: white;
        width: 32px; height: 32px;
        border-radius: 50%;
        text-align: center;
        line-height: 32px;
        font-weight: 700;
        font-size: 0.9rem;
        margin-right: 12px;
    }
    .step-title {
        display: inline;
        font-size: 1.25rem;
        font-weight: 600;
        color: #1A1A1A;
    }
    .step-desc {
        color: #6C757D;
        font-size: 0.88rem;
        margin-top: 6px;
        margin-left: 44px;
        line-height: 1.5;
    }

    /* Reference badges */
    .ref-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #E8F5E9;
        color: #2E7D32;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 500;
    }
    .ref-badge.empty {
        background: #FFF3E0;
        color: #E65100;
    }

    /* Stat box */
    .stat-box {
        background: #F8F9FA;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        border: 1px solid #E0E0E0;
    }
    .stat-number {
        font-size: 1.8rem;
        font-weight: 700;
        color: #26374A;
    }
    .stat-label {
        color: #6C757D;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Download card */
    .download-card {
        background: linear-gradient(135deg, #26374A 0%, #1A2836 100%);
        border-radius: 12px;
        padding: 32px;
        text-align: center;
        margin-top: 16px;
    }
    .download-card h3 { color: #FFFFFF; margin-bottom: 8px; }
    .download-card p { color: #CFD1D5; font-size: 0.9rem; margin-bottom: 20px; }

    /* Success arrow */
    .success-arrow {
        font-size: 3rem;
        text-align: center;
        animation: bounce 1s ease infinite;
        margin: 12px 0;
    }
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-8px); }
    }

    /* Red accent buttons */
    .stButton > button[kind="primary"],
    .stDownloadButton > button {
        background-color: #AF3C43 !important;
        border-color: #AF3C43 !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        padding: 8px 24px !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button:hover {
        background-color: #8B2F35 !important;
        border-color: #8B2F35 !important;
        box-shadow: 0 2px 8px rgba(175, 60, 67, 0.3) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 0; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0 0;
        padding: 10px 24px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #AF3C43 !important;
        color: white !important;
    }

    /* Footer */
    .gov-footer {
        background: #26374A;
        color: #CFD1D5;
        padding: 16px 32px;
        margin: 3rem -1rem -1rem -1rem;
        text-align: center;
        font-size: 0.8rem;
        border-top: 4px solid #AF3C43;
    }

    header[data-testid="stHeader"] { background: #26374A; }
    section[data-testid="stSidebar"] { background: #F8F9FA; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="gov-header">
    <span class="maple">🍁</span>
    <div>
        <h1>Qualtrics Dashboard Translator</h1>
        <div class="gov-subtitle">English &harr; French (Canada) &mdash; Offline Translation Tool</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: Advanced Settings ───────────────────────────────────────────
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
            "Argos Translate - Offline (Recommended)",
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
    st.markdown(
        '<p style="color:#6C757D;font-size:0.78rem;">'
        'Token protection and HTML preservation are always enabled.'
        '</p>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════
#  STEP 1 — Reference Files
# ══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="step-card">
    <span class="step-number">1</span>
    <span class="step-title">Upload Your Reference Files</span>
    <div class="step-desc">
        Reference files teach the translator your approved terminology.
        Upload previously translated Qualtrics files so the app reuses
        known translations before generating new ones. These are
        <strong>optional</strong> but highly recommended for consistency.
    </div>
</div>
""", unsafe_allow_html=True)

ref_col1, ref_col2 = st.columns(2)

with ref_col1:
    st.markdown("**Reference Labels File**")
    st.caption("A previously translated data-translations file (has `default value` column)")
    ref_labels_file = st.file_uploader(
        "Upload reference labels file",
        type=["csv", "xlsx"],
        key="ref_labels",
        label_visibility="collapsed",
    )

with ref_col2:
    st.markdown("**Reference Data File**")
    st.caption("A previously translated dashboard-translations file (has `entityKey` column)")
    ref_data_file = st.file_uploader(
        "Upload reference data file",
        type=["csv", "xlsx"],
        key="ref_data",
        label_visibility="collapsed",
    )

# Build shared translation memory from reference files
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

# Memory status row
mem_col1, mem_col2, mem_col3 = st.columns(3)
with mem_col1:
    if st.session_state.get("ref_labels_loaded"):
        st.markdown('<div class="ref-badge">&#10003; Labels reference loaded</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ref-badge empty">&#9675; No labels reference</div>', unsafe_allow_html=True)
with mem_col2:
    if st.session_state.get("ref_data_loaded"):
        st.markdown('<div class="ref-badge">&#10003; Data reference loaded</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ref-badge empty">&#9675; No data reference</div>', unsafe_allow_html=True)
with mem_col3:
    total_entries = memory.data_file_entries + memory.label_file_entries
    st.markdown(
        f'<div class="stat-box">'
        f'<div class="stat-number">{total_entries:,}</div>'
        f'<div class="stat-label">Translation Memory Entries</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
#  STEP 2 — Upload & Translate Main File
# ══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="step-card">
    <span class="step-number">2</span>
    <span class="step-title">Translate a File</span>
    <div class="step-desc">
        Choose your file type below, then upload the file to translate.
        Translations are written into both the <strong>FR</strong>
        and <strong>FR-CA</strong> columns.
    </div>
</div>
""", unsafe_allow_html=True)

tab_labels, tab_data = st.tabs(["📋  Labels File", "📊  Data File"])


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

        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown(
                f'<div class="stat-box"><div class="stat-number">{len(preview_df):,}</div>'
                f'<div class="stat-label">Rows</div></div>',
                unsafe_allow_html=True,
            )
        with s2:
            st.markdown(
                f'<div class="stat-box"><div class="stat-number">{len(all_cols)}</div>'
                f'<div class="stat-label">Columns</div></div>',
                unsafe_allow_html=True,
            )
        with s3:
            src_display = source_col_override or "EN"
            st.markdown(
                f'<div class="stat-box"><div class="stat-number">{src_display}</div>'
                f'<div class="stat-label">Source Column</div></div>',
                unsafe_allow_html=True,
            )

        with st.expander("Preview first 8 rows", expanded=False):
            st.dataframe(preview_df.head(8), use_container_width=True)

    except Exception as e:
        st.error(f"Error loading file: {e}")
        return

    st.markdown("")
    if st.button("Translate Now", type="primary", use_container_width=True, key=f"translate_{tab_key}"):
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

        st.markdown('<div class="success-arrow">&#8595;</div>', unsafe_allow_html=True)

        if result.validation.passed:
            st.success("Structural validation passed — file integrity preserved")
        else:
            st.error("Structural validation failed")
            for issue in result.validation.issues:
                st.warning(issue)

        prov_counts: dict[str, int] = {}
        for t in result.translations:
            prov_counts[t.provenance.value] = prov_counts.get(t.provenance.value, 0) + 1

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ref_count = prov_counts.get("reference_exact_match", 0) + prov_counts.get("reference_normalized_match", 0)
            st.metric("From Reference", ref_count)
        with c2:
            st.metric("From Cache", prov_counts.get("session_cache", 0))
        with c3:
            st.metric("Fresh Translations", prov_counts.get("fresh_translation", 0))
        with c4:
            skipped = sum(v for k, v in prov_counts.items() if "skipped" in k)
            st.metric("Skipped", skipped)

        with st.expander("Translation Preview", expanded=False):
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
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        with st.expander("Diagnostics & Notes", expanded=False):
            for k, v in sorted(result.diagnostics.items()):
                st.text(f"{k}: {v}")
            st.divider()
            st.dataframe(result.notes_df, use_container_width=True, hide_index=True)

        # Download section
        st.markdown(
            '<div class="download-card">'
            '<h3>&#x2713; Translation Complete</h3>'
            '<p>Your file is ready for Qualtrics import.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

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
                label="Download Translation Notes",
                data=result.notes_csv_bytes,
                file_name=result.notes_filename,
                mime="text/csv",
                use_container_width=True,
                key=f"dl_notes_{tab_key}",
            )

        with st.expander("View full translated file", expanded=False):
            st.dataframe(result.translated_df, use_container_width=True)


# ── Labels File Tab ──────────────────────────────────────────────────────
with tab_labels:
    st.markdown(
        '<p style="color:#6C757D;margin-bottom:4px;">'
        'Upload a <strong>dashboard data translations</strong> file. '
        'Source text is read from the <code>default value</code> column. '
        'Translations go into both <strong>FR</strong> and <strong>FR-CA</strong>.'
        '</p>',
        unsafe_allow_html=True,
    )
    labels_upload = st.file_uploader(
        "Upload Labels File (.csv / .xlsx)",
        type=["csv", "xlsx"],
        key="labels_main",
        label_visibility="collapsed",
    )
    _run_translation(labels_upload, FileType.DATA_FILE, "default value", "labels")


# ── Data File Tab ────────────────────────────────────────────────────────
with tab_data:
    st.markdown(
        '<p style="color:#6C757D;margin-bottom:4px;">'
        'Upload a <strong>dashboard translations</strong> file. '
        'Source text is read from the <code>EN</code> column. '
        'Translations go into both <strong>FR</strong> and <strong>FR-CA</strong>.'
        '</p>',
        unsafe_allow_html=True,
    )
    data_upload = st.file_uploader(
        "Upload Data File (.csv / .xlsx)",
        type=["csv", "xlsx"],
        key="data_main",
        label_visibility="collapsed",
    )
    _run_translation(data_upload, FileType.LABEL_FILE, None, "data")


# ── Footer ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="gov-footer">
    Qualtrics Dashboard Translator &mdash; Offline Translation Tool
    &bull; Built with Streamlit &amp; Argos Translate
</div>
""", unsafe_allow_html=True)
