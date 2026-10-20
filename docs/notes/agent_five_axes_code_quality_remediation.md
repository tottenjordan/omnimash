# Agent Module 5-Axes Code Quality Remediation

## Overview
This note documents the root causes, remediations, and design decisions arising from the thorough 5-axes code quality review of `src/omnimash/agent`.

---

## 1. Character Wardrobe Normalization & Preservation
### Root Cause
`CharacterRole` defines a `wardrobe: str = ""` field for styling prompts.
In `process_user_turn`, whenever characters were passed as `dict`, `CharacterRole`, or Pydantic models, character objects were manually reconstructed. The reconstruction omitted `wardrobe`, causing user-supplied wardrobe descriptions to be silently dropped before reaching the prompt compiler and Omni Flash.

### Solution
Created a canonical `normalize_character_role(char: Any, clean_fn: Callable | None = None) -> CharacterRole` in `src/omnimash/prompts/character_roles.py`.
- Preserves all 10 fields: `role_id`, `name`, `description`, `reference_url`, `aesthetic_tags`, `voice_style`, `voice_profile`, `wardrobe`, `image_role`, and `is_offscreen_narrator`.
- Reused across `orchestrator.py`, `adk_pipeline.py`, and application endpoints, eliminating over 80 lines of duplicated type-checking logic.

---

## 2. Greedy State Removal Regex in `CumulativeStateTracker`
### Root Cause
In `record_shot_directive`, removal verbs (e.g. `removes`, `takes off`) matched target phrases using `[a-zA-Z0-9_\s]+`. Because this regex was unconstrained by clause boundaries, in prompts like `"Totti removes blindfold and steps into the ring"`, `target` matched the entire rest of the sentence (`"blindfold and steps into the ring"`).
Any word in that target (such as `"ring"` or `"steps"`) was treated as a state removal word, inadvertently deleting unrelated states such as `"diamond ring"`.

### Solution
Truncate matched removal phrases at clause, conjunction, and preposition boundaries:
```python
target = (
    re.split(
        r"[,;.]|\b(?:while|as|and|then|in|on|at|under|into|through|across|towards|from|with|surrounded|steps|walks|moves|runs)\b",
        raw_target,
        flags=re.IGNORECASE,
    )[0]
    .strip()
    .lower()
)
```
Additionally, removed verb keywords (`"holding"`, `"wearing"`) from `tracked_keywords` to prevent raw verbs from polluting character states.
Renamed `Journey3StateTracker` to `CumulativeStateTracker` with a backwards-compatible alias to keep the domain generic.

---

## 3. Multi-Chunk Session Turn Graph Consistency
### Root Cause
When video generation requested durations $> 10$ seconds, `process_user_turn` recursively generated 10-second chunks and stitched them into a final master video. While the stitched video URL was returned in `AgentTurnResponse`, the session turn node in `session.turns[turn_id].video_url` remained set to the unstitched final 10s chunk.

### Solution
Added `update_turn_video(session_id, turn_id, video_url, gcs_uri)` to `SessionManager`. After concatenation and master upload, `process_user_turn` updates `session.turns[last_resp.turn_id]` with the stitched master proxy URL and persists the session manifest.

---

## 4. Conversational Edit Validation Refinements
### Root Cause
`validate_conversational_edit` strictly enforces Google's Golden Rule (1 edit per turn). However, naive counting of action verbs caused false positives on valid single changes:
- `"Add a setting sun"` (matched `add` and `setting`).
- `"Make the car turn left"` (matched `make` and `turn`).
- `"Set camera to zoom in"` (matched `set` and `zoom`).
- `"Make him walk slowly, to the edge"` (rejected due to `, to` in clause 2).

### Solution
- Pre-process participle adjectives (`"setting sun"`, `"panning shot"`, `"zooming view"`).
- Recognize causative auxiliary constructions (`"make ... turn"`, `"set camera to zoom"`) as single composite action directives.
- In comma-separated clauses, require an actual action verb or explicit connector (`and`, `then`, `also`) before rejecting.

---

## 5. ADK Tool Schema & CLI Runner Integration
### Root Cause
1. `generate_parody_clip` only accepted `prompt`, `user_id`, `project_id`, `clip_index`, `parent_turn_id`, and `reference_url`. It lacked arguments for `duration_seconds`, `resolution`, `aspect_ratio`, `keyframe_image_url`, `is_conversational_edit`, and `audio_stem`, preventing the agent from fulfilling its system prompt directives.
2. The ADK CLI loader (`adk run`) strictly checks `isinstance(agent, BaseAgent)`. Lazy proxy wrappers raise a `ValueError` during CLI discovery.

### Solution
- Expanded `generate_parody_clip` with full typed parameters and Google-style docstring sections so ADK generates rich tool JSON schemas.
- Exposed `root_agent: Agent = get_root_agent()` as a concrete `Agent` instance conforming to ADK CLI loader expectations.
