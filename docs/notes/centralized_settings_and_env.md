# 🔒 Centralized Settings (`OmniMashSettings`) & `.env` Isolation

## 📌 Context & Best Practices
To prevent API keys, Google Cloud project identifiers, and Cloud Storage bucket names from leaking into git repositories, OmniMash uses **centralized, type-safe settings** powered by `pydantic-settings`.

---

## 🏗️ Architecture

1. **`.env.example`**: Committed template containing all configurable cloud keys, defaults, and resource placeholders (`GOOGLE_CLOUD_PROJECT`, `OMNIMASH_GCS_BUCKET`, `GEMINI_API_KEY`, `MODEL_ARMOR_TEMPLATE_ID`).
2. **`.gitignore` Protection**: `.env`, `.env.local`, `credentials.json`, and private keys are strictly excluded from git tracking.
3. **`OmniMashSettings` (`src/omnimash/config.py`)**:
   - Single source of truth loaded automatically from `.env` or system environment.
   - Dynamic GCS bucket derivation: if `OMNIMASH_GCS_BUCKET` is not explicitly defined, it defaults automatically to `omnimash-media-{GOOGLE_CLOUD_PROJECT}`.

---

## 🚀 Usage

```python
from omnimash.config import settings

# Access type-safe configuration everywhere
project = settings.google_cloud_project
bucket = settings.gcs_bucket_name
is_mock = settings.mock_mode
```
