# Subagent Execution & Permission Grating Quirks

This note documents non-obvious operational insights regarding autonomous subagent execution and permission handling in this environment.

---

## 🔑 Key Insights & Operational Rules

1. **Permission Inheritance Timing:**
   - Subagents inherit permissions active at the exact moment of invocation.
   - If spawned prior to a blanket grant, their cached permission map may trigger interactive approval modals.

2. **Autonomous Tooling Choice in Subagents:**
   - In subagent instructions, note that `command(*)` is fully pre-approved.
   - Subagents can execute shell commands (including Python scripts for file generation/updates, pytest, ruff, and ty) via `run_command` without waiting for approval modals.

3. **Multi-Subagent Review Workflow:**
   - For rigorous spec and quality control, dispatching dedicated **Spec Reviewer** and **Code Quality Reviewer** subagents per task ensures 100% test coverage, clean typing, and full compliance with [CODE_STANDARDS.md](file:///usr/local/google/home/jordantotten/omnimash/CODE_STANDARDS.md).
