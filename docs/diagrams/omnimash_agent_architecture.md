# Agent Orchestration Architecture

This document describes the orchestration loop, concept deconstruction engine, safety gateways, and prompt compiler subsystems powering the **OmniMash Agent** (`src/omnimash/agent/orchestrator.py`).

---

## 🖼️ Reference Architecture Diagram

![OmniMash Agent Architecture](omnimash_agent_architecture.png)

---

## 🏗️ Architectural Topology & Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as "User / Frontend UI (3-Act Studio)"
    participant API as "FastAPI App (/api/deconstruct-concept, /api/generate)"
    participant Agent as "OmniMashAgent Orchestrator"
    participant Guard as "ModelArmorGuardrail"
    participant Compiler as "PromptCompiler (Anchor, Deconstruct & Storyboard)"
    participant Session as "SessionManager (DAG & Depth Tracker)"
    participant Omni as "OmniFlashClient (Gemini Omni Flash)"

    %% 1. Act 1: Concept Deconstruction Flow
    Note over User,Omni: 🎭 Act 1: Concept Deconstruction & Character Casting
    User->>API: POST /api/deconstruct-concept (concept shorthand)
    API->>Compiler: deconstruct_concept(concept)
    Compiler-->>API: MetaPromptTags (Role A, Role B, Aesthetic, Environment, Audio)
    API-->>User: HTTP 200 / JSON (Editable Meta-Prompt Tags & Character Roles)

    %% 2. Act 2/3: Multi-Character Storyboard Video Generation
    Note over User,Omni: 🎬 Act 2 & 3: Storyboard Compilation & Video Synthesis
    User->>API: POST /api/generate (concept, characters + Image Role URLs, scenes, tags)
    API->>Agent: process_user_turn()
    
    Agent->>Guard: validate_prompt(concept/delta)
    alt RAI Policy Violation / Prompt Injection
        Guard-->>Agent: GuardrailResult(is_approved=False, reason="...")
        Agent-->>API: AgentTurnResponse(success=False, status="GUARDRAIL_BLOCKED")
        API-->>User: HTTP 200 / JSON (error="Policy violation...")
    else Approved Content
        Guard-->>Agent: GuardrailResult(is_approved=True, sanitized_prompt)
        Agent->>Session: get_or_create_session(user_id, project_id)
        
        alt Multi-Scene Storyboard Generation
            Agent->>Compiler: compile_storyboard(concept, characters, scenes, aesthetic_tags, ...)
            Compiler-->>Agent: Storyboard Prompt ([ROLE DEFINITIONS] + [AESTHETIC INJECTION] + [STORYBOARD SEQUENCE])
            Agent->>Omni: generate_clip(compiled_storyboard_prompt, character_role_image_urls)
        else Conversational Delta Diff (parent_turn_id provided)
            Agent->>Compiler: compile_delta(delta_instruction, custom_lock)
            Compiler-->>Agent: Delta Prompt ([PRESERVATION LOCK] + [ISOLATED DIFF])
            Agent->>Omni: apply_interaction_diff(interaction_thread_id, formatted_delta_prompt)
        else Single-Clip Baseline
            Agent->>Compiler: compile(raw_prompt, style_preset, ...)
            Compiler-->>Agent: 5-Part Compiled Prompt ([SUBJECT ANCHOR] + ...)
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
   - Screens for RAI violations (hate speech, sexual, harassment, dangerous content) and prompt injection/jailbreak attempts.

2. **Concept Deconstruction & Storyboard Prompt Compiler (`omnimash.prompts.compiler`):**
   - **NLP Concept Deconstruction (`deconstruct_concept`)**: Parses open-ended parody shorthand into structured `MetaPromptTags`, extracting character entities, aesthetic tags, environment settings, and audio beat tempo.
   - **Gemini Omni Image Roles Specification**: Defines `CharacterRole` bindings (`Role A`, `Role B`) with rich visual descriptions and attached reference image URLs ([Gemini Omni Image Roles API](https://ai.google.dev/gemini-api/docs/omni#set-image-roles)).
   - **Storyboard Sequence Compiler (`compile_storyboard`)**: Compiles multi-scene storyboards into three structured prompt blocks (`[ROLE DEFINITIONS]`, `[AESTHETIC INJECTION]`, and `[STORYBOARD SEQUENCE]`).
   - **Single-Clip & Delta Compilation**: Implements 5-part Anchor & Inject (`compile`) and 2-part Lock & Isolate (`compile_delta`).

3. **Session Version DAG & Depth Tracker (`omnimash.state.session_manager`):**
   - Tracks `edit_depth_in_thread` across sequential turns in a session tree.
   - Emits `COMMIT_RECOMMENDED` at depth $\ge 3$ and manages non-linear version branching.

4. **Gemini Omni Flash Interactions Client (`omnimash.engine.omni_client`):**
   - Integrates with Google GenAI SDK and Gemini Omni Flash (`gemini-omni-flash-preview`).
   - Generates 720p native MP4 video with synchronized audio and multi-character consistency.
   - Preserves thread continuity across turns using `interaction_thread_id`, supports `start_thread_from_video` on commits, and tags rendered video artifacts with SynthID / C2PA watermark provenance.
