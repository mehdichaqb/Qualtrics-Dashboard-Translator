# Qualtrics Dashboard Translator

A local Streamlit app that translates Qualtrics survey/dashboard CSV and XLSX files between **English** and **French (Canada)**, with optional reference-file translation memory.

## Features

- **Auto-detects** Qualtrics Data Files vs Label Files
- **Translation memory** from optional reference files (reuses known translations)
- **Token protection** preserves `${e://Field/...}`, HTML tags, QIDs, UUIDs
- **Provenance tracking** shows how each cell was translated (reference match, cache, fresh)
- **Structural validation** ensures row/column counts, headers, and ordering are preserved
- **UTF-8 CSV export** with optional BOM for Excel compatibility
- **Swappable translation backend** (Anthropic Claude API or mock for testing)

## Project Structure

```
.
├── app.py                        # Streamlit UI
├── processor/
│   ├── __init__.py
│   ├── file_loader.py            # CSV/XLSX loading with encoding detection
│   ├── detector.py               # File type detection (Data vs Label)
│   ├── classifier.py             # Cell content classification
│   ├── protector.py              # Token protection and restoration
│   ├── reference_memory.py       # Translation memory from reference files
│   ├── translator.py             # Translation provider abstraction
│   ├── rules.py                  # Decision hierarchy engine
│   ├── validator.py              # Structural integrity validation
│   ├── exporter.py               # UTF-8 CSV export
│   └── pipeline.py               # Full processing flow orchestrator
├── tests/
│   ├── test_file_loader.py
│   ├── test_detector.py
│   ├── test_classifier.py
│   ├── test_protector.py
│   ├── test_reference_memory.py
│   ├── test_rules.py
│   ├── test_validator.py
│   └── test_exporter.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

### 1. Clone and install

```bash
git clone https://github.com/mehdichaqb/Qualtrics-Dashboard-Translator.git
cd Qualtrics-Dashboard-Translator
pip install -r requirements.txt
```

### 2. Configure API key (optional)

Copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

Or set the environment variable directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Without an API key, the app falls back to a mock translator (prefixes `[FR-CA]`).

### 3. Run the app

```bash
streamlit run app.py
```

### 4. Run tests

```bash
python -m pytest tests/ -v
```

## How It Works

### File Type Detection

The detector uses column-name signatures and content patterns:
- **Data Files** have columns like `unique identifier`, `type`, `recode`, `default value`, with `DM_*` identifiers
- **Label Files** have columns like `pageId [DO NOT EDIT]`, `entityKey [DO NOT EDIT]`, with widget metadata

### Reference-File Translation Memory

1. Load reference Data File and/or Label File
2. Auto-detect locale columns (EN, FR-CA, etc.)
3. Build source-to-target dictionaries from bilingual pairs
4. For each cell in the main file, check (in order):
   - **Priority 1**: Exact reference match
   - **Priority 2**: Normalized match (trimmed whitespace, collapsed spaces)
   - **Priority 3**: Session cache (reuse earlier translations from this run)
   - **Priority 4**: Fresh translation via the translation engine
   - **Priority 5**: Keep original and flag if ambiguous

### Translation Provenance

Every translated cell is tagged with its provenance:
- `reference_exact_match` - found in reference file
- `reference_normalized_match` - found after whitespace normalization
- `session_cache` - same text was translated earlier in this run
- `fresh_translation` - translated by the translation engine
- `skipped_protected` - purely technical content (tokens, codes)
- `skipped_empty` / `skipped_numeric` / `skipped_internal`

### Swapping Translation Providers

The translator uses a provider pattern. To add a new provider:

1. Subclass `TranslationProvider` in `processor/translator.py`
2. Implement `translate_single()` and `translate_batch()`
3. Register it in the `get_translator()` factory function

Built-in providers:
- `AnthropicTranslator` - uses Claude API with batched numbered-list prompts
- `MockTranslator` - for testing, prefixes `[FR-CA]`

## Limitations & Edge Cases

- **No internet?** Falls back to mock translator
- **Very large files** (10k+ rows) may be slow with the API due to per-cell translation
- **HTML in cells** is preserved structurally but complex nested HTML may need manual review
- **Fuzzy matching** is intentionally conservative to avoid injecting incorrect survey wording
- **Multiple target locales** are not translated simultaneously; process one direction at a time
- **Conflicting reference translations** are flagged in the notes report

## Next Improvements

- Batch API calls more aggressively (group 50+ cells per request)
- Add Google Translate / DeepL / Azure provider options
- Support translating multiple target locale columns in one pass
- Add diff view comparing original vs translated side-by-side
- Export XLSX output option
- Add fuzzy-match suggestions with confidence scores
- Progress persistence for resuming interrupted translations
- CLI mode for headless/scripted usage
