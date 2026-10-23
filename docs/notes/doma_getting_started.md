# Getting Started with DOMA (Directorial Observability & Meta-Optimization Architecture)

This guide provides step-by-step instructions for using, developing, and operating the **DOMA** closed-loop meta-optimization system in OmniMash.

---

## 1. Core Architecture Overview

DOMA replaces the traditional open-loop prompt compiler with a dual-loop closed system:

```text
               ┌────────────────────────────────────────────────────────┐
               │              Turn-0 Prompt Compilation                 │
               │  - Strategy Bank Invariant Injection                   │
               │  - 5-Star Exemplar Few-Shot Grounding                  │
               │  - Deterministic Pre-Flight Gatekeeper Auto-Repair     │
               └──────────────────────────┬─────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │   Gemini Omni Flash 1.1 Video   │
                         └────────────────┬────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
       [ Micro-Loop (In-Session) ]                 [ Macro-Loop (Cross-Session) ]
       - Directorial Review (1-5 Stars)            - Offline Rule Induction
       - Multimodal Gemini 3.8 Critic              - Defect Pattern Clustering
       - Structured Scorecard Diagnostics          - Counterfactual Validation
       - 1-Click Prompt Patch & Re-Render          - Pareto Rule Pruning
```

---

## 2. Prerequisites & Environment Setup

Ensure dependencies are synced using `uv`:

```bash
# Sync dependencies
uv sync

# Ensure Google Cloud credentials for Gemini API & GCS
gcloud auth application-default login

# Verify environment variables
export GOOGLE_CLOUD_PROJECT="hybrid-vertex"
export GCP_REGION="us-central1"
export GEMINI_LOCATION="global"
export GOOGLE_CLOUD_LOCATION="global"
```

Start the local development server:

```bash
uv run uvicorn src.omnimash.api.app:create_app --factory --reload --port 8000
```

Open `http://localhost:8000` in your browser.

---

## 3. Screening Room Studio UI Workflow

### 3.1. Pre-Flight Invariant Verification (Act 1 & Mode 3)
When deconstructing a concept or editing shot prompt cards:
1. Check the compiled prompt preview panel.
2. Verify the **`✅ Pre-Flight Passed`** badge in the header:
   - Green pill confirms that character reference offsets (`@Image2`, `@Image3`), tag uniqueness, wardrobe redundancy removal, and audio ducking clauses have been verified and auto-repaired.
3. If prompt overrides contain stacked tags (e.g. `<IMAGE_REF_0> <IMAGE_REF_1>`) or un-ducked dialogue, the Pre-Flight Gatekeeper cleans them automatically before dispatching to Omni Flash.

### 3.2. Directorial Review Bar (Act 3: The Screening Room)
After rendering an 8–10s clip:
1. Locate the **Directorial Review Bar** below the video player.
2. **Rate the Shot (1–5 Stars)**:
   - ⭐⭐⭐⭐⭐ (5 Stars): Automatically unlocks the **`🌟 Save as 5-Star Exemplar`** button.
   - ⭐–⭐⭐⭐ (1–3 Stars): Automatically displays defect category chips (`Wardrobe Conflict`, `Audio Masked`, `Likeness Drift`, `Tag Collision`, `Beat Missed`).
3. Click one or more defect chips and enter optional notes (e.g., *"Background hip-hop beat drowns out Harry's rap"*).
4. Click **`Submit Review`** to persist the review triplet to GCS.

### 3.3. AI Critic Diagnosis & 1-Click Prompt Patching
1. When a clip is rated $\le 3$ stars, click **`🎯 Diagnose Shot`**.
2. The multimodal `VideoCriticAgent` (`gemini-3.8-flash`) inspects the MP4 video against the reference turnaround sheets and prompt.
3. Review the **AI Critic Diagnosis Card**:
   - Inspect dimensional scores: Video-Text Adherence, Likeness, Audio-Visual Harmony, Tag Integrity.
   - Inspect the highlighted root defect and surgical prompt mutation.
4. Click **`Approve & Re-Render Clip`** to apply the patched prompt and generate an improved cut immediately.

### 3.4. Curation & Directorial Memory Modal
1. Click **`🌟 Save as 5-Star Exemplar`** to archive exceptional generations into the **Exemplar Memory Bank**. These exemplars serve as few-shot demonstrations for future Turn-0 compilations.
2. Click **`🧠 Directorial Memory`** in the navigation header to open the Directorial Memory dialog:
   - **Active Strategy Bank Invariants**: View all currently active prompt invariants, confidence scores, and defect reduction rates.
   - **5-Star Exemplars**: Browse saved exemplars, their concepts, and compiled prompts.
   - **`⚡ Induce Rules`**: Trigger on-demand offline rule induction from accumulated defect history.
   - **`✂️ Pareto Prune`**: Run Pareto pruning to eliminate redundant or low-impact invariants, preventing prompt bloat.

