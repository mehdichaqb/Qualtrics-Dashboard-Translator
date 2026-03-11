"""
Qualtrics Dashboard Translator — Streamlit App

A local app for translating Qualtrics survey/dashboard CSV/XLSX files
between English and French (Canada), with optional reference-file
translation memory support.
"""

from __future__ import annotations

import io
import os
from typing import Optional, Tuple, Union

import pandas as pd
import streamlit as st

from processor.classifier import CellType
from processor.detector import FileType, detect_file_type, find_locale_columns
from processor.file_loader import load_file
from processor.pipeline import PipelineConfig, PipelineResult, run_pipeline
from processor.rules import Provenance

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Qualtrics Dashboard Translator",
    page_icon="🌐",
    layout="wide",
)

st.title("Qualtrics Dashboard Translator")
st.markdown(
    "Translate Qualtrics survey/dashboard files between "
    "**English** and **French (Canada)** with optional reference-file "
    "translation memory."
)

# ── Sidebar: Settings ────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    direction = st.selectbox(
        "Translation Direction",
        options=["English → French (Canada)", "French (Canada) → English"],
        index=0,
    )
    if direction == "English → French (Canada)":
        source_lang, target_lang = "EN", "FR-CA"
    else:
        source_lang, target_lang = "FR-CA", "EN"

    file_type_choice = st.selectbox(
        "File Type Detection",
        options=["Auto Detect", "Data File", "Label File"],
        index=0,
    )
    file_type_override: Optional[FileType] = None
    if file_type_choice == "Data File":
        file_type_override = FileType.DATA_FILE
    elif file_type_choice == "Label File":
        file_type_override = FileType.LABEL_FILE

    st.divider()

    encoding_choice = st.selectbox(
        "Export Encoding",
        options=["UTF-8 with BOM (recommended)", "UTF-8"],
        index=0,
    )
    use_bom = "BOM" in encoding_choice

    st.divider()

    st.markdown("**Protection (always on)**")
    st.checkbox("Preserve HTML tags", value=True, disabled=True)
    st.checkbox("Protect Qualtrics tokens", value=True, disabled=True)

    st.divider()

    st.subheader("Translation Provider")
    provider_choice = st.selectbox(
        "Provider",
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
            "Anthropic API Key (or set ANTHROPIC_API_KEY env var)",
            type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
        )

# ── Main: File Uploaders ─────────────────────────────────────────────────
st.header("1. Upload Files")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Main File (required)")
    main_file = st.file_uploader(
        "Upload CSV or XLSX",
        type=["csv", "xlsx"],
        key="main_file",
    )

with col2:
    st.subheader("Reference Data File")
    ref_data = st.file_uploader(
        "Optional data-file reference",
        type=["csv", "xlsx"],
        key="ref_data",
    )

with col3:
    st.subheader("Reference Label File")
    ref_label = st.file_uploader(
        "Optional label-file reference",
        type=["csv", "xlsx"],
        key="ref_label",
    )

# ── Preview uploaded file ────────────────────────────────────────────────
if main_file is not None:
    st.header("2. File Preview & Detection")

    try:
        preview_bytes = main_file.read()
        main_file.seek(0)  # rewind for pipeline
        preview_df = load_file(io.BytesIO(preview_bytes), file_name=main_file.name)

        detected_type = detect_file_type(preview_df)
        effective_type = file_type_override or detected_type

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Rows", len(preview_df))
        with col_b:
            st.metric("Columns", len(preview_df.columns))
        with col_c:
            badge_color = "normal" if detected_type != FileType.UNKNOWN else "off"
            st.metric("Detected Type", effective_type.value.replace("_", " ").title())

        locale_cols = find_locale_columns(preview_df)
        if locale_cols:
            st.info(f"**Locale columns found:** {', '.join(locale_cols[:20])}{'...' if len(locale_cols) > 20 else ''}")

        with st.expander("Preview first 10 rows", expanded=False):
            st.dataframe(preview_df.head(10), use_container_width=True)

    except Exception as e:
        st.error(f"Error loading file: {e}")

