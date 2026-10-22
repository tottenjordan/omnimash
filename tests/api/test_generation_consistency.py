"""Tests for Mode 1 multi-scene prompt consistency, role binding repair, and fresh Turn-0 generation."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.engine.guardrails import _abstract_prompt_for_responsible_ai
from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.compiler import (
    PromptCompiler,
    SceneDirective,
    validate_and_repair_role_bindings,
)


def test_validate_and_repair_role_bindings_remaps_unbound_roles_and_populates_empty_scene_header():
    """Verify unbound Role B in Concept/Timeline is remapped to declared Role C <IMAGE_REF_1>
    and empty '- Scene 1 []:' is repaired with active character roles and reference tags."""
    chars = [
        CharacterRole(
            role_id="Role C",
            name="Bee Allison",
            description="A gritty, thin-faced, fit, high-energy trap wizard.",
            reference_url="gs://bucket/bee_allison_sheet.png",
            voice_style="British accent with a polished, clear, and articulate delivery style",
        ),
        CharacterRole(
            role_id="Role A",
            name="YoTotti",
            description="A young tatted wizard, highly confident, radiating zen energy.",
            reference_url="gs://bucket/yototti_sheet.png",
            voice_style="British, East London accent",
        ),
    ]

    raw_prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]\n\n"
        "### CHARACTER PROFILES\n"
        "- Role C <IMAGE_REF_1>: A gritty, thin-faced, fit, high-energy trap wizard.\n"
        "- Role A <IMAGE_REF_0>: A young tatted wizard, highly confident.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Concept: Behind a black marble desk stands Role A. Beside the desk stands Role B holding a crystal vial.\n\n"
        "### TIMELINE\n"
        '- Scene 1 []: [0-3s] Role B steps forward in white gloves. | Dialogue: Role B: "The vintage elixir, Master." Role A <IMAGE_REF_0> says: "Bottle it."'
    )

    repaired = validate_and_repair_role_bindings(raw_prompt, chars)

    # Unbound Role B must be remapped to the declared Role C (with reference tag in timeline/dialogue)
    assert "Role B" not in repaired
    assert "- Scene 1 []:" not in repaired
    assert "Role A <IMAGE_REF_0>" in repaired
    assert "Role C <IMAGE_REF_1>" in repaired
    assert "- Scene 1 [" in repaired


def test_compile_storyboard_populates_empty_active_roles_and_repairs_phantom_roles():
    """Verify compile_storyboard auto-populates active_roles when empty and repairs phantom Role IDs."""
    compiler = PromptCompiler(mock_mode=True)
    chars = [
        CharacterRole(
            role_id="Role A",
            name="YoTotti",
            description="Young tatted wizard",
            reference_url="gs://bucket/yototti.png",
            voice_style="British, East London accent",
        ),
        CharacterRole(
            role_id="Role C",
            name="Bee Allison",
            description="High-energy trap wizard",
            reference_url="gs://bucket/bee.png",
            voice_style="Polished British accent",
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=[],
            action="[0-3s] Role B steps forward toward Role A's marble desk. [3-6s] Role A inspects the scale. [6-10s] Role A smirks.",
            dialogue='Role B: "The vintage elixir." / Role A: "Bottle it."',
        )
    ]

    compiled = compiler.compile_storyboard(
        concept="Role A and Role B in a gothic office.",
        characters=chars,
        scenes=scenes,
        enable_sanitization=False,
    )

    assert "- Scene 1 []:" not in compiled
    assert "- Scene 1 [Role A <IMAGE_REF_0>, Role C <IMAGE_REF_1>]" in compiled
    assert "Role B" not in compiled


def test_generate_endpoint_forces_fresh_turn0_when_scenes_passed_with_empty_prompt():
    """Verify POST /api/generate with scenes/concept and empty prompt forces parent_turn_id=None
    (fresh Turn-0 generation) even if client sent a stale parent_turn_id, and preserves screenplay_script."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    chars = [
        {
            "role_id": "Role A",
            "name": "YoTotti",
            "description": "Young tatted wizard",
            "reference_url": "gs://bucket/yototti.png",
            "voice_style": "East London accent",
        },
        {
            "role_id": "Role C",
            "name": "Bee Allison",
            "description": "High-energy trap wizard",
            "reference_url": "gs://bucket/bee.png",
            "voice_style": "Polished British accent",
        },
    ]

    # Scene 1 (Turn 0)
    res1 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_studio",
            "project_id": "prj_director",
            "session_name": "revamp_fresh_test",
            "prompt": "",
            "clip_index": 0,
            "parent_turn_id": None,
            "concept": "Gothic office scene with Role A and Role B",
            "characters": chars,
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role C", "Role A"],
                    "screenplay_script": '[0-3s] ACTION: Role B steps forward. DIALOGUE: Role B: "The vintage elixir." [3-6s] ACTION: Role A leans in. [6-10s] ACTION: Role A smirks.',
                }
            ],
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    turn_0_id = data1["turn_id"]
    assert "(Screenplay Script):" in data1["raw_compiled_prompt"]
    assert "Role B" not in data1["raw_compiled_prompt"]

    # Scene 2 (Client accidentally passes stale parent_turn_id=turn_0_id with empty prompt="")
    with (
        patch.object(
            app.state.agent.omni_client,
            "generate_clip",
            wraps=app.state.agent.omni_client.generate_clip,
        ) as spy_gen_clip,
        patch.object(
            app.state.agent.omni_client,
            "apply_interaction_diff",
            wraps=app.state.agent.omni_client.apply_interaction_diff,
        ) as spy_diff,
    ):
        res2 = client.post(
            "/api/generate",
            json={
                "user_id": "usr_studio",
                "project_id": "prj_director",
                "session_name": "revamp_fresh_test",
                "prompt": "",
                "clip_index": 1,
                "parent_turn_id": turn_0_id,
                "concept": "Gothic office scene 2 with Role A and Role B",
                "characters": chars,
                "scenes": [
                    {
                        "scene_number": 1,
                        "active_roles": [],
                        "screenplay_script": '[0-3s] ACTION: Camera glides as Role B places vial. [3-6s] ACTION: Role A inspects scale. [6-10s] ACTION: Role A taps ring. DIALOGUE: Role A: "The runway awaits."',
                    }
                ],
            },
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["success"] is True
        assert data2["depth"] == 0
        # Must call generate_clip (Turn-0), NOT apply_interaction_diff
        assert spy_gen_clip.call_count == 1
        assert spy_diff.call_count == 0
        assert "(Screenplay Script):" in data2["raw_compiled_prompt"]
        assert "- Scene 1 []:" not in data2["raw_compiled_prompt"]
        assert "Concept:" in data2["raw_compiled_prompt"]
        assert "Role B" not in data2["raw_compiled_prompt"]


def test_abstract_prompt_for_responsible_ai_preserves_concept_and_scene_structure():
    """Verify _abstract_prompt_for_responsible_ai never deletes the Concept: line,
    ### CHARACTER PROFILES, <IMAGE_REF_N> tags, or - Scene 1 [...] (Screenplay Script): header."""
    compiled_prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]\n\n"
        "### CHARACTER PROFILES\n"
        "- Role C <IMAGE_REF_1>: A gritty trap wizard [Style: white foam cup, dark sunglasses]\n"
        "- Role A <IMAGE_REF_0>: A young tatted wizard [Style: diamond chains]\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Concept: Cinematic widescreen shot of a lavish gothic office with Role A <IMAGE_REF_0> and Role C <IMAGE_REF_1>.\n"
        "Environment: Grand vaulted gothic stone office.\n\n"
        "### TIMELINE\n"
        "- Scene 1 [Role C <IMAGE_REF_1>, Role A <IMAGE_REF_0>] (Screenplay Script):\n"
        '  [0-3s] ACTION: Role C steps forward. DIALOGUE: Role C <IMAGE_REF_1> says: "The vintage elixir."'
    )

    abstracted = _abstract_prompt_for_responsible_ai(compiled_prompt)

    assert "### INPUT ROLES & REFERENCES" in abstracted
    assert "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]" in abstracted
    assert "### CHARACTER PROFILES" in abstracted
    assert "Concept: Cinematic widescreen shot" in abstracted
    assert (
        "- Scene 1 [Role C <IMAGE_REF_1>, Role A <IMAGE_REF_0>] (Screenplay Script):" in abstracted
    )
    assert "<IMAGE_REF_0>" in abstracted
    assert "<IMAGE_REF_1>" in abstracted


