# Omnimash Agent Context & Guidelines

## 🚨 Critical Standards Reference
Always refer to [CODE_STANDARDS.md](CODE_STANDARDS.md) when writing code, making environment changes, or managing dependencies.

---

## 🛠️ Tech Stack, Build & Tooling Rules
- **Package & Environment Manager:** Use `uv` exclusively (`uv add`, `uv remove`, `uv sync`). Never use bare `pip`, manual `python` execution, or manual virtualenv activation.
- **Run Commands:** Always execute commands prefixed with `uv run`:
  - Run application locally: `uv run python main.py`
  - Run full test suite: `uv run pytest`
  - Run API & UI tests: `uv run pytest tests/api/test_app.py -v`
  - Run linter: `uv run ruff check .` (or `uv run ruff check --fix .`)
  - Format code: `uv run ruff format .`
  - Run static type checker: `uv run ty check`
- **Linting & Formatting:** Use `ruff` exclusively for all linting and code formatting. Never use `black`, `flake8`, `isort`, or `pydocstyle`.
- **Git Commits & PRs:** Never add `Co-Authored-By` trailers in commit messages or pull requests. Use Conventional Commits formatting.
- **Branching & PR Workflow:** ALWAYS create feature branches (`feature/<name>`, `fix/<name>`, `refactor/<name>`) and open Pull Requests with detailed, comprehensive descriptions (including background context, root cause analysis, implementation details, and verification steps) for user review. NEVER commit or push directly to `main`. NEVER merge any Pull Request until the user has explicitly reviewed it and given direct approval to merge.
- **Cloud Redeployments:** Never redeploy any cloud resources (Cloud Run via `./scripts/deploy_cloud_run.sh`, Cloud Storage, Vertex AI) without explicit user approval.

---

## 🎬 Video Model Engine & Location Rules
- **Sole Video Model:** Gemini Omni Flash (`gemini-omni-1.1-flash-preview` / `gemini-omni-flash-preview`) is our SOLE video+audio generation model across all scenes, initial clips, and conversational interaction diffs.
- **PROHIBITED:** NEVER use or reference Veo models (`veo-2.0-generate-001`, `veo-1.0`, etc.) under ANY circumstances — not even for testing or fallback.
- **Model Locations:**
  - Gemini 3 & Omni models (`gemini-omni-1.1-flash-preview`, `gemini-3.1-pro-preview`, `gemini-3.1-flash-image-preview`) MUST use the `"global"` endpoint location (`GEMINI_LOCATION=global` / `GOOGLE_CLOUD_LOCATION=global`).
  - General GCP infrastructure resources (Cloud Run, Cloud Storage, Artifact Registry) default to regional `us-central1` (`GCP_REGION=us-central1`).

---

## 🖥️ Web UI (`UI_HTML`) Guardrails
- **JSX Tag Balance Verification:** Whenever editing `UI_HTML` in `src/omnimash/api/app.py`, you MUST verify that all HTML/JSX tags (`<div>`, `<label>`, `<button>`, `<select>`, `<main>`) are 100% balanced and closed within their respective JSX expression scopes. Unbalanced JSX tags crash in-browser Babel compilation and cause the page to render blank (dark blue screen).
- **Mandatory Validation:** Run `uv run pytest tests/api/test_app.py -k "test_ui_html_syntax_and_tag_balance or test_ui_html_renders_in_browser_without_syntax_error" -v` (and the full `tests/api/test_app.py` suite) before committing any UI changes.

---

## 📂 Key Paths & Project Knowledge
- **Source Code:** `src/omnimash/` (`api/app.py`, `engine/omni_client.py`, `prompts/compiler.py`, `agent/adk_pipeline.py`, `stitching/stitcher.py`, `storage/gcs.py`)
- **Test Suite:** `tests/` (`tests/api/`, `tests/engine/`, `tests/prompts/`, `tests/agent/`, `tests/stitching/`, `tests/storage/`)
- **Project Notes & Knowledge:**
  - Document session notes and non-derivable insights in single-topic markdown files under `docs/notes/`.
  - Maintain the top-level index in [docs/notes/README.md](docs/notes/README.md) with direct links to key files and topic notes (kept < 200 lines).
