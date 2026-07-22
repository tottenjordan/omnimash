# Codebase Review Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> On execution start, copy this plan to `docs/plans/2026-07-22-codebase-review-remediation.md` (repo convention) on a feature branch off `cc-work`.

**Goal:** Address every finding from the 2026-07-22 codebase review (`docs/notes/codebase_review_backlog.md`), phased Critical → Low, hardening security and robustness without ever tightening content-moderation behavior.

**Architecture:** Small, well-tested changes layered behind a tooling safety net (CI + ruff/ty first). Shared helpers built once and reused (path sanitizer, ffmpeg runner, settings-driven constants). Large structural refactors are isolated to the final phase so correctness/security work lands first behind green tests.

**Tech Stack:** Python 3.12, `uv`, `ruff`, `ty`, `pytest`, FastAPI, pydantic / pydantic-settings, google-genai, google-cloud-storage, ffmpeg.

---

## Context

The review found ~25 issues across security, robustness, config, performance, and structure. Some are exploitable today (arbitrary cross-bucket GCS read via `/api/media-proxy`), most are latent risks or maintainability debt. This plan turns that backlog into executable, test-first tasks. Work happens on `cc-work` (integration branch) via per-task `feature/*` branches → PRs into `cc-work`; **`cc-work` is not merged to `main` until the user says so.**

### User decisions shaping this plan
- **Scope:** all findings, phased; big refactors last.
- **Guardrails: relaxed by default — do not interfere.** See "Explicitly out of scope" below.
- **Session state:** minimal fix (lock + eviction), no new infra.
- **Auth:** deferred. Do scoping + input validation only; no auth dependency added.

### Explicitly OUT OF SCOPE (won't-fix, by user direction)
- **Content moderation stays permissive.** Do **not** implement real Model Armor, do **not** make `ModelArmorGuardrail` fail-closed, and do **not** route `compiled_override`/`voiceover`/`on_screen_text`/scene text/character `description` through content validation. (Backlog "Guardrail is a stub" + "Guardrail bypass" are intentional.)
- The relaxed `BLOCK_NONE` safety settings and `_abstract_prompt_for_responsible_ai` in `engine/omni_client.py` remain untouched.
- **Guard against regressions:** any validation added below is for *structured identifiers and URLs only* (traversal/SSRF), never free-text creative content. Add a test asserting a "spicy" free-text prompt still passes end-to-end (Task 5).

### Constraints / environment gotchas
- **Tests can't run in the Claude sandbox** (HTTP 401 from the private registry `us-python.pkg.dev/artifact-foundry-prod`). All `pytest`/`ruff`/`ty` verification must be run locally by the executor.
- **No `conftest.py` / no fixtures exist.** Tests are self-contained functions constructing objects inline with `mock_mode=True`; mocking via `unittest.mock` (`patch`, `MagicMock`), `monkeypatch`, and local dummy classes. New tests must follow this style. Run with `uv run pytest` (`pythonpath=["src"]`).
- No `Co-Authored-By` trailers. Conventional Commit messages. Use `uv` only.

### Shared foundations (build first, reuse everywhere)
- **`sanitize_path_segment(value)`** — new helper in `src/omnimash/storage/gcs.py` (near `_slugify`, gcs.py:378). Rejects/normalizes traversal. Reused by `build_session_blob_path` and API validators.
- **`run_ffmpeg(cmd, *, timeout)`** — new helper in `src/omnimash/engine/media_utils.py` (new module) wrapping `subprocess.run(..., timeout=, capture_output=True, check=False)` + `TimeoutExpired` handling + returncode/stderr surfacing. Reused by `omni_client.ensure_rendered_video` and `stitcher.concatenate_clips`.
- **Settings-driven constants** — add fields to `OmniMashSettings` (`config.py`) for model id, HTTP timeout, retry count/delay, ffmpeg presets; replace hardcoded literals.

---

## Phase 0 — Tooling & safety net (do first)

