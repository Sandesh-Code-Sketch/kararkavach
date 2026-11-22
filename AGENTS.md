# AGENTS.md — KararKavach Coding & Architecture Rules

## Non-Negotiable Architecture Rules
- **NO LLM Wrapper:** Legal scoring, clause extraction, and red-flag detection MUST be 100% deterministic Python code.
- **Deterministic Core (`core/`):**
  - `core/ocr.py`: OpenCV (`cv2` grayscale + adaptive thresholding) + `pytesseract` returning text and pixel bounding boxes `(x, y, w, h)`.
  - `core/extractor.py`: Python `re` (Regex) + `spaCy` (`EntityRuler`) extracting `₹` amounts, percentages, lock-in months, and notice days.
  - `core/rule_engine.py`: Pure Python evaluator loading `rules/tenancy_india.yaml` to compute a deterministic `0–100` Safety Score and `RED` / `YELLOW` / `GREEN` verdicts.
- **Targeted AI Adapter (`adapters/`):**
  - Only runs AFTER `rule_engine.py` flags `RED` or `YELLOW` clauses—strictly for plain-language Kannada/Hindi translation, audio generation (`gTTS`), and polite counter-clause drafting.
  - Must work 100% offline with clean template fallbacks when no LLM API key is configured.

## Verification & Done-When Rules
- Always write type hints on Python functions.
- Always run `pytest -v` after creating or modifying any backend module. Do not consider a task done until all tests pass.