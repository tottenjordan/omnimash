# 5-Axes Code Review: `src/omnimash/storage`

**Module Under Review:** [`src/omnimash/storage/gcs.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py), [`src/omnimash/storage/__init__.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/__init__.py)  
**Review Methodology:** 5-Axes Framework (Correctness, Readability & Simplicity, Architecture, Security, Performance)  
**Review Standard:** Strict Google Cloud & Python 3.12 Production Standards  

---

## Executive Summary & Severity Breakdown

| Severity | Count | Summary of Key Findings |
|---|:---:|---|
| **Critical** | 1 | Unvalidated `urllib.request.urlopen` remote media fetch creating Server-Side Request Forgery (SSRF) |
| **Required** | 10 | Unconfined path traversal, thread-safety race condition in shared client cache, missing GCS timeouts, 35 silent exception swallowing blocks, inconsistent proxy unquoting, eager subprocess initialization, leaky private field access, unsynchronized mock state, God-class bloat, and N+1 synchronous blob downloads |
| **Optional** | 3 | Incomplete MIME detection in `load_bytes`, hardcoded seed data in driver, and memory-buffered media uploads |
| **Nit** | 2 | Undocumented alias `GCSStorage` and loose `Any` typing |

---

## 1. Security (Highest Leverage)

### `[SEC-01]` Critical: Server-Side Request Forgery (SSRF) in `save_character_sheet` via Unvalidated `urllib.request.urlopen`
- **Location:** [`src/omnimash/storage/gcs.py#L629-L634`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L629-L634)
- **Problem:** When `image_data` is an HTTP/HTTPS URL, `save_character_sheet` makes a direct network call:
  ```python
  elif image_data.startswith("http://") or image_data.startswith("https://"):
      try:
          req = urllib.request.Request(image_data, headers={"User-Agent": "Mozilla/5.0"})
          raw_bytes = urllib.request.urlopen(req, timeout=10).read()
      except Exception:
          pass
  ```
  The URL is never validated. An attacker or malicious user can supply `http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token`, internal microservice endpoints, or localhost URLs, enabling instance metadata theft, service account token exfiltration, or intranet port scanning.
- **Remedy (Named Restructuring: Reuse Canonical Helper):** Remove `urllib.request.urlopen`. Validate using `validate_remote_media_url` and download safely using `fetch_media_bytes` from `omnimash.engine.media_loader`.

---

### `[SEC-02]` Required: Path Traversal Vulnerability in `save_final_master` via Unconfined Local Path
- **Location:** [`src/omnimash/storage/gcs.py#L496-L503`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L496-L503)
- **Problem:**
  ```python
  norm_source = self._normalize_media_source_path(source_rel_path)
  local_path = norm_source
  if local_path.startswith("/static/"):
      local_path = os.path.join(os.getcwd(), local_path.lstrip("/"))
  elif not os.path.isabs(local_path) and os.path.exists(
      os.path.join(os.getcwd(), local_path)
  ):
      local_path = os.path.join(os.getcwd(), local_path)
  ```
  If `source_rel_path` is `/static/../../etc/passwd` or contains directory traversal sequences (`..`), `local_path` escapes the `static/` directory boundary and uploads arbitrary host files to GCS.
- **Remedy (Named Restructuring: Reuse Canonical Helper):** Validate `local_path` with `validate_local_media_path` from `omnimash.engine.media_loader` to strictly confine reads to designated roots (`static/`, `/tmp`).

---

### `[SEC-03]` Required: Thread-Safety Race Condition in Class-Level Client Cache `_SHARED_CLIENTS`
- **Location:** [`src/omnimash/storage/gcs.py#L67`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L67), [`#L95-L103`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L95-L103)
- **Problem:**
  ```python
  _SHARED_CLIENTS: dict[str, Any] = {}
  ...
  client_key = self.project_id or "default"
  if client_key not in self._SHARED_CLIENTS:
      self._SHARED_CLIENTS[client_key] = storage.Client(project=self.project_id)
  ```
  `_SHARED_CLIENTS` is a shared class attribute mutated across threads without synchronization. In a multi-threaded ASGI server (Uvicorn with worker threads), concurrent requests initializing storage instances simultaneously will cause race conditions, duplicate client allocations, or dictionary corruption.
- **Remedy (Named Restructuring: Thread-Safe Singleton):** Protect `_SHARED_CLIENTS` access with a `threading.Lock()` using double-checked locking, or extract a thread-safe singleton factory `_get_shared_client(project_id)`.

---