### Task 0.1: Add ruff + ty config and fix surfaced lint
**Files:** Modify `pyproject.toml`.
**Why:** CODE_STANDARDS mandates ruff/ty but there is no `[tool.ruff]`/`[tool.ty]` config, so nothing is actually enforced and no shared rule set exists.
**Fix:** Add:
```toml
[tool.ruff]
target-version = "py312"
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "S"]
ignore = ["S603", "S607"]  # subprocess use is intentional & wrapped (Task 2.x)
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # asserts in tests
[tool.ty.environment]
python-version = "3.12"
```
**New behavior:** `uv run ruff check` and `uv run ty check` run against a defined rule set; `S` (bandit) rules surface unsafe patterns (some findings below).
**Steps:** (1) add config; (2) `uv run ruff check src/ tests/` — triage; auto-fix with `--fix`; (3) `uv run ruff format .`; (4) `uv run ty check src/` — record baseline errors (fix trivially, defer large ones with `# ty: ignore` + note); (5) commit `chore(tooling): add ruff and ty configuration`.

### Task 0.2: Add coverage tooling
**Files:** Modify `pyproject.toml`.
**Why:** No `pytest-cov`; the review's test-gap findings can't be measured.
**Fix:** `uv add --group dev pytest-cov`; then:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
addopts = "--cov=omnimash --cov-report=term-missing"
```
**New behavior:** `uv run pytest` prints per-module coverage with missing lines, establishing a baseline to raise as later phases add error-path tests.
**Steps:** add dep + config → `uv run pytest` → commit `chore(tooling): add pytest-cov coverage reporting`.

### Task 0.3: CI workflow
**Files:** Create `.github/workflows/ci.yml`.
**Why:** No CI exists; standards are unenforced on PRs.
**Fix:** GitHub Actions on pull_request/push: setup `uv`, `uv sync --all-groups`, run `uv run ruff format --check .`, `uv run ruff check .`, `uv run ty check src/`, `uv run pytest`.
**New behavior:** every PR into `cc-work`/`main` is gated on format/lint/type/test.
**Steps:** write workflow → commit `ci: add lint, type-check, and test workflow`. (Note: CI runner needs registry access; if the private index requires auth, document required secrets in the PR.)

### Task 0.4: Fix pyproject metadata
**Files:** `pyproject.toml:4`.
**Why:** `description = "Add your description here"` placeholder.
**Fix/New behavior:** real one-line description. Commit `chore: set package description`.

---

## Phase 1 — Critical & High security (scoping + validation only)

### Task 1.1: Build `sanitize_path_segment` helper (foundation)
**Files:** Modify `src/omnimash/storage/gcs.py` (add near `_slugify`, ~line 378); Test `tests/storage/test_gcs.py`.
**Why:** `build_session_blob_path` (gcs.py:114) interpolates `session_id`/`category` raw into keys — `../` or leading `/` escapes the `sessions/{id}/` prefix (cross-session read/write). `_slugify` is too lossy for ids (drops `-`/`_`, lowercases) and isn't applied to paths.
**Fix:**
```python
@staticmethod
def sanitize_path_segment(value: str | None, *, default: str = "global") -> str:
    """Sanitize a single GCS key path segment: no traversal, no separators."""
    if not value or not value.strip():
        return default
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip())
    cleaned = cleaned.strip("._-")           # kill leading dots/dashes
    return cleaned or default