# ── Translate Button ─────────────────────────────────────────────────────
if main_file is not None:
    st.header("3. Translate")

    if st.button("Start Translation", type="primary", use_container_width=True):
        config = PipelineConfig(
            file_type_override=file_type_override,
            source_lang=source_lang,
            target_lang=target_lang,
            use_bom=use_bom,
            provider=provider,
            api_key=api_key if api_key else None,
        )

        # Prepare reference files
        ref_data_tuple = None
        ref_label_tuple = None
        if ref_data:
            ref_data_bytes = ref_data.read()
            ref_data.seek(0)
            ref_data_tuple = (io.BytesIO(ref_data_bytes), ref_data.name)
        if ref_label:
            ref_label_bytes = ref_label.read()
            ref_label.seek(0)
            ref_label_tuple = (io.BytesIO(ref_label_bytes), ref_label.name)

        # Run pipeline
        progress_bar = st.progress(0, text="Starting...")

        def update_progress(step: str, pct: float) -> None:
            progress_bar.progress(min(pct, 1.0), text=step)

        try:
            main_file.seek(0)
            result = run_pipeline(
                main_file=io.BytesIO(main_file.read()),
                main_filename=main_file.name,
                config=config,
                ref_data_file=ref_data_tuple,
                ref_label_file=ref_label_tuple,
                progress_callback=update_progress,
            )

            st.session_state["result"] = result
            st.success("Translation complete!")

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            import traceback
            st.code(traceback.format_exc())

# ── Results Section ──────────────────────────────────────────────────────
if "result" in st.session_state:
    result: PipelineResult = st.session_state["result"]

    st.header("4. Results")

    # Validation status
    if result.validation.passed:
        st.success("Structural validation PASSED")
    else:
        st.error("Structural validation FAILED")
        for issue in result.validation.issues:
            st.warning(issue)

    # ── Provenance Summary ───────────────────────────────────────────
    st.subheader("Translation Provenance Summary")
    prov_counts: dict[str, int] = {}
    for t in result.translations:
        key = t.provenance.value
        prov_counts[key] = prov_counts.get(key, 0) + 1

    prov_df = pd.DataFrame(
        [{"Provenance": k, "Count": v} for k, v in sorted(prov_counts.items())]
    )
    st.dataframe(prov_df, use_container_width=True, hide_index=True)

    # ── Diagnostics ──────────────────────────────────────────────────
    with st.expander("Diagnostics", expanded=False):
        for k, v in sorted(result.diagnostics.items()):
            st.text(f"{k}: {v}")

    # ── Preview Translations ─────────────────────────────────────────
    st.subheader("Translation Preview (sample)")

    # Show interesting translations (non-empty, non-skipped)
    interesting = [
        t for t in result.translations
        if t.provenance not in (
            Provenance.SKIPPED_EMPTY,
            Provenance.SKIPPED_NUMERIC,
            Provenance.SKIPPED_INTERNAL,
            Provenance.SKIPPED_PROTECTED,
        )
    ][:50]  # Cap at 50

    if interesting:
        preview_rows = []
        for t in interesting:
            preview_rows.append({
                "Row": t.row_index,
                "Provenance": t.provenance.value,
                "Original": t.original[:80],
                "Translated": t.translated[:80],
                "Notes": "; ".join(t.notes) if t.notes else "",
            })

        st.dataframe(
            pd.DataFrame(preview_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No translatable cells found.")

    # ── Conflict Report ──────────────────────────────────────────────
    if "result" in st.session_state:
        # We'd need access to the memory for conflicts
        # For now, show from diagnostics
        if int(result.diagnostics.get("memory_conflicts", "0")) > 0:
            st.warning(
                f"Found {result.diagnostics['memory_conflicts']} conflicting "
                f"translations in reference files. See notes report."
            )

    # ── Notes / Flags ────────────────────────────────────────────────
    st.subheader("Notes & Flags")
    with st.expander("View notes report", expanded=False):
        st.dataframe(result.notes_df, use_container_width=True, hide_index=True)

    # ── Download Buttons ─────────────────────────────────────────────
    st.header("5. Download")

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.download_button(
            label=f"Download Translated CSV",
            data=result.translated_csv_bytes,
            file_name=result.translated_filename,
            mime="text/csv",
            use_container_width=True,
        )

    with col_d2:
        st.download_button(
            label=f"Download Translation Notes",
            data=result.notes_csv_bytes,
            file_name=result.notes_filename,
            mime="text/csv",
            use_container_width=True,
        )

    # ── Full translated DataFrame ────────────────────────────────────
    with st.expander("View full translated file", expanded=False):
        st.dataframe(result.translated_df, use_container_width=True)
