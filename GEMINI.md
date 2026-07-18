# Omnimash Agent Context & Guidelines

## 🚨 Critical Standards Reference
Always refer to [CODE_STANDARDS.md](file:///usr/local/google/home/jordantotten/omnimash/CODE_STANDARDS.md) when writing code, making environment changes, or managing dependencies.

---

## 🛠️ Environment & Tooling Rules
- **Package Manager:** Use `uv` exclusively (`uv add`, `uv remove`, `uv sync`). Never use bare `pip` or manual `python` execution.
- **Run Commands:** Always run commands prefixed with `uv run` (e.g. `uv run pytest`, `uv run ruff check`).
- **Linting & Formatting:** Use `ruff` for all linting and code formatting. Do not use `black` or `flake8`.
- **Testing & Type Checking:** Use `pytest` for testing and `ty` for type checking.
- **Git Commits & PRs:** Never add `Co-Authored-By` trailers in commit messages or pull requests.

---

## 📝 Project Notes & Knowledge
- Document session notes and non-derivable insights in single-topic markdown files under `docs/notes/`.
- Maintain the top-level index in [docs/notes/README.md](file:///usr/local/google/home/jordantotten/omnimash/docs/notes/README.md) with direct links to key files and topic notes (kept < 200 lines).
