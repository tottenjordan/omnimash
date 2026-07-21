# Gemini Omni Prompt Guide Alignment: Dedicated Voiceover, Voice Styles & Audio Direction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align OmniMash's prompt generation and studio UI with the official Gemini Omni Prompt Guide by introducing dedicated inputs for character-specific voice styles, global vocal delivery/voiceover, background sound design, and structured prompt sectioning.

**Architecture:** 
1. Extend `CharacterRole` with `voice_style: str` (e.g., *"Fast-paced Atlanta rap cadence with subtle autotune"*) and `MetaPromptTags` with `vocal_delivery: str`.
2. Update `PromptCompiler.compile_storyboard` and `deconstruct_concept` to format a structured `[AUDIO & VOCAL DIRECTION]` block separating background sound design from character vocal timbres and spoken dialogue per Gemini Omni best practices.
3. Add dedicated Voice Style & Accent inputs per Character Role card and Global Vocal Delivery controls in Act 1 of the React 18 dashboard.

**Tech Stack:** Python 3.12, Google ADK, FastAPI, Pydantic v2, React 18 + Tailwind CSS, pytest, uv, ruff, ty.

---

### Task 1: Extend CharacterRole, MetaPromptTags & PromptCompiler with Voice Styles & `[AUDIO & VOCAL DIRECTION]` Block

**Files:**
- Modify: `src/omnimash/prompts/compiler.py`
- Test: `tests/prompts/test_compiler.py`
- Test: `tests/prompts/test_deconstruct.py`

**Step 1: Write the failing unit tests**
In `tests/prompts/test_compiler.py`:
```python
def test_compile_storyboard_with_audio_and_vocal_direction():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Harry Potter, young wizard",
            aesthetic_tags=["Red Gucci Tracksuit", "Cartier Glasses"],
            reference_url="gs://bucket/harry.jpg",
            voice_style="Fast-paced confident Atlanta rap flow with autotune",
        ),
        CharacterRole(
            role_id="Role B",
            name="Draco",
            description="Draco Malfoy, rival wizard",
            aesthetic_tags=["Platinum Slicked Hair"],
            reference_url="gs://bucket/draco.jpg",
            voice_style="Pompous, cynical British drawl with aggressive cadence",
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Standing over potion stove",
            dialogue="I been cooking potions since first year. Burrr!",
        )
    ]
    compiled = compiler.compile_storyboard(
        concept="Harry vs Draco rap battle",
        characters=chars,
        scenes=scenes,
        aesthetic_tags=["2000s Atlanta Trap Disstrack"],
        environment_tag="Hogwarts courtyard",
        audio_beat="140 BPM Heavy 808 Trap",
        vocal_delivery="High-energy back-and-forth rap battle delivery with synchronized lip-sync",
    )

    assert "[AUDIO & VOCAL DIRECTION]" in compiled
    assert "Background Beat: 140 BPM Heavy 808 Trap" in compiled
    assert "Voice Style (Role A): Fast-paced confident Atlanta rap flow with autotune" in compiled
    assert "Voice Style (Role B): Pompous, cynical British drawl with aggressive cadence" in compiled
    assert "Vocal Delivery: High-energy back-and-forth rap battle delivery with synchronized lip-sync" in compiled
```

In `tests/prompts/test_deconstruct.py`:
```python
def test_deconstruct_concept_populates_voice_styles():
    compiler = PromptCompiler()
    tags = compiler.deconstruct_concept("Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style")
    assert len(tags.characters) >= 2
    assert any("trap" in c.voice_style.lower() or "rap" in c.voice_style.lower() for c in tags.characters)
    assert tags.vocal_delivery != ""
```

**Step 2: Run test to verify it fails**
```bash
uv run pytest tests/prompts/test_compiler.py -k test_compile_storyboard_with_audio_and_vocal_direction
```
Expected: FAIL with missing fields/arguments.

**Step 3: Write minimal implementation in `compiler.py`**
- Update `CharacterRole` dataclass:
  ```python
  @dataclass
  class CharacterRole:
      role_id: str
      name: str
      description: str
      reference_url: str | None = None
      aesthetic_tags: list[str] = field(default_factory=list)
      voice_style: str = ""
  ```
- Update `MetaPromptTags` dataclass:
  ```python
  @dataclass
  class MetaPromptTags:
      characters: list[CharacterRole] = field(default_factory=list)
      aesthetic_tags: list[str] = field(default_factory=list)
      environment_tag: str = ""
      camera_lighting_tag: str = ""
      audio_beat: str = ""
      vocal_delivery: str = ""
  ```
- Update `compile_storyboard(...)` to format `[AUDIO & VOCAL DIRECTION]` block:
  ```python
  audio_parts: list[str] = []
  if audio_beat and audio_beat.strip():
      audio_parts.append(f"Background Beat: {audio_beat.strip()} (ducked at 15% volume under dialogue)")
  for char in characters:
      if char.voice_style and char.voice_style.strip():
          audio_parts.append(f"Voice Style ({char.role_id}): {char.voice_style.strip()}")
  if vocal_delivery and vocal_delivery.strip():
      audio_parts.append(f"Vocal Delivery: {vocal_delivery.strip()}")
  audio_block = "\n".join(audio_parts) if audio_parts else "Default Audio & Voice Direction"
  ```
- Update `deconstruct_concept(...)` to assign character-specific voice styles and vocal delivery.

**Step 4: Run test to verify it passes**
```bash
uv run pytest tests/prompts/
```

