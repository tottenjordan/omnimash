# Omnimash Agent Context & Guidelines

## 🚨 Critical Standards Reference
Always refer to [CODE_STANDARDS.md](CODE_STANDARDS.md) when writing code, making environment changes, or managing dependencies.

---

## 🛠️ Environment & Tooling Rules
- **Package Manager:** Use `uv` exclusively (`uv add`, `uv remove`, `uv sync`). Never use bare `pip` or manual `python` execution.
- **Run Commands:** Always run commands prefixed with `uv run` (e.g. `uv run pytest`, `uv run ruff check`).
- **Linting & Formatting:** Use `ruff` for all linting and code formatting. Do not use `black` or `flake8`.
- **Git Commits & PRs:** Never add `Co-Authored-By` trailers in commit messages or pull requests.
- **Branching & PR Workflow:** ALWAYS create feature branches (`feature/<name>`) and open Pull Requests with detailed, comprehensive descriptions (including background context, root cause analysis, implementation details, and verification steps) for user review. NEVER commit or push directly to `main`. NEVER merge any Pull Request until the user has explicitly reviewed it and given direct approval to merge.
- **Cloud Redeployments:** Never redeploy any cloud resources (Cloud Run, Cloud Storage, Vertex AI) without explicit user approval.

## 🎬 Video Model Engine Rule
- **Sole Video Model:** Gemini Omni Flash (`gemini-omni-flash-preview`) is our SOLE video+audio generation model across all scenes, initial clips, and conversational interaction diffs.
- **PROHIBITED:** NEVER use or reference Veo models (`veo-2.0-generate-001`, `veo-1.0`, etc.) under ANY circumstances — not even for testing or fallback.

## 🖥️ Web UI (`UI_HTML`) Guardrails
- **JSX Tag Balance Verification:** Whenever editing `UI_HTML` in `src/omnimash/api/app.py`, you MUST verify that all HTML/JSX tags (`<div>`, `<label>`, `<button>`, `<select>`, `<main>`) are 100% balanced and closed. Unbalanced JSX tags crash in-browser Babel compilation and cause the page to render blank (dark blue screen).
- **Mandatory Validation:** Run `uv run pytest tests/api/test_app.py` to ensure `test_ui_html_syntax_and_tag_balance` passes before committing any UI changes.

---

## 📝 Project Notes & Knowledge
- Document session notes and non-derivable insights in single-topic markdown files under `docs/notes/`.
- Maintain the top-level index in [docs/notes/README.md](docs/notes/README.md) with direct links to key files and topic notes (kept < 200 lines).

