# Project Notes & Session Knowledge Index

This directory documents non-obvious knowledge, session notes, and operational quirks for **omnimash** that are not easily derivable from git history or standard docs.

## 📌 Guiding Principles for Notes
- **Check & Update First:** Always check for an existing note on a topic before creating a new one. Update or prune stale/invalid notes.
- **Verification:** Re-verify referenced filenames, flags, or environment behaviors before acting on them.
- **High-Value & Non-Derivable:** Capture quirks, workarounds, and tricky setup details (e.g., tool/CLI quirks, broken flags, environment gotchas).

---

## 🗂️ Key Project Files
- [CODE_STANDARDS.md](../../CODE_STANDARDS.md) – Mandatory coding standards, tooling rules, and git practices.
- [GEMINI.md](../../GEMINI.md) – Agent context and workflow rules.
- [Implementation Plan (2026-07-18)](../plans/2026-07-18-omnimash-core-architecture.md) – Core architecture & pipeline implementation plan.
- [pyproject.toml](../../pyproject.toml) – Build configuration and dependencies (`uv`).
- [main.py](../../main.py) – Application entrypoint.
- [tests/test_main.py](../../tests/test_main.py) – Pytest test suite.
- [README.md](../../README.md) – Project overview.

---

## 📑 Topic Notes

| Topic | Note File | Description |
| :--- | :--- | :--- |
| Prompt Compiler & Anchor/Inject | [prompt_compiler_anchor_inject.md](prompt_compiler_anchor_inject.md) | Solving character decay and latent space averaging via 5-part Anchor & Inject meta-prompts |
| Context Decay & Checkpoints | [context_decay_commit_branch.md](context_decay_commit_branch.md) | Solving the 4-turn multimodal context decay via Commit & Branch thread re-anchoring |
| Subagents & Permissions | [subagent_workflow_quirks.md](subagent_workflow_quirks.md) | Insights into subagent permission inheritance and autonomous command execution |
| Architecture & System Design | [architecture_omnimash.md](architecture_omnimash.md) | Reference architecture, component breakdown, and pipeline design for OmniMash |
| Request Lifecycle & State | [request_lifecycle.md](request_lifecycle.md) | Blueprint for state management, Model Armor gating, and Interactions API lifecycle |
