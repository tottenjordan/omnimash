from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent


class GenerateRequest(BaseModel):
    user_id: str
    project_id: str
    prompt: str
    clip_index: int = 0
    parent_turn_id: str | None = None


class CommitRequest(BaseModel):
    user_id: str
    project_id: str
    turn_id: str
    next_prompt: str = ""


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None


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
        const { useState } = React;

        const characterLoreAnchors = {
            snape: "Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair",
            dumbledore: "Albus Dumbledore, an elderly wizard with half-moon spectacles, long flowing silver beard, and ornate wizard robes",
            voldemort: "Lord Voldemort, a pale serpentine figure with slit-like nostrils, no hair, chalk-white skin, and piercing cold eyes",
            harry: "Harry Potter, a young man with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead"
        };

        const aestheticSignifiers = {
            "90s_rap_video": {
                wardrobe: "wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses",
                camera: "shot on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with green and purple neon rim lights",
                motion: "nodding rhythmically to a boom-bap beat while gesturing emphatically for a 10-second clip"
            },
            "trap_disstrack": {
                wardrobe: "wearing designer streetwear, iced-out medallions, and tinted aviator sunglasses",
                camera: "rapid visual jump cuts, dark moody 808 bass lighting, heavy laser smoke, and strobe flashes",
                motion: "aggressive lyrical hand gestures and slow walking toward the camera for 10 seconds"
            },
            "cyberpunk_drift": {
                wardrobe: "wearing a high-collar LED-lined techwear coat with holographic chrome accessories",
                camera: "anamorphic widescreen lens, rainy asphalt reflections, synthwave purple and cyan color grading",
                motion: "slowly turning to face the camera amidst falling digital rain for 10 seconds"
            },
            "vhs_anime": {
                wardrobe: "cel-shaded retro anime styling with oversized 80s shoulder pads and vintage headbands",
                camera: "retro 4:3 VHS tape grain, analog scanlines, chromatic aberration, and warm nostalgic bloom",
                motion: "classic limited-frame anime speech animation and dynamic wind blowing through hair for 10 seconds"
            }
        };

        function compilePromptPreview(rawPrompt, presetId) {
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

            return {
                subjectAnchor,
                aestheticInjection: style.wardrobe,
                environment,
                cameraLighting: style.camera,
                motion: style.motion
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
            const [selectedPreset, setSelectedPreset] = useState("90s_rap_video");
            const [parentTurnId, setParentTurnId] = useState("");
            const [loading, setLoading] = useState(false);
            const [status, setStatus] = useState("COMPLETED");
            const [showCommitModal, setShowCommitModal] = useState(false);
            const [commitPrompt, setCommitPrompt] = useState("");
            const [history, setHistory] = useState([
                { turnId: "turn_init", prompt: "Severus Snape in 90s rap video", status: "COMPLETED", videoUrl: "/static/rendered/mock.mp4", parent: null, is_checkpoint: false }
            ]);
            const [currentVideo, setCurrentVideo] = useState("/static/rendered/mock.mp4");

            const compiledPreview = compilePromptPreview(prompt, selectedPreset);

            const handleGenerate = async (e) => {
                e.preventDefault();
                setLoading(true);
                try {
                    const res = await fetch("/api/generate", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "usr_web",
                            project_id: "prj_mashup",
                            prompt: prompt,
                            clip_index: 0,
                            parent_turn_id: parentTurnId || null
                        })
                    });
                    const data = await res.json();
                    if (data.success) {
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
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
                                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                                    Style Presets
                                </h2>
                                <div className="grid grid-cols-2 gap-3">
                                    {stylePresets.map(preset => (
                                        <button
                                            key={preset.id}
                                            onClick={() => setSelectedPreset(preset.id)}
                                            className={`p-3 rounded-lg border text-left transition ${
                                                selectedPreset === preset.id
                                                    ? "bg-purple-950/60 border-purple-500 text-white"
                                                    : "bg-gray-800/40 border-gray-700/60 text-gray-400 hover:border-gray-600"
                                            }`}
                                        >
                                            <div className="text-xl mb-1">{preset.icon}</div>
                                            <div className="text-xs font-bold text-white">{preset.name}</div>
                                            <div className="text-[10px] text-gray-400 mt-1 line-clamp-2">{preset.desc}</div>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg flex flex-col">
                                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                                    Prompt Bar
                                </h2>
                                <form onSubmit={handleGenerate} className="flex flex-col space-y-4">
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">
                                            Active Prompt / Conversational Diff
                                        </label>
                                        <textarea
                                            rows="3"
                                            value={prompt}
                                            onChange={(e) => setPrompt(e.target.value)}
                                            placeholder="e.g. Add diamond chains and green neon lights..."
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm focus:outline-none focus:border-purple-500 text-white placeholder-gray-600"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-gray-400 mb-1">
                                            Parent Turn ID (Branching DAG Node)
                                        </label>
                                        <input
                                            type="text"
                                            value={parentTurnId}
                                            onChange={(e) => setParentTurnId(e.target.value)}
                                            placeholder="Leave empty for new root clip"
                                            className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600"
                                        />
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={loading || !prompt}
                                        className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-medium py-3 px-4 rounded-lg shadow-lg disabled:opacity-50 transition"
                                    >
                                        {loading ? "Generating Parody Clip..." : "Generate OmniMash Video"}
                                    </button>
                                </form>
                            </div>

                            {/* 🪄 5-Part Anchor & Inject Preview Card */}
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg space-y-3">
                                <div className="flex items-center justify-between">
                                    <h2 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                                        <span>🪄 5-Part Anchor &amp; Inject Preview</span>
                                    </h2>
                                    <span className="text-[10px] bg-purple-950 text-purple-400 px-2 py-0.5 rounded border border-purple-800 font-mono">
                                        Omni Flash Taxonomy
                                    </span>
                                </div>
                                <p className="text-[11px] text-gray-400">
                                    Live compilation of raw shorthand into rigid 5-part multimodal taxonomy to prevent character decay.
                                </p>
                                <div className="space-y-2 text-xs">
                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                        <span className="font-bold text-pink-400 font-mono">[SUBJECT ANCHOR]: </span>
                                        <span className="text-gray-300">{compiledPreview.subjectAnchor}</span>
                                    </div>
                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                        <span className="font-bold text-purple-400 font-mono">[AESTHETIC INJECTION]: </span>
                                        <span className="text-gray-300">{compiledPreview.aestheticInjection}</span>
                                    </div>
                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                        <span className="font-bold text-blue-400 font-mono">[ENVIRONMENT]: </span>
                                        <span className="text-gray-300">{compiledPreview.environment}</span>
                                    </div>
                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                        <span className="font-bold text-amber-400 font-mono">[CAMERA/LIGHTING]: </span>
                                        <span className="text-gray-300">{compiledPreview.cameraLighting}</span>
                                    </div>
                                    <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                                        <span className="font-bold text-emerald-400 font-mono">[MOTION]: </span>
                                        <span className="text-gray-300">{compiledPreview.motion}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="col-span-5 flex flex-col">
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg h-full flex flex-col">
                                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                                    Video Player
                                </h2>
                                <div className="flex-1 bg-black rounded-lg border border-gray-800 flex items-center justify-center relative overflow-hidden group">
                                    {currentVideo ? (
                                        <div className="w-full h-full flex flex-col items-center justify-center text-center p-6">
                                            <div className="w-16 h-16 rounded-full bg-purple-600/20 text-purple-400 flex items-center justify-center mb-4 border border-purple-500/30">
                                                ▶
                                            </div>
                                            <p className="text-sm font-mono text-purple-300">{currentVideo}</p>
                                            <span className="mt-2 text-xs text-gray-500">SynthID Watermark Verified</span>
                                        </div>
                                    ) : (
                                        <p className="text-gray-600 text-sm">No video rendered yet</p>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="col-span-3 flex flex-col">
                            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg h-full flex flex-col">
                                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                                    Timeline DAG Viewer
                                </h2>
                                <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                                    {history.map((node, idx) => {
                                        const isAnchor = node.is_checkpoint || node.status === "REANCHORED";
                                        return (
                                            <div
                                                key={node.turnId || idx}
                                                onClick={() => {
                                                    setParentTurnId(node.turnId);
                                                    if (node.videoUrl) setCurrentVideo(node.videoUrl);
                                                    if (node.status === "COMMIT_RECOMMENDED") {
                                                        setStatus("COMMIT_RECOMMENDED");
                                                        setShowCommitModal(true);
                                                    }
                                                }}
                                                className={`p-3 rounded-lg border cursor-pointer transition ${
                                                    parentTurnId === node.turnId
                                                        ? "bg-purple-950/40 border-purple-500"
                                                        : "bg-gray-950 border-gray-800 hover:border-gray-700"
                                                }`}
                                            >
                                                <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                                                    <span className="font-mono">{node.turnId || "Root"}</span>
                                                    <div className="flex items-center space-x-1">
                                                        {isAnchor && (
                                                            <span className="text-[10px] bg-green-950 text-green-400 px-1.5 py-0.5 rounded border border-green-700 flex items-center gap-1 font-medium shadow-sm">
                                                                <span>⚓</span>
                                                                <span>Checkpoint Anchor Badge</span>
                                                            </span>
                                                        )}
                                                        <span className="text-[10px] bg-green-950 text-green-400 px-1.5 py-0.5 rounded border border-green-800">
                                                            {node.status}
                                                        </span>
                                                    </div>
                                                </div>
                                                <p className="text-xs text-gray-200 line-clamp-2">{node.prompt}</p>
                                                {node.parent && (
                                                    <div className="mt-2 text-[10px] text-purple-400 flex items-center">
                                                        ↳ branch of {node.parent}
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


def create_app(mock_mode: bool = True) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0")
    agent = OmniMashAgent(mock_mode=mock_mode)

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
        )
        return GenerateResponse(
            success=res.success,
            status=res.status_event,
            video_url=res.video_url,
            turn_id=res.turn_id,
            depth=res.depth,
            error=res.error_message,
        )

    @app.post("/api/commit", response_model=GenerateResponse)
    def commit_turn(req: CommitRequest) -> GenerateResponse:
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
        )

    return app
