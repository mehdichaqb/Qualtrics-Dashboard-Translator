"""
Qualtrics Dashboard Translator — Streamlit App
==============================================
Persistent file stores + glossary, simultaneous label+data translation,
multi-file results with ZIP download.
"""
from __future__ import annotations
import hashlib
import io
import os
import zipfile
from typing import Optional

import pandas as pd
import streamlit as st

from processor.detector import FileType
from processor.file_loader import load_file
from processor.pipeline import PipelineConfig, PipelineResult, run_pipeline
from processor.reference_memory import TranslationMemory, build_memory_from_reference
from processor.rules import Provenance

st.set_page_config(
    page_title="Qualtrics Dashboard Translator",
    page_icon="\U0001f341",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAPLE_LEAF_SVG = """<svg width="28" height="28" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path fill="#D52B1E" d="M31.9 6l4.2 10.6 7-3.6-1.8 8.2 9-1.3-5.9 7.1 8.8 2.7-8 4.5 5 8-9-2.3.8 9.2-9.2-7.6-9.2 7.6.8-9.2-9 2.3 5-8-8-4.5 8.8-2.7-5.9-7.1 9 1.3-1.8-8.2 7 3.6z"/></svg>"""
CURVED_ARROW_SVG = """<svg width="88" height="56" viewBox="0 0 88 56" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M8 10 C 28 10, 26 40, 56 40 L 70 40" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/><path d="M62 32 L 74 40 L 62 48" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

REF_LABELS_KEY = "ref_labels_store"
REF_DATA_KEY   = "ref_data_store"
TX_LABELS_KEY  = "tx_labels_store"
TX_DATA_KEY    = "tx_data_store"
ALL_STORES     = [REF_LABELS_KEY, REF_DATA_KEY, TX_LABELS_KEY, TX_DATA_KEY]
GEN_KEYS       = {
    REF_LABELS_KEY: "gen_ref_labels",
    REF_DATA_KEY:   "gen_ref_data",
    TX_LABELS_KEY:  "gen_tx_labels",
    TX_DATA_KEY:    "gen_tx_data",
}

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
    --bg:#FFFFFF;--bg-soft:#F7F7F7;--bg-elevated:#F0F0F0;--bg-hover:#E8E8E8;
    --text:#111111;--text-sub:#333333;--text-dim:#6B7280;
    --border:#D9D9D9;--border-accent:rgba(28,61,90,0.18);
    --red:#D52B1E;--red-hover:#B82219;--red-soft:rgba(213,43,30,0.08);--red-glow:rgba(213,43,30,0.20);
    --blue:#1C3D5A;--blue-soft:rgba(28,61,90,0.10);
    --green:#1A7742;--green-soft:rgba(26,119,66,0.10);
    --amber:#B56F00;--amber-soft:rgba(181,111,0,0.10);
    --shadow-sm:0 1px 3px rgba(0,0,0,0.06);--shadow-md:0 8px 24px rgba(0,0,0,0.08);
    --transition:150ms ease;--divider-color:#D9D9D9;
}
@media (prefers-color-scheme:dark){:root{
    --bg:#1A1A1A;--bg-soft:#1C2E4A;--bg-elevated:#223754;--bg-hover:#2A4060;
    --text:#F3F4F6;--text-sub:#D1D5DB;--text-dim:#9CA3AF;
    --border:#2D4A6A;--border-accent:rgba(96,165,250,0.20);
    --red:#EF4444;--red-hover:#DC2626;--red-soft:rgba(239,68,68,0.14);--red-glow:rgba(239,68,68,0.28);
    --blue:#60A5FA;--blue-soft:rgba(96,165,250,0.16);
    --green:#34D399;--green-soft:rgba(52,211,153,0.14);
    --amber:#FBBF24;--amber-soft:rgba(251,191,36,0.14);
    --shadow-sm:0 1px 3px rgba(0,0,0,0.40);--shadow-md:0 10px 28px rgba(0,0,0,0.45);
    --divider-color:#2D4A6A;
}}
.stApp[data-theme="dark"],[data-theme="dark"],
[data-testid="stAppViewContainer"][style*="background-color: rgb(14"],
[data-testid="stAppViewContainer"][style*="background-color: rgb(0"]{
    --bg:#1A1A1A;--bg-soft:#1C2E4A;--bg-elevated:#223754;--bg-hover:#2A4060;
    --text:#F3F4F6;--text-sub:#D1D5DB;--text-dim:#9CA3AF;
    --border:#2D4A6A;--border-accent:rgba(96,165,250,0.20);
    --red:#EF4444;--red-hover:#DC2626;--red-soft:rgba(239,68,68,0.14);--red-glow:rgba(239,68,68,0.28);
    --blue:#60A5FA;--blue-soft:rgba(96,165,250,0.16);
    --green:#34D399;--green-soft:rgba(52,211,153,0.14);
    --amber:#FBBF24;--amber-soft:rgba(251,191,36,0.14);
    --shadow-sm:0 1px 3px rgba(0,0,0,0.40);--shadow-md:0 10px 28px rgba(0,0,0,0.45);
    --divider-color:#2D4A6A;
}
html,body,.stApp,[data-testid="stAppViewContainer"],.stMarkdown,div,p,span,label,button,h1,h2,h3{
    font-family:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif !important;}
.stApp{color:var(--text);font-size:15px;line-height:1.5;}
header[data-testid="stHeader"]{background:transparent !important;}
[data-testid="stToolbar"],[data-testid="stDecoration"],.stDeployButton,#MainMenu{display:none !important;}
[data-testid="stMainBlockContainer"],.block-container{
    max-width:1100px !important;padding-top:1.2rem !important;
    padding-left:2rem !important;padding-right:2rem !important;}
[data-testid="stFileUploader"]>label{display:none !important;}
.app-header{text-align:center;padding-top:32px;}
.app-header .leaf{display:inline-flex;align-items:center;justify-content:center;
    width:56px;height:56px;border-radius:50%;background:var(--red-soft);
    border:2px solid rgba(213,43,30,0.15);box-shadow:var(--shadow-sm);margin-bottom:16px;}
.app-header h1{margin:0;color:var(--text) !important;font-size:76px;font-weight:800;line-height:1.04;letter-spacing:-0.04em;}
.app-header p{margin:14px 0 32px 0;color:var(--text-sub) !important;font-size:18px;}
.app-divider{width:100%;max-width:800px;height:2px;
    background:linear-gradient(90deg,transparent,var(--red) 30%,var(--red) 70%,transparent);
    opacity:0.2;border:0;margin:0 auto;}
.section-wrap{margin-top:56px;text-align:center;width:100%;}
.section-wrap h2{margin:0 0 8px 0;font-size:24px;font-weight:600;color:var(--text) !important;}
.section-wrap p{margin:0 auto 28px auto;max-width:660px;font-size:15px;
    color:var(--text-dim) !important;text-align:center;display:block;width:100%;}
.section-divider{width:100%;max-width:800px;height:1px;background:var(--divider-color);border:0;margin:56px auto 0 auto;}
.ref-caption{text-align:center;margin-bottom:12px;}
.ref-caption .title{font-size:20px;font-weight:600;color:var(--text) !important;margin-bottom:4px;}
.ref-caption .drag{font-size:15px;color:var(--text-sub) !important;margin-bottom:4px;}
.ref-caption .detail{font-size:13px;color:var(--text-dim) !important;line-height:1.4;}
.uploader-wrap{margin-top:8px;}
.uploader-wrap [data-testid="stFileUploader"] section{
    min-height:140px !important;background:var(--bg-soft) !important;
    border:2px dashed var(--border-accent) !important;border-radius:16px !important;
    padding:18px 20px !important;transition:border-color var(--transition),box-shadow var(--transition) !important;}
.uploader-wrap [data-testid="stFileUploader"] section:hover{
    border-color:var(--blue) !important;box-shadow:var(--shadow-md) !important;}
.uploader-wrap [data-testid="stFileUploader"] small{
    display:block !important;text-align:center !important;color:var(--text-dim) !important;font-size:12px !important;}
.uploader-wrap [data-testid="stFileUploader"] button{
    border-radius:999px !important;border:1px solid var(--border) !important;
    background:var(--bg-elevated) !important;color:var(--text) !important;
    font-size:13px !important;font-weight:600 !important;padding:8px 22px !important;}
.uploader-wrap [data-testid="stFileUploader"] button:hover{
    border-color:var(--blue) !important;background:var(--blue-soft) !important;color:var(--blue) !important;}
.uploader-wrap [data-testid="stFileUploader"] section div,
.uploader-wrap [data-testid="stFileUploader"] section span,
.uploader-wrap [data-testid="stFileUploader"] section p{color:var(--text-dim) !important;}
.stored-file-row{display:flex;align-items:center;gap:8px;padding:5px 10px;
    border-radius:8px;background:var(--bg-soft);border:1px solid var(--border);margin-bottom:5px;}
.stored-file-row .sf-name{flex:1;font-size:13px;color:var(--text-sub) !important;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.remove-btn>div>button,.remove-btn button{
    min-height:26px !important;height:26px !important;padding:0 8px !important;
    font-size:12px !important;border-radius:6px !important;margin:0 !important;
    background:transparent !important;border:1px solid var(--border) !important;
    color:var(--text-dim) !important;line-height:1 !important;box-shadow:none !important;transform:none !important;}
.remove-btn>div>button:hover,.remove-btn button:hover{
    border-color:var(--red) !important;color:var(--red) !important;
    background:var(--red-soft) !important;transform:none !important;}
.status-row{display:flex;justify-content:center;align-items:center;gap:14px;flex-wrap:wrap;margin-top:24px;}
.status-pill{display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:999px;font-size:14px;font-weight:600;}
.status-pill.ok{background:var(--green-soft);color:var(--green);}
.status-pill.warn{background:var(--amber-soft);color:var(--amber);}
.memory-box{margin:20px auto 0 auto;max-width:220px;text-align:center;background:var(--bg-soft);
    border:1px solid var(--border-accent);border-radius:14px;padding:20px;box-shadow:var(--shadow-sm);}
.memory-box .value{font-size:36px;font-weight:700;color:var(--red);line-height:1;}
.memory-box .label{margin-top:5px;font-size:13px;font-weight:500;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-dim) !important;}
.glossary-card{background:var(--bg-soft);border:1px solid var(--border-accent);
    border-radius:16px;padding:24px 28px;margin-top:24px;}
.glossary-note{font-size:13px;color:var(--text-dim) !important;margin-top:10px;text-align:center;}
.stButton>button{min-height:58px !important;border-radius:24px !important;font-size:16px !important;
    font-weight:600 !important;padding:16px 34px !important;transition:all var(--transition) !important;
    display:flex !important;justify-content:center !important;align-items:center !important;margin:0 auto !important;}
.stButton>button[kind="primary"]{background:var(--red) !important;border:0 !important;
    color:#FFFFFF !important;box-shadow:0 4px 20px var(--red-glow) !important;}
.stButton>button[kind="primary"]:hover{background:var(--red-hover) !important;
    transform:scale(1.03) !important;box-shadow:0 8px 24px var(--red-glow) !important;}
.stButton>button[kind="secondary"]{background:var(--bg-soft) !important;
    color:var(--text) !important;border:2px solid var(--border) !important;}
.stButton>button[kind="secondary"]:hover{border-color:var(--blue) !important;
    background:var(--blue-soft) !important;color:var(--blue) !important;transform:scale(1.03) !important;}
.stDownloadButton>button{min-height:58px !important;border-radius:24px !important;font-size:16px !important;
    font-weight:600 !important;padding:16px 34px !important;background:var(--red) !important;
    color:#FFFFFF !important;border:0 !important;box-shadow:0 4px 20px var(--red-glow) !important;
    transition:all var(--transition) !important;display:flex !important;
    justify-content:center !important;align-items:center !important;margin:0 auto !important;}
.stDownloadButton>button:hover{background:var(--red-hover) !important;
    transform:scale(1.03) !important;box-shadow:0 8px 24px var(--red-glow) !important;}
.stat-card{flex:1;min-width:140px;background:var(--bg-soft);border:1px solid var(--border-accent);
    border-radius:14px;padding:18px 14px;text-align:center;}
.stats-row{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;margin:22px auto 0 auto;max-width:560px;}
.stat-card .value{font-size:22px;font-weight:700;color:var(--text) !important;line-height:1;}
.stat-card .label{margin-top:5px;font-size:12px;color:var(--text-dim) !important;
    text-transform:uppercase;letter-spacing:0.05em;font-weight:500;}
.file-result-header{display:flex;align-items:center;gap:10px;margin:32px 0 10px 0;
    padding-bottom:10px;border-bottom:1px solid var(--border);}
.file-result-header .idx{display:inline-flex;align-items:center;justify-content:center;
    width:26px;height:26px;border-radius:50%;background:var(--red-soft);color:var(--red);
    font-size:12px;font-weight:700;flex-shrink:0;}
.file-result-header .fname{font-size:15px;font-weight:600;color:var(--text) !important;word-break:break-all;}
.file-result-header .ftype{font-size:12px;font-weight:500;color:var(--text-dim) !important;
    background:var(--bg-elevated);border-radius:6px;padding:2px 8px;flex-shrink:0;}
.processing-card{max-width:720px;margin:24px auto 0 auto;background:var(--bg-soft);
    border:1px solid var(--border);border-radius:16px;padding:24px 24px 18px 24px;text-align:center;}
.processing-card .title{font-size:20px;font-weight:600;color:var(--text) !important;margin-bottom:4px;}
.processing-card .sub{font-size:14px;color:var(--text-dim) !important;margin-bottom:18px;}
.prov-row{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:24px auto;max-width:700px;}
.prov-card{flex:1;min-width:125px;background:var(--bg-soft);border:1px solid var(--border-accent);
    border-radius:14px;padding:16px 12px;text-align:center;}
.prov-card .value{font-size:22px;font-weight:700;color:var(--text) !important;}
.prov-card .label{margin-top:4px;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;
    color:var(--text-dim) !important;font-weight:500;}
.done-area{text-align:center;margin:34px auto 0 auto;max-width:620px;}
.done-area .done-arrow{color:var(--red);display:inline-flex;margin-bottom:6px;
    animation:floatArrow 1.5s ease-in-out infinite;}
@keyframes floatArrow{0%,100%{transform:translateY(0);}50%{transform:translateY(-6px);}}
.done-area h3{margin:0 0 6px 0;color:var(--text) !important;font-size:22px;font-weight:700;}
.done-area p{margin:0 0 20px 0;color:var(--text-dim) !important;font-size:15px;}
.secondary-downloads{max-width:420px;margin:18px auto 0 auto;}
.stProgress>div>div>div>div{background:var(--red) !important;border-radius:999px !important;}
.stSuccess,.stError,.stWarning,.stInfo{border-radius:14px !important;}
details{border-radius:14px !important;}
.streamlit-expanderHeader{font-size:15px !important;font-weight:600 !important;}
.app-footer{text-align:center;font-size:13px;color:var(--text-dim) !important;padding:56px 0 24px 0;}
section[data-testid="stSidebar"]{background:var(--bg-soft) !important;}
section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] p{color:var(--text) !important;}
@media (prefers-color-scheme:dark){
    .app-header h1,.section-wrap h2,.ref-caption .title,.stat-card .value,
    .prov-card .value,.processing-card .title,.done-area h3,.file-result-header .fname{color:#F3F4F6 !important;}
    .app-header p,.ref-caption .drag,.section-wrap p,.ref-caption .detail,
    .stat-card .label,.prov-card .label,.processing-card .sub,
    .done-area p,.app-footer,.stored-file-row .sf-name{color:#9CA3AF !important;}
    .stApp,[data-testid="stAppViewContainer"]{background-color:#1A1A1A !important;}
}
</style>
"""

# ---------------------------------------------------------------------------
# FILE STORE HELPERS
# ---------------------------------------------------------------------------
def _sig(name: str, data: bytes) -> str:
    return hashlib.sha256(name.encode() + data).hexdigest()[:12]

def init_stores() -> None:
    for key in ALL_STORES:
        if key not in st.session_state:
            st.session_state[key] = []
    for gk in GEN_KEYS.values():
        if gk not in st.session_state:
            st.session_state[gk] = 0
    if "glossary" not in st.session_state:
        st.session_state["glossary"] = [
            {"EN": "BDM",                             "FR-CA": "MVP",                                           "Note": "Benefits Delivery Modernization acronym"},
            {"EN": "OAS",                             "FR-CA": "SV",                                            "Note": "Old Age Security acronym"},
            {"EN": "EI",                              "FR-CA": "AE",                                            "Note": "Employment Insurance acronym"},
            {"EN": "Benefits Delivery Modernization", "FR-CA": "Modernisation du versement des prestations",    "Note": "Full program name"},
            {"EN": "survey",                          "FR-CA": "sondage",                                       "Note": ""},
            {"EN": "onboarding",                      "FR-CA": "intégration",                                   "Note": ""},
            {"EN": "",                                "FR-CA": "",                                               "Note": ""},
        ]

def sync_to_store(store_key: str, uploaded_files) -> bool:
    if not uploaded_files:
        return False
    store = st.session_state[store_key]
    existing = {f["sig"] for f in store}
    added = False
    for uf in uploaded_files:
        data = uf.getvalue()
        sig = _sig(uf.name, data)
        if sig not in existing:
            store.append({"name": uf.name, "data": data, "sig": sig})
            existing.add(sig)
            added = True
    if added:
        st.session_state[store_key] = store
        st.session_state[GEN_KEYS[store_key]] += 1
    return added

def remove_file(store_key: str, sig: str) -> None:
    st.session_state[store_key] = [f for f in st.session_state[store_key] if f["sig"] != sig]
    st.session_state.pop(f"result_{sig}", None)
    if store_key in (REF_LABELS_KEY, REF_DATA_KEY):
        st.session_state.pop("memory_sig", None)

def _glossary_sig() -> str:
    rows = st.session_state.get("glossary", [])
    key = "|".join(f"{r.get("EN","")}:{r.get("FR-CA","")}" for r in rows if r.get("EN","").strip())
    return hashlib.md5(key.encode()).hexdigest()[:8]

def _memory_sig() -> str:
    parts = [f["sig"] for f in st.session_state.get(REF_LABELS_KEY, [])]
    parts += [f["sig"] for f in st.session_state.get(REF_DATA_KEY, [])]
    parts.append(_glossary_sig())
    return "|".join(sorted(parts)) or "empty"

def get_or_build_memory() -> TranslationMemory:
    sig = _memory_sig()
    if st.session_state.get("memory_sig") != sig:
        memory = TranslationMemory()
        # 1. Glossary entries first (highest priority — injected as exact matches)
        rows = st.session_state.get("glossary", [])
        valid_rows = [r for r in rows if r.get("EN","").strip() and r.get("FR-CA","").strip()]
        if valid_rows:
            gloss_df = pd.DataFrame(valid_rows)[["EN","FR-CA"]].rename(columns={"FR-CA":"FR-CA"})
            try:
                build_memory_from_reference(gloss_df, memory, "EN", "FR-CA")
                # also load as FR so FR column is populated
                gloss_fr_df = gloss_df.rename(columns={"FR-CA":"FR"})
                gloss_fr_df["EN"] = gloss_df["EN"]
                build_memory_from_reference(gloss_fr_df, memory, "EN", "FR")
            except Exception:
                pass
        # 2. Reference files
        for store_key in (REF_LABELS_KEY, REF_DATA_KEY):
            for item in st.session_state.get(store_key, []):
                try:
                    df = load_file(io.BytesIO(item["data"]), file_name=item["name"])
                    build_memory_from_reference(df, memory, "EN", "FR-CA")
                    build_memory_from_reference(df, memory, "EN", "FR")
                except Exception:
                    pass
        st.session_state["memory"] = memory
        st.session_state["memory_sig"] = sig
    return st.session_state["memory"]

# ---------------------------------------------------------------------------
# RENDER HELPERS
# ---------------------------------------------------------------------------
def render_stored_files(store_key: str) -> None:
    store = st.session_state.get(store_key, [])
    if not store:
        return
    for item in list(store):
        col_name, col_btn = st.columns([14, 1])
        with col_name:
            st.markdown(
                f'<div class="stored-file-row">'                f'<span style="font-size:13px;flex-shrink:0">\U0001f4c4</span>'                f'<span class="sf-name">{item["name"]}</span></div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            st.markdown('<div class="remove-btn">', unsafe_allow_html=True)
            if st.button("\u2715", key=f"rm_{item['sig']}", help=f"Remove {item['name']}"):
                remove_file(store_key, item["sig"])
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

def _uploader(label: str, store_key: str, caption_html: str):
    st.markdown(caption_html, unsafe_allow_html=True)
    st.markdown('<div class="uploader-wrap">', unsafe_allow_html=True)
    files = st.file_uploader(
        label, type=["csv","xlsx"],
        key=f"ul_{store_key}_{st.session_state[GEN_KEYS[store_key]]}",
        label_visibility="collapsed",
        accept_multiple_files=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return files or []

# ---------------------------------------------------------------------------
# RENDERERS
# ---------------------------------------------------------------------------
def render_header() -> None:
    st.markdown(f'''
<div class="app-header">
    <div class="leaf">{MAPLE_LEAF_SVG}</div>
    <h1>Qualtrics Dashboard<br>Translator</h1>
    <p>Translate Qualtrics Data and Label files between English and French (Canada)</p>
    <div class="app-divider"></div>
</div>
''', unsafe_allow_html=True)

def render_sidebar() -> tuple[bool, str, str]:
    # Resolve API key from secrets → env → empty
    _secret_key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else ""
    _env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    _default_key = _secret_key or _env_key

    with st.sidebar:
        st.markdown("### Advanced Settings")
        encoding_choice = st.selectbox("Export Encoding",
            options=["UTF-8 with BOM (recommended)","UTF-8"], index=0)
        use_bom = "BOM" in encoding_choice
        st.divider()
        # Default to Claude if a key is available, otherwise offline
        _default_engine_idx = 1 if _default_key else 0
        provider_choice = st.selectbox("Translation Engine", options=[
            "Argos Translate \u2014 Offline",
            "Claude (Anthropic API)", "Mock (for testing)"],
            index=_default_engine_idx)
        provider = ("argos" if "Argos" in provider_choice
                    else "anthropic" if "Claude" in provider_choice else "mock")
        api_key = ""
        if provider == "anthropic":
            api_key = st.text_input("Anthropic API Key", type="password",
                                    value=_default_key,
                                    help="Pre-loaded from secrets. Change only if needed.")
        st.divider()
        st.caption("Token protection and HTML preservation are always enabled.")
    return use_bom, provider, api_key

def render_reference_upload() -> None:
    st.markdown('''
<div class="section-wrap">
    <h2>Upload Your Reference Files</h2>
    <p>Reference files seed the translation memory. Files stay loaded until you remove them.</p>
</div>
''', unsafe_allow_html=True)
    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        new_lbl = _uploader("Reference label files", REF_LABELS_KEY, '''
<div class="ref-caption">
    <div class="title">Reference Label Files</div>
    <div class="drag">Drag and drop files here</div>
    <div class="detail">Previously translated label files (EN / FR / FR-CA)</div>
</div>''')
        render_stored_files(REF_LABELS_KEY)
    with col_right:
        new_dat = _uploader("Reference data files", REF_DATA_KEY, '''
<div class="ref-caption">
    <div class="title">Reference Data Files</div>
    <div class="drag">Drag and drop files here</div>
    <div class="detail">Previously translated data files (default value / FR / FR-CA)</div>
</div>''')
        render_stored_files(REF_DATA_KEY)
    added = sync_to_store(REF_LABELS_KEY, new_lbl)
    added |= sync_to_store(REF_DATA_KEY, new_dat)
    if added:
        st.rerun()
    n_lbl = len(st.session_state.get(REF_LABELS_KEY, []))
    n_dat = len(st.session_state.get(REF_DATA_KEY, []))
    memory = get_or_build_memory()
    total_entries = memory.data_file_entries + memory.label_file_entries
    lbl_text = f"{n_lbl} file{'s' if n_lbl!=1 else ''} loaded" if n_lbl else "not loaded"
    dat_text = f"{n_dat} file{'s' if n_dat!=1 else ''} loaded" if n_dat else "not loaded"
    st.markdown(f'''
<div class="status-row">
    <span class="status-pill {'ok' if n_lbl else 'warn'}">{'&#10003;' if n_lbl else '&#9675;'} Labels \u2014 {lbl_text}</span>
    <span class="status-pill {'ok' if n_dat else 'warn'}">{'&#10003;' if n_dat else '&#9675;'} Data \u2014 {dat_text}</span>
</div>
<div class="memory-box"><div class="value">{total_entries:,}</div><div class="label">Memory Entries</div></div>
''', unsafe_allow_html=True)

def render_glossary() -> None:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown('''
<div class="section-wrap">
    <h2>Glossary</h2>
    <p>
        Define exact term mappings that will always be respected during translation.
        Perfect for acronyms, program names, and fixed phrases.
    </p>
</div>
''', unsafe_allow_html=True)

    current = st.session_state.get("glossary", [{"EN":"","FR-CA":"","Note":""}])
    df_gloss = pd.DataFrame(current) if current else pd.DataFrame(columns=["EN","FR-CA","Note"])

    edited = st.data_editor(
        df_gloss,
        column_config={
            "EN":    st.column_config.TextColumn("English (source)", width="medium"),
            "FR-CA": st.column_config.TextColumn("French (FR-CA translation)", width="medium"),
            "Note":  st.column_config.TextColumn("Note / context (optional)", width="medium"),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="glossary_editor",
    )

    # Persist edits and rebuild memory if changed
    new_rows = edited.to_dict("records")
    old_sig = _glossary_sig()
    st.session_state["glossary"] = new_rows
    if _glossary_sig() != old_sig:
        st.session_state.pop("memory_sig", None)

    valid_count = sum(1 for r in new_rows if r.get("EN","").strip() and r.get("FR-CA","").strip())
    st.markdown(f'<p class="glossary-note">&#10003; {valid_count} active term{'s' if valid_count!=1 else ''} in glossary — applied with highest priority during translation</p>',
                unsafe_allow_html=True)

def render_translate_section(use_bom: bool, provider: str, api_key: str) -> None:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown('''
<div class="section-wrap">
    <h2>Files to Translate</h2>
    <p>Upload label files and/or data files \u2014 both types translate together with one click. Files stay loaded until you remove them.</p>
</div>
''', unsafe_allow_html=True)
    col_left, col_right = st.columns(2, gap="large")
    with col_left:
        new_lbl = _uploader("Label files to translate", TX_LABELS_KEY, '''
<div class="ref-caption">
    <div class="title">Label Files</div>
    <div class="drag">Drag and drop files here</div>
    <div class="detail"><code style="background:var(--blue-soft);color:var(--blue);padding:1px 6px;border-radius:5px;font-weight:600;font-size:12px;">EN</code> column &#10132; <strong>FR</strong> + <strong>FR-CA</strong></div>
</div>''')
        render_stored_files(TX_LABELS_KEY)
    with col_right:
        new_dat = _uploader("Data files to translate", TX_DATA_KEY, '''
<div class="ref-caption">
    <div class="title">Data Files</div>
    <div class="drag">Drag and drop files here</div>
    <div class="detail"><code style="background:var(--blue-soft);color:var(--blue);padding:1px 6px;border-radius:5px;font-weight:600;font-size:12px;">default value</code> column &#10132; <strong>FR</strong> + <strong>FR-CA</strong></div>
</div>''')
        render_stored_files(TX_DATA_KEY)
    added = sync_to_store(TX_LABELS_KEY, new_lbl)
    added |= sync_to_store(TX_DATA_KEY, new_dat)
    if added:
        st.rerun()

    label_files = st.session_state.get(TX_LABELS_KEY, [])
    data_files  = st.session_state.get(TX_DATA_KEY, [])
    total = len(label_files) + len(data_files)
    if total == 0:
        return

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(f'''
<div class="section-wrap" style="margin-top:32px;">
    <h2>Run Translation</h2>
    <p>{total} file{'s' if total!=1 else ''} queued \u2014 {len(label_files)} label, {len(data_files)} data</p>
</div>
''', unsafe_allow_html=True)

    if st.button(f"Translate All {total} File{'s' if total!=1 else ''}",
                 key="translate_all_btn", type="primary", use_container_width=True):
        memory = get_or_build_memory()
        for store_items, ftype, source_col in [
            (label_files, FileType.LABEL_FILE, None),
            (data_files,  FileType.DATA_FILE,  "default value"),
        ]:
            for item in store_items:
                try:
                    df_check = load_file(io.BytesIO(item["data"]), file_name=item["name"])
                    target_cols = [c for c in df_check.columns if c.strip().upper() in ("FR","FR-CA")]
                except Exception:
                    target_cols = []
                config = PipelineConfig(
                    file_type_override=ftype, source_lang="EN", target_lang="FR-CA",
                    target_columns=target_cols if target_cols else ["FR","FR-CA"],
                    source_column_override=source_col, use_bom=use_bom,
                    provider=provider, api_key=api_key if api_key else None,
                )
                _run_translation(item, config, memory)

    _render_results(label_files, data_files)

def _run_translation(item: dict, config: PipelineConfig, memory: TranslationMemory) -> None:
    result_key  = f"result_{item['sig']}"
    status_box   = st.empty()
    progress_box = st.empty()
    status_box.markdown(f'''<div class="processing-card">
    <div class="title">Translating\u2026</div><div class="sub">{item["name"]}</div>
</div>''', unsafe_allow_html=True)
    progress = progress_box.progress(0, text="Loading\u2026")
    def _cb(step:str, pct:float)->None:
        progress.progress(min(max(pct,0.0),1.0), text=step)
    try:
        result = run_pipeline(
            main_file=io.BytesIO(item["data"]), main_filename=item["name"],
            config=config, memory=memory, progress_callback=_cb,
        )
        st.session_state[result_key] = result
    except Exception as exc:
        st.error(f"Error translating **{item['name']}**: {exc}")
    finally:
        progress_box.empty()
        status_box.empty()

def _render_results(label_files: list, data_files: list) -> None:
    all_entries = ([(i,"Label File") for i in label_files] + [(i,"Data File") for i in data_files])
    available = [(i,tl) for i,tl in all_entries if f"result_{i['sig']}" in st.session_state]
    if not available:
        return
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown('''<div class="section-wrap" style="margin-top:32px;"><h2>Results</h2></div>''',
                unsafe_allow_html=True)
    for idx, (item, type_label) in enumerate(available, 1):
        result: PipelineResult = st.session_state[f"result_{item['sig']}"]
        st.markdown(f'''<div class="file-result-header">
    <span class="idx">{idx}</span>
    <span class="fname">{item["name"]}</span>
    <span class="ftype">{type_label}</span>
</div>''', unsafe_allow_html=True)
        if result.validation.passed:
            st.success("Validation passed \u2014 file integrity preserved.")
        else:
            st.error("Validation failed.")
            for issue in result.validation.issues:
                st.warning(issue)
        prov: dict[str,int] = {}
        for t in result.translations:
            prov[t.provenance.value] = prov.get(t.provenance.value,0)+1
        ref_c   = prov.get("reference_exact_match",0)+prov.get("reference_normalized_match",0)
        cache_c = prov.get("session_cache",0)
        fresh_c = prov.get("fresh_translation",0)
        skip_c  = sum(v for k,v in prov.items() if "skipped" in k)
        st.markdown(f'''<div class="prov-row">
    <div class="prov-card"><div class="value">{ref_c}</div><div class="label">Reference</div></div>
    <div class="prov-card"><div class="value">{cache_c}</div><div class="label">Cache</div></div>
    <div class="prov-card"><div class="value">{fresh_c}</div><div class="label">Fresh</div></div>
    <div class="prov-card"><div class="value">{skip_c}</div><div class="label">Skipped</div></div>
</div>''', unsafe_allow_html=True)
        with st.expander("Translation Preview"):
            interesting = [t for t in result.translations if t.provenance not in (
                Provenance.SKIPPED_EMPTY,Provenance.SKIPPED_NUMERIC,
                Provenance.SKIPPED_INTERNAL,Provenance.SKIPPED_PROTECTED)][:40]
            if interesting:
                st.dataframe(pd.DataFrame([{
                    "Row":t.row_index,"Provenance":t.provenance.value.replace("_"," ").title(),
                    "Original":t.original[:80],"Translated":t.translated[:80],
                } for t in interesting]), use_container_width=True, hide_index=True)
        with st.expander("Diagnostics & Notes"):
            for k,v in sorted(result.diagnostics.items()): st.text(f"{k}: {v}")
            st.divider()
            st.dataframe(result.notes_df, use_container_width=True, hide_index=True)
        st.markdown(f'''<div class="done-area">
    <div class="done-arrow">{CURVED_ARROW_SVG}</div>
    <h3>Download Translated File</h3><p>Ready for Qualtrics import.</p>
</div>''', unsafe_allow_html=True)
        dl_l,dl_m,dl_r = st.columns([1,2,1])
        with dl_m:
            st.download_button("Download Translated File", data=result.translated_csv_bytes,
                file_name=result.translated_filename, mime="text/csv",
                key=f"dl_{item['sig']}", use_container_width=True)
        with st.expander("Optional downloads & full output"):
            st.markdown('<div class="secondary-downloads">', unsafe_allow_html=True)
            st.download_button("Download Notes Report", data=result.notes_csv_bytes,
                file_name=result.notes_filename, mime="text/csv",
                key=f"dl_notes_{item['sig']}", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.divider()
            st.dataframe(result.translated_df, use_container_width=True, hide_index=True)
    if len(available) > 1:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('''<div class="section-wrap" style="margin-top:32px;">
    <h2>Download All</h2><p>All translated files in one ZIP archive.</p>
</div>''', unsafe_allow_html=True)
        zb = io.BytesIO()
        with zipfile.ZipFile(zb,"w",zipfile.ZIP_DEFLATED) as zf:
            for item,_ in available:
                r = st.session_state[f"result_{item['sig']}"]
                zf.writestr(r.translated_filename, r.translated_csv_bytes)
        zb.seek(0)
        zl,zm,zr = st.columns([1,2,1])
        with zm:
            st.download_button(f"Download All {len(available)} Translated Files (.zip)",
                data=zb.getvalue(), file_name="translated_files.zip", mime="application/zip",
                key="dl_all_zip", use_container_width=True)

def render_footer() -> None:
    st.markdown('''<div class="app-footer">
    Qualtrics Dashboard Translator &middot; Powered by Argos Translate &middot; Free &amp; Offline
</div>''', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
def main() -> None:
    init_stores()
    st.markdown(CSS, unsafe_allow_html=True)
    render_header()
    use_bom, provider, api_key = render_sidebar()
    render_reference_upload()
    render_glossary()
    render_translate_section(use_bom, provider, api_key)
    render_footer()

main()