```
Apply in `build_session_blob_path`: `sid = self.sanitize_path_segment(session_id)`, `clean_cat = self.sanitize_path_segment(category, default="misc")`, keep `os.path.basename(filename)`.
**New behavior:** `session_id="../other"` → `other`; keys can never escape `sessions/`. Existing valid ids (uuid/slug/`user:project` → `user_project`) unchanged except `:` → `_` (matches existing `get_or_create_session` sanitize at session_manager.py:40, so keys stay consistent).
**Tests (TDD):** write `test_sanitize_path_segment_blocks_traversal` asserting `..`, `/x`, `a/../b` collapse to safe segments and `build_session_blob_path("../evil","x","f.mp4")` stays under `sessions/`. Run → fail → implement → pass → commit `fix(storage): sanitize session/category path segments`.

### Task 1.2: Lock down `/api/media-proxy` to the app bucket + session scope
**Files:** Modify `src/omnimash/storage/gcs.py` (`download_blob_bytes`, 185–223); `src/omnimash/api/app.py` (media_proxy, 2257–2274); Test `tests/api/test_app.py`, `tests/storage/test_gcs.py`.
**Why (Critical):** `download_blob_bytes` parses the bucket from the user URI (`self._client.bucket(bucket_name)`, gcs.py:204) — any caller reads any object in any bucket the SA can access. Verified.
**Fix:** In `download_blob_bytes`, after parsing, reject buckets not in an allow-list: `{self.bucket_name}` plus any configured read-only reference buckets (add `settings.allowed_read_buckets: list[str] = []`; include the `DEFAULT_CHARACTERS` reference bucket `reference-images-jt-trend-trawler` so existing refs still load). If `bucket_name` not allowed → return `(b"", "")` (proxy turns that into 404). Keep the media_proxy handler's `gs://` check; it now inherits enforcement.
**New behavior:** proxy serves only the app bucket + explicitly-allowed reference buckets; cross-bucket reads return 404. No API contract change for legitimate media.
**Tests:** `test_media_proxy_rejects_foreign_bucket` (live-path `GcsStorageManager` with dummy client, assert foreign `gs://other-bucket/...` → empty); API test asserting 404. Commit `fix(security): restrict media-proxy to allow-listed buckets`.

### Task 1.3: Add path-safety validators to API request models
**Files:** Modify `src/omnimash/api/app.py` (models 13–141); Test `tests/api/test_app.py`.
**Why (High):** `session_name`, `master_title`, `slug`, `category` are free-form and flow into GCS keys; only client-side JS sanitizes.
**Fix:** Add a shared `pydantic.field_validator` (or `Annotated[str, AfterValidator(...)]`) reusing `GcsStorageManager.sanitize_path_segment` for `session_name`/`master_title`/`slug` on `SaveCharacterRequest`, `LoadCharacterRequest`, `SaveRosterRequest`, `GenerateRequest`, `CommitRequest`, `SaveFinalRequest`, `StitchClipsRequest`, `ExtendSceneRequest`, `ExtractReferenceRequest`. Do **not** validate creative text fields.
**New behavior:** identifiers are normalized server-side before reaching storage; traversal payloads become inert. Creative fields untouched (keeps guardrails relaxed).
**Tests:** POST with `session_name="../../x"` → stored/echoed value is sanitized. Commit `fix(security): validate identifier fields on API models`.

### Task 1.4: Validate reference/research URLs (SSRF surface)
**Files:** Modify `src/omnimash/api/app.py` (`ExtractReferenceRequest.url` 70–72; optionally `ResearchRequest`); Test `tests/api/test_app.py`.
**Why (High):** `url` is plain `str` handed to the extractor. Extractor is currently a stub, so latent — but wire the guard now so real ingestion is safe from the start.
**Fix:** Type `url` as `pydantic.HttpUrl` (or `AnyHttpUrl`), plus an allow-list validator for expected hosts (`youtube.com`, `youtu.be`, `www.youtube.com`). Reject others with 422.
**New behavior:** only well-formed http(s) URLs on allow-listed hosts reach the extractor; scheme/host abuse rejected before any fetch.
**Tests:** `file:///etc/passwd`, `http://169.254.169.254/...` → 422; a youtube URL → 200. Commit `fix(security): validate reference URLs against host allow-list`.

### Task 1.5: `mock_mode` should not silently fake in production
**Files:** Modify `src/omnimash/config.py` (mock_mode:16; add validator); Test `tests/test_config.py`.
**Why (Critical):** `mock_mode` defaults `True` (config.py:16). Components constructed without an explicit flag default to mock via `settings.mock_mode`, so a prod misconfig silently returns fake URLs/media. (`create_app` already defaults real via `MOCK_MODE=false`, so this mainly affects direct component construction and is an inconsistency.)
**Fix:** Default `mock_mode: bool = False`. Add a `model_validator(mode="after")` that, when `not mock_mode`, requires real creds/bucket resolvable (at least one of `google_api_key`/`gemini_api_key` or ADC project + a bucket name) — else raise `ValueError` at settings load (fail fast, not fake). Tests already pass `mock_mode=True` explicitly, so they're unaffected. **Does not touch guardrails.**
**New behavior:** real mode is the default; a broken prod config fails loudly at startup instead of serving fakes. Dev/tests opt into mock explicitly.
**Tests:** `OmniMashSettings(mock_mode=False, google_api_key=None, gemini_api_key=None, omnimash_gcs_bucket=None, google_cloud_project="")` raises; `mock_mode=True` returns fine. Commit `fix(config): default mock_mode off and validate real-mode credentials`.

