# Code Review: `src/omnimash/prompts` Module

**Review Target:** `src/omnimash/prompts/` (`__init__.py`, `character_roles.py`, `compiler.py`, `storyboard_agent.py`, `taxonomy.py`)  
**Review Standard:** Multi-dimensional 5-axes framework (`Correctness`, `Readability & Simplicity`, `Architecture`, `Security`, `Performance`)  
**Date:** 2026-10-20  

---

## Executive Summary

The `src/omnimash/prompts/` module defines the core prompt compilation, screenplay parsing, character role normalization, aesthetic taxonomy, and multi-shot storyboard expansion engines powering OmniMash's video generation with Gemini Omni Flash (`gemini-omni-1.1-flash-preview`).

While the module recently adopted `google-genai` structured outputs, `pydantic` schemas, and Python 3.12 `StrEnum`, thorough inspection across the 5 axes reveals significant structural, architectural, and performance technical debt:
1. **Severe Architectural Duplication & Shadowing:** `parse_timecoded_script` is implemented with completely diverging logic in two separate files (`compiler.py` and `storyboard_agent.py`), leading to subtle semantic divergences and silent shadowing.
2. **Monolithic Mega-File Degradation:** `src/omnimash/prompts/compiler.py` has grown to 3,172 lines, housing disjoint responsibilities (celebrity parody dictionaries, screenplay regex parsers, voice style resolvers, multi-role prompt compilers, and LLM deconstruction clients).
3. **Inefficient O(N * M) Repeated Regex & Substring Loops:** Multiple functions re-compile regular expressions inside loops or perform quadratic nested string scans across character arrays and candidate tokens.
4. **ReDoS / Backtracking Vulnerability in Screenplay Regex:** Unanchored, overlapping greedy/non-greedy regex alternatives in `_extract_character_dialogue` and `parse_screenplay_script` pose catastrophic backtracking risks on long user screenplays.

---

## Severity-Labeled Findings Breakdown

### 1. Correctness

- **Critical: Diverging Implementations of `parse_timecoded_script` in `compiler.py` vs `storyboard_agent.py`**
  - **Location:** `src/omnimash/prompts/compiler.py:1125` and `src/omnimash/prompts/storyboard_agent.py:163`
  - **Issue:** Both modules define a public function named `parse_timecoded_script`, but their signatures and behaviors drastically diverge:
    - `compiler.py` takes `(script_text, characters=None, char_tag_map=None)` and handles screenplay parentheticals and dialogue tag injection.
    - `storyboard_agent.py` takes `(script_text, default_duration=30.0)` and chunks scripts exceeding 10 seconds into sequential shot intervals (`[0-10s]`, `[10-20s]`).
    - Depending on which file a caller imports `parse_timecoded_script` from, dialogue extraction or 10-second chunking is silently bypassed.
  - **Remedy:** Unify into a single canonical screenplay parser module (`src/omnimash/prompts/screenplay.py`), consolidating chunking and tag injection into a single predictable pipeline.

- **Required: Missing Boundary Clamping for Single-Digit Timecode Durations in `compiler.py:parse_timecoded_script`**
  - **Location:** `src/omnimash/prompts/compiler.py:1149`
  - **Issue:** `dur_sec = max(0.0, end_sec - start_sec)` does not enforce an upper bound on single shot duration, whereas Gemini Omni Flash prompts require durations $\le 10.0$ seconds. Shots defined as `[0-30s]` in screenplay text pass through unchunked in `compile_prompt()`.
  - **Remedy:** Apply consistent `<= 10.0s` chunking validation via the unified screenplay parser.

- **Required: Brittle Speaker Name Matching in `enrich_timeline_dialogue_speakers`**
  - **Location:** `src/omnimash/prompts/compiler.py:1002-1025`
  - **Issue:** The candidate generator splits names on whitespace (`for token in source_name.split(): candidate_keys.add(tok)`). For characters with common name tokens (e.g. "The", "A", "Of", "Fam", "Bruv", "Blood"), single generic tokens are added as candidate keys. If any dialogue has `The: "Hello"`, it can falsely match a character role.
  - **Remedy:** Disallow stop-words and single-token candidates with length $< 3$ unless they explicitly equal the character's exact `role_id`.

---

### 2. Readability & Simplicity

