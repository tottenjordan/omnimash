# ADK Graph Workflow Modernization & Model Modality Separation

## 📌 Context & Motivation
During the Source-Driven Development audit of `src/omnimash/agent`, two critical architectural findings were identified when running under Google Agent Development Kit (`google-adk` 2.11.0+) and Google GenAI SDK (`google-genai` 2.31.0+):

1. **Legacy Workflow Agents Deprecation:** `SequentialAgent` and `ParallelAgent` are formally deprecated in ADK 2.x in favor of graph-based `google.adk.workflow.Workflow` DAGs.
2. **Model Modality Separation Conflict:** Configuring an ADK `Agent` with `model="gemini-omni-1.1-flash-preview"` caused live execution (`adk run` or `adk web`) to crash with HTTP 400 (`"gemini-omni-1.1-flash-preview is only supported in the Interactions API and cannot be called directly via generateContent"`).

---

## 🛠️ Key Architectural Patterns

### 1. Modern DAG Workflow Pipeline
In ADK 2.11+, workflows are modeled as graphs with explicit nodes, edges, `START`, and `JoinNode`:
```python
from google.adk.workflow import START, JoinNode, Workflow

def build_production_orchestrator(num_shots: int = 3) -> Workflow:
    deconstructor = create_script_deconstructor_agent()
    storyboard_compiler = create_storyboard_compiler_agent()
    shot_workers = [create_shot_execution_worker(shot_idx=i) for i in range(1, num_shots + 1)]
    join_node = JoinNode(name="shot_join_node")
    stitcher = create_final_cut_stitcher_agent()

    edges = [
        (START, deconstructor),
        (deconstructor, storyboard_compiler),
    ]
    for worker in shot_workers:
        edges.append((storyboard_compiler, worker))
        edges.append((worker, join_node))
    edges.append((join_node, stitcher))

    return Workflow(
        name="root_production_orchestrator",
        edges=edges,
    )
```
- Eliminates all runtime `DeprecationWarning` logs.
- Establishes a clean fan-out to parallel workers followed by an explicit `JoinNode` fan-in prior to final stitching.

### 2. Cognitive vs Video Model Modality Separation
- **Cognitive / Conversational Agent Layer:** Must run on a reasoning model supporting `generateContent` and function calling, specifically `settings.flash_model_id` (`gemini-3.8-flash` or `gemini-2.5-flash`).
- **Video & Audio Synthesis Tool Layer:** The agent's function tool (`generate_parody_clip`) invokes `OmniMashAgent.process_user_turn`, which drives `OmniFlashClient` to call `gemini-omni-1.1-flash-preview` through the **Interactions API** (`client.interactions`).
- **Function Tool Schema:** The tool function must include an `Args:` docstring section so ADK can inspect and pass parameter descriptions to Gemini's function declaration schemas.

### 3. Local ADK CLI & Dev UI Execution
- Running `adk run src/omnimash/agent "Hello"` executes cleanly via Vertex AI with:
  ```bash
  GOOGLE_GENAI_USE_VERTEXAI=1 GOOGLE_CLOUD_PROJECT=hybrid-vertex GOOGLE_CLOUD_LOCATION=global uv run adk run src/omnimash/agent "Hello"
  ```
- Running `adk web` in the Antigravity browser opens the developer UI:
  ```
  http://127.0.0.1:8000/dev-ui/?app-agent.py_folder
  ```
