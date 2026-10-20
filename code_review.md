# 5-Axes Code Review: `src/omnimash/engine` Module

**Reviewed Module:** `src/omnimash/engine/`
- `src/omnimash/engine/__init__.py` (0 lines)
- `src/omnimash/engine/omni_client.py` (2,724 lines)
- `src/omnimash/engine/telemetry.py` (130 lines)

**Companion Test Suite:** `tests/engine/`
- `tests/engine/test_omni_client.py` (2,663 lines)
- `tests/engine/test_omni_flash_1_1.py` (206 lines)
- `tests/engine/test_omni_retry.py` (165 lines)
- `tests/engine/test_telemetry.py` (139 lines)

---

## Executive Summary & Verdict

**Verdict: Request Changes**

The `src/omnimash/engine` module implements the core multimodal generation client for Gemini Omni Flash 1.1 (`gemini-omni-1.1-flash-preview`), Gemini image generation (`gemini-nano-banana-2.1`, `gemini-3-pro-image`), Responsible AI prompt abstraction, procedural fallback synthesis, and OpenTelemetry GenAI span logging.

While recent SDK modernizations (PR #168) aligned `Files.upload`, `ImageConfig(aspect_ratio=...)`, and OpenTelemetry error span status with `google-genai==2.31.0` and `opentelemetry-api==1.42.1`, a deep 5-axes inspection revealed **3 Critical** issues (SSRF/DoS and `.svg` path traversal in `_fetch_image_bytes`, plus broken `/static/...` path handling and temporary file leaks in `start_thread_from_video`), **7 Required** issues across correctness, architecture, performance, and readability (including a 2,724-line god module that exceeds the ~1,000-line boundary by 2.7x), **3 Optional/Consider** suggestions, and **3 Nits**.

---

## Findings Breakdown (Ordered by Leverage & Severity)

| Label | Axis | Location | Summary |
| :--- | :--- | :--- | :--- |
| **Critical:** | 4. Security | `omni_client.py:1947-2046` | SSRF via DNS resolution & HTTP redirects, unbounded `resp.read()` memory DoS, and `.svg` local path traversal in `_fetch_image_bytes` |
| **Critical:** | 1. Correctness | `omni_client.py:1851-1890` | `start_thread_from_video(regenerate_audio=True)` passes leading-slash URLs to FFmpeg, ignores non-zero exit codes, and leaks temporary `.mp4` files |
| **Critical:** | 4. Security / 1. Correctness | `omni_client.py:2279-2340`, `2531-2574` | Incomplete XML/HTML escaping (`&` and `'`) in `_get_mock_keyframe` and `_get_mock_ref_sheet` corrupts SVG DOM and allows entity injection |
| *(Required)* | 1. Correctness | `omni_client.py:791, 2276` | Shared mutable instance attribute `self.last_keyframe_prompt` causes data races across concurrent requests |
| *(Required)* | 1. Correctness | `omni_client.py:1042-1055` | `_log_multimodal_inference` starts and immediately ends OpenTelemetry spans post-hoc (~0ms duration) instead of timing inference execution |
| *(Required)* | 1. Correctness | `telemetry.py:115-119`, `omni_client.py:797` | `setup_opentelemetry_genai_logging` unconditionally overwrites `os.environ` on every `OmniFlashClient` instantiation |
| *(Required)* | 3. Architecture | `omni_client.py:1-2724` | 2,724-line God Module combining 5 distinct domains (procedural audio/video, RAI sanitization, telemetry parsing, media I/O, and GenAI client) |
| *(Required)* | 2. Readability & Simplicity | `omni_client.py:850-1055`, `1667-1829`, `2359-2700` | Severe code duplication across character normalization (5x), image generation boilerplate (2x), and video persistence (2x) |
| *(Required)* | 5. Performance | `omni_client.py:46-193` | Pure-Python per-sample audio synthesis loop (`441,000` iterations for 10s @ 44.1kHz) blocks the calling thread for ratusan ms |
| *(Required)* | 5. Performance | `omni_client.py:405-535`, `653` | 78 regex patterns re-compiled and executed sequentially on every `_abstract_prompt_for_responsible_ai` and guardrail check call |
| **Optional:** | 5. Performance | `omni_client.py:1089, 1183, 1205, 2374, 2400` | Sequential synchronous downloads in `_load_reference_images_as_input` and `generate_keyframe_image` (`N * RTT`) |
| **Optional:** | 1. Correctness | `omni_client.py:1533-1548, 1627-1637` | Retry loop skips backoff delay on 401/404 even when `switch_to_developer_api()` returns `False` (no Developer API key configured) |
| **Optional:** | 3. Architecture | `omni_client.py:14, 1739-1745` | `GenerationResult.duration_seconds` defaults to hardcoded `10` instead of reflecting requested `duration_seconds` |
| **Nit:** | 2. Readability | `omni_client.py:2416-2419` | Leftover `print(..., flush=True)` duplicates `logger.info` right above it in `generate_keyframe_image` |
| **Nit:** | 2. Readability | `omni_client.py:200, 1104, 1633, 1922, 1989, 2019` | Redundant inline `import re`, `import time`, `import tempfile` inside methods when already imported (or belong) at module top |
| **Nit:** | 3. Architecture | `engine/__init__.py`, `omni_client.py:764, 2723-2724` | Empty `__init__.py` alongside 3 redundant class aliases (`OmniFlashClient`, `OmniClient`, `OmniEngineClient`) |

---

## Detailed Axis-by-Axis Analysis & Structural Remedies

### Axis 1 & 4: Security & Correctness (Critical Findings)

#### 1. **Critical:** SSRF via DNS Resolution & Redirects, Unbounded HTTP Read DoS, and `.svg` Local Path Traversal in `_fetch_image_bytes`
- **Location:** [`src/omnimash/engine/omni_client.py:1947-2046`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1947-L2046)
- **Root Cause Analysis:**
  1. **`.svg` Local Path Traversal (`lines 1947-1956`):**
     ```python
     if ref_url.lower().endswith(".svg"):
         svg_raw = b""
         loc_path = os.path.join(os.getcwd(), ref_url.lstrip("/"))
         if os.path.exists(loc_path):
             with open(loc_path, "rb") as sf:
                 svg_raw = sf.read()
     ```
     Unlike the general local-file branch at `line 2021` (which resolves `os.path.realpath(ref_url)` and verifies it starts with `static/` or `/tmp/`), the `.svg` branch runs *first* and performs **no `realpath` or `allowed_roots` check**. A crafted `ref_url` such as `../../etc/something.svg` or `../secret.svg` bypasses directory confinement.
  2. **DNS Resolution & HTTP Redirect SSRF (`lines 1987-2015`):**
     `ipaddress.ip_address(hostname)` only parses literal IP strings. When `hostname` is a domain name that resolves to `127.0.0.1`, `169.254.169.254`, or private RFC1918 space (e.g., `127.0.0.1.nip.io` or an internal hostname), `ipaddress.ip_address(hostname)` raises `ValueError`, which is ignored by `except ValueError: pass` (`line 2008`). Furthermore, `urllib.request.urlopen` automatically follows HTTP `301/302/307/308` redirects to internal/loopback/metadata targets without re-validating the redirect target.
  3. **Unbounded Memory Read (`line 2014`):**
     `resp.read()` reads the entire HTTP response body into memory with no cap, allowing a remote server to stream an arbitrarily large payload and trigger an OOM crash.
- **Mutation Test Finding (Step 2 Verification):**
  Disabling the hostname check (`if False and (not hostname or ...):`) in `_fetch_image_bytes` resulted in **all 92 tests in `tests/engine/` passing** (`92 passed in 13.42s`). There is currently **zero unit test coverage in `tests/engine/`** for `_fetch_image_bytes` SSRF/path-traversal rejection.
- **Structural Remedy:**
  - Extract a dedicated media fetcher helper (e.g., `validate_and_resolve_local_path(path, allowed_roots)` and `safe_fetch_http_bytes(url, max_bytes=50 * 1024 * 1024)`).
  - Resolve DNS via `socket.getaddrinfo(hostname, None)` and verify *every* resolved IP address against `ip.is_private`, `ip.is_loopback`, `ip.is_link_local`, `ip.is_reserved`, and `ip.is_multicast`.
  - Use a custom `urllib.request.HTTPRedirectHandler` that re-validates redirect target URLs/IPs (or disables cross-host redirects), and cap reads at `max_bytes + 1` (`resp.read(MAX_FETCH_BYTES + 1)`).
  - Apply the same `allowed_roots` (`static/`, `/tmp/`) realpath check to `.svg` files before opening them.

---

#### 2. **Critical:** `start_thread_from_video(..., regenerate_audio=True)` Leading-Slash Bug, Unchecked FFmpeg Failure, and Temp File Leak
- **Location:** [`src/omnimash/engine/omni_client.py:1850-1890`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1850-L1890)
- **Root Cause Analysis:**
  ```python
  effective_base_video = base_video_url
  if regenerate_audio:
      stripped_path = f"static/rendered/{thread_id}_stripped_silent.mp4"
      os.makedirs(os.path.dirname(stripped_path), exist_ok=True)
      cmd = ["ffmpeg", "-y", "-i", base_video_url, "-c:v", "copy", "-an", stripped_path]
      try:
          subprocess.run(cmd, capture_output=True, check=False)
          effective_base_video = stripped_path
  ```
  1. Callers pass `base_video_url` as a web path starting with `/static/...` (e.g., `"/static/rendered/clip1.mp4"` in `test_start_thread_from_video_mock` at `line 158` and `test_omni_retry.py:147`). Passing `/static/rendered/clip1.mp4` directly to `ffmpeg -i` without `.lstrip("/")` causes FFmpeg to look at the root directory `/static/...`, which does not exist!
  2. `subprocess.run(cmd, capture_output=True, check=False)` ignores `res.returncode` and does not check whether `stripped_path` was actually created and non-empty before overwriting `effective_base_video = stripped_path`.
  3. `stripped_path` (`static/rendered/{thread_id}_stripped_silent.mp4`) is never cleaned up in a `finally:` block after `_generate_live_omni_flash_video` completes, leaking temporary `.mp4` files on disk on every call.
- **Structural Remedy:**
  - Normalize local `/static/...` paths via `input_path = base_video_url.lstrip("/") if base_video_url.startswith("/static/") else base_video_url`.
  - Check `if res.returncode == 0 and os.path.exists(stripped_path) and os.path.getsize(stripped_path) > 0: effective_base_video = stripped_path` (otherwise log a warning and keep `base_video_url`).
  - Wrap `_generate_live_omni_flash_video` in a `try ... finally:` block that removes `stripped_path` if it exists.

---

#### 3. **Critical:** Unescaped `&` and `'` in SVG Generation Corrupts XML and Enables SVG Entity/Markup Injection
- **Location:** [`src/omnimash/engine/omni_client.py:2279-2287`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L2279-L2287) (`_get_mock_keyframe`) and [`src/omnimash/engine/omni_client.py:2531-2542`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L2531-L2542) (`_get_mock_ref_sheet`)
- **Root Cause Analysis:**
  ```python
  clean_prompt = prompt.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
  ```
  `&` is never escaped! Any prompt, character name, description, style preset, or `aspect_ratio` containing `&` (e.g., `"R&B & Hip-Hop"` or `"Tom & Jerry"`) produces malformed XML (`<text>...R&B...</text>`) inside the `data:image/svg+xml;base64,...` URI, causing browsers to fail to render the SVG image completely. Furthermore, `aspect_ratio` (`lines 2336, 2556`) is interpolated into the SVG without any escaping at all.
- **Structural Remedy:**
  - Replace manual `.replace(...)` chains with `html.escape(value, quote=True)` for all interpolated SVG strings (`prompt`, `style_preset`, `style_tone`, `character_name`, `description`, and `aspect_ratio`).

---

### Axis 1: Correctness (Required Findings)

#### 4. **Required:** Shared Mutable Instance Attribute `self.last_keyframe_prompt` Race Condition
- **Location:** [`src/omnimash/engine/omni_client.py:791, 2276`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L2276)
- **Root Cause Analysis:**
  `OmniFlashClient` is instantiated once per `OmniMashAgent` singleton and shared across worker threads. `generate_keyframe_image` mutates `self.last_keyframe_prompt = prompt_text` at `line 2276`. When two concurrent requests generate keyframes simultaneously, Thread B overwrites `self.last_keyframe_prompt` before Thread A reads it (note that `generate_keyframe_image` already supports `return_compiled_prompt: bool = False`, which returns `(url, prompt_text)` cleanly without shared state!).
- **Structural Remedy:**
  - Store `last_keyframe_prompt` in a `contextvars.ContextVar` (or `threading.local`) behind a `@property def last_keyframe_prompt(self) -> str` so concurrent requests never overwrite each other's prompt, while preserving backward compatibility for callers reading `client.last_keyframe_prompt`.

#### 5. **Required:** `_log_multimodal_inference` Emits Post-Hoc Zero-Duration OpenTelemetry Spans
- **Location:** [`src/omnimash/engine/omni_client.py:1042-1055`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1042-L1055)
- **Root Cause Analysis:**
  ```python
  span = self.telemetry.start_inference_span(...)
  if span:
      span.end()
  ```
  `_log_multimodal_inference` is called *after* the model call and GCS upload have already completed, and immediately calls `span.end()` on the next line. Every `gen_ai.client.inference` span exported to Cloud Trace therefore reports a near-zero (~0.01ms) duration instead of the actual inference latency.
- **Structural Remedy:**
  - Pass `start_time_ns: int | None = None` (or `latency_ms: float | None = None`) into `_log_multimodal_inference` / `start_inference_span` (OpenTelemetry `tracer.start_span(..., start_time=start_time_ns)` natively accepts `start_time` in nanoseconds, or record `gen_ai.client.inference.duration_ms` as a span attribute) so Cloud Trace spans accurately reflect model inference duration.

#### 6. **Required:** `setup_opentelemetry_genai_logging` Unconditionally Overwrites `os.environ` on Every `OmniFlashClient` Init
- **Location:** [`src/omnimash/engine/telemetry.py:115-119`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/telemetry.py#L115-L119) and [`src/omnimash/engine/omni_client.py:797`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L797)
- **Root Cause Analysis:**
  `setup_opentelemetry_genai_logging` uses direct assignment (`os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = ...`), mutating global process environment variables every time `OmniFlashClient()` is instantiated and overriding any environment configuration set by the deployment environment.
- **Structural Remedy:**
  - Use `os.environ.setdefault(...)` in `setup_opentelemetry_genai_logging` so existing environment overrides are respected while still setting defaults when unset.

---

### Axis 2 & 3: Architecture, Readability & Simplicity (Required Findings)

#### 7. **Required:** 2,724-Line God Module (`src/omnimash/engine/omni_client.py`)
- **Location:** [`src/omnimash/engine/omni_client.py:1-2724`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1-L2724)
- **Root Cause Analysis:**
  At 2,724 lines, `omni_client.py` is nearly 3x the ~1,000-line module health threshold. A single file currently owns five distinct architectural concerns:
  1. **Offline Audio & FFmpeg Procedural Renderer** (`_generate_dynamic_audio_wav`, `extract_clean_dialogue_summary`, `ensure_rendered_video` — 342 lines)
  2. **Responsible AI Prompt Sanitizer & Guardrail Error Analyzer** (`_abstract_prompt_for_responsible_ai`, `parse_guardrail_error_guidance`, `_get_relaxed_safety_settings` — 377 lines)
  3. **Multimodal Telemetry URI Extractor** (`_log_multimodal_inference` — 205 lines)
  4. **Media Fetcher & Multimodal Payload Builder** (`_load_reference_images_as_input`, `_build_multimodal_contents`, `_render_svg_to_png_bytes`, `_fetch_image_bytes` — 550 lines)
  5. **Gemini Omni Flash & Image Generation Client** (`OmniFlashClient` video & image generation methods — 1,250 lines)
- **Structural Remedy (Split Large File into Focused Submodules):**
  Decompose `src/omnimash/engine/` into focused modules while re-exporting public symbols from `src/omnimash/engine/omni_client.py` and `src/omnimash/engine/__init__.py` to maintain 100% backward compatibility with existing imports and test patches:
  - `src/omnimash/engine/procedural_renderer.py`: `_generate_dynamic_audio_wav`, `extract_clean_dialogue_summary`, `ensure_rendered_video`
  - `src/omnimash/engine/guardrails.py`: `_abstract_prompt_for_responsible_ai`, `parse_guardrail_error_guidance`, `_get_relaxed_safety_settings`
  - `src/omnimash/engine/media_loader.py`: SSRF-safe media fetching, SVG rendering, and character normalization helpers
  - `src/omnimash/engine/omni_client.py`: `OmniFlashClient` and `GenerationResult`

#### 8. **Required:** Severe Code Duplication Across Character Extraction, Image Generation, and Video Persistence
- **Location:**
  - Character dict/object unpacking duplicated **5 times**: [`omni_client.py:556-573`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L556-L573), [`894-920`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L894-L920), [`943-967`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L943-L967), [`1074-1085`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1074-L1085), [`2069-2104`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L2069-L2104).
  - `_log_multimodal_inference` (`lines 880-1008`) uses 125 lines of deeply nested `if/elif/for` loops to extract `reference_image_uris` and `prompt_text` from `str | dict | list`.
  - `generate_keyframe_image` (`lines 2359-2489`) and `generate_character_reference_sheet` (`lines 2579-2693`) duplicate ~110 lines of `genai.Client` creation, `Part.from_bytes` wrapping, `GenerateContentConfig` construction, candidate `thought=True` filtering, base64 decoding, and GCS upload.
  - `generate_clip` (`lines 1667-1745`) and `apply_interaction_diff` (`lines 1747-1829`) duplicate 95% of their body (path sanitization, calling `_generate_live_omni_flash_video`, mock procedural fallback, and GCS intermediate upload).
- **Structural Remedy:**
  - Extract a single canonical `_ coerce_character_roles(characters)` / `_extract_character_uris(characters)` helper.
  - Extract `_extract_telemetry_prompt_and_uris(input_prompt, characters, keyframe_image_url, reference_image_uris)` to replace the 125-line nested conditional block in `_log_multimodal_inference`.
  - Extract `_execute_gemini_image_generation(contents, prompt_text, image_model, aspect_ratio, blob_prefix, fallback_fn)` shared by `generate_keyframe_image` and `generate_character_reference_sheet`.

---

### Axis 5: Performance (Required Findings)

#### 9. **Required:** Pure-Python Per-Sample Audio Synthesis Loop (`_generate_dynamic_audio_wav`)
- **Location:** [`src/omnimash/engine/omni_client.py:46-193`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L46-L193)
- **Root Cause Analysis:**
  `_generate_dynamic_audio_wav` defaults to `duration: int = 10` at `sample_rate = 44100`, running `for i in range(441_000):` in pure Python bytecode with multiple `math.sin`, `math.exp`, and `audio_data.append(...)` calls per sample (~300ms of CPU-bound GIL contention for a 10s clip). Notice also that `struct.pack(f"<{len(audio_data)}h", *audio_data)` at `line 189` unpacks a 441,000-element list into `*args` on the CPython call stack!
- **Structural Remedy:**
  - Synthesize a single 2-bar loop cycle (`loop_samples = int(sample_rate * min(duration, 2.0))`) into an `array.array("h")` buffer and tile/slice it to `total_samples` before writing with `wf.writeframes(buf.tobytes())`. This cuts CPU time and memory allocations by **5x** for 10-second clips and eliminates the 441,000-arg `*audio_data` stack unpacking.

#### 10. **Required:** Repeated Compilation of 78 Regex Patterns on Every Call (`_abstract_prompt_for_responsible_ai` & `parse_guardrail_error_guidance`)
- **Location:** [`src/omnimash/engine/omni_client.py:405-535`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L405-L535) and [`653`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L653)
- **Root Cause Analysis:**
  `_abstract_prompt_for_responsible_ai` reconstructs a 75-key dictionary and calls `re.compile` / `re.sub` 78 times on every invocation. `parse_guardrail_error_guidance` also calls `re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")` on every invocation.
- **Structural Remedy:**
  - Hoist `_PROTECTED_TOKEN_PATTERN`, `_RAI_REPLACEMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...]`, `_REF_IMAGE_TAG_PATTERN`, `_GS_URI_PATTERN`, and `_FULL_NAME_PATTERN` to module-level pre-compiled constants.

---

### Optional / Consider Findings

1. **Optional:** **Parallelize Reference Image Downloads (`omni_client.py:1089, 2396`):**
   - When loading multiple character reference sheets (`_load_reference_images_as_input` and `generate_keyframe_image`), fetching `gs://` blobs sequentially incurs `N * RTT`. Consider fetching multiple reference URLs concurrently with a bounded `ThreadPoolExecutor(max_workers=4)` while preserving deterministic character role ordering.
2. **Optional:** **Respect Backoff Delay on 401/404 When No Developer API Fallback Exists (`omni_client.py:1533-1548, 1627-1637`):**
   - When a `401` or `404` occurs on Vertex AI, `self.switch_to_developer_api()` is called and `time.sleep(delay)` is skipped so the Developer API client can be tried immediately. However, if `self._dev_client` is `None` (`switch_to_developer_api()` returns `False`), skipping `time.sleep(delay)` causes the loop to retry the same failing Vertex AI client immediately. Consider only skipping `time.sleep(delay)` when `switched_client` is `True`.
3. **Optional:** **Propagate `duration_seconds` into `GenerationResult` (`omni_client.py:1667-1829`):**
   - `GenerationResult.duration_seconds` is always `10` because `generate_clip` and `apply_interaction_diff` do not pass `duration_seconds` when constructing `GenerationResult`.

---

### Nit Findings

1. **Nit:** Remove duplicate `print(f"\n==================== [KEYFRAME PROMPT SENT TO GEMINI] ...", flush=True)` at [`omni_client.py:2416-2419`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L2416-L2419) since `logger.info` already logs the exact same banner on `lines 2412-2415`.
2. **Nit:** Remove redundant inline imports (`import re` at `line 200`, `import tempfile` at `lines 1104, 2019`, `import time` at `line 1633`) and move `import io`, `import ipaddress`, `import tempfile`, and `import html` to the top of the module.
3. **Nit:** Export `OmniFlashClient`, `OmniClient`, `OmniEngineClient`, `GenerationResult`, and `GenAITelemetryLogger` in [`src/omnimash/engine/__init__.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/__init__.py) with an explicit `__all__`.

---

## Dead Code Hygiene

During inspection of `src/omnimash/engine/`, the following unused/redundant elements were identified:
1. **`audio_stem: str | None = None` parameter in `ensure_rendered_video` (`omni_client.py:228`):**
   - Passed by `generate_clip`, `apply_interaction_diff`, and `start_thread_from_video`, but never referenced anywhere inside `ensure_rendered_video`. (Kept in signature for caller compatibility, or can be wired/documented.)
2. **Duplicate alias exports in `omni_client.py` (`lines 764, 2723-2724`):**
   - `get_relaxed_safety_settings = _get_relaxed_safety_settings`
   - `OmniClient = OmniFlashClient`
   - `OmniEngineClient = OmniFlashClient`
   - *Note:* `OmniClient` and `OmniEngineClient` are still imported in `tests/engine/test_omni_client.py` (`lines 9, 2234`) and `src/omnimash/agent/orchestrator.py`, so they should remain as backward-compatible aliases until callers are consolidated.

---

## The Review Checklist

### Context
- [x] I understand what this module does and why

### Correctness
- [x] Change matches spec/task requirements
- [ ] Edge cases handled (`start_thread_from_video` `/static/` leading-slash & FFmpeg exit code check needed)
- [ ] Error paths handled (`start_thread_from_video` temp file cleanup needed)
- [ ] Tests cover the module adequately (missing SSRF/path-traversal unit tests on `_fetch_image_bytes`, verified via mutation testing)

### Readability
- [x] Names are clear and consistent
- [ ] Logic is straightforward (`_log_multimodal_inference` URI extraction and duplicated image/video generation methods need simplification)
- [ ] No unnecessary complexity

### Architecture
- [x] Follows existing patterns
- [x] No unnecessary coupling or dependencies
- [ ] Appropriate abstraction level
- [ ] File stays within a healthy size (`omni_client.py` is 2,724 lines; needs decomposition into focused modules)

### Security
- [x] No secrets in code
- [ ] Input validated at boundaries (`_fetch_image_bytes` needs `.svg` realpath confinement, DNS-resolved IP validation, redirect validation, and bounded HTTP read size; SVG generators need `html.escape`)
- [ ] No injection vulnerabilities (SVG `&` / XML escaping needed)
- [x] Auth checks in place
- [ ] External data sources treated as untrusted (HTTP image fetch needs `MAX_FETCH_BYTES` cap)

### Performance
- [x] No N+1 patterns
- [ ] No unbounded operations (`resp.read()` in `_fetch_image_bytes`; 441,000-sample Python loop in `_generate_dynamic_audio_wav`; repeated regex compilation in `_abstract_prompt_for_responsible_ai`)
- [x] Pagination on list endpoints (N/A for engine module)

### Verification
- [x] Existing tests pass (`92 passed` in `tests/engine/`)
- [x] Linter and type checker pass (`uv run ruff check`, `uv run ty check`)
- [x] Mutation testing performed on `_fetch_image_bytes`

### Verdict
- [ ] **Approve** — Ready to merge
- [x] **Request changes** — Critical and Required issues documented above should be addressed
