# Code Quality Review: `src/omnimash/stitching` Module

**Review Date:** October 20, 2026  
**Target Module:** [`src/omnimash/stitching/`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching) (`stitcher.py`, `audio_overlay.py`, `__init__.py`)  
**Evaluation Framework:** 5-Axes Code Quality (Correctness, Readability, Architecture, Security, Performance)  
**Approval Standard:** Request Changes (Actionable remediation required prior to production release)

---

## Executive Summary

The `src/omnimash/stitching` module is responsible for video timeline assembly, audio stem mixing, dialogue ducking, title card generation, and master artifact delivery to Google Cloud Storage. 

While the core FFmpeg filtergraph design (`sidechaincompress`, `concat` demuxer, `lavfi anullsrc`) demonstrates a solid understanding of multimedia pipelines, the module exhibits critical security vulnerabilities (unbounded SSRF via `urllib.request.urlretrieve` and unconfined `/static/` path resolution), correctness bugs (single quotes breaking the FFmpeg concat demuxer parser, unhandled empty clip lists causing `FileNotFoundError`, and silent failure text files disguised as media clips), and architectural fragmentation (three duplicated, divergent implementations of media path resolution).

---

## 5-Axes Findings Summary

| Axis | Critical | Required | Optional | Nit | Total |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Correctness** | 1 | 3 | 1 | 0 | **5** |
| **2. Readability & Simplicity** | 0 | 2 | 1 | 1 | **4** |
| **3. Architecture** | 0 | 3 | 1 | 1 | **5** |
| **4. Security** | 2 | 1 | 0 | 0 | **3** |
| **5. Performance** | 0 | 2 | 1 | 0 | **3** |
| **Total** | **3** | **11** | **4** | **2** | **20** |

---

## Severity-Labeled Detailed Findings

### Axis 1: Correctness

#### `[CORR-01]` Critical: Empty `clip_paths` in `concatenate_clips` Causes Unhandled `FileNotFoundError` on GCS Upload
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L48-L86`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L48-L86), [`L245-L250`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L245-L250)
- **Problem:** If `clip_paths` is empty (`[]`) in non-mock mode, `resolved_clips` evaluates to `[]`. The `if resolved_clips:` block is skipped entirely, meaning `out_path` is never created. Execution immediately proceeds to line 250: `self.storage.upload_file(out_path, ...)`, raising a fatal `FileNotFoundError`.
- **Structural Remedy:** Guard against empty inputs at the function entrypoint:
  ```python
  if not clip_paths:
      raise ValueError("concatenate_clips requires at least one clip path.")
  ```

#### `[CORR-02]` Required: FFmpeg Concat Demuxer Syntax Error on Unescaped Single Quotes
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L135-L138`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L135-L138)
- **Problem:** In `concatenate_clips`, file paths are written to the concat manifest using `f"file '{clip_file}'\n"`. Per official FFmpeg concat demuxer documentation, single quotes within file paths must be escaped (`'\''`). If a clip name contains a single quote (e.g. `director's_cut.mp4`), FFmpeg crashes with a manifest syntax error.
- **Structural Remedy:** Sanitize and escape single quotes before writing:
  ```python
  escaped_path = clip_file.replace("'", "'\\''")
  f.write(f"file '{escaped_path}'\n")
  ```

#### `[CORR-03]` Required: Silent Failure Writes Plaintext Disguised as Media Files
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L273-L275`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L273-L275), [`L380-L385`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L380-L385), [`src/omnimash/stitching/audio_overlay.py#L121-L126`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L121-L126)
- **Problem:** When title card generation or audio ducking fails, the code writes ASCII text strings (e.g. `"fallback title card video content"` or `"fallback ducked audio content"`) into files with `.mp4` and `.aac` extensions. In `stitcher.py#L144-L149`, an ad-hoc byte sniffer reads the first 64 bytes to detect this placeholder. Passing these corrupt text files into downstream FFmpeg concat commands causes mysterious downstream rendering crashes.
- **Structural Remedy:** Replace disguised corrupt text writes with proper structured error raising (`RuntimeError`) or return `None` so the orchestrator can fall back cleanly without byte-sniffing corrupted files.

