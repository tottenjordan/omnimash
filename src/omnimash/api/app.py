import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.ingestion.media_extractor import (
    ParodyResearchResult,
    ReferenceAnalysisReport,
)


class CharacterRoleModel(BaseModel):
    role_id: str
    name: str = ""
    description: str = ""
    reference_url: str | None = None
    aesthetic_tags: list[str] = []
    voice_style: str = ""


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


class SaveFinalResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str


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
                    voice_style: "Fast-paced confident Atlanta rap flow with autotune"
                },
                {
                    role_id: "Role B",
                    name: "Draco",
                    description: "Draco Malfoy, a pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored silver-trimmed robes",
                    reference_url: "https://example.com/draco.jpg",
                    aesthetic_tags: ["Platinum Slicked Hair", "Diamond Iced-Out Chain"],
                    voice_style: "Pompous, cynical British drawl with aggressive rap cadence"
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
                    active_roles: ["Role A"],
                    action: "Arriving at foggy Hogwarts courtyard rapping into microphone wand",
                    dialogue: "I been cooking potions since first year. Burrr!"
                },
                {
                    scene_number: 2,
                    active_roles: ["Role B"],
                    action: "Stepping from shadows in high-gloss neon lighting with ice chain",
                    dialogue: "This is Trap or Die, Potter! Let's get it!"
                }
            ]);
            const [copied, setCopied] = useState(false);

            // Act 3: The Screening Room & Branching State
            const [currentVideo, setCurrentVideo] = useState("/static/rendered/mock.mp4");
            const [deltaPrompt, setDeltaPrompt] = useState("");
            const [parentTurnId, setParentTurnId] = useState("");
            const [loading, setLoading] = useState(false);
            const [status, setStatus] = useState("COMPLETED");
            const [generationMode, setGenerationMode] = useState("LIVE_OMNI_FLASH");
            const [lastError, setLastError] = useState(null);
            const [showCommitModal, setShowCommitModal] = useState(false);
            const [commitPrompt, setCommitPrompt] = useState("");

            const initialRawPrompt = `[ROLE DEFINITIONS]\n- Role A (Harry): Harry Potter, a young wizard with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead [Style: Red Gucci Tracksuit, Cartier Glasses] (Ref: https://example.com/harry.jpg)\n- Role B (Draco): Draco Malfoy, a pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored silver-trimmed robes [Style: Platinum Slicked Hair, Diamond Iced-Out Chain] (Ref: https://example.com/draco.jpg)\n\n[AESTHETIC INJECTION]\nConcept: Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style\nAesthetic Tags: 2000s Atlanta Trap Disstrack, Diamond Lightning Bolt Chain, Heavy 808 Bass Lighting, Vintage Streetwear\nEnvironment: Gothic Hogwarts courtyard lit by neon stage lights and smoky haze\nCamera/Lighting: Low-angle 90s fisheye tracking shot with high-contrast green and purple neon rim lights\n\n[AUDIO & VOCAL DIRECTION]\nBackground Beat: 140 BPM Heavy 808 Trap (ducked at 15% volume under dialogue)\nVoice Style (Role A): Fast-paced confident Atlanta rap flow with autotune\nVoice Style (Role B): Pompous, cynical British drawl with aggressive rap cadence\nVocal Delivery: High-energy back-and-forth rap battle delivery with synchronized lip-sync\n\n[STORYBOARD SEQUENCE]\n- Scene 1 [Role A]: Arriving at foggy Hogwarts courtyard rapping into microphone wand | Dialogue: "I been cooking potions since first year. Burrr!"\n- Scene 2 [Role B]: Stepping from shadows in high-gloss neon lighting with ice chain | Dialogue: "This is Trap or Die, Potter! Let's get it!"`;

            const [rawCompiledPrompt, setRawCompiledPrompt] = useState(initialRawPrompt);
            const [masterTitle, setMasterTitle] = useState("official_rap_battle_master");
            const [savedGcsUri, setSavedGcsUri] = useState(null);
            const [showSaveModal, setShowSaveModal] = useState(false);
            const [saveLoading, setSaveLoading] = useState(false);
            const [extendLoading, setExtendLoading] = useState(false);

            const [history, setHistory] = useState([
                {
                    turnId: "turn_init",
                    prompt: "Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style",
                    status: "COMPLETED",
                    videoUrl: "/static/rendered/mock.mp4",
                    parent: null,
                    lock: "Maintain character likeness, Role A/B identities, and background environment.",
                    diff: "Initial parody cut generated from Act 1 & Act 2 storyboard sequence.",
                    rawCompiledPrompt: initialRawPrompt
                }
            ]);

            // Helper: Client-side Live Storyboard Prompt Compiler Preview
            const compileStoryboardPreview = () => {
                const roleLines = characters.map(c => {
                    const style = (c.aesthetic_tags && c.aesthetic_tags.length > 0) ? ` [Style: ${c.aesthetic_tags.join(", ")}]` : "";
                    const ref = c.reference_url ? ` (Ref: ${c.reference_url})` : "";
                    return `- ${c.role_id} (${c.name || "Unnamed"}): ${c.description || "No description"}${style}${ref}`;
                }).join("\n");

                const aestheticParts = [];
                if (concept && concept.trim()) aestheticParts.push(`Concept: ${concept.trim()}`);
                if (aestheticTags && aestheticTags.length > 0) aestheticParts.push(`Aesthetic Tags: ${aestheticTags.join(", ")}`);
                if (environmentTag && environmentTag.trim()) aestheticParts.push(`Environment: ${environmentTag.trim()}`);
                if (cameraLightingTag && cameraLightingTag.trim()) aestheticParts.push(`Camera/Lighting: ${cameraLightingTag.trim()}`);
                const aestheticBlock = aestheticParts.length > 0 ? aestheticParts.join("\n") : "Default Aesthetic";

                const audioParts = [];
                if (audioBeat && audioBeat.trim()) {
                    audioParts.push(`Background Beat: ${audioBeat.trim()} (ducked at 15% volume under dialogue)`);
                }
                characters.forEach(c => {
                    if (c.voice_style && c.voice_style.trim()) {
                        audioParts.push(`Voice Style (${c.role_id}): ${c.voice_style.trim()}`);
                    }
                });
                if (vocalDelivery && vocalDelivery.trim()) {
                    audioParts.push(`Vocal Delivery: ${vocalDelivery.trim()}`);
                }
                const audioBlock = audioParts.length > 0 ? audioParts.join("\n") : "Default Audio & Voice Direction";

                const sceneLines = scenes.map(s => {
                    const roles = (s.active_roles && s.active_roles.length > 0) ? s.active_roles.join(", ") : "All Roles";
                    const diag = (s.dialogue && s.dialogue.trim()) ? ` | Dialogue: "${s.dialogue.trim()}"` : "";
                    return `- Scene ${s.scene_number} [${roles}]: ${s.action || "Action description"}${diag}`;
                }).join("\n");

                return `[ROLE DEFINITIONS]\n${roleLines || "- None"}\n\n[AESTHETIC INJECTION]\n${aestheticBlock}\n\n[AUDIO & VOCAL DIRECTION]\n${audioBlock}\n\n[STORYBOARD SEQUENCE]\n${sceneLines || "- No scenes"}`;
            };

            // Act 1 Handler: Deconstruct Concept (POST /api/deconstruct-concept)
            const handleDeconstructConcept = async (conceptOverride) => {
                const targetConcept = conceptOverride || concept;
                if (!targetConcept || !targetConcept.trim()) return;
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
                            voice_style: c.voice_style || ""
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

            // Character Roles management
            const addCharacterRole = () => {
                const nextLetter = String.fromCharCode(65 + characters.length);
                const newRole = {
                    role_id: `Role ${nextLetter}`,
                    name: `Character ${nextLetter}`,
                    description: "Distinct cinematic character with expressive facial features and stylized attire",
                    reference_url: "",
                    aesthetic_tags: [],
                    voice_style: ""
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
                    active_roles: [characters[0]?.role_id || "Role A"],
                    action: "",
                    dialogue: ""
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
                    const payload = {
                        user_id: "usr_studio",
                        project_id: "prj_director",
                        prompt: deltaPrompt || concept,
                        clip_index: 0,
                        parent_turn_id: parentTurnId || null,
                        session_name: sessionName,
                        concept: concept,
                        characters: characters,
                        scenes: scenes,
                        aesthetic_tags: aestheticTags,
                        environment_tag: environmentTag,
                        audio_stem: audioBeat,
                        vocal_delivery: vocalDelivery
                    };
                    const endpoint = parentTurnId ? "/api/diff" : "/api/generate";
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
                            master_title: masterTitle || "final_master"
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
                setSessionName(`session_${Date.now().toString().slice(-4)}`);
                setConcept("");
                setCharacters([]);
                setAestheticTags([]);
                setEnvironmentTag("");
                setCameraLightingTag("");
                setAudioBeat("");
                setVocalDelivery("");
                setScenes([]);
                setHistory([]);
                setParentTurnId("");
                setDeltaPrompt("");
                setRawCompiledPrompt("Ready for new concept deconstruction.");
                setActiveAct(1);
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
                                    <span className="text-2xl">💾</span>
                                    <div>
                                        <h3 className="font-bold text-base text-amber-200">Save Final Master to GCS</h3>
                                        <p className="text-xs text-amber-300/80 mt-0.5">Persist this rendered parody cut to dedicated production GCS final master vault storage.</p>
                                    </div>
                                </div>
                                <div className="space-y-4 mb-6">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">Master Title</label>
                                        <input
                                            type="text"
                                            value={masterTitle}
                                            onChange={(e) => setMasterTitle(e.target.value)}
                                            placeholder="e.g. official_rap_battle_master"
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
                                        <span>{saveLoading ? "Saving..." : "Save Final Master to GCS"}</span>
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
                                    <p className="text-[11px] text-gray-400">Flexible Parody Concept &amp; Character Roles Workflow (Gemini Omni Image Roles)</p>
                                </div>
                            </div>
                        </div>

                        {/* GCS Session Name & Reset Studio */}
                        <div className="flex items-center space-x-3">
                            <button
                                onClick={handleResetStudio}
                                className="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 transition shadow-sm"
                            >
                                <span>🔄 New Project / Start Over</span>
                            </button>
                            <div className="bg-black/60 border border-gray-800 rounded-lg px-3 py-1.5 flex items-center space-x-2">
                                <span className="text-xs text-purple-400">🗂️ GCS Session:</span>
                                <input
                                    type="text"
                                    value={sessionName}
                                    onChange={(e) => setSessionName(e.target.value)}
                                    placeholder="session_name"
                                    className="bg-transparent border-b border-gray-700 text-xs font-mono text-purple-200 focus:outline-none focus:border-purple-400 w-32"
                                />
                            </div>
                        </div>
                    </header>

                    {/* 3-Act Navigation Bar */}
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
                            <span>Act 1: The Concept &amp; Cast Manager</span>
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
                            <span>Act 2: Fine-Tune &amp; Storyboard Directing</span>
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

                    {/* Main Stage Studio Container */}
                    <main className="flex-1 max-w-7xl w-full mx-auto p-6 overflow-y-auto custom-scrollbar">

                        {/* ========================================================= */}
                        {/* 🎭 ACT 1: THE CONCEPT & CAST MANAGER                      */}
                        {/* ========================================================= */}
                        {activeAct === 1 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-purple-950/40 to-pink-950/40 border border-purple-800/50 rounded-2xl p-5">
                                    <h2 className="text-base font-bold text-purple-200 flex items-center gap-2">
                                        <span>🎭</span>
                                        <span>Act 1: The Concept &amp; Cast Manager</span>
                                    </h2>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Enter an open-ended visual concept or parody prompt. Deconstruct it into dynamic character roles, aesthetic tags, and environmental parameters with Gemini Omni Image Roles.
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
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h3 className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-2">
                                                <span>👥</span>
                                                <span>Character Roles (Gemini Omni Image Roles Reference)</span>
                                            </h3>
                                            <p className="text-[11px] text-gray-400 mt-0.5">
                                                Define character roles with visual descriptions and attached reference image URLs to maintain likeness.
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={addCharacterRole}
                                            className="bg-purple-900/60 hover:bg-purple-800 text-purple-200 border border-purple-700 font-bold text-xs py-1.5 px-3 rounded-lg shadow flex items-center gap-1"
                                        >
                                            <span>+ Add Character Role</span>
                                        </button>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {characters.map((char, idx) => (
                                            <div key={idx} className="bg-gray-950 border border-gray-800/90 rounded-xl p-4 space-y-3 relative group">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs font-bold font-mono bg-pink-950 text-pink-300 px-2.5 py-1 rounded border border-pink-800/80">
                                                        {char.role_id}
                                                    </span>
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
                                                        🎨 Character Style Signifiers (Aesthetic Tags)
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
                                                        🎙️ Voice Style & Accent
                                                    </label>
                                                    <input
                                                        type="text"
                                                        value={char.voice_style || ""}
                                                        onChange={(e) => updateCharacter(idx, "voice_style", e.target.value)}
                                                        placeholder="e.g. Fast-paced confident Atlanta rap flow with autotune..."
                                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                    />
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
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* 3. Editable Meta-Prompt Tags, Environment & Audio Beat */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Aesthetic Tags & Audio Beat */}
                                    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
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
                                        <span>Proceed to Act 2: Fine-Tune &amp; Storyboard Directing</span>
                                        <span>➔</span>
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎛️ ACT 2: FINE-TUNE & STORYBOARD DIRECTING                */}
                        {/* ========================================================= */}
                        {activeAct === 2 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-pink-950/40 to-amber-950/40 border border-pink-800/50 rounded-2xl p-5">
                                    <h2 className="text-base font-bold text-pink-200 flex items-center gap-2">
                                        <span>🎛️</span>
                                        <span>Act 2: Fine-Tune &amp; Storyboard Directing</span>
                                    </h2>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Sequence multi-character scenes for a cohesive ~1-minute parody cut. Toggle active character roles and configure character action and spoken dialogue.
                                    </p>
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

                                                        {/* Action Description */}
                                                        <div>
                                                            <label className="block text-[11px] text-gray-400 mb-1">
                                                                Action Description
                                                            </label>
                                                            <textarea
                                                                rows={2}
                                                                value={scene.action}
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
                                                                value={scene.dialogue}
                                                                onChange={(e) => updateScene(idx, "dialogue", e.target.value)}
                                                                placeholder='e.g. Harry: "I been cooking potions since first year. Burrr!"'
                                                                className="w-full bg-gray-900 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono text-[11px]"
                                                            />
                                                        </div>
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
                        {/* 🎬 ACT 3: THE SCREENING ROOM & BRANCHING                  */}
                        {/* ========================================================= */}
                        {activeAct === 3 && (
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
                                                        Turn: {parentTurnId || "turn_init"}
                                                    </span>
                                                </div>
                                                <div className="flex items-center space-x-3">
                                                    <button
                                                        type="button"
                                                        onClick={() => setShowSaveModal(true)}
                                                        className="text-xs bg-amber-950/80 hover:bg-amber-900 text-amber-300 border border-amber-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
                                                    >
                                                        <span>💾</span>
                                                        <span>Save Final Master to GCS</span>
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
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </main>
                </div>
            );
        }

        ReactDOM.createRoot(document.getElementById("__next")).render(<OmniMashApp />);
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
        voiceover='Harry: "You talkin bout potions Draco? I been cooking since first year. Burrr!" / Draco: "This is Trap or Die Potter! Let us get it!"',
    )

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        return HTMLResponse(content=UI_HTML)

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
        agent_turn = agent.process_user_turn(
            user_id=req.user_id,
            project_id=req.project_id,
            prompt=req.prompt,
            clip_index=req.clip_index,
            parent_turn_id=req.parent_turn_id,
            reference_url=req.reference_url,
            audio_stem=req.audio_stem,
            voiceover=req.voiceover,
            is_silent=req.is_silent,
            on_screen_text=req.on_screen_text,
            compiled_override=req.compiled_override,
            session_name=req.session_name,
            concept=req.concept,
            characters=req.characters,
            scenes=req.scenes,
            aesthetic_tags=req.aesthetic_tags,
            environment_tag=req.environment_tag,
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

    @app.post("/api/commit", response_model=GenerateResponse)
    def commit_and_branch(req: CommitRequest) -> GenerateResponse:
        agent_turn = agent.commit_and_branch(
            user_id=req.user_id,
            project_id=req.project_id,
            turn_id=req.turn_id,
            prompt=req.next_prompt,
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
        _pub_url, gcs_uri = agent.save_final_master(
            session_id=req.session_name,
            video_url=req.video_url,
            master_title=req.master_title,
        )
        return SaveFinalResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Final master successfully saved to {gcs_uri}",
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

    return app


app = create_app()
