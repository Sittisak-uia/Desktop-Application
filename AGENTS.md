# AGENTS.md

Early-stage Python project (scaffolding only). There is **no application source code, no tests, and no git repository** yet — the only committed artifacts are `requirements.txt` and a local `.venv`.

## Environment

- Virtualenv: local `.venv/` (Python 3.13.7). Use `& .venv\Scripts\python.exe` or activate it; do not rely on a system Python.
- All runtime/test packages are pinned in `requirements.txt`.
  - To sync after editing: `& .venv\Scripts\pip.exe install -r requirements.txt`

## Dependency stack (intended direction)

`requirements.txt` pre-installs the likely tech choices, but no code uses them yet:

- **AI / RAG**: `sentence-transformers`, `transformers`, `torch`, `faiss-cpu` (embeddings/indexing), plus `google-genai` and `gspread` (Gemini + Google Sheets).
- **UIs**: `streamlit` (web), `Django` (web framework), `PyQt6` (desktop GUI) — three distinct frontends are provisioned.
- **Other**: `pytest` (test runner), `python-dotenv` (env loading), `uvicorn` + `fastapi`/`starlette` (ASGI serving).

## Gotchas

- Don't assume a specific frontend/framework is in use — nothing is implemented. Confirm what the user wants built against this stack.
- No configured lint/typecheck/test commands exist yet; `pytest` is installed and will pick up `test_*.py`/`*_test.py` files.
- `.venv/` is present and should never be treated as project source.
