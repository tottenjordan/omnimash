# Gemini Omni Flash Safety Guardrails & Real-Person Likeness Policy

This note documents operational gotchas, policy enforcement triggers, error codes, naming/reference best practices, and the automatic safety abstractor (`REAL_NAME_MAPPINGS` in `src/omnimash/prompts/compiler.py`) for handling Google Gemini Omni Flash (`gemini-omni-flash-preview`) safety policies.

---

## 🚨 400 Error Code & Policy Enforcement

When generating video clips or conversational diffs with `gemini-omni-flash-preview`, prompt inputs or reference image assets that violate Google's Real-Person Likeness and Trademark Safety Policies trigger an immediate HTTP `400` error:

> **400 Error Code:** `Input blocked: Sorry, we can't create videos with real people's names or likenesses.`

Even when configuring relaxed safety settings (`BLOCK_NONE`), Google's server-side safety gateway enforces zero-tolerance blocking for real-person names, public figures, trademarked items, and real human photographs.

---

## ⚡ Trigger Conditions

The 400 safety block is triggered by any of the following four conditions:

### 1. Full Real-World Human Names
* **Description:** Specifying full first + last names of real-world non-public or public individuals.
* **Examples:** `"Jordan Totten"`, `"John Smith"`.
* **Root Cause:** Gemini Omni Flash flags two-word real-name formats as potential real-person identifiers.

### 2. Public Figures & Athletes
* **Description:** Referencing known celebrities, public figures, musical artists, or professional athletes (by full name or distinctive single-word surname/handle).
* **Examples:** `"Francesco Totti"` / `"Totti"`, `"Yo Gotti"`, `"Gordon Ramsay"`, `"Drake"`, `"Travis Scott"`.
* **Root Cause:** Public figure likeness protection triggers server-side input rejection.

### 3. Trademarked Pop-Culture Items
* **Description:** Including protected brand names, fictional artifacts, or trademarked pop-culture vehicles/props in prompt text or role names.
* **Examples:** `"Golden Snitch"`, `"Lightsaber"`, `"Batmobile"`, `"Burberry"`, `"Dark Mark"`.
* **Root Cause:** Intellectual property and brand trademark filters block prompt generation.

### 4. Real Human Photographs Attached to Reference Roles (`@Image1`)
* **Description:** Attaching actual photographic portraits or real human facial photos as reference images in `CharacterRole` bindings (`reference_url` / `@Image1`).
* **Root Cause:** Multimodal vision analysis detects real human facial features in attached reference images and rejects video generation to prevent deepfake synthesis.

---

## 💡 Best Practices & Mitigations

### 1. Character Naming Best Practices
* **Use Single-Word Handles & Stylized Titles:** Avoid full real names. Use stylized parody handles, single-word nicknames, or fantasy wizard titles.
* **Examples:**
  - Instead of `"Jordan Totten"` $\rightarrow$ Use `"J-Totts"`, `"Jordy"`, or `"Tha Plug"`.
  - Instead of `"Gordon Ramsay"` $\rightarrow$ Use `"Fiery Chef Blood"`.
  - Instead of `"Severus Snape"` $\rightarrow$ Use `"Potion Master"`.

### 2. Character Reference Best Practices
* **Use 1-Click AI Turnaround Sheet Generation:** Never upload real human photographs as reference image assets.
* **Workflow:** Generate stylized, non-photorealistic AI character turnaround sheets (e.g., stylized 3D animation keyframes or digital illustration turnaround sheets via `gemini-3.1-flash-image`) from the Project-Level Character Vault instead of uploading real human photos.

---

## 🛡️ Automatic Safety Gateway Abstractor (`REAL_NAME_MAPPINGS`)

OmniMash provides automated mitigation via `sanitize_real_names()` in [`src/omnimash/prompts/compiler.py`](../../src/omnimash/prompts/compiler.py):

* **`REAL_NAME_MAPPINGS` / `REAL_NAME_PARODY_MAP`:** A regex-based dictionary in `compiler.py` that intercepts and rewrites real human names, public figure identifiers, trademarked items, street slang, and tattoo signifiers into safe parody descriptors prior to sending requests to the Gemini API.
* **Abstracted Mapping Examples:**
  - `Gordon Ramsay` $\rightarrow$ `Fiery Chef Blood`
  - `Francesco Totti` / `Totti` $\rightarrow$ `a tatted wizard`
  - `Golden Snitch` $\rightarrow$ `glowing golden flying orb`
  - `Lightsaber` $\rightarrow$ `laser sword`
  - `Batmobile` $\rightarrow$ `armored tactical vehicle`
  - `stepped on` $\rightarrow$ `diluted`
  - `tear drop tattoo` $\rightarrow$ `facial ink accent`