#### `[CORR-04]` Required: Unchecked Returncode on FFmpeg Re-encode Fallback
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L236`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L236)
- **Problem:** In `concatenate_clips`, if the fast `-c copy` pass fails (e.g. mismatched codecs/resolutions), it falls back to `cmd_reencode`. However, `subprocess.run(cmd_reencode, capture_output=True, text=True)` does not check `res.returncode` and does not set `check=True`. If the re-encode fails, the error is swallowed and line 250 attempts to upload an incomplete or missing file.
- **Structural Remedy:** Check `res.returncode != 0`, log `res.stderr`, and raise a descriptive `RuntimeError` if re-encoding fails.

#### `[CORR-05]` Optional: Title Card Insertion Order Inversion on Equal Indices
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L423-L445`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L423-L445)
- **Problem:** `title_cards` are sorted by `insert_at` in reverse order before insertion. If multiple cards specify identical `insert_at` indices (or invalid strings that fail `int(insert_at)`), their relative sequence is inverted or can trigger unhandled `ValueError`.
- **Structural Remedy:** Validate `insert_at` with safe integer coercion and preserve stable insertion order.

---

### Axis 2: Readability & Simplicity

#### `[READ-01]` Required: Replace Ad-Hoc Temporary File Lists with `tempfile.TemporaryDirectory`
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L55`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L55), [`L237-L244`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L237-L244), [`src/omnimash/stitching/audio_overlay.py#L49`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L49), [`L128-L133`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L128-L133)
- **Problem:** `temp_cleanup_paths: list[str] = []` and `temp_files: list[str] = []` require manual append calls after every file creation and manual loops in `finally:` blocks. If an unhandled exception or SIGTERM occurs before registration, files leak on disk.
- **Structural Remedy:** Use `tempfile.TemporaryDirectory()` context manager. All intermediate clips, manifests, and audio stems are placed in the scoped directory and cleaned up automatically in one step.

#### `[READ-02]` Required: Flatten Nested TrueType / Pillow Font Loading Ladder
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L304-L314`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L304-L314)
- **Problem:** Three levels of deeply nested `try...except` ladders attempt font loading with duplicate magic strings and fallback logic.
- **Structural Remedy:** Extract a clean helper:
  ```python
  def _get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
      for candidate in (font_name, "DejaVuSans.ttf", "Arial.ttf"):
          try:
              return ImageFont.truetype(candidate, size)
          except Exception:
              continue
      return ImageFont.load_default(size=size)
  ```

#### `[READ-03]` Optional: Inlined Dynamic Import of `settings` Inside Methods
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L28`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L28), [`src/omnimash/stitching/audio_overlay.py#L30`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L30)
- **Problem:** `from omnimash.config import settings` is imported inside method bodies. There are no circular import issues between `config` and `stitching`.
- **Structural Remedy:** Move `from omnimash.config import settings` to top-level imports.

#### `[READ-04]` Nit: Inconsistent Logging Formats
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L11`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L11), [`src/omnimash/stitching/audio_overlay.py#L6`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L6)
- **Problem:** Logger naming uses `logging.getLogger(__name__)`, which is standard, but log messages mix f-strings and `%s` arguments inconsistently.
- **Structural Remedy:** Standardize on lazy formatting `%s` throughout.

---

### Axis 3: Architecture & Design

#### `[ARCH-01]` Required: Unify Triplicated Media Path Resolution into a Canonical Helper
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L58-L86`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L58-L86), [`L88-L129`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L88-L129), [`src/omnimash/stitching/audio_overlay.py#L51-L84`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L51-L84)
- **Problem:** Media resolution logic is implemented three times with divergent capabilities:
  1. `stitcher.py` clip loop: does not decode `/api/media-proxy`, does not support HTTP URLs, accesses private `_bucket`.
  2. `stitcher.py` audio block: supports HTTP URLs via insecure `urlretrieve`, does not decode `/api/media-proxy`.
  3. `audio_overlay.py` `_resolve_audio_input`: decodes `/api/media-proxy`, downloads GCS blobs via `download_blob_bytes`, but ignores HTTP URLs.
- **Structural Remedy:** Collapse into a single canonical helper `resolve_media_source_to_local_path(source: str, temp_dir: str, storage: GcsStorageManager) -> str` used by both `VideoStitcher` and `apply_dialogue_audio_ducking`.