---

## Phase 2 — Robustness & error handling

### Task 2.1: ffmpeg runner with timeout + returncode checks (foundation)
**Files:** Create `src/omnimash/engine/media_utils.py`; Test `tests/engine/test_media_utils.py`.
**Why (High):** No `subprocess.run` for ffmpeg passes `timeout=` (omni_client.py:325,372; stitcher.py:52,71) → a stalled ffmpeg hangs the worker forever; stitcher's re-encode returncode is unchecked (stitcher.py:71) → broken masters uploaded.
**Fix:** `run_ffmpeg(cmd, *, timeout=120) -> subprocess.CompletedProcess` wrapping `subprocess.run(cmd, capture_output=True, check=False, timeout=timeout)`, catching `TimeoutExpired` → raise a typed `FfmpegError` with stderr tail; expose `ok` helper.
**New behavior:** every ffmpeg call is bounded and its result inspectable.
**Tests:** `patch("subprocess.run", ...)` for success, non-zero, and `TimeoutExpired`; assert wrapper behavior. Commit `feat(engine): add bounded ffmpeg runner helper`.

### Task 2.2: Adopt runner in omni_client and stitcher; verify outputs
**Files:** Modify `src/omnimash/engine/omni_client.py` (325,372), `src/omnimash/stitching/stitcher.py` (52,71,79); Test `tests/stitching/test_stitcher.py`.
**Why:** see 2.1; also stitcher returns `out_path` even when both ffmpeg calls failed (stitcher.py:79).
**Fix:** replace direct `subprocess.run` with `run_ffmpeg(..., timeout=...)`; in stitcher, check returncode of both calls, and before upload assert `os.path.exists(out_path) and os.path.getsize(out_path) > 0` else raise. Log stderr on failure (replace `except Exception: pass`).
**New behavior:** a failed/hung stitch raises instead of uploading a broken/empty master; failures are logged with ffmpeg stderr.
**Tests:** stitcher with mocked failing re-encode → raises (not silent upload). Commit `fix(engine): bound ffmpeg calls and verify stitched output`.

### Task 2.3: Unique, cleaned-up temp files
**Files:** `src/omnimash/stitching/stitcher.py` (33: `concat_list.txt`); `src/omnimash/engine/omni_client.py` (fixed `temp_*` names in ensure_rendered_video); `src/omnimash/ingestion/media_extractor.py` (fixed `/tmp/mock_frame_*.jpg`, 143–146).
**Why (Medium):** fixed temp names in shared dirs collide under concurrency and leak disk; stitcher writes clip paths into concat list without escaping single quotes.
**Fix:** use `tempfile.mkdtemp()`/`NamedTemporaryFile` per call; remove in `finally`. Escape single quotes in concat-list paths (`path.replace("'", "'\\''")`).
**New behavior:** concurrent renders/stitches don't clobber each other; temp files are cleaned; odd paths don't corrupt the concat list.
**Tests:** stitcher builds concat file with an apostrophe path → correct escaping (assert file contents via a mocked run). Commit `fix(engine): use unique temp files and escape concat paths`.

