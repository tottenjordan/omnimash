# Prompt Compiler: "Anchor & Inject" Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent character decay and latent space averaging in `gemini-omni-flash-preview` by building a Prompt Compiler that translates raw user shorthand into a structured 5-part "Anchor & Inject" meta-prompt.

**Architecture:** An internal Prompt Compiler expands character IP names into explicit anatomical/physical lore anchors and merges them with hyper-specific wardrobe, camera, lighting, and motion signifiers. The Google ADK agent system instruction enforces this compiler across all new clip generations and conversational diffs.

**Tech Stack:** Python 3.12, Google ADK 2.5 (`google.adk.agents.Agent`), Gemini Omni Flash (`google-genai`), Pydantic, FastAPI, Pytest, Ruff, Ty.

---

### Task 1: Prompt Compiler 5-Part Model & Knowledge Bases

**Files:**
- Create: `src/omnimash/prompts/compiler.py`
- Create: `tests/prompts/test_compiler.py`

**Step 1: Write the failing test**

```python
from omnimash.prompts.compiler import PromptCompiler, CompiledPromptParts
from omnimash.prompts.taxonomy import StylePreset

def test_prompt_compiler_anchor_and_inject():
    compiler = PromptCompiler()
    parts = compiler.compile(
        raw_prompt="Severus Snape in a 90s rap video",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions="rapping in the dungeon"
    )
    assert isinstance(parts, CompiledPromptParts)
    assert "gaunt" in parts.subject_anchor or "hooked nose" in parts.subject_anchor
    assert "puffer jacket" in parts.aesthetic_injection or "Cuban link" in parts.aesthetic_injection
    assert "dungeon" in parts.environment
    assert "fisheye lens" in parts.camera_lighting
    assert "10-second" in parts.motion or "nodding" in parts.motion

    full_prompt = parts.to_full_prompt()
    assert "[SUBJECT ANCHOR]:" in full_prompt
    assert "[AESTHETIC INJECTION]:" in full_prompt
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prompts/test_compiler.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'omnimash.prompts.compiler'`

**Step 3: Write minimal implementation**

Create `src/omnimash/prompts/compiler.py`:
```python
from dataclasses import dataclass
from omnimash.prompts.taxonomy import StylePreset

@dataclass
class CompiledPromptParts:
    subject_anchor: str
    aesthetic_injection: str
    environment: str
    camera_lighting: str
    motion: str

    def to_full_prompt(self) -> str:
        return (
            f"[SUBJECT ANCHOR]: {self.subject_anchor} | "
            f"[AESTHETIC INJECTION]: {self.aesthetic_injection} | "
            f"[ENVIRONMENT]: {self.environment} | "
            f"[CAMERA/LIGHTING]: {self.camera_lighting} | "
            f"[MOTION]: {self.motion}"
        )

CHARACTER_LORE_ANCHORS = {
    "snape": "Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair",
    "dumbledore": "Albus Dumbledore, an elderly wizard with half-moon spectacles, long flowing silver beard, and ornate wizard robes",
    "voldemort": "Lord Voldemort, a pale serpentine figure with slit-like nostrils, no hair, chalk-white skin, and piercing cold eyes",
    "harry": "Harry Potter, a young man with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead",
}

AESTHETIC_SIGNIFIERS = {
    StylePreset.NINETIES_RAP_VIDEO: {
        "wardrobe": "wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses",
        "camera": "shot on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with green and purple neon rim lights",
        "motion": "nodding rhythmically to a boom-bap beat while gesturing emphatically for a 10-second clip",
    },
    StylePreset.TRAP_DISSTRACK: {
        "wardrobe": "wearing designer streetwear, iced-out medallions, and tinted aviator sunglasses",
        "camera": "rapid visual jump cuts, dark moody 808 bass lighting, heavy laser smoke, and strobe flashes",
        "motion": "aggressive lyrical hand gestures and slow walking toward the camera for 10 seconds",
    },
    StylePreset.CYBERPUNK_DRIFT: {
        "wardrobe": "wearing a high-collar LED-lined techwear coat with holographic chrome accessories",
        "camera": "anamorphic widescreen lens, rainy asphalt reflections, synthwave purple and cyan color grading",
        "motion": "slowly turning to face the camera amidst falling digital rain for 10 seconds",
    },
    StylePreset.VHS_ANIME: {
        "wardrobe": "cel-shaded retro anime styling with oversized 80s shoulder pads and vintage headbands",
        "camera": "retro 4:3 VHS tape grain, analog scanlines, chromatic aberration, and warm nostalgic bloom",
        "motion": "classic limited-frame anime speech animation and dynamic wind blowing through hair for 10 seconds",
    },
}

class PromptCompiler:
    def compile(
        self,
        raw_prompt: str,
        style_preset: StylePreset = StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions: str = "",
    ) -> CompiledPromptParts:
        lower = raw_prompt.lower()
        
        # 1. Resolve Subject Anchor
        anchor = "A distinct cinematic character with sharp facial features and expressive eyes"
        for name, desc in CHARACTER_LORE_ANCHORS.items():
            if name in lower:
                anchor = desc
                break

        # 2. Resolve Style Signifiers
        style_info = AESTHETIC_SIGNIFIERS.get(
            style_preset,
            AESTHETIC_SIGNIFIERS[StylePreset.NINETIES_RAP_VIDEO]
        )

        # 3. Resolve Environment
        env = "in a stone Hogwarts dungeon lit by atmospheric fog and ambient glow"
        if custom_instructions:
            env = f"in {custom_instructions} with atmospheric environmental lighting"

        return CompiledPromptParts(
            subject_anchor=anchor,
            aesthetic_injection=style_info["wardrobe"],
            environment=env,
            camera_lighting=style_info["camera"],
            motion=style_info["motion"],
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prompts/test_compiler.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/prompts/compiler.py tests/prompts/test_compiler.py
git commit -m "feat(prompts): add PromptCompiler with 5-part Anchor and Inject framework"
```

