# Engine Module SDK Best Practices & Modernization (`src/omnimash/engine`)

This note captures non-derivable SDK quirks and official best-practice patterns verified during the Source-Driven Development review of `src/omnimash/engine/` (`omni_client.py` and `telemetry.py`).

---

## 1. Detected Package Versions

- **`google-genai==2.31.0`** (`pyproject.toml`: `google-genai>=1.0.0`)
- **`opentelemetry-api==1.42.1`** & **`opentelemetry-sdk==1.42.1`** (`pyproject.toml`: `>=1.20.0`)
- **`pillow==12.3.0`** (`pyproject.toml`: `pillow>=10.0.0`)
- **`google-cloud-storage==3.17.1`** (`pyproject.toml`: `>=2.14.0`)

---

## 2. `google-genai` v2.31.0 Quirks & Best Practices

### `client.files.upload()` Signature & Vertex AI Guard
- **Official Signature:**
  ```python
  upload(
      self,
      *,
      file: Union[str, os.PathLike[str], io.IOBase],
      config: Optional[types.UploadFileConfigOrDict] = None,
  ) -> types.File
  ```
- **Gotcha 1 (`mime_type` kwarg):** Passing `mime_type=...` directly as a top-level keyword argument to `client.files.upload()` raises `TypeError: Files.upload() got an unexpected keyword argument 'mime_type'`. Always pass `mime_type` inside `config=types.UploadFileConfig(mime_type=mime_type)`.
- **Gotcha 2 (Vertex AI restriction):** `client.files.upload()` is only supported on the Gemini Developer API client (`vertexai=False`). Calling it on a Vertex AI client (`vertexai=True`) raises `ValueError: This method is only supported in the Gemini Developer client.`. In `_load_reference_images_as_input()`, large (>25 MB) media files only use `files.upload` when a non-Vertex Developer API client (`vertexai is not True`) is available, falling back to inline base64 payloads otherwise.
- **Reference:** https://googleapis.github.io/python-genai/ & https://ai.google.dev/gemini-api/docs/files

### `types.ImageConfig(aspect_ratio=...)` in `GenerateContentConfig`
- For Gemini image generation models (`gemini-nano-banana-2.1` and `gemini-3-pro-image`), output aspect ratio (`"16:9"`, `"9:16"`, `"1:1"`, etc.) is configured via `image_config=types.ImageConfig(aspect_ratio=aspect_ratio)` inside `types.GenerateContentConfig`:
  ```python
  config = genai.types.GenerateContentConfig(
      safety_settings=_get_relaxed_safety_settings(),
      image_config=genai.types.ImageConfig(aspect_ratio=aspect_ratio),
  )
  ```
- Both `generate_keyframe_image()` and `generate_character_reference_sheet()` also close their per-call `image_client` via `image_client.close()` in a `finally:` block to prevent underlying `httpx.Client` connection pool leaks while remaining compatible with unit tests that patch `google.genai.Client` per call.
- **Reference:** https://ai.google.dev/gemini-api/docs/image-generation#aspect_ratios & https://googleapis.github.io/python-genai/#client-context-managers

---

## 3. OpenTelemetry GenAI Span Error Status (`telemetry.py`)

- In `GenAITelemetryLogger.start_inference_span()`, when `error_code` is provided, the span status is explicitly marked with `span.set_status(Status(StatusCode.ERROR, str(error_code)))` in addition to setting the `"gen_ai.error.code"` attribute.
- Note that `"gen_ai.system": "vertex_ai"` is intentionally retained in `build_telemetry_labels()` to preserve backward compatibility with existing Cloud Trace queries and unit test assertions in `tests/engine/test_telemetry.py`.
- **Reference:** https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
