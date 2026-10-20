# API Architecture & Framework Modernization

## 📌 Context & Motivation
During the Source-Driven Development review of `src/omnimash/api`, the API implementation was audited against current official documentation for FastAPI (`0.141.1`), Pydantic (`2.14.1`), and Starlette (`1.7.0`). The goal of this audit is to ensure all patterns adhere to modern framework standards, eliminate deprecated conventions, and establish architectural guidelines for future API expansions.

---

## 🛠️ Stack & Version Specifications
- **Python:** 3.12 (`requires-python = ">=3.12"`)
- **Web Framework:** FastAPI `0.141.1` (backed by Starlette `1.7.0`)
- **Data Validation & Serialization:** Pydantic `2.14.1`
- **ASGI Server:** Uvicorn `0.54.0`
- **Environment & Build Management:** `uv`

---

## 📐 Key Modernization Patterns & Best Practices

### 1. Application Lifecycle: Lifespan Context Manager
- **Anti-Pattern:** Running heavy mock asset generation, warmup procedures, or external network calls synchronously during app creation or module import (`create_app` execution).
- **Modern Standard:** FastAPI replaces legacy `startup` and `shutdown` event handlers with the `lifespan` parameter:
  ```python
  from contextlib import asynccontextmanager
  from fastapi import FastAPI


  @asynccontextmanager
  async def lifespan(app: FastAPI):
      # Startup phase: Initialize warmups, caches, and mock assets
      from omnimash.engine.omni_client import ensure_rendered_video

      ensure_rendered_video("/static/rendered/mock.mp4", prompt="Trapwarts trailer")
      yield
      # Shutdown phase: Clean up client connections or temp directories if needed
```
- **Official Source:** [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/#lifespan)

---

### 2. Parameter Declarations: PEP 593 `Annotated`
- **Anti-Pattern:** Assigning framework markers as default function argument values (e.g. `file: UploadFile = File(...)`). The ellipsis `...` was an idiom from Pydantic v1 / older FastAPI versions.
- **Modern Standard:** Use `typing.Annotated` (PEP 593):
  ```python
  from typing import Annotated
  from fastapi import File, UploadFile


  @app.post("/api/upload")
  async def upload_media_file(file: Annotated[UploadFile, File()]): ...
```
- **Benefits:** Keeps parameter defaults clean, enables standard static type checking without false positives, and aligns with FastAPI's primary documentation pattern.
- **Official Source:** [FastAPI Request Files with Annotated](https://fastapi.tiangolo.com/tutorial/request-files/#file-parameters-with-uploadfile)

---

### 3. Pydantic v2 Collection Defaults: `Field(default_factory=list)`
- **Anti-Pattern:** Setting mutable default literals on model fields (e.g. `aesthetic_tags: list[str] = []` or `data: dict = {}`).
- **Modern Standard:** Use `Field(default_factory=...)` consistently:
  ```python
  from typing import Any
  from pydantic import BaseModel, Field


  class CharacterRoleModel(BaseModel):
      role_id: str
      name: str = ""
      description: str = ""
      reference_url: str | None = None
      aesthetic_tags: list[str] = Field(default_factory=list)
```
- **Benefits:** Prevents accidental shared mutable state between model instances, silences linter warnings (e.g. Ruff B006 / Flake8 W0102), and produces explicit OpenAPI schemas.
- **Official Source:** [Pydantic Fields — Default Values](https://docs.pydantic.dev/latest/concepts/fields/#default-values)

---

### 4. Pydantic Type Specialization: Parameterized `dict[str, Any]`
- **Anti-Pattern:** Using unadorned `dict` in type unions (e.g. `characters: list[CharacterRoleModel | dict] | None = None`).
- **Modern Standard:** Explicitly parameterize dict types as `dict[str, Any]`:
  ```python
  characters: list[CharacterRoleModel | dict[str, Any]] | None = None
```
- **Official Source:** [Pydantic Types — Standard Library Types](https://docs.pydantic.dev/latest/concepts/types/#standard-library-types)

---

### 5. Dependency Injection with `Depends`
- **Anti-Pattern:** Relying on closure variables across thousands of lines inside a monolithic `create_app` function.
- **Modern Standard:** Expose shared application state (`app.state.agent`) via FastAPI dependency providers:
  ```python
  from typing import Annotated
  from fastapi import Depends, Request
  from omnimash.agent.orchestrator import OmniMashAgent


  def get_agent(request: Request) -> OmniMashAgent:
      return request.app.state.agent


  AgentDep = Annotated[OmniMashAgent, Depends(get_agent)]
```
- **Benefits:** Allows seamless dependency overriding during testing via `app.dependency_overrides[get_agent] = mock_agent`.
- **Official Source:** [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)

---

### 6. Media Streaming & Range Requests (`media_proxy`)
- **Current Approach:** Reading complete blob bytes into RAM (`download_blob_bytes(uri)`) and slicing sub-arrays for HTTP 206 Partial Content responses.
- **Modern Standard for Large Files:** Use Starlette's `StreamingResponse` with an async generator for video files >10MB to avoid large memory allocations during concurrent stream scrubbing in the browser video player.
- **Official Source:** [Starlette StreamingResponse](https://www.starlette.io/responses/#streamingresponse)

---

### 7. Dependency Grooming: `sse-starlette`
- `sse-starlette>=3.5.0` is currently declared in `pyproject.toml` but is unused across `src/omnimash/api`.
- Future milestone: Introduce Server-Sent Events (`EventSourceResponse`) to stream real-time progress for long-running batch video renders and storyboard generation. If unneeded, it should be pruned via `uv remove sse-starlette`.
