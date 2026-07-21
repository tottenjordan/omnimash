# Multimodal Base64 Reference Images & Image Role Tagging Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Supply native base64-encoded reference images (`{"type": "image", "data": b64_str, "mime_type": ...}`) to `gemini-omni-flash-preview` via `client.interactions.create`, mapping images to character roles via clean `[IMAGE N]: Reference image for Role X (Name)` tags without raw GCS path pollution.

---

## 📋 Execution Plan

### 1. 🖼️ Multimodal Reference Image Loader (`OmniFlashClient`)
- **Requirement**: Fetch and base64-encode character reference images from GCS/storage when constructing `input=[]` for `gemini-omni-flash-preview`.
- **Implementation**:
  - In `src/omnimash/engine/omni_client.py`:
    - Add helper `_load_reference_images_as_input(self, session_id: str | None, characters: list[CharacterRole]) -> tuple[list[dict], list[str]]`.
    - Reads character `reference_url` assets from GCS storage bucket (or local disk/proxy).
    - Base64-encodes image bytes into `{"type": "image", "data": b64_str, "mime_type": mime_type}`.
    - Generates corresponding role tag header lines: `[IMAGE 1]: Reference image for Role A (Harry).`

### 2. 🧹 Clean Prompt Compiler (`PromptCompiler`)
- **Requirement**: Remove raw `(Ref: gs://...)` path strings from compiled prompt text to avoid text pollution, and replace with clean `[IMAGE N]` tag mapping headers per Google Gemini Omni guidelines.
- **Implementation**:
  - Update `PromptCompiler.compile_multi_role_prompt(...)` in `src/omnimash/prompts/compiler.py`:
    - Strip raw `gs://` URIs from `role_lines`.
    - Prepend clean `[IMAGE ROLES]` mapping section if reference images are present.

### 3. 🧪 Unit & Integration Testing
- Add unit tests in `tests/engine/test_omni_client.py` and `tests/prompts/test_compiler.py` verifying:
  - Base64 payload generation and input array construction.
  - Image role tag mapping headers without `gs://` path strings in compiled prompts.
- Run `uv run pytest`.

---

## Tech Stack & Tools
Python 3.12, `google-genai` SDK, GCS Storage Client, FastAPI, pytest, uv, ruff, ty.

---

## Execution Tasks

### Task 1: Update PromptCompiler for Clean Image Role Tags
- Update `compile_multi_role_prompt` in `src/omnimash/prompts/compiler.py` to output clean `[IMAGE N]: Reference image for Role X` tags and strip raw `gs://` URIs from prompt strings.
- Add test assertions in `tests/prompts/test_compiler.py`.
- Run `uv run pytest tests/prompts/test_compiler.py`.

### Task 2: Update OmniFlashClient for Base64 Multimodal Reference Images
- Update `OmniFlashClient._generate_live_omni_flash_video` in `src/omnimash/engine/omni_client.py` to construct `input` arrays containing base64 image objects and text prompt objects.
- Add unit tests in `tests/engine/test_omni_client.py`.
- Run `uv run pytest tests/engine/test_omni_client.py`.

### Task 3: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
