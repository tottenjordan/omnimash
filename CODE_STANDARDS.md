# Code & Development Standards for omnimash

This document outlines the mandatory engineering standards, tooling rules, and development practices for the **omnimash** project.

---

## 🐍 Package & Environment Management (Modern Python)
- **Always use `uv`**: Manage all dependencies and environments exclusively via `uv`.
- **No bare `pip` or `python`**: Never run `pip install`, `python ...`, or manually activate virtualenvs (`source .venv/bin/activate`).
- **Running commands**: Always execute scripts and tools within the project environment using `uv run <command>` (e.g. `uv run python main.py`, `uv run pytest`).
- **Adding/Removing dependencies**:
  - Add runtime packages: `uv add <package>`
  - Add dev/test/lint tools: `uv add --group <group> <package>` (e.g. `uv add --group dev ruff ty`)
  - Remove packages: `uv remove <package>`
- **Dependency Groups**: Use `[dependency-groups]` in [pyproject.toml](pyproject.toml) (PEP 735) for development, linting, and testing dependencies.

---

## 🧹 Linting & Formatting
- **Ruff only**: Use `ruff` exclusively for both linting and formatting.
- **Forbidden legacy tools**: Never use `black`, `flake8`, `isort`, `pyupgrade`, or `pydocstyle`.
- **Commands**:
  - Format code: `uv run ruff format .`
  - Lint & auto-fix: `uv run ruff check --fix .`

---

## 🧪 Testing & Type Checking
- **Testing framework**: Use `pytest` for all unit and integration testing.
  - Run test suite: `uv run pytest`
- **Type checker**: Use `ty` for static type checking.
  - Run type checking: `uv run ty check`

---

## 📦 Git, Commit & Pull Request Guidelines
- **Structural Changes as Pull Requests**: All structural changes (modifying core architecture, schemas, system instructions, or adding new features) must be committed on a dedicated branch (`feature/...`, `refactor/...`, `fix/...`) and submitted as a Pull Request.
- **Unmerged PR Review Policy**: Never auto-merge PRs containing structural changes. Push the branch, open the Pull Request against `main`, and present the PR link and test verification summary to the user for review.
- **No Co-Authored-By Trailers**: Never add `Co-Authored-By` trailers or attribution lines when creating git commits or submitting PRs.
- **Commit Messages**: Write clean, descriptive commit messages matching Conventional Commits.
