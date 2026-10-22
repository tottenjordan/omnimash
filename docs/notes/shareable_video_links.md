# 7-Day Shareable Video Links & Main App Isolation Architecture

This document details the architecture, security isolation, and operational mechanics of the 7-day shareable video links feature in **omnimash**.

---

## 1. Architectural Motivation & Security Isolation

In enterprise environments, AI media generation platforms (such as OmniMash) are typically deployed in private networks, internal Google Cloud VPCs, or behind Cloud IAM / Identity-Aware Proxy (IAP) perimeters. Exposing the main application to the public internet introduces severe risks:
1. **DDoS & Scraping:** Public internet exposure exposes FastAPI application servers and Vertex AI / Gemini API quotas to unauthorized traffic.
2. **Bandwidth Saturation:** Streaming multi-gigabyte 720p/1080p/4k video files through application servers exhausts CPU threads and network I/O.
3. **Authentication Leakage:** Requiring external clients or partners to log into the main studio forces provisioning unnecessary internal IAM accounts.

### The Solution: Direct Google Cloud Storage (GCS) V4 Signed URLs

Instead of proxying shared video traffic through the main application:
1. The authenticated studio creator clicks **"Share Video (7 Days)"** in the OmniMash UI.
2. The FastAPI backend calls `GcsStorageManager.create_shareable_link()`, which generates a cryptographically signed V4 URL pointing directly to `storage.googleapis.com`.
3. When the recipient opens the link, their browser establishes an HTTPS connection **directly with Google Cloud Storage CDN**.
4. **Zero traffic reaches the OmniMash Cloud Run container or internal VPC.** The main application can remain 100% private and protected behind IAM/IAP.

```mermaid
flowchart TD
    subgraph PrivatePerimeter["Internal / Authenticated Studio (Private VPC / IAM / IAP)"]
        User["Internal Studio Creator"] -->|1. Clicks 'Share Video'| UI["OmniMash UI (SPA)"]
        UI -->|2. POST /api/share/create| API["FastAPI Backend (routers/share.py)"]
        API -->|3. create_shareable_link()| Storage["GcsStorageManager (storage/gcs.py)"]
        Storage -->|4. Cryptographic V4 Sign| Signer["GCS V4 Signer (IAM / SA)"]
        Signer -->|5. 7-Day Signed URL| Storage
        Storage -->|6. JSON Response| UI
        UI -->|7. Display Share Modal & Copy Link| User
    end

    subgraph PublicInternet["Public Internet (Zero Access to OmniMash Application)"]
        Recipient["External Recipient / Partner"]
        GCS["Google Cloud Storage Global CDN\n(storage.googleapis.com)"]
        
        User -.->|8. Shares link via Slack / Email / Chat| Recipient
        Recipient -->|9. GET https://storage.googleapis.com/...| GCS
        GCS -->|10. Direct Hardware-Accelerated MP4 Stream| Recipient
    end

    style PrivatePerimeter fill:#1e1e2e,stroke:#89b4fa,stroke-width:2px,color:#cdd6f4
    style PublicInternet fill:#181825,stroke:#a6e3a1,stroke-width:2px,color:#cdd6f4
```

---

## 2. GCS V4 Protocol & 7-Day Lifespan

Google Cloud Storage V4 signed URLs support an expiration of up to **7 days** (604,800 seconds).

### Signing Parameters
- `X-Goog-Algorithm=GOOG4-RSA-SHA256`
- `X-Goog-Credential=<service_account>/<date>/auto/storage/goog4_request`
- `X-Goog-Date=<ISO8601 UTC timestamp>`
- `X-Goog-Expires=604800` (7 days)
- `X-Goog-SignedHeaders=host`
- `X-Goog-Signature=<hex RSA-SHA256 signature>`
- `response-content-disposition=inline` (for direct in-browser streaming)
- `response-content-type=video/mp4` (ensures browser video player launches immediately)

### Download Link Variant
A dedicated download link is provided with:
`response-content-disposition=attachment; filename="<master_title>.mp4"`
This causes the browser to prompt the user to save the file locally rather than playing inline.

---

## 3. Resilient Multi-Environment Signing Strategy

To ensure deterministic testing, offline development, and zero developer lockouts:
1. **Production (Service Account Key or Cloud IAM `signBlob`):**
   Calls `blob.generate_signed_url(version="v4", expiration=timedelta(days=7), method="GET", ...)`.
2. **Local Development (User ADC without `signBlob`):**
   If local credentials lack IAM `signBlob` permissions, the engine logs a warning and returns a simulated signed URL format with an explanatory development note rather than throwing an unhandled exception or 500.
3. **Mock Mode (`mock_mode=True`):**
   Generates a deterministic V4 URL matching the exact query parameter structure for high-speed offline unit testing.

---

## 4. API Endpoints & Schemas

### `POST /api/share/create`

**Request (`CreateShareLinkRequest`):**
```json
{
  "session_name": "rap_battle_session",
  "video_url": "gs://omnimash-media-hybrid-vertex/sessions/s1/final_masters/master.mp4",
  "master_title": "master",
  "expiration_days": 7
}
```

**Response (`CreateShareLinkResponse`):**
```json
{
  "success": true,
  "share_url": "https://storage.googleapis.com/omnimash-media-hybrid-vertex/sessions/s1/final_masters/master.mp4?X-Goog-Algorithm=GOOG4-RSA-SHA256&...",
  "download_url": "https://storage.googleapis.com/omnimash-media-hybrid-vertex/sessions/s1/final_masters/master.mp4?X-Goog-Algorithm=GOOG4-RSA-SHA256&...&response-content-disposition=attachment...",
  "embed_snippet": "<video controls src=\"...\" width=\"100%\"><source src=\"...\" type=\"video/mp4\"></video>",
  "expires_at": "2026-10-29T01:40:00+00:00",
  "lifespan_days": 7,
  "gcs_uri": "gs://omnimash-media-hybrid-vertex/sessions/s1/final_masters/master.mp4",
  "filename": "master.mp4",
  "message": "Shareable link generated. Valid for 7 days until 2026-10-29T01:40:00+00:00."
}
```

---

## 5. UI Integration Points

1. **Act 3 Screening Room Toolbar:**
   `🔗 Share Video (7 Days)` button in the primary video controls toolbar.
2. **GCS Export Success Banner:**
   `🔗 Get Shareable Link (7 Days)` button directly inside the export confirmation card.
3. **Mode 3 (Journey 3) Stitched Master Card:**
   `🔗 Share Video (7 Days)` button next to the master stitch sequence action.
4. **Share Video Modal:**
   - Privacy disclosure explaining that the video streams from Google Cloud Storage without exposing the studio.
   - Read-only direct link input with 1-click clipboard copy (`✓ Copied!`).
   - "Preview in New Tab" link (`target="_blank"`).
   - "Copy Download URL" button.
   - "Copy Embed Code" button.
   - Escape key and backdrop dismissal.
