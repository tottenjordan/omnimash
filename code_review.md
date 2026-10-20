# Code Review: `src/omnimash/security` Module

**Inspection Target:** `src/omnimash/security/` (`__init__.py`, `models.py`, `heuristics.py`, `client.py`, `guardrail.py`, `adk_plugin.py`)  
**Review Standard:** 5-Axes Code Review Framework (`Correctness`, `Readability & Simplicity`, `Architecture`, `Security`, `Performance`)  
**Overall Verdict:** **Conditionally Approved with Recommended Improvements**  
**Executive Summary:** The recent modernization of `src/omnimash/security` successfully introduced official Google Cloud Model Armor SDK integration (`google-cloud-modelarmor>=0.7.2`), regional endpoint routing, async client support, and high-speed local regex heuristics. However, inspection revealed several critical and required improvements concerning detector failure handling, RPC timeouts, heuristic false-positive sensitivity, and production fail-closed defaults.

---

## Findings Summary by Severity

| Severity | Count | Summary |
|---|---|---|
| **Critical** | 1 | Unhandled `InvocationResult.FAILURE` and `EXECUTION_ERROR` leading to silent approval of failed screenings. |
| **Required** | 2 | Missing RPC timeout parameters; Overly broad "hate speech" heuristic trigger causing false positives on benign screenplays. |
| **Optional** | 3 | Production `fail_closed` configuration; Missing client connection pool teardown; Empty/whitespace prompt RPC bypass. |
| **Nit** | 3 | Type annotations on client factories; Thread-safe client initialization lock; Cache key using `id(credentials)`. |

---

## Detailed Findings Across the 5 Axes

### 1. Correctness

#### `[CORR-01]` Critical: Unhandled `InvocationResult.FAILURE` and `EXECUTION_ERROR` causes silent approval
- **Location:** `src/omnimash/security/guardrail.py:138-164`
- **Description:** In `_process_sanitization_result`, the method only checks:
  ```python
  is_match = match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND
  ```
  If the remote Model Armor service experiences a backend detector outage, invocation failure (`result.invocation_result == InvocationResult.FAILURE`), or execution error (`result.filter_match_state == FilterMatchState.EXECUTION_ERROR`), `is_match` evaluates to `False`. The function then proceeds directly to line 178:
  ```python
  return GuardrailResult(is_approved=True, sanitized_prompt=sanitized_text, filter_match_state="NO_MATCH_FOUND", ...)
  ```
  This creates a critical vulnerability: failed or errored security scans are silently treated as approved and clean.
- **Remedy:** Inspect `result.invocation_result` and `result.filter_match_state`. If an error or failure is reported:
  ```python
  if getattr(result, "invocation_result", None) == modelarmor_v1.InvocationResult.FAILURE or match_state == modelarmor_v1.FilterMatchState.EXECUTION_ERROR:
      if self.fail_closed:
          return GuardrailResult(is_approved=False, sanitized_prompt="", rejection_reason="Model Armor screening failed to execute.", filter_match_state="EXECUTION_ERROR")
      return validate_prompt_heuristics(original_prompt)
  ```

#### `[CORR-02]` Required: Missing RPC Timeout on Synchronous and Asynchronous `sanitize_user_prompt` Calls
- **Location:** `src/omnimash/security/guardrail.py:82` and `src/omnimash/security/guardrail.py:112`
- **Description:** Both `client.sanitize_user_prompt(request=request)` and `await client.sanitize_user_prompt(request=request)` do not specify a `timeout` argument. Under network degradation or gRPC channel stalls, requests can hang up to default gRPC deadlines (often 60s+), freezing the FastAPI/Uvicorn event loop and orchestrator turns.
- **Remedy:** Pass a configurable `timeout` parameter (e.g. `timeout: float = 5.0`) on all `sanitize_user_prompt` invocations.

#### `[CORR-03]` Optional: Empty and Whitespace-Only Prompts Trigger Unnecessary Remote RPCs
- **Location:** `src/omnimash/security/guardrail.py:68` and `src/omnimash/security/guardrail.py:98`
- **Description:** If a user submits an empty string or whitespace-only prompt, the guardrail still constructs a `SanitizeUserPromptRequest` and performs a remote network call to Model Armor, risking 400 `INVALID_ARGUMENT` errors and introducing needless latency.
- **Remedy:** Guard early in `validate_prompt` and `validate_prompt_async`:
  ```python
  if not prompt or not prompt.strip():
      return GuardrailResult(is_approved=True, sanitized_prompt="")
  ```

---

### 2. Readability & Simplicity

#### `[READ-01]` Nit: Broad `-> Any` Return Type Annotations on Client Factory Functions
- **Location:** `src/omnimash/security/client.py:35` and `src/omnimash/security/client.py:75`
- **Description:** Both `get_model_armor_client` and `get_model_armor_async_client` return `-> Any` to avoid import errors when the package is missing. This deprives IDEs, static type checkers, and callers of autocomplete and type safety.
- **Remedy:** Use `typing.TYPE_CHECKING` to import and annotate `modelarmor_v1.ModelArmorClient` and `modelarmor_v1.ModelArmorAsyncClient` accurately.

