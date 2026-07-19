import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent


class GenerateRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    prompt: str
    clip_index: int = 0
    parent_turn_id: str | None = None
    reference_url: str | None = None
    audio_stem: str | None = None
    on_screen_text: str | None = None
    compiled_override: str | None = None


class CommitRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    turn_id: str
    next_prompt: str = ""


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None
    raw_compiled_prompt: str | None = None
    reference_analysis: dict | None = None


UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OmniMash Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body class="bg-gray-950 text-white font-sans antialiased min-h-screen">
    <div id="__next"></div>

    <script type="text/babel">
        const { useState, useEffect } = React;

        const characterLoreAnchors = {
            snape: "Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair",
            dumbledore: "Albus Dumbledore, an elderly wizard with half-moon spectacles, long flowing silver beard, and ornate wizard robes",
            voldemort: "Lord Voldemort, a pale serpentine figure with slit-like nostrils, no hair, chalk-white skin, and piercing cold eyes",
            harry: "Harry Potter, a young man with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead"
        };

        const aestheticSignifiers = {
            "90s_rap_video": {
                wardrobe: "wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses",
                camera: "In a single continuous shot, no scene cuts. Shot on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with green and purple neon rim lights",
                motion: "bopping head rhythmically to a 120 BPM beat while gesturing emphatically for a 10-second clip",
                audio: "120 BPM boom-bap hip-hop beat, vinyl scratch intro, punchy kick drum, crisp snare, and rhythmic rap cadence"
            },
            "trap_disstrack": {
                wardrobe: "wearing designer streetwear, iced-out medallions, and tinted aviator sunglasses",
                camera: "In a single continuous shot, dark moody 808 bass lighting, heavy laser smoke, and strobe flashes. No dialogue",
                motion: "aggressive lyrical hand gestures and slow walking toward the camera for 10 seconds",
                audio: "Muffled blown-out 808 sub-bass, rapid 16th-note trap hi-hat trills, and slow dark rap beat playing in the background"
            },
            "cyberpunk_drift": {
                wardrobe: "wearing a high-collar LED-lined techwear coat with holographic chrome accessories",
                camera: "In a single continuous shot, no scene cuts. Anamorphic widescreen lens, rainy asphalt reflections, synthwave purple and cyan color grading",
                motion: "slowly turning to face the camera amidst falling digital rain for 10 seconds",
                audio: "Synthesizer arpeggios, heavy analog synth bassline, and futuristic ambient cyberpunk drone"
            },
            "vhs_anime": {
                wardrobe: "cel-shaded retro anime styling with oversized 80s shoulder pads and vintage headbands",
                camera: "In a single continuous shot. Retro 4:3 VHS tape grain, analog scanlines, chromatic aberration, and warm nostalgic bloom",
                motion: "classic limited-frame anime speech animation and dynamic wind blowing through hair for 10 seconds",
                audio: "Retro 80s city pop brass samples, lo-fi cassette tape hiss, and upbeat Japanese synth melody"
            }
        };

        function compilePromptPreview(rawPrompt, presetId, customAudio, customText) {
            const lower = (rawPrompt || "").toLowerCase();
            let subjectAnchor = "A distinct cinematic character with sharp facial features and expressive eyes";
            for (const [key, desc] of Object.entries(characterLoreAnchors)) {
                if (lower.includes(key)) {
                    subjectAnchor = desc;
                    break;
                }
            }
            const style = aestheticSignifiers[presetId] || aestheticSignifiers["90s_rap_video"];
            const environment = "in a stone Hogwarts dungeon lit by atmospheric fog and ambient glow";
            const audioTrack = (customAudio && customAudio.trim().length > 0) ? customAudio.trim() : style.audio;
            const onScreenText = (customText && customText.trim().length > 0) ? customText.trim() : "";

            return {
                subjectAnchor,
                aestheticInjection: style.wardrobe,
                environment,
                cameraLighting: style.camera,
                motion: style.motion,
                audioTrack,
                onScreenText
            };
        }

        function compileDeltaPreview(deltaPrompt) {
            const instruction = deltaPrompt || "make his chain bigger";
            return {
                preservationLock: "Maintain exact subject face, character likeness, expression, wardrobe baseline, background environment, and audio stem rhythm from the previous turn.",
                isolatedDiff: `Alter only the specified element: ${instruction}. Do not modify any surrounding visual or audio features.`
            };
        }

        const stylePresets = [
            { id: "90s_rap_video", name: "90s Rap Video", icon: "🎤", desc: "Fisheye lens, boom-bap aesthetic, oversized bombers" },
            { id: "trap_disstrack", name: "Trap Disstrack", icon: "🔥", desc: "Dark 808 bass lighting, neon smoke, rapid cuts" },
            { id: "cyberpunk_drift", name: "Cyberpunk Drift", icon: "🏎️", desc: "Holographic neon glow, synthwave color grading" },
            { id: "vhs_anime", name: "VHS Anime", icon: "📼", desc: "Retro 4:3 VHS tape grain, analog scanlines" }
        ];

        function OmniMashApp() {
            const [prompt, setPrompt] = useState("");
            const [referenceUrl, setReferenceUrl] = useState("");
            const [audioStem, setAudioStem] = useState("");
            const [onScreenText, setOnScreenText] = useState("");
            const [selectedPreset, setSelectedPreset] = useState("90s_rap_video");
            const [parentTurnId, setParentTurnId] = useState("");
            const [loading, setLoading] = useState(false);
            const [status, setStatus] = useState("COMPLETED");
            const [showCommitModal, setShowCommitModal] = useState(false);
            const [commitPrompt, setCommitPrompt] = useState("");

            // Reference Analysis & Raw Payload State
            const [referenceAnalysis, setReferenceAnalysis] = useState(null);
            const [rawCompiledPrompt, setRawCompiledPrompt] = useState("");
            const [isRawPayloadOpen, setIsRawPayloadOpen] = useState(true);
            const [copied, setCopied] = useState(false);
            
            // Editable Prompt Compiler Previews
            const [editableParts, setEditableParts] = useState(compilePromptPreview("", "90s_rap_video", "", ""));
            const [editableDelta, setEditableDelta] = useState(compileDeltaPreview(""));
            const [isCustomEdited, setIsCustomEdited] = useState(false);

            const [history, setHistory] = useState([
                { turnId: "turn_init", prompt: "Severus Snape in 90s rap video", status: "COMPLETED", videoUrl: "/static/rendered/mock.mp4", parent: null, is_checkpoint: false }
            ]);
            const [currentVideo, setCurrentVideo] = useState("/static/rendered/mock.mp4");

            const selectedParentTurnId = parentTurnId;

            const defaultAnalysis = {
                video_title: "Reference Beat & Character Baseline",
                duration_seconds: 180,
                detected_bpm: 120,
                dominant_colors: ["#1B2A4A", "#0B6623", "#D4AF37"],
                extracted_keyframes: [
                    {
                        timestamp: "00:02",
                        image_url: "/tmp/mock_frame_1.jpg",
                        usage_annotation: "🎯 [SUBJECT ANCHOR]: Conditioning facial likeness, expression, and hair baseline."
                    },
                    {
                        timestamp: "00:15",
                        image_url: "/tmp/mock_frame_2.jpg",
                        usage_annotation: "🧥 [AESTHETIC BASELINE]: Reference for lighting contrast and initial character wardrobe."
                    },
                    {
                        timestamp: "00:30",
                        image_url: "/tmp/mock_frame_3.jpg",
                        usage_annotation: "🎵 [ACOUSTIC STEM]: Tempo reference extracted for 120 BPM audio track synchronization."
                    }
                ]
            };

            const activeAnalysis = referenceAnalysis || ((referenceUrl && referenceUrl.trim().length > 0) ? defaultAnalysis : null);

            useEffect(() => {
                if (!isCustomEdited) {
                    setEditableParts(compilePromptPreview(prompt, selectedPreset, audioStem, onScreenText));
                    setEditableDelta(compileDeltaPreview(prompt));
                }
            }, [prompt, selectedPreset, audioStem, onScreenText, isCustomEdited]);

            const handleResetAutoCompile = () => {
                setIsCustomEdited(false);
                setEditableParts(compilePromptPreview(prompt, selectedPreset, audioStem, onScreenText));
                setEditableDelta(compileDeltaPreview(prompt));
            };

            const handlePartChange = (field, val) => {
                setIsCustomEdited(true);
                setEditableParts(prev => ({ ...prev, [field]: val }));
            };

            const handleDeltaChange = (field, val) => {
                setIsCustomEdited(true);
                setEditableDelta(prev => ({ ...prev, [field]: val }));
            };

            const textDirective = (editableParts.onScreenText && editableParts.onScreenText.trim().length > 0)
                ? `On-screen text: '${editableParts.onScreenText.trim()}'`
                : "No text, no subtitles, no captions on screen";

            const currentCompiledPrompt = selectedParentTurnId
                ? `Apply conversational diff to the existing video latent space using Lock & Isolate: [PRESERVATION LOCK]: ${editableDelta.preservationLock} | [ISOLATED DIFF]: ${editableDelta.isolatedDiff}`
                : `Generate a 720p 10-second cinematic parody video with native audio using the Anchor & Inject framework: [SUBJECT ANCHOR]: ${editableParts.subjectAnchor} | [AESTHETIC INJECTION]: ${editableParts.aestheticInjection} | [ENVIRONMENT]: ${editableParts.environment} | [CAMERA/LIGHTING]: ${editableParts.cameraLighting} | [MOTION]: ${editableParts.motion} | [AUDIO TRACK]: ${editableParts.audioTrack} | Sound design: ${editableParts.audioTrack}. ${textDirective}.`;

            const displayRawPrompt = rawCompiledPrompt || currentCompiledPrompt;

            const handleCopyRawPrompt = () => {
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(displayRawPrompt);
                }
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            };

            const handleGenerate = async (e) => {
                e.preventDefault();
                setLoading(true);
                try {
                    const compiledOverride = selectedParentTurnId
                        ? `[PRESERVATION LOCK]: ${editableDelta.preservationLock} | [ISOLATED DIFF]: ${editableDelta.isolatedDiff}`
                        : `[SUBJECT ANCHOR]: ${editableParts.subjectAnchor} | [AESTHETIC INJECTION]: ${editableParts.aestheticInjection} | [ENVIRONMENT]: ${editableParts.environment} | [CAMERA/LIGHTING]: ${editableParts.cameraLighting} | [MOTION]: ${editableParts.motion} | [AUDIO TRACK]: ${editableParts.audioTrack} | Sound design: ${editableParts.audioTrack}. ${textDirective}.`;

                    const res = await fetch("/api/generate", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "usr_web",
                            project_id: "prj_mashup",
                            prompt: prompt,
                            clip_index: 0,
                            parent_turn_id: parentTurnId || null,
                            reference_url: referenceUrl || null,
                            audio_stem: audioStem || null,
                            on_screen_text: onScreenText || null,
                            compiled_override: compiledOverride
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        if (data.reference_analysis) {
                            setReferenceAnalysis(data.reference_analysis);
                        }
                        if (data.raw_compiled_prompt) {
                            setRawCompiledPrompt(data.raw_compiled_prompt);
                        }
                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: prompt,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            is_checkpoint: data.status === "REANCHORED"
                        };
                        setHistory(prev => [...prev, newTurn]);
                        setCurrentVideo(data.video_url);
                        setParentTurnId(data.turn_id);
                        setStatus(data.status);
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

            const handleCommit = async () => {
                setLoading(true);
                try {
                    const nextPrompt = commitPrompt || prompt || "Re-anchored checkpoint";
                    const res = await fetch("/api/commit", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "usr_web",
                            project_id: "prj_mashup",
                            turn_id: parentTurnId,
                            next_prompt: nextPrompt
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
                        if (data.reference_analysis) {
                            setReferenceAnalysis(data.reference_analysis);
                        }
                        if (data.raw_compiled_prompt) {
                            setRawCompiledPrompt(data.raw_compiled_prompt);
                        }
                        const newTurn = {
                            turnId: data.turn_id,
                            prompt: nextPrompt,
                            status: data.status,
                            videoUrl: data.video_url,
                            parent: parentTurnId || null,
                            is_checkpoint: true
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
                <div className="flex flex-col h-screen relative">
                    {/* Commit & Re-Anchor Warning Banner Modal */}
                    {isCommitModalVisible && (
                        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                            <div className="bg-gray-900 border-2 border-amber-500/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
                                <div className="flex items-center space-x-3 bg-amber-950/80 border border-amber-500/50 rounded-xl p-4 mb-5 text-amber-300">
                                    <span className="text-2xl">⚠️</span>
                                    <div>
                                        <h3 className="font-bold text-base text-amber-200">Commit &amp; Re-Anchor</h3>
                                        <p className="text-xs text-amber-300/80 mt-0.5">Edit depth limit reached (Depth &ge; 3). Re-anchoring preserves prompt fidelity and video quality.</p>
                                    </div>
                                </div>

                                <div className="space-y-4 mb-6">
                                    <p className="text-sm text-gray-300">
                                        You have made 3 consecutive conversational edits on this thread. To prevent multimodal video drift and context decay, commit your changes now to create a fresh video keyframe anchor.
                                    </p>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">
                                            Next Prompt / Re-Anchor Prompt
                                        </label>
                                        <input
                                            type="text"
                                            value={commitPrompt}
                                            onChange={(e) => setCommitPrompt(e.target.value)}
                                            placeholder="e.g. Reanchored turn checkpoint..."
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500"
                                        />
                                    </div>
                                </div>

                                <div className="flex items-center justify-end space-x-3">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowCommitModal(false);
                                            if (status === "COMMIT_RECOMMENDED") {
                                                setStatus("DISMISSED_WARNING");
                                            }
                                        }}
                                        className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white transition"
                                    >
                                        Dismiss
                                    </button>
                                    <button
                                        type="button"
                                        disabled={loading}
                                        onClick={handleCommit}
                                        className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-black font-bold text-xs py-2.5 px-5 rounded-lg shadow-lg flex items-center gap-2 transition disabled:opacity-50"
                                    >
                                        <span>⚓</span>
                                        <span>{loading ? "Committing..." : "Commit & Re-Anchor"}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur px-6 py-4 flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <span className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
                                OmniMash
                            </span>
                            <span className="text-xs bg-purple-900/60 text-purple-300 px-2 py-0.5 rounded-full border border-purple-700">
                                Next.js + React Dashboard
                            </span>
                        </div>
                    </header>

                    <main className="flex-1 grid grid-cols-12 gap-6 p-6 overflow-hidden">
                        <div className="col-span-4 flex flex-col space-y-6 overflow-y-auto pr-1">
                            {/* Style Presets */}
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
                                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                                    Style Presets
                                </h2>
                                <div className="grid grid-cols-2 gap-3">
                                    {stylePresets.map(preset => (
                                        <button
                                            key={preset.id}
                                            onClick={() => {
                                                setSelectedPreset(preset.id);
                                                setIsCustomEdited(false);
                                            }}
                                            className={`p-3 rounded-lg border text-left transition flex flex-col justify-between ${
                                                selectedPreset === preset.id
                                                    ? "border-purple-500 bg-purple-950/40 text-purple-200"
                                                    : "border-gray-800 hover:border-gray-700 bg-gray-950 text-gray-400"
                                            }`}
                                        >
                                            <div className="text-xl mb-1">{preset.icon}</div>
                                            <div className="font-semibold text-xs">{preset.name}</div>
                                            <div className="text-[10px] text-gray-500 line-clamp-2 mt-1">{preset.desc}</div>
                                        </button>
                                    ))}
                                </div>

                                {/* Style Preset Contribution Inspector */}
                                <div className="mt-4 pt-4 border-t border-gray-800 space-y-2">
                                    <div className="flex items-center justify-between">
                                        <h3 className="text-xs font-semibold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
                                            <span>🔍 Style Preset Contribution Inspector</span>
                                        </h3>
                                        <span className="text-[10px] bg-purple-950/80 text-purple-300 px-2 py-0.5 rounded border border-purple-800/80 font-mono">
                                            {selectedPreset}
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 space-y-1">
                                            <span className="font-bold text-pink-400 flex items-center gap-1">
                                                <span>👔</span> Wardrobe
                                            </span>
                                            <p className="text-gray-400 text-[10px] leading-tight">
                                                {aestheticSignifiers[selectedPreset]?.wardrobe}
                                            </p>
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 space-y-1">
                                            <span className="font-bold text-amber-400 flex items-center gap-1">
                                                <span>🎥</span> Camera / Lighting
                                            </span>
                                            <p className="text-gray-400 text-[10px] leading-tight">
                                                {aestheticSignifiers[selectedPreset]?.camera}
                                            </p>
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 space-y-1">
                                            <span className="font-bold text-emerald-400 flex items-center gap-1">
                                                <span>🏃</span> Motion
                                            </span>
                                            <p className="text-gray-400 text-[10px] leading-tight">
                                                {aestheticSignifiers[selectedPreset]?.motion}
                                            </p>
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800 space-y-1">
                                            <span className="font-bold text-teal-400 flex items-center gap-1">
                                                <span>🎵</span> Sound Design
                                            </span>
                                            <p className="text-gray-400 text-[10px] leading-tight">
                                                {aestheticSignifiers[selectedPreset]?.audio}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* UI Input Controls (Separated Inputs) */}
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
                                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                                    Prompt &amp; Multimodal Inputs
                                </h2>
                                <form onSubmit={handleGenerate} className="space-y-4">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                                            Creative Concept / Parody Prompt
                                        </label>
                                        <textarea
                                            rows={2}
                                            value={prompt}
                                            onChange={(e) => setPrompt(e.target.value)}
                                            placeholder="e.g. Severus Snape rapping in 90s rap video, or make his chain bigger"
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600 focus:border-purple-500 focus:outline-none"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1 flex items-center justify-between">
                                            <span>🎥 1. Reference YouTube URL</span>
                                            <span className="text-[10px] text-gray-500 font-normal">extracts portrait keyframes</span>
                                        </label>
                                        <input
                                            type="url"
                                            value={referenceUrl}
                                            onChange={(e) => setReferenceUrl(e.target.value)}
                                            placeholder="https://www.youtube.com/watch?v=sample_character"
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600 focus:border-purple-500 focus:outline-none font-mono"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1 flex items-center justify-between">
                                            <span>🎵 2. Audio Stem / Sound Design</span>
                                            <span className="text-[10px] text-gray-500 font-normal">acoustic BPM &amp; tempo</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={audioStem}
                                            onChange={(e) => setAudioStem(e.target.value)}
                                            placeholder="e.g. 140 BPM UK Drill 808s, or 120 BPM Boom-Bap..."
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600 focus:border-teal-500 focus:outline-none"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1 flex items-center justify-between">
                                            <span>📝 3. On-Screen Text / Subtitles (Optional)</span>
                                            <span className="text-[10px] text-gray-500 font-normal">captions, titles, lyrics</span>
                                        </label>
                                        <input
                                            type="text"
                                            value={onScreenText}
                                            onChange={(e) => setOnScreenText(e.target.value)}
                                            placeholder="e.g. SNAPE 1994, lyrics, or leave empty for clean video..."
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600 focus:border-amber-500 focus:outline-none"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">
                                            Parent Turn ID (for Conversational Diffs)
                                        </label>
                                        <input
                                            type="text"
                                            value={parentTurnId}
                                            onChange={(e) => setParentTurnId(e.target.value)}
                                            placeholder="Leave empty for new root clip"
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600 font-mono"
                                        />
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={loading || !prompt}
                                        className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-medium py-3 px-4 rounded-lg shadow-lg disabled:opacity-50 transition flex items-center justify-center gap-2"
                                    >
                                        <span>{loading ? "🎬 Rendering 720p Video..." : "🎬 Generate Parody Clip"}</span>
                                    </button>
                                </form>
                            </div>

                            {/* 🪄 6-Part Anchor & Inject Preview / Delta Lock & Isolate Preview Card (DIRECTLY EDITABLE) */}
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg space-y-3">
                                <div className="flex items-center justify-between">
                                    <h2 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                                        <span>{selectedParentTurnId ? "🪄 Delta Prompt Tuning (Lock & Isolate)" : "🪄 6-Part Anchor & Inject Prompt Tuning"}</span>
                                    </h2>
                                    <div className="flex items-center gap-2">
                                        {isCustomEdited ? (
                                            <button
                                                type="button"
                                                onClick={handleResetAutoCompile}
                                                className="text-[10px] bg-amber-950 text-amber-300 px-2 py-0.5 rounded border border-amber-800 font-medium hover:bg-amber-900 transition"
                                            >
                                                🔄 Reset Auto-Compile
                                            </button>
                                        ) : (
                                            <span className="text-[10px] bg-green-950 text-green-300 px-2 py-0.5 rounded border border-green-800 font-medium">
                                                ✨ Auto-Compiled (Click to Edit)
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <p className="text-[11px] text-gray-400">
                                    {selectedParentTurnId
                                        ? "Directly edit the lock or isolated diff before generating to enforce precise conversational diffing."
                                        : "Directly edit any of the 6 compiled taxonomy fields or on-screen subtitles to tune the prompt before generation."}
                                </p>

                                {selectedParentTurnId ? (
                                    <div className="space-y-3 text-xs">
                                        <div className="bg-gray-950 p-3 rounded-lg border border-amber-500/40 space-y-1.5 shadow-sm">
                                            <div className="flex items-center justify-between">
                                                <span className="font-bold text-amber-300 font-mono flex items-center gap-1.5">
                                                    <span>🔒 [PRESERVATION LOCK]</span>
                                                </span>
                                                <span className="text-[10px] bg-amber-950/80 text-amber-300 px-2 py-0.5 rounded border border-amber-700/60 font-medium">
                                                    Editable Lock
                                                </span>
                                            </div>
                                            <textarea
                                                rows={2}
                                                value={editableDelta.preservationLock}
                                                onChange={(e) => handleDeltaChange("preservationLock", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-2 text-gray-200 text-[11px] font-mono focus:border-amber-400 focus:outline-none"
                                            />
                                        </div>

                                        <div className="bg-gray-950 p-3 rounded-lg border border-purple-500/40 space-y-1.5 shadow-sm">
                                            <div className="flex items-center justify-between">
                                                <span className="font-bold text-purple-300 font-mono flex items-center gap-1.5">
                                                    <span>🎯 [ISOLATED DIFF]</span>
                                                </span>
                                                <span className="text-[10px] bg-purple-950/80 text-purple-300 px-2 py-0.5 rounded border border-purple-700/60 font-medium">
                                                    Editable Diff
                                                </span>
                                            </div>
                                            <textarea
                                                rows={2}
                                                value={editableDelta.isolatedDiff}
                                                onChange={(e) => handleDeltaChange("isolatedDiff", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-2 text-gray-200 text-[11px] font-mono focus:border-purple-400 focus:outline-none"
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    <div className="space-y-2.5 text-xs">
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-pink-400 font-mono block mb-1">[SUBJECT ANCHOR]: </span>
                                            <textarea
                                                rows={2}
                                                value={editableParts.subjectAnchor}
                                                onChange={(e) => handlePartChange("subjectAnchor", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-pink-500 focus:outline-none"
                                            />
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-purple-400 font-mono block mb-1">[AESTHETIC INJECTION]: </span>
                                            <textarea
                                                rows={2}
                                                value={editableParts.aestheticInjection}
                                                onChange={(e) => handlePartChange("aestheticInjection", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-purple-500 focus:outline-none"
                                            />
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-blue-400 font-mono block mb-1">[ENVIRONMENT]: </span>
                                            <input
                                                type="text"
                                                value={editableParts.environment}
                                                onChange={(e) => handlePartChange("environment", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-blue-500 focus:outline-none"
                                            />
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-amber-400 font-mono block mb-1">[CAMERA/LIGHTING]: </span>
                                            <textarea
                                                rows={2}
                                                value={editableParts.cameraLighting}
                                                onChange={(e) => handlePartChange("cameraLighting", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-amber-500 focus:outline-none"
                                            />
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-emerald-400 font-mono block mb-1">[MOTION]: </span>
                                            <input
                                                type="text"
                                                value={editableParts.motion}
                                                onChange={(e) => handlePartChange("motion", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-emerald-500 focus:outline-none"
                                            />
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-teal-400 font-mono block mb-1">[AUDIO SOUND DESIGN]: </span>
                                            <input
                                                type="text"
                                                value={editableParts.audioTrack}
                                                onChange={(e) => handlePartChange("audioTrack", e.target.value)}
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-teal-500 focus:outline-none"
                                            />
                                        </div>
                                        <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                            <span className="font-bold text-amber-300 font-mono block mb-1">[ON-SCREEN TEXT / SUBTITLES]: </span>
                                            <input
                                                type="text"
                                                value={editableParts.onScreenText}
                                                onChange={(e) => handlePartChange("onScreenText", e.target.value)}
                                                placeholder="Leave empty for clean video without captions"
                                                className="w-full bg-black/80 border border-gray-800 rounded p-1.5 text-gray-300 text-[11px] focus:border-amber-400 focus:outline-none"
                                            />
                                        </div>
                                    </div>
                                )}

                                {/* Raw Compiled Model Payload Container */}
                                <div className="mt-4 pt-4 border-t border-gray-800 space-y-2">
                                    <div className="flex items-center justify-between">
                                        <button
                                            type="button"
                                            onClick={() => setIsRawPayloadOpen(!isRawPayloadOpen)}
                                            className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-2 hover:text-emerald-300 transition"
                                        >
                                            <span>{isRawPayloadOpen ? "▼" : "▶"}</span>
                                            <span>📦 Raw Compiled Model Payload (gemini-omni-flash-preview)</span>
                                        </button>
                                        <button
                                            type="button"
                                            onClick={handleCopyRawPrompt}
                                            className="text-[10px] bg-emerald-950 text-emerald-300 hover:bg-emerald-900 px-2.5 py-1 rounded border border-emerald-700/80 font-mono transition flex items-center gap-1"
                                        >
                                            <span>{copied ? "✓ Copied!" : "📋 Copy Raw Prompt"}</span>
                                        </button>
                                    </div>
                                    {isRawPayloadOpen && (
                                        <div className="bg-black/90 p-3 rounded-lg border border-emerald-500/40 shadow-inner">
                                            <pre className="font-mono text-[10px] text-emerald-300 whitespace-pre-wrap break-all leading-relaxed select-all">
                                                {displayRawPrompt}
                                            </pre>
                                        </div>
                                    )}
                                </div>
                            </div>

                        </div>

                        <div className="col-span-5 flex flex-col space-y-6 overflow-y-auto pr-1">
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg flex flex-col">
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                                        Video Player
                                    </h2>
                                    {currentVideo && (
                                        <a
                                            href={currentVideo}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-xs text-purple-400 hover:text-purple-300 underline font-mono flex items-center gap-1"
                                        >
                                            <span>↗</span> Fullscreen / Direct MP4
                                        </a>
                                    )}
                                </div>
                                <div className="bg-black rounded-lg border border-gray-800 flex flex-col items-center justify-center relative overflow-hidden group p-3 min-h-[300px]">
                                    {currentVideo ? (
                                        <div className="w-full flex flex-col items-center justify-center">
                                            <video
                                                key={currentVideo}
                                                controls
                                                autoPlay
                                                loop
                                                className="max-h-[380px] w-auto rounded shadow-2xl object-contain border border-gray-900"
                                            >
                                                <source src={currentVideo} type="video/mp4" />
                                                Your browser does not support the video tag.
                                            </video>
                                        </div>
                                    ) : (
                                        <div className="text-center text-gray-600 space-y-2">
                                            <div className="text-4xl">🎬</div>
                                            <div className="text-xs">No video rendered yet. Choose a preset or prompt to begin.</div>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Ingested YouTube Reference Analysis & Keyframes Gallery */}
                            {activeAnalysis && (
                                <div className="bg-gray-900 border border-teal-800/80 rounded-xl p-5 shadow-lg space-y-4">
                                    {/* Ingested Analysis Card Header & Badges */}
                                    <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-gray-800">
                                        <div className="space-y-0.5">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-semibold text-teal-300 uppercase tracking-wider flex items-center gap-1.5">
                                                    <span>📊</span> Ingested YouTube Reference Analysis
                                                </span>
                                            </div>
                                            <div className="text-xs text-gray-400 font-medium">
                                                {activeAnalysis.video_title} ({activeAnalysis.duration_seconds}s)
                                            </div>
                                        </div>
                                        
                                        <div className="flex items-center gap-3">
                                            {/* Detected BPM Badge */}
                                            <span className="bg-teal-950 text-teal-300 border border-teal-600 px-3 py-1 rounded-full text-xs font-mono font-bold flex items-center gap-1.5 shadow">
                                                <span>🎵</span> {activeAnalysis.detected_bpm} BPM
                                            </span>

                                            {/* Dominant Hex Color Palette Swatches */}
                                            <div className="flex items-center gap-1.5 bg-gray-950 p-1.5 rounded-lg border border-gray-800">
                                                <span className="text-[10px] text-gray-400 font-semibold uppercase mr-1">Palette:</span>
                                                {activeAnalysis.dominant_colors.map((hex, idx) => (
                                                    <div key={idx} className="flex items-center gap-1" title={hex}>
                                                        <div
                                                            style={{ backgroundColor: hex }}
                                                            className="w-4 h-4 rounded-full border border-white/30 shadow-inner"
                                                        />
                                                        <span className="text-[9px] font-mono text-gray-300 hidden sm:inline">{hex}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Extracted Reference Keyframes Gallery */}
                                    <div>
                                        <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                                            <span>🖼️ Extracted Reference Keyframes Gallery &amp; Usage Annotations</span>
                                        </h3>
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                            {activeAnalysis.extracted_keyframes.map((frame, idx) => {
                                                const isAnchor = frame.usage_annotation.includes("SUBJECT ANCHOR");
                                                const isBaseline = frame.usage_annotation.includes("AESTHETIC BASELINE");
                                                const isStem = frame.usage_annotation.includes("ACOUSTIC STEM");

                                                return (
                                                    <div
                                                        key={idx}
                                                        className={`p-3 rounded-lg border flex flex-col justify-between space-y-2 bg-gray-950 ${
                                                            isAnchor
                                                                ? "border-pink-500/50"
                                                                : isBaseline
                                                                ? "border-purple-500/50"
                                                                : "border-teal-500/50"
                                                        }`}
                                                    >
                                                        {/* Keyframe Thumbnail Container */}
                                                        <div className="h-24 bg-gradient-to-br from-gray-900 to-black rounded border border-gray-800 flex flex-col items-center justify-center relative overflow-hidden group">
                                                            <span className="text-3xl opacity-60">🎬</span>
                                                            <span className="text-[10px] font-mono text-gray-400 mt-1">
                                                                Frame {idx + 1} ({frame.timestamp})
                                                            </span>
                                                            <div className="absolute top-1 left-1 bg-black/80 px-1.5 py-0.5 rounded text-[9px] font-mono text-gray-300 border border-gray-800">
                                                                ⏱️ {frame.timestamp}
                                                            </div>
                                                        </div>

                                                        {/* Keyframe Usage Annotation & Badges */}
                                                        <div className="space-y-1.5">
                                                            <div className="flex items-center gap-1 flex-wrap">
                                                                {isAnchor && (
                                                                    <span className="text-[9px] bg-pink-950 text-pink-300 px-2 py-0.5 rounded border border-pink-700/80 font-bold font-mono">
                                                                        🎯 [SUBJECT ANCHOR]
                                                                    </span>
                                                                )}
                                                                {isBaseline && (
                                                                    <span className="text-[9px] bg-purple-950 text-purple-300 px-2 py-0.5 rounded border border-purple-700/80 font-bold font-mono">
                                                                        🧥 [AESTHETIC BASELINE]
                                                                    </span>
                                                                )}
                                                                {isStem && (
                                                                    <span className="text-[9px] bg-teal-950 text-teal-300 px-2 py-0.5 rounded border border-teal-700/80 font-bold font-mono">
                                                                        🎵 [ACOUSTIC STEM]
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <p className="text-[10px] text-gray-300 leading-relaxed font-sans">
                                                                {frame.usage_annotation}
                                                            </p>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="col-span-3 flex flex-col space-y-6 overflow-y-auto">
                            {/* Version Tree DAG */}
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg flex-1 flex flex-col">
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                                        Version Tree DAG
                                    </h2>
                                    <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full font-mono">
                                        {history.length} Clips
                                    </span>
                                </div>
                                <div className="space-y-3 flex-1 overflow-y-auto pr-1">
                                    {history.map((item, idx) => {
                                        const isCurrent = currentVideo === item.videoUrl;
                                        return (
                                            <div
                                                key={item.turnId}
                                                onClick={() => {
                                                    setCurrentVideo(item.videoUrl);
                                                    setParentTurnId(item.turnId);
                                                }}
                                                className={`p-3 rounded-lg border cursor-pointer transition relative text-xs ${
                                                    isCurrent
                                                        ? "border-purple-500 bg-purple-950/30"
                                                        : "border-gray-800 hover:border-gray-700 bg-gray-950"
                                                }`}
                                            >
                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="font-mono text-[10px] text-gray-500">
                                                        Turn #{idx + 1}
                                                    </span>
                                                    <div className="flex items-center gap-1">
                                                        {item.is_checkpoint && (
                                                            <span className="text-[9px] bg-amber-950 text-amber-400 px-1.5 py-0.5 rounded border border-amber-800 font-bold">
                                                                ⚓ Checkpoint Anchor
                                                            </span>
                                                        )}
                                                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                                                            item.status === "COMPLETED" || item.status === "REANCHORED"
                                                                ? "bg-green-950 text-green-400"
                                                                : item.status === "COMMIT_RECOMMENDED"
                                                                ? "bg-amber-950 text-amber-400"
                                                                : "bg-red-950 text-red-400"
                                                        }`}>
                                                            {item.status}
                                                        </span>
                                                    </div>
                                                </div>
                                                <div className="text-gray-300 font-medium line-clamp-2">
                                                    {item.prompt}
                                                </div>
                                                {item.parent && (
                                                    <div className="text-[10px] text-gray-600 font-mono mt-1">
                                                        ↳ diff from: {item.parent}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
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
            on_screen_text=req.on_screen_text,
            compiled_override=req.compiled_override,
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

    return app