---

### Task 2: Prompt Taxonomy Engine Integration

**Files:**
- Modify: `src/omnimash/prompts/taxonomy.py`
- Modify: `tests/prompts/test_taxonomy.py`

**Step 1: Write the failing test**

```python
def test_taxonomy_engine_uses_prompt_compiler():
    engine = PromptTaxonomyEngine()
    composed = engine.build_initial_prompt(
        base_character="Severus Snape",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions="rapping in dungeon"
    )
    assert "[SUBJECT ANCHOR]:" in composed
    assert "gaunt man with a hooked nose" in composed
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prompts/test_taxonomy.py -v`  
Expected: FAIL with `AssertionError: assert '[SUBJECT ANCHOR]:' in composed`

**Step 3: Write minimal implementation**

Modify `src/omnimash/prompts/taxonomy.py`:
```python
from enum import Enum
from omnimash.prompts.compiler import PromptCompiler, CompiledPromptParts

class StylePreset(str, Enum):
    NINETIES_RAP_VIDEO = "90s_rap_video"
    TRAP_DISSTRACK = "trap_disstrack"
    CYBERPUNK_DRIFT = "cyberpunk_drift"
    VHS_ANIME = "vhs_anime"

class PromptTaxonomyEngine:
    def __init__(self):
        self.compiler = PromptCompiler()

    def build_initial_prompt(
        self,
        base_character: str,
        style_preset: StylePreset,
        custom_instructions: str,
    ) -> str:
        parts: CompiledPromptParts = self.compiler.compile(
            raw_prompt=base_character,
            style_preset=style_preset,
            custom_instructions=custom_instructions,
        )
        return (
            f"Generate a 720p 10-second cinematic parody video with native audio using the Anchor & Inject framework: "
            f"{parts.to_full_prompt()}"
        )

    def build_delta_prompt(self, current_clip_desc: str, delta_instruction: str) -> str:
        return (
            f"Apply conversational diff to the existing video latent space using Anchor & Inject preservation: "
            f"[DIFF INSTRUCTION]: {delta_instruction}. "
            f"[PRESERVATION CONSTRAINT]: Maintain exact character facial anchors, wardrobe signifiers, and lighting consistency."
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prompts/test_taxonomy.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/prompts/taxonomy.py tests/prompts/test_taxonomy.py
git commit -m "feat(prompts): integrate PromptCompiler into PromptTaxonomyEngine"
```

---

### Task 3: Google ADK Agent System Instruction & Tool Integration

**Files:**
- Modify: `src/omnimash/agent/orchestrator.py`
- Modify: `tests/agent/test_orchestrator.py`

**Step 1: Write the failing test**

```python
def test_adk_agent_instruction_and_compiler_integration():
    adk_agent = build_adk_agent(mock_mode=True)
    assert "Prompt Compiler" in adk_agent.instruction
    assert "[SUBJECT ANCHOR]" in adk_agent.instruction
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/agent/test_orchestrator.py -v`  
Expected: FAIL with `AssertionError: assert 'Prompt Compiler' in adk_agent.instruction`

**Step 3: Write minimal implementation**

Modify `src/omnimash/agent/orchestrator.py`:
- Update `build_adk_agent()` system instruction with the 5-part Prompt Compiler rules:
```python
    instruction = (
        "You are the Prompt Compiler for OmniMash. Your job is to take the user's video concept "
        "and format it into an optimized 5-part prompt for the gemini-omni-flash-preview video model.\n\n"
        "Never pass the user's raw text. Always rewrite it using this exact structure:\n"
        "[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + [ENVIRONMENT] + [CAMERA/LIGHTING] + [MOTION]\n\n"
        "Rules:\n"
        "1. SUBJECT ANCHOR: Do not just use character names. Explicitly describe their defining physical traits.\n"
        "2. AESTHETIC INJECTION: Define wardrobe and props using hyper-specific cultural signifiers.\n"
        "3. ENVIRONMENT: Anchor the background scene with atmospheric lighting.\n"
        "4. CAMERA/LIGHTING: Use specific directorial terms (e.g. fisheye lens, low-angle shot, neon rim lights).\n"
        "5. MOTION: Keep motion simple and physically plausible for a 10-second clip."
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/agent/test_orchestrator.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat(agent): update ADK system instructions with 5-part Anchor and Inject rules"
```

---

### Task 4: FastAPI & Web UI 5-Part Prompt Preview Integration

**Files:**
- Modify: `src/omnimash/api/app.py`
- Modify: `tests/api/test_integration.py`

**Step 1: Write the failing test**

```python
def test_e2e_compiled_prompt_generation():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={"user_id": "u_comp", "project_id": "p_comp", "prompt": "Snape 90s rap", "clip_index": 0}
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/api/test_integration.py -v`  
Expected: PASS

**Step 3: Write minimal implementation**

Enhance the HTML/React template inside `src/omnimash/api/app.py` to:
- Render a **"🪄 5-Part Anchor & Inject Preview"** card in the dashboard showing the compiled prompt sections (`[SUBJECT ANCHOR]`, `[AESTHETIC INJECTION]`, `[ENVIRONMENT]`, `[CAMERA/LIGHTING]`, `[MOTION]`).

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_integration.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py tests/api/test_integration.py
git commit -m "feat(ui): add 5-part Anchor and Inject preview badge to dashboard"
```

---

## 🧪 Global Quality & Verification Commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check .
```