### `[SEC-04]` Required: Missing Explicit Network Timeouts on All GCS SDK Operations
- **Location:** [`src/omnimash/storage/gcs.py#L111-L113`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L111-L113), [`#L183`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L183), [`#L201`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L201), [`#L243`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L243), [`#L286`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L286), [`#L303`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L303), [`#L411`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L411), [`#L506`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L506), [`#L838`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L838), [`#L899`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L899), [`#L916`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L916), [`#L950`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L950), [`#L980`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L980), [`#L1016`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1016), [`#L1053`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1053), [`#L1100`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1100), [`#L1118`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1118), [`#L1204`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1204), [`#L1249`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1249), [`#L1286`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1286)
- **Problem:** All calls to `blob.upload_from_filename`, `blob.upload_from_string`, `blob.download_as_bytes`, `blob.download_as_text`, `blob.delete`, and `client.list_blobs` omit the `timeout` parameter. In `google-cloud-storage` v3.x, default timeout behavior can hang indefinite TCP sockets during network interruptions, leading to worker exhaustion.
- **Remedy (Named Restructuring: Timeout Injection):** Define `DEFAULT_GCS_TIMEOUT = float(getattr(settings, "gcs_timeout_seconds", 30.0))` and pass `timeout=DEFAULT_GCS_TIMEOUT` across all SDK operations.

---

## 2. Correctness

### `[CORR-01]` Required: Blanket Silent Exception Swallowing (35 Instances of `except Exception: pass`)
- **Location:** 35 distinct locations across `gcs.py` (lines 102, 117, 185, 203, 218, 259, 317, 333, 417, 461, 512, 617, 627, 633, 641, 801, 808, 844, 874, 909, 911, 926, 928, 960, 962, 993, 1027, 1031, 1058, 1106, 1140, 1221, 1225, 1255, 1291).
- **Problem:** When GCS API calls encounter `Forbidden` (403), `NotFound` (404), `Unauthorized` (401), or `GoogleCloudError`, the exception is swallowed without any log message. The methods return empty lists, `None`, or empty strings.
  - This completely obscures configuration errors, invalid bucket names, expired service account tokens, or quota exhaustion.
  - Developers and operators have no diagnostic telemetry in Cloud Logging to understand why files are missing or why uploads failed.
- **Remedy (Named Restructuring: Structured Observability):** Replace silent `pass` blocks with structured `logger.warning("GCS operation '%s' failed on %s: %s", op, blob_path, exc)` or `logger.error(...)`.

---

### `[CORR-02]` Required: Inconsistent `/api/media-proxy` URL Unquoting Across Normalization Sites
- **Location:** [`src/omnimash/storage/gcs.py#L212-L219`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L212-L219), [`#L470-L475`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L470-L475), [`#L621-L628`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L621-L628)
- **Problem:**
  - In `download_blob_bytes` (line 217): `raw_uri = qs["uri"][0]` &rarr; **Not unquoted!** If the URL was percent-encoded (e.g. `uri=gs%3A%2F%2Fbucket%2Fclip.mp4`), `raw_uri.startswith("gs://")` fails and the download returns empty bytes.
  - In `save_character_sheet` (line 626): `unquote(qs["uri"][0])` &rarr; Unquoted.
  - In `_normalize_media_source_path` (line 474): `unquote(qs["uri"][0])` &rarr; Unquoted.
- **Remedy (Named Restructuring: Single Canonical Helper):** Consolidate all media-proxy parameter unpacking into `_normalize_media_source_path`, ensuring `unquote()` is consistently applied everywhere.

---

### `[CORR-03]` Required: Eager `storage.Client` Initialization in `__init__` Triggers Blocking Subprocesses
- **Location:** [`src/omnimash/storage/gcs.py#L95-L103`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L95-L103)
- **Problem:** `GcsStorageManager.__init__` eagerly attempts to construct `storage.Client(project=self.project_id)` whenever `not self.mock_mode and storage`. If `project_id` is None, `storage.Client()` runs `subprocess.run(('gcloud', 'config', 'get', 'project'))`.
  - In unit tests or environments without ADC credentials, this causes test timeouts or unexpected subprocess execution.
- **Remedy (Named Restructuring: Lazy Property Initialization):** Defer client construction until the first actual network call via `@property def client(self)` or `_get_client()`.

---

### `[CORR-04]` Optional: Incomplete MIME Type Fallback in `load_bytes`
- **Location:** [`src/omnimash/storage/gcs.py#L331`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L331), [`#L337`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L337)
- **Problem:**
  ```python
  mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
  ```
  Any non-PNG file (such as `.mp4`, `.wav`, `.aac`, `.json`) loaded via `load_bytes` is erroneously labeled `"image/jpeg"`.
