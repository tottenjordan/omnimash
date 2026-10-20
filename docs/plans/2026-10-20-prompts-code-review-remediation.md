# Implementation Plan: `src/omnimash/prompts` Code Review Remediation

**Target Module:** `src/omnimash/prompts/`  
**Reference Document:** [code_review.md](file:///usr/local/google/home/jordantotten/omnimash/code_review.md)  
**Goal:** Address all **Critical**, **Required**, **Optional**, and **Nit** issues identified in the 5-axes review of `src/omnimash/prompts/`, modularizing the 3,172-line mega-file into clean, cohesive submodules, resolving ReDoS risks, unifying diverging screenplay parsers, eliminating circular dependencies, optimizing repeated regex loops, and expanding tests.  

---

## Strategy & Wave Architecture

To minimize the total execution time, we structure the remediation across **two waves**:
- **Wave 1 (3 Parallel PRs on Independent Files):**
  - **PR 1 (Wave 1A):** `refactor/prompts-parody-and-image-tags`
    - Creates `src/omnimash/prompts/parody.py` (extracting `REAL_NAME_PARODY_MAP`, `_COMPILED_PARODY_PATTERNS`, `sanitize_real_names()`)
    - Creates `src/omnimash/prompts/image_tags.py` (extracting `sort_characters_by_role_id()`, `build_character_image_ref_tags()`, single-pass `replace_character_in_text_image_tags()`)
    - Addresses: `PERF-01` ($O(K \times L)$ regex pass replaced with single alternation regex), `CORR-03` (speaker token length/stop-word filter), `READ-01` (submodule extraction).
  - **PR 2 (Wave 1B):** `fix/prompts-screenplay-and-security`
    - Creates `src/omnimash/prompts/screenplay.py`
    - Unifies diverging `parse_timecoded_script()` implementations into a single canonical parser with <=10s shot chunking and dialogue tag injection.
    - Resolves ReDoS vulnerability in `_extract_character_dialogue` (`SEC-01`) using linear token scanning.
    - Adds input length validation guards for concepts & screenplays (`SEC-02`).
    - Fixes `not in list` linear scan using `seen` set (`PERF-03`).
    - Addresses: `CORR-01`, `CORR-02`, `SEC-01`, `SEC-02`, `PERF-03`.
  - **PR 3 (Wave 1C):** `refactor/prompts-voice-and-storyboard`
    - Creates `src/omnimash/prompts/voice.py` (`ensure_character_voice_style()`, `apply_conversational_voice_edits()`, `enrich_timeline_dialogue_speakers()`)
    - Refactors `src/omnimash/prompts/storyboard_agent.py` to use `src/omnimash/prompts/screenplay.py` and concurrent shot prompt optimization (`PERF-02`), removing circular dependency on `compiler.py`.
    - Implements shared GenAI client initializer (`ARCH-02`).
    - Addresses: `ARCH-01` (circular imports), `ARCH-02` (redundant GenAI clients), `PERF-02` (concurrent shot optimization).
- **Wave 2 (1 Consolidation PR):**
  - **PR 4 (Wave 2):** `refactor/prompts-compiler-and-exports`
    - Creates `src/omnimash/prompts/journey3.py` (`compile_journey3_shot_prompt()`, `CumulativeShotState`)
    - Cleans up `src/omnimash/prompts/compiler.py` to import from the new focused submodules, reducing lines by >60% and standardizing `format_timeline_dialogue` (`READ-02`).
    - Updates `src/omnimash/prompts/__init__.py` to re-export all canonical prompt symbols in `__all__` (`ARCH-03`).
    - Full regression validation of `tests/prompts/`, `tests/api/`, `tests/engine/`, `tests/agent/`.

```mermaid
graph TD
    subgraph Wave 1 (Parallel Independent Submodules)
        PR1["PR 1: parody.py & image_tags.py<br/>(PERF-01, CORR-03, READ-01)"]
        PR2["PR 2: screenplay.py & security guards<br/>(CORR-01, CORR-02, SEC-01, SEC-02, PERF-03)"]
        PR3["PR 3: voice.py & storyboard_agent.py refactor<br/>(ARCH-01, ARCH-02, PERF-02)"]
    end
    
    subgraph Wave 2 (Consolidation & Exports)
        PR4["PR 4: journey3.py, compiler.py cleanup & __init__.py<br/>(READ-01, READ-02, ARCH-03, Final Integration)"]
    end
    
    PR1 --> PR4
    PR2 --> PR4
    PR3 --> PR4
```

---

## Detailed PR Breakdown

### PR 1 (Wave 1A): Parody & Image Tags Submodules (`refactor/prompts-parody-and-image-tags`)

#### Issues Addressed:
1. **`READ-01` (Submodule Extraction):** Extract `REAL_NAME_PARODY_MAP`, `_COMPILED_PARODY_PATTERNS`, and `sanitize_real_names()` to `src/omnimash/prompts/parody.py`.
2. **`PERF-01` ($O(K \times L)$ Quadratic Regex in `replace_character_in_text_image_tags`):**
   - *Current:* Loops over all character keys, running `re.sub()` across the entire prompt for each key.
   - *Fix:* Compile keys into a single alternation regex `\b(?:key1|key2|...)\b` and substitute matches in a single $O(L)$ scan.
3. **`CORR-03` (Brittle Speaker Candidate Token Matching):**
   - *Current:* Generates candidate tokens by naive whitespace splitting, matching short generic stop-words ("The", "A", "Bruv", "Blood").
   - *Fix:* Disallow stop-words and single tokens with length $< 3$ unless they explicitly equal the character's exact `role_id`.

#### Files Changed:
- `[NEW] src/omnimash/prompts/parody.py`
- `[NEW] src/omnimash/prompts/image_tags.py`
- `[MODIFY] src/omnimash/prompts/compiler.py` (import from `parody.py` and `image_tags.py` to maintain backwards compatibility)
- `[NEW] tests/prompts/test_parody.py`
- `[NEW] tests/prompts/test_image_tags.py`

---

### PR 2 (Wave 1B): Screenplay Parser Unification & Security Hardening (`fix/prompts-screenplay-and-security`)

#### Issues Addressed:
1. **`CORR-01` (Diverging `parse_timecoded_script` Implementations):**
   - *Current:* `compiler.py` and `storyboard_agent.py` have completely disjoint implementations of `parse_timecoded_script`.
   - *Fix:* Create `src/omnimash/prompts/screenplay.py` housing a unified `parse_timecoded_script()` that handles timecode detection, auto-splitting scripts $>10.0$s into sequential shots, parenthetical audio/action extraction, and character role matching.
2. **`CORR-02` (Missing Boundary Clamping on Timecode Durations):**
   - *Current:* Single timecode blocks like `[0-30s]` in `compiler.py` were passed through unchunked.
   - *Fix:* Enforce $\le 10.0$s chunking across all screenplay inputs.
3. **`SEC-01` (ReDoS Vulnerability in Screenplay Regex):**
   - *Current:* Unanchored lookbehinds with nested quantifiers in `_extract_character_dialogue` cause exponential backtracking.
   - *Fix:* Replace nested lookbehinds with clean linear delimiter scanning (`split_colon`, `strip_quotes`).
4. **`SEC-02` (Input Length Validation):**
   - *Fix:* Add validation guards rejecting screenplays $> 20,000$ characters and concepts $> 2,000$ characters with explicit `ValueError`.
5. **`PERF-03` ($O(N^2)$ `not in list` Deduplication):**
   - *Fix:* Maintain an order-preserving `seen: set[str]` alongside list appending.

#### Files Changed:
- `[NEW] src/omnimash/prompts/screenplay.py`
- `[MODIFY] src/omnimash/prompts/storyboard_agent.py` (use unified `screenplay.py` parser)
- `[MODIFY] src/omnimash/prompts/compiler.py` (delegate `parse_screenplay_script` and `parse_timecoded_script` to `screenplay.py`)
- `[NEW] tests/prompts/test_screenplay.py`

---

### PR 3 (Wave 1C): Voice Styling & Storyboard Agent Optimization (`refactor/prompts-voice-and-storyboard`)

#### Issues Addressed:
1. **`READ-01` (Voice Submodule Extraction):** Extract `ensure_character_voice_style()`, `apply_conversational_voice_edits()`, and `enrich_timeline_dialogue_speakers()` into `src/omnimash/prompts/voice.py`.
2. **`ARCH-01` (Circular Dependency between `storyboard_agent.py` and `compiler.py`):**
   - *Current:* `storyboard_agent.py` imported `CharacterRole` and `sanitize_real_names` from `compiler.py` and did deferred `import PromptCompiler`.
   - *Fix:* Import `CharacterRole` from `character_roles.py`, `sanitize_real_names` from `parody.py`, and deconstruct logic cleanly.
3. **`ARCH-02` (Redundant GenAI Client Instantiations):**
   - *Current:* 3 separate clients initialized for global location.
   - *Fix:* Provide a shared `get_genai_client(location: str = "global")` factory or reuse clients.
4. **`PERF-02` (Sequential LLM Calls in `expand_vision`):**
   - *Current:* In live mode, loops over shots calling `optimize_shot_prompt` sequentially.
   - *Fix:* Parallelize via `concurrent.futures.ThreadPoolExecutor(max_workers=4)`.

#### Files Changed:
- `[NEW] src/omnimash/prompts/voice.py`
- `[MODIFY] src/omnimash/prompts/storyboard_agent.py`
- `[MODIFY] src/omnimash/prompts/compiler.py` (re-export voice functions from `voice.py`)
- `[NEW] tests/prompts/test_voice.py`

---

### PR 4 (Wave 2): Journey 3 Extraction, Compiler Modularization & Package Exports (`refactor/prompts-compiler-and-exports`)

#### Issues Addressed:
1. **`READ-01` (Journey 3 Shot Compiler Extraction):** Extract `compile_journey3_shot_prompt()` and `CumulativeShotState` (400+ lines) into `src/omnimash/prompts/journey3.py`.
2. **`READ-02` (Duplicated Dialogue Formatting):** Extract unified `format_timeline_dialogue()` helper.
3. **`ARCH-03` (`__init__.__all__` Re-Exports):** Re-export all canonical symbols (`CharacterRole`, `SceneDirective`, `compile_journey3_shot_prompt`, `sanitize_real_names`, `CumulativeShotState`) in `src/omnimash/prompts/__init__.py`.
4. **Final Consolidation:** Reduce `compiler.py` from 3,172 lines to ~600 lines focusing exclusively on `PromptCompiler`, `PromptOptimizer`, and orchestration.

#### Files Changed:
- `[NEW] src/omnimash/prompts/journey3.py`
- `[MODIFY] src/omnimash/prompts/compiler.py`
- `[MODIFY] src/omnimash/prompts/__init__.py`
- `[MODIFY] tests/prompts/test_compiler.py`
- `[NEW] tests/prompts/test_journey3.py`

---

## Verification Plan

### Automated Tests
Run across each PR branch and after merging Wave 1 and Wave 2:
```bash
# 1. Full prompt test suite
uv run pytest tests/prompts/ -v

# 2. End-to-end integration across dependent modules
uv run pytest tests/api/test_app.py -v
uv run pytest tests/engine/ -q
uv run pytest tests/agent/ -q

# 3. Code formatting, linting, and type checks
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

### Manual Verification
- Verify that `from omnimash.prompts import CharacterRole, SceneDirective, PromptCompiler, StoryboardAgent, sanitize_real_names` resolves without circular import warnings or runtime errors.
- Verify ReDoS immunity by passing 5,000-character adversarial screenplay strings (unclosed quotes, repeated whitespace) and measuring execution time ($< 10$ms).