**Step 5: Commit**
```bash
git add src/omnimash/prompts/compiler.py tests/prompts/
git commit -m "feat(prompts): add voice styles and structured audio direction to compiler"
```

---

### Task 2: Update Agent Orchestrator & API Models for Voice Styles

**Files:**
- Modify: `src/omnimash/agent/orchestrator.py`
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_app.py`
- Test: `tests/api/test_concept_api.py`

**Step 1: Write the failing API test**
In `tests/api/test_concept_api.py`:
```python
def test_deconstruct_concept_returns_voice_styles():
    client = TestClient(app)
    res = client.post("/api/deconstruct-concept", json={"concept": "Gordon Ramsay vs Julia Child iron chef battle"})
    assert res.status_code == 200
    data = res.json()
    assert "characters" in data
    assert len(data["characters"]) >= 2
    assert "voice_style" in data["characters"][0]
    assert "vocal_delivery" in data
```

**Step 2: Run test to verify it fails**
```bash
uv run pytest tests/api/test_concept_api.py -k test_deconstruct_concept_returns_voice_styles
```

**Step 3: Write minimal implementation**
- Update Pydantic and dataclass models in `orchestrator.py` and `app.py` to include `voice_style: str = ""` in character dictionaries and `vocal_delivery: str = ""` in requests and responses.
- Update `/api/deconstruct-concept`, `/api/generate`, `/api/extend-scene` to deserialize and preserve `voice_style` and `vocal_delivery`.

**Step 4: Run test to verify it passes**
```bash
uv run pytest tests/api/test_concept_api.py tests/api/test_app.py
```

**Step 5: Commit**
```bash
git add src/omnimash/agent/orchestrator.py src/omnimash/api/app.py tests/api/
git commit -m "feat(api): propagate voice styles and vocal delivery in API routes"
```

---

### Task 3: Update React Dashboard UI (Act 1 Voice Style Inputs & Act 3 Prompt Viewer)

**Files:**
- Modify: `src/omnimash/api/app.py` (`UI_HTML`)
- Test: `tests/api/test_integration.py`

**Step 1: Write failing UI integration test**
In `tests/api/test_integration.py`:
```python
def test_dashboard_ui_html_voiceover_inputs():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "Voice Style & Accent" in html
    assert "Vocal Delivery / Voiceover Style" in html
    assert "[AUDIO & VOCAL DIRECTION]" in html
```

**Step 2: Run test to verify it fails**
```bash
uv run pytest tests/api/test_integration.py -k test_dashboard_ui_html_voiceover_inputs
```

**Step 3: Update `UI_HTML` in `app.py`**
- In Act 1:
  - Inside each Character Role card, render a text input for `char.voice_style`:
    ```html
    <div>
        <label className="block text-[11px] font-bold text-amber-400 uppercase tracking-wider mb-1">
            🎙️ Voice Style & Accent (Gemini Omni Speech Timbre)
        </label>
        <input
            type="text"
            value={char.voice_style || ""}
            onChange={(e) => updateCharacter(idx, "voice_style", e.target.value)}
            placeholder="e.g. Fast-paced Atlanta trap flow with subtle autotune..."
            className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 font-mono text-[11px]"
        />
    </div>
    ```
  - In the Environment & Audio Beat card, add an input for `vocalDelivery`:
    ```html
    <div>
        <label className="block text-[11px] font-bold text-purple-400 uppercase tracking-wider mb-1">
            🎙️ Global Vocal Delivery / Voiceover Style
        </label>
        <input
            type="text"
            value={vocalDelivery}
            onChange={(e) => setVocalDelivery(e.target.value)}
            placeholder="e.g. High-energy back-and-forth rap battle delivery with synchronized lip-sync..."
            className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono text-[11px]"
        />
    </div>
    ```
- Update `compileStoryboardPreview()` to output `[AUDIO & VOCAL DIRECTION]` block.
- Update Act 3 Prompt Viewer to render the formatted `[AUDIO & VOCAL DIRECTION]` section.

**Step 4: Run test to verify it passes**
```bash
uv run pytest tests/api/test_integration.py
```

**Step 5: Commit**
```bash
git add src/omnimash/api/app.py tests/api/test_integration.py
git commit -m "feat(ui): add voice style and vocal delivery controls to React studio"
```

---

### Task 4: Documentation & Screenshot Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/notes/audio_dialogue_and_voiceover_prompting.md`
- Modify: `scratch/render_readme_screenshots.py`
- Update images: `imgs/ui_act1_concept_and_cast.jpg`, `imgs/ui_act2_storyboard_directing.jpg`, `imgs/ui_act3_screening_room.jpg`

**Step 1: Update documentation files**
- Document character voice styles and `[AUDIO & VOCAL DIRECTION]` in `README.md` and `docs/notes/audio_dialogue_and_voiceover_prompting.md`.

**Step 2: Update screenshot renderer and re-generate screenshots**
- Update `scratch/render_readme_screenshots.py` to reflect the new `🎙️ Voice Style & Accent` input in Act 1 and the updated `[AUDIO & VOCAL DIRECTION]` prompt preview block in Act 2 and Act 3.
- Run `uv run python3 scratch/render_readme_screenshots.py`.

**Step 3: Run full verification suite**
```bash
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv run ty check .
```

**Step 4: Commit**
```bash
git add README.md docs/notes/ scratch/ imgs/
git commit -m "docs: update documentation and screenshots for voice styles and audio direction"
```