#### `[ARCH-02]` Required: Eliminate Direct Private `_bucket` Access and GCS Prefix String Hacks
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L68-L80`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L68-L80)
- **Problem:** `stitcher.py` accesses `self.storage._bucket` directly and attempts to parse blob names with:
  `blob_name = norm_clip.replace(f"gs://{self.storage.bucket_name}/", "").lstrip("/")`
  If `norm_clip` is in another bucket (or an HTTPS GCS URL), this string replacement fails, and `self.storage._bucket.blob(...)` crashes.
- **Structural Remedy:** Delegate blob retrieval to `self.storage.download_blob_bytes(uri)` or a public `storage.download_to_file(uri, dest_path)`.

#### `[ARCH-03]` Required: Export Public API Symbols in `src/omnimash/stitching/__init__.py`
- **File & Lines:** [`src/omnimash/stitching/__init__.py#L1`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/__init__.py#L1)
- **Problem:** `__init__.py` is completely empty. Callers must know internal module filenames (`omnimash.stitching.stitcher`, `omnimash.stitching.audio_overlay`).
- **Structural Remedy:** Export `VideoStitcher` and `apply_dialogue_audio_ducking` in `__init__.py` with `__all__`.

#### `[ARCH-04]` Optional: Unused Dependency `ffmpeg-python` in `pyproject.toml`
- **File & Lines:** [`pyproject.toml#L10`](file:///usr/local/google/home/jordantotten/omnimash/pyproject.toml#L10)
- **Problem:** `ffmpeg-python>=0.2.0` is declared in project dependencies, but is unmaintained and never imported anywhere in the project.
- **Structural Remedy:** Remove `ffmpeg-python` via `uv remove ffmpeg-python` to eliminate dead weight and security footprint.

#### `[ARCH-05]` Nit: Pass Explicit Aspect Ratio Type or Enum
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L260`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L260), [`L279-L285`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L279-L285)
- **Problem:** `aspect_ratio: str = "16:9"` uses raw string mapping with an arbitrary dictionary fallback.
- **Structural Remedy:** Use `Literal["16:9", "9:16", "1:1", "21:9"]` for explicit typing.

---

### Axis 4: Security

#### `[SEC-01]` Critical: Server-Side Request Forgery (SSRF) via Insecure `urllib.request.urlretrieve`
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L114-L126`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L114-L126)
- **Problem:** In `concatenate_clips`, when `norm_audio` starts with `http://` or `https://`, it executes `urllib.request.urlretrieve(norm_audio, tmp_audio_path)`.
  1. No hostname validation (allows requests to `169.254.169.254`, `localhost`, or internal VPC IPs).
  2. No request timeout (vulnerable to Slowloris DoS).
  3. No file size ceiling (vulnerable to disk exhaustion via unbounded streams).
- **Structural Remedy:** Enforce validation using `validate_remote_media_url` and download safely using `safe_fetch_remote_bytes(url, max_bytes=MAX_MEDIA_FETCH_BYTES)` from `omnimash.engine.media_loader`.

#### `[SEC-02]` Critical: Unconfined Path Traversal in `/static/` File Resolution
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L62-L65`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L62-L65), [`L92-L95`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L92-L95), [`src/omnimash/stitching/audio_overlay.py#L63-L66`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L63-L66)
- **Problem:** In both files, paths starting with `/static/` are resolved via:
  `loc = os.path.join(os.getcwd(), norm_clip.lstrip("/"))`
  If a user passes `/static/../../etc/passwd` or `/static/../../../app/.env`, `os.path.join` traverses out of the intended directory.
- **Structural Remedy:** Enforce directory confinement using `validate_local_media_path` from `omnimash.engine.media_loader`.

#### `[SEC-03]` Required: Missing Subprocess Execution Timeouts (Process Hang / Resource Exhaustion)
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L191`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L191), [`L236`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L236), [`L377`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L377), [`src/omnimash/stitching/audio_overlay.py#L118`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L118)
- **Problem:** All FFmpeg invocations run `subprocess.run(cmd, ...)` with NO `timeout` parameter. Corrupt video streams or malformed inputs can hang FFmpeg indefinitely, freezing worker processes and exhausting thread pools.
- **Structural Remedy:** Pass `timeout=settings.ffmpeg_timeout_seconds` (default 120s) and handle `subprocess.TimeoutExpired` with proper error logging and process cleanup.