### Task 2.4: Retry backoff jitter + exception-type classification
**Files:** `src/omnimash/engine/omni_client.py` retry loop (713–872), constructor (515–581); Test `tests/engine/test_omni_retry.py`.
**Why (Medium):** backoff has no jitter (thundering herd across clip workers), doubles a possibly-zero base delay (tight retry storm if misconfigured), and classifies retryability by substring-matching `str(exc)` (fragile).
**Fix:** enforce a min base delay in real mode; add jitter `delay = base * 2**(attempt-1); sleep(delay/2 + random.uniform(0, delay/2))` (vary by attempt; note scripts can't use `random` — production code can). Classify by exception type/`.code`/`.status` where google-genai exposes it, falling back to current substring checks only as a last resort. Keep auth-fallback behavior. Do not change safety-settings stripping.
**New behavior:** retries are jittered and capped; transient (429/5xx/timeout) retried, permanent (400/403) not; no zero-delay storms.
**Tests:** extend `test_omni_retry.py` (uses `client.retry_delay=0.0`, injected MagicMock clients) — assert non-retryable error stops early; assert retry count for retryable. Commit `fix(engine): jittered backoff and typed retry classification`.

### Task 2.5: Stop silent failures in the GCS layer
**Files:** `src/omnimash/storage/gcs.py` (upload_file 164–165, upload_bytes 182–183, and the `except Exception: pass` sites listed at 84,222,244,314,357,435,439,468,516,540); Test `tests/storage/test_gcs.py`.
**Why (High):** uploads return a fabricated public URL even on exception (146/165/176/183) → silent data loss + dangling URLs; reads swallow errors returning empty bytes.
**Fix:** catch narrow `google.api_core.exceptions.GoogleAPIError` (import guarded); log with context (`logging.getLogger(__name__)`); on upload failure **raise** (or return an explicit `None`/sentinel the caller checks) instead of a fake URL; reads return `None` on genuine error, not empty-success. Keep mock-mode fabricated URLs (that's intended for offline dev). Callers in orchestrator handle failures via Task 2.6.
**New behavior:** real upload failures surface; no dangling "success" URLs.
**Tests:** live `GcsStorageManager` with dummy client whose upload raises → `upload_file` raises/returns None (not a URL). Commit `fix(storage): surface GCS errors instead of fabricating success`.

### Task 2.6: Error handling around orchestrator + API external calls
**Files:** `src/omnimash/agent/orchestrator.py` (external calls at 71–80,142–154,202–214,272–288,349–393); `src/omnimash/api/app.py` (add exception handler in create_app ~2011); Test `tests/agent/test_orchestrator.py`, `tests/api/test_app.py`.
**Why (High):** no try/except around media/GCS/generation/ffmpeg calls → raw 500s, orphaned partial work, and `success=True` returned even when a save produced nothing.
**Fix:** wrap external calls in orchestrator methods; on failure return `AgentTurnResponse(success=False, status_event="ERROR", error_message=...)`. Add a FastAPI exception handler mapping known storage/engine errors → 502/400 with sanitized messages (no raw bucket/URI leakage). Before returning `success=True` in save/stitch endpoints, verify the returned URI is non-empty.
**New behavior:** downstream failures become typed error responses, not 500s; no orphaned "success". Internal URIs not leaked in errors.
**Tests:** `monkeypatch` `agent.omni_client.generate_clip` to raise → `process_user_turn` returns `success=False`; API save endpoint with empty save result → non-200/`success=False`. Commit `fix(orchestrator): handle external failures and return typed errors`.

### Task 2.7: Thread-safe, bounded session store (minimal per user)
**Files:** `src/omnimash/state/session_manager.py` (whole class); `src/omnimash/agent/orchestrator.py` (`_get_session` 336–347); Test `tests/state/test_session_manager.py`.
**Why (High):** `_sessions` dict has no lock (check-then-mutate races), never evicts (unbounded), and `add_turn`/`commit_turn` raise bare `KeyError`. `_get_session` reaches into the private dict.
**Fix (minimal, no new infra):** guard mutations with `threading.Lock`; add capacity/TTL eviction (e.g. `OrderedDict` LRU with `max_sessions` from settings, evict oldest); raise a domain `SessionNotFound` instead of bare `KeyError`; add a public `SessionManager.find_session(session_id)` encapsulating the sanitize/fallback lookup and use it from `_get_session`. Document the single-process limitation in a `docs/notes/` note.
**New behavior:** concurrent turns don't corrupt state; memory bounded; clearer errors; orchestrator no longer touches private state. (Still single-process — documented.)
**Tests:** LRU eviction test; `find_session` sanitize fallback; `SessionNotFound` raised. Commit `fix(state): thread-safe bounded session store with public lookup`.

### Task 2.8: Role-ID collision for 5+ named characters
**Files:** `src/omnimash/prompts/compiler.py:1085`; Test `tests/prompts/test_character_roles.py`.
**Why (Medium/correctness):** `role_id=role_labels[min(idx, len-1)]` clamps every character past the 4th to the last label → ambiguous `[STORYBOARD SEQUENCE]` references.
**Fix:** generate labels dynamically: `f"Role {chr(65+idx)}"` (A,B,C,…), or cap explicitly and `log.warning` when truncating.
**New behavior:** each character gets a unique role id; no silent aliasing.
**Tests:** deconstruct a concept naming 5 characters → 5 distinct role_ids. Commit `fix(prompts): unique role ids for 5+ characters`.

### Task 2.9: Regression guard — relaxed guardrail stays relaxed
**Files:** Test `tests/security/test_guardrail.py`, `tests/agent/test_orchestrator.py`.
**Why:** ensure none of the validation added in Phases 1–2 accidentally blocks spicy creative content (user requirement).
**Fix:** add tests asserting (a) `validate_prompt` approves edgy-but-legal free text, and (b) `process_user_turn` with a spicy `prompt`/`compiled_override` still returns `success=True` in mock mode.
**New behavior:** a guardrail regression that tightens content fails CI.
**Steps:** write tests → run → commit `test(security): lock in relaxed-guardrail behavior`.

---

## Phase 3 — Config, secrets & consistency

### Task 3.1: Secrets as `SecretStr`
**Files:** `src/omnimash/config.py` (13–14, 15); consumers in `engine/omni_client.py` (read `.get_secret_value()`); Test `tests/test_config.py`.
**Why (Medium):** `google_api_key`/`gemini_api_key` are plain `str | None` → leak into tracebacks/`repr`/settings dumps.
**Fix:** type as `pydantic.SecretStr | None`; update read sites to `.get_secret_value()`.
**New behavior:** keys masked in logs/repr; explicit unwrap at use.
**Tests:** `repr(settings)` doesn't contain the key value. Commit `fix(config): store API keys as SecretStr`.

### Task 3.2: Move hardcoded constants into settings
**Files:** `src/omnimash/config.py`; `src/omnimash/engine/omni_client.py` (model id 752/758, http timeout 556, max_attempts 731, retry_delay 526, `delay*=2`); optionally `compiler.py` model ids (869/880); stitcher/omni ffmpeg presets.
**Why (Medium):** deployment/cost-sensitive values buried in code.
**Fix:** add settings fields (`omni_model_id="gemini-omni-flash-preview"`, `omni_http_timeout_ms=300000`, `omni_max_retries=3`, `omni_retry_base_delay=0.5`, ffmpeg preset/crf/res/fps); reference them. **Keep `gemini-omni-flash-preview` as the sole video model (CLAUDE.md rule); never introduce Veo.**
**New behavior:** tuning via env/settings without code edits; single source of truth.
**Tests:** overriding `omni_model_id` via settings is honored by the client (monkeypatch settings, assert kwargs["model"]). Commit `refactor(config): centralize model/timeout/retry/ffmpeg constants`.

### Task 3.3: GCS client reuse + timeouts/retry policy
**Files:** `src/omnimash/storage/gcs.py` (`__init__` 63–85, call sites); optionally module-level client cache; Test `tests/storage/test_gcs.py`.
**Why (Medium):** each `GcsStorageManager()` builds a new `storage.Client` and does a network `lookup_bucket` in the ctor (media_extractor builds its own manager → extra round-trip); no `timeout=`/`retry=` on GCS calls → hangs.
**Fix:** cache a module-level client (lazy singleton keyed by project); make bucket verification lazy/one-time; pass explicit `timeout=` and `DEFAULT_RETRY` to upload/download/list calls.
**New behavior:** fewer client inits/round-trips; bounded, auto-retried GCS I/O.
**Tests:** two managers share one client (assert identity with patched `storage.Client`). Commit `perf(storage): reuse GCS client and bound calls with timeouts`.

### Task 3.4: Signed URLs for private buckets
**Files:** `src/omnimash/storage/gcs.py` `get_public_url` (104–107) and callers.
**Why (Low):** `get_public_url` always returns `https://storage.googleapis.com/...`, which 403s for private buckets yet is handed to clients as valid.
**Fix:** return `gs://` internally; add `generate_browser_url(blob)` using `blob.generate_signed_url(...)` when a browser-fetchable link is needed (media is already served via the proxy, so prefer proxy paths). Keep mock behavior.
**New behavior:** clients get working links (proxy or signed) instead of 403-prone public URLs.
**Tests:** signed-url path invoked for private bucket (mocked blob). Commit `fix(storage): signed/proxy URLs instead of assumed-public links`.

### Task 3.5: Remove dead code
**Files:** `src/omnimash/prompts/compiler.py` (`compile_storyboard` pass-through 841–859, dead Tier-1 replacements 327–333, local `import re` 198), `src/omnimash/engine/omni_client.py` (unused `audio_stem` param path; local re-imports of `re`/`time`), `known_lore` duplication (compiler 1040–1077 vs `CHARACTER_LORE_ANCHORS` 114–119).
**Why (Low):** dead/duplicated code drifts and misleads.
**Fix:** collapse `compile_storyboard` to an alias or single public name; delete dead replacements; hoist imports to module top; make `CHARACTER_LORE_ANCHORS` the single lore source and derive the fallback from it. Remove or wire `audio_stem` if truly unused (verify call sites first).
**New behavior:** less surface area; lore defined once.
**Tests:** existing compiler tests still green; add one asserting fallback lore matches `CHARACTER_LORE_ANCHORS`. Commit `refactor(prompts): remove dead code and dedupe lore`.

---

## Phase 4 — Performance

### Task 4.1: Stream media-proxy with HTTP Range support
**Files:** `src/omnimash/api/app.py` media_proxy (2257–2274); `src/omnimash/storage/gcs.py` (add ranged/streamed download); Test `tests/api/test_app.py`.
**Why (Medium):** proxy buffers the whole file into RAM and returns no `Accept-Ranges` → video scrubbing re-downloads the entire file.
**Fix:** add a streaming download (GCS `blob.open("rb")` or chunked `download_as_bytes(start,end)`), return `StreamingResponse` honoring `Range` (206 + `Content-Range`/`Accept-Ranges`). Preserve Task 1.2 bucket allow-list.
**New behavior:** constant-memory streaming; browsers can seek.
**Tests:** `Range: bytes=0-1023` → 206 with `Content-Range`; full GET → 200. Commit `perf(api): stream media-proxy with range support`.

### Task 4.2: Parallelize independent clip generation
**Files:** `src/omnimash/engine/omni_client.py` (batch entry) / `src/omnimash/agent/orchestrator.py` (storyboard multi-scene path); Test `tests/agent/test_orchestrator.py`.
**Why (Medium):** clips are generated one at a time though independent (non-diff-chain) clips are I/O-bound.
**Fix:** add an optional batch path using `concurrent.futures.ThreadPoolExecutor` for clips with no `parent_turn_id` chain; keep stateful diff/commit chains strictly sequential (ordering matters). Bound worker count via settings.
**New behavior:** multi-scene initial generation is faster; chained edits unchanged.
**Tests:** batch of 3 independent clips calls the client 3× and preserves order (monkeypatched client). Commit `perf(engine): parallelize independent clip generation`.

---

## Phase 5 — Structural refactors (largest; land behind green tests)

### Task 5.1: Extract the embedded frontend
**Files:** `src/omnimash/api/app.py` (`UI_HTML` 144–2007) → `static/` asset (e.g. `static/index.html`); serve via existing StaticFiles mount / `HTMLResponse` reading the file.
**Why (Medium):** ~1,863 lines of React/HTML live inside the Python module (CDN Babel at runtime), dwarfing ~270 lines of real API and making the file untestable/unwieldy.
**Fix:** move the string to a file; `GET /` returns its contents. No behavior change to the UI.
**New behavior:** `app.py` shrinks to API wiring; UI editable as a real asset.
**Tests:** `GET /` returns 200 HTML containing a known marker. Commit `refactor(api): extract embedded UI to static asset`.

### Task 5.2: Split API into routers + lifespan startup
**Files:** `src/omnimash/api/app.py` → `src/omnimash/api/routers/{generation,characters,sessions,media}.py`; `create_app` uses `APIRouter`s + `lifespan`.
**Why (Medium):** one monolithic `create_app`; `app = create_app()` and agent/`ensure_rendered_video` run at **import** (side effects: GCS/ffmpeg on import) → slow, fragile, hard to test.
**Fix:** move agent construction + warm-up into a FastAPI `lifespan` handler; expose agent via `app.state`/dependency; group endpoints into routers; `create_app()` composes them. Keep sync handlers (correct for the threadpool).
**New behavior:** no import-time I/O; testable, modular API; faster reload/worker startup.
**Tests:** importing `omnimash.api.app` does no network/ffmpeg (patch + assert not called); `TestClient` still green across endpoints. Commit `refactor(api): split routers and move startup into lifespan`.

### Task 5.3: Decompose the prompt-compiler fallback
**Files:** `src/omnimash/prompts/compiler.py` (`_deconstruct_fallback` 891–1213; duplicated keyword tuples at 896/909–920/936/963–1005/1128–1195).
**Why (Medium):** a ~320-line data-monolith with style-category keyword tuples duplicated 3× → edits desync silently.
**Fix:** extract module-level `STYLE_PROFILES: dict[Category, StyleProfile]` (char tags, voices, aesthetic/audio/env/camera) and a `classify_concept(text)` computed once; drive all lookups from it. Pure functions → unit-testable.
**New behavior:** one keyword source; fallback shrinks to lookup logic; each table independently testable. No output change for existing concepts (lock via golden tests first).
**Tests:** golden-output tests for 3 representative concepts BEFORE refactor (characterization), assert unchanged after. Commit `refactor(prompts): table-driven style profiles for fallback`.

---

## Verification (run locally — sandbox can't reach the registry)
1. `uv sync --all-groups`
2. `uv run ruff format --check . && uv run ruff check .`
3. `uv run ty check src/`
4. `uv run pytest` — all green; coverage should rise vs the Phase 0 baseline (error paths now covered).
5. Manual smoke (mock mode): `MOCK_MODE=true uv run python main.py`, then:
   - `GET /api/media-proxy?uri=gs://SOME-OTHER-bucket/x` → 404 (Task 1.2).
   - `POST /api/extract-reference` with a non-youtube URL → 422 (Task 1.4).
   - `POST /api/generate` with a spicy free-text prompt → still `success:true` (Task 2.9, relaxed guardrails intact).
   - `GET /api/media-proxy` with `Range` header → 206 (Task 4.1).
6. Real-mode config sanity: unset creds + `MOCK_MODE=false` → app fails fast at settings load (Task 1.5).

## Notes for the executor
- **Branching/PR methodology:** ONE `feature/*` branch off `cc-work` holds ALL of this work, delivered as a **single PR into `cc-work`**. Keep commits scoped per task (the Conventional Commit messages listed in each task) so the one PR stays reviewable commit-by-commit and revertible. Do **not** merge `cc-work` → `main` without explicit user instruction. No `Co-Authored-By` trailers.
- **Keep the branch fresh:** because the frontend (`app.py`) may also be edited by a parallel working group on `cc-work`, periodically `git merge cc-work` into this feature branch to avoid a large end-of-branch conflict.
- **Sequence the collision-prone work last:** land the Phase 5 refactors (extract `UI_HTML`, split `app.py`) as the final, clearly-isolated commits to contain conflicts with any parallel UI work.
- Never introduce Veo; `gemini-omni-flash-preview` stays the sole video model.
- After Phase 2/5, update `docs/notes/` (session store single-process limitation; API restructure) and refresh `docs/notes/codebase_review_backlog.md` to check off resolved items.
