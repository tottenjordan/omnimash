"""Tests for Mode 4: Director's Co-Pilot Intent Clarification and Auto-Orchestration API."""

import pytest
from fastapi.testclient import TestClient

from omnimash.agent.adk_pipeline import (
    INTENT_CLARIFIER_DEFAULT_INSTRUCTION,
    create_intent_clarifier_agent,
)
from omnimash.api.app import create_app


@pytest.fixture
def client():
    app = create_app(mock_mode=True)
    with TestClient(app) as c:
        yield c


# --- 1. Gap Analysis Endpoint Tests ---


def test_analyze_gaps_with_valid_intent_returns_questions(client):
    payload = {
        "intent": "Two rival chefs competing in an underground ramen kitchen battle",
        "optional_inputs": {
            "characters": ["Chef Kenji", "Chef Ren"],
        },
        "session_name": "ramen_showdown_session",
    }
    res = client.post("/api/intent/analyze-gaps", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["intent"] == payload["intent"]
    assert "Chef Kenji" in data["filled_slots"]["characters"]
    assert len(data["questions"]) >= 2
    assert len(data["questions"]) <= 3

    for q in data["questions"]:
        assert q["question_id"].startswith("q_")
        assert q["slot_target"] in (
            "characters",
            "setting",
            "style_tone",
            "audio_beat",
            "sound_effects",
            "dialogue",
        )
        assert len(q["options"]) >= 2
        assert q["allow_custom"] is True
        for opt in q["options"]:
            assert opt["id"] != ""
            assert opt["label"] != ""


@pytest.mark.parametrize("empty_intent", ["", "   ", "\t\n"])
def test_analyze_gaps_rejects_empty_intent(client, empty_intent):
    payload = {
        "intent": empty_intent,
    }
    res = client.post("/api/intent/analyze-gaps", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Missing intent"


# --- 2. Auto-Fill Plan Endpoint Tests ---


def test_auto_fill_plan_produces_cohesive_four_block_plan(client):
    payload = {
        "intent": "Cyberpunk bounty hunters cornering a rogue AI in a rain-slicked alley",
        "optional_inputs": {
            "setting": "Neo Neo-Tokyo alleyway beneath neon signs",
        },
        "question_answers": {
            "q_audio": "135 BPM Dark Synthwave with pounding 808s",
            "q_style": "High-contrast anamorphic 35mm with teal and magenta neon lighting",
        },
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "session_name": "cyber_bounty_session",
    }
    res = client.post("/api/intent/auto-fill", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    plan = data["plan"]
    assert "Neo-Tokyo" in plan["environment"]
    assert "135 BPM" in plan["audio_beat"] or "Synthwave" in plan["audio_beat"]
    assert len(plan["characters"]) >= 2

    raw_prompt = data["raw_compiled_prompt"]
    assert "### INPUT ROLES & REFERENCES" in raw_prompt
    assert "### CHARACTER PROFILES" in raw_prompt
    assert "### SCENE INSTRUCTIONS" in raw_prompt
    assert "### TIMELINE" in raw_prompt
    assert "[0-3s]" in raw_prompt or "[0.00s" in raw_prompt


@pytest.mark.parametrize("empty_intent", ["", "   "])
def test_auto_fill_plan_rejects_empty_intent(client, empty_intent):
    payload = {
        "intent": empty_intent,
    }
    res = client.post("/api/intent/auto-fill", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Missing intent"


# --- 3. Direct Render Endpoint Tests ---


def test_render_direct_dispatches_turn_and_returns_generate_response(client):
    payload = {
        "intent": "Two master wizards engaging in a lyrical wizard duel in an enchanted library",
        "optional_inputs": {
            "audio_beat": "140 BPM Heavy 808 Trap Beat with pipe organ stabs",
        },
        "question_answers": {
            "q_dialogue": "Sharp, fast-paced theatrical banter rhyming spell incantations",
        },
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "session_name": "wizard_duel_session",
    }
    res = client.post("/api/intent/render-direct", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] in ("COMPLETED", "LIVE_OMNI_FLASH", "STITCHED_SCENES")
    assert data["video_url"] is not None
    assert data["video_url"].endswith(".mp4")
    assert data["turn_id"] is not None
    assert data["raw_compiled_prompt"] is not None
    assert "### INPUT ROLES & REFERENCES" in data["raw_compiled_prompt"]
    assert "### TIMELINE" in data["raw_compiled_prompt"]


@pytest.mark.parametrize("empty_intent", ["", "   "])
def test_render_direct_rejects_empty_intent(client, empty_intent):
    payload = {
        "intent": empty_intent,
    }
    res = client.post("/api/intent/render-direct", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Missing intent"


# --- 4. ADK Agent Factory Tests ---


def test_create_intent_clarifier_agent_default():
    agent = create_intent_clarifier_agent()
    assert agent.name == "intent_clarifier"
    assert agent.instruction == INTENT_CLARIFIER_DEFAULT_INSTRUCTION
    assert isinstance(agent.instruction, str)
    assert "Director's Assistant & Intent Clarifier Agent" in agent.instruction
    assert "Gemini Omni Flash 1.1" in agent.instruction
    assert agent.tools == []


def test_create_intent_clarifier_agent_custom_overrides():
    custom_instruction = "Custom assistant instruction"
    custom_tools = [lambda x: x]
    agent = create_intent_clarifier_agent(
        name="custom_clarifier",
        model="gemini-4-argon",
        instruction=custom_instruction,
        tools=custom_tools,
    )
    assert agent.name == "custom_clarifier"
    assert agent.model == "gemini-4-argon"
    assert agent.instruction == custom_instruction
    assert agent.tools == custom_tools


def test_auto_fill_and_render_with_vault_characters_and_dialogue_direction(client):
    payload = {
        "intent": "Headmaster and young wizard auditing glowing gold galleons in a gothic vault",
        "optional_inputs": {
            "character_profiles": [
                {
                    "role_id": "Role A",
                    "name": "Dumble Dior",
                    "description": "Elderly high-fashion wizard headmaster with diamond spectacles",
                    "reference_url": "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/dumble_dior_office_sheet_v13.png",
                    "wardrobe": "Floor-length custom silk monogram wizard robe",
                    "voice_style": "Sharp, vigorous Oxford English cadence",
                },
                {
                    "role_id": "Role B",
                    "name": "YoTotti",
                    "description": "Confident young wizard in blue-shaded aviator sunglasses",
                    "reference_url": "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/yototti_office_sheet_v13.png",
                    "wardrobe": "Tailored black designer tracksuit and diamond chains",
                    "voice_style": "Calm, unfazed East London cadence",
                },
            ],
            "dialogue_direction": "Trade calm executive audit banter contrasting high-fashion luxury with overflowing magical wealth",
        },
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "session_name": "vault_audit_copilot",
    }
    res = client.post("/api/intent/auto-fill", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    plan = data["plan"]
    assert plan["dialogue_direction"] == payload["optional_inputs"]["dialogue_direction"]
    assert len(plan["characters"]) >= 2
    assert plan["characters"][0]["name"] == "Dumble Dior"
    assert plan["characters"][0]["reference_url"].endswith("dumble_dior_office_sheet_v13.png")
    assert plan["characters"][1]["name"] == "YoTotti"
    assert plan["characters"][1]["reference_url"].endswith("yototti_office_sheet_v13.png")
    assert "Dialogue Direction" in data["raw_compiled_prompt"]

    render_res = client.post("/api/intent/render-direct", json=payload)
    assert render_res.status_code == 200
    render_data = render_res.json()
    assert render_data["success"] is True
    assert "Dialogue Direction" in render_data["raw_compiled_prompt"]


def test_render_direct_with_compiled_override(client):
    custom_override = (
        "### INPUT ROLES & REFERENCES\n"
        "Role A: Dumble Dior [gs://bucket/dumble.png]\n"
        "### CHARACTER PROFILES\n"
        "[Role A] Dumble Dior: Master wizard in diamond spectacles.\n"
        "### SCENE INSTRUCTIONS\n"
        "[SCENE 1]\n"
        "Action: Casting a customized golden lumos spell.\n"
        "### TIMELINE\n"
        "[0-3s] Slow zoom in on glowing wand tip."
    )
    payload = {
        "intent": "Wizard duel in enchanted library",
        "compiled_override": custom_override,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "session_name": "custom_override_session",
    }
    res = client.post("/api/intent/render-direct", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["video_url"] is not None
    assert "golden lumos" in data["raw_compiled_prompt"]