#### `[READ-02]` Nit: Duplicate Import Guard Logic Across `client.py` and `guardrail.py`
- **Location:** `src/omnimash/security/guardrail.py:14-17` and `src/omnimash/security/client.py:8-14`
- **Description:** Both modules define independent `try...from google.cloud import modelarmor_v1...except ImportError` blocks.
- **Remedy:** Centralize the imported module in `client.py` and import `modelarmor_v1` directly from `omnimash.security.client`.

---

### 3. Architecture

#### `[ARCH-01]` Optional: Naming and Domain Clarification Between `omnimash.security` and `omnimash.engine.guardrails`
- **Location:** `src/omnimash/security/guardrail.py` vs `src/omnimash/engine/guardrails.py`
- **Description:** Having `omnimash.security.guardrail` (Model Armor input screening) alongside `omnimash.engine.guardrails` (Responsible AI prompt abstraction for character names/copyrights and post-inference 400 error parsing) creates naming confusion.
- **Remedy:** Add clear module-level docstrings explicitly delineating the responsibilities:
  - `omnimash.security`: Pre-generation adversarial injection, jailbreak, and PII gateway.
  - `omnimash.engine.guardrails`: In-engine prompt keyword abstraction and video inference policy error guidance.

#### `[ARCH-02]` Optional: Missing Cleanup / Teardown Hook for Cached gRPC Clients
- **Location:** `src/omnimash/security/client.py:18-19`
- **Description:** Cached `ModelArmorClient` and `ModelArmorAsyncClient` instances hold persistent gRPC channels and thread pools. During application shutdown or test teardown, channels remain open without an explicit `close()` hook.
- **Remedy:** Add `close_model_armor_clients()` and `async close_model_armor_async_clients()` functions to gracefully shut down open transports.

---

### 4. Security

#### `[SEC-01]` Required: Overly Broad Literal `"hate speech"` Pattern in Local Heuristics
- **Location:** `src/omnimash/security/heuristics.py:28`
- **Description:** `_MALICIOUS_PROMPT_PATTERNS` includes `r"\bhate\s+speech\b"`. This matches any occurrence of the literal phrase "hate speech", even when used harmlessly in screenplays (e.g. *"Detective: The suspect was investigated for hate speech online"*). This causes unintended false-positive rejections.
- **Remedy:** Refine the pattern to focus on intent or explicit attack phrasing:
  ```python
  r"\b(?:generate|write|produce|create)\s+(?:overt\s+)?hate\s+speech\b",
  r"\bovert\s+hate\s+speech\b",
  ```

#### `[SEC-02]` Optional: Production `fail_closed` Policy Configuration
- **Location:** `src/omnimash/security/guardrail.py:31`
- **Description:** `ModelArmorGuardrail.__init__` defaults to `fail_closed = False`. While ideal for developer convenience and automated CI test execution, production deployments should fail closed by default if the Model Armor service becomes unreachable.
- **Remedy:** Bind default `fail_closed` to `getattr(settings, "model_armor_fail_closed", False)`, allowing production `.env` to enforce strict fail-closed security.

#### `[SEC-03]` Nit: Cache Key Using `id(credentials)` Vulnerable to ID Collision
- **Location:** `src/omnimash/security/client.py:54` and `src/omnimash/security/client.py:94`
- **Description:** `cache_key = f"{effective_loc}:{id(credentials)}"` relies on `id(credentials)`. In CPython, if short-lived credential objects are allocated and deallocated, memory addresses can be recycled, leading to potential cache key collisions.
- **Remedy:** Use a tuple `(effective_loc, credentials)` or a weak reference cache dictionary.

---

### 5. Performance

#### `[PERF-01]` Nit: Thread-Safe Client Cache Initialization Lock
- **Location:** `src/omnimash/security/client.py:56-68`
- **Description:** Client caching uses a non-atomic `if cache_key not in _CLIENT_CACHE: ...` pattern without a mutex. Under high-concurrency cold-start scenarios, multiple worker threads may instantiate redundant `ModelArmorClient` gRPC channels.
- **Remedy:** Protect client cache initialization with a `threading.Lock()`.

---

## Action Plan & Remediation Roadmap

1. **Immediate / Critical:**
   - Update `_process_sanitization_result` to reject or fallback on `InvocationResult.FAILURE` and `FilterMatchState.EXECUTION_ERROR`.
   - Add default `timeout=5.0` to synchronous and asynchronous `sanitize_user_prompt` calls.
   - Refine `r"\bhate\s+speech\b"` in `heuristics.py` to prevent screenplay dialogue false positives.
2. **Follow-up / Optional & Nits:**
   - Add early return for empty/whitespace prompts.
   - Add `close_model_armor_clients()` teardown hook in `client.py`.
   - Add thread lock to client initialization.
   - Bind `fail_closed` to `settings.model_armor_fail_closed`.
