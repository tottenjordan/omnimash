# Code Review: `src/omnimash/api` Module

## Context & Scope

This review conducts an in-depth inspection of the `src/omnimash/api` module using the **5-Axes Quality Framework**:
1. **Correctness**
2. **Readability & Simplicity**
3. **Architecture**
4. **Security**
5. **Performance**

### Target Files Inspected
- [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py) (11,060 lines, 814 KB)
- [`src/omnimash/api/__init__.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/__init__.py) (0 lines)

### Associated Test Suites Inspected
- [`tests/api/test_app.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_app.py) (2,040 lines, 80 tests)
- [`tests/api/test_character_api.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_character_api.py)
- [`tests/api/test_concept_api.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_concept_api.py)
- [`tests/api/test_integration.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_integration.py)
- [`tests/api/test_storyboard_library_api.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_storyboard_library_api.py)
- [`tests/api/test_phase1_shot_and_draft_bugs.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_phase1_shot_and_draft_bugs.py)
- [`tests/api/test_phase3_media_security.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_phase3_media_security.py)
- [`tests/api/test_architecture_remediation.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_architecture_remediation.py)

---

## Executive Summary & Quality Verdict

- **Overall Health Verdict:** **Request Changes** — While the API has strong unit and browser integration test coverage (416 passing tests), it suffers from severe file bloat (11,060 lines in a single file containing an embedded 8,810-line React SPA), blocking synchronous I/O within an `async def` route handler, lack of exception isolation in concurrent batch tasks, extensive copy-paste logic duplication (~250+ lines across 5 endpoints), and full-file in-memory buffering on video range requests.
- **Total Findings:** 18
  - **Critical:** 3
  - **Required (no prefix):** 7
  - **Consider / Optional:** 5
  - **Nit:** 3

---

## 1. Correctness

### **Critical:** Blocking Synchronous I/O in `async def upload_media_file`
- **File:** [`src/omnimash/api/app.py#L9618-L9648`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9618-L9648)
- **Problem:** `upload_media_file` is defined as `async def`, but executes blocking synchronous file I/O (`with open(local_path, "wb") as f: f.write(content)`) and blocking synchronous network I/O (`agent.storage.upload_bytes(...)`).
- **Impact:** In FastAPI, an `async def` endpoint executes directly on the main asyncio event loop thread. Any blocking disk or network write freezes the entire event loop, preventing all other concurrent requests, SSE connections, or background tasks from progressing until the file write completes.
- **Remedy:** Either change the signature to standard synchronous `def upload_media_file(...)` (so FastAPI automatically offloads execution to its AnyIO worker threadpool), or wrap blocking writes in `await anyio.to_thread.run_sync(...)`.

### **Critical:** Unhandled Exceptions in `generate_draft_batch` Abort the Entire Batch
- **File:** [`src/omnimash/api/app.py#L10603-L10642`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10603-L10642)
- **Problem:** In `/api/storyboard/draft-batch`, the inner function `_run_draft` lacks a `try...except` block around `agent.process_user_turn(...)`. `executor.map(_run_draft, tasks)` is then evaluated into a list via `list(...)`.
- **Impact:** If even a single variation fails due to a transient API timeout, rate limit, or model safety filter, `executor.map` raises the exception upon consumption. This crashes the entire HTTP request with a 500 Internal Server Error, discarding all other successfully rendered variations and leaking compute.
- **Remedy:** Wrap `_run_draft` in a `try...except Exception as exc:` block, returning a `DraftBatchItem` with `status="FAILED"`, `video_url=None`, and capturing the error message so the caller receives the partial batch.

### **Critical:** Temporary File Descriptor & Disk Leak on Stitching Upload Failure
- **File:** [`src/omnimash/api/app.py#L10103-L10116`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10103-L10116) and [`#L10577-L10590`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10577-L10590)
- **Problem:** In `/api/storyboard/stitch_master` and `/api/journey3/stitch`, `local_master_path` is removed only if `agent.storage.upload_file` succeeds without raising an exception. If GCS upload fails or raises an error, `os.remove(local_master_path)` is never reached. (Compare with `/api/stitch-clips` at `#L10080-L10085`, which properly uses a `finally:` block).
- **Impact:** Failed stitch uploads leave multi-megabyte temporary H.264 video files indefinitely in `/tmp/`, causing disk exhaustion on long-running container instances.
- **Remedy:** Wrap GCS upload in `try: ... finally: if local_master_path.startswith('/tmp/') and os.path.exists(local_master_path): os.remove(...)`.

### Inconsistent Error Protocol: HTTP Status Codes vs 200 OK with `success: False`
- **File:** [`src/omnimash/api/app.py#L10971-L11046`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10971-L11046) vs [`#L9657-L9695`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9657-L9695)
- **Problem:** Endpoints use divergent error reporting conventions:
  - `/api/characters/generate-sheet` and `/api/characters/save-sheet` catch all exceptions and return HTTP 200 with `GenerateCharacterSheetResponse(success=False, details=str(e))`.
  - `/api/motion-reference/upload` catches exceptions and raises `HTTPException(status_code=500, detail=str(exc))`.
  - `/api/journey3/keyframe` catches exceptions and returns `JSONResponse(status_code=400, content={"detail": err_str})`.
- **Impact:** Client-side fetch handlers and frontend state management cannot rely on HTTP status codes to detect failures, forcing bespoke response-body checking per endpoint.
- **Remedy:** Standardize on FastAPI `HTTPException` with semantic status codes (400, 404, 422, 500) and consistent error schemas.

---

## 2. Readability & Simplicity

### Monolithic 11,060-Line File (`app.py`) Containing an Embedded 8,810-Line SPA
- **File:** [`src/omnimash/api/app.py#L507-L9317`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L507-L9317)
- **Problem:** `UI_HTML` is an 8,810-line raw string literal embedded directly inside a Python backend module. Navigating Python backend code requires jumping past nearly 9,000 lines of Babel/React/Tailwind code.
- **Impact:** Violates single-responsibility principle; breaks IDE tooling, linting, and type checking for the frontend codebase; creates extreme merge-conflict vulnerability.
- **Remedy:** Extract `UI_HTML` into a dedicated file (e.g. `src/omnimash/api/templates/index.html` or `static/index.html`) loaded lazily or served directly via `FileResponse` / `StaticFiles`.

### Massive Duplication of Character Role Normalization Logic (~175 Lines)
- **File:** [`src/omnimash/api/app.py#L9420-L9455`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9420-L9455), [`#L9700-L9740`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9700-L9740), [`#L9896-L9940`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9896-L9940), [`#L10308-L10326`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10308-L10326), [`#L10425-L10460`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10425-L10460)
- **Problem:** The identical ~35-line loop that normalizes `CharacterRoleModel | dict` into `CharacterRole` dataclass objects (handling `role_id`, `name`, `description`, `reference_url`, `aesthetic_tags`, `voice_style`, `wardrobe`, `image_role`, and `is_offscreen_narrator` with fallback attribute getters) is duplicated verbatim across 5 route handlers.
- **Remedy:** Extract a single canonical conversion helper: `def normalize_character_roles(characters: list[CharacterRoleModel | dict[str, Any]] | None, sanitize: bool = False) -> list[CharacterRole]`.

### Duplicate Storyboard Master Stitching Handlers
- **File:** [`src/omnimash/api/app.py#L10092-L10125`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10092-L10125) and [`#L10568-L10601`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10568-L10601)
- **Problem:** `/api/storyboard/stitch_master` and `/api/journey3/stitch` execute identical business logic: calling `agent.stitcher.stitch_storyboard_master`, uploading to `sessions/{session_id}/masters/`, converting GCS URIs to proxy URLs, and returning master paths.
- **Remedy:** Unify into a single service helper `_stitch_and_upload_master(...)` called by both endpoints.

### Repeated Character Dict-to-Model Mapping in Storage Listing Routes
- **File:** [`src/omnimash/api/app.py#L10700-L10715`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10700-L10715), [`#L10755-L10770`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10755-L10770), [`#L10794-L10805`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10794-L10805), [`#L10823-L10836`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10823-L10836)
- **Problem:** Converting raw character dicts from storage into `CharacterRoleModel` instances is duplicated 4 times across `/api/characters/list`, `/api/projects/{name}/characters`, `/api/characters/load`, and `/api/characters/roster`.
- **Remedy:** Add a `classmethod` constructor: `CharacterRoleModel.from_storage_dict(data: dict[str, Any]) -> CharacterRoleModel`.

### Recompiled Regexes on Every Call in `parse_shot_directive_if_needed`
- **File:** [`src/omnimash/api/app.py#L9833-L9865`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9833-L9865)
- **Problem:** Six regexes (`r"-\s*Action\s*/\s*Subject:\s*(.*)"`, `r"-\s*(?:Dialogue...):\s*(.*)"`, etc.) are compiled on every single shot generation request inside an inner helper function.
- **Remedy:** Precompile patterns as module-level constants (`_RE_ACTION = re.compile(...)`).

---

## 3. Architecture

### Lack of Modular `APIRouter` Architecture (1,735-Line Closure Function)
- **File:** [`src/omnimash/api/app.py#L9320-L11050`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9320-L11050)
- **Problem:** All 38 route handlers are declared as nested inner functions inside a monolithic `def create_app(...)` factory.
- **Impact:**
  - Route handlers cannot be imported or tested independently.
  - Handlers capture outer scope variables (`agent`) rather than receiving dependencies via FastAPI's dependency injection (`Depends`).
  - OpenAPI tags and route metadata cannot be partitioned cleanly.
- **Remedy:** Modularize routes using `APIRouter` in `src/omnimash/api/routers/`:
  - `routers/generation.py` (`/api/generate`, `/api/diff`, `/api/journey3/...`)
  - `routers/storyboard.py` (`/api/storyboard/...`)
  - `routers/projects.py` (`/api/projects/...`, `/api/sessions/...`)
  - `routers/characters.py` (`/api/characters/...`)
  - `routers/media.py` (`/api/upload`, `/api/media-proxy`, `/api/motion-reference/...`)

### Direct Lexical Closure Access vs FastAPI Dependency Injection (`Depends`)
- **File:** [`src/omnimash/api/app.py#L9329-L9353`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9329-L9353)
- **Problem:** While `app.state.agent = agent` is set, all endpoints access the local variable `agent` directly from the enclosing `create_app` scope.
- **Impact:** Prevents overriding dependencies in tests via `app.dependency_overrides`.
- **Remedy:** Declare a dependency provider `def get_agent(request: Request) -> OmniMashAgent:` and inject it into endpoints via `agent: Annotated[OmniMashAgent, Depends(get_agent)]`.

### Hardcoded Allowed Buckets in `media_proxy`
- **File:** [`src/omnimash/api/app.py#L10911-L10918`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10911-L10918)
- **Problem:** `media_proxy` contains a hardcoded set of bucket names:
  ```python
  allowed_buckets = {
      agent.storage.bucket_name,
      settings.gcs_bucket_name,
      "reference-images-jt-trend-trawler",
      "omnimash-media-hybrid-vertex",
      "test-omnimash-bucket",
      "bucket",
  }
  ```
- **Impact:** Architectural leakage — environment-specific and test fixture bucket names are hardcoded in application logic.
- **Remedy:** Move permitted external bucket identifiers to `Settings` in `src/omnimash/config.py` (`settings.allowed_gcs_buckets`).

### Unused Package Dependency in `pyproject.toml`
- **File:** [`pyproject.toml#L17`](file:///usr/local/google/home/jordantotten/omnimash/pyproject.toml#L17)
- **Problem:** `sse-starlette>=3.5.0` is declared as a direct runtime dependency, but is neither imported nor used anywhere in the codebase.
- **Remedy:** Either implement real-time SSE progress streaming for batch video generation or prune the dependency with `uv remove sse-starlette`.

---

## 4. Security

### Memory Exhaustion (DoS Risk) via Full Blob Buffering in `media_proxy`
- **File:** [`src/omnimash/api/app.py#L10924-L10950`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10924-L10950)
- **Problem:** When handling HTTP 206 Partial Content (range requests) for video playback, `media_proxy` downloads the *entire* media file into memory via `data, content_type = agent.storage.download_blob_bytes(uri)` before slicing `chunk = data[start:end+1]`.
- **Impact:** Video players send dozens of small range requests during playback and scrubbing. A 50MB master video file scrubbed 10 times causes 500MB of transient RAM allocation. Under concurrent streaming, this creates high risk of Out-Of-Memory (OOM) worker termination.
- **Remedy:** Use GCS byte-range downloads (`blob.download_as_bytes(start=start, end=end)`) or stream directly via Starlette's `StreamingResponse`.

### Unsanitized Project & Session Names in GCS Storage Paths
- **File:** [`src/omnimash/api/app.py#L10723-L10750`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10723-L10750)
- **Problem:** `req.project_name`, `req.session_name`, and path parameter `project_name` are passed directly to `agent.storage.create_project` and `agent.storage.create_session` without validation against path traversal characters (e.g. `../`, `/`, null bytes).
- **Remedy:** Add Pydantic field validators with regex `^[a-zA-Z0-9_\-]+$` or sanitize using a slugify helper before constructing GCS blob paths.

### Unvalidated File Extension & Content-Type in `/api/upload`
- **File:** [`src/omnimash/api/app.py#L9627-L9635`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9627-L9635)
- **Problem:** `/api/upload` extracts the extension using `os.path.splitext(file.filename or "file")[1]` and stores the file without validating against permitted media types.
- **Remedy:** Validate against an explicit media extension allowlist (`.mp4`, `.mov`, `.mp3`, `.wav`, `.jpg`, `.jpeg`, `.png`, `.webp`) and reject unapproved MIME types.

---

## 5. Performance

### Inefficient ThreadPool Nesting in `generate_draft_batch`
- **File:** [`src/omnimash/api/app.py#L10640-L10642`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10640-L10642)
- **Problem:** `/api/storyboard/draft-batch` creates a new `ThreadPoolExecutor(max_workers=4)` inside a synchronous route handler that is already executing on one of FastAPI's AnyIO threadpool worker threads.
- **Impact:** Thread pool oversubscription and synchronous blocking of the HTTP worker until all 12 drafts finish.
- **Remedy:** Either convert to asynchronous execution using `asyncio.gather()` with `anyio.to_thread.run_sync`, or use a shared application-level threadpool.

### Absence of HTTP Compression on 814KB `UI_HTML` Response
- **File:** [`src/omnimash/api/app.py#L9342-L9350`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9342-L9350)
- **Problem:** The `/` dashboard endpoint returns `HTMLResponse(content=UI_HTML)` without `GZipMiddleware` enabled on the FastAPI application.
- **Impact:** Every page load transfers ~814 KB uncompressed HTML over the network instead of ~140 KB compressed (an unnecessary 5.8x network transfer penalty).
- **Remedy:** Add `app.add_middleware(GZipMiddleware, minimum_size=1000)` in `create_app`.

---

## Findings Summary & Priority Matrix

| ID | Finding Description | Axis | Severity | Recommended Remediation |
| :--- | :--- | :--- | :--- | :--- |
| **COR-01** | Blocking synchronous file & GCS I/O in `async def upload_media_file` | Correctness | **Critical** | Switch to `def` or use `anyio.to_thread.run_sync` |
| **COR-02** | Unhandled exception in batch draft worker crashes entire request | Correctness | **Critical** | Wrap `_run_draft` in `try...except` to capture `status="FAILED"` |
| **COR-03** | Temporary video file leak in `/tmp/` on failed stitching GCS uploads | Correctness | **Critical** | Enforce cleanup inside `try...finally` blocks |
| **SEC-01** | Full blob RAM buffering on range requests in `media_proxy` (DoS risk) | Security | Required | Fetch byte ranges via GCS API or `StreamingResponse` |
| **SEC-02** | Unsanitized project & session names in GCS path construction | Security | Required | Enforce `^[a-zA-Z0-9_\-]+$` regex validation in Pydantic models |
| **SEC-03** | Unvalidated file extensions & content-types in `/api/upload` | Security | Required | Enforce allowed media extension and MIME allowlists |
| **ARC-01** | Monolithic 1,735-line `create_app` closure lacking `APIRouter`s | Architecture | Required | Decompose into 5 domain `APIRouter` modules |
| **ARC-02** | Direct closure variable access to `agent` bypassing `Depends` | Architecture | Required | Introduce `get_agent` dependency provider |
| **RED-01** | 8,810-line embedded React SPA string inside backend `app.py` | Readability | Required | Extract `UI_HTML` to `src/omnimash/api/templates/index.html` |
| **RED-02** | Verbatim 35-line character normalization loop duplicated across 5 routes | Readability | Required | Extract `normalize_character_roles` helper |
| **RED-03** | Storyboard master stitching logic duplicated in two endpoints | Readability | Required | Unify into `_stitch_and_upload_master` |
| **PER-01** | Absence of GZip compression on 814KB dashboard response | Performance | Consider | Add FastAPI `GZipMiddleware(minimum_size=1000)` |
| **PER-02** | ThreadPoolExecutor oversubscription in `generate_draft_batch` | Performance | Consider | Use shared executor or async task orchestration |
| **ARC-03** | Hardcoded bucket names in `media_proxy` | Architecture | Consider | Move bucket allowlist to `Settings` in `config.py` |
| **ARC-04** | Unused `sse-starlette` dependency in `pyproject.toml` | Architecture | Consider | Prune with `uv remove` or adopt for streaming |
| **RED-04** | Recompiled regexes in `parse_shot_directive_if_needed` | Performance | Consider | Precompile module-level `re.Pattern` constants |
| **COR-04** | Inconsistent error schemas (200 OK error vs HTTPException vs JSONResponse) | Correctness | Consider | Standardize on `HTTPException` with consistent JSON schema |
| **NIT-01** | F-strings used inside `logger.error` instead of %-formatting | Readability | Nit | Use `logger.error("msg: %s", exc)` |
