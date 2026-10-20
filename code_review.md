# 5-Axes Code Review: `src/omnimash/ingestion` Module

**Scope:**
- [src/omnimash/ingestion/__init__.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/__init__.py) (1 line)
- [src/omnimash/ingestion/media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py) (361 lines)
- [tests/ingestion/test_media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/tests/ingestion/test_media_extractor.py) (185 lines)

**Review Framework:** 5-Axes Code Review (`Correctness`, `Readability & Simplicity`, `Architecture`, `Security`, `Performance`)

---

## Executive Summary

| Severity | Count | Summary |
| :--- | :---: | :--- |
| **Critical** | **3** | SSRF / arbitrary extractor invocation via unvalidated URL in `_extract_youtube_metadata` (`SEC-01`); path traversal via unsanitized `session_id` in `analyze_youtube_reference` & `process_youtube_url` (`SEC-02`); `PermissionError` crash on `/static/...` paths in `crop_3s_motion_reference` (`COR-01`) |
| **Required** (no prefix) | **6** | Predictable `/tmp/mock_frame_*.jpg` symlink/race vulnerability & dead code (`SEC-03`); missing `NaN`/`inf`/negative duration validation in `extract_reference_video_clip` (`COR-02`); `research_parody_clash` ignoring `subject` & `aesthetic` parameters (`COR-03`); repetitive 3x keyframe boilerplate in `analyze_youtube_reference` (`RED-01`); missing public exports in `src/omnimash/ingestion/__init__.py` (`ARC-01`); redundant disk copies & sequential GCS uploads (`PER-01`) |
| **Nit / Optional** | **2** | Lazy `from omnimash.config import settings` inside `MediaExtractor.__init__` (`NIT-01`); magic numbers for canvas dimensions and colors in `_generate_keyframe_jpeg` (`NIT-02`) |

**Verdict:** **Request Changes** — Resolve the 3 Critical and 6 Required findings before production sign-off.

---

## Prioritized Findings (Ordered by Leverage)

### 1. Security & Correctness Blockers (`Critical`)

