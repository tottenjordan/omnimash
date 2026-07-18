# Agent Orchestration Architecture

This document describes the orchestration loop and core subsystems powering the **OmniMash Agent** (`src/omnimash/agent/orchestrator.py`).

---

## 🖼️ Reference Architecture Diagram

![OmniMash Agent Architecture](omnimash_agent_architecture.png)

---

## 🏗️ Architectural Topology & Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Frontend UI
    participant API as FastAPI App (/api/generate)
    participant Agent as OmniMashAgent Orchestrator
    participant Guard as ModelArmorGuardrail
    participant Session as SessionManager (DAG)
    participant Taxonomy as PromptTaxonomyEngine
    participant Omni as OmniFlashClient (Interactions API)

    User->>API: POST /api/generate (user_id, project_id, prompt, parent_turn_id)
    API->>Agent: process_user_turn()
    
    Agent->>Guard: validate_prompt(prompt)
    alt RAI Policy Violation / Prompt Injection
        Guard-->>Agent: GuardrailResult(is_approved=False, reason="...")
        Agent-->>API: AgentTurnResponse(success=False, status="GUARDRAIL_BLOCKED")
        API-->>User: HTTP 200 / JSON (error="Policy violation...")
    else Approved Content
        Guard-->>Agent: GuardrailResult(is_approved=True, sanitized_prompt)
        Agent->>Session: get_or_create_session(user_id, project_id)
        
        alt Conversational Delta Diff (parent_turn_id provided)
            Agent->>Taxonomy: build_delta_prompt(parent_prompt, delta_instructions)
            Taxonomy-->>Agent: formatted_delta_prompt
            Agent->>Omni: apply_interaction_diff(interaction_thread_id, formatted_delta_prompt)
        else Initial Clip Generation
            Agent->>Taxonomy: build_initial_prompt(character, style_preset, instructions)
            Taxonomy-->>Agent: formatted_initial_prompt
            Agent->>Omni: generate_clip(formatted_initial_prompt)
        end
        
        Omni-->>Agent: GenerationResult(thread_id, video_url, duration=10s, watermark="SYNTHID")
        Agent->>Session: add_turn(clip_index, prompt, thread_id, video_url, parent_turn_id)
        Session-->>Agent: TurnNode(turn_id, ...)
        
        Agent-->>API: AgentTurnResponse(success=True, status="COMPLETED", video_url, turn_id)
        API-->>User: HTTP 200 / JSON {success: true, video_url, turn_id}
    end
```

---

## 🧩 Core Subsystem Responsibilities

1. **Model Armor Guardrail Gateway (`omnimash.security.guardrail`):**
   - Pre-gates all incoming prompts before executing expensive multimodal generation calls.
   - Screen for RAI violations (hate speech, sexual, harassment, dangerous content) and prompt injection/jailbreak attempts.

2. **Prompt Taxonomy Engine (`omnimash.prompts.taxonomy`):**
   - Applies style-blending heuristics across four core presets: `90s_rap_video`, `trap_disstrack`, `cyberpunk_drift`, and `vhs_anime`.
   - Structures lore anchors and scene constraints to preserve facial and lighting consistency across conversational diffs.

3. **Gemini Omni Flash Interactions Client (`omnimash.engine.omni_client`):**
   - Integrates with `google-genai` SDK and Gemini Omni Flash.
   - Preserves thread continuity across turns using `interaction_thread_id` and tags rendered video artifacts with SynthID / C2PA watermark provenance.
