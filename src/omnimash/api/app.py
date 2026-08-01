import logging
import os
import re
import uuid
from typing import Any
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.ingestion.media_extractor import (
    ParodyResearchResult,
    ReferenceAnalysisReport,
)
from omnimash.prompts.compiler import (
    CharacterRole,
    SceneDirective,
    sanitize_real_names,
)

logger = logging.getLogger(__name__)


class CharacterRoleModel(BaseModel):
    role_id: str
    name: str = ""
    description: str = ""
    reference_url: str | None = None
    aesthetic_tags: list[str] = []
    voice_style: str = ""
    voice_profile: str = ""
    wardrobe: str = ""
    image_role: str = "Character Reference"
    is_offscreen_narrator: bool = False




class SaveCharacterRequest(BaseModel):
    session_name: str | None = None
    character: CharacterRoleModel
    is_library: bool = True


class SaveCharacterResponse(BaseModel):
    success: bool = True
    gcs_uri: str = ""
    message: str = ""


class SessionListResponse(BaseModel):
    sessions: list[str]


class CharacterListResponse(BaseModel):
    characters: list[CharacterRoleModel] = []


class LoadCharacterRequest(BaseModel):
    slug: str
    session_name: str | None = None


class SaveRosterRequest(BaseModel):
    session_name: str
    characters: list[CharacterRoleModel]


class DeconstructResponse(BaseModel):
    characters: list[CharacterRoleModel] = []
    aesthetic_tags: list[str] = []
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
    vocal_delivery: str = ""


class ConceptDeconstructRequest(BaseModel):
    concept: str


class ResearchRequest(BaseModel):
    subject: str
    aesthetic: str


class ExtractReferenceRequest(BaseModel):
    url: str
    session_name: str | None = None


class GenerateRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    prompt: str = ""
    clip_index: int = 0
    parent_turn_id: str | None = None
    reference_url: str | None = None
    audio_stem: str | None = None
    voiceover: str | None = None
    is_silent: bool = False
    on_screen_text: str | None = None
    compiled_override: str | None = None
    session_name: str | None = None
    concept: str | None = None
    characters: list[CharacterRoleModel | dict] | None = None
    scenes: list[dict] | None = None
    aesthetic_tags: list[str] | None = None
    environment_tag: str | None = None
    vocal_delivery: str = ""
    optimize_prompt: bool = False
    shot_directive: str | None = None


class CommitRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    turn_id: str
    next_prompt: str = ""
    session_name: str | None = None


class SaveFinalRequest(BaseModel):
    session_name: str | None = None
    video_url: str
    master_title: str
    is_single_clip: bool = False
    master_audio_path: str | None = None
    master_audio_url: str | None = None


class StoryboardShotModel(BaseModel):
    shot_index: int
    duration_seconds: float
    action: str
    location: str
    style_lighting: str
    framing_motion: str
    audio: str
    dialogue: str = ""
    summary: str = ""
    keyframe_image_url: str = ""
    video_url: str = ""
    narrative_stage: str = "Rising Action"
    preceding_context: str = ""
    camera_transition: str = "Continuous match cut"
    character_continuity: str = "Maintain subject outfit, posture, and facial expression from preceding shot"


class StoryboardExpandRequest(BaseModel):
    concept: str
    style_tone: str = "Cinematic Trap Parody"
    target_duration: float = 30.0
    characters: list[CharacterRoleModel | dict] | None = None
    screenplay_script: str = ""
    directors_notes: str = ""


class StoryboardExpandResponse(BaseModel):
    shots: list[StoryboardShotModel]


class SaveStoryboardRequest(BaseModel):
    name: str
    storyboard_data: dict[str, Any]
    session_name: str | None = None
    is_library: bool = True


class SaveStoryboardResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str


class StoryboardMetadataModel(BaseModel):
    name: str
    slug: str
    concept: str = ""
    shot_count: int = 0
    updated_at: str = ""


class StoryboardListResponse(BaseModel):
    storyboards: list[StoryboardMetadataModel]


class LoadStoryboardRequest(BaseModel):
    slug: str
    session_name: str | None = None


class DeleteStoryboardRequest(BaseModel):
    slug: str
    session_name: str | None = None


class KeyframeImageRequest(BaseModel):
    shot_index: int = 1
    action: str = ""
    location: str = ""
    style_lighting: str = ""
    summary: str = ""
    characters: list[CharacterRoleModel | dict] | None = None
    reference_image_urls: list[str] | None = None
    anchor_keyframe_url: str | None = None



class KeyframeImageResponse(BaseModel):
    success: bool = True
    keyframe_image_url: str


class GenerateShotRequest(BaseModel):
    session_name: str | None = "parody_session_1"
    shot_index: int = 1
    shot_directive: str = ""
    action: str = ""
    location: str = ""
    framing_motion: str = ""
    audio: str = ""
    dialogue: str = ""
    characters: list[CharacterRoleModel | dict] | None = None
    duration_seconds: float = 10.0
    parent_turn_id: str | None = None
    keyframe_image_url: str | None = None
    style_lighting: str = ""
    audio_stem: str | None = None


class GenerateShotResponse(BaseModel):
    success: bool = True
    video_url: str | None = None
    keyframe_image_url: str | None = None
    turn_id: str | None = None
    status: str = "COMPLETED"
    generation_mode: str = "LIVE_OMNI_FLASH"
    error: str | None = None
    raw_compiled_prompt: str | None = None


class StitchClipsRequest(BaseModel):
    session_name: str
    clip_urls: list[str]
    master_title: str = "custom_stitched_cut"


class SaveFinalResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str
    video_url: str | None = None


class ExtendSceneRequest(BaseModel):
    session_name: str | None = None
    turn_id: str | None = None
    next_scene_action: str = ""
    dialogue: str | None = None
    active_roles: list[str] | None = None
    vocal_delivery: str = ""


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"
    raw_compiled_prompt: str | None = None
    reference_analysis: dict | None = None


UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OmniMash • Digital Director's Studio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <style>
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #0b0f19; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1f293d; border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #374151; }
    </style>
