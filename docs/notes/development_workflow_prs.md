# PR-First Workflow for Structural Changes

## 📌 Core Rule
All structural changes (modifying core architecture, adding new engine integrations, updating API schemas, modifying agent system instructions, or touching key infrastructure) must be committed to dedicated feature/refactor branches and submitted as unmerged Pull Requests for user review.

---

## 🛠️ Step-by-Step PR Procedure

1. **Branch Creation:**
   - Create a clean topic branch from `main`:
     ```bash
     git checkout -b feature/<feature-name>
     ```

2. **Verification Before Push:**
   - Ensure all quality gates pass:
     ```bash
     uv run pytest
     uv run ruff check --fix .
     uv run ruff format .
     uv run ty check .
     ```

3. **Commit Guidelines:**
   - Write clean Conventional Commit messages.
   - **CRITICAL:** Never add `Co-Authored-By` trailers or attribution lines.

4. **Pull Request Submission:**
   - Push the branch to GitHub:
     ```bash
     git push -u origin feature/<feature-name>
     ```
   - Create the Pull Request using GitHub CLI or GitHub API:
     ```bash
     gh pr create --title "<Title>" --body "<Summary>" --base main --head feature/<feature-name>
     ```

5. **Review Gate (Do Not Auto-Merge):**
   - **DO NOT MERGE** the Pull Request.
   - Present the PR link, summary of changes, and verification test status to the user for review and approval.