---

### Axis 5: Performance

#### `[PERF-01]` Required: Dialogue Audio Ducking Muffled by FFmpeg `amix` Normalization Default
- **File & Lines:** [`src/omnimash/stitching/audio_overlay.py#L95-L99`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/audio_overlay.py#L95-L99)
- **Problem:** The filtergraph sets `amix=inputs=2:duration=first[aout]`. In FFmpeg, `amix` defaults to `normalize=true`, which divides the volume of each input stream by 2 (-6dB). Because the background music was already ducked by `sidechaincompress`, attenuating the speech track by -6dB results in muffled dialogue.
- **Structural Remedy:** Specify `amix=inputs=2:duration=first:dropout_transition=0:normalize=0`.

#### `[PERF-02]` Required: FFmpeg Re-encode Fallback Lacks Framerate Normalization
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L205-L235`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L205-L235)
- **Problem:** In `cmd_reencode`, `-r 24` is omitted, while `generate_title_card_clip` enforces `-r 24`. Concatenating clips with differing or variable framerates causes video stutter and timestamp drift during re-encoding.
- **Structural Remedy:** Add `-r 24` and `-pix_fmt yuv420p` to ensure smooth playback and stream alignment.

#### `[PERF-03]` Optional: Synchronous Sequential Clip Downloads from GCS
- **File & Lines:** [`src/omnimash/stitching/stitcher.py#L58-L86`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L58-L86)
- **Problem:** Clips stored in GCS are downloaded sequentially in a blocking `for` loop. When stitching 5 to 10 clips for a long master video, network latency compounds.
- **Structural Remedy:** Download clips concurrently using a `ThreadPoolExecutor` when multiple GCS URIs are detected.

---

## Remediation Plan Blueprint

To ensure clean isolation, thorough testing, and minimal execution time, we propose organizing the fixes into **two parallel PRs**:

```
                              ┌────────────────────────────────────────┐
                              │  PR 1: Security & Path Confinement     │
                              │  - Safe remote media fetch (SSRF fix)  │
                              │  - Local /static/ path confinement     │
                              │  - Subprocess timeouts                 │
                              │  - Concat demuxer quote escaping       │
                              │  - Empty clip_paths guard              │
                              └────────────────────────────────────────┘
                                                 │
                                                 ▼
┌───────────────────────────┐ ┌────────────────────────────────────────┐
│ main (Green: 503 passing) │ │  PR 2: Architecture & Audio Modernize  │
└───────────────────────────┘ │  - Unified canonical media resolution  │
                              │  - FFmpeg amix normalize=0 (0dB voice) │
                              │  - Tempfile.TemporaryDirectory cleanup │
                              │  - Public __init__.py exports          │
                              │  - Remove unused ffmpeg-python dep     │
                              └────────────────────────────────────────┘
```

### Proposed PR 1: Security, Input Validation & Subprocess Hardening
- Remediates: `SEC-01`, `SEC-02`, `SEC-03`, `CORR-01`, `CORR-02`, `CORR-04`
- Estimated Diff: ~120 lines changed
- Scope: In `stitcher.py` and `audio_overlay.py`, wire SSRF validation, path confinement, subprocess timeouts, and concat single-quote escaping.

### Proposed PR 2: Architecture Unification, Audio Modernization & Cleanup
- Remediates: `ARCH-01`, `ARCH-02`, `ARCH-03`, `ARCH-04`, `PERF-01`, `PERF-02`, `READ-01`, `READ-02`, `CORR-03`
- Estimated Diff: ~150 lines changed
- Scope: Unified media resolver helper, `tempfile.TemporaryDirectory`, `amix normalize=0`, `__init__.py` exports, and removal of unused `ffmpeg-python` dependency.

---

## Verification Strategy
- **Unit & Integration Suite:** `uv run pytest tests/stitching/ -v`
- **Full Test Suite:** `uv run pytest`
- **Linting:** `uv run ruff check .`
- **Static Typing:** `uv run ty check`
