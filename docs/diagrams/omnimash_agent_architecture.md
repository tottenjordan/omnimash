# Agent Orchestration Architecture

This document describes the orchestration loop, safety gateways, and prompt compiler subsystems powering the **OmniMash Agent** (`src/omnimash/agent/orchestrator.py`).

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
    participant Compiler as PromptCompiler (Anchor & Inject)
    participant Session as SessionManager (DAG & Depth Tracker)
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
            Agent->>Compiler: build_delta_prompt(parent_prompt, delta_instructions)
            Compiler-->>Agent: formatted_delta_prompt (Anchor & Inject preservation)
            Agent->>Omni: apply_interaction_diff(interaction_thread_id, formatted_delta_prompt)
        else Initial Clip Generation
            Agent->>Compiler: compile(raw_prompt, style_preset, custom_instructions)
            Compiler-->>Agent: 5-Part Compiled Prompt ([SUBJECT ANCHOR] + [AESTHETIC INJECTION] + ...)
            Agent->>Omni: generate_clip(formatted_initial_prompt)
        end
        
        Omni-->>Agent: GenerationResult(thread_id, video_url, duration=10s, watermark="SYNTHID")
        Agent->>Session: add_turn(clip_index, prompt, thread_id, video_url, parent_turn_id)
        Session-->>Agent: TurnNode(turn_id, edit_depth_in_thread, ...)
        
        alt Thread Depth >= 3
            Agent-->>API: AgentTurnResponse(success=True, status="COMMIT_RECOMMENDED", depth=3)
        else Normal Turn
            Agent-->>API: AgentTurnResponse(success=True, status="COMPLETED", depth)
        end
        
        API-->>User: HTTP 200 / JSON {success: true, video_url, turn_id, status, depth}
    end
```

---

## 🧩 Core Subsystem Responsibilities

1. **Model Armor Guardrail Gateway (`omnimash.security.guardrail`):**
   - Pre-gates all incoming prompts before executing expensive multimodal generation calls.
   - Screen for RAI violations (hate speech, sexual, harassment, dangerous content) and prompt injection/jailbreak attempts.

2. **5-Part Prompt Compiler (`omnimash.prompts.compiler`):**
   - Implements the "Anchor & Inject" framework to eliminate character decay and latent space averaging.
   - Formats user shorthand into `[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + [ENVIRONMENT] + [CAMERA/LIGHTING] + [MOTION]`.

3. **Session Version DAG & Depth Tracker (`omnimash.state.session_manager`):**
   - Tracks `edit_depth_in_thread` across sequential turns.
   - Emits `COMMIT_RECOMMENDED` at depth $\ge 3$ and manages non-linear version branching.

4. **Gemini Omni Flash Interactions Client (`omnimash.engine.omni_client`):**
   - Integrates with `google-genai` SDK and Gemini Omni Flash.
   - Preserves thread continuity across turns using `interaction_thread_id`, supports `start_thread_from_video` on commits, and tags rendered video artifacts with SynthID / C2PA watermark provenance.