#### `SEC-01` — **Critical:** Unvalidated URL Scheme & Extractor Scope in `_extract_youtube_metadata` Enables SSRF and Arbitrary `yt-dlp` Extractor Execution
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L69-L106)
- **Axis:** Security
- **Problem:**
  `_extract_youtube_metadata(self, url: str)` passes any caller-supplied `url` directly into `yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)` without validating the URL scheme, hostname, or resolved IP address, and without restricting `allowed_extractors` in `ydl_opts`. Because `POST /api/extract-reference` ([media.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/routers/media.py#L253-L257)) forwards `req.url` directly to `analyze_youtube_reference`, an attacker when `mock_mode=False` can supply:
  - `http://169.254.169.254/latest/meta-data/` or internal RFC-1918/loopback URLs (causing `yt-dlp`'s generic extractor to probe internal services and potentially leak page titles/metadata in `ReferenceAnalysisReport.video_title`), or
  - `file:///...` or non-YouTube URLs.
- **Structural Remedy:**
  1. Validate `url` using `urllib.parse.urlparse(url)`: require `scheme in ("http", "https")`, verify the hostname belongs to an explicit YouTube host allowlist (`youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`, `music.youtube.com`), and validate via `validate_remote_media_url(url)` (from `omnimash.engine.media_loader`) to block private/loopback/metadata DNS resolution.
  2. Restrict `ydl_opts["allowed_extractors"] = ["youtube", "youtube:tab"]` so `yt-dlp` refuses to fall back to the `generic` HTTP scraper.

---

#### `SEC-02` — **Critical:** Path Traversal via Unsanitized `session_id` in `analyze_youtube_reference` and `process_youtube_url`
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L157-L190)
- **Axis:** Security
- **Problem:**
  `analyze_youtube_reference` interpolates `session_id` directly into a local filesystem directory path:
  ```python
  sid = session_id or "default"
  local_dir = f"static/sessions/{sid}/references"
  os.makedirs(local_dir, exist_ok=True)
  ```
  Furthermore, `POST /api/extract-reference` ([media.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/routers/media.py#L253-L257)) passes `req.session_name` directly into `analyze_youtube_reference` without calling `validate_safe_identifier`. A crafted `session_id` such as `"../../../tmp/arbitrary_dir"` escapes `static/sessions/` and writes `frame_1.jpg`, `frame_2.jpg`, and `frame_3.jpg` to arbitrary writable locations on disk.
- **Structural Remedy:**
  Add a `_sanitize_session_id(session_id: str | None) -> str` helper in `MediaExtractor` (enforcing `^[a-zA-Z0-9_\-]+$` and raising `ValueError` on traversal characters `..`, `/`, `\`, or null bytes) and verify `os.path.realpath(local_dir)` is strictly confined under `os.path.realpath("static/sessions")`. Also validate `req.session_name` in `POST /api/extract-reference`.

---

#### `COR-01` — **Critical:** `crop_3s_motion_reference` Crashes with `PermissionError` on `/static/...` URLs Returned by `/api/upload`
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L284-L343)
- **Axis:** Correctness / Security
- **Problem:**
  When a user uploads a motion reference video via `POST /api/upload`, the endpoint returns `{"url": "/static/uploads/<filename>.mp4"}` (with a leading `/`). When the frontend passes that URL to `POST /api/motion-reference/upload`, `crop_3s_motion_reference` and `extract_reference_video_clip` treat `"/static/uploads/<filename>.mp4"` as an absolute OS filesystem path `/static/...` rather than the workspace-relative `static/uploads/...`:
  1. `os.makedirs("/static/uploads", exist_ok=True)` raises `PermissionError: [Errno 13] Permission denied: '/static'` on Linux, causing `POST /api/motion-reference/upload` to fail with HTTP 500!
  2. Even if `output_clip_path` is in a writable directory, `source_video_path = "/static/uploads/..."` does not exist at `/static/...`, so `ffmpeg` fails and falls back to writing a 24-byte `ftyp` stub.
  3. Additionally, if `source_video_path` begins with `-`, `ffmpeg` interprets it as a CLI flag.
- **Structural Remedy:**
  Normalize leading `/static/` paths in `crop_3s_motion_reference` and `extract_reference_video_clip` (`path.lstrip("/")` when `path.startswith("/static/")`), validate that local input and output paths resolve inside allowed roots (`static/` or `/tmp/`), reject paths starting with `-`, and preserve the `/static/...` URL prefix in the returned value when the caller passed a `/static/...` URL (or return the normalized playable path consistently).

---

### 2. Required Changes (No Prefix — Must Address Before Merge)

#### `SEC-03` — Predictable `/tmp/mock_frame_*.jpg` Writes Create Symlink/TOCTOU Risk and Cross-Worker Races
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L210-L219)
- **Axis:** Security / Correctness / Dead Code Hygiene
- **Problem:**
  `analyze_youtube_reference` unconditionally copies all 3 keyframes to hardcoded global paths `/tmp/mock_frame_1.jpg`, `/tmp/mock_frame_2.jpg`, and `/tmp/mock_frame_3.jpg`.
  1. Zero callers in `src/` or `tests/` read `/tmp/mock_frame_*.jpg`.
  2. `shutil.copyfile(src, "/tmp/mock_frame_1.jpg")` in shared `/tmp` is vulnerable to CWE-377 symlink attacks and causes concurrent `pytest-xdist` workers and concurrent requests to clobber each other's files.
- **Structural Remedy:**
  Remove the dead `/tmp/mock_frame_*.jpg` copy loop entirely.

---

#### `COR-02` — Missing Validation for `NaN`, `inf`, and Non-Positive `duration_seconds` in `extract_reference_video_clip`
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L284-L312)
- **Axis:** Correctness
- **Problem:**
  - `start_time_seconds = max(0.0, float(start_time_seconds))` does not check `math.isfinite(...)`, allowing `float("nan")` or `float("inf")` to be passed to `ffmpeg -ss`.
  - `duration_seconds` is never validated or clamped: passing `duration_seconds <= 0` or `NaN`/`inf` causes `ffmpeg -t` to fail immediately.
- **Structural Remedy:**
  Validate both `start_time_seconds` and `duration_seconds` with `math.isfinite(...)`, clamp `start_time_seconds >= 0.0`, and clamp `duration_seconds` to a valid range (e.g., `0.1 <= duration_seconds <= 60.0`, defaulting to `3.0` if non-finite or `<= 0`).

---

#### `COR-03` — `research_parody_clash` Completely Ignores `subject` and `aesthetic` Inputs
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L268-L282)
- **Axis:** Correctness
- **Problem:**
  `research_parody_clash(self, subject: str, aesthetic: str) -> ParodyResearchResult` ignores both `subject` and `aesthetic` parameters and always returns a static Harry Potter / Atlanta Trap synopsis even when the user queries a completely different subject or aesthetic via `POST /api/research`.
- **Structural Remedy:**
  Incorporate cleaned `subject` and `aesthetic` inputs into `ParodyResearchResult` (`synopsis`, `suggested_vibe`, `suggested_audio`, `suggested_dialogue`, and `suggested_props`) when custom inputs are provided while preserving the rich Hogwarts/Atlanta Trap defaults when those inputs match or are empty.

---

#### `RED-01` — Duplicated 3x Keyframe Generation, Upload, and Annotation Blocks in `analyze_youtube_reference`
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L187-L263)
- **Axis:** Readability & Simplicity
- **Problem:**
  `analyze_youtube_reference` manually writes out `f1_path`, `f2_path`, `f3_path`, 3 calls to `_generate_keyframe_jpeg`, 3 calls to `self.storage.upload_file`, and 3 `KeyframeAnnotation` objects across 75 lines of repetitive code.
- **Structural Remedy:**
  Replace the 3x copy-pasted blocks with a declarative `_REFERENCE_KEYFRAME_SPECS` tuple and a single loop or comprehension.

---

#### `ARC-01` — `src/omnimash/ingestion/__init__.py` Exports No Public Symbols
- **Location:** [__init__.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/__init__.py#L1)
- **Axis:** Architecture
- **Problem:**
  Unlike `src/omnimash/engine/__init__.py`, `src/omnimash/ingestion/__init__.py` does not re-export `MediaExtractor`, `ExtractedReference`, `KeyframeAnnotation`, `ParodyResearchResult`, or `ReferenceAnalysisReport`, nor does it define `__all__`.
- **Structural Remedy:**
  Re-export the public dataclasses and `MediaExtractor` in `src/omnimash/ingestion/__init__.py` with an explicit `__all__`.

---

#### `PER-01` — Sequential Keyframe Generation & GCS Uploads in `analyze_youtube_reference`
- **Location:** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L191-L239)
- **Axis:** Performance
- **Problem:**
  In live mode, `analyze_youtube_reference` uploads 3 keyframe JPEGs to GCS sequentially (`upload_file` × 3), multiplying network RTT by 3, and performs 3 redundant synchronous file copies to `/tmp/mock_frame_*.jpg`.
- **Structural Remedy:**
  Eliminate the redundant `/tmp/mock_frame_*.jpg` copies (`SEC-03`) and execute the 3 keyframe generation + GCS upload tasks concurrently via `concurrent.futures.ThreadPoolExecutor(max_workers=3)` when `not self.storage.mock_mode` (or in a clean helper).

---

### 3. Nits & Optional Suggestions

- **`NIT-01` (Nit):** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L60) imports `from omnimash.config import settings` inside `__init__`. Moving `from omnimash.config import settings` to module top-level matches the rest of the codebase.
- **`NIT-02` (Nit):** [media_extractor.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/ingestion/media_extractor.py#L122-L154) uses inline magic numbers (`1280`, `720`, `90`) in `_generate_keyframe_jpeg`; extracting named module constants (`KEYFRAME_WIDTH = 1280`, `KEYFRAME_HEIGHT = 720`, `JPEG_QUALITY = 90`) improves self-documentation.

---

## Review Checklist

- [x] **Context:** Reviewed `src/omnimash/ingestion` (`__init__.py`, `media_extractor.py`) and all callers (`orchestrator.py`, `api/routers/media.py`, `tests/ingestion/test_media_extractor.py`).
- [ ] **Correctness:** `COR-01`, `COR-02`, and `COR-03` must be resolved.
- [ ] **Readability:** `RED-01` (3x duplicated keyframe generation/upload blocks) should be collapsed into a data-driven loop.
- [ ] **Architecture:** `ARC-01` (`__init__.py` public exports) should be added.
- [ ] **Security:** `SEC-01` (URL/extractor validation in `_extract_youtube_metadata`), `SEC-02` (`session_id` path traversal prevention), and `SEC-03` (removal of predictable `/tmp/mock_frame_*.jpg` writes) must be resolved.
- [ ] **Performance:** `PER-01` (remove redundant `/tmp` copies and parallelize live GCS uploads).
- [x] **Verification:** Existing 8 unit tests in `tests/ingestion/test_media_extractor.py` pass; new regression tests are needed for `SEC-01`, `SEC-02`, `COR-01`, `COR-02`, and `COR-03`.
