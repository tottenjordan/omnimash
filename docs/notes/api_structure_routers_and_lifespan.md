# API Structure: Routers, Schemas & Lifespan Startup

How the FastAPI layer under `src/omnimash/api/` is organized after the
Phase 5 refactor of the codebase-review remediation. Prior to this the whole
API (models + all endpoints + ~1,860 lines of embedded React UI) lived in a
single `app.py`, and the agent + ffmpeg warm-up ran at **import time**.

## Module layout
- `api/app.py` — **wiring only**. `create_app()` builds the `FastAPI`, constructs
  the agent, stores it on `app.state.agent`, registers the external-service
  exception handler, mounts `/static`, and `include_router`s each domain router.
  Keeps `app = create_app()` at the bottom (Dockerfile uses `--factory`, but the
  module-level `app` stays for compatibility). Re-exports the schema models and
  helpers (`create_app`, `GenerateRequest`, `_parse_range_header`,
  `_load_ui_html`, …) so `from omnimash.api.app import ...` keeps working.
- `api/schemas.py` — all pydantic request/response models plus the identifier
  sanitizer (`SafeIdentifier`/`OptSafeIdentifier` via `sanitize_path_segment`)
  and the reference-URL host allow-list validator. No dependency on app wiring,
  so it imports cleanly anywhere (no import cycles).
- `api/deps.py` — shared FastAPI dependencies: `get_agent(request)` returns
  `request.app.state.agent`; `load_ui_html()` reads+caches the dashboard asset
  (`_load_ui_html` kept as a backward-compatible alias).
- `api/routers/` — one `APIRouter` per domain:
  - `sessions.py` — `GET /` (dashboard HTML) + `GET /api/sessions`
  - `generation.py` — generate/diff, commit, save-final, stitch-clips,
    extend-scene, deconstruct-concept, research, extract-reference
  - `characters.py` — character + roster save/load/list
  - `media.py` — `GET /api/media-proxy` (holds `_parse_range_header`)

Handlers stay **sync `def`** on purpose (FastAPI runs them on the threadpool;
the blocking GCS/ffmpeg work must not sit on the event loop).

## Startup / lifespan (no import-time I/O)
The ffmpeg warm-up (`ensure_rendered_video`) runs **only** inside a FastAPI
`lifespan` handler, so importing `omnimash.api.app` — or building the app with
`create_app()` — shells out to nothing. The warm-up fires on server startup
(uvicorn) or when a test enters the `TestClient` context manager.

**Gotcha:** the agent is constructed in `create_app`, *not* in `lifespan`,
because the existing tests use `TestClient(app)` **without** a `with` block, so
the lifespan never runs for them. Putting the agent in `app.state` during
`create_app` keeps those non-context tests working while still deferring the
ffmpeg side effect. If you move agent construction into `lifespan`, every
non-context `TestClient` test breaks (`app.state.agent` unset).

Regression test: `tests/api/test_app.py::test_import_and_create_app_do_not_run_ffmpeg_warmup`
asserts import + `create_app()` never call `ensure_rendered_video`, and that
entering the `TestClient` context runs it exactly once.
