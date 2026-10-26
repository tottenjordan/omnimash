# Session Handoff & Production Operational State

This document captures the current production operational state, recent milestones (PRs #203 – #208), architecture, and verification procedures for **omnimash**.

---

## 1. Live Production Deployments

| Component | Target / Region | Active Revision / Identifier | Status |
| :--- | :--- | :--- | :--- |
| **Cloud Run Web App** | `us-central1` | `omnimash-api-00169-hn2` | Serving 100% traffic, HTTP 200 |
| **Live Studio URL** | Public HTTPS | [https://omnimash-api-934903580331.us-central1.run.app](https://omnimash-api-934903580331.us-central1.run.app) | Verified live with PR #221 |
| **Vertex AI Agent Engine** | `us-central1` | `projects/934903580331/locations/us-central1/reasoningEngines/3773209721079595008` | 1 active instance, 0 orphans |
| **Media Bucket** | GCS (`hybrid-vertex`) | `gs://omnimash-media-hybrid-vertex` | Staging, assets, storyboards |

---

## 2. Recent Milestones & Pull Requests

- **[PR #210](https://github.com/tottenjordan/omnimash/commit/44f91d2)** (`feat(share)`): 7-day shareable video links via GCS V4 signed URLs with zero main app exposure.
- **[PR #211](https://github.com/tottenjordan/omnimash/commit/7f843fc)** (`feat(ui,prompts)`): Mode 4 Director's Co-Pilot and ubiquitous cross-mode gap filler.
- **[PR #218](https://github.com/tottenjordan/omnimash/pull/218)** (`fix(multimodal,api)`): Eliminate phantom keyframe seed to prevent character likeness drift and image shift.
- **[PR #219](https://github.com/tottenjordan/omnimash/pull/219)** (`feat(evaluation)`): DOMA Phase 1 & 2 closed-loop critic evaluator, scorecards, and prompt refiner.
- **[PR #220](https://github.com/tottenjordan/omnimash/pull/220)** (`feat(doma)`): DOMA Phase 3 & 4 pre-flight gatekeeper, macro-loop rule inducer, 5-star exemplar bank, and directorial memory UI.
- **[PR #221](https://github.com/tottenjordan/omnimash/pull/221)** (`feat(studio)`): Session iteration engine (fresh Turn-0 generation with existing values) and Mode 4 AI Critic integration.

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
