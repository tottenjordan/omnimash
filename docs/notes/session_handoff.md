# Session Handoff & Production Operational State

This document captures the current production operational state, recent milestones (PRs #203 – #208), architecture, and verification procedures for **omnimash**.

---

## 1. Live Production Deployments

| Component | Target / Region | Active Revision / Identifier | Status |
| :--- | :--- | :--- | :--- |
| **Cloud Run Web App** | `us-central1` | `omnimash-api-00162-klq` | Serving 100% traffic, HTTP 200 |
| **Live Studio URL** | Public HTTPS | [https://omnimash-api-934903580331.us-central1.run.app](https://omnimash-api-934903580331.us-central1.run.app) | Verified live with PR #211 |
| **Vertex AI Agent Engine** | `us-central1` | `projects/934903580331/locations/us-central1/reasoningEngines/1344918499926999040` | 1 active instance, 0 orphans |
| **Media Bucket** | GCS (`hybrid-vertex`) | `gs://omnimash-media-hybrid-vertex` | Staging, assets, storyboards |

---

## 2. Recent Milestones & Pull Requests

- **[PR #203](https://github.com/tottenjordan/omnimash/commit/0cc1d46)** (`feat(prompts)`): Added `prompt_intent_engine.py` expanding minimal 1-sentence ideas into structured 4-block Omni Flash prompts.
- **[PR #204](https://github.com/tottenjordan/omnimash/commit/d67b4db)** (`refactor(ui)`): Streamlined frontend user journeys into 3 distinct modes with Express 1-click video generation and cross-mode handoffs.
- **[PR #205](https://github.com/tottenjordan/omnimash/commit/46ab5e1)** (`fix(engine)`): Aligned Gemini Developer API model ID to `gemini-omni-1.1-flash` to eliminate HTTP 404 errors.
- **[PR #206](https://github.com/tottenjordan/omnimash/commit/28d25fc)** (`feat(ui)`): Added 1-click **🏰 Load Trapwarts Vault Default** preset preloading saved characters and GCS reference sheets.
- **[PR #207](https://github.com/tottenjordan/omnimash/commit/119dd88)** (`feat(prompts,engine)`): Aligned multimodal prompt compiler and pipeline with official Gemini Omni documentation (guiding instructions, task injection, continuation timecodes reset).
- **[PR #208](https://github.com/tottenjordan/omnimash/commit/be3628b)** (`feat(agent)`): Cleaned up 4 orphan Reasoning Engine instances and established automated lifecycle pruning in `scripts/deploy_agent_engine.py`.
- **[PR #210](https://github.com/tottenjordan/omnimash/commit/44f91d2)** (`feat(share)`): 7-day shareable video links via GCS V4 signed URLs with zero main app exposure.
- **[PR #211](https://github.com/tottenjordan/omnimash/commit/7f843fc)** (`feat(ui,prompts)`): Mode 4 Director's Co-Pilot and ubiquitous cross-mode gap filler.

---

## 3. Quick Verification Commands

```bash
# Full test suite (611 tests)
uv run pytest

# Targeted deploy script tests
uv run pytest tests/agent/test_deploy_agent_engine.py -v

# Linters & type check
uv run ruff check .
uv run ty check

# Check Agent Engine reasoning engines (dry run)
uv run python scripts/deploy_agent_engine.py --prune-orphans-only --dry-run
```