- **Remedy:** Replace with unified `_guess_content_type(path)`.

---

## 3. Readability & Simplicity

### `[READ-01]` Required: Massive 1,313-Line God Class Violating Single Responsibility
- **Location:** Entire [`src/omnimash/storage/gcs.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py)
- **Problem:** `GcsStorageManager` contains 38 public/internal methods combining:
  1. Low-level GCS SDK blob operations (`upload_file`, `upload_bytes`, `download_blob_bytes`, `download_blob_range`, `ensure_bucket_exists`)
  2. Prompt & session manifest JSON persistence
  3. Reference analysis persistence
  4. Storyboard JSON CRUD (`save_storyboard`, `list_storyboards`, `load_storyboard`, `delete_storyboard`)
  5. Character catalog & cast roster CRUD
  6. Product catalog CRUD
  7. Multi-tenant project hierarchy simulation (`list_projects`, `create_project`, `list_sessions`, etc.)
- **Remedy (Named Restructuring: Logical Partitioning):**
  - Group methods into clear functional sections with section header blocks.
  - Extract common repetitive JSON read/write logic into generic helpers `_upload_json_payload` and `_download_json_payload` to eliminate ~250 lines of duplicate JSON dumping, UTF-8 encoding, and error handling.

---

### `[READ-02]` Required: Quadruplicate Hardcoded Content-Type Ladders
- **Location:** [`src/omnimash/storage/gcs.py#L170-L181`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L170-L181), [`#L246-L257`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L246-L257), [`#L306-L315`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L306-L315), [`#L814-L816`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L814-L816)
- **Problem:** Four separate 10-line chains checking `.mp4`, `.wav`, `.jpg`, `.jpeg`, `.png`, `.json`.
- **Remedy (Named Restructuring: Helper Extraction):** Extract `_guess_content_type(path: str, default: str = "application/octet-stream") -> str` using Python's `mimetypes.guess_type()`.

---

### `[READ-03]` Nit: Class Alias `GCSStorage = GcsStorageManager` Lacks Documentation
- **Location:** [`src/omnimash/storage/gcs.py#L1312-L1313`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1312-L1313)
- **Problem:** `GCSStorage = GcsStorageManager` is appended at the bottom of the file without docstring context.
- **Remedy:** Add docstring explaining that `GCSStorage` is an alias preserved for backward compatibility.

---

### `[READ-04]` Nit: Pervasive `Any` Typing and Loose Signatures
- **Location:** Throughout method parameters and return signatures (`dict[str, Any]`, `_client: Any`, `_bucket: Any`).
- **Remedy:** Type `_client: storage.Client | None` and `_bucket: storage.Bucket | None` with `TYPE_CHECKING` guards.

---

## 4. Architecture

### `[ARCH-01]` Required: Leaky Abstraction — Callers Accessing Internal `_bucket` Directly
- **Location:** Multiple call sites across modules and tests directly inspect `self.storage._bucket`.
- **Problem:** Bypasses encapsulation, making it impossible to substitute alternative storage providers or maintain invariants.
- **Remedy (Named Restructuring: Public Facade Methods):** Provide public `blob_exists(blob_path: str) -> bool`, `get_blob_metadata(blob_path: str) -> dict[str, Any] | None`, and `delete_blob(blob_path: str) -> bool`.

---

### `[ARCH-02]` Required: Unsynchronized In-Memory Mock State Between Mock Mode and Live Mode
- **Location:** [`src/omnimash/storage/gcs.py#L80-L93`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L80-L93)
- **Problem:** Nine separate internal dictionaries (`self._mock_characters`, `self._mock_analyses`, `self._mock_session_manifests`, `self._mock_storyboards`, `self._mock_projects`, `self._mock_project_sessions`, `self._mock_project_characters`, `self._mock_project_products`, `self._mock_project_reference_sheets`) serve as in-memory caches. In live mode, some methods write to them and others don't, causing state divergence.
- **Remedy (Named Restructuring: Explicit Storage Provider Isolation):** Centralize mock cache updates so that mock mode operates deterministically and live mode interacts cleanly with GCS without leaking stale cache entries.

---

### `[ARCH-03]` Optional: Hardcoded Seed Data (`DEFAULT_CHARACTERS`) in Storage Driver
- **Location:** [`src/omnimash/storage/gcs.py#L24-L61`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L24-L61)
- **Problem:** 37 lines of character definitions ("Harry 'Gucci'", "Young Draco 'Jeezy'", "Cyborg Gordon Ramsay", "Neon Julia Child") and external bucket references (`gs://reference-images-jt-trend-trawler/...`) reside inside the generic storage manager file.
- **Remedy:** Move seed data to a dedicated configuration/defaults module or JSON fixture.

---

## 5. Performance

### `[PERF-01]` Required: Unbounded `list_blobs` Iteration Without Page Size Constraints
- **Location:** [`src/omnimash/storage/gcs.py#L899`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L899), [`#L916`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L916), [`#L950`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L950), [`#L980`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L980), [`#L1016`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1016), [`#L1118`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1118), [`#L1204`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1204)
- **Problem:** Methods iterate over `self._bucket.list_blobs(prefix=prefix)` with no `page_size` or limit. In `list_session_ids`:
  ```python
  blobs = list(self._client.list_blobs(self.bucket_name, prefix="sessions/"))
  ```
  `list(...)` eagerly materializes every blob in memory. In a bucket with 10,000 files, this takes several seconds and megabytes of memory.
- **Remedy:** Supply `page_size=100` and stream iteratively without eager `list()` evaluation.

---

### `[PERF-02]` Required: N+1 Sequential Synchronous Network Calls in Listing Endpoints
- **Location:** [`src/omnimash/storage/gcs.py#L903`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L903), [`#L920`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L920), [`#L954`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L954), [`#L1020`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1020), [`#L1208`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L1208)
- **Problem:** In `list_characters`, `list_storyboards`, and `list_project_characters`, the code loops over every discovered blob and calls `blob.download_as_text()` synchronously:
  ```python
  blobs = self._bucket.list_blobs(prefix=prefix)
  for blob in blobs:
      if blob.name.endswith(".json"):
          data = json.loads(blob.download_as_text())
  ```
  Listing 30 storyboards generates 30 serial HTTPS requests over the internet.
- **Remedy (Named Restructuring: Parallel Fetch / Metadata Headers):** Use a `ThreadPoolExecutor(max_workers=8)` to fetch JSON payloads concurrently, reducing latency by ~85%.

---

### `[PERF-03]` Optional: In-Memory Byte Buffering for Large Video Artifacts
- **Location:** [`src/omnimash/storage/gcs.py#L744-L753`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L744-L753), [`#L610-L647`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L610-L647)
- **Problem:** `save_video_clip` and `save_character_sheet` frequently read entire files into Python `bytes` objects in memory before calling `upload_bytes`, doubling heap consumption for large clips.
- **Remedy:** Stream directly from disk using `upload_file` / `blob.upload_from_filename` whenever a local file path exists.

---

## Prioritized Remediation Roadmap

1. **PR 1: Security & Stability Hardening (Immediate Priority)**
   - `[SEC-01]`: Mitigate SSRF in `save_character_sheet` using `validate_remote_media_url` and `fetch_media_bytes`.
   - `[SEC-02]`: Enforce local path containment in `save_final_master` using `validate_local_media_path`.
   - `[SEC-03]`: Add `threading.Lock()` to `_SHARED_CLIENTS` for thread-safe client cache.
   - `[SEC-04]`: Inject `timeout=settings.gcs_timeout_seconds` across all GCS operations.
   - `[CORR-01]`: Replace silent `pass` blocks with structured `logger.warning` / `logger.error`.
   - `[CORR-02]`: Consolidate `/api/media-proxy` unquoting in `_normalize_media_source_path`.
   - `[CORR-03]`: Lazy-initialize `self._client` to eliminate blocking `gcloud` subprocess calls in tests.

2. **PR 2: Architecture & Performance Modernization**
   - `[READ-02]`, `[CORR-04]`: Extract unified `_guess_content_type` helper using `mimetypes.guess_type()`.
   - `[READ-01]`: Extract generic `_upload_json_payload` and `_download_json_payload` helpers to deduplicate ~250 lines of boilerplate.
   - `[ARCH-01]`: Expose clean public facade methods (`blob_exists`, `get_blob_metadata`, `delete_blob`).
   - `[PERF-01]`: Add `page_size` and eliminate eager `list()` materialization in `list_session_ids`.
   - `[PERF-02]`: Implement parallel JSON blob download via `ThreadPoolExecutor` for listing endpoints.
   - `[PERF-03]`: Prefer disk-to-cloud streaming over memory byte buffering in `save_video_clip`.
   - `[READ-03]`, `[READ-04]`: Document class alias and refine type annotations.
