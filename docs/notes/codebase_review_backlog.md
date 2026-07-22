# Codebase Review Backlog (2026-07-22)

Point-in-time audit of ~6,100 LOC / 22 modules via parallel per-area review. Findings are ordered by severity. **Re-verify line numbers before acting** — files change. Related: [architecture_omnimash.md](architecture_omnimash.md), [request_lifecycle.md](request_lifecycle.md), [centralized_settings_and_env.md](centralized_settings_and_env.md), [gcs_artifact_persistence.md](gcs_artifact_persistence.md).

> Static review only: `ruff`/`ty`/`pytest` could not run in-session (sandbox gets HTTP 401 from the private package registry `us-python.pkg.dev/artifact-foundry-prod`). Re-run these locally to confirm.

## Critical
- **`/api/media-proxy` = arbitrary GCS read** (`api/app.py:2258` → `storage/gcs.py:195`). Only checks `startswith("gs://")`, then `download_blob_bytes` parses the *bucket from the user URI* (`self._client.bucket(bucket_name)`), so it reads any object in any bucket the SA can access. Verified firsthand. Fix: rebuild key from validated session + allowlisted bucket; require auth.
- **Guardrail is a stub** (`security/guardrail.py:11`). `ModelArmorGuardrail` ignores `mock_mode`; only substring-matches `"illegal"`/`"hate speech"`. No real Model Armor call exists. Only 2 call sites (`orchestrator.py:84,253`).
- **`mock_mode` defaults `True`** (`config.py:16`) → silent fake behavior in prod if env var unset.

## High
- **Guardrail bypass**: `compiled_override` + free-text fields (`voiceover`, scene `action`/`dialogue`, character `description`) never validated; only `prompt or concept` is (`orchestrator.py:82-195`).
- **Path traversal into GCS keys**: `session_name`/`master_title`/`slug`/`category` free-form; `build_session_blob_path` (`gcs.py:114`) only `basename`s filename. No server-side validators anywhere in the API.
- **SSRF**: `/api/extract-reference` + `/api/research` take plain-`str` URLs (extractor currently a stub, so latent).
- **No error handling** around external calls in `orchestrator.py` + all API handlers → raw 500s, orphaned partial work, some `success=True` on empty saves.
- **Session state** (`state/session_manager.py:34`): in-memory dict, no lock (race), dies on restart, breaks with >1 worker, unbounded.
- **Silent-failure GCS layer** (`gcs.py`, ~8 `except Exception: pass` / fabricated success URLs). Uploads return fake public URL even on throw.
- **ffmpeg**: no `timeout=` on any `subprocess.run` (`omni_client.py:325,372`, `stitcher.py:52,71`); stitcher ignores returncode and uploads possibly-broken master.
- **Tooling**: no CI, no `[tool.ruff]`/`[tool.ty]` config despite CODE_STANDARDS mandate.

## Medium (themes)
- `api/app.py` monolith: lines 144–2007 are an embedded React/HTML `UI_HTML` string (CDN Babel at runtime); only ~270 lines are real API. Extract to static asset + split routers.
- Import-time side effects: `app = create_app()` + `root_agent` build full dep graph (GCS, ffmpeg warm-up) at import. Move to FastAPI `lifespan`.
- `media_proxy` buffers whole file to RAM, no HTTP Range → no video seeking.
- Prompt compiler: style-keyword tuples duplicated 3×; `known_lore` duplicates `CHARACTER_LORE_ANCHORS`; `_deconstruct_fallback` ~320-line data monolith (`compiler.py:891-1213`).
- Retry logic: no jitter (thundering herd), doubles possibly-zero base delay, classifies retryability by substring-matching `str(exc)` (`omni_client.py:819-870`).
- Clip generation fully sequential; independent clips could use a `ThreadPoolExecutor`.
- Fixed temp filenames collide under concurrency, never cleaned (`temp_silent.wav`, `concat_list.txt`, `/tmp/mock_frame_1.jpg`).
- GCS client re-instantiated per manager (+ `lookup_bucket` in ctor); no GCS timeouts/retry policy.
- Config: API keys plain `str` (use `SecretStr`); no validation keys/bucket exist when not mocking.
- Hardcoded model IDs / locations / timeouts / ffmpeg presets scattered vs `config.py`.
- Test gaps: no error-path tests; guardrail tests lock in insecure behavior; real ffmpeg path untested; no `pytest-cov`.
- Role-ID collision for 5+ named characters (`compiler.py:1085` clamps to last label).

## Low
Dead code (`compile_storyboard` pass-through, unused `audio_stem`, dead Tier-1 replacements); `pyproject.toml` placeholder description; `get_public_url` assumes public bucket (private → 403); `_get_session` touches `SessionManager._sessions` private state.

## Already good (don't "fix")
Handlers are sync `def` on purpose (FastAPI threadpool) — no blocking-in-`async` bugs. No bare `except:`, no `print()`, no mutable-default-arg bugs. Test layout mirrors `src/`. `.env` gitignored.
