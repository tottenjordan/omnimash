# Gemini Enterprise Telemetry & Guardrail Guidance Architecture

This note documents the OpenTelemetry GenAI semantic conventions (v1.37.0+), Google Cloud Observability configuration, GCS multimodal prompt JSONL export schema, Cloud Trace span formatting, and UI guardrail error guidance architecture for **OmniMash**.

---

## 📊 OpenTelemetry GenAI Semantic Convention (v1.37.0+) Configuration

OmniMash integrates OpenTelemetry GenAI semantic conventions v1.37.0+ for tracking LLM/GenAI inference operations across the Google Cloud Observability ecosystem and Vertex AI Agent Engine.

### 🌐 Environment Flags

The following environment variables configure standard GenAI telemetry upload hooks and Opt-In stability schemas:

* `OTEL_SEMCONV_STABILITY_OPT_IN='gen_ai_latest_experimental'` — Enables latest OpenTelemetry GenAI experimental semantic conventions.
* `OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK='upload'` — Configures completion hook to upload prompt payloads automatically.
* `OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT='jsonl'` — Formats prompt input/output payload files as JSONL.
* `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY='true'` — Enables native Google Cloud Agent Engine telemetry telemetry exports.

These flags are initialized automatically via `setup_opentelemetry_genai_logging(bucket_name)` in [`src/omnimash/engine/telemetry.py`](../../src/omnimash/engine/telemetry.py).

---

## 🏷️ OpenTelemetry Span Labels & Attributes

Each inference request generates structured OpenTelemetry span attributes:

| Attribute Key | Type | Description / Example Value |
| :--- | :--- | :--- |
| `gen_ai.system` | `str` | `"vertex_ai"` |
| `event.name` | `str` | `"gen_ai.client.inference.operation.details"` |
| `gen_ai.input.messages_ref` | `str` | `"gs://<bucket>/telemetry/<session_id>_input.jsonl"` |
| `gen_ai.output.messages_ref` | `str` | `"gs://<bucket>/telemetry/<session_id>_output.jsonl"` |
| `gen_ai.error.code` | `str` | Error status code (e.g. `"400"`, `"429"`, `"RESOURCE_EXHAUSTED"`) |
| `gen_ai.safety.guardrail_type` | `str` | Safety guardrail category (e.g. `"MODEL_ARMOR_INJECTION"`, `"REAL_PERSON_LIKENESS"`) |

---

## 📄 Multimodal Prompt & Output JSONL Storage

Large multimodal prompt payloads (including base64 frames or turnaround sheet image references) and generation output metadata are exported as structured `.jsonl` files in session-scoped Cloud Storage folders:

* **Input Reference:** `gs://<bucket_name>/telemetry/<session_id>_input.jsonl`
* **Output Reference:** `gs://<bucket_name>/telemetry/<session_id>_output.jsonl`

### JSONL Format Example
```json
{"event": "gen_ai.client.inference.input", "session_id": "sess_882a", "system_prompt": "You are a director...", "roles": ["Role A", "Role B"], "timestamp": "2026-08-14T20:14:37Z"}
```

---

## 🔍 Cloud Trace & Cloud Logging Span Formatting

In Google Cloud Observability (Cloud Trace & Cloud Logging):
* Spans are rooted under `gen_ai.client.inference`.
* When a guardrail violation occurs, `gen_ai.error.code` and `gen_ai.safety.guardrail_type` are added to the active trace span, enabling instant query filtering in Cloud Logging:
  ```sql
  resource.type="cloud_run_revision"
  labels."gen_ai.safety.guardrail_type"!=""
  ```

---

## 🛡️ UI Guardrail Guidance Architecture

When prompt inputs or character names trigger safety blocks (such as Model Armor injection detection or Gemini 400 Real-Person Likeness blocks), the UI receives structured guidance:

1. **Model Armor Gateway Interception:** Flags policy violations prior to API submission.
2. **Structured Error Payload:** The API returns `rejection_reason` and `guardrail_type` alongside user-facing actionable guidance.
3. **UI Error Notification:** The React Continuity Studio UI highlights the exact guardrail category and suggests safe alternatives (e.g., using 1-click turnaround sheet generation instead of uploading real photos, or replacing real celebrity names with stylized parody handles).
