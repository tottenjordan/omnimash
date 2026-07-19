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


class ResearchRequest(BaseModel):
    subject: str
    aesthetic: str


class ExtractReferenceRequest(BaseModel):
    url: str
    session_name: str | None = None


class GenerateRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    prompt: str
    clip_index: int = 0
    parent_turn_id: str | None = None
    reference_url: str | None = None
    audio_stem: str | None = None
    voiceover: str | None = None
    is_silent: bool = False
    on_screen_text: str | None = None
    compiled_override: str | None = None
    session_name: str | None = None


class CommitRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    turn_id: str
    next_prompt: str = ""
    session_name: str | None = None


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None
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

        const subjectArchetypes = [
            { id: "harry_draco", name: "Harry & Draco (Trap-Warts)", icon: "🧙‍♂️", desc: "Gucci Harry vs. Jeezy Draco trap rivalry at Hogwarts", prompt: "Harry 'Gucci' Potter and Draco 'Jeezy' Malfoy in a rap video confrontation" },
            { id: "snape", name: "Dark Wizard (Snape)", icon: "🧙", desc: "Severus Snape in gothic stone dungeon with heavy shadows", prompt: "Severus Snape in 90s rap video" },
            { id: "scifi_hunter", name: "Sci-Fi Bounty Hunter", icon: "🚀", desc: "Armored bounty hunter in neon cantina", prompt: "Sci-Fi Bounty Hunter in futuristic neon cantina" },
            { id: "painter", name: "Renaissance Painter", icon: "🎨", desc: "16th-century classical master in gilded studio", prompt: "Renaissance Painter in dramatic baroque lighting" },
            { id: "custom", name: "Custom Subject Prompt", icon: "✍️", desc: "Define your own subject archetype or uploaded characters", prompt: "" }
        ];

        const aestheticSubcultures = [
            { id: "trap_disstrack", name: "Atlanta Trap Disstrack", icon: "🔥", desc: "Dark 808 bass lighting, heavy laser smoke, iced-out drip", bpm: "140 BPM Heavy 808 Trap" },
            { id: "90s_rap_video", name: "90s East Coast Rap", icon: "🎤", desc: "Fisheye lens, boom-bap beat, oversized shiny puffers", bpm: "120 BPM Boom-Bap" },
            { id: "cyberpunk_drift", name: "Cyberpunk Drift", icon: "🏎️", desc: "Holographic neon glow, synthwave purple & cyan grading", bpm: "110 BPM Cyberpunk Synthwave" },
            { id: "vhs_anime", name: "VHS Anime Lo-Fi", icon: "📼", desc: "Retro 4:3 VHS tape grain, analog scanlines, warm bloom", bpm: "85 BPM VHS Lo-Fi" },
            { id: "nu_metal", name: "00s Nu-Metal Video", icon: "🎸", desc: "Fisheye low-angle, grunge distortion, aggressive cadence", bpm: "130 BPM Nu-Metal Groove" }
        ];

        const presetDripPool = [
            "💎 Diamond Lightning Bolt Chain",
            "🧥 Vintage Gucci Tracksuit",
            "⛄ Slytherin Snowman Pendant",
            "🎙️ Microphone Wand",
            "🕶️ Shutter Shades",
            "✨ Diamond Grillz",
            "👑 Oversized Puffer Vest",
            "⌚ Iced-Out Rolex Watch"
        ];

        function OmniMashApp() {
            // Navigation Act State (1: The Clash, 2: The Fine-Tune, 3: The Director's Chair)
            const [activeAct, setActiveAct] = useState(1);

            // Session & Project State
            const [sessionName, setSessionName] = useState("dripwarts_vol1");

            // Act 1: The Clash State
            const [selectedSubjectId, setSelectedSubjectId] = useState("harry_draco");
            const [customSubjectText, setCustomSubjectText] = useState("");
            const [selectedAestheticId, setSelectedAestheticId] = useState("trap_disstrack");
            const [referenceUrl, setReferenceUrl] = useState("https://www.youtube.com/watch?v=sample_trap_beat");
            const [referenceAnalysis, setReferenceAnalysis] = useState(null);
            const [parodyResearch, setParodyResearch] = useState(null);
            const [researchLoading, setResearchLoading] = useState(false);
            const [extractLoading, setExtractLoading] = useState(false);

            // Act 2: The Fine-Tune State
            const [activeDrip, setActiveDrip] = useState([
                "💎 Diamond Lightning Bolt Chain",
                "🧥 Vintage Gucci Tracksuit",
                "⛄ Slytherin Snowman Pendant",
                "🎙️ Microphone Wand"
            ]);
            const [customDripInput, setCustomDripInput] = useState("");
            const [vibeIntensity, setVibeIntensity] = useState(75); // 0 (Gritty) to 100 (Glossy)
            const [audioBeat, setAudioBeat] = useState("140 BPM Heavy 808 Trap");
            const [voiceover, setVoiceover] = useState("Harry: \"I been cooking potions since first year. Burrr!\" / Draco: \"This is Trap or Die, Potter!\"");
            const [isSilent, setIsSilent] = useState(false);
            const [onScreenText, setOnScreenText] = useState("DRIPWARTS: HARRY VS. DRACO VOL. 1");
            const [rawCompiledPrompt, setRawCompiledPrompt] = useState("");
            const [isRawPayloadOpen, setIsRawPayloadOpen] = useState(true);
            const [copied, setCopied] = useState(false);

            // Act 3: The Director's Chair State
            const [currentVideo, setCurrentVideo] = useState("/static/rendered/mock.mp4");
            const [deltaPrompt, setDeltaPrompt] = useState("");
            const [parentTurnId, setParentTurnId] = useState("");
            const [loading, setLoading] = useState(false);
            const [status, setStatus] = useState("COMPLETED");
            const [showCommitModal, setShowCommitModal] = useState(false);
            const [commitPrompt, setCommitPrompt] = useState("");

            const [history, setHistory] = useState([
                {
                    turnId: "turn_init",
                    prompt: "Dripwarts: Harry Gucci Potter & Draco Jeezy Malfoy trailer",
                    status: "COMPLETED",
                    videoUrl: "/static/rendered/mock.mp4",
                    parent: null,
                    lock: "Maintain exact Harry Gucci & Draco Jeezy face likeness, diamond lightning chain, Gucci tracksuit, and Hogwarts dungeon environment.",
                    diff: "Initial 720p 10-second directorial cut generated from Act 1 & Act 2 setups."
                }
            ]);

            // Helper: Resolve active prompt string
            const getActiveSubject = () => {
                if (selectedSubjectId === "custom") return customSubjectText || "Custom cinematic character";
                const arch = subjectArchetypes.find(s => s.id === selectedSubjectId);
                return arch ? arch.prompt : "Harry 'Gucci' Potter and Draco 'Jeezy' Malfoy";
            };

            const getVibeDescription = (val) => {
                if (val <= 30) return "🌑 Gritty / Underground (Dark moody lighting, heavy laser smoke, 16mm raw grain)";
                if (val <= 70) return "🎥 Balanced Cinematic (High-contrast MTV rap video lighting, balanced color grading)";
                return "💎 High-Gloss Neon (Anamorphic lens flare, holographic bloom, polished commercial aesthetic)";
            };

            // 1-Click "Load Trap-Warts Concept" Loader
            const handleLoadTrapWartsConcept = () => {
                setSelectedSubjectId("harry_draco");
                setSelectedAestheticId("trap_disstrack");
                setSessionName("dripwarts_vol1");
                setActiveDrip([
                    "💎 Diamond Lightning Bolt Chain",
                    "🧥 Vintage Gucci Tracksuit",
                    "⛄ Slytherin Snowman Pendant",
                    "🎙️ Microphone Wand",
                    "🕶️ Shutter Shades"
                ]);
                setVibeIntensity(80);
                setAudioBeat("140 BPM Heavy 808 Trap");
                setVoiceover('Harry: "You talkin\' \'bout potions, Draco? I been cooking since first year. Burrr!" / Draco: "This is Trap or Die, Potter! Let\'s get it!"');
                setOnScreenText("DRIPWARTS: HARRY VS. DRACO VOL. 1");
                setIsSilent(false);
                setParodyResearch({
                    synopsis: "Dripwarts: Harry & The Brick Factory - A viral high-fashion rap trailer mashup of Hogwarts wizard rivalry with 2010s Atlanta trap music beef (Gucci vs. Jeezy).",
                    suggested_props: ["Diamond Lightning Bolt Chain", "Vintage Gucci Tracksuit", "Slytherin Snowman Pendant", "Microphone Wand", "Shutter Shades"],
                    suggested_vibe: "Dark moody 808 bass lighting, laser smoke, and high-gloss neon reflections",
                    vibe_intensity: 80,
                    suggested_audio: "140 BPM Heavy 808 Trap",
                    suggested_dialogue: "Harry: \"I been cooking potions since first year. Burrr!\" / Draco: \"This is Trap or Die, Potter!\""
                });
            };

            // Ingest Reference URL (POST /api/extract-reference)
            const handleExtractReference = async () => {
                if (!referenceUrl) return;
                setExtractLoading(true);
                try {
                    const res = await fetch("/api/extract-reference", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ url: referenceUrl, session_name: sessionName })
                    });
                    const data = await res.json();
                    setReferenceAnalysis(data);
                } catch (err) {
                    console.error("Reference extraction failed:", err);
                } finally {
                    setExtractLoading(false);
                }
            };

            // Gemini Parody Research (POST /api/research)
            const handleResearchClash = async () => {
                setResearchLoading(true);
                try {
                    const subject = getActiveSubject();
                    const aesthetic = aestheticSubcultures.find(a => a.id === selectedAestheticId)?.name || "Trap Disstrack";
                    const res = await fetch("/api/research", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ subject, aesthetic })
                    });
                    const data = await res.json();
                    setParodyResearch(data);
                    if (data.suggested_props && data.suggested_props.length > 0) {
                        setActiveDrip(data.suggested_props.map(p => p.startsWith("💎") || p.startsWith("🧥") ? p : `💎 ${p}`));
                    }
                    if (data.vibe_intensity) setVibeIntensity(data.vibe_intensity);
                    if (data.suggested_audio) setAudioBeat(data.suggested_audio);
                    if (data.suggested_dialogue) setVoiceover(data.suggested_dialogue);
                } catch (err) {
                    console.error("Parody research failed:", err);
                } finally {
                    setResearchLoading(false);
                }
            };

            const toggleDripProp = (prop) => {
                if (activeDrip.includes(prop)) {
                    setActiveDrip(activeDrip.filter(p => p !== prop));
                } else {
                    setActiveDrip([...activeDrip, prop]);
                }
            };

            const addCustomDrip = (e) => {
                e.preventDefault();
                if (customDripInput.trim().length > 0) {
                    const newProp = `✨ ${customDripInput.trim()}`;
                    if (!activeDrip.includes(newProp)) {
                        setActiveDrip([...activeDrip, newProp]);
                    }
                    setCustomDripInput("");
                }
            };

            // Generate Video Cut (POST /api/generate)
            const handleGenerate = async (e) => {
                if (e) e.preventDefault();
                setLoading(true);
                try {
                    const subject = getActiveSubject();
                    const aesthetic = aestheticSubcultures.find(a => a.id === selectedAestheticId)?.name || "Trap Disstrack";
                    const promptText = deltaPrompt || `${subject} in a ${aesthetic} video`;

                    const res = await fetch("/api/generate", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "usr_studio",
                            project_id: "prj_director",
                            prompt: promptText,
                            clip_index: 0,
                            parent_turn_id: parentTurnId || null,
                            reference_url: referenceUrl || null,
                            audio_stem: isSilent ? "mute" : audioBeat,
                            voiceover: voiceover || null,
                            is_silent: isSilent,
                            on_screen_text: onScreenText || null,
                            session_name: sessionName
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        if (data.reference_analysis) setReferenceAnalysis(data.reference_analysis);
                        if (data.raw_compiled_prompt) setRawCompiledPrompt(data.raw_compiled_prompt);
                        
                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: promptText,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            lock: "Maintain subject face likeness, diamond chains, and background environment.",
                            diff: deltaPrompt ? `Delta edit: ${deltaPrompt}` : `Initial directorial cut (${aesthetic})`
                        };
                        setHistory(prev => [...prev, newTurn]);
                        setCurrentVideo(data.video_url);
                        setParentTurnId(data.turn_id);
                        setStatus(data.status);
                        setDeltaPrompt("");
                        setActiveAct(3); // Advance to Act 3 Director's Chair!
                        if (data.status === "COMMIT_RECOMMENDED") {
                            setShowCommitModal(true);
                        }
                    }
                } catch (err) {
                    console.error("Generation failed:", err);
                } finally {
                    setLoading(false);
                }
            };

            // Commit & Re-Anchor
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
                    if (data.success) {
                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: nextPrompt,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            lock: "New baseline re-anchored keyframe lock established.",
                            diff: `Checkpoint commit: ${nextPrompt}`
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
                } finally {
                    setLoading(false);
                }
            };

            const isCommitModalVisible = status === "COMMIT_RECOMMENDED" || showCommitModal;

            return (
                <div className="flex flex-col min-h-screen bg-gray-950 text-gray-100">
                    {/* Commit & Re-Anchor Warning Modal */}
                    {isCommitModalVisible && (
                        <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
                            <div className="bg-gray-900 border-2 border-amber-500/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
                                <div className="flex items-center space-x-3 bg-amber-950/80 border border-amber-500/50 rounded-xl p-4 mb-5 text-amber-300">
                                    <span className="text-2xl">⚠️</span>
                                    <div>
                                        <h3 className="font-bold text-base text-amber-200">Commit &amp; Re-Anchor Required</h3>
                                        <p className="text-xs text-amber-300/80 mt-0.5">Edit depth limit reached (Depth &ge; 3). Re-anchoring establishes a fresh keyframe baseline to prevent drift.</p>
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

                    {/* Top Application Header & Toolbar */}
                    <header className="border-b border-gray-800 bg-gray-900/90 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center space-x-4">
                            <div className="flex items-center space-x-2">
                                <span className="text-2xl">🎬</span>
                                <div>
                                    <h1 className="text-lg font-extrabold bg-gradient-to-r from-purple-400 via-pink-400 to-amber-400 bg-clip-text text-transparent">
                                        OMNIMASH • DIGITAL DIRECTOR'S STUDIO
                                    </h1>
                                    <p className="text-[11px] text-gray-400">Anchor &amp; Inject Progressive Latent Engine</p>
                                </div>
                            </div>
                        </div>

                        {/* Session / GCS Folder & Trap-Warts Loader */}
                        <div className="flex items-center space-x-3">
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
                            <button
                                type="button"
                                onClick={handleLoadTrapWartsConcept}
                                className="bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 hover:opacity-95 text-white font-bold text-xs py-1.5 px-3.5 rounded-lg shadow flex items-center gap-1.5 transition transform hover:scale-105"
                            >
                                <span>⚡</span>
                                <span>Load Trap-Warts Concept</span>
                            </button>
                        </div>
                    </header>

                    {/* 3-Act Stepper Navigation Bar */}
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
                            <span>Act 1: The Clash</span>
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
                            <span>Act 2: The Fine-Tune</span>
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
                            <span>Act 3: The Director's Chair</span>
                        </button>
                    </div>

                    {/* Main Stage Studio Container */}
                    <main className="flex-1 max-w-7xl w-full mx-auto p-6 overflow-y-auto custom-scrollbar">

                        {/* ========================================================= */}
                        {/* 🎭 ACT 1: THE CLASH (SPLIT-SCREEN SETUP)                   */}
                        {/* ========================================================= */}
                        {activeAct === 1 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-purple-950/40 to-pink-950/40 border border-purple-800/50 rounded-2xl p-5">
                                    <h2 className="text-base font-bold text-purple-200 flex items-center gap-2">
                                        <span>🎭</span>
                                        <span>Act 1: The Clash • Define Conflicting Universes</span>
                                    </h2>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Choose your Subject Anchor (left) and Aesthetic Injection (right) to anchor the joint audio-video latent space.
                                    </p>
                                </div>

                                {/* Split-Screen Card Grids */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Left Column: Subject Anchor Cards */}
                                    <div className="bg-gray-900/80 border border-gray-800 rounded-2xl p-5 shadow-xl">
                                        <div className="flex items-center justify-between mb-4">
                                            <h3 className="text-sm font-bold text-pink-400 uppercase tracking-wider flex items-center gap-2">
                                                <span>🎯 [SUBJECT ANCHOR]</span>
                                            </h3>
                                            <span className="text-[11px] bg-pink-950/80 text-pink-300 px-2 py-0.5 rounded border border-pink-800/60">
                                                Character Likeness
                                            </span>
                                        </div>
                                        <div className="space-y-3">
                                            {subjectArchetypes.map(arch => (
                                                <div
                                                    key={arch.id}
                                                    onClick={() => setSelectedSubjectId(arch.id)}
                                                    className={`p-3.5 rounded-xl border cursor-pointer transition ${
                                                        selectedSubjectId === arch.id
                                                            ? "bg-pink-950/40 border-pink-500 shadow-md shadow-pink-950/50"
                                                            : "bg-gray-950/60 border-gray-800/80 hover:border-gray-700"
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center space-x-3">
                                                            <span className="text-2xl">{arch.icon}</span>
                                                            <div>
                                                                <h4 className="text-xs font-bold text-white">{arch.name}</h4>
                                                                <p className="text-[11px] text-gray-400 mt-0.5">{arch.desc}</p>
                                                            </div>
                                                        </div>
                                                        <input
                                                            type="radio"
                                                            checked={selectedSubjectId === arch.id}
                                                            onChange={() => setSelectedSubjectId(arch.id)}
                                                            className="text-pink-500 focus:ring-0"
                                                        />
                                                    </div>
                                                    {arch.id === "custom" && selectedSubjectId === "custom" && (
                                                        <div className="mt-3 pt-3 border-t border-gray-800">
                                                            <input
                                                                type="text"
                                                                value={customSubjectText}
                                                                onChange={(e) => setCustomSubjectText(e.target.value)}
                                                                placeholder="e.g. 1920s jazz detective with trench coat..."
                                                                className="w-full bg-black/80 border border-gray-700 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-pink-500"
                                                            />
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Right Column: Aesthetic Injection Cards */}
                                    <div className="bg-gray-900/80 border border-gray-800 rounded-2xl p-5 shadow-xl">
                                        <div className="flex items-center justify-between mb-4">
                                            <h3 className="text-sm font-bold text-purple-400 uppercase tracking-wider flex items-center gap-2">
                                                <span>🎨 [AESTHETIC INJECTION]</span>
                                            </h3>
                                            <span className="text-[11px] bg-purple-950/80 text-purple-300 px-2 py-0.5 rounded border border-purple-800/60">
                                                Musical Subculture
                                            </span>
                                        </div>
                                        <div className="space-y-3">
                                            {aestheticSubcultures.map(aes => (
                                                <div
                                                    key={aes.id}
                                                    onClick={() => {
                                                        setSelectedAestheticId(aes.id);
                                                        setAudioBeat(aes.bpm);
                                                    }}
                                                    className={`p-3.5 rounded-xl border cursor-pointer transition ${
                                                        selectedAestheticId === aes.id
                                                            ? "bg-purple-950/40 border-purple-500 shadow-md shadow-purple-950/50"
                                                            : "bg-gray-950/60 border-gray-800/80 hover:border-gray-700"
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center space-x-3">
                                                            <span className="text-2xl">{aes.icon}</span>
                                                            <div>
                                                                <h4 className="text-xs font-bold text-white">{aes.name}</h4>
                                                                <p className="text-[11px] text-gray-400 mt-0.5">{aes.desc}</p>
                                                            </div>
                                                        </div>
                                                        <input
                                                            type="radio"
                                                            checked={selectedAestheticId === aes.id}
                                                            onChange={() => {
                                                                setSelectedAestheticId(aes.id);
                                                                setAudioBeat(aes.bpm);
                                                            }}
                                                            className="text-purple-500 focus:ring-0"
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                {/* YouTube Reference URL & Extraction Panel */}
                                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl">
                                    <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                                        <span>🔍</span>
                                        <span>Multimodal YouTube Reference &amp; Keyframe Ingestion</span>
                                    </h3>
                                    <div className="flex flex-col sm:flex-row items-center gap-3">
                                        <input
                                            type="text"
                                            value={referenceUrl}
                                            onChange={(e) => setReferenceUrl(e.target.value)}
                                            placeholder="https://www.youtube.com/watch?v=..."
                                            className="flex-1 w-full bg-gray-950 border border-gray-800 rounded-xl p-2.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono"
                                        />
                                        <button
                                            type="button"
                                            disabled={extractLoading || !referenceUrl}
                                            onClick={handleExtractReference}
                                            className="w-full sm:w-auto bg-purple-900/60 hover:bg-purple-800 text-purple-200 border border-purple-700 font-bold text-xs py-2.5 px-4 rounded-xl shadow flex items-center justify-center gap-2 transition disabled:opacity-50"
                                        >
                                            <span>🔍</span>
                                            <span>{extractLoading ? "Extracting..." : "Extract Reference Assets"}</span>
                                        </button>
                                        <button
                                            type="button"
                                            disabled={researchLoading}
                                            onClick={handleResearchClash}
                                            className="w-full sm:w-auto bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 text-white font-bold text-xs py-2.5 px-5 rounded-xl shadow flex items-center justify-center gap-2 transition disabled:opacity-50"
                                        >
                                            <span>🧠</span>
                                            <span>{researchLoading ? "Researching..." : "Research Parody with Gemini 3.5"}</span>
                                        </button>
                                    </div>

                                    {/* Ingested Analysis Card & Keyframes */}
                                    {referenceAnalysis && (
                                        <div className="mt-5 pt-5 border-t border-gray-800 space-y-4">
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                                <div className="flex items-center space-x-2">
                                                    <span className="text-xs font-bold text-purple-300">📊 {referenceAnalysis.video_title}</span>
                                                    <span className="text-[10px] bg-purple-950 text-purple-400 px-2 py-0.5 rounded border border-purple-800">
                                                        {referenceAnalysis.detected_bpm} BPM Detected
                                                    </span>
                                                </div>
                                                <div className="flex items-center space-x-1.5">
                                                    <span className="text-[10px] text-gray-400">Palette:</span>
                                                    {referenceAnalysis.dominant_colors.map((c, i) => (
                                                        <span key={i} className="w-4 h-4 rounded-full border border-gray-700 shadow" style={{ backgroundColor: c }} title={c}></span>
                                                    ))}
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                {referenceAnalysis.extracted_keyframes.map((kf, i) => (
                                                    <div key={i} className="bg-gray-950 rounded-xl border border-gray-800 p-2.5 text-left">
                                                        <div className="h-20 bg-gray-900 rounded-lg flex items-center justify-center text-xs text-gray-500 font-mono mb-2 border border-gray-800/80">
                                                            🖼️ Frame @ {kf.timestamp}
                                                        </div>
                                                        <p className="text-[11px] text-gray-300 font-mono leading-tight">{kf.usage_annotation}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Gemini Parody Research Breakdown */}
                                    {parodyResearch && (
                                        <div className="mt-5 p-4 bg-purple-950/30 border border-purple-800/60 rounded-xl space-y-2">
                                            <div className="flex items-center space-x-2 text-xs font-bold text-pink-300">
                                                <span>✨ Gemini 3.5 Flash Parody Lore Breakdown:</span>
                                            </div>
                                            <p className="text-xs text-purple-200">{parodyResearch.synopsis}</p>
                                            <div className="text-[11px] text-gray-300 flex flex-wrap gap-2 pt-1">
                                                <span className="bg-black/60 px-2 py-0.5 rounded border border-purple-900 font-mono">Suggested Audio: {parodyResearch.suggested_audio}</span>
                                                <span className="bg-black/60 px-2 py-0.5 rounded border border-purple-900 font-mono">Vibe: {parodyResearch.suggested_vibe}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Act 1 Bottom Navigation */}
                                <div className="flex justify-end pt-4">
                                    <button
                                        type="button"
                                        onClick={() => setActiveAct(2)}
                                        className="bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 hover:opacity-90 text-white font-bold text-sm py-3 px-8 rounded-xl shadow-xl flex items-center gap-2 transition transform hover:scale-105"
                                    >
                                        <span>Proceed to Act 2: Fine-Tune Directing</span>
                                        <span>➔</span>
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎛️ ACT 2: THE FINE-TUNE (DIRECTING CONTROLS)              */}
                        {/* ========================================================= */}
                        {activeAct === 2 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-pink-950/40 to-amber-950/40 border border-pink-800/50 rounded-2xl p-5">
                                    <h2 className="text-base font-bold text-pink-200 flex items-center gap-2">
                                        <span>🎛️</span>
                                        <span>Act 2: The Fine-Tune • Direct Props, Camera Vibe &amp; Audio Synchronization</span>
                                    </h2>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Customize specific wardrobe props ("Drip"), camera lighting vibe, audio beat loop, and spoken character dialogue.
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                    {/* Left 7 Cols: Directorial Controls */}
                                    <div className="lg:col-span-7 space-y-5">
                                        {/* 1. The Drip Selector */}
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl">
                                            <h3 className="text-xs font-bold text-pink-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                                <span>💎</span>
                                                <span>The "Drip" Selector (Aesthetic Wardrobe &amp; Props)</span>
                                            </h3>
                                            <div className="flex flex-wrap gap-2 mb-3">
                                                {presetDripPool.map((prop, i) => (
                                                    <button
                                                        key={i}
                                                        type="button"
                                                        onClick={() => toggleDripProp(prop)}
                                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
                                                            activeDrip.includes(prop)
                                                                ? "bg-pink-600 text-white shadow-md shadow-pink-900/50"
                                                                : "bg-gray-950 text-gray-400 border border-gray-800 hover:border-gray-700"
                                                        }`}
                                                    >
                                                        <span>{prop}</span>
                                                        {activeDrip.includes(prop) && <span>✓</span>}
                                                    </button>
                                                ))}
                                            </div>
                                            <form onSubmit={addCustomDrip} className="flex gap-2">
                                                <input
                                                    type="text"
                                                    value={customDripInput}
                                                    onChange={(e) => setCustomDripInput(e.target.value)}
                                                    placeholder="Add custom drip accessory (e.g. 1996 Cartier shades)..."
                                                    className="flex-1 bg-gray-950 border border-gray-800 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-pink-500"
                                                />
                                                <button
                                                    type="submit"
                                                    className="bg-gray-800 hover:bg-gray-700 text-xs text-pink-300 font-bold px-3 py-2 rounded-lg border border-gray-700"
                                                >
                                                    + Add Drip
                                                </button>
                                            </form>
                                        </div>

                                        {/* 2. Vibe Slider (Lighting / Camera) */}
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl">
                                            <div className="flex items-center justify-between mb-2">
                                                <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                                                    <span>🎥</span>
                                                    <span>Vibe Slider (Lighting &amp; Camera Grading)</span>
                                                </h3>
                                                <span className="text-xs font-mono font-bold text-amber-300">{vibeIntensity}%</span>
                                            </div>
                                            <input
                                                type="range"
                                                min="0"
                                                max="100"
                                                value={vibeIntensity}
                                                onChange={(e) => setVibeIntensity(parseInt(e.target.value))}
                                                className="w-full accent-amber-500 bg-gray-950 h-2 rounded-lg cursor-pointer"
                                            />
                                            <div className="flex justify-between text-[10px] text-gray-500 mt-1 font-mono">
                                                <span>0% (Gritty / 16mm)</span>
                                                <span>50% (Balanced MTV)</span>
                                                <span>100% (High-Gloss Neon)</span>
                                            </div>
                                            <div className="mt-3 p-2.5 bg-black/60 border border-gray-800/80 rounded-xl text-xs text-amber-200 font-mono">
                                                {getVibeDescription(vibeIntensity)}
                                            </div>
                                        </div>

                                        {/* 3. Audio Beat Loop & Voiceover Directives */}
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                                            <h3 className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-2">
                                                <span>🎵</span>
                                                <span>Audio Beat Loop &amp; Voiceover Overrides</span>
                                            </h3>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                {["140 BPM Heavy 808 Trap", "120 BPM Boom-Bap", "110 BPM Cyberpunk Synthwave", "85 BPM VHS Lo-Fi"].map((beat, i) => (
                                                    <button
                                                        key={i}
                                                        type="button"
                                                        onClick={() => {
                                                            setAudioBeat(beat);
                                                            setIsSilent(false);
                                                        }}
                                                        className={`p-2.5 rounded-xl border text-left text-xs font-mono transition ${
                                                            !isSilent && audioBeat === beat
                                                                ? "bg-purple-950/60 border-purple-500 text-purple-200 shadow"
                                                                : "bg-gray-950 border-gray-800 text-gray-400 hover:border-gray-700"
                                                        }`}
                                                    >
                                                        🎵 {beat}
                                                    </button>
                                                ))}
                                            </div>

                                            <div className="flex items-center space-x-2 pt-1">
                                                <input
                                                    type="checkbox"
                                                    id="silentToggle"
                                                    checked={isSilent}
                                                    onChange={(e) => setIsSilent(e.target.checked)}
                                                    className="rounded text-purple-600 focus:ring-0"
                                                />
                                                <label htmlFor="silentToggle" className="text-xs text-gray-300">
                                                    🔇 Override to Silent Video (No background music, no audio)
                                                </label>
                                            </div>

                                            <div>
                                                <label className="block text-xs font-bold text-gray-300 mb-1">
                                                    🎙️ Spoken Voiceover / Character Dialogue Turns
                                                </label>
                                                <textarea
                                                    rows={2}
                                                    value={voiceover}
                                                    onChange={(e) => setVoiceover(e.target.value)}
                                                    placeholder='e.g. Harry: "I been cooking potions..." / Draco: "This is Trap or Die!"'
                                                    className="w-full bg-gray-950 border border-gray-800 rounded-xl p-2.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500 font-mono"
                                                />
                                                <p className="text-[10px] text-purple-400/90 mt-1">
                                                    🎚️ Automatic Beat Ducking: Background beat will be ducked to 18% volume for crystal-clear foreground speech.
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Right 5 Cols: Live Compiled Prompt Preview */}
                                    <div className="lg:col-span-5 space-y-5">
                                        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col h-full justify-between">
                                            <div>
                                                <div className="flex items-center justify-between mb-3">
                                                    <h3 className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-2">
                                                        <span>📋</span>
                                                        <span>Compiled Anchor &amp; Inject Prompt</span>
                                                    </h3>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            if (navigator.clipboard) navigator.clipboard.writeText(rawCompiledPrompt || "Compiled prompt");
                                                            setCopied(true);
                                                            setTimeout(() => setCopied(false), 2000);
                                                        }}
                                                        className="text-[10px] bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded hover:bg-purple-900"
                                                    >
                                                        {copied ? "✓ Copied!" : "📋 Copy Prompt"}
                                                    </button>
                                                </div>

                                                <div className="space-y-2 text-xs font-mono">
                                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                                        <span className="text-pink-400 font-bold block mb-0.5">[SUBJECT ANCHOR]:</span>
                                                        <span className="text-gray-300">{getActiveSubject()}</span>
                                                    </div>
                                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                                        <span className="text-purple-400 font-bold block mb-0.5">[AESTHETIC &amp; DRIP]:</span>
                                                        <span className="text-gray-300">
                                                            {aestheticSubcultures.find(a => a.id === selectedAestheticId)?.desc}, accessorized with {activeDrip.join(", ")}
                                                        </span>
                                                    </div>
                                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                                        <span className="text-amber-400 font-bold block mb-0.5">[CAMERA &amp; VIBE]:</span>
                                                        <span className="text-gray-300">{getVibeDescription(vibeIntensity)}</span>
                                                    </div>
                                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                                        <span className="text-blue-400 font-bold block mb-0.5">[AUDIO &amp; DIALOGUE]:</span>
                                                        <span className="text-gray-300">
                                                            {isSilent ? "Silent Video" : audioBeat}. {voiceover}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="pt-6 flex items-center justify-between gap-3">
                                                <button
                                                    type="button"
                                                    onClick={() => setActiveAct(1)}
                                                    className="px-4 py-2.5 rounded-xl border border-gray-800 text-xs text-gray-400 hover:text-white"
                                                >
                                                    ⮌ Back to Act 1
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={loading}
                                                    onClick={handleGenerate}
                                                    className="flex-1 bg-gradient-to-r from-purple-600 via-pink-600 to-amber-500 hover:opacity-90 text-white font-bold text-sm py-3 px-6 rounded-xl shadow-xl flex items-center justify-center gap-2 transition disabled:opacity-50"
                                                >
                                                    <span>🚀</span>
                                                    <span>{loading ? "Rendering Directorial Cut..." : "Generate Directorial Cut ➔"}</span>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ========================================================= */}
                        {/* 🎬 ACT 3: THE DIRECTOR'S CHAIR (ITERATION & TIMELINE)      */}
                        {/* ========================================================= */}
                        {activeAct === 3 && (
                            <div className="space-y-6">
                                <div className="bg-gradient-to-r from-amber-950/40 to-purple-950/40 border border-amber-800/50 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
                                    <div>
                                        <h2 className="text-base font-bold text-amber-200 flex items-center gap-2">
                                            <span>🎬</span>
                                            <span>Act 3: The Director's Chair • High-Resolution Playback &amp; Conversational Edits</span>
                                        </h2>
                                        <p className="text-xs text-gray-400 mt-1">
                                            Review the rendered 10-second cut and apply conversational diffs via the Gemini Enterprise Interactions API.
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setActiveAct(2)}
                                        className="bg-gray-900 border border-gray-700 text-xs text-amber-300 px-3 py-1.5 rounded-lg hover:bg-gray-800"
                                    >
                                        🎛️ Adjust Fine-Tune Directing
                                    </button>
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                    {/* Left 8 Cols: Central High-Res Video Player & Delta Chat Bar */}
                                    <div className="lg:col-span-8 space-y-4">
                                        <div className="bg-black rounded-2xl border border-gray-800 overflow-hidden shadow-2xl relative">
                                            <video
                                                src={currentVideo}
                                                controls
                                                autoPlay
                                                loop
                                                className="w-full aspect-video object-contain bg-black"
                                            />
                                            <div className="p-4 bg-gray-900/90 border-t border-gray-800 flex items-center justify-between">
                                                <div className="flex items-center space-x-2 text-xs">
                                                    <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
                                                    <span className="font-bold text-gray-300">Live Latent Cut</span>
                                                    <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-mono">
                                                        Turn: {parentTurnId || "turn_init"}
                                                    </span>
                                                </div>
                                                <a
                                                    href={currentVideo}
                                                    download="omnimash_cut.mp4"
                                                    className="text-xs text-purple-400 hover:text-purple-300 font-bold flex items-center gap-1"
                                                >
                                                    <span>⬇️ Download MP4</span>
                                                </a>
                                            </div>
                                        </div>

                                        {/* Direct the Scene Conversational Delta Chat Bar */}
                                        <form onSubmit={handleGenerate} className="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl flex gap-3 items-center">
                                            <div className="text-xl">💬</div>
                                            <input
                                                type="text"
                                                value={deltaPrompt}
                                                onChange={(e) => setDeltaPrompt(e.target.value)}
                                                placeholder="Direct the scene (e.g. Make his sunglasses darker and add green laser smoke)..."
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

                                    {/* Right 4 Cols: Chronological Layer-Cake Edit History */}
                                    <div className="lg:col-span-4 bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col h-[560px]">
                                        <div className="flex items-center justify-between mb-4 border-b border-gray-800 pb-3">
                                            <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                                                <span>🍰</span>
                                                <span>Chronological Edit History</span>
                                            </h3>
                                            <span className="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800">
                                                Layer-Cake Timeline
                                            </span>
                                        </div>

                                        <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar">
                                            {history.map((turn, i) => (
                                                <div
                                                    key={i}
                                                    onClick={() => {
                                                        setCurrentVideo(turn.videoUrl);
                                                        setParentTurnId(turn.turnId);
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

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        return HTMLResponse(content=UI_HTML)

    @app.post("/api/generate", response_model=GenerateResponse)
    def generate_video(req: GenerateRequest) -> GenerateResponse:
        res = agent.process_user_turn(
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
        )
        return GenerateResponse(
            success=res.success,
            status=res.status_event,
            video_url=res.video_url,
            turn_id=res.turn_id,
            depth=res.depth,
            error=res.error_message,
            raw_compiled_prompt=res.raw_compiled_prompt,
            reference_analysis=res.reference_analysis,
        )

    @app.post("/api/commit", response_model=GenerateResponse)
    def commit_and_branch(req: CommitRequest) -> GenerateResponse:
        res = agent.commit_and_branch(
            user_id=req.user_id,
            project_id=req.project_id,
            turn_id=req.turn_id,
            prompt=req.next_prompt,
            session_name=req.session_name,
        )
        return GenerateResponse(
            success=res.success,
            status=res.status_event,
            video_url=res.video_url,
            turn_id=res.turn_id,
            depth=res.depth,
            error=res.error_message,
            raw_compiled_prompt=res.raw_compiled_prompt,
            reference_analysis=res.reference_analysis,
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
