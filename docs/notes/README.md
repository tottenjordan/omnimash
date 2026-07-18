# Project Notes & Session Knowledge Index

This directory documents non-obvious knowledge, session notes, and operational quirks for **omnimash** that are not easily derivable from git history or standard docs.

## 📌 Guiding Principles for Notes
- **Check & Update First:** Always check for an existing note on a topic before creating a new one. Update or prune stale/invalid notes.
- **Verification:** Re-verify referenced filenames, flags, or environment behaviors before acting on them.
- **High-Value & Non-Derivable:** Capture quirks, workarounds, and tricky setup details (e.g., tool/CLI quirks, broken flags, environment gotchas).

---

## 🗂️ Key Project Files
- [CODE_STANDARDS.md](file:///usr/local/google/home/jordantotten/omnimash/CODE_STANDARDS.md) – Mandatory coding standards, tooling rules, and git practices.
- [GEMINI.md](file:///usr/local/google/home/jordantotten/omnimash/GEMINI.md) – Agent context and workflow rules.
- [Implementation Plan (2026-07-18)](file:///usr/local/google/home/jordantotten/omnimash/docs/plans/2026-07-18-omnimash-core-architecture.md) – Core architecture & pipeline implementation plan.
- [pyproject.toml](file:///usr/local/google/home/jordantotten/omnimash/pyproject.toml) – Build configuration and dependencies (`uv`).
- [main.py](file:///usr/local/google/home/jordantotten/omnimash/main.py) – Application entrypoint.
- [tests/test_main.py](file:///usr/local/google/home/jordantotten/omnimash/tests/test_main.py) – Pytest test suite.
- [README.md](file:///usr/local/google/home/jordantotten/omnimash/README.md) – Project overview.

---

## 📑 Topic Notes
*(Notes will be added here organized by topic as session work progresses)*

| Topic | Note File | Description |
| :--- | :--- | :--- |
| *Environment & Build* | *(Pending)* | Quirks with `uv`, python runtime, or dependencies |
| Architecture & System Design | [architecture_omnimash.md](file:///usr/local/google/home/jordantotten/omnimash/docs/notes/architecture_omnimash.md) | Reference architecture, component breakdown, and pipeline design for OmniMash |
| Request Lifecycle & State | [request_lifecycle.md](file:///usr/local/google/home/jordantotten/omnimash/docs/notes/request_lifecycle.md) | Blueprint for state management, Model Armor gating, and Interactions API lifecycle |