- **Required: Monolithic 3,172-Line `compiler.py` Violates Single-Responsibility Principle**
  - **Location:** `src/omnimash/prompts/compiler.py`
  - **Issue:** The file contains 3,172 lines mixing:
    1. Static dictionaries & parody mappings (`REAL_NAME_PARODY_MAP`, `AESTHETIC_SIGNIFIERS`, `CHARACTER_LORE_ANCHORS`)
    2. Screenplay and dialogue parsing regex logic (`parse_screenplay_script`, `parse_timecoded_script`, `enrich_timeline_dialogue_speakers`)
    3. Voice styling and accent assignment logic (`ensure_character_voice_style`, `apply_conversational_voice_edits`)
    4. Image tag reference assembly (`build_character_image_ref_tags`, `replace_character_in_text_image_tags`)
    5. Prompt compilation dataclasses and classes (`CompiledPromptParts`, `PromptCompiler`, `PromptOptimizer`)
    6. Journey 3 shot compiler (`compile_journey3_shot_prompt`)
  - **Remedy:** Decompose into cohesive, focused submodules under `src/omnimash/prompts/`:
    - `parody.py`: `REAL_NAME_PARODY_MAP`, `_COMPILED_PARODY_PATTERNS`, `sanitize_real_names()`
    - `screenplay.py`: `parse_screenplay_script()`, `parse_timecoded_script()`, `parse_directors_notes()`
    - `voice.py`: `ensure_character_voice_style()`, `apply_conversational_voice_edits()`, `enrich_timeline_dialogue_speakers()`
    - `image_tags.py`: `sort_characters_by_role_id()`, `build_character_image_ref_tags()`, `replace_character_in_text_image_tags()`
    - `journey3.py`: `compile_journey3_shot_prompt()`, `CumulativeShotState`
    - `compiler.py`: Main `PromptCompiler`, `PromptOptimizer`, and data structures.

- **Required: Duplicated / Redundant String Replacement Logic in `to_full_prompt` vs `compile_storyboard` vs `compile_journey3_shot_prompt`**
  - **Location:** `src/omnimash/prompts/compiler.py:441-454`, `compiler.py:1711-1721`, `compiler.py:2114-2138`
  - **Issue:** Stripping `Narrator (VO)` prefixes and formatting spoken dialogue is copy-pasted across three separate methods with slightly differing regular expressions (`r"^(?:(?:Role\s*\w+\s*\()?Narrator(?:\s*(?:VO|Voiceover\)))?\)?:\s*)[\"']?|[\"']?$"`).
  - **Remedy:** Extract a canonical `format_timeline_dialogue(speaker, text, is_narrator)` helper.

---

### 3. Architecture

- **Critical: Circular & Redundant Imports Across Prompts Submodules**
  - **Location:** `src/omnimash/prompts/storyboard_agent.py:14`, `storyboard_agent.py:719`, `taxonomy.py:6`, `compiler.py:14`
  - **Issue:** `storyboard_agent.py` imports `CharacterRole` and `sanitize_real_names` from `compiler.py`, while inside `StoryboardAgent.expand_vision()`, it does a deferred `from omnimash.prompts.compiler import PromptCompiler`. Similarly, `taxonomy.py` imports `PromptCompiler` from `compiler.py`, while `compiler.py` imports `StylePreset` under `TYPE_CHECKING` from `taxonomy.py`.
  - **Remedy:** Establish a clean DAG dependency flow:
    `character_roles.py` / `parody.py` $\rightarrow$ `image_tags.py` $\rightarrow$ `screenplay.py` $\rightarrow$ `compiler.py` $\rightarrow$ `storyboard_agent.py` / `taxonomy.py`.

- **Required: Redundant GenAI Client Instantiations for Global Endpoints**
  - **Location:** `src/omnimash/prompts/compiler.py:1330-1358` and `src/omnimash/prompts/storyboard_agent.py:534-558`
  - **Issue:** `PromptCompiler._init_deconstructor_clients` instantiates two separate clients (`_pro_global_client` with `location="global"` and `_flash_regional_client` with `location=settings.gemini_location or "global"`), while `StoryboardAgent._init_genai_client` instantiates a third client. Because `genai.Client` is thread-safe and model requests pass `model=...` per call, creating three identical clients creates redundant connection pools and memory overhead.
  - **Remedy:** Share a shared or memoized client initializer across prompt agents or pass the client as an optional dependency.

- **Optional: `__all__` in `src/omnimash/prompts/__init__.py` Omits Core Symbols**
  - **Location:** `src/omnimash/prompts/__init__.py:13-23`
  - **Issue:** `CharacterRole`, `SceneDirective`, `compile_journey3_shot_prompt`, and `sanitize_real_names` are not exported in `__init__.__all__`, forcing consumer modules across `engine/`, `api/`, and `agent/` to import directly from `compiler.py`.
  - **Remedy:** Re-export all canonical prompt symbols from `omnimash.prompts`.

---

### 4. Security