---

## 4. REST API Quickstart

### 4.1. Submit Directorial Feedback
```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "turn_id": "turn_sample123",
    "session_name": "hiphop_dumble",
    "project_id": "prj_studio",
    "rating": 2,
    "selected_defect_categories": ["AUDIO_DROWNED"],
    "critique_text": "Spoken dialogue drowned by synth beat.",
    "video_url": "gs://omnimash-media-hybrid-vertex/renders/clip1.mp4",
    "prompt_text": "DumbleDior rapping in neon corridor."
  }'
```

### 4.2. Retrieve AI Critic Scorecard
```bash
curl -s http://localhost:8000/api/eval/scorecard/turn_sample123 | jq .
```

### 4.3. List Active Strategy Bank Invariants
```bash
curl -s http://localhost:8000/api/eval/rules | jq .
```

### 4.4. Trigger Macro-Loop Rule Induction
```bash
curl -X POST http://localhost:8000/api/eval/induce-rules \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": null,
    "min_defect_count": 2
  }' | jq .
```

### 4.5. Run Pareto Rule Pruning
```bash
curl -X POST http://localhost:8000/api/eval/rules/prune \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": null,
    "max_rules": 20
  }' | jq .
```

### 4.6. Ingest and List 5-Star Exemplars
```bash
# Ingest 5-star exemplar
curl -X POST http://localhost:8000/api/eval/exemplars \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "hiphop_dumble",
    "concept": "DumbleDior Paris Fashion Runway Showdown",
    "compiled_4block_prompt": "### INPUT ROLES & REFERENCES\n- Role A: DumbleDior\n### SCENE INSTRUCTIONS\nRunway walk in silk robes.",
    "video_url": "gs://omnimash-media-hybrid-vertex/renders/exemplar1.mp4",
    "user_rating": 5,
    "tags": ["Fashion", "Runway", "Silk"]
  }' | jq .

# List exemplars
curl -s http://localhost:8000/api/eval/exemplars | jq .
```

---

## 5. Python SDK & Developer Quickstart

### 5.1. Running the Pre-Flight Gatekeeper Directly
```python
from omnimash.prompts import PreFlightGatekeeper

raw_prompt = """
### INPUT ROLES & REFERENCES
[# Sources <FIRST_FRAME>@KeyframeSeed]
[# References <IMAGE_REF_0>@Image1]
- Role A <IMAGE_REF_0> <IMAGE_REF_1>: Harry Potter (@Image1)
  Wardrobe: Blue jeans and flannel shirt

### TIMELINE & DIALOGUE
[0-3s] Harry: "I will finish this."
"""

# Lint and auto-repair
result = PreFlightGatekeeper.lint_and_repair(
    prompt=raw_prompt,
    characters=[{"role_id": "Role A", "name": "Harry Potter"}],
    keyframe_image_url="https://storage.googleapis.com/bucket/start.png",
)

print(f"Is valid after repair: {result.is_valid}")
print(f"Repaired prompt:\n{result.repaired_prompt}")
for violation in result.violations:
  print(f"- Repaired [{violation.rule_id}]: {violation.message}")
```

### 5.2. Querying Few-Shot Demonstrations with Dynamic Code-Fences
```python
from omnimash.evaluation import ExemplarBankManager
from omnimash.storage.gcs import gcs_client

bank = ExemplarBankManager(storage=gcs_client)

# Formats 5-star exemplars with nested backtick protection (eliminates syntax breakout)
few_shot_markdown = bank.format_few_shot_block(
    concept="Cyberpunk neon alley duel",
    limit=2,
)
print(few_shot_markdown)
```

### 5.3. Inducing Rules Programmatically
```python
from omnimash.evaluation import DirectorialRuleInducer
from omnimash.storage.gcs import gcs_client

inducer = DirectorialRuleInducer(storage=gcs_client)

# Induces invariants from historical defect clusters
report = inducer.induce_rules_from_history(min_defect_count=2)
print(f"Induced {report['count']} new invariants.")

# Prune redundant or low-impact rules
pruned = inducer.pareto_prune_rules(max_rules=20)
print(f"Active invariant count after Pareto pruning: {len(pruned)}")
```

---

## 6. Testing & Quality Verification

Run DOMA test suites to verify local behavior:

```bash
# Run all DOMA evaluation tests (103 tests)
uv run pytest tests/evaluation/ tests/prompts/test_preflight_linter.py tests/prompts/test_compiler_doma.py tests/agent/test_adk_pipeline_doma.py tests/storage/test_gcs_exemplars.py -v

# Run closed macro-loop end-to-end test
uv run pytest tests/evaluation/test_doma_macro_e2e.py -v

# Run static type and lint checks
uv run ruff check .
uv run ty check
```
