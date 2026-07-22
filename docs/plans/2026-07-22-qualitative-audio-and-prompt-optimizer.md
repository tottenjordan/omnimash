# Qualitative Audio Prompting & Gemini Omni Flash Prompt Optimization Plan

**Goal:** Transition video/audio prompt construction from rigid quantitative mixing parameters (e.g., `"ducked at 15% volume under dialogue"`) to natural **qualitative audio descriptors** (e.g., `"subtly ducked in the background beneath dialogue"`), and introduce a **Gemini Omni Flash Prompt Optimization** layer to synthesize structured storyboards into high-impact, consolidated prompt directives before API invocation.

---

## 🎯 Background & Motivation

1. **Qualitative Audio Prompting**:
   - Generative multimodal models like `gemini-omni-flash-preview` process natural language qualitative descriptions of sound balance much more effectively than DAW engineering parameters (`15% volume`, `volume=0.15`).
   - Specifying exact numerical percentages can confuse video/audio joint latent diffusion and lead to awkward prompt over-specification. Replacing `"ducked at 15% volume under dialogue"` with `"subtly ducked in the background beneath dialogue"` improves audio mixing fidelity.

2. **Gemini Omni Flash Prompt Optimization Step**:
   - Structured prompt builders produce blocky sectioned prompts (`[ROLE DEFINITIONS]`, `[AESTHETIC INJECTION]`, `[AUDIO & VOCAL DIRECTION]`, `[STORYBOARD SEQUENCE]`).
   - A fast **Prompt Optimization step** powered by `gemini-3.6-flash-preview` / `gemini-3.5-flash` can take raw compiled prompts and condense them into cohesive, high-impact generation directives specifically optimized for Gemini Omni Flash's neural engine—eliminating redundant instructions while preserving character role bindings (`Role A`, `Role B`).

---

## ⚠️ User Review Required

> [!IMPORTANT]
> **Key Architectural Decisions:**
> 1. **Qualitative Audio Standard:** Standardize all audio mix prompts across the backend compiler (`compiler.py`), FastAPI endpoints (`app.py`), and test suite to use qualitative descriptors (`subtly ducked in the background beneath dialogue`).
> 2. **Two-Tier Prompt Optimization Architecture:**
>    - **Tier 1 (Deterministic / Default):** Enhanced `PromptCompiler` generating clean, qualitative prompts without extra network latency ($0\text{ms}$ delay).
>    - **Tier 2 (LLM Optimization Pass / Optional):** `PromptOptimizer.optimize()` using `gemini-3.6-flash-preview` to condense over-specified storyboards into highly expressive narrative directives when `optimize=True`.

---

## 📋 Proposed Changes

### Component 1: `omnimash.prompts` (Compiler & Optimizer)

#### [MODIFY] [compiler.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/prompts/compiler.py)
- Update `compile_multi_role_prompt` audio construction to use qualitative phrasing:
  ```python
  # Before:
  audio_parts.append(f"Background Beat: {audio_beat.strip()} (ducked at 15% volume under dialogue)")
  
  # After:
  audio_parts.append(f"Background Beat: {audio_beat.strip()} (subtly ducked in the background beneath dialogue)")
  ```
- Update `compile()` sound directive in `SingleRolePromptCompiler`:
  ```python
  # Before:
  "is quietly ducked at 15% volume in the background"
  
  # After:
  "is subtly ducked in the background beneath dialogue"
  ```
- Implement `PromptOptimizer` class:
  ```python
  class PromptOptimizer:
      """Optimizes compiled storyboards into cohesive Gemini Omni Flash directives."""
      def __init__(self, client: Any = None) -> None:
          self.client = client

      def optimize(self, compiled_prompt: str) -> str:
          """Synthesizes structured block prompts into dense, natural-language directives."""
          ...
  ```

---

### Component 2: `omnimash.api` (Web UI & Endpoints)

#### [MODIFY] [app.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py)
- Update initial raw prompt template and prompt assembly helper functions in `app.py` to use qualitative audio phrasing:
  ```javascript
  // Before:
  Background Beat: 140 BPM Heavy 808 Trap (ducked at 15% volume under dialogue)
  
  // After:
  Background Beat: 140 BPM Heavy 808 Trap (subtly ducked in the background beneath dialogue)
  ```

---

### Component 3: `omnimash.agent` (Orchestrator)

#### [MODIFY] [orchestrator.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py)
- Wire optional `optimize_prompt: bool = False` flag into `generate_video_turn` to optionally pass compiled prompts through `PromptOptimizer` before sending to `OmniClient`.

---

### Component 4: Tests & Documentation

#### [MODIFY] [test_compiler.py](file:///usr/local/google/home/jordantotten/omnimash/tests/prompts/test_compiler.py)
- Update test assertion strings matching qualitative audio outputs (`subtly ducked`).
- Add test coverage for `PromptOptimizer`.

#### [MODIFY] [audio_dialogue_and_voiceover_prompting.md](file:///usr/local/google/home/jordantotten/omnimash/docs/notes/audio_dialogue_and_voiceover_prompting.md)
- Document the qualitative audio prompting standard and prompt optimization workflow.

---

## 🧪 Verification Plan

### Automated Tests
Run full test suite via `uv`:
```bash
uv run pytest
uv run ruff check .
uv run ty check .
```

### Manual Verification
1. Inspect UI initial prompt output in Act 2 to ensure qualitative audio directives render cleanly (`subtly ducked in the background beneath dialogue`).
2. Test `PromptOptimizer` with sample storyboard prompts to verify retention of image role markers (`Role A`, `Role B`) and qualitative audio descriptors.