- **Critical: Catastrophic Regex Backtracking (ReDoS) Risk in Screenplay Parsing**
  - **Location:** `src/omnimash/prompts/storyboard_agent.py:98-111` and `compiler.py:603-614`
  - **Issue:** The regex in `_extract_character_dialogue`:
    ```python
    re.compile(
        r"(?:^|(?<=[\.\?\!,;–—\-\:])\s+|\b(?i:DIALOGUE|ACTION):\s*|\s+)"
        r"([A-Z0-9][A-Za-z0-9_\-\']*(?:\s+[A-Z0-9\(][A-Za-z0-9_\-\)\']*){0,4})"
        r"(?:\s+says:?|:)\s*"
        r"([\"'].*[\"']|[^\n]+)$"
    )
    ```
    contains unanchored lookbehinds with nested quantifiers (`(?:\s+...)*{0,4}`) combined with greedy wildcard matching (`[\"'].*[\"']|[^\n]+`). Passing complex or malformed screenplay text with unmatched quotes or nested colons causes exponential state-space evaluation.
  - **Remedy:** Replace nested quantified lookaheads/lookbehinds with linear token-based scanning or non-backtracking RE2-compatible expressions.

- **Required: Missing Input Length Validation on Custom Screenplay & Concept Text**
  - **Location:** `src/omnimash/prompts/compiler.py:1573`, `compiler.py:1787`, `storyboard_agent.py:709`
  - **Issue:** Public API endpoints (`POST /api/generate-storyboard` and `POST /api/compile-prompt`) accept arbitrary string inputs for `concept` and `screenplay_script` with no maximum character limit check in the compiler layer. Extremely large payloads (e.g. 500 KB scripts) cause excessive memory consumption during string manipulation and token exhaustion at the LLM boundary.
  - **Remedy:** Enforce reasonable length limits (e.g. 10,000 characters for screenplays, 1,000 characters for concept/directives) with explicit `ValueError` guards.

---

### 5. Performance

- **Required: Quadratic $O(K \times L)$ Loop in `replace_character_in_text_image_tags`**
  - **Location:** `src/omnimash/prompts/compiler.py:320-336`
  - **Issue:** For every character name in `sorted_keys`, `replace_character_in_text_image_tags` runs `re.sub(r"\b" + re.escape(key) + r"\b", _repl, result)`. In a script with 10 characters and multiple paragraphs, the full text is rescanned and allocated 10+ times.
  - **Remedy:** Combine keys into a single compiled alternation regex `\b(?:key1|key2|...)\b` and perform a single-pass token substitution using a replacement dictionary lookup.

- **Required: Redundant Double Optimization in `StoryboardAgent.expand_vision`**
  - **Location:** `src/omnimash/prompts/storyboard_agent.py:801-803`, `809-811`, `931-933`
  - **Issue:** In `expand_vision`, after shots are parsed or generated, a loop calls `shot.action = self.optimize_shot_prompt(shot.action)` for every shot sequentially. In live mode, this fires $N$ sequential synchronous Gemini API calls (`generate_content`) one after another, adding 3-6 seconds of network latency per shot (up to 15-30s total).
  - **Remedy:** In live mode, optimize shot directives concurrently using `ThreadPoolExecutor` or batch them into a single call, or skip LLM re-expansion if the shot action was already generated by `gemini-3.8-flash`.

- **Nit: Repeated String Concatenation and List Deduplication via `not in list`**
  - **Location:** `src/omnimash/prompts/compiler.py:626-632`, `storyboard_agent.py:240-246`
  - **Issue:** Checking `val_clean not in action_parts` where `action_parts` is a Python `list` is $O(N^2)$ for many lines.
  - **Remedy:** Track seen items using a `set` while preserving order in the `list`.

---

## Review Checklist & Quality Gate Verdict

| Axis | Status | Key Observations |
|---|---|---|
| **1. Correctness** | ⚠️ Issues Found | Diverging implementations of `parse_timecoded_script` across two files; brittle speaker candidate token matching. |
| **2. Readability & Simplicity** | ⚠️ Issues Found | Monolithic 3,172-line `compiler.py`; copy-pasted dialogue sanitization logic. |
| **3. Architecture** | ⚠️ Issues Found | Circular imports between `storyboard_agent.py` and `compiler.py`; redundant GenAI clients; missing `__init__.__all__` exports. |
| **4. Security** | ⚠️ Issues Found | ReDoS vulnerability in screenplay parsing regex; missing input size bounds on user scripts. |
| **5. Performance** | ⚠️ Issues Found | Sequential $N$-shot synchronous LLM calls in `expand_vision`; $O(K \times L)$ repeated regex passes in `replace_character_in_text_image_tags`. |

**Verdict:** **Request Changes (Remediation Required)**  
The module requires modular decomposition, unification of screenplay parsing, ReDoS mitigation, and optimization of repeated regex loops before further feature expansion.