</head>
<body class="bg-gray-950 text-white font-sans antialiased min-h-screen">
    <div id="__next"></div>

    <script type="text/babel">
        const { useState, useEffect } = React;

        const getDisplayableRefUrl = (url) => {
            if (!url) return "";
            const clean = String(url).trim();
            if (clean.startsWith("gs://") || clean.startsWith("https://storage.googleapis.com/") || clean.startsWith("https://storage.cloud.google.com/")) {
                return `/api/media-proxy?uri=${encodeURIComponent(clean)}`;
            }
            return clean;
        };

        const getNextAvailableRoleId = (charList) => {
            const used = new Set((charList || []).map(c => c && c.role_id).filter(Boolean));
            for (let i = 0; i < 26; i++) {
                const candidate = `Role ${String.fromCharCode(65 + i)}`;
                if (!used.has(candidate)) return candidate;
            }
            return `Role ${(charList || []).length + 1}`;
        };

        const exampleConcepts = [
            "Gordon Ramsay vs Julia Child in a cyberpunk iron chef battle",
            "Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style",
            "Severus Snape in a 90s East Coast boom-bap rap video",
            "Cyborg Ninja vs Neon Samurai in an arcade showdown"
        ];

        function OmniMashApp() {
            // Navigation Act State (1: The Concept & Cast Manager, 2: Fine-Tune & Storyboard Directing, 3: The Screening Room & Branching)
            const [activeAct, setActiveAct] = useState(1);

            // Session & Project State
            const [sessionName, setSessionName] = useState("parody_session_1");
            const [availableSessions, setAvailableSessions] = useState([]);

            useEffect(() => {
                fetch("/api/sessions")
                    .then((res) => res.json())
                    .then((data) => {
                        if (data && data.sessions && data.sessions.length > 0) {
                            setAvailableSessions(data.sessions);
                            if (data.sessions[0]) {
                                setSessionName(data.sessions[0]);
                            }
                        }
                    })
                    .catch((err) => console.error("Failed to load sessions:", err));
            }, []);

            // Act 1: Character Vault & Saved Cast State
            const [savedVaultCharacters, setSavedVaultCharacters] = useState([]);

            useEffect(() => {
                fetch("/api/characters")
                    .then((res) => res.json())
                    .then((data) => {
                        if (data && data.characters) {
                            setSavedVaultCharacters(data.characters);
                        }
                    })
                    .catch((err) => console.error("Failed to load vault characters:", err));
            }, []);

            // Act 1: The Concept & Cast Manager State
            const [concept, setConcept] = useState("Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style");
            const [deconstructLoading, setDeconstructLoading] = useState(false);

            const [characters, setCharacters] = useState([
                {
                    role_id: "Role A",
                    name: "Harry",
                    description: "Harry Potter, a young wizard with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead",
                    reference_url: "https://example.com/harry.jpg",
                    aesthetic_tags: ["Red Gucci Tracksuit", "Cartier Glasses"],
                    voice_style: "Fast-paced confident Atlanta rap flow with autotune",
                    voice_profile: "High-energy young male wizard voice with rapid cadence",
                    wardrobe: "Red Gucci Tracksuit, Cartier wire-rim glasses"
                },
                {
                    role_id: "Role B",
                    name: "Draco",
                    description: "Draco Malfoy, a pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored silver-trimmed robes",
                    reference_url: "https://example.com/draco.jpg",
                    aesthetic_tags: ["Platinum Slicked Hair", "Diamond Iced-Out Chain"],
                    voice_style: "Pompous, cynical British drawl with aggressive rap cadence",
                    voice_profile: "Deep arrogant aristocratic drawl with precise articulation",
                    wardrobe: "Platinum slicked hair, diamond iced-out chain, silver-trimmed robes"
                }
            ]);
            const [charTagInputs, setCharTagInputs] = useState({});

            const [aestheticTags, setAestheticTags] = useState([
                "2000s Atlanta Trap Disstrack",
                "Diamond Lightning Bolt Chain",
                "Heavy 808 Bass Lighting",
                "Vintage Streetwear"
            ]);
            const [newTagInput, setNewTagInput] = useState("");

            const [environmentTag, setEnvironmentTag] = useState("Gothic Hogwarts courtyard lit by neon stage lights and smoky haze");
            const [cameraLightingTag, setCameraLightingTag] = useState("Low-angle 90s fisheye tracking shot with high-contrast green and purple neon rim lights");
            const [audioBeat, setAudioBeat] = useState("140 BPM Heavy 808 Trap");
            const [vocalDelivery, setVocalDelivery] = useState("High-energy back-and-forth rap battle delivery with synchronized lip-sync");

            // Act 2: Fine-Tune & Storyboard Directing State
            const [scenes, setScenes] = useState([
                {
                    scene_number: 1,
                    mode: "guided",
                    active_roles: ["Role A"],
                    action: "Arriving at foggy Hogwarts courtyard rapping into microphone wand",
                    dialogue: "I been cooking potions since first year. Burrr!",
                    screenplay_script: ""
                },
                {
                    scene_number: 2,
                    mode: "guided",
                    active_roles: ["Role B"],
                    action: "Stepping from shadows in high-gloss neon lighting with ice chain",
                    dialogue: "This is Trap or Die, Potter! Let's get it!",
                    screenplay_script: ""
                }
            ]);
            const [copied, setCopied] = useState(false);

            // Act 3: The Screening Room & Branching State
            const [currentVideo, setCurrentVideo] = useState("");
            const [deltaPrompt, setDeltaPrompt] = useState("");
            const [parentTurnId, setParentTurnId] = useState("");
            const [loading, setLoading] = useState(false);
            const [status, setStatus] = useState("COMPLETED");
            const [generationMode, setGenerationMode] = useState("LIVE_OMNI_FLASH");
            const [lastError, setLastError] = useState(null);
            const [showCommitModal, setShowCommitModal] = useState(false);
            const [commitPrompt, setCommitPrompt] = useState("");

            const initialRawPrompt = `[ROLE DEFINITIONS]\n- Role A (Harry): Harry Potter, a young wizard with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead [Style: Red Gucci Tracksuit, Cartier Glasses] (Ref: https://example.com/harry.jpg)\n- Role B (Draco): Draco Malfoy, a pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored silver-trimmed robes [Style: Platinum Slicked Hair, Diamond Iced-Out Chain] (Ref: https://example.com/draco.jpg)\n\n[AESTHETIC INJECTION]\nConcept: Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style\nAesthetic Tags: 2000s Atlanta Trap Disstrack, Diamond Lightning Bolt Chain, Heavy 808 Bass Lighting, Vintage Streetwear\nEnvironment: Gothic Hogwarts courtyard lit by neon stage lights and smoky haze\nCamera/Lighting: Low-angle 90s fisheye tracking shot with high-contrast green and purple neon rim lights\n\n[AUDIO & VOCAL DIRECTION]\nBackground Beat: 140 BPM Heavy 808 Trap (subtly ducked in the background beneath dialogue)\nVoice Style (Role A): Fast-paced confident Atlanta rap flow with autotune\nVoice Style (Role B): Pompous, cynical British drawl with aggressive rap cadence\nVocal Delivery: High-energy back-and-forth rap battle delivery with synchronized lip-sync\n\n[STORYBOARD SEQUENCE]\n- Scene 1 [Role A]: Arriving at foggy Hogwarts courtyard rapping into microphone wand | Dialogue: "I been cooking potions since first year. Burrr!"\n- Scene 2 [Role B]: Stepping from shadows in high-gloss neon lighting with ice chain | Dialogue: "This is Trap or Die, Potter! Let's get it!"`;

            const [rawCompiledPrompt, setRawCompiledPrompt] = useState(initialRawPrompt);
            const [masterTitle, setMasterTitle] = useState("official_rap_battle_master");
            const [saveModalMode, setSaveModalMode] = useState("master"); // "clip" | "master"
            const [savedGcsUri, setSavedGcsUri] = useState(null);
            const [showSaveModal, setShowSaveModal] = useState(false);
            const [saveLoading, setSaveLoading] = useState(false);
            const [extendLoading, setExtendLoading] = useState(false);

            const [showStitchModal, setShowStitchModal] = useState(false);
            const [selectedClipUrls, setSelectedClipUrls] = useState([]);
            const [stitchLoading, setStitchLoading] = useState(false);
            const [stitchResultGcs, setStitchResultGcs] = useState(null);

            // Studio Mode Switcher State ("acts" | "stages")
            const [studioMode, setStudioMode] = useState("stages");

            // 4-Stage Journey State (1: Vision, 2: Storyboard, 3: The Dailies, 4: The Final Cut)
            const [activeStage, setActiveStage] = useState(1);
            const [activeShotIdx, setActiveShotIdx] = useState(0);
            const [stageStyleTone, setStageStyleTone] = useState("🎨 90s Cel-Shaded Anime");
            const [stageTargetDuration, setStageTargetDuration] = useState(30.0);
            const [stageRefImage, setStageRefImage] = useState("");
            const [stageRefAudio, setStageRefAudio] = useState("");
            const [screenplayScript, setScreenplayScript] = useState("");
            const [showScreenplayModal, setShowScreenplayModal] = useState(false);
            const [storyboardPath, setStoryboardPath] = useState("path1");
            const [showBestPracticesModal, setShowBestPracticesModal] = useState(false);
            const [keyframeLoadingMap, setKeyframeLoadingMap] = useState({});
            const [shotGeneratingMap, setShotGeneratingMap] = useState({});
            const [shotDiffPrompts, setShotDiffPrompts] = useState({});
            const [shotDiffLoading, setShotDiffLoading] = useState({});
            const [showInspectorMap, setShowInspectorMap] = useState({});
            const [selectedShotIndex, setSelectedShotIndex] = useState(1);
            const [stageShots, setStageShots] = useState([
                {
                    shot_index: 1,
                    duration_seconds: 10.0,
                    summary: "Entrance & Concept Setup",
                    action: "[0-3s] Action: Establishing shot of foggy Hogwarts courtyard as Spectacled Wizard Bruv enters. Audio: Ambient wind and heavy 808 trap intro. Dialogue: Spectacled Wizard Bruv: \"I been cooking potions since first year.\"\n[3-6s] Action: Spectacled Wizard Bruv raises microphone wand as stage lights flare. Audio: Rhythmic snare trill.\n[6-10s] Action: Crowd cheering in background while fog drifts across courtyard. Audio: Full trap beat drop.",
                    location: "Dimly lit stone dungeon classroom with bubbling cauldrons",
                    style_lighting: "🎨 90s Cel-Shaded Anime, vibrant flat colors with sharp ink linework",
                    framing_motion: "Static medium shot with subtle handheld drift",
                    audio: "[0-3s] 140 BPM Trap Beat Intro | [3-10s] Heavy 808 Sub-Bass",
                    dialogue: "Spectacled Wizard Bruv: \"I been cooking potions since first year.\"",
                    camera_transition: "Continuous match cut from preceding shot",
                    character_continuity: "Maintain subject outfit, posture, and facial expression from preceding shot"
                },
                {
                    shot_index: 2,
                    duration_seconds: 10.0,
                    summary: "Dramatic Action & Potion Drink",
                    action: "[0-3s] Action: Platinum Rival Blood steps from shadows in high-gloss neon lighting. Audio: Heavy 808 trap beat drop. Dialogue: Platinum Rival Blood: \"This is Trap or Die, Potter! Let's get it!\"\n[3-6s] Action: Dynamic dolly zoom in on character face with diamond chain flashing. Audio: Sub-bass resonance.\n[6-10s] Action: Character holds up glowing potion bottle amidst green rim light. Audio: Rhythmic snare trills.",
                    location: "Gothic potion classroom with floating candles",
                    style_lighting: "🎨 90s Cel-Shaded Anime, expressive cel shading with dramatic rim light",
                    framing_motion: "Dynamic dolly zoom in on character face",
                    audio: "[0-3s] Heavy 808 Trap Beat Drop | [3-10s] Sub-Bass and Crisp Snares",
                    dialogue: "Platinum Rival Blood: \"This is Trap or Die, Potter! Let's get it!\"",
                    camera_transition: "Continuous match cut from preceding shot",
                    character_continuity: "Maintain subject outfit, posture, and facial expression from preceding shot"
                },
                {
                    shot_index: 3,
                    duration_seconds: 10.0,
                    summary: "Transformation Reveal & Drip Climax",
                    action: "[0-3s] Action: Both rap battle rivals step forward in upgraded aesthetic wardrobe under stage smoke. Audio: Aggressive trap beat climax. Dialogue: Both: \"Trap or Die!\"\n[3-6s] Action: Low angle pedestal shot moving upward slowly as neon stage flares flash. Audio: Heavy kick drum and synth riser.\n[6-10s] Action: Full stage view of crowd cheering in synchronized pulse. Audio: Final sub-bass decay.",
                    location: "High contrast courtyard with stage smoke and ambient flares",
                    style_lighting: "🎨 90s Cel-Shaded Anime, vivid pop art lighting with bold ink outlines",
                    framing_motion: "Low angle pedestal shot moving upward slowly",
                    audio: "[0-3s] Aggressive Trap Climax | [3-10s] Heavy Kick Drum & Synth Riser",
                    dialogue: "Both: \"Trap or Die!\"",
                    camera_transition: "Continuous match cut from preceding shot",
                    character_continuity: "Maintain subject outfit, posture, and facial expression from preceding shot"
                }
            ]);
            const [expandLoading, setExpandLoading] = useState(false);
            const [masterAudioUrl, setMasterAudioUrl] = useState("");
            const [stageSaveGcs, setStageSaveGcs] = useState(null);
            const [stageSaveLoading, setStageSaveLoading] = useState(false);
            const [isBatchGeneratingVideos, setIsBatchGeneratingVideos] = useState(false);
            const [batchVideoProgress, setBatchVideoProgress] = useState({ current: 0, total: 0, activeShotIndex: 0 });

            const getShotTimecodeRange = (shots, idx) => {
                if (!shots || idx < 0 || idx >= shots.length) return "0:00 - 0:10";
                let start = 0;
                for (let i = 0; i < idx; i++) {
                    start += shots[i].duration_seconds || 10;
                }
                const end = start + (shots[idx].duration_seconds || 10);
                const format = (sec) => {
                    const m = Math.floor(sec / 60);
                    const s = Math.floor(sec % 60);
                    return `${m}:${s < 10 ? "0" : ""}${s}`;
                };
                return `${format(start)} - ${format(end)}`;
            };

            // Handlers for 4-Stage Journey
            const handleExpandStoryboard = async () => {
                setExpandLoading(true);
                setLastError(null);
                try {
                    const res = await fetch("/api/storyboard/expand", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            concept: concept || "Parody music video clash",
                            style_tone: stageStyleTone,
                            target_duration: parseFloat(stageTargetDuration) || 30.0,
                            characters: characters,
                            screenplay_script: screenplayScript
                        })
                    });
                    const data = await res.json();
                    if (data && data.error) {
                        setLastError(data.error);
                    } else if (data && data.shots && data.shots.length > 0) {
                        setStageShots(data.shots);
                        setActiveShotIdx(0);
                        setActiveStage(2);
                        setTimeout(() => {
                            handleGenerateAllKeyframes(data.shots);
                        }, 100);
                    }
                } catch (err) {
                    console.error("Storyboard expansion failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setExpandLoading(false);
                }
            };

            const handleGenerateKeyframeImage = async (idx, shot) => {
                if (!shot) return null;
                const shotIdx = shot.shot_index || (idx + 1);
                setKeyframeLoadingMap((prev) => ({ ...prev, [shotIdx]: true }));
                setLastError(null);
                try {
                    const anchorUrl = (idx > 0 && stageShots[0] && stageShots[0].keyframe_image_url)
                        ? stageShots[0].keyframe_image_url
                        : null;
                    const res = await fetch("/api/storyboard/keyframe-image", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            shot_index: shotIdx,
                            action: shot.action || "",
                            location: shot.location || "",
                            style_lighting: shot.style_lighting || stageStyleTone,
                            summary: shot.summary || "",
                            characters: characters,
                            anchor_keyframe_url: anchorUrl
                        })
                    });
                    const data = await res.json();
                    if (data && data.keyframe_image_url) {
                        updateStageShot(idx, "keyframe_image_url", data.keyframe_image_url);
                        return data.keyframe_image_url;
                    } else if (data && data.error) {
                        setLastError(data.error);
                    }
                } catch (err) {
                    console.error("Keyframe image generation failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setKeyframeLoadingMap((prev) => ({ ...prev, [shotIdx]: false }));
                }
                return null;
            };

            const handleGenerateAllKeyframes = async (shotsToGenerate) => {
                const list = shotsToGenerate || stageShots;
                for (let i = 0; i < list.length; i++) {
                    await handleGenerateKeyframeImage(i, list[i]);
                }
            };

            const handleGenerateShotVideo = async (idx, shot, parentIdOverride = null) => {
                const shotIdx = shot.shot_index || (idx + 1);
                setShotGeneratingMap((prev) => ({ ...prev, [shotIdx]: true }));
                setLastError(null);
                try {
                    const parentTurnId = parentIdOverride || (idx > 0 && stageShots[idx - 1] ? stageShots[idx - 1].turn_id : null);
                    const res = await fetch("/api/generate-shot", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            session_name: sessionName,
                            shot_index: shotIdx,
                            action: shot.action || shot.summary || "",
                            location: shot.location || "",
                            style_lighting: shot.style_lighting || stageStyleTone || "",
                            framing_motion: shot.framing_motion || "",
                            audio: shot.audio || "",
                            dialogue: shot.dialogue || "",
                            keyframe_image_url: shot.keyframe_image_url || shot.image_url || null,
                            characters: characters,
                            duration_seconds: parseFloat(shot.duration_seconds) || 10.0,
                            parent_turn_id: parentTurnId,
                            audio_stem: shot.audio || null
                        })
                    });
                    const data = await res.json();
                    const errMsg = (data && (data.error || data.error_message || data.detail)) || null;
                    if (!res.ok || (data && data.success === false)) {
                        const finalErr = typeof errMsg === "string" ? errMsg : (errMsg ? JSON.stringify(errMsg) : `Shot video generation failed (Status ${res.status})`);
                        setLastError(finalErr);
                    }
                    if (data && data.video_url) {
                        updateStageShot(idx, "video_url", data.video_url);
                        updateStageShot(idx, "turn_id", data.turn_id);
                        if (data.raw_compiled_prompt) {
                            updateStageShot(idx, "raw_compiled_prompt", data.raw_compiled_prompt);
                            setRawCompiledPrompt(data.raw_compiled_prompt);
                        }
                        setCurrentVideo(data.video_url);
                        if (data.turn_id) setParentTurnId(data.turn_id);
                        return data.turn_id;
                    }
                } catch (err) {
                    console.error("Generate shot video failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setShotGeneratingMap((prev) => ({ ...prev, [shotIdx]: false }));
                }
                return null;
            };

            const handleApplyShotDiff = async (idx, shot) => {
                const sNum = shot.shot_index || (idx + 1);
                const diffText = (shotDiffPrompts[sNum] || "").trim();
                if (!diffText) return;

                setShotDiffLoading((prev) => ({ ...prev, [sNum]: true }));
                setLastError(null);
                try {
                    const res = await fetch("/api/diff", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "user_stage",
                            project_id: "proj_stage",
                            prompt: diffText,
                            parent_turn_id: shot.turn_id || null,
                            clip_index: idx,
                            session_name: sessionName
                        })
                    });
                    const data = await res.json();
                    if (data && data.video_url) {
                        updateStageShot(idx, "video_url", data.video_url);
                        if (data.turn_id) {
                            updateStageShot(idx, "turn_id", data.turn_id);
                        }
                        setShotDiffPrompts((prev) => ({ ...prev, [sNum]: "" }));
                    } else if (data && data.error) {
                        setLastError(data.error);
                    }
                } catch (err) {
                    console.error("Shot diff error:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setShotDiffLoading((prev) => ({ ...prev, [sNum]: false }));
                }
            };

            const handleGenerateAllShotVideosSequentially = async (autoNavigateToStage3 = false) => {
                if (!stageShots || stageShots.length === 0) return;
                setIsBatchGeneratingVideos(true);
                setBatchVideoProgress({ current: 0, total: stageShots.length, activeShotIndex: 1 });
                let lastTurnId = null;
                try {
                    for (let i = 0; i < stageShots.length; i++) {
                        const shot = stageShots[i];
                        const shotIdx = shot.shot_index || (i + 1);
                        setBatchVideoProgress({ current: i + 1, total: stageShots.length, activeShotIndex: shotIdx });
                        const createdTurnId = await handleGenerateShotVideo(i, shot, lastTurnId);
                        if (createdTurnId) {
                            lastTurnId = createdTurnId;
                        }
                    }
                    if (autoNavigateToStage3) {
                        setActiveStage(3);
                    }
                } catch (err) {
                    console.error("Batch video generation failed:", err);
                } finally {
                    setIsBatchGeneratingVideos(false);
                }
            };

            const updateStageShot = (idx, field, value) => {
                setStageShots((prevShots) => {
                    const updated = [...prevShots];
                    if (updated[idx]) {
                        updated[idx] = { ...updated[idx], [field]: value };
                    }
                    return updated;
                });
            };

            const handleGlobalStyleToneChange = (newTone, applyToAllShots = true) => {
                setStageStyleTone(newTone);
                if (applyToAllShots) {
                    setStageShots((prevShots) =>
                        prevShots.map((shot) => ({
                            ...shot,
                            style_lighting: `${newTone}, high-contrast lighting`
                        }))
                    );
                }
            };

            const addStageShot = () => {
                const nextIdx = stageShots.length + 1;
                setStageShots([
                    ...stageShots,
                    {
                        shot_index: nextIdx,
                        duration_seconds: 10.0,
                        action: "New shot directive and subject action",
                        location: "Cinematic set location",
                        style_lighting: `${stageStyleTone}, high-contrast lighting`,
                        framing_motion: "Medium tracking shot",
                        audio: "Atmospheric soundscape cue"
                    }
                ]);
            };

            const removeStageShot = (idx) => {
                if (stageShots.length <= 1) return;
                const updated = stageShots.filter((_, i) => i !== idx).map((s, i) => ({
                    ...s,
                    shot_index: i + 1
                }));
                setStageShots(updated);
            };

            const handleStageSaveFinal = async () => {
                setStageSaveLoading(true);
                setStageSaveGcs(null);
                try {
                    const res = await fetch("/api/save-final", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            session_name: sessionName,
                            video_url: currentVideo,
                            master_title: masterTitle || "final_master_export",
                            is_single_clip: false,
                            master_audio_url: masterAudioUrl || stageRefAudio || null
                        })
                    });
                    const data = await res.json();
                    if (data && data.gcs_uri) {
                        setStageSaveGcs(data.gcs_uri);
                    }
                    if (data && data.video_url) {
                        setCurrentVideo(data.video_url);
                    }
                } catch (err) {
                    console.error("Stage final save failed:", err);
                } finally {
                    setStageSaveLoading(false);
                }
            };

            const handleProceedToStage4 = async () => {
                setActiveStage(4);
                setTimeout(() => {
                    handleStageSaveFinal();
                }, 50);
            };

            const [history, setHistory] = useState([]);

            // Helper: Client-side Live Storyboard Prompt Compiler Preview (Four-Block Multimodal Structure)
            const compileStoryboardPreview = () => {
                const inputRoleLines = characters.filter(c => c.reference_url).map(c => {
                    const roleType = c.image_role || "Character Reference";
                    return `- ${c.role_id} (${roleType}): ${c.reference_url}`;
                });
                const inputRolesStr = inputRoleLines.length > 0 ? inputRoleLines.join("\n") : "None.";

                const charProfileLines = characters.map(c => {
                    const style = (c.aesthetic_tags && c.aesthetic_tags.length > 0) ? ` [Style: ${c.aesthetic_tags.join(", ")}]` : "";
                    const wardrobe = c.wardrobe ? ` [Wardrobe: ${c.wardrobe}]` : "";
                    const narrator = c.is_offscreen_narrator ? " [🎙️ Off-Screen Narrator]" : "";
                    const ref = c.reference_url ? ` (Ref: ${c.reference_url})` : "";
                    return `- ${c.role_id} (${c.name || "Unnamed"}): ${c.description || "No description"}${style}${wardrobe}${narrator}${ref}`;
                });
                const charProfilesStr = charProfileLines.length > 0 ? charProfileLines.join("\n") : "None.";

                const camHeader = cameraLightingTag || "In a single continuous shot. No scene cuts. High contrast cinematic lighting";
                const envStr = environmentTag || "Cinematic Studio Setting";
                const audioStr = audioBeat ? `Sound design: Foreground voiceover dominant. Background beat (${audioBeat}) subtly ducked.` : "Sound design: Standard audio.";
                const sceneInstStr = `Camera & Lighting: ${camHeader}\nEnvironment: ${envStr}\nAudio: ${audioStr}`;

                const sceneLines = scenes.map(s => {
                    const roles = (s.active_roles && s.active_roles.length > 0) ? s.active_roles.join(", ") : "All Roles";
                    const spScript = s.screenplay_script || s.screenplay_text;
                    if ((s.mode === "screenplay" || spScript) && spScript && spScript.trim()) {
                        const indented = spScript.trim().split("\n").map(l => `  ${l}`).join("\n");
                        return `- Scene ${s.scene_number} [${roles}] (Screenplay Script):\n${indented}`;
                    }
                    const diag = (s.dialogue && s.dialogue.trim()) ? ` | Dialogue: "${s.dialogue.trim()}"` : "";
                    return `- Scene ${s.scene_number} [${roles}]: ${s.action || "Action description"}${diag}`;
                }).join("\n");
                const timelineStr = sceneLines || "- No scenes";

                return `### INPUT ROLES\n${inputRolesStr}\n\n### CHARACTER PROFILES\n${charProfilesStr}\n\n### SCENE INSTRUCTIONS\n${sceneInstStr}\n\n### TIMELINE\n${timelineStr}`;
            };

            // Act 1 Handler: Deconstruct Concept (POST /api/deconstruct-concept)
            const handleDeconstructConcept = async (conceptOverride) => {
                const targetConcept = (typeof conceptOverride === "string" && conceptOverride.trim()) ? conceptOverride : concept;
                if (!targetConcept || !targetConcept.trim()) return;
                setParentTurnId(null);
                setRawCompiledPrompt("");
                setDeconstructLoading(true);
                try {
                    const res = await fetch("/api/deconstruct-concept", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ concept: targetConcept })
                    });
                    const data = await res.json();
                    if (data.characters && data.characters.length > 0) {
                        const formattedChars = data.characters.map(c => ({
                            ...c,
                            aesthetic_tags: c.aesthetic_tags || [],
                            voice_style: c.voice_style || "",
                            voice_profile: c.voice_profile || "",
                            wardrobe: c.wardrobe || ""
                        }));
                        setCharacters(formattedChars);
                        const newScenes = formattedChars.map((char, idx) => ({
                            scene_number: idx + 1,
                            active_roles: [char.role_id],
                            action: `${char.name || char.role_id} in action sequence`,
                            dialogue: ""
                        }));
                        if (newScenes.length > 0) setScenes(newScenes);
                    }
                    if (data.aesthetic_tags) setAestheticTags(data.aesthetic_tags);
                    if (data.environment_tag) setEnvironmentTag(data.environment_tag);
                    if (data.camera_lighting_tag) setCameraLightingTag(data.camera_lighting_tag);
                    if (data.audio_beat) setAudioBeat(data.audio_beat);
                    if (data.vocal_delivery) setVocalDelivery(data.vocal_delivery);
                } catch (err) {
                    console.error("Deconstruction failed:", err);
                } finally {
                    setDeconstructLoading(false);
                }
            };

            // Character Vault & Saved Cast Management
            const handleSaveCharacterToVault = async (char) => {
                try {
                    const res = await fetch("/api/characters/save", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            character: char,
                            session_name: sessionName,
                            is_library: true
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        const listRes = await fetch("/api/characters");
                        const listData = await listRes.json();
                        if (listData && listData.characters) {
                            setSavedVaultCharacters(listData.characters);
                        }
                    }
                } catch (err) {
                    console.error("Save character to vault failed:", err);
                }
            };

            const handleLoadVaultCharacter = (c) => {
                const roleId = getNextAvailableRoleId(characters);
                const newRole = {
                    role_id: roleId,
                    name: c.name || "",
                    description: c.description || "",
                    reference_url: c.reference_url || "",
                    voice_style: c.voice_style || "",
                    voice_profile: c.voice_profile || "",
                    wardrobe: c.wardrobe || "",
                    aesthetic_tags: c.aesthetic_tags ? [...c.aesthetic_tags] : []
                };
                setCharacters([...characters, newRole]);
            };


            const handleSaveSessionRoster = async () => {
                try {
                    await fetch("/api/characters/save-roster", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            session_name: sessionName,
                            characters: characters
                        })
                    });
                } catch (err) {
                    console.error("Save session roster failed:", err);
                }
            };

            const handleLoadSessionRoster = async (targetSessionName) => {
                const targetSession = targetSessionName || sessionName;
                try {
                    const res = await fetch(`/api/characters/roster?session_name=${encodeURIComponent(targetSession)}`);
                    const data = await res.json();
                    if (data && data.characters) {
                        const restored = [];
                        for (const c of data.characters) {
                            const roleId = c.role_id || getNextAvailableRoleId(restored);
                            restored.push({
                                role_id: roleId,
                                name: c.name || "",
                                description: c.description || "",
                                reference_url: c.reference_url || "",
                                voice_style: c.voice_style || "",
                                voice_profile: c.voice_profile || "",
                                wardrobe: c.wardrobe || "",
                                aesthetic_tags: c.aesthetic_tags ? [...c.aesthetic_tags] : []
                            });
                        }
                        setCharacters(restored);
                    }
                } catch (err) {
                    console.error("Load session roster failed:", err);
                }
            };

            // Character Roles management
            const addCharacterRole = () => {
                const roleId = getNextAvailableRoleId(characters);
                const letter = roleId.replace("Role ", "");
                const newRole = {
                    role_id: roleId,
                    name: `Character ${letter}`,
                    description: "Distinct cinematic character with expressive facial features and stylized attire",
                    reference_url: "",
                    aesthetic_tags: [],
                    voice_style: "",
                    voice_profile: "",
                    wardrobe: ""
                };
                setCharacters([...characters, newRole]);
            };

            const updateCharacter = (index, field, value) => {
                const updated = [...characters];
                updated[index] = { ...updated[index], [field]: value };
                setCharacters(updated);
            };

            const addCharAestheticTag = (charIndex) => {
                const inputVal = (charTagInputs[charIndex] || "").trim();
                if (!inputVal) return;
                const currentTags = characters[charIndex].aesthetic_tags || [];
                if (!currentTags.includes(inputVal)) {
                    updateCharacter(charIndex, "aesthetic_tags", [...currentTags, inputVal]);
                }
                setCharTagInputs(prev => ({ ...prev, [charIndex]: "" }));
            };

            const removeCharAestheticTag = (charIndex, tagToRemove) => {
                const currentTags = characters[charIndex].aesthetic_tags || [];
                updateCharacter(charIndex, "aesthetic_tags", currentTags.filter(t => t !== tagToRemove));
            };

            const removeCharacter = (index) => {
                if (characters.length <= 1) return;
                const removedRoleId = characters[index].role_id;
                const updated = characters.filter((_, i) => i !== index);
                setCharacters(updated);
                setScenes(scenes.map(s => ({
                    ...s,
                    active_roles: (s.active_roles || []).filter(r => r !== removedRoleId)
                })));
            };

            // Aesthetic tags management
            const handleAddAestheticTag = (e) => {
                if (e) e.preventDefault();
                if (newTagInput.trim() && !aestheticTags.includes(newTagInput.trim())) {
                    setAestheticTags([...aestheticTags, newTagInput.trim()]);
                    setNewTagInput("");
                }
            };

            const removeAestheticTag = (tagToRemove) => {
                setAestheticTags(aestheticTags.filter(t => t !== tagToRemove));
            };

            // Scenes management
            const addScene = () => {
                const nextNum = scenes.length + 1;
                const newScene = {
                    scene_number: nextNum,
                    mode: "guided",
                    active_roles: [characters[0]?.role_id || "Role A"],
                    action: "",
                    dialogue: "",
                    screenplay_script: ""
                };
                setScenes([...scenes, newScene]);
            };

            const updateScene = (index, field, value) => {
                const updated = [...scenes];
                updated[index] = { ...updated[index], [field]: value };
                setScenes(updated);
            };

            const toggleSceneRole = (sceneIndex, roleId) => {
                const scene = scenes[sceneIndex];
                const active = scene.active_roles || [];
                const nextActive = active.includes(roleId)
                    ? active.filter(r => r !== roleId)
                    : [...active, roleId];
                updateScene(sceneIndex, "active_roles", nextActive);
            };

            const removeScene = (index) => {
                if (scenes.length <= 1) return;
                const updated = scenes.filter((_, i) => i !== index).map((s, idx) => ({
                    ...s,
                    scene_number: idx + 1
                }));
                setScenes(updated);
            };

            // Act 3 Handler: Generate Parody Cut (POST /api/generate or POST /api/diff)
            const handleGenerate = async (e) => {
                if (e && e.preventDefault) e.preventDefault();
                setLoading(true);
                try {
                    const selectedShotObj = stageShots.find(s => (s.shot_index || (stageShots.indexOf(s) + 1)) === selectedShotIndex);
                    const shotTurnId = selectedShotObj?.turn_id || parentTurnId || null;
                    const payload = {
                        user_id: "usr_studio",
                        project_id: "prj_director",
                        prompt: deltaPrompt || concept,
                        clip_index: (selectedShotIndex - 1) >= 0 ? (selectedShotIndex - 1) : 0,
                        parent_turn_id: shotTurnId,
                        session_name: sessionName,
                        concept: concept,
                        characters: characters,
                        scenes: scenes,
                        aesthetic_tags: aestheticTags,
                        environment_tag: environmentTag,
                        audio_stem: audioBeat,
                        vocal_delivery: vocalDelivery
                    };
                    const endpoint = shotTurnId ? "/api/diff" : "/api/generate";
                    const res = await fetch(endpoint, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });
                    const data = await res.json();
                    if (data.generation_mode) setGenerationMode(data.generation_mode);
                    setLastError(data.error || null);
                    if (data.success) {
                        const compiled = data.raw_compiled_prompt || compileStoryboardPreview();
                        if (compiled) setRawCompiledPrompt(compiled);

                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: deltaPrompt || concept,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            lock: "Maintain character role likeness, aesthetic tags, and scene sequence.",
                            diff: deltaPrompt ? `Conversational diff: ${deltaPrompt}` : `Parody cut from storyboard`,
                            rawCompiledPrompt: compiled
                        };
                        setHistory(prev => [...prev, newTurn]);
                        setCurrentVideo(data.video_url);
                        setParentTurnId(data.turn_id);
                        setStatus(data.status);
                        setDeltaPrompt("");
                        setActiveAct(3);

                        if (studioMode === "stages" || activeStage >= 2) {
                            setStageShots((prevShots) => {
                                const updated = [...prevShots];
                                const targetIdx = prevShots.findIndex(s => (s.shot_index || (prevShots.indexOf(s) + 1)) === selectedShotIndex);
                                if (targetIdx >= 0) {
                                    updated[targetIdx] = {
                                        ...updated[targetIdx],
                                        video_url: data.video_url,
                                        turn_id: data.turn_id
                                    };
                                }
                                return updated;
                            });
                        }

                        if (data.status === "COMMIT_RECOMMENDED") {
                            setShowCommitModal(true);
                        }
                    }
                } catch (err) {
                    console.error("Generation failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setLoading(false);
                }
            };

            // Commit & Re-Anchor Handler (POST /api/commit)
            const handleCommit = async () => {
                setLoading(true);
                try {
                    const nextPrompt = commitPrompt || "Re-anchored checkpoint";
                    const res = await fetch("/api/commit", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "usr_studio",
                            project_id: "prj_director",
                            turn_id: parentTurnId,
                            next_prompt: nextPrompt,
                            session_name: sessionName
                        })
                    });
                    const data = await res.json();
                    if (data.generation_mode) setGenerationMode(data.generation_mode);
                    setLastError(data.error || null);
                    if (data.success) {
                        const compiled = data.raw_compiled_prompt || rawCompiledPrompt;
                        if (compiled) setRawCompiledPrompt(compiled);

                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: nextPrompt,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            lock: "New baseline re-anchored keyframe lock established.",
                            diff: `Checkpoint commit: ${nextPrompt}`,
                            rawCompiledPrompt: compiled
                        };
                        setHistory(prev => [...prev, newTurn]);
                        setCurrentVideo(data.video_url);
                        setParentTurnId(data.turn_id);
                        setStatus(data.status);
                        setShowCommitModal(false);
                        setCommitPrompt("");
                    }
                } catch (err) {
                    console.error("Commit failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setLoading(false);
                }
            };

            // Save Final Master Handler (POST /api/save-final)
            const handleSaveFinal = async () => {
                setSaveLoading(true);
                try {
                    const res = await fetch("/api/save-final", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            session_name: sessionName,
                            video_url: currentVideo,
                            master_title: masterTitle || "final_master",
                            is_single_clip: saveModalMode === "clip"
                        })
                    });
                    const data = await res.json();
                    if (data.success && data.gcs_uri) {
                        setSavedGcsUri(data.gcs_uri);
                        setShowSaveModal(false);
                    } else if (data.error) {
                        setLastError(data.error);
                    }
                } catch (err) {
                    console.error("Save final master failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setSaveLoading(false);
                }
            };

            // Stitch Selected Clips Handler (POST /api/stitch-clips)
            const handleStitchSelectedClips = async () => {
                if (!selectedClipUrls || selectedClipUrls.length === 0) return;
                setStitchLoading(true);
                setStitchResultGcs(null);
                try {
                    const res = await fetch("/api/stitch-clips", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            session_name: sessionName,
                            clip_urls: selectedClipUrls,
                            master_title: masterTitle || "custom_stitched_cut"
                        })
                    });
                    const data = await res.json();
                    if (data.success && data.gcs_uri) {
                        setStitchResultGcs(data.gcs_uri);
                        setSavedGcsUri(data.gcs_uri);
                    } else if (data.error) {
                        setLastError(data.error);
                    }
                } catch (err) {
                    console.error("Stitch clips failed:", err);
                    setLastError(err.message || String(err));
                } finally {
                    setStitchLoading(false);
                }
            };

            // Extend Scene Handler (POST /api/extend-scene)
            const handleExtendScene = async () => {
                setExtendLoading(true);
                try {
                    const nextSceneNum = scenes.length + 1;
                    const nextAction = `Scene ${nextSceneNum} continuation sequence`;
                    const res = await fetch("/api/extend-scene", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            session_name: sessionName,
                            turn_id: parentTurnId || null,
                            next_scene_action: nextAction,
                            dialogue: "",
                            active_roles: [characters[0]?.role_id || "Role A"],
                            vocal_delivery: vocalDelivery
                        })
                    });
                    const data = await res.json();
                    if (data.generation_mode) setGenerationMode(data.generation_mode);
                    if (data.success) {
                        const compiled = data.raw_compiled_prompt || compileStoryboardPreview();
                        if (compiled) setRawCompiledPrompt(compiled);
                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: nextAction,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            lock: "Extended scene sequence lock.",
                            diff: `Extended Scene #${nextSceneNum}`,
                            rawCompiledPrompt: compiled
                        };
                        setHistory(prev => [...prev, newTurn]);
                        if (data.video_url) setCurrentVideo(data.video_url);
                        setParentTurnId(data.turn_id);
                        setStatus(data.status);

                        const newScene = {
                            scene_number: nextSceneNum,
                            active_roles: [characters[0]?.role_id || "Role A"],
                            action: nextAction,
                            dialogue: ""
                        };
                        setScenes([...scenes, newScene]);
                        setActiveAct(2);
                    }
                } catch (err) {
                    console.error("Extend scene failed:", err);
                    addScene();
                    setActiveAct(2);
                } finally {
                    setExtendLoading(false);
                }
            };

            // Helper: Reset Studio / Start Over
            const handleResetStudio = () => {
                setConcept("");
                setCharacters([]);
                setAestheticTags([]);
                setEnvironmentTag("");
                setCameraLightingTag("");
                setAudioBeat("");
                setVocalDelivery("");
                setScenes([]);
                setHistory([]);
                setParentTurnId(null);
                setDeltaPrompt("");
                setRawCompiledPrompt("");
                setActiveAct(1);
            };

            const handleCreateNewSession = () => {
                const input = window.prompt("Enter new GCS session folder name:", "");
                let cleaned = (input || "").toLowerCase().replace(/[^a-z0-9_-]/g, "");
                if (!cleaned) {
                    cleaned = `session_${Date.now()}`;
                }
                setSessionName(cleaned);
                setAvailableSessions((prev) => (prev.includes(cleaned) ? prev : [...prev, cleaned]));
                handleResetStudio();
            };

            const isCommitModalVisible = status === "COMMIT_RECOMMENDED" || showCommitModal;


            return (
                <div className="flex flex-col min-h-screen bg-gray-950 text-gray-100">
                    {/* Commit & Re-Anchor Modal */}
                    {isCommitModalVisible && (
                        <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
                            <div className="bg-gray-900 border-2 border-amber-500/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
                                <div className="flex items-center space-x-3 bg-amber-950/80 border border-amber-500/50 rounded-xl p-4 mb-5 text-amber-300">
                                    <span className="text-2xl">⚠️</span>
                                    <div>
                                        <h3 className="font-bold text-base text-amber-200">Commit &amp; Re-Anchor Required</h3>
                                        <p className="text-xs text-amber-300/80 mt-0.5">Edit depth limit reached (Depth &ge; 3). Re-anchoring establishes a fresh keyframe baseline to prevent visual drift.</p>
                                    </div>
                                </div>
                                <div className="space-y-4 mb-6">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">Re-Anchor Prompt / Summary</label>
                                        <input
                                            type="text"
                                            value={commitPrompt}
                                            onChange={(e) => setCommitPrompt(e.target.value)}
                                            placeholder="e.g. Master keyframe lock for Act 3..."
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500"
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center justify-end space-x-3">
                                    <button
                                        type="button"
                                        onClick={() => setShowCommitModal(false)}
                                        className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white"
                                    >
                                        Dismiss
                                    </button>
                                    <button
                                        type="button"
                                        disabled={loading}
                                        onClick={handleCommit}
                                        className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 text-black font-bold text-xs py-2.5 px-5 rounded-lg shadow-lg flex items-center gap-2"
                                    >
                                        <span>⚓</span>
                                        <span>{loading ? "Committing..." : "Commit & Re-Anchor"}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Save Final Master Modal */}
                    {showSaveModal && (
                        <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
                            <div className="bg-gray-900 border-2 border-amber-500/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
                                <div className="flex items-center space-x-3 bg-amber-950/80 border border-amber-500/50 rounded-xl p-4 mb-5 text-amber-300">
                                    <span className="text-2xl">{saveModalMode === "clip" ? "💾" : "🎬"}</span>
                                    <div>
                                        <h3 className="font-bold text-base text-amber-200">
                                            {saveModalMode === "clip" ? "Save Active Clip to GCS" : "Stitch & Save Session Master (30–60s) to GCS"}
                                        </h3>
                                        <p className="text-xs text-amber-300/80 mt-0.5">
                                            {saveModalMode === "clip"
                                                ? "Export and save the currently active 10-second scene clip directly to Google Cloud Storage."
                                                : "OmniMash will automatically concatenate all 10-second scene clips and audio stems generated in this session into a single 30–60s master MP4 file exported to Google Cloud Storage."}
                                        </p>
                                    </div>
                                </div>
                                <div className="space-y-4 mb-6">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">
                                            {saveModalMode === "clip" ? "Clip Title" : "Master Title"}
                                        </label>
                                        <input
                                            type="text"
                                            value={masterTitle}
                                            onChange={(e) => setMasterTitle(e.target.value)}
                                            placeholder={saveModalMode === "clip" ? "e.g. active_scene_clip_1" : "e.g. official_rap_battle_master"}
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 font-mono"
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center justify-end space-x-3">
                                    <button
                                        type="button"
                                        onClick={() => setShowSaveModal(false)}
                                        className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="button"
                                        disabled={saveLoading || !masterTitle.trim()}
                                        onClick={handleSaveFinal}
                                        className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 text-black font-bold text-xs py-2.5 px-5 rounded-lg shadow-lg flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <span>💾</span>
                                        <span>
                                            {saveLoading
                                                ? "Saving..."
                                                : saveModalMode === "clip"
                                                ? "Save Active Clip to GCS"
                                                : "Stitch & Save Master (30–60s) to GCS"}
                                        </span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Stitch & Combine Selected Clips Modal */}
                    {showStitchModal && (
                        <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
                            <div className="bg-gray-900 border-2 border-purple-500/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
                                <div className="flex items-center space-x-3 bg-purple-950/80 border border-purple-500/50 rounded-xl p-4 mb-5 text-purple-300">
                                    <span className="text-2xl">🎬</span>
                                    <div>
                                        <h3 className="font-bold text-base text-purple-200">Stitch &amp; Combine Selected Clips</h3>
                                        <p className="text-xs text-purple-300/80 mt-0.5">Select specific scene clips from your session history to concatenate into a custom master video exported to GCS.</p>
                                    </div>
                                </div>
                                <div className="space-y-4 mb-6">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">Master Title</label>
                                        <input
                                            type="text"
                                            value={masterTitle}
                                            onChange={(e) => setMasterTitle(e.target.value)}
                                            placeholder="e.g. custom_stitched_cut"
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-2">Select Clips from History to Concatenate</label>
                                        <div className="max-h-48 overflow-y-auto space-y-2 border border-gray-800 rounded-xl p-3 bg-gray-950 custom-scrollbar">
                                            {history.map((turn, idx) => {
                                                const clipUrl = turn.videoUrl;
                                                const isChecked = selectedClipUrls.includes(clipUrl);
                                                return (
                                                    <label key={idx} className="flex items-center space-x-3 text-xs text-gray-300 cursor-pointer hover:bg-gray-900 p-2 rounded-lg transition">
                                                        <input
                                                            type="checkbox"
                                                            checked={isChecked}
                                                            onChange={(e) => {
                                                                if (e.target.checked) {
                                                                    setSelectedClipUrls([...selectedClipUrls, clipUrl]);
                                                                } else {
                                                                    setSelectedClipUrls(selectedClipUrls.filter(u => u !== clipUrl));
                                                                }
                                                            }}
                                                            className="rounded border-gray-700 text-purple-600 focus:ring-purple-500 bg-gray-900 w-4 h-4"
                                                        />
                                                        <div className="flex-1 min-w-0">
                                                            <div className="font-bold text-gray-200 truncate">Turn #{idx + 1}: {turn.prompt}</div>
                                                            <div className="text-[10px] text-gray-500 font-mono truncate">{clipUrl}</div>
                                                        </div>
                                                    </label>
                                                );
                                            })}
                                            {history.length === 0 && (
                                                <div className="text-xs text-gray-500 italic p-2">No generated clips available in history.</div>
                                            )}
                                        </div>
                                    </div>
                                    {stitchResultGcs && (
                                        <div className="bg-green-950/60 border border-green-500/80 rounded-xl p-3 text-xs text-green-300 break-all font-mono">
                                            <span className="font-bold block text-green-200 mb-1">✓ Custom Cut Saved:</span>
                                            {stitchResultGcs}
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center justify-end space-x-3">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowStitchModal(false);
                                            setStitchResultGcs(null);
                                        }}
                                        className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white"
                                    >
                                        Close
                                    </button>
                                    <button
                                        type="button"
                                        disabled={stitchLoading || selectedClipUrls.length === 0 || !masterTitle.trim()}
                                        onClick={handleStitchSelectedClips}
                                        className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold text-xs py-2.5 px-5 rounded-lg shadow-lg flex items-center gap-2 disabled:opacity-50"
                                    >
                                        <span>🎬</span>
                                        <span>{stitchLoading ? "Concatenating..." : "🎬 Concatenate Selected Videos"}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Top Application Header & Toolbar */}
                    <header className="border-b border-gray-800 bg-gray-900/90 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center space-x-4">
                            <div className="flex items-center space-x-2">
                                <span className="text-2xl">🎬</span>
                                <div>
                                    <h1 className="text-lg font-extrabold bg-gradient-to-r from-purple-400 via-pink-400 to-amber-400 bg-clip-text text-transparent">
                                        OMNIMASH • DIGITAL DIRECTOR'S STUDIO
                                    </h1>
                                    <p className="text-[11px] text-gray-400">Gemini Omni Flash 30–60s Parody &amp; Storyboard Studio</p>
                                </div>
                            </div>
                        </div>

                        {/* Studio Mode Switcher Toggle */}
                        <div className="flex items-center bg-gray-950 border border-gray-800 rounded-xl p-1 shadow-inner">
                            <button
                                type="button"
                                onClick={() => setStudioMode("acts")}
                                className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                                    studioMode === "acts"
                                        ? "bg-purple-600 text-white shadow shadow-purple-900/50"
                                        : "text-gray-400 hover:text-gray-200"
                                }`}
                            >
                                <span>🎭</span>
                                <span>Act-Based Director Mode</span>
                            </button>
                            <button
                                type="button"
                                onClick={() => setStudioMode("stages")}
                                className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                                    studioMode === "stages"
                                        ? "bg-gradient-to-r from-amber-500 to-orange-500 text-black shadow shadow-amber-900/50 font-extrabold"
                                        : "text-gray-400 hover:text-gray-200"
                                }`}
                            >
                                <span>🎬</span>
                                <span>4-Stage Storyboard Journey</span>
                            </button>
                        </div>

                        {/* GCS Session Name & Reset Studio */}
                        <div className="flex items-center space-x-3">
                            <button
                                type="button"
                                onClick={() => setShowBestPracticesModal(true)}
                                className="bg-gradient-to-r from-purple-900/80 to-pink-900/80 hover:from-purple-800 hover:to-pink-800 text-purple-200 border border-purple-600/60 rounded-lg px-3 py-1.5 text-xs font-bold flex items-center gap-1.5 transition shadow-sm"
                            >
                                <span>💡 Prompt Best Practices &amp; Examples</span>
                            </button>
                            <button
                                onClick={handleResetStudio}
                                className="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 transition shadow-sm"
                            >
                                <span>🔄 New Project / Start Over</span>
                            </button>
                            <div className="bg-black/60 border border-gray-800 rounded-lg px-3 py-1.5 flex items-center space-x-2">
                                <span className="text-xs text-purple-400">🗂️ GCS Session:</span>
                                <select
                                    value={sessionName}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        if (val) {
                                            setSessionName(val);
                                            handleLoadSessionRoster(val);
                                        }
                                    }}
                                    className="bg-gray-900 border border-gray-700 text-xs font-mono text-purple-200 rounded px-2 py-1 focus:outline-none focus:border-purple-400"
                                >
                                    <option value="">-- Select Session --</option>
                                    {availableSessions.map((s) => (
                                        <option key={s} value={s}>{s}</option>
                                    ))}
                                </select>
                                <input
                                    type="text"
                                    value={sessionName}
                                    onChange={(e) => setSessionName(e.target.value)}
                                    onBlur={() => {
                                        if (sessionName.trim()) {
                                            setAvailableSessions((prev) => (prev.includes(sessionName.trim()) ? prev : [...prev, sessionName.trim()]));
                                        }
                                    }}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" && sessionName.trim()) {
                                            setAvailableSessions((prev) => (prev.includes(sessionName.trim()) ? prev : [...prev, sessionName.trim()]));
                                        }
                                    }}
                                    placeholder="session_name"
                                    className="bg-transparent border-b border-gray-700 text-xs font-mono text-purple-200 focus:outline-none focus:border-purple-400 w-32"
                                />
                                <button
                                    type="button"
                                    onClick={handleCreateNewSession}
                                    className="bg-purple-900/60 hover:bg-purple-800 border border-purple-700 text-purple-200 text-xs font-semibold px-2 py-1 rounded transition"
                                >
                                    + New Session
                                </button>

                            </div>

                        </div>
                    </header>

                    {/* Navigation Bar based on Studio Mode */}
                    {studioMode === "acts" ? (
                        <div className="bg-gray-900/60 border-b border-gray-800/80 px-6 py-2.5 flex items-center justify-center space-x-2 sm:space-x-6">
                            <button
                                onClick={() => setActiveAct(1)}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeAct === 1
                                        ? "bg-purple-600/30 text-purple-300 border border-purple-500 shadow-lg shadow-purple-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span className="text-base">🎭</span>
                                <span>Act 1: Global Production Context (Applies to All Shots)</span>
                                {activeAct > 1 && <span className="text-[10px] bg-green-950 text-green-400 px-1.5 rounded border border-green-800">✓</span>}
                            </button>
                            <span className="text-gray-700 font-bold">➔</span>
                            <button
                                onClick={() => setActiveAct(2)}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeAct === 2
                                        ? "bg-pink-600/30 text-pink-300 border border-pink-500 shadow-lg shadow-pink-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span className="text-base">🎛️</span>
                                <span>Act 2: Storyboard &amp; Shot Director (10-Second Video Clips)</span>
                                {activeAct > 2 && <span className="text-[10px] bg-green-950 text-green-400 px-1.5 rounded border border-green-800">✓</span>}
                            </button>
                            <span className="text-gray-700 font-bold">➔</span>
                            <button
                                onClick={() => setActiveAct(3)}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeAct === 3
                                        ? "bg-amber-600/30 text-amber-300 border border-amber-500 shadow-lg shadow-amber-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span className="text-base">🎬</span>
                                <span>Act 3: The Screening Room &amp; Branching</span>
                            </button>
                        </div>
                    ) : (
                        <div className="bg-gray-900/80 border-b border-gray-800 px-6 py-2.5 flex items-center justify-center space-x-2 sm:space-x-4">
                            <button
                                onClick={() => setActiveStage(1)}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeStage === 1
                                        ? "bg-amber-500/20 text-amber-300 border border-amber-500 shadow-md shadow-amber-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span>💡 Stage 1: Vision &amp; Style</span>
                                {activeStage > 1 && <span className="text-[10px] bg-green-950 text-green-400 px-1.5 rounded border border-green-800">✓</span>}
                            </button>
                            <span className="text-gray-700 font-bold">➔</span>
                            <button
                                onClick={() => setActiveStage(2)}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeStage === 2
                                        ? "bg-purple-500/20 text-purple-300 border border-purple-500 shadow-md shadow-purple-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span>📋 Stage 2: Storyboard Grid</span>
                                {activeStage > 2 && <span className="text-[10px] bg-green-950 text-green-400 px-1.5 rounded border border-green-800">✓</span>}
                            </button>
                            <span className="text-gray-700 font-bold">➔</span>
                            <button
                                onClick={() => setActiveStage(3)}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeStage === 3
                                        ? "bg-pink-500/20 text-pink-300 border border-pink-500 shadow-md shadow-pink-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span>📽️ Stage 3: The Dailies</span>
                                {activeStage > 3 && <span className="text-[10px] bg-green-950 text-green-400 px-1.5 rounded border border-green-800">✓</span>}
                            </button>
                            <span className="text-gray-700 font-bold">➔</span>
                            <button
                                onClick={handleProceedToStage4}
                                className={`flex items-center space-x-2 px-4 py-1.5 rounded-xl text-xs font-bold transition ${
                                    activeStage === 4
                                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500 shadow-md shadow-emerald-900/20"
                                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                                }`}
                            >
                                <span>🏆 Stage 4: The Final Cut</span>
                            </button>
                        </div>
                    )}

                    {/* Main Stage Studio Container */}
                    <main className="flex-1 max-w-7xl w-full mx-auto p-6 overflow-y-auto custom-scrollbar space-y-6">

                        {/* Global Prominent Error Alert Banner */}
                        {lastError && (
                            <div className="bg-red-950/60 border-2 border-red-500/80 rounded-2xl p-5 shadow-2xl text-red-200 space-y-3 animate-fade-in">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 font-bold text-red-300 text-xs uppercase tracking-wider">
                                        <span className="text-xl">⚠️</span>
                                        <span className="text-sm font-extrabold text-red-200">Gemini Omni Flash Alert / Generation Notice</span>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setLastError(null)}
                                        className="text-red-300 hover:text-white text-xs font-extrabold px-3 py-1.5 rounded-lg border border-red-700 bg-red-900/80 hover:bg-red-800 transition"
                                    >
                                        ✕ Dismiss Notice
                                    </button>
                                </div>
                                <div className="bg-black/70 border border-red-800 rounded-xl p-4 text-xs font-mono text-red-200 break-words whitespace-pre-wrap leading-relaxed shadow-inner">
                                    <span className="text-red-400 font-bold block mb-1.5">Error Message:</span>
                                    {lastError}
                                </div>
                                {String(lastError).includes("real people") && (
                                    <div className="bg-amber-950/50 border border-amber-500/50 rounded-xl p-3 text-amber-300 text-xs flex items-start gap-2">
                                        <span className="text-base">💡</span>
                                        <div>
                                            <span className="font-bold block">Model Safety Tip (Real Names / Likenesses):</span>
                                            <span>Gemini Omni Flash blocks real celebrity/artist names. Replace real names with fictional parody descriptions (e.g., use <em>"Gaunt Wizard in Black Puffer Jacket"</em> instead of real celebrity names).</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎭 ACT 1: THE CONCEPT & CAST MANAGER                      */}
                        {/* ========================================================= */}
                        {studioMode === "acts" && activeAct === 1 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-purple-950/40 to-pink-950/40 border border-purple-800/50 rounded-2xl p-5">
                                    <h2 className="text-base font-bold text-purple-200 flex items-center gap-2">
                                        <span>🎭</span>
                                        <span>Act 1: Global Production Context (Applies to All Shots)</span>
                                    </h2>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Set character likeness, outfits, voice styles, and global parody environment once. Shared across all 10s video clips.
                                    </p>
                                </div>

                                {/* 1. Visual Concept / Parody Prompt & Example Chips */}
                                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs font-bold text-pink-400 uppercase tracking-wider flex items-center gap-2">
                                            <span>💡</span>
                                            <span>Visual Concept / Parody Prompt</span>
                                        </label>
                                        <span className="text-[11px] bg-purple-950 text-purple-300 px-2 py-0.5 rounded border border-purple-800">
                                            Open-Ended NLP Input
                                        </span>
                                    </div>
                                    <textarea
                                        rows={3}
                                        value={concept}
                                        onChange={(e) => setConcept(e.target.value)}
                                        placeholder="e.g. Gordon Ramsay vs Julia Child in a cyberpunk iron chef battle..."
                                        className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-pink-500 font-mono"
                                    />

                                    {/* Example Chips */}
                                    <div>
                                        <span className="text-[11px] text-gray-400 font-medium block mb-2">⚡ Example Concept Chips (Click to load &amp; deconstruct):</span>
                                        <div className="flex flex-wrap gap-2">
                                            {exampleConcepts.map((ex, i) => (
                                                <button
                                                    key={i}
                                                    type="button"
                                                    onClick={() => {
                                                        setConcept(ex);
                                                        handleDeconstructConcept(ex);
                                                    }}
                                                    className="bg-gray-950 border border-gray-800 hover:border-pink-500/70 text-gray-300 hover:text-pink-200 px-3 py-1.5 rounded-lg text-xs transition text-left"
                                                >
                                                    {ex}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="flex justify-end pt-1">
                                        <button
                                            type="button"
                                            disabled={deconstructLoading || !concept.trim()}
                                            onClick={() => handleDeconstructConcept()}
                                            className="bg-gradient-to-r from-pink-600 via-purple-600 to-amber-500 hover:opacity-90 text-white font-bold text-xs py-2.5 px-6 rounded-xl shadow-lg flex items-center gap-2 transition disabled:opacity-50"
                                        >
                                            <span>✨</span>
                                            <span>{deconstructLoading ? "Deconstructing Concept..." : "✨ Deconstruct Concept"}</span>
                                        </button>
                                    </div>
                                </div>

                                {/* 2. Dynamic Character Roles Manager */}
                                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                            <h3 className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-2">
                                                <span>👥</span>
                                                <span>Character Roles (Gemini Omni Image Roles Reference)</span>
                                            </h3>
                                            <p className="text-[11px] text-gray-400 mt-0.5">
                                                Define character roles with visual descriptions and attached reference image URLs to maintain likeness.
                                            </p>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <button
                                                type="button"
                                                onClick={handleSaveSessionRoster}
                                                className="bg-gray-950 hover:bg-gray-800 text-purple-300 hover:text-purple-200 border border-purple-900/60 font-bold text-xs py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
                                                title="Save current cast roster to session"
                                            >
                                                <span>💾</span>
                                                <span>Save Cast Roster</span>
                                            </button>
                                            <button
                                                type="button"
                                                onClick={handleLoadSessionRoster}
                                                className="bg-gray-950 hover:bg-gray-800 text-gray-300 hover:text-white border border-gray-700 font-bold text-xs py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
                                                title="Restore saved cast roster for this session"
                                            >
                                                <span>📂</span>
                                                <span>Restore Cast</span>
                                            </button>
                                            <button
                                                type="button"
                                                onClick={addCharacterRole}
                                                className="bg-purple-900/60 hover:bg-purple-800 text-purple-200 border border-purple-700 font-bold text-xs py-1.5 px-3 rounded-lg shadow flex items-center gap-1"
                                            >
                                                <span>+ Add Character Role</span>
                                            </button>
                                        </div>
                                    </div>

                                    {/* 🏛️ Character Vault & Saved Library */}
                                    <div className="bg-gray-950/80 border border-purple-900/50 rounded-xl p-3.5 space-y-2.5">
                                        <div className="flex items-center justify-between">
                                            <label className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-2">
                                                <span>🏛️</span>
                                                <span>Character Vault &amp; Saved Library</span>
                                            </label>
                                            <span className="text-[10px] text-gray-400 font-mono">
                                                {savedVaultCharacters.length} Preset(s) Available
                                            </span>
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {savedVaultCharacters.map((c, vIdx) => {
                                                const chipText = c.name || c.role_id || `Preset ${vIdx + 1}`;
                                                return (
                                                    <button
                                                        key={vIdx}
                                                        type="button"
                                                        onClick={() => handleLoadVaultCharacter(c)}
                                                        className="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 hover:border-purple-500 text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shadow-sm"
                                                        title={`Click to load ${c.name || c.role_id} into roster`}
                                                    >
                                                        {c.reference_url && (
                                                            <img
                                                                src={getDisplayableRefUrl(c.reference_url)}
                                                                alt={c.name || "Preset"}
                                                                className="w-4 h-4 rounded-full object-cover border border-purple-400/50"
                                                            />
                                                        )}
                                                        <span>+</span>
                                                        <span>{chipText}</span>
                                                    </button>
                                                );
                                            })}
                                            {savedVaultCharacters.length === 0 && (
                                                <span className="text-xs text-gray-500 italic py-1">
                                                    No characters in vault yet. Save character roles below to build your library.
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {characters.map((char, idx) => (
                                            <div key={idx} className="bg-gray-950 border border-gray-800/90 rounded-xl p-4 space-y-3 relative group">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs font-bold font-mono bg-pink-950 text-pink-300 px-2.5 py-1 rounded border border-pink-800/80">
                                                        {char.role_id}
                                                    </span>
                                                    <div className="flex items-center space-x-2">
                                                        <button
                                                            type="button"
                                                            onClick={() => handleSaveCharacterToVault(char)}
                                                            className="bg-gray-900 hover:bg-purple-950 text-purple-300 hover:text-purple-200 border border-purple-900/60 hover:border-purple-700 text-xs px-2.5 py-1 rounded-lg transition flex items-center gap-1.5 shadow-sm font-medium"
                                                            title="Save character to vault library"
                                                        >
                                                            <span>💾</span>
                                                            <span>Save to Vault</span>
                                                        </button>
                                                        {characters.length > 1 && (
                                                            <button
                                                                type="button"
                                                                onClick={() => removeCharacter(idx)}
                                                                className="text-gray-500 hover:text-red-400 text-xs px-2 py-1 transition"
                                                                title="Remove Character Role"
                                                            >
                                                                🗑️ Remove
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                                <div>
                                                    <label className="block text-[11px] text-gray-400 mb-1">Character Name</label>
                                                    <input
                                                        type="text"
                                                        value={char.name}
                                                        onChange={(e) => updateCharacter(idx, "name", e.target.value)}
                                                        placeholder="e.g. Harry"
                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-medium"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="block text-[11px] text-gray-400 mb-1">Visual Likeness &amp; Description</label>
                                                    <textarea
                                                        rows={2}
                                                        value={char.description}
                                                        onChange={(e) => updateCharacter(idx, "description", e.target.value)}
                                                        placeholder="Visual description for prompt compiler..."
                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                    />
                                                </div>

                                                {/* Character Style Signifiers (Aesthetic Tags) Chip Manager */}
                                                <div>
                                                    <label className="block text-[11px] font-bold text-pink-400 uppercase tracking-wider mb-1">
                                                        👔 Wardrobe &amp; Aesthetic Style Signifiers
                                                    </label>
                                                    <div className="flex flex-wrap gap-1.5 mb-2">
                                                        {(char.aesthetic_tags || []).map((tag, tIdx) => (
                                                            <span
                                                                key={tIdx}
                                                                className="bg-purple-950/70 border border-purple-800/80 text-purple-200 text-xs px-2.5 py-0.5 rounded-lg flex items-center gap-1.5"
                                                            >
                                                                <span>{tag}</span>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => removeCharAestheticTag(idx, tag)}
                                                                    className="text-purple-400 hover:text-white font-bold text-xs"
                                                                    title="Remove Style Tag"
                                                                >
                                                                    ×
                                                                </button>
                                                            </span>
                                                        ))}
                                                        {(!char.aesthetic_tags || char.aesthetic_tags.length === 0) && (
                                                            <span className="text-[10px] text-gray-500 italic">No specific character style tags</span>
                                                        )}
                                                    </div>
                                                    <div className="flex gap-1.5">
                                                        <input
                                                            type="text"
                                                            value={charTagInputs[idx] || ""}
                                                            onChange={(e) => setCharTagInputs({ ...charTagInputs, [idx]: e.target.value })}
                                                            onKeyDown={(e) => {
                                                                if (e.key === "Enter") {
                                                                    e.preventDefault();
                                                                    addCharAestheticTag(idx);
                                                                }
                                                            }}
                                                            placeholder="e.g. Red Gucci Tracksuit, Cartier Glasses..."
                                                            className="flex-1 bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                        />
                                                        <button
                                                            type="button"
                                                            onClick={() => addCharAestheticTag(idx)}
                                                            className="bg-purple-900/60 hover:bg-purple-800 text-purple-200 border border-purple-700 font-bold text-xs px-3 py-1.5 rounded-lg shadow transition"
                                                        >
                                                            + Add Style
                                                        </button>
                                                    </div>
                                                </div>

                                                <div>
                                                    <label className="block text-[11px] text-gray-400 mb-1">
                                                        🎙️ Voice Profile / Vocal Style
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={char.voice_profile || ""}
                                                        onChange={(e) => updateCharacter(idx, "voice_profile", e.target.value)}
                                                        placeholder="e.g. Deep raspy baritone voice with fast rap cadence..."
                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                    />
                                                </div>


                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                                                    <div>
                                                        <label className="block text-[11px] font-bold text-purple-300 uppercase tracking-wider mb-1">
                                                            🖼️ Gemini Image Role
                                                        </label>
                                                        <select
                                                            value={char.image_role || "Character Reference"}
                                                            onChange={(e) => updateCharacter(idx, "image_role", e.target.value)}
                                                            className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-purple-200 focus:outline-none focus:border-purple-500 font-mono"
                                                        >
                                                            <option value="Character Reference">Character Reference</option>
                                                            <option value="Product Reference">Product Reference</option>
                                                            <option value="Starting Frame">Starting Frame</option>
                                                            <option value="Style Reference">Style Reference</option>
                                                        </select>
                                                    </div>
                                                    <div className="flex items-end pb-1">
                                                        <label className="flex items-center space-x-2 cursor-pointer text-[11px] text-gray-300 bg-gray-900 border border-gray-800 hover:border-amber-500/50 p-2 rounded-lg w-full transition">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!char.is_offscreen_narrator}
                                                                onChange={(e) => updateCharacter(idx, "is_offscreen_narrator", e.target.checked)}
                                                                className="rounded border-gray-700 text-amber-500 focus:ring-amber-500 bg-gray-950 w-4 h-4"
                                                            />
                                                            <span className="font-bold text-amber-300">🎙️ Off-Screen Narrator</span>
                                                        </label>
                                                    </div>
                                                </div>

                                                <div>
                                                    <label className="block text-[11px] text-gray-400 mb-1">
                                                        🖼️ Reference Image URL <span className="text-purple-400 text-[10px]">(Gemini Omni Image Role)</span>
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={char.reference_url || ""}
                                                        onChange={(e) => updateCharacter(idx, "reference_url", e.target.value)}
                                                        placeholder="https://example.com/character_reference.jpg"
                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                    />
                                                    {char.reference_url && (
                                                        <div className="flex items-center space-x-2 bg-purple-950/40 border border-purple-800/60 rounded-lg p-2 mt-2">
                                                            <img
                                                                src={getDisplayableRefUrl(char.reference_url)}
                                                                alt={char.name || char.role_id}
                                                                className="w-10 h-10 object-cover rounded-lg border border-purple-500/50"
                                                            />
                                                            <div className="overflow-hidden">
                                                                <span className="text-[10px] font-bold text-purple-300 uppercase tracking-wider block">Linked Image Role: {char.image_role || "Character Reference"}</span>
                                                                <span className="text-[10px] text-gray-400 font-mono truncate block">{char.reference_url}</span>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* 3. Editable Meta-Prompt Tags, Environment & Audio Beat */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Aesthetic Tags & Audio Beat */}
                                    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                        <div className="pb-3 border-b border-gray-800">
                                            <label className="text-xs font-bold text-amber-400 uppercase tracking-wider block mb-2 flex items-center gap-1.5">
                                                <span>🎨</span>
                                                <span>Cartoon &amp; Art Style Presets:</span>
                                            </label>
                                            <div className="flex flex-wrap gap-1.5">
                                                {[
                                                    "🎨 90s Cel-Shaded Anime",
                                                    "🍿 3D Stylized Animation (Arcane)",
                                                    "💥 Comic Book Graphic Novel",
                                                    "🖌️ 2D Vector Toon Parody",
                                                    "👾 16-Bit Pixel Art Anime",
                                                    "🏰 1930s Rubber Hose Toon",
                                                    "🐉 Claymation Stop-Motion",
                                                    "✨ Cyberpunk Neon Anime",
                                                    "🎬 Cinematic Trap Parody",
                                                    "📹 Gritty 90s Rap Video"
                                                ].map((tone) => (
                                                    <button
                                                        key={tone}
                                                        type="button"
                                                        onClick={() => {
                                                            handleGlobalStyleToneChange(tone, true);
                                                            if (!aestheticTags.includes(tone)) setAestheticTags([tone, ...aestheticTags]);
                                                            setCameraLightingTag(`${tone}, high-contrast lighting`);
                                                        }}
                                                        className={`px-2.5 py-1 rounded-full text-xs font-semibold transition ${
                                                            stageStyleTone === tone
                                                                ? "bg-amber-500 text-black font-extrabold shadow-md shadow-amber-900/50"
                                                                : "bg-gray-950 text-gray-300 hover:bg-gray-800 border border-gray-800"
                                                        }`}
                                                    >
                                                        {stageStyleTone === tone && "✓ "}
                                                        {tone}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                        <div>
                                            <h3 className="text-xs font-bold text-pink-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                                                <span>🎨</span>
                                                <span>Aesthetic Tags &amp; Style Signifiers</span>
                                            </h3>
                                            <div className="flex flex-wrap gap-2 mb-3">
                                                {aestheticTags.map((tag, idx) => (
                                                    <span
                                                        key={idx}
                                                        className="bg-pink-950/60 border border-pink-800/80 text-pink-200 text-xs px-2.5 py-1 rounded-lg flex items-center gap-1.5"
                                                    >
                                                        <span>{tag}</span>
                                                        <button
                                                            type="button"
                                                            onClick={() => removeAestheticTag(tag)}
                                                            className="text-pink-400 hover:text-white font-bold text-xs"
                                                        >
                                                            ×
                                                        </button>
                                                    </span>
                                                ))}
                                            </div>
                                            <form onSubmit={handleAddAestheticTag} className="flex gap-2">
                                                <input
                                                    type="text"
                                                    value={newTagInput}
                                                    onChange={(e) => setNewTagInput(e.target.value)}
                                                    placeholder="Add custom aesthetic tag..."
                                                    className="flex-1 bg-gray-950 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-pink-500"
                                                />
                                                <button
                                                    type="submit"
                                                    className="bg-gray-800 hover:bg-gray-700 text-xs text-pink-300 font-bold px-3 py-2 rounded-lg border border-gray-700"
                                                >
                                                    + Add Tag
                                                </button>
                                            </form>
                                        </div>

                                        <div className="pt-3 border-t border-gray-800">
                                            <label className="block text-xs font-bold text-purple-400 uppercase tracking-wider mb-1">
                                                🎵 Audio Beat &amp; Music Genre
                                            </label>
                                            <input
                                                type="text"
                                                value={audioBeat}
                                                onChange={(e) => setAudioBeat(e.target.value)}
                                                placeholder="e.g. 140 BPM Heavy 808 Trap"
                                                className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500"
                                            />
                                        </div>

                                        <div className="pt-3 border-t border-gray-800">
                                            <label className="block text-xs font-bold text-pink-400 uppercase tracking-wider mb-1">
                                                🎙️ Vocal Delivery / Voiceover Style
                                            </label>
                                            <input
                                                type="text"
                                                value={vocalDelivery}
                                                onChange={(e) => setVocalDelivery(e.target.value)}
                                                placeholder="e.g. High-energy back-and-forth rap battle delivery with synchronized lip-sync"
                                                className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-pink-500"
                                            />
                                        </div>
                                    </div>

                                    {/* Environment & Camera/Lighting */}
                                    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                        <div>
                                            <label className="block text-xs font-bold text-amber-400 uppercase tracking-wider mb-1">
                                                🌍 Environment &amp; Background Setting
                                            </label>
                                            <textarea
                                                rows={2}
                                                value={environmentTag}
                                                onChange={(e) => setEnvironmentTag(e.target.value)}
                                                placeholder="e.g. Gothic Hogwarts courtyard lit by neon stage lights and smoky haze"
                                                className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-amber-500"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-xs font-bold text-blue-400 uppercase tracking-wider mb-1">
                                                🎥 Camera &amp; Lighting Styling
                                            </label>
                                            <textarea
                                                rows={2}
                                                value={cameraLightingTag}
                                                onChange={(e) => setCameraLightingTag(e.target.value)}
                                                placeholder="e.g. Low-angle 90s fisheye tracking shot with high-contrast neon rim lights"
                                                className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
                                            />
                                        </div>
                                    </div>
                                </div>

                                {/* Bottom Navigation for Act 1 */}
                                <div className="flex justify-end pt-4">
                                    <button
                                        type="button"
                                        onClick={() => setActiveAct(2)}
                                        className="bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 hover:opacity-90 text-white font-bold text-sm py-3 px-8 rounded-xl shadow-xl flex items-center gap-2 transition transform hover:scale-105"
                                    >
                                        <span>Proceed to Act 2: Storyboard &amp; Shot Director (10-Second Video Clips)</span>
                                        <span>➔</span>
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎛️ ACT 2: STORYBOARD & SHOT DIRECTOR (10-SECOND VIDEO CLIPS) */}
                        {/* ========================================================= */}
                        {studioMode === "acts" && activeAct === 2 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-pink-950/40 to-amber-950/40 border border-pink-800/50 rounded-2xl p-5">
                                    <h2 className="text-base font-bold text-pink-200 flex items-center gap-2">
                                        <span>🎛️</span>
                                        <span>Act 2: Storyboard &amp; Shot Director (10-Second Video Clips)</span>
                                    </h2>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Direct individual 10-second video shots using Guided Mode or Screenplay Scripting.
                                    </p>
                                    <details className="mt-2 bg-gray-900/80 border border-gray-800 rounded-xl p-3 text-xs text-gray-300">
                                        <summary className="font-bold text-purple-400 cursor-pointer flex items-center gap-1.5 select-none">
                                            <span>💡</span>
                                            <span>Guided Mode vs. Screenplay Mode Guide (Click to expand)</span>
                                        </summary>
                                        <div className="mt-2 pt-2 border-t border-gray-800 grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300">
                                            <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 space-y-1">
                                                <span className="font-bold text-purple-300">🎛️ Guided Mode (Default)</span>
                                                <p className="text-[11px] text-gray-400">
                                                    Quick 10-second shot setup. Use separate fields for visual action and spoken dialogue. Compiles into clean single-line storyboard directives.
                                                </p>
                                            </div>
                                            <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 space-y-1">
                                                <span className="font-bold text-pink-300">📜 Screenplay Mode</span>
                                                <p className="text-[11px] text-gray-400">
                                                    Write multi-line script directives: <code className="text-pink-400">Character: (Action description. Audio cue.) "Dialogue"</code>. Parses visual actions, audio FX stems, and dialogue quotes automatically.
                                                </p>
                                            </div>
                                        </div>
                                    </details>
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                    {/* Left 7 Cols: Multi-Scene Storyboard Editor */}
                                    <div className="lg:col-span-7 space-y-4">
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                                                <h3 className="text-xs font-bold text-pink-400 uppercase tracking-wider flex items-center gap-2">
                                                    <span>🎬</span>
                                                    <span>Multi-Scene Storyboard Sequence (~1-Min Cut)</span>
                                                </h3>
                                                <button
                                                    type="button"
                                                    onClick={addScene}
                                                    className="bg-pink-900/60 hover:bg-pink-800 text-pink-200 border border-pink-700 font-bold text-xs py-1.5 px-3 rounded-lg shadow flex items-center gap-1"
                                                >
                                                    <span>+ Add Scene</span>
                                                </button>
                                            </div>

                                            <div className="space-y-4">
                                                {scenes.map((scene, idx) => (
                                                    <div key={idx} className="bg-gray-950 border border-gray-800 rounded-xl p-4 space-y-3">
                                                        <div className="flex items-center justify-between">
                                                            <span className="text-xs font-bold text-amber-300 font-mono bg-amber-950/80 px-2.5 py-0.5 rounded border border-amber-800">
                                                                Scene #{scene.scene_number}
                                                            </span>
                                                            <div className="flex items-center space-x-2">
                                                                <div className="bg-gray-900 border border-gray-800 rounded-lg p-0.5 flex items-center">
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => updateScene(idx, "mode", "guided")}
                                                                        className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition ${
                                                                            (scene.mode || "guided") === "guided"
                                                                                ? "bg-purple-600 text-white shadow"
                                                                                : "text-gray-400 hover:text-gray-200"
                                                                        }`}
                                                                    >
                                                                        Guided Mode
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => updateScene(idx, "mode", "screenplay")}
                                                                        className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition flex items-center gap-1 ${
                                                                            scene.mode === "screenplay"
                                                                                ? "bg-purple-600 text-white shadow"
                                                                                : "text-gray-400 hover:text-gray-200"
                                                                        }`}
                                                                    >
                                                                        <span>📜</span>
                                                                        <span>Screenplay Mode</span>
                                                                    </button>
                                                                </div>
                                                                {scenes.length > 1 && (
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => removeScene(idx)}
                                                                        className="text-gray-500 hover:text-red-400 text-xs px-2 py-1 transition"
                                                                        title="Remove Scene"
                                                                    >
                                                                        🗑️ Remove Scene
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </div>

                                                        {/* Active Roles Selector */}
                                                        <div>
                                                            <label className="block text-[11px] font-bold text-gray-400 mb-1.5">
                                                                Active Character Roles in this Scene:
                                                            </label>
                                                            <div className="flex flex-wrap gap-2">
                                                                {characters.map((char, cIdx) => {
                                                                    const isSelected = (scene.active_roles || []).includes(char.role_id);
                                                                    return (
                                                                        <button
                                                                            key={cIdx}
                                                                            type="button"
                                                                            onClick={() => toggleSceneRole(idx, char.role_id)}
                                                                            className={`px-3 py-1 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
                                                                                isSelected
                                                                                    ? "bg-purple-600 text-white shadow-md shadow-purple-900/50"
                                                                                    : "bg-gray-900 text-gray-400 border border-gray-800 hover:border-gray-700"
                                                                            }`}
                                                                        >
                                                                            <span>{isSelected ? "✓" : "○"}</span>
                                                                            <span>{char.role_id} ({char.name || "Char"})</span>
                                                                        </button>
                                                                    );
                                                                })}
                                                            </div>
                                                        </div>

                                                        {(scene.mode || "guided") === "guided" ? (
                                                            <>
                                                                {/* Action Description */}
                                                                <div>
                                                                    <label className="block text-[11px] text-gray-400 mb-1">
                                                                        Action Description
                                                                    </label>
                                                                    <textarea
                                                                        rows={2}
                                                                        value={scene.action || ""}
                                                                        onChange={(e) => updateScene(idx, "action", e.target.value)}
                                                                        placeholder="e.g. Arriving at foggy courtyard rapping into microphone wand..."
                                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-pink-500 font-mono"
                                                                    />
                                                                </div>

                                                                {/* Character Dialogue / Voiceover Line */}
                                                                <div>
                                                                    <label className="block text-[11px] text-gray-400 mb-1">
                                                                        🎙️ Character Dialogue / Spoken Voiceover Line
                                                                    </label>
                                                                    <input
                                                                        type="text"
                                                                        value={scene.dialogue || ""}
                                                                        onChange={(e) => updateScene(idx, "dialogue", e.target.value)}
                                                                        placeholder='e.g. Harry: "I been cooking potions since first year. Burrr!"'
                                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                                    />
                                                                </div>
                                                            </>
                                                        ) : (
                                                            <div>
                                                                <div className="flex items-center justify-between mb-1">
                                                                    <label className="block text-[11px] text-gray-400">
                                                                        📜 Screenplay Script
                                                                    </label>
                                                                    <span className="text-[10px] text-purple-400 font-mono">
                                                                        Supports Character: (Action) "Dialogue" &amp; [0-5s] Timecoded Script
                                                                    </span>
                                                                </div>
                                                                <textarea
                                                                    rows={3}
                                                                    value={scene.screenplay_script || ""}
                                                                    onChange={(e) => updateScene(idx, "screenplay_script", e.target.value)}
                                                                    placeholder='e.g. Harry: (Pulls out wand. Audio: Whoosh sfx.) "Expelliarmus!" or [0-5s] Action: ... Dialogue: ...'
                                                                    className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono"
                                                                />
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Right 5 Cols: Live Compiled Prompt Preview & Generate */}
                                    <div className="lg:col-span-5 space-y-4">
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col h-full justify-between">
                                            <div>
                                                <div className="flex items-center justify-between mb-3">
                                                    <h3 className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-2">
                                                        <span>📋</span>
                                                        <span>Anchor &amp; Inject Storyboard Prompt Preview</span>
                                                    </h3>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            const preview = compileStoryboardPreview();
                                                            if (navigator.clipboard) navigator.clipboard.writeText(preview);
                                                            setCopied(true);
                                                            setTimeout(() => setCopied(false), 2000);
                                                        }}
                                                        className="text-[10px] bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded hover:bg-purple-900"
                                                    >
                                                        {copied ? "✓ Copied!" : "📋 Copy Prompt"}
                                                    </button>
                                                </div>

                                                <pre className="bg-gray-950 border border-gray-800 rounded-xl p-3 text-[11px] text-gray-300 font-mono whitespace-pre-wrap max-h-[420px] overflow-y-auto custom-scrollbar leading-relaxed">
                                                    {compileStoryboardPreview()}
                                                </pre>
                                            </div>

                                            <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
                                                <button
                                                    type="button"
                                                    onClick={() => setActiveAct(1)}
                                                    className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-gray-800 text-xs text-gray-400 hover:text-white"
                                                >
                                                    ⮌ Back to Act 1
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={loading}
                                                    onClick={handleGenerate}
                                                    className="w-full sm:flex-1 bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 hover:opacity-90 text-white font-bold text-xs py-3 px-6 rounded-xl shadow-xl flex items-center justify-center gap-2 transition disabled:opacity-50"
                                                >
                                                    <span>🎬</span>
                                                    <span>{loading ? "Rendering Parody Cut..." : "🎬 Generate Parody Cut ➔"}</span>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎬 DEDICATED 4-STAGE STORYBOARD JOURNEY WORKFLOW          */}
                        {/* ========================================================= */}
                        {studioMode === "stages" && (
                            <div className="space-y-6">
                                {/* STAGE 1: VISION & STYLE SETUP */}
                                {activeStage === 1 && (
                                    <div className="space-y-6">
                                        <div className="bg-gradient-to-r from-amber-950/40 via-orange-950/40 to-purple-950/40 border border-amber-800/50 rounded-2xl p-5 shadow-xl">
                                            <div className="flex flex-wrap items-center justify-between gap-4">
                                                <div>
                                                    <h2 className="text-base font-bold text-amber-200 flex items-center gap-2">
                                                        <span>💡</span>
                                                        <span>Stage 1: 60s Vision &amp; Style Directing</span>
                                                    </h2>
                                                    <p className="text-xs text-gray-400 mt-1">
                                                        Define your overall 30–60s video concept, select style &amp; tone presets, and upload reference image and audio assets.
                                                    </p>
                                                </div>
                                                <div className="flex items-center bg-gray-950 border border-gray-800 rounded-xl p-1 shadow-inner">
                                                    <button
                                                        type="button"
                                                        onClick={() => setStoryboardPath("path1")}
                                                        className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                                                            storyboardPath === "path1"
                                                                ? "bg-gradient-to-r from-amber-500 to-orange-500 text-black font-extrabold shadow"
                                                                : "text-gray-400 hover:text-white"
                                                        }`}
                                                    >
                                                        <span>📜</span>
                                                        <span>Path 1: Single 30–60s Master Script</span>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setStoryboardPath("path2");
                                                            setActiveStage(2);
                                                        }}
                                                        className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                                                            storyboardPath === "path2"
                                                                ? "bg-purple-600 text-white font-extrabold shadow"
                                                                : "text-gray-400 hover:text-white"
                                                        }`}
                                                    >
                                                        <span>📋</span>
                                                        <span>Path 2: Per-Shot Workstation</span>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>

                                        {storyboardPath === "path1" && (
                                            <div className="bg-amber-950/60 border border-amber-500/50 rounded-xl p-3.5 flex items-start gap-3 text-amber-300 text-xs">
                                                <span className="text-xl">✂️</span>
                                                <div>
                                                    <span className="font-bold block text-amber-200">Path 1: Master Script &amp; Auto-Splitter Guidance</span>
                                                    <span className="text-amber-300/90 text-[11px]">
                                                        Write or paste a single continuous script with timecodes ([0-10s], [10-20s], [20-30s]). OmniMash auto-splits long scripts &gt; 10s into sequential 10-second shot cards while preserving subject, outfit, and character continuity.
                                                    </span>
                                                </div>
                                            </div>
                                        )}

                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                            <div className="flex items-center justify-between">
                                                <label className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                                                    Visual Concept / Parody Idea (30–60s)
                                                </label>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-gray-400">Target Duration:</span>
                                                    <select
                                                        value={stageTargetDuration}
                                                        onChange={(e) => setStageTargetDuration(parseFloat(e.target.value))}
                                                        className="bg-gray-950 border border-gray-700 rounded text-xs font-mono px-2 py-1 text-amber-300"
                                                    >
                                                        <option value={30.0}>30 Seconds (3 Shots)</option>
                                                        <option value={45.0}>45 Seconds (5 Shots)</option>
                                                        <option value={60.0}>60 Seconds (6 Shots)</option>
                                                    </select>
                                                </div>
                                            </div>
                                            <textarea
                                                rows={3}
                                                value={concept}
                                                onChange={(e) => setConcept(e.target.value)}
                                                placeholder="Describe your 60s parody video concept in detail..."
                                                className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 font-mono"
                                            />

                                            <div>
                                                <div className="flex items-center justify-between mb-1">
                                                    <label className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                                                        <span>📜</span>
                                                        <span>Timecoded Screenplay &amp; Director's Notes Studio</span>
                                                    </label>
                                                    <span className="text-[10px] text-gray-400 font-mono">Include [DIRECTOR'S NOTES], [0-3s] Action:, Audio:, Dialogue:</span>
                                                </div>
                                                <div className="flex flex-wrap gap-1.5 mb-2">
                                                    <span className="text-[11px] text-gray-400 self-center font-medium">Presets:</span>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            const preset = `[DIRECTOR'S NOTES]\n- Tone: High-Energy 90s Cel-Shaded Anime Rap Battle\n- Relational Dynamic: Intense rivalry between Dumble Dior & Snape Dawg; mutual respect masked by humorous disses.\n- Dumble Dior Profile: Regal, charismatic, confident flow.\n- Snape Dawg Profile: Deep subterranean trap flow with autotune.\n\n[0-3s] Action: Dumble Dior steps up to the mic under glowing neon lights. Audio: Heavy 808 trap beat with ambient crowd cheers. Dialogue: Dumble Dior: "Welcome to Dripwarts, turn the beat up!"\n\n[3-6s] Action: Snape Dawg drops a heavy 808 trap beat. Audio: Crisp snare trills and sub-bass drop. Dialogue: Snape Dawg: "Potions class is in session, no cap!"\n\n[6-10s] Action: Both perform synchronized rap battle climax amidst stage smoke and purple rim lights. Audio: Climax 808 beat drop. Dialogue: Both: "Trap or Die!"`;
                                                            setScreenplayScript(preset);
                                                        }}
                                                        className="bg-amber-950/60 border border-amber-800/80 hover:border-amber-500 text-amber-200 text-[11px] px-2.5 py-1 rounded-lg transition"
                                                    >
                                                        📜 Rap Battle (Director's Notes + Timecodes)
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            const preset = `[DIRECTOR'S NOTES]\n- Tone: Cinematic Cyberpunk Action\n- Relational Dynamic: Partner operatives navigating high-stakes heist.\n\n[0-5s] Action: Operative A hacks the security vault console under neon holographic interface. Audio: High-frequency data pulse and rhythmic synth bass. Dialogue: Operative A: "Systems breached, we have 30 seconds."\n\n[5-10s] Action: Operative B covers the perimeter with plasma pulse rifle. Audio: Rhythmic alarm klaxons and pulsing bass drop. Dialogue: Operative B: "Security drones inbound, move now!"`;
                                                            setScreenplayScript(preset);
                                                        }}
                                                        className="bg-purple-950/60 border border-purple-800/80 hover:border-purple-500 text-purple-200 text-[11px] px-2.5 py-1 rounded-lg transition"
                                                    >
                                                        🎬 Cyberpunk Heist (Action &amp; Dialogue)
                                                    </button>
                                                </div>
                                                <textarea
                                                    rows={6}
                                                    value={screenplayScript}
                                                    onChange={(e) => setScreenplayScript(e.target.value)}
                                                    placeholder={`[DIRECTOR'S NOTES]\n- Tone: High-energy 90s Cel-Shaded Anime Rap Battle\n- Relational Dynamic: Friendly rivalry between Dumble Dior and Snape Dawg\n\n# Supports both Character: (Action) "Dialogue" AND [0-3s] Timecoded Script:\n\nDumble Dior: (Steps up to the mic under glowing neon lights. Audio: Heavy 808 trap beat.) "Welcome to Dripwarts, turn the beat up!"\n\nSnape Dawg: (Drops a heavy 808 trap beat. Audio: Crisp snare trills and sub-bass drop.) "Potions class is in session, no cap!"\n\n[6-10s] Action: Both perform synchronized rap battle climax amidst stage smoke and purple rim lights. Audio: Climax 808 beat drop. Dialogue: Both: "Trap or Die!"`}
                                                    className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 font-mono"
                                                />
                                            </div>

                                            <div>
                                                <label className="text-xs font-bold text-gray-300 block mb-2">Style &amp; Tone Preset Pills:</label>
                                                <div className="flex flex-wrap gap-2">
                                                    {[
                                                        "🎨 90s Cel-Shaded Anime",
                                                        "🍿 3D Stylized Animation (Arcane)",
                                                        "💥 Comic Book Graphic Novel",
                                                        "🖌️ 2D Vector Toon Parody",
                                                        "👾 16-Bit Pixel Art Anime",
                                                        "🏰 1930s Rubber Hose Toon",
                                                        "🐉 Claymation Stop-Motion",
                                                        "✨ Cyberpunk Neon Anime",
                                                        "🎬 Cinematic Trap Parody",
                                                        "📹 Gritty 90s Rap Video"
                                                    ].map((tone) => (
                                                        <button
                                                            key={tone}
                                                            type="button"
                                                            onClick={() => handleGlobalStyleToneChange(tone, true)}
                                                            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
                                                                stageStyleTone === tone
                                                                    ? "bg-amber-500 text-black font-extrabold shadow-md shadow-amber-900/50"
                                                                    : "bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700"
                                                            }`}
                                                        >
                                                            {stageStyleTone === tone && "✓ "}
                                                            {tone}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-gray-800">
                                                <div>
                                                    <label className="block text-xs font-bold text-purple-300 uppercase tracking-wider mb-1">
                                                        🎵 Audio Beat &amp; Music Genre
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={audioBeat}
                                                        onChange={(e) => setAudioBeat(e.target.value)}
                                                        placeholder="e.g. 140 BPM Heavy 808 Trap"
                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500 mb-2"
                                                    />
                                                    <div className="flex items-center justify-between mb-1">
                                                        <label className="text-[11px] font-bold text-gray-400">Master Audio Stem / Track (MP3 File, URL, or GCS Path)</label>
                                                        <label className="text-[10px] font-bold bg-purple-950 hover:bg-purple-900 border border-purple-700 text-purple-300 px-2 py-0.5 rounded cursor-pointer transition">
                                                            📁 Upload Local MP3
                                                            <input
                                                                type="file"
                                                                accept="audio/*,.mp3,.wav,.m4a"
                                                                className="hidden"
                                                                onChange={async (e) => {
                                                                    const file = e.target.files && e.target.files[0];
                                                                    if (file) {
                                                                        const formData = new FormData();
                                                                        formData.append("file", file);
                                                                        try {
                                                                            const res = await fetch("/api/upload", { method: "POST", body: formData });
                                                                            const data = await res.json();
                                                                            if (data && data.url) {
                                                                                setStageRefAudio(data.url);
                                                                                setMasterAudioUrl(data.url);
                                                                            }
                                                                        } catch (err) {
                                                                            console.error("Audio upload error:", err);
                                                                        }
                                                                    }
                                                                }}
                                                            />
                                                        </label>
                                                    </div>
                                                    <input
                                                        type="text"
                                                        value={stageRefAudio}
                                                        onChange={(e) => {
                                                            setStageRefAudio(e.target.value);
                                                            setMasterAudioUrl(e.target.value);
                                                        }}
                                                        placeholder="https://example.com/beat.mp3 or gs://... or upload local file above"
                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono placeholder-gray-600 focus:outline-none focus:border-purple-500"
                                                    />
                                                </div>

                                                <div>
                                                    <label className="block text-xs font-bold text-pink-300 uppercase tracking-wider mb-1">
                                                        🎙️ Vocal Delivery / Voiceover Style
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={vocalDelivery}
                                                        onChange={(e) => setVocalDelivery(e.target.value)}
                                                        placeholder="e.g. High-energy rap battle flow with autotune..."
                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-pink-500 mb-2"
                                                    />
                                                    <label className="text-[11px] font-bold text-gray-400 block mb-1">Primary Character Reference Image (URL or GCS Path)</label>
                                                    <input
                                                        type="text"
                                                        value={stageRefImage}
                                                        onChange={(e) => setStageRefImage(e.target.value)}
                                                        placeholder="https://example.com/character.jpg or gs://..."
                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono placeholder-gray-600 focus:outline-none focus:border-pink-500"
                                                    />
                                                </div>
                                            </div>

                                            {/* Character Roles & Character Vault (Gemini Omni Image Roles) */}
                                            <div className="pt-3 border-t border-gray-800 space-y-3">
                                                <div className="flex items-center justify-between">
                                                    <label className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
                                                        <span>👥</span>
                                                        <span>Character Roles &amp; Character Vault (Gemini Omni Image Roles)</span>
                                                    </label>
                                                    <button
                                                        type="button"
                                                        onClick={addCharacterRole}
                                                        className="bg-purple-900/60 hover:bg-purple-800 border border-purple-700 text-purple-200 text-xs font-bold px-2.5 py-1 rounded-lg transition"
                                                    >
                                                        + Add Character Role
                                                    </button>
                                                </div>

                                                {/* 🏛️ Character Vault & Saved Library */}
                                                <div className="bg-gray-950/80 border border-purple-900/50 rounded-xl p-3 space-y-2">
                                                    <div className="flex items-center justify-between">
                                                        <label className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
                                                            <span>🏛️</span>
                                                            <span>Character Vault Library</span>
                                                        </label>
                                                        <span className="text-[10px] text-gray-400 font-mono">
                                                            {savedVaultCharacters.length} Preset(s) Available
                                                        </span>
                                                    </div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {savedVaultCharacters.map((c, vIdx) => {
                                                            const chipText = c.name || c.role_id || `Preset ${vIdx + 1}`;
                                                            return (
                                                                <button
                                                                    key={vIdx}
                                                                    type="button"
                                                                    onClick={() => handleLoadVaultCharacter(c)}
                                                                    className="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 hover:border-purple-500 text-xs px-2.5 py-1 rounded-lg flex items-center gap-1.5 transition shadow-sm"
                                                                    title={`Click to load ${c.name || c.role_id} into roster`}
                                                                >
                                                                    {c.reference_url && (
                                                                        <img
                                                                            src={getDisplayableRefUrl(c.reference_url)}
                                                                            alt={c.name || "Preset"}
                                                                            className="w-4 h-4 rounded-full object-cover border border-purple-400/50"
                                                                        />
                                                                    )}
                                                                    <span>+</span>
                                                                    <span>{chipText}</span>
                                                                </button>
                                                            );
                                                        })}
                                                        {savedVaultCharacters.length === 0 && (
                                                            <span className="text-xs text-gray-500 italic py-0.5">
                                                                No characters in vault yet. Save character roles below to build your library.
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    {characters.map((char, cIdx) => (
                                                        <div key={cIdx} className="bg-gray-950 border border-gray-800 rounded-xl p-4 space-y-3">
                                                            <div className="flex items-center justify-between">
                                                                <span className="text-xs font-bold font-mono bg-purple-950 text-purple-300 px-2 py-0.5 rounded border border-purple-800">
                                                                    {char.role_id}
                                                                </span>
                                                                <div className="flex items-center space-x-2">
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => handleSaveCharacterToVault(char)}
                                                                        className="bg-gray-900 hover:bg-purple-950 text-purple-300 hover:text-purple-200 border border-purple-900/60 hover:border-purple-700 text-xs px-2 py-0.5 rounded-lg transition flex items-center gap-1 font-medium"
                                                                        title="Save character to vault library"
                                                                    >
                                                                        <span>💾</span>
                                                                        <span>Save Vault</span>
                                                                    </button>
                                                                    {characters.length > 1 && (
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => removeCharacter(cIdx)}
                                                                            className="text-gray-500 hover:text-red-400 text-xs px-1.5 py-0.5 transition"
                                                                            title="Remove Character Role"
                                                                        >
                                                                            🗑️
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            </div>

                                                            <div>
                                                                <label className="block text-[11px] text-gray-400 mb-1">Character Name</label>
                                                                <input
                                                                    type="text"
                                                                    value={char.name}
                                                                    onChange={(e) => updateCharacter(cIdx, "name", e.target.value)}
                                                                    placeholder="e.g. Harry"
                                                                    className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-medium"
                                                                />
                                                            </div>

                                                            <div>
                                                                <label className="block text-[11px] text-gray-400 mb-1">Visual Likeness &amp; Description</label>
                                                                <textarea
                                                                    rows={2}
                                                                    value={char.description}
                                                                    onChange={(e) => updateCharacter(cIdx, "description", e.target.value)}
                                                                    placeholder="Visual description for prompt compiler..."
                                                                    className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                                />
                                                            </div>

                                                            {/* Character Style Signifiers (Aesthetic Tags) */}
                                                            <div>
                                                                <label className="block text-[11px] font-bold text-pink-400 uppercase tracking-wider mb-1">
                                                                    👔 Wardrobe &amp; Aesthetic Style Signifiers
                                                                </label>
                                                                <div className="flex flex-wrap gap-1.5 mb-2">
                                                                    {(char.aesthetic_tags || []).map((tag, tIdx) => (
                                                                        <span
                                                                            key={tIdx}
                                                                            className="bg-purple-950/70 border border-purple-800/80 text-purple-200 text-xs px-2 py-0.5 rounded-lg flex items-center gap-1.5"
                                                                        >
                                                                            <span>{tag}</span>
                                                                            <button
                                                                                type="button"
                                                                                onClick={() => removeCharAestheticTag(cIdx, tag)}
                                                                                className="text-purple-400 hover:text-white font-bold text-xs"
                                                                                title="Remove Style Tag"
                                                                            >
                                                                                ×
                                                                            </button>
                                                                        </span>
                                                                    ))}
                                                                    {(!char.aesthetic_tags || char.aesthetic_tags.length === 0) && (
                                                                        <span className="text-[10px] text-gray-500 italic">No specific character style tags</span>
                                                                    )}
                                                                </div>
                                                                <div className="flex gap-1.5">
                                                                    <input
                                                                        type="text"
                                                                        value={charTagInputs[cIdx] || ""}
                                                                        onChange={(e) => setCharTagInputs({ ...charTagInputs, [cIdx]: e.target.value })}
                                                                        onKeyDown={(e) => {
                                                                            if (e.key === "Enter") {
                                                                                e.preventDefault();
                                                                                addCharAestheticTag(cIdx);
                                                                            }
                                                                        }}
                                                                        placeholder="e.g. Red Gucci Tracksuit..."
                                                                        className="flex-1 bg-gray-900 border border-gray-800 rounded-lg p-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                                    />
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => addCharAestheticTag(cIdx)}
                                                                        className="bg-purple-900/60 hover:bg-purple-800 text-purple-200 border border-purple-700 font-bold text-xs px-2.5 py-1.5 rounded-lg shadow transition"
                                                                    >
                                                                        + Add Style
                                                                    </button>
                                                                </div>
                                                            </div>

                                                            <div>
                                                                <div>
                                                                    <label className="block text-[11px] text-gray-400 mb-1">
                                                                        🎙️ Voice Profile / Vocal Style
                                                                    </label>
                                                                    <input
                                                                        type="text"
                                                                        value={char.voice_profile || ""}
                                                                        onChange={(e) => updateCharacter(cIdx, "voice_profile", e.target.value)}
                                                                        placeholder="e.g. Deep raspy baritone voice..."
                                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                                    />
                                                                </div>

                                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                                                                    <div>
                                                                        <label className="block text-[11px] font-bold text-purple-300 uppercase tracking-wider mb-1">
                                                                            🖼️ Gemini Image Role
                                                                        </label>
                                                                        <select
                                                                            value={char.image_role || "Character Reference"}
                                                                            onChange={(e) => updateCharacter(cIdx, "image_role", e.target.value)}
                                                                            className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-purple-200 focus:outline-none focus:border-purple-500 font-mono"
                                                                        >
                                                                            <option value="Character Reference">Character Reference</option>
                                                                            <option value="Product Reference">Product Reference</option>
                                                                            <option value="Starting Frame">Starting Frame</option>
                                                                            <option value="Style Reference">Style Reference</option>
                                                                        </select>
                                                                    </div>
                                                                    <div className="flex items-end pb-1">
                                                                        <label className="flex items-center space-x-2 cursor-pointer text-[11px] text-gray-300 bg-gray-900 border border-gray-800 hover:border-amber-500/50 p-2 rounded-lg w-full transition">
                                                                            <input
                                                                                type="checkbox"
                                                                                checked={!!char.is_offscreen_narrator}
                                                                                onChange={(e) => updateCharacter(cIdx, "is_offscreen_narrator", e.target.checked)}
                                                                                className="rounded border-gray-700 text-amber-500 focus:ring-amber-500 bg-gray-950 w-4 h-4"
                                                                            />
                                                                            <span className="font-bold text-amber-300">🎙️ Off-Screen Narrator</span>
                                                                        </label>
                                                                    </div>
                                                                </div>

                                                                <div>
                                                                    <label className="block text-[11px] text-gray-400 mb-1">🖼️ Reference Image URL (Gemini Omni Image Role)</label>
                                                                    <input
                                                                        type="text"
                                                                        value={char.reference_url || ""}
                                                                        onChange={(e) => updateCharacter(cIdx, "reference_url", e.target.value)}
                                                                        placeholder="https://example.com/character.jpg"
                                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white font-mono"
                                                                    />
                                                                    {char.reference_url && (
                                                                        <div className="flex items-center space-x-2 bg-purple-950/40 border border-purple-800/60 rounded-lg p-2 mt-2">
                                                                            <img
                                                                                src={getDisplayableRefUrl(char.reference_url)}
                                                                                alt={char.name || char.role_id}
                                                                                className="w-8 h-8 object-cover rounded border border-purple-500/50"
                                                                            />
                                                                            <span className="text-[10px] text-purple-300 font-mono truncate">{char.reference_url}</span>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>

                                            <div className="pt-3 flex flex-wrap justify-end gap-3">
                                                <button
                                                    type="button"
                                                    disabled={deconstructLoading || !concept.trim()}
                                                    onClick={() => handleDeconstructConcept(concept)}
                                                    className="bg-gray-900 hover:bg-gray-800 border border-purple-800 text-purple-300 font-bold text-xs py-3 px-5 rounded-xl shadow-lg flex items-center gap-2 transition disabled:opacity-50"
                                                    title="Analyze concept prompt to automatically extract characters, aesthetics, audio beat, and style tags"
                                                >
                                                    <span>✨</span>
                                                    <span>{deconstructLoading ? "Deconstructing Concept..." : "Deconstruct & Extract Cast (AI)"}</span>
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={expandLoading || !concept.trim()}
                                                    onClick={handleExpandStoryboard}
                                                    className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-black font-extrabold text-xs py-3 px-6 rounded-xl shadow-lg flex items-center gap-2 disabled:opacity-50"
                                                >
                                                    <span>🚀</span>
                                                    <span>{expandLoading ? "Expanding 60s Vision..." : "Expand Vision into 5-Part Storyboard Grid (AI)"}</span>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                        {/* STAGE 2: INTERACTIVE SEQUENTIAL SHOT PRODUCTION WORKSTATION */}
                        {activeStage === 2 && (
                            <div className="space-y-6">
                                {/* Top Header & Master Controls */}
                                <div className="bg-gradient-to-r from-purple-950/50 via-pink-950/50 to-amber-950/50 border border-purple-800/50 rounded-2xl p-5 shadow-xl flex flex-wrap items-center justify-between gap-4">
                                    <div>
                                        <h2 className="text-base font-bold text-purple-200 flex items-center gap-2">
                                            <span>📋</span>
                                            <span>Interactive Shot Production Workstation ({stageShots.length} Shots)</span>
                                        </h2>
                                        <p className="text-xs text-gray-400 mt-1">
                                            Tune shot directives, pre-render keyframe art, render clips one shot at a time, and apply conversational diffs.
                                        </p>
                                    </div>
                                    <div className="flex items-center bg-gray-950 border border-gray-800 rounded-xl p-1 shadow-inner">
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setStoryboardPath("path1");
                                                setActiveStage(1);
                                            }}
                                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                                                storyboardPath === "path1"
                                                    ? "bg-gradient-to-r from-amber-500 to-orange-500 text-black font-extrabold shadow"
                                                    : "text-gray-400 hover:text-white"
                                            }`}
                                        >
                                            <span>📜</span>
                                            <span>Path 1: Single Master Script</span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setStoryboardPath("path2")}
                                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                                                storyboardPath === "path2"
                                                    ? "bg-purple-600 text-white font-extrabold shadow"
                                                    : "text-gray-400 hover:text-white"
                                            }`}
                                        >
                                            <span>📋</span>
                                            <span>Path 2: Per-Shot Workstation</span>
                                        </button>
                                    </div>
                                            <div className="flex items-center space-x-2">
                                                <button
                                                    type="button"
                                                    onClick={() => setShowScreenplayModal(true)}
                                                    className="bg-amber-950/80 hover:bg-amber-900 border border-amber-700 text-amber-200 text-xs font-bold px-3 py-2 rounded-xl transition flex items-center gap-1.5 shadow"
                                                >
                                                    <span>📜</span>
                                                    <span>View Master Screenplay &amp; Notes</span>
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleGenerateAllKeyframes()}
                                                    className="bg-purple-950/70 hover:bg-purple-900 border border-purple-800 text-purple-200 text-xs font-bold px-3 py-2 rounded-xl transition flex items-center gap-1.5"
                                                    title="Generate keyframe images for all shot cards concurrently"
                                                >
                                                    <span>🖼️</span>
                                                    <span>Generate All Keyframes</span>
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={isBatchGeneratingVideos}
                                                    onClick={() => handleGenerateAllShotVideosSequentially(false)}
                                                    className="bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white text-xs font-bold px-3 py-2 rounded-xl transition flex items-center gap-1.5 shadow-md disabled:opacity-50"
                                                >
                                                    <span>🎬</span>
                                                    <span>Batch Render All Shots (1 ➔ N)</span>
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={addStageShot}
                                                    className="bg-purple-900/60 hover:bg-purple-800 border border-purple-700 text-purple-200 text-xs font-bold px-3 py-2 rounded-xl transition"
                                                >
                                                    + Add Shot Card
                                                </button>
                                            </div>
                                        </div>

                                        {/* Shot Stepper Tabs Header */}
                                        <div className="flex items-center gap-2 overflow-x-auto pb-2 custom-scrollbar">
                                            {stageShots.map((s, i) => {
                                                const sNum = s.shot_index || (i + 1);
                                                const isActive = activeShotIdx === i;
                                                const hasVideo = !!s.video_url;
                                                const hasKeyframe = !!s.keyframe_image_url;
                                                return (
                                                    <button
                                                        key={i}
                                                        type="button"
                                                        onClick={() => setActiveShotIdx(i)}
                                                        className={`px-4 py-2.5 rounded-xl font-bold text-xs transition flex items-center gap-2 border whitespace-nowrap ${
                                                            isActive
                                                                ? "bg-purple-600 text-white border-purple-400 shadow-lg shadow-purple-900/40 ring-2 ring-purple-400/50"
                                                                : hasVideo
                                                                ? "bg-green-950/60 text-green-300 border-green-800 hover:bg-green-900/50"
                                                                : hasKeyframe
                                                                ? "bg-amber-950/60 text-amber-300 border-amber-800 hover:bg-amber-900/50"
                                                                : "bg-gray-900 text-gray-400 border-gray-800 hover:bg-gray-800"
                                                        }`}
                                                    >
                                                        <span>Shot #{sNum}</span>
                                                        {hasVideo ? (
                                                            <span className="text-[10px] bg-green-500 text-black px-1.5 py-0.5 rounded font-extrabold">✓ Video</span>
                                                        ) : hasKeyframe ? (
                                                            <span className="text-[10px] bg-amber-500 text-black px-1.5 py-0.5 rounded font-extrabold">🖼️ Keyframe</span>
                                                        ) : (
                                                            <span className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">Pending</span>
                                                        )}
                                                    </button>
                                                );
                                            })}
                                        </div>

                                        {/* Main 2-Column Workstation Layout */}
                                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                            {/* LEFT / MAIN COLUMN: Active Shot Editor Workstation (7/12) */}
                                            <div className="lg:col-span-7 space-y-5">
                                                {(() => {
                                                    const idx = Math.min(activeShotIdx, Math.max(0, stageShots.length - 1));
                                                    const shot = stageShots[idx];
                                                    if (!shot) return null;
                                                    const sNum = shot.shot_index || (idx + 1);

                                                    return (
                                                        <div className="bg-gray-900 border border-purple-900/60 rounded-2xl p-5 shadow-2xl space-y-4">
                                                            {/* Shot Workstation Header */}
                                                            <div className="flex flex-wrap items-center justify-between border-b border-gray-800 pb-3 gap-2">
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    <span className="text-sm font-extrabold text-amber-300 bg-amber-950 px-3 py-1 rounded-xl border border-amber-700">
                                                                        Shot #{sNum} of {stageShots.length} ({shot.duration_seconds || 10}s)
                                                                    </span>
                                                                    <span className="text-xs font-mono font-extrabold text-amber-200 bg-black/60 px-2.5 py-1 rounded-xl border border-amber-800/80 flex items-center gap-1">
                                                                        <span>⏱️</span>
                                                                        <span>{getShotTimecodeRange(stageShots, idx)}</span>
                                                                    </span>
                                                                    <span className="text-xs font-bold text-cyan-300 bg-cyan-950 px-2.5 py-1 rounded-lg border border-cyan-800">
                                                                        🎭 {shot.narrative_stage || "Rising Action"}
                                                                    </span>
                                                                </div>

                                                                 {/* Scene Continuation & Continuous Shot Control */}
                                                                 <div className="flex flex-col space-y-2 bg-gray-950 border border-gray-800 rounded-xl p-2.5">
                                                                     <div className="flex items-center justify-between">
                                                                         <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1">
                                                                             <span>🎥</span>
                                                                             <span>Continuous Shot &amp; Scene Transition Control</span>
                                                                         </span>
                                                                         <div className="flex items-center bg-black border border-gray-800 rounded-lg p-0.5">
                                                                             <button
                                                                                 type="button"
                                                                                 onClick={() => {
                                                                                     updateStageShot(idx, "camera_transition", "Continuous match cut from preceding shot");
                                                                                     updateStageShot(idx, "preceding_context", idx > 0 ? `Chained from Shot #${idx}` : "Initial shot");
                                                                                 }}
                                                                                 className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                                                                                     shot.camera_transition?.includes("Continuous") || shot.camera_transition?.includes("match")
                                                                                         ? "bg-indigo-600 text-white shadow"
                                                                                         : "text-gray-400 hover:text-white"
                                                                                 }`}
                                                                             >
                                                                                 🔗 Continue Scene
                                                                             </button>
                                                                             <button
                                                                                 type="button"
                                                                                 onClick={() => {
                                                                                     updateStageShot(idx, "camera_transition", "Fresh camera angle and new scene setting");
                                                                                     updateStageShot(idx, "preceding_context", "New scene baseline");
                                                                                 }}
                                                                                 className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                                                                                     shot.camera_transition?.includes("Fresh") || shot.camera_transition?.includes("New")
                                                                                         ? "bg-purple-600 text-white shadow"
                                                                                         : "text-gray-400 hover:text-white"
                                                                                 }`}
                                                                             >
                                                                                 ✨ New Scene
                                                                             </button>
                                                                         </div>
                                                                     </div>
                                                                     <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                                                                         <div>
                                                                             <label className="text-[9px] font-bold text-gray-400 block mb-0.5">Camera Transition Control:</label>
                                                                             <input
                                                                                 type="text"
                                                                                 value={shot.camera_transition || "Continuous match cut from preceding shot"}
                                                                                 onChange={(e) => updateStageShot(idx, "camera_transition", e.target.value)}
                                                                                 placeholder="e.g. Continuous match cut from preceding shot"
                                                                                 className="w-full bg-black/60 border border-gray-800 rounded-lg p-1.5 text-gray-200 focus:outline-none focus:border-indigo-500 font-mono text-[10px]"
                                                                             />
                                                                         </div>
                                                                         <div>
                                                                             <label className="text-[9px] font-bold text-gray-400 block mb-0.5">Subject Character Continuity:</label>
                                                                             <input
                                                                                 type="text"
                                                                                 value={shot.character_continuity || "Maintain subject outfit, posture, and facial expression"}
                                                                                 onChange={(e) => updateStageShot(idx, "character_continuity", e.target.value)}
                                                                                 placeholder="e.g. Maintain subject outfit, posture, and facial expression"
                                                                                 className="w-full bg-black/60 border border-gray-800 rounded-lg p-1.5 text-gray-200 focus:outline-none focus:border-indigo-500 font-mono text-[10px]"
                                                                             />
                                                                         </div>
                                                                     </div>
                                                                 </div>
                                                            </div>

                                                            {/* 16:9 Large Keyframe Preview Container */}
                                                            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-gray-800 flex flex-col items-center justify-center relative group shadow-inner">
                                                                {shot.keyframe_image_url ? (
                                                                    <img
                                                                        src={getDisplayableRefUrl(shot.keyframe_image_url)}
                                                                        alt={`Keyframe Shot #${sNum}`}
                                                                        className="w-full h-full object-contain bg-gray-950"
                                                                    />
                                                                ) : (
                                                                    <div className="p-6 text-center space-y-2 text-gray-500">
                                                                        <span className="text-3xl block">🖼️</span>
                                                                        <span className="text-xs font-semibold block text-gray-400">No Keyframe Art Generated Yet</span>
                                                                        <span className="text-[10px] text-gray-600 block">Pre-render visual keyframe art to anchor starting visual tone</span>
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {/* Keyframe Generation Button */}
                                                            <button
                                                                type="button"
                                                                disabled={keyframeLoadingMap[sNum]}
                                                                onClick={() => handleGenerateKeyframeImage(idx, shot)}
                                                                className="w-full bg-purple-950/70 hover:bg-purple-900 border border-purple-800 text-purple-200 font-bold text-xs py-2 px-4 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-50"
                                                            >
                                                                <span>🖼️</span>
                                                                <span>
                                                                    {keyframeLoadingMap[sNum]
                                                                        ? "Rendering Keyframe Art (Gemini 3.1 Flash)..."
                                                                        : "🖼️ Generate / Re-generate Keyframe Image (Gemini 3.1 Flash)"}
                                                                </span>
                                                            </button>

                                                            {/* Prompt & Payload Inspector Drawer Toggle */}
                                                            <div className="pt-1">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => setShowInspectorMap((prev) => ({ ...prev, [sNum]: !prev[sNum] }))}
                                                                    className="w-full bg-black/60 hover:bg-black/90 border border-cyan-800/60 text-cyan-300 font-bold text-xs py-2 px-3 rounded-xl flex items-center justify-between transition"
                                                                >
                                                                    <span className="flex items-center gap-2">
                                                                        <span>🔍</span>
                                                                        <span>Inspect Prompt &amp; Multimodal Image Payload</span>
                                                                    </span>
                                                                    <span className="text-[10px] font-mono text-cyan-400">
                                                                        {showInspectorMap[sNum] ? "▲ Hide Inspector" : "▼ Show Prompt Details"}
                                                                    </span>
                                                                </button>

                                                                {showInspectorMap[sNum] && (
                                                                    <div className="mt-2 bg-gray-950 border border-cyan-950 rounded-xl p-3.5 space-y-3 text-xs font-mono">
                                                                        <div>
                                                                            <span className="font-bold text-cyan-400 block mb-1 text-[11px]">🖼️ Multimodal Reference Images Status:</span>
                                                                            <div className="space-y-1.5 text-[10px]">
                                                                                <div className="flex items-center justify-between bg-black/60 p-2 rounded border border-gray-800">
                                                                                    <span className="text-gray-300">Image #1: Keyframe Seed Image</span>
                                                                                    <span className={shot.keyframe_image_url ? "text-green-400 font-bold" : "text-amber-400"}>
                                                                                        {shot.keyframe_image_url ? "ATTACHED ✓" : "OPTIONAL (Missing)"}
                                                                                    </span>
                                                                                </div>
                                                                                {characters && characters.map((c, cI) => (
                                                                                    <div key={cI} className="flex items-center justify-between bg-black/60 p-2 rounded border border-gray-800">
                                                                                        <span className="text-purple-300">{c.role_id || `Role #${cI + 1}`} ({c.name || "Unnamed"}):</span>
                                                                                        <span className={c.reference_url ? "text-green-400 font-bold" : "text-gray-500"}>
                                                                                            {c.reference_url ? "ATTACHED ✓" : "No Reference URL"}
                                                                                        </span>
                                                                                    </div>
                                                                                ))}
                                                                            </div>
                                                                        </div>

                                                                        {shot.raw_compiled_prompt ? (
                                                                            <div>
                                                                                <span className="font-bold text-cyan-400 block mb-1 text-[11px]">📜 Exact Timecoded Prompt Sent to Gemini:</span>
                                                                                <pre className="bg-black/90 p-3 rounded-lg border border-cyan-900/60 text-[10px] text-cyan-200 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed custom-scrollbar">
                                                                                    {shot.raw_compiled_prompt}
                                                                                </pre>
                                                                            </div>
                                                                        ) : (
                                                                            <div>
                                                                                <span className="font-bold text-cyan-400 block mb-1 text-[11px]">📜 Formatted Four-Block Prompt Structure (Omni Flash Preview):</span>
                                                                                <pre className="bg-black/90 p-3 rounded-lg border border-cyan-900/60 text-[10px] text-cyan-200 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed custom-scrollbar">
{`### INPUT ROLES
${(characters || []).filter(c => c.reference_url).map(c => `- ${c.role_id} (${c.image_role || "Character Reference"}): ${c.reference_url}`).join("\n") || "None."}

### CHARACTER PROFILES
${(characters || []).map(c => `- ${c.role_id} (${c.name || "Unnamed"}): ${c.description || "Visual profile"}${c.is_offscreen_narrator ? " [🎙️ Off-Screen Narrator]" : ""}`).join("\n") || "- Role A: Primary Subject"}

### SCENE INSTRUCTIONS
Camera & Lighting: In a single continuous shot. No scene cuts. ${shot.style_lighting || stageStyleTone}
Environment: ${shot.location || "Cinematic set"}
Audio: ${shot.audio || "Atmospheric soundscape"}

### TIMELINE
${shot.action || "[0-3s] Action: Establishing shot. Audio: Rhythmic beat.\n[3-6s] Action: Subject movement.\n[6-10s] Action: Climax resolution."}`}
                                                                                </pre>
                                                                                <div className="text-[10px] text-gray-500 italic bg-black/40 p-2 mt-1 rounded border border-gray-800 flex items-center justify-between">
                                                                                    <span>💡 Formatted according to Gemini Omni Flash Four-Block Prompt Specification.</span>
                                                                                    <span>Render shot video to inspect exact compiled payload.</span>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {/* 5-Part Directives Editor */}
                                                            <div className="space-y-3 pt-2 text-xs">
                                                                <div className="bg-amber-950/40 border border-amber-500/30 rounded-xl p-2.5">
                                                                    <label className="text-[10px] font-extrabold uppercase tracking-wider text-amber-300 block mb-1">⚡ Action Summary</label>
                                                                    <input
                                                                        type="text"
                                                                        value={shot.summary || ""}
                                                                        onChange={(e) => updateStageShot(idx, "summary", e.target.value)}
                                                                        className="w-full bg-gray-950 border border-amber-500/50 rounded-lg p-2 text-amber-200 font-bold text-xs focus:outline-none focus:border-amber-400"
                                                                    />
                                                                </div>
                                                                <div>
                                                                    <label className="text-[10px] font-bold uppercase tracking-wider text-pink-400 block mb-0.5 flex items-center justify-between">
                                                                        <span>1. Visual Action &amp; Scene Description</span>
                                                                        <span className="text-[9px] text-gray-500 font-mono">Describe camera, character movement, and setting</span>
                                                                    </label>
                                                                    <textarea
                                                                        rows={4}
                                                                        value={shot.action || ""}
                                                                        onChange={(e) => updateStageShot(idx, "action", e.target.value)}
                                                                        placeholder="e.g. Spectacled Wizard Bruv enters courtyard under dramatic lighting. Dynamic zoom on glowing wand."
                                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-gray-200 focus:outline-none focus:border-pink-500 text-xs font-mono leading-relaxed"
                                                                    />
                                                                </div>
                                                                <div>
                                                                    <label className="text-[10px] font-bold uppercase tracking-wider text-purple-400 block mb-0.5">2. Location</label>
                                                                    <input
                                                                        type="text"
                                                                        value={shot.location || ""}
                                                                        onChange={(e) => updateStageShot(idx, "location", e.target.value)}
                                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2 text-gray-200 focus:outline-none focus:border-purple-500 text-xs"
                                                                    />
                                                                </div>
                                                                <div>
                                                                    <label className="text-[10px] font-bold uppercase tracking-wider text-amber-400 block mb-0.5">3. Style &amp; Lighting</label>
                                                                    <input
                                                                        type="text"
                                                                        value={shot.style_lighting || ""}
                                                                        onChange={(e) => updateStageShot(idx, "style_lighting", e.target.value)}
                                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2 text-gray-200 focus:outline-none focus:border-amber-500 text-xs"
                                                                    />
                                                                    <div className="flex flex-wrap gap-1 mt-1.5">
                                                                        {["🎨 90s Anime", "🍿 3D Stylized", "💥 Comic Book", "🖌️ 2D Vector", "👾 Pixel Art", "🏰 1930s Hose", "🐉 Claymation", "✨ Cyberpunk", "🎬 Cinematic"].map((preset) => (
                                                                            <button
                                                                                key={preset}
                                                                                type="button"
                                                                                onClick={() => updateStageShot(idx, "style_lighting", `${preset}, high-contrast lighting`)}
                                                                                className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-950 text-amber-300 hover:bg-amber-950/60 border border-amber-900/40 transition"
                                                                            >
                                                                                {preset}
                                                                            </button>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                                    <div>
                                                                        <label className="text-[10px] font-bold uppercase tracking-wider text-cyan-400 block mb-0.5">4. Framing &amp; Motion</label>
                                                                        <input
                                                                            type="text"
                                                                            value={shot.framing_motion || ""}
                                                                            onChange={(e) => updateStageShot(idx, "framing_motion", e.target.value)}
                                                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2 text-gray-200 focus:outline-none focus:border-cyan-500 text-xs"
                                                                        />
                                                                    </div>
                                                                    <div>
                                                                        <label className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 block mb-0.5">5. Audio Soundscape (Timecoded Audio Blocks)</label>
                                                                        <input
                                                                            type="text"
                                                                            value={shot.audio || ""}
                                                                            onChange={(e) => updateStageShot(idx, "audio", e.target.value)}
                                                                            placeholder="e.g. [0-3s] 140 BPM Trap Beat Intro | [3-10s] Heavy 808 Sub-Bass & Crisp Snares"
                                                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2 text-gray-200 focus:outline-none focus:border-emerald-500 text-xs font-mono"
                                                                        />
                                                                    </div>
                                                                </div>
                                                                <div>
                                                                    <label className="text-[10px] font-bold uppercase tracking-wider text-rose-400 block mb-0.5 flex items-center justify-between">
                                                                        <span>6. Dialogue &amp; On-Screen Speech (Auto-populated from Screenplay)</span>
                                                                        <span className="text-[9px] text-gray-500 font-mono">e.g. Dumble Dior: &quot;Welcome!&quot; | Snape Dawg: &quot;Potions class is in session!&quot;</span>
                                                                    </label>
                                                                    <input
                                                                        type="text"
                                                                        value={shot.dialogue || ""}
                                                                        onChange={(e) => updateStageShot(idx, "dialogue", e.target.value)}
                                                                        placeholder='e.g. Dumble Dior: "Welcome!" | Snape Dawg: "Potions class is in session!"'
                                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2 text-gray-200 focus:outline-none focus:border-rose-500 text-xs"
                                                                    />
                                                                </div>
                                                            </div>

                                                            {/* Render Video & Single-Change Conversational Diff Workstation */}
                                                            <div className="pt-3 border-t border-gray-800 space-y-3">
                                                                <button
                                                                    type="button"
                                                                    disabled={shotGeneratingMap[sNum]}
                                                                    onClick={() => handleGenerateShotVideo(idx, shot)}
                                                                    className="w-full bg-gradient-to-r from-pink-600 via-purple-600 to-indigo-600 hover:from-pink-500 hover:to-indigo-500 text-white font-extrabold text-xs py-3 px-4 rounded-xl shadow-lg flex items-center justify-center gap-2 disabled:opacity-50 transition"
                                                                >
                                                                    <span>🎬</span>
                                                                    <span>
                                                                        {shotGeneratingMap[sNum]
                                                                            ? `Rendering Shot #${sNum} Video...`
                                                                            : `🎬 Render Video for Shot #${sNum}`}
                                                                    </span>
                                                                </button>

                                                                {/* Single-Change Conversational Diff Editor Bar */}
                                                                <div className="bg-purple-950/40 border border-purple-500/40 rounded-xl p-3 space-y-2">
                                                                    <div className="flex items-center justify-between text-[11px] font-bold text-purple-300">
                                                                        <span className="flex items-center gap-1.5">
                                                                            <span>✨</span>
                                                                            <span>Conversational Edit (Single-Change Diff)</span>
                                                                        </span>
                                                                        <span className="text-[10px] bg-purple-900/80 text-purple-200 px-2 py-0.5 rounded font-mono">
                                                                            Preserve 95% baseline clip
                                                                        </span>
                                                                    </div>
                                                                    <div className="flex gap-2">
                                                                        <input
                                                                            type="text"
                                                                            value={shotDiffPrompts[sNum] || ""}
                                                                            onChange={(e) => setShotDiffPrompts((prev) => ({ ...prev, [sNum]: e.target.value }))}
                                                                            placeholder="e.g. Make camera zoom 50% faster and add glowing neon outlines..."
                                                                            className="flex-1 bg-gray-950 border border-purple-800 rounded-lg p-2 text-xs text-purple-100 placeholder-purple-400/50 focus:outline-none focus:border-purple-400"
                                                                        />
                                                                        <button
                                                                            type="button"
                                                                            disabled={shotDiffLoading[sNum] || !shot.video_url || !(shotDiffPrompts[sNum] || "").trim()}
                                                                            onClick={() => handleApplyShotDiff(idx, shot)}
                                                                            className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs px-3 py-2 rounded-lg transition disabled:opacity-50 shadow"
                                                                        >
                                                                            {shotDiffLoading[sNum] ? "Diffing..." : "Apply Diff"}
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            {/* Stepper Footer Buttons */}
                                                            <div className="flex items-center justify-between pt-3 border-t border-gray-800">
                                                                <button
                                                                    type="button"
                                                                    disabled={activeShotIdx === 0}
                                                                    onClick={() => setActiveShotIdx(prev => Math.max(0, prev - 1))}
                                                                    className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-bold py-2 px-4 rounded-xl disabled:opacity-40 transition"
                                                                >
                                                                    ⬅️ Previous Shot
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    disabled={activeShotIdx >= stageShots.length - 1}
                                                                    onClick={() => setActiveShotIdx(prev => Math.min(stageShots.length - 1, prev + 1))}
                                                                    className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-black font-extrabold text-xs py-2 px-5 rounded-xl disabled:opacity-40 shadow transition"
                                                                >
                                                                    🚀 Approve &amp; Next Shot ➔
                                                                </button>
                                                            </div>
                                                        </div>
                                                    );
                                                })()}
                                            </div>

                                            {/* RIGHT / SIDE COLUMN: Live Dailies Reel & Shot Strip (5/12) */}
                                            <div className="lg:col-span-5 space-y-4">
                                                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
                                                    <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                                                        <span>🎞️</span>
                                                        <span>Live Dailies Reel &amp; Shot Strip</span>
                                                    </h3>
                                                    <span className="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800 font-mono">
                                                        {stageShots.filter(s => s.video_url).length} / {stageShots.length} Ready
                                                    </span>
                                                </div>

                                                <div className="space-y-4 max-h-[850px] overflow-y-auto pr-1 custom-scrollbar">
                                                    {stageShots.map((s, i) => {
                                                        const sNum = s.shot_index || (i + 1);
                                                        const isActive = activeShotIdx === i;

                                                        return (
                                                            <div
                                                                key={i}
                                                                onClick={() => setActiveShotIdx(i)}
                                                                className={`bg-gray-950 border rounded-2xl p-3.5 cursor-pointer transition flex flex-col space-y-2.5 ${
                                                                    isActive
                                                                        ? "border-amber-500 ring-2 ring-amber-500/40 bg-amber-950/20 shadow-xl"
                                                                        : "border-gray-800 hover:border-gray-700"
                                                                }`}
                                                            >
                                                                <div className="flex items-center justify-between text-xs">
                                                                    <span className="font-extrabold text-amber-300 flex items-center gap-1.5">
                                                                        <span>Shot #{sNum}</span>
                                                                        {isActive && <span className="text-[9px] bg-amber-500 text-black px-1.5 py-0.2 rounded font-extrabold uppercase">Editing</span>}
                                                                    </span>
                                                                    <span className="text-[10px] font-mono text-gray-400">
                                                                        {s.duration_seconds || 10}s
                                                                    </span>
                                                                </div>

                                                                {/* Video or Keyframe Preview */}
                                                                <div className="aspect-video bg-black rounded-xl overflow-hidden border border-gray-800 flex items-center justify-center relative">
                                                                    {s.video_url ? (
                                                                        <video
                                                                            src={getDisplayableRefUrl(s.video_url)}
                                                                            controls
                                                                            className="w-full h-full object-contain"
                                                                        />
                                                                    ) : s.keyframe_image_url ? (
                                                                        <img
                                                                            src={getDisplayableRefUrl(s.keyframe_image_url)}
                                                                            alt={`Keyframe Shot #${sNum}`}
                                                                            className="w-full h-full object-contain"
                                                                        />
                                                                    ) : (
                                                                        <div className="text-center p-3 text-gray-600 text-xs italic">
                                                                            Pending Generation
                                                                        </div>
                                                                    )}
                                                                </div>

                                                                <p className="text-[11px] text-gray-300 line-clamp-2 font-mono">
                                                                    {s.summary || s.action || "No action specified"}
                                                                </p>
                                                            </div>
                                                        );
                                                    })}
                                                </div>

                                                {/* Bottom Action Bar */}
                                                <div className="pt-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => setActiveStage(4)}
                                                        className="w-full bg-gradient-to-r from-pink-600 via-purple-600 to-teal-600 hover:from-pink-500 hover:to-teal-500 text-white font-extrabold text-xs py-3 px-5 rounded-xl shadow-lg flex items-center justify-center gap-2 transition"
                                                    >
                                                        <span>🍿</span>
                                                        <span>Proceed to Stage 4 Final Master Stitch ➔</span>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* STAGE 3: THE DAILIES & CONVERSATIONAL DIFF */}
                                {activeStage === 3 && (
                                    <div className="space-y-6">
                                        <div className="bg-gradient-to-r from-pink-950/40 via-purple-950/40 to-indigo-950/40 border border-pink-800/50 rounded-2xl p-5 shadow-xl flex items-center justify-between">
                                            <div>
                                                <h2 className="text-base font-bold text-pink-200 flex items-center gap-2">
                                                    <span>📽️</span>
                                                    <span>Stage 3: The Dailies &amp; Single-Change Conversational Diff</span>
                                                </h2>
                                                <p className="text-xs text-gray-400 mt-1">
                                                    Review generated clip iterations side-by-side. Perform single-change conversational diffs adhering to the Gemini Omni Flash golden rule.
                                                </p>
                                            </div>
                                            {!parentTurnId && (
                                                <button
                                                    type="button"
                                                    disabled={loading}
                                                    onClick={handleGenerate}
                                                    className="bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white font-extrabold text-xs py-2.5 px-5 rounded-xl shadow-lg flex items-center gap-2 disabled:opacity-50 transition"
                                                >
                                                    <span>⚡</span>
                                                    <span>{loading ? "Generating..." : "Generate Initial Video Clip"}</span>
                                                </button>
                                            )}
                                        </div>

                                        {/* Shot Selector Tabs / Dropdown */}
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl space-y-3">
                                            <div className="flex items-center justify-between">
                                                <label className="text-xs font-bold text-pink-300 uppercase tracking-wider flex items-center gap-2">
                                                    <span>🎯</span>
                                                    <span>Select Shot Card to Inspect &amp; Diff</span>
                                                </label>
                                                <select
                                                    value={selectedShotIndex}
                                                    onChange={(e) => setSelectedShotIndex(parseInt(e.target.value))}
                                                    className="bg-gray-950 border border-gray-700 rounded text-xs font-mono px-3 py-1.5 text-pink-300 focus:outline-none focus:border-pink-500"
                                                >
                                                    {stageShots.map((s, i) => {
                                                        const sIdx = s.shot_index || (i + 1);
                                                        return (
                                                            <option key={sIdx} value={sIdx}>
                                                                Shot #{sIdx} {s.summary ? `— ${s.summary}` : ""} {s.video_url ? "(✓ Video)" : ""}
                                                            </option>
                                                        );
                                                    })}
                                                </select>
                                            </div>
                                            <div className="flex flex-wrap gap-2 pt-1 border-t border-gray-800">
                                                {stageShots.map((s, i) => {
                                                    const sIdx = s.shot_index || (i + 1);
                                                    const isSelected = selectedShotIndex === sIdx;
                                                    return (
                                                        <button
                                                            key={sIdx}
                                                            type="button"
                                                            onClick={() => setSelectedShotIndex(sIdx)}
                                                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                                                                isSelected
                                                                    ? "bg-pink-600 text-white shadow-md shadow-pink-900/50 border border-pink-400"
                                                                    : "bg-gray-950 text-gray-300 hover:bg-gray-800 border border-gray-800"
                                                            }`}
                                                        >
                                                            <span>Shot #{sIdx}</span>
                                                            {s.video_url && <span className="text-[10px] text-green-400 font-extrabold">✓</span>}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl space-y-3">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs font-bold text-purple-300">Active Clip (Shot #{selectedShotIndex})</span>
                                                    <span className={`text-[10px] px-2 py-0.5 rounded border font-bold ${parentTurnId ? "bg-green-950 text-green-400 border-green-800" : "bg-amber-950 text-amber-300 border-amber-800"}`}>
                                                        {parentTurnId ? "LIVE" : "READY TO GENERATE"}
                                                    </span>
                                                </div>
                                                {(() => {
                                                    const currentShot = stageShots.find(s => (s.shot_index || (stageShots.indexOf(s) + 1)) === selectedShotIndex) || stageShots[0];
                                                    const shotVideo = currentShot?.video_url || currentVideo;

                                                    const promptLines = currentShot ? [
                                                        currentShot.action ? `- Action / Subject: ${currentShot.action}` : "",
                                                        currentShot.location ? `- Location / Setting: ${currentShot.location}` : "",
                                                        currentShot.style_lighting ? `- Style & Lighting: ${currentShot.style_lighting}` : "",
                                                        currentShot.framing_motion ? `- Framing & Motion: ${currentShot.framing_motion}` : "",
                                                        currentShot.audio ? `- Audio Directives: ${currentShot.audio}` : "",
                                                        currentShot.dialogue ? `- Dialogue / Text Overlay: "${currentShot.dialogue}"` : ""
                                                    ].filter(Boolean) : [];
                                                    const formattedPrompt = promptLines.join("\n");

                                                    return (
                                                        <div className="space-y-3">
                                                            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-gray-800 flex flex-col items-center justify-center relative group">
                                                                {shotVideo ? (
                                                                    <video src={getDisplayableRefUrl(shotVideo)} controls className="w-full h-full object-cover" />
                                                                ) : (
                                                                    <div className="p-6 text-center space-y-3">
                                                                        <span className="text-4xl block animate-bounce">🎬</span>
                                                                        <div className="text-xs text-gray-300 font-bold">No clip generated yet for Shot #{selectedShotIndex}.</div>
                                                                        <p className="text-[11px] text-gray-500 max-w-xs mx-auto">
                                                                            Click below or generate video on Shot #{selectedShotIndex}'s card in Stage 2!
                                                                        </p>
                                                                        <button
                                                                            type="button"
                                                                            disabled={loading}
                                                                            onClick={handleGenerate}
                                                                            className="bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white font-extrabold text-xs py-2.5 px-5 rounded-xl shadow-lg inline-flex items-center gap-2 transition disabled:opacity-50"
                                                                        >
                                                                            <span>⚡</span>
                                                                            <span>{loading ? "Generating Initial Video..." : `Generate Video for Shot #${selectedShotIndex}`}</span>
                                                                        </button>
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {/* Active Shot Video Generation Prompt Display */}
                                                            <div className="bg-gray-950 border border-purple-900/40 rounded-xl p-3 space-y-2">
                                                                <div className="flex items-center justify-between border-b border-gray-800/80 pb-1.5">
                                                                    <span className="text-[11px] font-bold text-purple-300 flex items-center gap-1.5">
                                                                        <span>📜</span>
                                                                        <span>Gemini Omni Flash Prompt (Shot #{selectedShotIndex})</span>
                                                                    </span>
                                                                    <button
                                                                        type="button"
                                                                        onClick={() => {
                                                                            if (formattedPrompt) {
                                                                                navigator.clipboard.writeText(formattedPrompt);
                                                                                alert("Video prompt copied to clipboard!");
                                                                            }
                                                                        }}
                                                                        className="text-[10px] bg-purple-950 hover:bg-purple-900 text-purple-200 border border-purple-800 px-2 py-0.5 rounded transition flex items-center gap-1 font-bold"
                                                                    >
                                                                        <span>📋</span>
                                                                        <span>Copy</span>
                                                                    </button>
                                                                </div>
                                                                <pre className="text-[11px] font-mono text-pink-200/90 bg-gray-900/80 border border-gray-800/80 rounded-lg p-2.5 whitespace-pre-wrap overflow-x-auto leading-relaxed">
                                                                    {formattedPrompt || "No prompt details specified for this shot."}
                                                                </pre>
                                                            </div>
                                                        </div>
                                                    );
                                                })()}
                                            </div>

                                            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl space-y-3">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs font-bold text-gray-400">Previous / Baseline Reference Clip</span>
                                                    <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded">BASELINE</span>
                                                </div>
                                                <div className="aspect-video bg-black rounded-xl overflow-hidden border border-gray-800 flex items-center justify-center">
                                                    {history.length > 1 ? (
                                                        <video src={getDisplayableRefUrl(history[history.length - 2].videoUrl)} controls className="w-full h-full object-cover" />
                                                    ) : (
                                                        <div className="text-xs text-gray-500 italic p-4 text-center">No previous turn clip yet. Generate a diff turn to compare side-by-side.</div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                            <div className="flex items-center space-x-3 bg-amber-950/60 border border-amber-500/50 rounded-xl p-3 text-amber-300 text-xs">
                                                <span className="text-lg">⚠️</span>
                                                <div>
                                                    <span className="font-bold block">Gemini Omni Flash Rule: One Change Per Turn</span>
                                                    <span className="text-amber-300/80 text-[11px]">For best results, request only one modification per diff turn (e.g. "Add neon green rims to car" or "Change shirt color to red").</span>
                                                </div>
                                            </div>

                                            <div>
                                                <label className="text-xs font-bold text-pink-400 block mb-1">Conversational Diff Instruction Prompt:</label>
                                                <div className="flex gap-2">
                                                    <input
                                                        type="text"
                                                        value={deltaPrompt}
                                                        onChange={(e) => setDeltaPrompt(e.target.value)}
                                                        placeholder="e.g. Change Harry's glasses to gold metallic sunglasses..."
                                                        className="flex-1 bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-pink-500 font-mono"
                                                    />
                                                    <button
                                                        type="button"
                                                        disabled={loading}
                                                        onClick={handleGenerate}
                                                        className="bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white font-bold text-xs px-5 rounded-xl shadow-lg flex items-center gap-2 disabled:opacity-50"
                                                    >
                                                        <span>⚡</span>
                                                        <span>{loading ? "Generating..." : "Apply Diff &amp; Render"}</span>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="pt-3 flex justify-between items-center">
                                            <button
                                                type="button"
                                                onClick={() => setShowCommitModal(true)}
                                                className="bg-amber-950/60 hover:bg-amber-900 border border-amber-700 text-amber-200 text-xs font-bold px-4 py-2.5 rounded-xl transition flex items-center gap-2"
                                            >
                                                <span>⚓</span>
                                                <span>Commit &amp; Re-Anchor Keyframe</span>
                                            </button>
                                            <button
                                                type="button"
                                                onClick={handleProceedToStage4}
                                                className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-extrabold text-xs py-3 px-6 rounded-xl shadow-lg flex items-center gap-2"
                                            >
                                                <span>🏆</span>
                                                <span>Proceed to Stage 4: The Final Cut ➔</span>
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* STAGE 4: THE FINAL CUT & GCS EXPORT */}
                                {activeStage === 4 && (
                                    <div className="space-y-6">
                                        <div className="bg-gradient-to-r from-emerald-950/40 via-teal-950/40 to-cyan-950/40 border border-emerald-800/50 rounded-2xl p-5 shadow-xl">
                                            <h2 className="text-base font-bold text-emerald-200 flex items-center gap-2">
                                                <span>🏆</span>
                                                <span>Stage 4: The Final Cut &amp; Master GCS Export</span>
                                            </h2>
                                            <p className="text-xs text-gray-400 mt-1">
                                                Review your full 30–60s stitched master video, configure master audio track overlay, and export to Google Cloud Storage.
                                            </p>
                                        </div>

                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                            <div className="flex items-center justify-between">
                                                <span className="text-xs font-bold text-emerald-300">Stitched 30–60s Master Video Player</span>
                                                <span className="text-[11px] font-mono text-gray-400">Master: {masterTitle}.mp4</span>
                                            </div>
                                            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-gray-800 flex items-center justify-center max-w-4xl mx-auto">
                                                <video src={getDisplayableRefUrl(currentVideo)} controls className="w-full h-full object-contain" />
                                            </div>
                                        </div>

                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                            <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Master Audio Overlay &amp; GCS Export Settings</h3>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <div>
                                                    <label className="text-xs font-bold text-gray-300 block mb-1">Master Video Title:</label>
                                                    <input
                                                        type="text"
                                                        value={masterTitle}
                                                        onChange={(e) => setMasterTitle(e.target.value)}
                                                        placeholder="official_rap_battle_master"
                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono placeholder-gray-600 focus:outline-none focus:border-emerald-500"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="text-xs font-bold text-gray-300 block mb-1">Master Audio Overlay Path / URL:</label>
                                                    <input
                                                        type="text"
                                                        value={masterAudioUrl}
                                                        onChange={(e) => setMasterAudioUrl(e.target.value)}
                                                        placeholder="gs://my-bucket/master_beat.mp3 or local path"
                                                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white font-mono placeholder-gray-600 focus:outline-none focus:border-emerald-500"
                                                    />
                                                </div>
                                            </div>

                                            {stageSaveGcs && (
                                                <div className="bg-green-950/80 border border-green-500/80 rounded-xl p-4 text-xs text-green-300 font-mono break-all space-y-1">
                                                    <span className="font-bold text-green-200 block">✓ Master Export Successful!</span>
                                                    <div>Saved to GCS URI: <span className="underline">{stageSaveGcs}</span></div>
                                                </div>
                                            )}

                                            <div className="pt-2 flex justify-end">
                                                <button
                                                    type="button"
                                                    disabled={stageSaveLoading}
                                                    onClick={handleStageSaveFinal}
                                                    className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-black font-extrabold text-xs py-3 px-6 rounded-xl shadow-lg flex items-center gap-2 disabled:opacity-50"
                                                >
                                                    <span>🎬</span>
                                                    <span>{stageSaveLoading ? "Exporting Master..." : "Stitch & Export Final 30–60s Master to GCS"}</span>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎬 ACT 3: THE SCREENING ROOM & BRANCHING                  */}
                        {/* ========================================================= */}
                        {studioMode === "acts" && activeAct === 3 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-amber-950/40 to-purple-950/40 border border-amber-800/50 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
                                    <div>
                                        <div className="flex flex-wrap items-center gap-3">
                                            <h2 className="text-base font-bold text-amber-200 flex items-center gap-2">
                                                <span>🎬</span>
                                                <span>Act 3: The Screening Room &amp; Branching</span>
                                            </h2>
                                            {/* Generation Status Pill Badge */}
                                            {generationMode === "LIVE_OMNI_FLASH" ? (
                                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-green-950/90 text-green-400 border border-green-700/80 shadow-md">
                                                    <span>🟢</span>
                                                    <span>Live Gemini Omni Flash</span>
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-950/90 text-amber-400 border border-amber-700/80 shadow-md">
                                                    <span>🟠</span>
                                                    <span>Procedural Fallback Animation</span>
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-xs text-gray-400 mt-1">
                                            Review the rendered parody cut, inspect the version tree timeline, and apply conversational diffs.
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setActiveAct(2)}
                                        className="bg-gray-900 border border-gray-700 text-xs text-amber-300 px-3 py-1.5 rounded-lg hover:bg-gray-800"
                                    >
                                        🎛️ Adjust Storyboard Directing
                                    </button>
                                </div>

                                {/* Active Error Mitigation Banner */}
                                {lastError && (
                                    <div className="bg-red-950/40 border-2 border-red-500/70 rounded-2xl p-4 shadow-xl text-red-200 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2 font-bold text-red-300 text-xs uppercase tracking-wider">
                                                <span className="text-base">⚠️</span>
                                                <span>Active Error Mitigation Banner</span>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => setLastError(null)}
                                                className="text-red-400 hover:text-red-200 text-xs font-bold px-2 py-0.5 rounded border border-red-800/80 bg-red-950 hover:bg-red-900"
                                            >
                                                ✕ Dismiss
                                            </button>
                                        </div>
                                        <div className="bg-black/60 border border-red-900/80 rounded-xl p-3 text-xs font-mono text-red-300 break-words whitespace-pre-wrap">
                                            <span className="text-red-400 font-bold block mb-1">Gemini Omni Flash Error / Trace:</span>
                                            {lastError}
                                        </div>
                                        <p className="text-[11px] text-amber-300/90 font-medium flex items-center gap-1.5 pt-0.5">
                                            <span>🛡️</span>
                                            <span>Automated exponential backoff retries &amp; Developer API auth switch executed.</span>
                                        </p>
                                    </div>
                                )}

                                {/* GCS Export Success Banner */}
                                {savedGcsUri && (
                                    <div className="bg-green-950/60 border-2 border-green-500/70 rounded-2xl p-4 shadow-xl text-green-200 flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <span className="text-2xl">💾</span>
                                            <div>
                                                <h4 className="font-bold text-xs text-green-300 uppercase tracking-wider">Final Master Saved to GCS</h4>
                                                <p className="text-xs font-mono text-green-200/90 mt-0.5 break-all">{savedGcsUri}</p>
                                            </div>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => setSavedGcsUri(null)}
                                            className="text-green-400 hover:text-white text-xs font-bold px-2 py-1 rounded bg-green-900/60 border border-green-700"
                                        >
                                            ✕ Dismiss
                                        </button>
                                    </div>
                                )}

                                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                    {/* Left 8 Cols: Video Player, Action Toolbar, Prompt Viewer, & Delta Prompt */}
                                    <div className="lg:col-span-8 space-y-4">
                                        <div className="bg-black rounded-2xl border border-gray-800 overflow-hidden shadow-2xl relative">
                                            <video
                                                src={currentVideo}
                                                controls
                                                loop
                                                className="w-full aspect-video object-contain bg-black"
                                            />
                                            <div className="p-4 bg-gray-900/90 border-t border-gray-800 flex flex-wrap items-center justify-between gap-3">
                                                <div className="flex items-center space-x-2 text-xs">
                                                    <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
                                                    <span className="font-bold text-gray-300">Live Parody Cut</span>
                                                    <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-mono">
                                                        Turn: {parentTurnId || "None"}
                                                    </span>
                                                </div>
                                                <div className="flex items-center space-x-3">
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setSaveModalMode("clip");
                                                            setMasterTitle("active_clip_master");
                                                            setShowSaveModal(true);
                                                        }}
                                                        className="text-xs bg-amber-950/80 hover:bg-amber-900 text-amber-300 border border-amber-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
                                                    >
                                                        <span>💾</span>
                                                        <span>Save Active Clip to GCS</span>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            if (selectedClipUrls.length === 0 && history.length > 0) {
                                                                setSelectedClipUrls(history.map(h => h.videoUrl));
                                                            }
                                                            setShowStitchModal(true);
                                                        }}
                                                        className="text-xs bg-purple-950/80 hover:bg-purple-900 text-purple-300 border border-purple-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
                                                    >
                                                        <span>🎬</span>
                                                        <span>Stitch & Combine Selected Clips</span>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setSaveModalMode("master");
                                                            setMasterTitle("official_rap_battle_master");
                                                            setShowSaveModal(true);
                                                        }}
                                                        className="text-xs bg-amber-950/80 hover:bg-amber-900 text-amber-300 border border-amber-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
                                                    >
                                                        <span>🎬</span>
                                                        <span>Stitch & Save Master (30–60s) to GCS</span>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        disabled={extendLoading}
                                                        onClick={handleExtendScene}
                                                        className="text-xs bg-purple-950/80 hover:bg-purple-900 text-purple-300 border border-purple-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition disabled:opacity-50"
                                                    >
                                                        <span>➕</span>
                                                        <span>{extendLoading ? "Extending..." : "Extend Video / Next Scene"}</span>
                                                    </button>
                                                    <a
                                                        href={currentVideo}
                                                        download="omnimash_parody_cut.mp4"
                                                        className="text-xs text-purple-400 hover:text-purple-300 font-bold flex items-center gap-1"
                                                    >
                                                        <span>⬇️ Download MP4</span>
                                                    </a>
                                                </div>
                                            </div>
                                        </div>

                                        {/* 🧠 Final Generation Prompt (Active Version) */}
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-3">
                                            <div className="flex items-center justify-between">
                                                <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                                                    <span>🧠</span>
                                                    <span>Final Generation Prompt (Active Version)</span>
                                                </h3>
                                                <span className="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800 font-mono">
                                                    Gemini Omni Directives
                                                </span>
                                            </div>
                                            <pre className="bg-gray-950 border border-gray-800 rounded-xl p-3 text-[11px] text-gray-300 font-mono whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar leading-relaxed">
                                                {rawCompiledPrompt || "No compiled prompt available for active version."}
                                            </pre>
                                        </div>

                                        {/* Conversational Delta Chat Bar */}
                                        <form onSubmit={handleGenerate} className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl flex gap-3 items-center">
                                            <div className="text-xl">💬</div>
                                            <input
                                                type="text"
                                                value={deltaPrompt}
                                                onChange={(e) => setDeltaPrompt(e.target.value)}
                                                placeholder="Direct the scene (e.g. Make Role A's glasses darker and add laser smoke)..."
                                                className="flex-1 bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 font-mono"
                                            />
                                            <button
                                                type="submit"
                                                disabled={loading || !deltaPrompt}
                                                className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 text-black font-bold text-xs py-3 px-5 rounded-xl shadow flex items-center gap-2 transition disabled:opacity-50"
                                            >
                                                <span>⚡</span>
                                                <span>{loading ? "Applying..." : "Apply Delta Edit"}</span>
                                            </button>
                                        </form>
                                    </div>

                                    {/* Right 4 Cols: Chronological Version Tree */}
                                    <div className="lg:col-span-4 bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col h-[640px]">
                                        <div className="flex items-center justify-between mb-4 border-b border-gray-800 pb-3">
                                            <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                                                <span>🍰</span>
                                                <span>Version Tree &amp; Timeline</span>
                                            </h3>
                                            <span className="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800">
                                                Chronological Edit History
                                            </span>
                                        </div>

                                        <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar">
                                            {history.map((turn, i) => (
                                                <div
                                                    key={i}
                                                    onClick={() => {
                                                        setCurrentVideo(turn.videoUrl);
                                                        setParentTurnId(turn.turnId);
                                                        if (turn.rawCompiledPrompt) {
                                                            setRawCompiledPrompt(turn.rawCompiledPrompt);
                                                        }
                                                    }}
                                                    className={`p-3 rounded-xl border text-left cursor-pointer transition ${
                                                        parentTurnId === turn.turnId
                                                            ? "bg-amber-950/40 border-amber-500 shadow-md"
                                                            : "bg-gray-950/80 border-gray-800 hover:border-gray-700"
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between text-[10px] font-mono text-gray-400 mb-1.5">
                                                        <span>Turn #{i + 1} ({turn.turnId})</span>
                                                        <span className="bg-gray-800 px-1.5 py-0.5 rounded text-gray-300">{turn.status}</span>
                                                    </div>
                                                    <p className="text-xs font-bold text-gray-200 mb-2">{turn.prompt}</p>
                                                    <div className="space-y-1.5 text-[10px] font-mono">
                                                        <div className="bg-black/60 p-1.5 rounded border border-gray-800/80 text-pink-300">
                                                            <span className="font-bold">🔒 Lock:</span> {turn.lock}
                                                        </div>
                                                        <div className="bg-black/60 p-1.5 rounded border border-gray-800/80 text-purple-300">
                                                            <span className="font-bold">🎯 Diff:</span> {turn.diff}
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                            {history.length === 0 && (
                                                <div className="text-xs text-gray-500 italic p-4 text-center border border-dashed border-gray-800 rounded-xl">
                                                    No turn history yet. Generate your first video to start building the version tree.
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Screenplay & Director's Notes Master Modal */}
                        {showScreenplayModal && (
                            <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
                                <div className="bg-gray-900 border border-amber-500/60 rounded-3xl p-6 max-w-3xl w-full shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
                                    <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-xl">📜</span>
                                            <h3 className="text-base font-extrabold text-amber-300">Master Timecoded Screenplay &amp; Director's Notes</h3>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => setShowScreenplayModal(false)}
                                            className="text-gray-400 hover:text-white text-lg font-black px-2 py-1"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                    <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
                                        <div className="bg-black/60 border border-amber-900/60 rounded-xl p-3 text-xs text-amber-200 font-mono">
                                            <span className="font-bold text-amber-400">💡 Tip:</span> You can edit your master screenplay below at any time, then click <span className="font-bold text-orange-400">"Re-expand Screenplay to Shots"</span> to re-sync all shot cards.
                                        </div>
                                        <textarea
                                            rows={12}
                                            value={screenplayScript}
                                            onChange={(e) => setScreenplayScript(e.target.value)}
                                            placeholder={`[DIRECTOR'S NOTES]\n- Tone: High-energy 90s Cel-Shaded Anime Rap Battle\n- Relational Dynamic: Friendly rivalry between Dumble Dior and Snape Dawg\n\n# Supports both Character: (Action) "Dialogue" AND [0-3s] Timecoded Script:\n\nDumble Dior: (Steps up to the mic under glowing neon lights. Audio: Heavy 808 trap beat.) "Welcome to Dripwarts, turn the beat up!"\n\nSnape Dawg: (Drops a heavy 808 trap beat. Audio: Crisp snare trills and sub-bass drop.) "Potions class is in session, no cap!"\n\n[6-10s] Action: Both perform synchronized rap battle climax amidst stage smoke and purple rim lights. Audio: Climax 808 beat drop. Dialogue: Both: "Trap or Die!"`}
                                            className="w-full bg-gray-950 border border-gray-800 rounded-xl p-4 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 font-mono"
                                        />
                                    </div>
                                    <div className="flex items-center justify-between border-t border-gray-800 pt-3">
                                        <button
                                            type="button"
                                            onClick={() => setShowScreenplayModal(false)}
                                            className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-bold px-4 py-2 rounded-xl transition"
                                        >
                                            Close
                                        </button>
                                        <button
                                            type="button"
                                            disabled={expandLoading}
                                            onClick={() => {
                                                setShowScreenplayModal(false);
                                                handleExpandStoryboard();
                                            }}
                                            className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-black font-extrabold text-xs px-5 py-2.5 rounded-xl shadow-lg transition flex items-center gap-1.5"
                                        >
                                            <span>🚀</span>
                                            <span>{expandLoading ? "Re-expanding..." : "Re-expand Screenplay to Shots"}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Gemini Omni Flash Prompt Best Practices & Official Examples Modal */}
                        {showBestPracticesModal && (
                            <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
                                <div className="bg-gray-900 border-2 border-purple-500/80 rounded-2xl max-w-3xl w-full p-6 shadow-2xl relative max-h-[85vh] flex flex-col">
                                    <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4">
                                        <div className="flex items-center space-x-3">
                                            <span className="text-2xl">✨</span>
                                            <div>
                                                <h3 className="font-bold text-base text-purple-200">Gemini Omni Flash Prompt Best Practices</h3>
                                                <p className="text-xs text-gray-400">Official Multimodal 4-Block Structure Guidelines &amp; Reference Examples</p>
                                            </div>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => setShowBestPracticesModal(false)}
                                            className="text-gray-400 hover:text-white text-lg font-bold px-2 py-1"
                                        >
                                            ✕
                                        </button>
                                    </div>

                                    <div className="overflow-y-auto custom-scrollbar space-y-6 pr-2 flex-1 text-xs text-gray-300">
                                        {/* Core Guidelines */}
                                        <div className="bg-purple-950/40 border border-purple-800/60 rounded-xl p-4 space-y-2">
                                            <h4 className="font-bold text-purple-300 uppercase tracking-wider text-[11px]">Core Multimodal Standards</h4>
                                            <ul className="list-disc list-inside space-y-1.5 text-gray-300 text-[11px]">
                                                <li><strong>Four-Block Structure:</strong> Always format prompt payloads into four clear blocks: <code>### INPUT ROLES</code>, <code>### CHARACTER PROFILES</code>, <code>### SCENE INSTRUCTIONS</code>, and <code>### TIMELINE</code>.</li>
                                                <li><strong>Image Roles:</strong> Explicitly assign reference image role tags (<code>Character Reference</code>, <code>Product Reference</code>, <code>Starting Frame</code>, <code>Style Reference</code>) to preserve visual assets.</li>
                                                <li><strong>Qualitative Mixing:</strong> Use qualitative audio descriptors (e.g., <em>"foreground voiceover dominant, background beat ducked"</em>) instead of raw numeric decibels/percentages.</li>
                                                <li><strong>Off-Screen Narrator:</strong> Use the <code>🎙️ Off-Screen Narrator</code> toggle or <code>Narrator (VO): "..."</code> formatting for voiceovers without animating character mouth movement.</li>
                                            </ul>
                                        </div>

                                        {/* Example 1: Cyberpunk Commercial */}
                                        <div className="bg-gray-950 border border-gray-800 rounded-xl p-4 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <span className="font-bold text-pink-400 text-xs">Example 1: Cyberpunk Commercial (Product Reference + Starting Frame)</span>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        const examplePrompt = `### INPUT ROLES\n- Image #1 (Starting Frame): gs://my-bucket/cyber_alley.jpg\n- Role A (Product Reference): gs://my-bucket/energy_drink_can.jpg\n\n### CHARACTER PROFILES\n- Role A (Cyber Neon Can): Sleek glowing cybernetic energy drink can with holographic cyan labeling [Product Reference]\n\n### SCENE INSTRUCTIONS\nCamera & Lighting: In a single continuous shot. No scene cuts. Anamorphic lens, rainy neon reflections, purple and teal synthwave color grading.\nEnvironment: Rainy futuristic cyberpunk Tokyo alleyway with floating digital billboards.\nAudio: Sound design: Pulsing synthwave synth lead with ambient rain and distant sirens.\n\n### TIMELINE\n[0-3s] Action: Camera pans down to glowing Cyber Neon Can resting on wet asphalt. Audio: Heavy analog synth riser.\n[3-6s] Action: Holographic energy pulses radiate from the can label. Audio: Resonant bass drop.\n[6-10s] Action: Neon sign behind can flares in bright cyan burst. Audio: Synthwave crescendo.`;
                                                        setConcept("Cyberpunk energy drink commercial in rainy neon Tokyo alleyway");
                                                        setScreenplayScript(examplePrompt);
                                                        setShowBestPracticesModal(false);
                                                    }}
                                                    className="text-[10px] bg-pink-950 hover:bg-pink-900 border border-pink-700 text-pink-300 px-2 py-1 rounded font-bold"
                                                >
                                                    Load Example
                                                </button>
                                            </div>
                                            <pre className="bg-black/90 p-3 rounded-lg border border-gray-800 text-[10px] font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
{`### INPUT ROLES
- Image #1 (Starting Frame): gs://my-bucket/cyber_alley.jpg
- Role A (Product Reference): gs://my-bucket/energy_drink_can.jpg

### CHARACTER PROFILES
- Role A (Cyber Neon Can): Sleek glowing cybernetic energy drink can with holographic cyan labeling

### SCENE INSTRUCTIONS
Camera & Lighting: In a single continuous shot. No scene cuts. Anamorphic lens, rainy neon reflections.
Environment: Rainy futuristic cyberpunk Tokyo alleyway with floating digital billboards.
Audio: Sound design: Pulsing synthwave synth lead with ambient rain and distant sirens.

### TIMELINE
[0-3s] Action: Camera pans down to glowing Cyber Neon Can resting on wet asphalt.
[3-6s] Action: Holographic energy pulses radiate from the can label.
[6-10s] Action: Neon sign behind can flares in bright cyan burst.`}
                                            </pre>
                                        </div>

                                        {/* Example 2: Noir Detective */}
                                        <div className="bg-gray-950 border border-gray-800 rounded-xl p-4 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <span className="font-bold text-amber-400 text-xs">Example 2: Noir Detective (Off-Screen Narrator VO)</span>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        const examplePrompt = `### INPUT ROLES\n- Role A (Character Reference): gs://my-bucket/detective_noir.jpg\n\n### CHARACTER PROFILES\n- Role A (Gritty Detective): World-weary detective in trench coat and fedora [🎙️ Off-Screen Narrator]\n\n### SCENE INSTRUCTIONS\nCamera & Lighting: In a single continuous shot. No scene cuts. High-contrast black and white noir film lighting with harsh Venetian blind shadows.\nEnvironment: Dimly lit 1940s office with rain beating against windowpanes.\nAudio: Sound design: Foreground spoken voiceover is dominant, crystal-clear, and front-of-mix. Background beat (instrumental melancholic saxophone and jazz piano) is subtly ducked in the background beneath dialogue.\nVoiceover: Narrator (VO) says: "Rain hit the pavement like a slow drumbeat. Another night in this city."\n\n### TIMELINE\n[0-3s] Action: Detective stands by window watching rain trickle down glass. Audio: Foreground voiceover dominant. Dialogue: Narrator (VO) says: "Rain hit the pavement like a slow drumbeat."\n[3-6s] Action: Detective takes a long drag from cigarette, smoke curling in light beam. Audio: Soft saxophone solo.\n[6-10s] Action: Silhouette of detective turning back to shadow-covered desk. Audio: Soft jazz piano decay.`;
                                                        setConcept("1940s Film Noir Detective Voiceover Monologue");
                                                        setScreenplayScript(examplePrompt);
                                                        setShowBestPracticesModal(false);
                                                    }}
                                                    className="text-[10px] bg-amber-950 hover:bg-amber-900 border border-amber-700 text-amber-300 px-2 py-1 rounded font-bold"
                                                >
                                                    Load Example
                                                </button>
                                            </div>
                                            <pre className="bg-black/90 p-3 rounded-lg border border-gray-800 text-[10px] font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
{`### INPUT ROLES
- Role A (Character Reference): gs://my-bucket/detective_noir.jpg

### CHARACTER PROFILES
- Role A (Gritty Detective): World-weary detective in trench coat [🎙️ Off-Screen Narrator]

### SCENE INSTRUCTIONS
Camera & Lighting: High-contrast black and white noir film lighting with harsh shadow lines.
Environment: Dimly lit 1940s office with rain beating against windowpanes.
Audio: Sound design: Foreground spoken voiceover is dominant. Background beat (instrumental saxophone) is subtly ducked in the background beneath dialogue.
Voiceover: Narrator (VO) says: "Rain hit the pavement like a slow drumbeat. Another night in this city."

### TIMELINE
[0-3s] Action: Detective stands by window watching rain. Audio: Foreground voiceover dominant. Dialogue: Narrator (VO): "Rain hit the pavement like a slow drumbeat."
[3-6s] Action: Detective takes drag from cigarette, smoke curling in light beam.
[6-10s] Action: Silhouette of detective turning back to desk.`}
                                            </pre>
                                        </div>

                                        {/* Example 3: Anime Rap Battle */}
                                        <div className="bg-gray-950 border border-gray-800 rounded-xl p-4 space-y-2">
                                            <div className="flex items-center justify-between">
                                                <span className="font-bold text-purple-400 text-xs">Example 3: Anime Rap Battle (Multi-Character Clash)</span>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        const examplePrompt = `### INPUT ROLES\n- Role A (Character Reference): gs://my-bucket/harry.jpg\n- Role B (Character Reference): gs://my-bucket/draco.jpg\n\n### CHARACTER PROFILES\n- Role A (Spectacled Wizard Bruv): Young wizard with round wire-rim glasses and red Gucci tracksuit [Style: Red Gucci Tracksuit, Cartier Glasses]\n- Role B (Platinum Rival Blood): Pale blonde rival with slicked-back platinum hair and diamond iced-out chain [Style: Diamond Chain, Silver Robes]\n\n### SCENE INSTRUCTIONS\nCamera & Lighting: In a single continuous shot. No scene cuts. Low-angle 90s fisheye tracking shot with green and purple neon rim lights.\nEnvironment: Gothic Hogwarts courtyard lit by neon stage lights and smoky haze.\nAudio: Sound design: 140 BPM Heavy 808 Trap beat ducked beneath high-energy rap dialogue.\nDialogue between subjects: Spectacled Wizard Bruv: "I been cooking potions since first year!" / Platinum Rival Blood: "This is Trap or Die, Potter!"\n\n### TIMELINE\n[0-3s] Action: Spectacled Wizard Bruv steps forward rapping into microphone wand. Audio: Heavy 808 trap intro. Dialogue: Spectacled Wizard Bruv: "I been cooking potions since first year!"\n[3-6s] Action: Platinum Rival Blood steps from shadows with diamond chain flashing. Audio: Sub-bass resonance. Dialogue: Platinum Rival Blood: "This is Trap or Die, Potter!"\n[6-10s] Action: Both rivals lock eyes as stage lights flare and crowd cheers. Audio: Full trap beat drop.`;
                                                        setConcept("Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style");
                                                        setScreenplayScript(examplePrompt);
                                                        setShowBestPracticesModal(false);
                                                    }}
                                                    className="text-[10px] bg-purple-950 hover:bg-purple-900 border border-purple-700 text-purple-300 px-2 py-1 rounded font-bold"
                                                >
                                                    Load Example
                                                </button>
                                            </div>
                                            <pre className="bg-black/90 p-3 rounded-lg border border-gray-800 text-[10px] font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
{`### INPUT ROLES
- Role A (Character Reference): gs://my-bucket/harry.jpg
- Role B (Character Reference): gs://my-bucket/draco.jpg

### CHARACTER PROFILES
- Role A (Spectacled Wizard Bruv): Young wizard with round glasses and red tracksuit
- Role B (Platinum Rival Blood): Pale blonde rival with slicked platinum hair and diamond chain

### SCENE INSTRUCTIONS
Camera & Lighting: Low-angle 90s fisheye tracking shot with green and purple neon rim lights.
Environment: Gothic Hogwarts courtyard lit by neon stage lights and smoky haze.
Audio: Sound design: 140 BPM Heavy 808 Trap beat ducked beneath high-energy rap dialogue.

### TIMELINE
[0-3s] Action: Spectacled Wizard Bruv steps forward rapping. Audio: Heavy 808 trap intro. Dialogue: Spectacled Wizard Bruv: "I been cooking potions!"
[3-6s] Action: Platinum Rival Blood steps from shadows with diamond chain. Dialogue: Platinum Rival Blood: "Trap or Die!"
[6-10s] Action: Both rivals lock eyes as stage lights flare and crowd cheers.`}
                                            </pre>
                                        </div>
                                    </div>

                                    <div className="pt-4 border-t border-gray-800 flex justify-end">
                                        <button
                                            type="button"
                                            onClick={() => setShowBestPracticesModal(false)}
                                            className="bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs py-2 px-5 rounded-xl shadow"
                                        >
                                            Close Best Practices
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </main>
                </div>
            );
        }

        class GlobalErrorBoundary extends React.Component {
            constructor(props) {
                super(props);
                this.state = { hasError: false, error: null };
            }
            static getDerivedStateFromError(error) {
                return { hasError: true, error };
            }
            componentDidCatch(error, errorInfo) {
                console.error("UI Rendering Error Caught:", error, errorInfo);
            }
            render() {
                if (this.state.hasError) {
                    return (
                        <div className="min-h-screen bg-gray-950 text-white p-8 flex flex-col items-center justify-center">
                            <div className="max-w-2xl w-full bg-gray-900 border border-red-800 rounded-3xl p-8 shadow-2xl space-y-6 text-center">
                                <span className="text-5xl block">⚠️</span>
                                <h1 className="text-2xl font-black text-red-400">UI Rendering Error Caught</h1>
                                <p className="text-sm text-gray-300">
                                    A rendering exception occurred in the workstation. The Error Boundary caught it safely without crashing your browser session.
                                </p>
                                <div className="bg-black/80 border border-red-900/60 rounded-xl p-4 text-left overflow-x-auto text-xs font-mono text-red-300 max-h-48">
                                    {this.state.error && this.state.error.toString()}
                                </div>
                                <button
                                    onClick={() => {
                                        this.setState({ hasError: false, error: null });
                                        if ("caches" in window) {
                                            caches.keys().then((names) => {
                                                names.forEach((name) => caches.delete(name));
                                            });
                                        }
                                        window.location.href = window.location.origin + window.location.pathname + "?v=" + Date.now();
                                    }}
                                    className="px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-extrabold text-sm rounded-xl shadow-lg transition"
                                >
                                    🔄 Clear Cache &amp; Hard Reload Workstation
                                </button>
                            </div>
                        </div>
                    );
                }
                return this.props.children;
            }
        }

        ReactDOM.createRoot(document.getElementById("__next")).render(
            <GlobalErrorBoundary>
                <OmniMashApp />
            </GlobalErrorBoundary>
        );
    </script>
</body>
</html>
"""


def create_app(mock_mode: bool | None = None) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0")
    is_mock = (
        mock_mode
        if mock_mode is not None
        else (os.environ.get("MOCK_MODE", "false").lower() in ("true", "1"))
    )
    agent = OmniMashAgent(mock_mode=is_mock)

    static_dir = os.path.join(os.getcwd(), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    from omnimash.engine.omni_client import ensure_rendered_video

    ensure_rendered_video(
        "/static/rendered/mock.mp4",
        prompt="Trapwarts trailer",
    )

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        return HTMLResponse(content=UI_HTML, headers=headers)

    @app.post("/api/deconstruct-concept", response_model=DeconstructResponse)
    def deconstruct_concept(req: ConceptDeconstructRequest) -> DeconstructResponse:
        tags = agent.deconstruct_concept(req.concept)
        return DeconstructResponse(
            characters=[
                CharacterRoleModel(
                    role_id=c.role_id,
                    name=c.name,
                    description=c.description,
                    reference_url=c.reference_url,
                    aesthetic_tags=c.aesthetic_tags,
                    voice_style=c.voice_style,
                    voice_profile=c.voice_profile,
                    wardrobe=getattr(c, "wardrobe", ""),
                    image_role=getattr(c, "image_role", "Character Reference"),
                    is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                )
                for c in tags.characters
            ],
            aesthetic_tags=tags.aesthetic_tags,
            environment_tag=tags.environment_tag,
            camera_lighting_tag=tags.camera_lighting_tag,
            audio_beat=tags.audio_beat,
            vocal_delivery=tags.vocal_delivery,
        )

    @app.post("/api/generate", response_model=GenerateResponse)
    @app.post("/api/diff", response_model=GenerateResponse)
    def generate_video(req: GenerateRequest) -> GenerateResponse:
        sanitized_prompt = sanitize_real_names(req.prompt) if req.prompt else ""
        is_edit = bool(req.parent_turn_id and not (req.scenes or req.concept or req.shot_directive))
        compiled_override_val = req.compiled_override

        if req.parent_turn_id and (req.shot_directive or req.scenes):
            char_objs: list[CharacterRole] = []
            if req.characters:
                for c in req.characters:
                    if isinstance(c, CharacterRole):
                        char_objs.append(c)
                    elif isinstance(c, dict):
                        char_objs.append(
                            CharacterRole(
                                role_id=c.get("role_id", ""),
                                name=sanitize_real_names(c.get("name", "")),
                                description=sanitize_real_names(c.get("description", "")),
                                reference_url=c.get("reference_url"),
                                aesthetic_tags=[sanitize_real_names(t) for t in c.get("aesthetic_tags", [])],
                                voice_style=sanitize_real_names(c.get("voice_style", "")),
                                voice_profile=sanitize_real_names(c.get("voice_profile", "")),
                                image_role=c.get("image_role", "Character Reference"),
                                is_offscreen_narrator=c.get("is_offscreen_narrator", False),
                            )
                        )
                    elif hasattr(c, "model_dump"):
                        cd = c.model_dump()
                        char_objs.append(
                            CharacterRole(
                                role_id=cd.get("role_id", ""),
                                name=sanitize_real_names(cd.get("name", "")),
                                description=sanitize_real_names(cd.get("description", "")),
                                reference_url=cd.get("reference_url"),
                                aesthetic_tags=[sanitize_real_names(t) for t in cd.get("aesthetic_tags", [])],
                                voice_style=sanitize_real_names(cd.get("voice_style", "")),
                                voice_profile=sanitize_real_names(cd.get("voice_profile", "")),
                                image_role=cd.get("image_role", "Character Reference"),
                                is_offscreen_narrator=cd.get("is_offscreen_narrator", False),
                            )
                        )
                    elif hasattr(c, "role_id"):
                        char_objs.append(
                            CharacterRole(
                                role_id=getattr(c, "role_id", ""),
                                name=sanitize_real_names(getattr(c, "name", "")),
                                description=sanitize_real_names(getattr(c, "description", "")),
                                reference_url=getattr(c, "reference_url", None),
                                aesthetic_tags=[sanitize_real_names(t) for t in getattr(c, "aesthetic_tags", [])],
                                voice_style=sanitize_real_names(getattr(c, "voice_style", "")),
                                voice_profile=sanitize_real_names(getattr(c, "voice_profile", "")),
                                image_role=getattr(c, "image_role", "Character Reference"),
                                is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                            )
                        )

            scene_objs: list[SceneDirective] = []
            if req.scenes:
                for s in req.scenes:
                    if isinstance(s, SceneDirective):
                        scene_objs.append(s)
                    elif isinstance(s, dict):
                        sp_script = s.get("screenplay_text") or s.get("screenplay_script")
                        scene_objs.append(
                            SceneDirective(
                                scene_number=s.get("scene_number", 0),
                                active_roles=s.get("active_roles", []),
                                action=s.get("action", ""),
                                dialogue=s.get("dialogue", ""),
                                screenplay_text=sp_script if isinstance(sp_script, str) else None,
                                audio_cues=s.get("audio_cues", ""),
                            )
                        )
            elif req.shot_directive:
                active_roles_list = [c.role_id or c.name for c in char_objs if c.role_id or c.name]
                if not active_roles_list:
                    active_roles_list = ["Role A"]
                scene_objs.append(
                    SceneDirective(
                        scene_number=1,
                        active_roles=active_roles_list,
                        action=sanitize_real_names(req.shot_directive),
                    )
                )

            if not compiled_override_val:
                compiled_override_val = agent.taxonomy.compiler.compile_storyboard(
                    concept=req.concept or sanitized_prompt,
                    characters=char_objs,
                    scenes=scene_objs,
                    aesthetic_tags=req.aesthetic_tags,
                    environment_tag=req.environment_tag,
                    audio_beat=req.audio_stem,
                    vocal_delivery=req.vocal_delivery,
                    edit_instruction=req.prompt,
                )

        agent_turn = agent.process_user_turn(
            user_id=req.user_id,
            project_id=req.project_id,
            prompt=sanitized_prompt,
            clip_index=req.clip_index,
            parent_turn_id=req.parent_turn_id,
            is_conversational_edit=is_edit,
            reference_url=req.reference_url,
            audio_stem=req.audio_stem,
            voiceover=req.voiceover,
            is_silent=req.is_silent,
            on_screen_text=req.on_screen_text,
            compiled_override=compiled_override_val,
            session_name=req.session_name,
            concept=req.concept,
            characters=req.characters,
            scenes=req.scenes,
            aesthetic_tags=req.aesthetic_tags,
            environment_tag=req.environment_tag,
            vocal_delivery=req.vocal_delivery,
            optimize_prompt=req.optimize_prompt,
        )
        return GenerateResponse(
            success=agent_turn.success,
            status=agent_turn.status_event,
            video_url=agent_turn.video_url,
            turn_id=agent_turn.turn_id,
            depth=agent_turn.depth,
            error=agent_turn.error_message,
            generation_mode=agent_turn.generation_mode,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt,
            reference_analysis=agent_turn.reference_analysis,
        )

    @app.post("/api/commit", response_model=GenerateResponse)
    def commit_and_branch(req: CommitRequest) -> GenerateResponse:
        sanitized_prompt = sanitize_real_names(req.next_prompt) if req.next_prompt else ""
        agent_turn = agent.commit_and_branch(
            user_id=req.user_id,
            project_id=req.project_id,
            turn_id=req.turn_id,
            prompt=sanitized_prompt,
            session_name=req.session_name,
        )
        return GenerateResponse(
            success=agent_turn.success,
            status=agent_turn.status_event,
            video_url=agent_turn.video_url,
            turn_id=agent_turn.turn_id,
            depth=agent_turn.depth,
            error=agent_turn.error_message,
            generation_mode=agent_turn.generation_mode,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt,
            reference_analysis=agent_turn.reference_analysis,
        )

    @app.post("/api/save-final", response_model=SaveFinalResponse)
    def save_final(req: SaveFinalRequest) -> SaveFinalResponse:
        audio = req.master_audio_path or req.master_audio_url
        if req.is_single_clip:
            pub_url, gcs_uri = agent.storage.save_final_master(
                session_id=req.session_name,
                source_rel_path=req.video_url,
                master_title=req.master_title,
            )
        else:
            pub_url, gcs_uri = agent.save_final_master(
                session_name=req.session_name,
                video_url=req.video_url,
                master_title=req.master_title,
                master_audio_path=audio,
            )
        return SaveFinalResponse(
            success=True,
            gcs_uri=gcs_uri,
            video_url=pub_url,
            message=f"Final master successfully saved to {gcs_uri}",
        )

    @app.post("/api/upload")
    async def upload_media_file(file: UploadFile = File(...)):
        """Uploads a local media file (audio MP3, WAV, image, etc.) to storage and returns accessible URL."""
        try:
            content = await file.read()
            ext = os.path.splitext(file.filename or "file")[1] or ".bin"
            filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"

            if agent.storage._bucket and not agent.storage.mock_mode:
                gcs_uri = agent.storage.upload_bytes(
                    content,
                    f"uploads/{filename}",
                    content_type=file.content_type or "application/octet-stream",
                )
                return {"success": True, "url": gcs_uri, "filename": file.filename}
            else:
                local_dir = os.path.join(os.getcwd(), "static", "uploads")
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, filename)
                with open(local_path, "wb") as f:
                    f.write(content)
                return {
                    "success": True,
                    "url": f"/static/uploads/{filename}",
                    "filename": file.filename,
                }
        except Exception as exc:
            logger.error("File upload failed: %s", exc)
            return JSONResponse(
                status_code=500, content={"success": False, "error": str(exc)}
            )

    @app.post("/api/storyboard/expand", response_model=StoryboardExpandResponse)
    def expand_storyboard(req: StoryboardExpandRequest) -> StoryboardExpandResponse:
        char_objs: list[CharacterRole] = []
        if req.characters:
            for c in req.characters:
                if isinstance(c, CharacterRole):
                    char_objs.append(c)
                elif isinstance(c, CharacterRoleModel):
                    char_objs.append(
                        CharacterRole(
                            role_id=c.role_id,
                            name=c.name,
                            description=c.description,
                            reference_url=c.reference_url,
                            aesthetic_tags=c.aesthetic_tags,
                            voice_style=c.voice_style,
                            voice_profile=c.voice_profile,
                            wardrobe=c.wardrobe,
                            image_role=c.image_role,
                            is_offscreen_narrator=c.is_offscreen_narrator,
                        )
                    )
                elif isinstance(c, dict):
                    char_objs.append(
                        CharacterRole(
                            role_id=c.get("role_id", ""),
                            name=c.get("name", ""),
                            description=c.get("description", ""),
                            reference_url=c.get("reference_url"),
                            aesthetic_tags=c.get("aesthetic_tags", []),
                            voice_style=c.get("voice_style", ""),
                            voice_profile=c.get("voice_profile", ""),
                            wardrobe=c.get("wardrobe", ""),
                            image_role=c.get("image_role", "Character Reference"),
                            is_offscreen_narrator=c.get("is_offscreen_narrator", False),
                        )
                    )
                elif hasattr(c, "model_dump"):
                    cd = c.model_dump()
                    char_objs.append(
                        CharacterRole(
                            role_id=cd.get("role_id", ""),
                            name=cd.get("name", ""),
                            description=cd.get("description", ""),
                            reference_url=cd.get("reference_url"),
                            aesthetic_tags=cd.get("aesthetic_tags", []),
                            voice_style=cd.get("voice_style", ""),
                            voice_profile=cd.get("voice_profile", ""),
                            wardrobe=cd.get("wardrobe", ""),
                            image_role=cd.get("image_role", "Character Reference"),
                            is_offscreen_narrator=cd.get("is_offscreen_narrator", False),
                        )
                    )

        shots = agent.storyboard_agent.expand_vision(
            concept=req.concept,
            style_tone=req.style_tone,
            target_duration=req.target_duration,
            characters=char_objs if char_objs else None,
            screenplay_script=req.screenplay_script,
        )
        return StoryboardExpandResponse(
            shots=[
                StoryboardShotModel(
                    shot_index=s.shot_index,
                    duration_seconds=s.duration_seconds,
                    action=s.action,
                    location=s.location,
                    style_lighting=s.style_lighting,
                    framing_motion=s.framing_motion,
                    audio=s.audio,
                    dialogue=getattr(s, "dialogue", ""),
                    summary=s.summary,
                    keyframe_image_url=getattr(s, "keyframe_image_url", ""),
                    video_url=getattr(s, "video_url", ""),
                    narrative_stage=getattr(s, "narrative_stage", "Rising Action"),
                    preceding_context=getattr(s, "preceding_context", ""),
                    camera_transition=getattr(s, "camera_transition", "Continuous match cut"),
                    character_continuity=getattr(s, "character_continuity", "Maintain subject outfit, posture, and facial expression from preceding shot"),
                )
                for s in shots
            ]
        )

    @app.post(
        "/api/storyboard/keyframe-image", response_model=KeyframeImageResponse
    )
    def generate_keyframe_image(
        req: KeyframeImageRequest,
    ) -> KeyframeImageResponse:
        prompt_parts = [p for p in [req.action, req.location] if p]
        prompt = (
            ", ".join(prompt_parts)
            if prompt_parts
            else (req.summary or f"Shot {req.shot_index}")
        )
        ref_urls: list[str] = list(req.reference_image_urls or [])
        if req.characters:
            for c in req.characters:
                ref = c.get("reference_url") if isinstance(c, dict) else getattr(c, "reference_url", None)
                if ref and ref not in ref_urls:
                    ref_urls.append(ref)

        image_url = agent.omni_client.generate_keyframe_image(
            prompt,
            style_tone=req.style_lighting,
            reference_image_urls=ref_urls,
            characters=req.characters,
            anchor_keyframe_url=req.anchor_keyframe_url,
        )
        return KeyframeImageResponse(success=True, keyframe_image_url=image_url)

    def parse_shot_directive_if_needed(req: GenerateShotRequest) -> tuple[str, str, str, str, str, str]:
        action = req.action or ""
        dialogue = req.dialogue or ""
        audio = req.audio or req.audio_stem or ""
        location = req.location or ""
        style_lighting = req.style_lighting or ""
        framing_motion = req.framing_motion or ""

        if req.shot_directive and req.shot_directive.strip():
            sd = req.shot_directive.strip()
            if not action:
                match_act = re.search(r"-\s*Action\s*/\s*Subject:\s*(.*)", sd, re.IGNORECASE)
                if match_act and match_act.group(1).strip():
                    action = match_act.group(1).strip()
                elif not sd.startswith("[SHOT DIRECTIVE") and not sd.startswith("- "):
                    action = sd
            if not dialogue:
                match_diag = re.search(r"-\s*(?:Dialogue\s*/\s*Text\s*Overlay|Dialogue|Voiceover):\s*(.*)", sd, re.IGNORECASE)
                if match_diag and match_diag.group(1).strip():
                    dialogue = match_diag.group(1).strip()
                    if (dialogue.startswith('"') and dialogue.endswith('"')) or (dialogue.startswith("'") and dialogue.endswith("'")):
                        dialogue = dialogue[1:-1].strip()
            if not audio:
                match_aud = re.search(r"-\s*Audio\s*Soundscape:\s*(.*)", sd, re.IGNORECASE)
                if match_aud and match_aud.group(1).strip():
                    audio = match_aud.group(1).strip()
            if not location:
                match_loc = re.search(r"-\s*Location:\s*(.*)", sd, re.IGNORECASE)
                if match_loc and match_loc.group(1).strip():
                    location = match_loc.group(1).strip()
            if not style_lighting:
                match_style = re.search(r"-\s*Style\s*&\s*Lighting:\s*(.*)", sd, re.IGNORECASE)
                if match_style and match_style.group(1).strip():
                    style_lighting = match_style.group(1).strip()
            if not framing_motion:
                match_frame = re.search(r"-\s*Framing\s*&\s*Motion:\s*(.*)", sd, re.IGNORECASE)
                if match_frame and match_frame.group(1).strip():
                    framing_motion = match_frame.group(1).strip()

        if not action:
            action = f"Shot {req.shot_index} action"

        return action, dialogue, audio, location, style_lighting, framing_motion

    @app.post("/api/generate-shot", response_model=GenerateShotResponse)
    def generate_shot(req: GenerateShotRequest) -> GenerateShotResponse:
        sanitized_directive = sanitize_real_names(req.shot_directive)
        keyframe_url = req.keyframe_image_url

        action_val, dialogue_val, audio_val, location_val, style_lighting_val, framing_motion_val = parse_shot_directive_if_needed(req)
        audio_stem_val = audio_val or req.audio_stem

        char_objs: list[CharacterRole] = []
        ref_urls: list[str] = []
        if req.characters:
            for c in req.characters:
                ref = c.get("reference_url") if isinstance(c, dict) else getattr(c, "reference_url", None)
                if ref and ref not in ref_urls:
                    ref_urls.append(ref)
                if isinstance(c, CharacterRole):
                    char_objs.append(c)
                elif isinstance(c, dict):
                    char_objs.append(
                        CharacterRole(
                            role_id=c.get("role_id", ""),
                            name=sanitize_real_names(c.get("name", "")),
                            description=sanitize_real_names(c.get("description", "")),
                            reference_url=c.get("reference_url"),
                            aesthetic_tags=[sanitize_real_names(t) for t in c.get("aesthetic_tags", [])],
                            voice_style=sanitize_real_names(c.get("voice_style", "")),
                            voice_profile=sanitize_real_names(c.get("voice_profile", "")),
                            image_role=c.get("image_role", "Character Reference"),
                            is_offscreen_narrator=c.get("is_offscreen_narrator", False),
                        )
                    )
                elif hasattr(c, "model_dump"):
                    cd = c.model_dump()
                    char_objs.append(
                        CharacterRole(
                            role_id=cd.get("role_id", ""),
                            name=sanitize_real_names(cd.get("name", "")),
                            description=sanitize_real_names(cd.get("description", "")),
                            reference_url=cd.get("reference_url"),
                            aesthetic_tags=[sanitize_real_names(t) for t in cd.get("aesthetic_tags", [])],
                            voice_style=sanitize_real_names(cd.get("voice_style", "")),
                            voice_profile=sanitize_real_names(cd.get("voice_profile", "")),
                            image_role=cd.get("image_role", "Character Reference"),
                            is_offscreen_narrator=cd.get("is_offscreen_narrator", False),
                        )
                    )
                elif hasattr(c, "role_id"):
                    char_objs.append(
                        CharacterRole(
                            role_id=getattr(c, "role_id", ""),
                            name=sanitize_real_names(getattr(c, "name", "")),
                            description=sanitize_real_names(getattr(c, "description", "")),
                            reference_url=getattr(c, "reference_url", None),
                            aesthetic_tags=[sanitize_real_names(t) for t in getattr(c, "aesthetic_tags", [])],
                            voice_style=sanitize_real_names(getattr(c, "voice_style", "")),
                            voice_profile=sanitize_real_names(getattr(c, "voice_profile", "")),
                            image_role=getattr(c, "image_role", "Character Reference"),
                            is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                        )
                    )

        active_roles: list[str] = []
        if char_objs:
            active_roles = [c.role_id or c.name for c in char_objs if c.role_id or c.name]
        if not active_roles:
            active_roles = ["Role A"]

        scene_directive = SceneDirective(
            scene_number=req.shot_index,
            active_roles=active_roles,
            action=action_val,
            dialogue=dialogue_val,
            duration_seconds=req.duration_seconds,
        )

        aesthetic_tags = [t for t in [style_lighting_val or req.style_lighting, framing_motion_val] if t and t.strip()]

        compiled_prompt = agent.taxonomy.compiler.compile_storyboard(
            concept=action_val,
            characters=char_objs,
            scenes=[scene_directive],
            aesthetic_tags=aesthetic_tags if aesthetic_tags else None,
            environment_tag=location_val if location_val.strip() else None,
            audio_beat=audio_stem_val,
            has_keyframe_seed=bool(keyframe_url),
            keyframe_image_url=keyframe_url,
        )

        # Option A: Auto-generate keyframe image first if missing so video always has starting image seed and tone anchor
        if not keyframe_url and (action_val or sanitized_directive):
            try:
                keyframe_url = agent.omni_client.generate_keyframe_image(
                    action_val or sanitized_directive,
                    style_tone=req.style_lighting or style_lighting_val,
                    reference_image_urls=ref_urls,
                    characters=req.characters,
                )
            except Exception as exc:
                logger.warning("Auto keyframe image generation before video generation failed: %s", exc)

        agent_turn = agent.process_user_turn(
            user_id="usr_default",
            project_id="prj_default",
            prompt=action_val or sanitized_directive,
            compiled_override=compiled_prompt,
            parent_turn_id=req.parent_turn_id,
            clip_index=req.shot_index,
            duration_seconds=req.duration_seconds,
            is_conversational_edit=False,
            session_name=req.session_name,
            characters=req.characters,
            scenes=[scene_directive],
            keyframe_image_url=keyframe_url,
            voiceover=dialogue_val if dialogue_val else None,
            audio_stem=audio_stem_val,
        )
        return GenerateShotResponse(
            success=agent_turn.success,
            video_url=agent_turn.video_url,
            keyframe_image_url=keyframe_url,
            turn_id=agent_turn.turn_id,
            status=agent_turn.status_event,
            generation_mode=getattr(agent_turn, "generation_mode", "LIVE_OMNI_FLASH"),
            error=agent_turn.error_message,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt or compiled_prompt,
        )

    @app.post("/api/stitch-clips", response_model=SaveFinalResponse)
    def stitch_clips(req: StitchClipsRequest) -> SaveFinalResponse:
        if not req.clip_urls:
            raise HTTPException(
                status_code=400,
                detail="At least one clip URL is required for stitching.",
            )
        stitched_path = agent.stitcher.concatenate_clips(
            req.clip_urls, session_id=req.session_name
        )
        _pub_url, gcs_uri = agent.storage.save_final_master(
            session_id=req.session_name,
            source_rel_path=stitched_path,
            master_title=req.master_title,
        )
        return SaveFinalResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Custom stitched master successfully saved to {gcs_uri}",
        )

    @app.post("/api/extend-scene", response_model=GenerateResponse)
    def extend_scene(req: ExtendSceneRequest) -> GenerateResponse:
        agent_turn = agent.extend_scene(
            session_name=req.session_name,
            turn_id=req.turn_id,
            next_scene_action=req.next_scene_action,
            dialogue=req.dialogue,
            active_roles=req.active_roles,
            vocal_delivery=req.vocal_delivery,
        )
        return GenerateResponse(
            success=agent_turn.success,
            status=agent_turn.status_event,
            video_url=agent_turn.video_url,
            turn_id=agent_turn.turn_id,
            depth=agent_turn.depth,
            error=agent_turn.error_message,
            generation_mode=agent_turn.generation_mode,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt,
            reference_analysis=agent_turn.reference_analysis,
        )

    @app.post("/api/research", response_model=ParodyResearchResult)
    def research_parody(req: ResearchRequest) -> ParodyResearchResult:
        return agent.media_extractor.research_parody_clash(req.subject, req.aesthetic)

    @app.post("/api/extract-reference", response_model=ReferenceAnalysisReport)
    def extract_reference(req: ExtractReferenceRequest) -> ReferenceAnalysisReport:
        return agent.media_extractor.analyze_youtube_reference(
            req.url, session_id=req.session_name or "default"
        )

    @app.post("/api/characters/save", response_model=SaveCharacterResponse)
    def save_character(req: SaveCharacterRequest) -> SaveCharacterResponse:
        _pub_url, gcs_uri = agent.storage.save_character(
            req.character.model_dump(),
            session_id=req.session_name,
            is_library=req.is_library,
        )
        return SaveCharacterResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Character saved successfully to {gcs_uri}",
        )

    @app.get("/api/characters", response_model=CharacterListResponse)
    def list_characters(session_name: str | None = None) -> CharacterListResponse:
        raw_chars = agent.storage.list_characters(session_id=session_name)
        characters = [
            CharacterRoleModel(
                role_id=c.get("role_id", "Role A"),
                name=c.get("name", ""),
                description=c.get("description", ""),
                reference_url=c.get("reference_url"),
                aesthetic_tags=c.get("aesthetic_tags", []),
                voice_style=c.get("voice_style", ""),
                voice_profile=c.get("voice_profile", ""),
                wardrobe=c.get("wardrobe", ""),
                image_role=c.get("image_role", "Character Reference"),
                is_offscreen_narrator=c.get("is_offscreen_narrator", False),
            )
            for c in (raw_chars or [])
        ]
        return CharacterListResponse(characters=characters)

    @app.get("/api/sessions", response_model=SessionListResponse)
    def list_sessions() -> SessionListResponse:
        return SessionListResponse(sessions=agent.storage.list_session_ids())

    @app.post("/api/characters/load", response_model=CharacterRoleModel)
    def load_character(req: LoadCharacterRequest) -> CharacterRoleModel:
        char_data = agent.storage.load_character(req.slug, session_id=req.session_name)
        if not char_data:
            raise HTTPException(
                status_code=404,
                detail=f"Character '{req.slug}' not found",
            )
        return CharacterRoleModel(
            role_id=char_data.get("role_id", "Role A"),
            name=char_data.get("name", ""),
            description=char_data.get("description", ""),
            reference_url=char_data.get("reference_url"),
            aesthetic_tags=char_data.get("aesthetic_tags", []),
            voice_style=char_data.get("voice_style", ""),
            voice_profile=char_data.get("voice_profile", ""),
            wardrobe=char_data.get("wardrobe", ""),
            image_role=char_data.get("image_role", "Character Reference"),
            is_offscreen_narrator=char_data.get("is_offscreen_narrator", False),
        )

    @app.post("/api/characters/save-roster", response_model=SaveCharacterResponse)
    def save_roster(req: SaveRosterRequest) -> SaveCharacterResponse:
        _pub_url, gcs_uri = agent.storage.save_session_roster(
            req.session_name,
            [c.model_dump() for c in req.characters],
        )
        return SaveCharacterResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Session roster saved successfully to {gcs_uri}",
        )

    @app.get("/api/characters/roster", response_model=CharacterListResponse)
    def get_session_roster(session_name: str) -> CharacterListResponse:
        raw_roster = agent.storage.load_session_roster(session_name)
        characters = [
            CharacterRoleModel(
                role_id=c.get("role_id", "Role A"),
                name=c.get("name", ""),
                description=c.get("description", ""),
                reference_url=c.get("reference_url"),
                aesthetic_tags=c.get("aesthetic_tags", []),
                voice_style=c.get("voice_style", ""),
                voice_profile=c.get("voice_profile", ""),
                wardrobe=c.get("wardrobe", ""),
                image_role=c.get("image_role", "Character Reference"),
                is_offscreen_narrator=c.get("is_offscreen_narrator", False),
            )
            for c in (raw_roster or [])
        ]
        return CharacterListResponse(characters=characters)

    @app.post("/api/storyboards/save", response_model=SaveStoryboardResponse)
    def save_storyboard(req: SaveStoryboardRequest) -> SaveStoryboardResponse:
        _pub_url, gcs_uri = agent.storage.save_storyboard(
            req.name,
            req.storyboard_data,
            session_id=req.session_name,
        )
        return SaveStoryboardResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Storyboard saved successfully to {gcs_uri}",
        )

    @app.get("/api/storyboards", response_model=StoryboardListResponse)
    def list_storyboards(session_name: str | None = None) -> StoryboardListResponse:
        raw_storyboards = agent.storage.list_storyboards(session_id=session_name)
        storyboards = [
            StoryboardMetadataModel(
                name=sb.get("name", ""),
                slug=sb.get("slug", ""),
                concept=sb.get("concept", ""),
                shot_count=sb.get("shot_count", 0),
                updated_at=sb.get("updated_at", ""),
            )
            for sb in (raw_storyboards or [])
        ]
        return StoryboardListResponse(storyboards=storyboards)

    @app.post("/api/storyboards/load", response_model=dict[str, Any])
    def load_storyboard(req: LoadStoryboardRequest) -> dict[str, Any]:
        storyboard_data = agent.storage.load_storyboard(
            req.slug, session_id=req.session_name
        )
        if storyboard_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Storyboard '{req.slug}' not found",
            )
        return storyboard_data

    @app.post("/api/storyboards/delete", response_model=dict[str, Any])
    def delete_storyboard(req: DeleteStoryboardRequest) -> dict[str, Any]:
        deleted = agent.storage.delete_storyboard(
            req.slug, session_id=req.session_name
        )
        message = (
            f"Storyboard '{req.slug}' deleted successfully"
            if deleted
            else f"Storyboard '{req.slug}' not found"
        )
        return {"success": deleted, "message": message}

    @app.get("/api/media-proxy")
    def media_proxy(uri: str) -> Response:
        if not uri:
            raise HTTPException(status_code=400, detail="Missing URI parameter")

        if uri.startswith("https://storage.googleapis.com/"):
            parts = uri.replace("https://storage.googleapis.com/", "").split("/", 1)
            if len(parts) == 2:
                uri = f"gs://{parts[0]}/{parts[1]}"
        elif uri.startswith("https://storage.cloud.google.com/"):
            parts = uri.replace("https://storage.cloud.google.com/", "").split("/", 1)
            if len(parts) == 2:
                uri = f"gs://{parts[0]}/{parts[1]}"

        if not uri.startswith("gs://"):
            raise HTTPException(
                status_code=400,
                detail="Invalid GCS URI. Must start with gs:// or https://storage.googleapis.com/",
            )
        data, content_type = agent.storage.download_blob_bytes(uri)
        if not data:
            raise HTTPException(
                status_code=404,
                detail="Media object not found or empty",
            )
        return Response(
            content=data,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    return app


app = create_app()
