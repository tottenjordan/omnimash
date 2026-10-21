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
- **Structural Changes as Pull Requests**: All structural changes (modifying core architecture, schemas, system instructions, or adding new features) must be committed on a dedicated branch (`feature/...`, `refactor/...`, `fix/...`) and submitted as a Pull Request. Never merge any Pull Request until the user has explicitly reviewed it and given direct approval to merge.
- **Commit Messages**: Write clean, descriptive commit messages matching Conventional Commits.

---

## ☁️ Cloud Resources & Deployment Policy
- **Explicit Approval Required for Redeployments**: Never redeploy any cloud resources (e.g. Cloud Run deployments via `./scripts/deploy_cloud_run.sh` or `gcloud run deploy`, Cloud Storage modifications, or Vertex AI Agent Engine deployments) without explicit, direct user approval.
- **Agent Engine Lifecycle & Orphan Pruning**: When deploying new revisions of OmniMash to Vertex AI Agent Engine (`omnimash-agent-production`), always prune superseded reasoning engine instances with the same display name (`.delete(force=True)`) to prevent orphan container resource accumulation. Never delete or modify reasoning engines with other display names or belonging to other projects.

---

## 🤖 Gemini Model Locations & Cloud Environment Variables
- **Gemini 3, 4 & Image Models (`global` location)**: All Gemini 3, Gemini 4, and Gemini Image generation models (`gemini-4-argon`, `gemini-3.8-flash`, `gemini-nano-banana-2.1`, `gemini-3-pro-image`, `gemini-omni-1.1-flash-preview`, `gemini-omni-flash-preview`) MUST use the `"global"` location for Vertex GenAI and Google GenAI model endpoints.
- **Gemini 2.X Models (Regional location)**: All Gemini 2.X models use a regional location (e.g., `us-central1`).
- **Environment Variable Conventions**:
  - `GOOGLE_CLOUD_LOCATION=global`: Specifically designates the Vertex GenAI / Google GenAI model endpoint location for Gemini 3 / 4 / Omni models.
  - `GCP_REGION=us-central1`: Specifically designates the default cloud region for all other Google Cloud infrastructure resources (BigQuery, Cloud Storage, Pub/Sub, Cloud Run Functions, Agent Engine).