def test_generate_endpoint_accepts_keyframe_seed_and_includes_first_frame_tag():
    """Verify POST /api/generate with keyframe_seed binds <FIRST_FRAME>@KeyframeSeed in INPUT ROLES & REFERENCES."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_studio",
            "project_id": "prj_director",
            "session_name": "keyframe_seed_test",
            "prompt": "",
            "clip_index": 1,
            "parent_turn_id": None,
            "concept": "Scene 2 with locked visual continuity keyframe seed",
            "keyframe_seed": "https://storage.googleapis.com/mock/seed_frame.png",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "YoTotti",
                    "description": "Young tatted wizard",
                    "reference_url": "gs://bucket/yototti.png",
                }
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role A"],
                    "action": "[0-3s] Role A steps into the hall. [3-6s] Role A raises goblet. [6-10s] Role A smiles.",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "<FIRST_FRAME>@KeyframeSeed" in data["raw_compiled_prompt"]


def test_generate_shot_endpoint_forces_fresh_turn0_even_with_parent_turn_id():
    """Verify POST /api/generate-shot ignores stale parent_turn_id so Shot 2 and Shot 3 always render as fresh Turn-0 clips."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res1 = client.post(
        "/api/generate-shot",
        json={
            "session_name": "shot_fresh_test",
            "shot_index": 1,
            "action": "[0-3s] Role A enters. [3-6s] Role A walks. [6-10s] Role A stops.",
            "parent_turn_id": None,
        },
    )
    assert res1.status_code == 200
    t1 = res1.json()["turn_id"]

    with patch.object(
        app.state.agent,
        "process_user_turn",
        wraps=app.state.agent.process_user_turn,
    ) as spy_turn:
        res2 = client.post(
            "/api/generate-shot",
            json={
                "session_name": "shot_fresh_test",
                "shot_index": 2,
                "action": "[0-3s] Role A speaks. [3-6s] Role A gestures. [6-10s] Role A nods.",
                "parent_turn_id": t1,
            },
        )
        assert res2.status_code == 200
        assert spy_turn.call_count == 1
        assert spy_turn.call_args.kwargs.get("parent_turn_id") is None


def test_generate_endpoint_with_placeholder_keyframe_seed_strips_first_frame_anchor():
    """Verify POST /api/generate with keyframe_seed='KeyframeSeed' filters out dummy token,
    preventing phantom FIRST_FRAME tag and off-by-one character image reference shifts."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/generate",
        json={
            "session_name": "seed_placeholder_filter_test",
            "clip_index": 0,
            "parent_turn_id": None,
            "concept": "Scene 1 with placeholder keyframe seed string",
            "keyframe_seed": "KeyframeSeed",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Bee Allison",
                    "description": "Trap wizard",
                    "reference_url": "gs://bucket/bee.png",
                },
                {
                    "role_id": "Role B",
                    "name": "YoTotti",
                    "description": "Young wizard",
                    "reference_url": "gs://bucket/yototti.png",
                },
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role A", "Role B"],
                    "action": "[0-5s] Role A speaks. [5-10s] Role B responds.",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    # <FIRST_FRAME>@KeyframeSeed must NOT be present when only a dummy placeholder token was provided
    assert "<FIRST_FRAME>" not in data["raw_compiled_prompt"]
