import base64
import os
import subprocess
from PIL import Image

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_DIR)

if not os.path.exists("/tmp/tailwind.js"):
    subprocess.run(
        ["curl", "-sL", "https://cdn.tailwindcss.com", "-o", "/tmp/tailwind.js"],
        check=False,
    )

frame_path = "/tmp/live_trap_frame.jpg"
if not os.path.exists(frame_path):
    frame_path = "/tmp/live_omni_frame_1.jpg"

with open(frame_path, "rb") as f:
    frame_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")

os.makedirs("imgs", exist_ok=True)
os.makedirs("/tmp/readme_html", exist_ok=True)


def get_html(act_num: int, content_body: str) -> str:
    tab1_cls = (
        "bg-gradient-to-r from-amber-500 to-orange-600 text-black shadow-lg shadow-orange-500/30"
        if act_num == 1
        else "text-gray-400 bg-gray-950/50"
    )
    tab2_cls = (
        "bg-gradient-to-r from-amber-500 to-orange-600 text-black shadow-lg shadow-orange-500/30"
        if act_num == 2
        else "text-gray-400 bg-gray-950/50"
    )
    tab3_cls = (
        "bg-gradient-to-r from-amber-500 to-orange-600 text-black shadow-lg shadow-orange-500/30"
        if act_num == 3
        else "text-gray-400 bg-gray-950/50"
    )

    template = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <title>OmniMash Digital Director's Studio</title>
    <script src="file:///tmp/tailwind.js"></script>
    <style>
        body { background-color: #030712; color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
    </style>
</head>
<body class="p-6 bg-gray-950 text-gray-100 min-h-screen">
    <div class="max-w-7xl mx-auto space-y-5">
        <header class="bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-2xl flex items-center justify-between">
            <div class="flex items-center space-x-4">
                <div class="w-11 h-11 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-purple-700 flex items-center justify-center text-2xl shadow-lg shadow-orange-500/20">
                    🎬
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h1 class="text-lg font-black tracking-tight text-white">OmniMash Digital Director's Studio</h1>
                        <span class="text-[10px] bg-purple-900/60 text-purple-300 border border-purple-700 px-2 py-0.5 rounded-full font-mono font-bold">
                            gemini-omni-flash-preview
                        </span>
                    </div>
                    <p class="text-xs text-gray-400 mt-0.5">
                        Native Joint Audio-Video Parody Engine • Atlanta Trap Disstrack Edition
                    </p>
                </div>
            </div>
            <div class="flex items-center space-x-3">
                <button class="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-xl px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 shadow-sm">
                    <span>🔄 New Project / Start Over</span>
                </button>
                <div class="flex items-center gap-2 bg-gray-950 border border-green-800/80 px-3 py-1.5 rounded-xl shadow-inner">
                    <span class="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
                    <span class="text-xs font-bold text-green-400 font-mono">🟢 Live Gemini Omni Flash (720p + Synced Audio)</span>
                </div>
                <div class="bg-gray-950 border border-gray-800 px-3 py-1.5 rounded-xl text-xs font-mono text-amber-400">
                    Session: trap_or_die_v1
                </div>
            </div>
        </header>

        <nav class="grid grid-cols-3 gap-3 bg-gray-900/90 border border-gray-800 p-1.5 rounded-2xl shadow-lg">
            <div class="py-2.5 px-4 rounded-xl text-center font-bold text-xs transition flex items-center justify-center gap-2 __TAB1__">
                <span>🪄</span>
                <span>Act 1: Concept &amp; Cast</span>
            </div>
            <div class="py-2.5 px-4 rounded-xl text-center font-bold text-xs transition flex items-center justify-center gap-2 __TAB2__">
                <span>📝</span>
                <span>Act 2: Storyboard Directing</span>
            </div>
            <div class="py-2.5 px-4 rounded-xl text-center font-bold text-xs transition flex items-center justify-center gap-2 __TAB3__">
                <span>🎬</span>
                <span>Act 3: Screening Room &amp; Branching</span>
            </div>
        </nav>

        <main>
            __CONTENT__
        </main>
    </div>
</body>
</html>"""
    return (
        template.replace("__TAB1__", tab1_cls)
        .replace("__TAB2__", tab2_cls)
        .replace("__TAB3__", tab3_cls)
        .replace("__CONTENT__", content_body)
    )


act1_content = """
<div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
    <div class="lg:col-span-8 space-y-4">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div class="flex items-center justify-between border-b border-gray-800 pb-2.5">
                <h2 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                    <span>💡</span><span>Open-Ended Concept &amp; NLP Deconstruction</span>
                </h2>
                <span class="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800 font-mono">
                    POST /api/deconstruct-concept
                </span>
            </div>
            <div>
                <label class="block text-[11px] font-semibold text-gray-400 mb-1.5 font-mono">PARODY CONCEPT SHORTHAND</label>
                <div class="flex gap-3">
                    <input type="text" readonly value="Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style" class="flex-1 bg-gray-950 border border-amber-500/50 rounded-xl p-2.5 text-xs text-white font-medium shadow-inner" />
                    <button class="bg-gradient-to-r from-amber-500 to-orange-600 text-black font-bold text-xs px-4 py-2.5 rounded-xl shadow-lg flex items-center gap-1.5">
                        <span>✨</span><span>Deconstruct</span>
                    </button>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-3 pt-1">
                <div class="bg-gray-950 p-3 rounded-xl border border-gray-800 space-y-1.5">
                    <span class="text-[10px] font-mono font-bold text-purple-400 uppercase">GLOBAL AESTHETIC TAGS</span>
                    <div class="flex flex-wrap gap-1">
                        <span class="bg-purple-950/80 text-purple-300 border border-purple-800 text-[10px] px-2 py-0.5 rounded">2000s Atlanta Trap Disstrack</span>
                        <span class="bg-purple-950/80 text-purple-300 border border-purple-800 text-[10px] px-2 py-0.5 rounded">Heavy 808 Bass Lighting</span>
                        <span class="bg-purple-950/80 text-purple-300 border border-purple-800 text-[10px] px-2 py-0.5 rounded">Vintage Streetwear</span>
                    </div>
                </div>
                <div class="bg-gray-950 p-3 rounded-xl border border-gray-800 space-y-1.5">
                    <span class="text-[10px] font-mono font-bold text-amber-400 uppercase">ENVIRONMENT &amp; AUDIO DIRECTION</span>
                    <div class="space-y-1 text-[11px] text-gray-300">
                        <p><strong class="text-gray-400">Environment:</strong> Abandoned house with potion stoves</p>
                        <p><strong class="text-gray-400">Audio Beat:</strong> <span class="bg-amber-950 text-amber-300 px-1.5 py-0.5 rounded font-mono text-[10px] border border-amber-800">140 BPM Heavy 808 Trap</span></p>
                        <div class="pt-1">
                            <label class="block text-[9.5px] font-mono font-bold text-pink-400 uppercase tracking-wider mb-0.5">🎙️ Vocal Delivery / Voiceover Style</label>
                            <input type="text" readonly value="High-energy back-and-forth rap battle delivery with synchronized lip-sync" class="w-full bg-gray-900 border border-gray-800 rounded-lg p-1.5 text-[10px] text-pink-200 font-mono shadow-inner" />
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-800 pb-2.5">
                <div>
                    <h2 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                        <span>👥</span><span>Gemini Omni Image Roles &amp; Character Style Signifiers</span>
                    </h2>
                    <p class="text-[10px] text-gray-400 mt-0.5">
                        Define character roles with visual descriptions and attached reference image URLs to maintain likeness.
                    </p>
                </div>
                <div class="flex items-center gap-2">
                    <button class="bg-gray-950 hover:bg-gray-800 text-purple-300 border border-purple-900/60 font-bold text-[10px] py-1 px-2.5 rounded-lg shadow flex items-center gap-1.5 transition">
                        <span>💾</span><span>Save Cast Roster</span>
                    </button>
                    <button class="bg-gray-950 hover:bg-gray-800 text-gray-300 border border-gray-700 font-bold text-[10px] py-1 px-2.5 rounded-lg shadow flex items-center gap-1.5 transition">
                        <span>📂</span><span>Restore Cast</span>
                    </button>
                </div>
            </div>

            <div class="bg-gray-950/80 border border-purple-900/50 rounded-xl p-3 space-y-2">
                <div class="flex items-center justify-between">
                    <label class="text-[11px] font-bold text-purple-300 uppercase tracking-wider flex items-center gap-2 font-mono">
                        <span>🏛️</span><span>Character Vault &amp; Saved Library</span>
                    </label>
                    <span class="text-[10px] text-gray-400 font-mono">4 Preset(s) Available</span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                    <button class="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 text-[10px] px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm font-medium">
                        <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><rect width='40' height='40' rx='20' fill='%23dc2626'/><circle cx='20' cy='16' r='9' fill='%23fca5a5'/><path d='M 10 35 C 10 25, 30 25, 30 35 Z' fill='%23991b1b'/></svg>" class="w-4 h-4 rounded-full object-cover border border-purple-400/50" />
                        <span>+</span><span>Harry "Gucci"</span>
                    </button>
                    <button class="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 text-[10px] px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm font-medium">
                        <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><rect width='40' height='40' rx='20' fill='%2315803d'/><circle cx='20' cy='16' r='9' fill='%23fde68a'/><path d='M 10 35 C 10 25, 30 25, 30 35 Z' fill='%23166534'/></svg>" class="w-4 h-4 rounded-full object-cover border border-purple-400/50" />
                        <span>+</span><span>Young Draco "Jeezy"</span>
                    </button>
                    <button class="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 text-[10px] px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm font-medium">
                        <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><rect width='40' height='40' rx='20' fill='%234338ca'/><circle cx='20' cy='16' r='9' fill='%23fed7aa'/><path d='M 10 35 C 10 25, 30 25, 30 35 Z' fill='%23312e81'/></svg>" class="w-4 h-4 rounded-full object-cover border border-purple-400/50" />
                        <span>+</span><span>Cyborg Gordon Ramsay</span>
                    </button>
                    <button class="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 text-[10px] px-2.5 py-1 rounded-lg flex items-center gap-1.5 shadow-sm font-medium">
                        <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><rect width='40' height='40' rx='20' fill='%23c026d3'/><circle cx='20' cy='16' r='9' fill='%23fbcfe8'/><path d='M 10 35 C 10 25, 30 25, 30 35 Z' fill='%2386198f'/></svg>" class="w-4 h-4 rounded-full object-cover border border-purple-400/50" />
                        <span>+</span><span>Neon Julia Child</span>
                    </button>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
                <div class="bg-gray-950 border border-amber-500/40 rounded-xl p-3.5 space-y-2.5 relative overflow-hidden">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="bg-amber-500 text-black font-black text-[10px] px-2 py-0.5 rounded font-mono uppercase">Role A</span>
                            <span class="text-[10px] text-green-400 font-mono">Image Role Attached 🔗</span>
                        </div>
                        <button class="bg-gray-900 hover:bg-purple-950 text-purple-300 border border-purple-900/60 text-[10px] px-2 py-0.5 rounded-lg flex items-center gap-1 font-medium shadow-sm">
                            <span>💾</span><span>Save to Vault</span>
                        </button>
                    </div>
                    <div>
                        <h3 class="text-xs font-bold text-white">Harry "Gucci"</h3>
                        <p class="text-[11px] text-gray-300 leading-relaxed mt-0.5">
                            Round gold Cartier glasses, untidy jet-black hair, red Gucci tracksuit, and distinct lightning scar.
                        </p>
                    </div>
                    <div class="flex items-center space-x-2 bg-purple-950/40 border border-purple-800/60 rounded-lg p-2">
                        <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect width='80' height='80' rx='16' fill='%23dc2626'/><circle cx='40' cy='32' r='18' fill='%23fca5a5'/><circle cx='33' cy='30' r='5' fill='none' stroke='%23f59e0b' stroke-width='2'/><circle cx='47' cy='30' r='5' fill='none' stroke='%23f59e0b' stroke-width='2'/><line x1='38' y1='30' x2='42' y2='30' stroke='%23f59e0b' stroke-width='2'/><path d='M 28 20 Q 40 12 52 20 Z' fill='%2318181b'/><path d='M 20 65 C 20 48, 60 48, 60 65 Z' fill='%23991b1b'/></svg>" alt="Harry" class="w-10 h-10 object-cover rounded-lg border border-purple-500/50 flex-shrink-0" />
                        <div class="overflow-hidden min-w-0">
                            <span class="text-[10px] font-bold text-purple-300 uppercase tracking-wider block">Linked Image Role</span>
                            <span class="text-[10px] text-gray-400 font-mono truncate block">gs://reference-images-jt-trend-trawler/harry_drip.jpeg</span>
                        </div>
                    </div>
                    <div class="space-y-1">
                        <label class="block text-[9.5px] font-mono font-bold text-amber-400 uppercase tracking-wider">🎙️ Voice Style &amp; Accent</label>
                        <input type="text" readonly value="Fast-paced confident Atlanta rap flow with autotune" class="w-full bg-gray-900 border border-gray-800 rounded-lg p-1.5 text-[10px] text-amber-200 font-mono shadow-inner" />
                    </div>
                    <div class="pt-1 border-t border-gray-800/80 space-y-1.5">
                        <span class="text-[9.5px] font-mono font-bold text-pink-400 uppercase tracking-wider block">🎨 Style Signifiers (Aesthetic Tags)</span>
                        <div class="flex flex-wrap gap-1.5">
                            <span class="bg-purple-950/90 text-purple-200 border border-purple-800 text-[10px] px-2 py-0.5 rounded font-mono">Red Gucci Tracksuit</span>
                            <span class="bg-purple-950/90 text-purple-200 border border-purple-800 text-[10px] px-2 py-0.5 rounded font-mono">Cartier Glasses</span>
                        </div>
                    </div>
                </div>

                <div class="bg-gray-950 border border-purple-500/40 rounded-xl p-3.5 space-y-2.5 relative overflow-hidden">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="bg-purple-500 text-black font-black text-[10px] px-2 py-0.5 rounded font-mono uppercase">Role B</span>
                            <span class="text-[10px] text-green-400 font-mono">Image Role Attached 🔗</span>
                        </div>
                        <button class="bg-gray-900 hover:bg-purple-950 text-purple-300 border border-purple-900/60 text-[10px] px-2 py-0.5 rounded-lg flex items-center gap-1 font-medium shadow-sm">
                            <span>💾</span><span>Save to Vault</span>
                        </button>
                    </div>
                    <div>
                        <h3 class="text-xs font-bold text-white">Young Draco "Jeezy"</h3>
                        <p class="text-[11px] text-gray-300 leading-relaxed mt-0.5">
                            Platinum slicked-back hair, green velvet blazer over black turtleneck, and iced-out diamond chain.
                        </p>
                    </div>
                    <div class="flex items-center space-x-2 bg-purple-950/40 border border-purple-800/60 rounded-lg p-2">
                        <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'><rect width='80' height='80' rx='16' fill='%2315803d'/><circle cx='40' cy='32' r='18' fill='%23fde68a'/><path d='M 24 24 Q 40 10 56 24 Z' fill='%23fef08a'/><path d='M 20 65 C 20 48, 60 48, 60 65 Z' fill='%23166534'/><polygon points='40,48 44,54 40,60 36,54' fill='%2338bdf8'/></svg>" alt="Draco" class="w-10 h-10 object-cover rounded-lg border border-purple-500/50 flex-shrink-0" />
                        <div class="overflow-hidden min-w-0">
                            <span class="text-[10px] font-bold text-purple-300 uppercase tracking-wider block">Linked Image Role</span>
                            <span class="text-[10px] text-gray-400 font-mono truncate block">gs://reference-images-jt-trend-trawler/draco.jpeg</span>
                        </div>
                    </div>
                    <div class="space-y-1">
                        <label class="block text-[9.5px] font-mono font-bold text-purple-400 uppercase tracking-wider">🎙️ Voice Style &amp; Accent</label>
                        <input type="text" readonly value="Pompous, cynical British drawl with aggressive rap cadence" class="w-full bg-gray-900 border border-gray-800 rounded-lg p-1.5 text-[10px] text-purple-200 font-mono shadow-inner" />
                    </div>
                    <div class="pt-1 border-t border-gray-800/80 space-y-1.5">
                        <span class="text-[9.5px] font-mono font-bold text-pink-400 uppercase tracking-wider block">🎨 Style Signifiers (Aesthetic Tags)</span>
                        <div class="flex flex-wrap gap-1.5">
                            <span class="bg-purple-950/90 text-purple-200 border border-purple-800 text-[10px] px-2 py-0.5 rounded font-mono">Platinum Slicked Hair</span>
                            <span class="bg-purple-950/90 text-purple-200 border border-purple-800 text-[10px] px-2 py-0.5 rounded font-mono">Diamond Iced-Out Chain</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="lg:col-span-4 bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
        <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
            <span>🛡️</span><span>Model Armor Guardrail Gate</span>
        </h3>
        <div class="bg-gray-950 p-4 rounded-xl border border-green-900/60 space-y-3 text-xs">
            <div class="flex items-center justify-between text-green-400 font-bold">
                <span>RAI Safety Pre-Filter</span>
                <span>PASSED ✅</span>
            </div>
            <p class="text-gray-400 text-[11px] leading-relaxed">
                Template: <code class="text-amber-400">omnimash-safety-filter</code><br/>
                Hate Speech &amp; Dangerous Content: 0.00%<br/>
                Jailbreak Attempt Risk: None Detected
            </p>
        </div>
        <div class="bg-gray-950 p-4 rounded-xl border border-gray-800 space-y-2 text-xs">
            <span class="text-gray-400 font-bold">Next Action:</span>
            <p class="text-gray-300 text-[11px]">Proceed to Act 2 to fine-tune storyboard scene sequence and character dialogue.</p>
        </div>
    </div>
</div>
"""

act2_content = """
<div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
    <div class="lg:col-span-7 space-y-4">
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-3.5">
            <div class="flex items-center justify-between border-b border-gray-800 pb-2.5">
                <h2 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                    <span>🎬</span><span>Multi-Scene Storyboard Directing</span>
                </h2>
                <span class="text-[10px] bg-purple-950 text-purple-400 px-2 py-0.5 rounded border border-purple-800 font-mono">
                    2 Active Scenes
                </span>
            </div>

            <div class="bg-gray-950 border border-gray-800 rounded-xl p-3.5 space-y-2.5">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-amber-400 font-mono">SCENE 1 (0s - 5s)</span>
                    <span class="bg-amber-950 text-amber-300 text-[10px] px-2 py-0.5 rounded font-mono border border-amber-800">Active Role: Role A (Harry)</span>
                </div>
                <div class="space-y-1 text-xs">
                    <p class="text-gray-300"><strong class="text-gray-400">Action:</strong> Standing over one of the stoves, cooking potions. In one hand, he holds an open box of baking soda.</p>
                    <p class="text-amber-300 font-mono bg-gray-900 p-2 rounded border border-gray-800 text-[11px]">💬 "I been cooking potions since first year, bruv!"</p>
                </div>
            </div>

            <div class="bg-gray-950 border border-gray-800 rounded-xl p-3.5 space-y-2.5">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-purple-400 font-mono">SCENE 2 (5s - 10s)</span>
                    <span class="bg-purple-950 text-purple-300 text-[10px] px-2 py-0.5 rounded font-mono border border-purple-800">Active Role: Role B (Draco)</span>
                </div>
                <div class="space-y-1 text-xs">
                    <p class="text-gray-300"><strong class="text-gray-400">Action:</strong> Stepping into rundown room with iced-out diamond chain, sneering at the stove.</p>
                    <p class="text-purple-300 font-mono bg-gray-900 p-2 rounded border border-gray-800 text-[11px]">💬 "Oh, please.... This is Trap or Die, Potter! You ain’t never seen a brick!"</p>
                </div>
            </div>

            <button class="w-full bg-gradient-to-r from-amber-500 to-orange-600 text-black font-black text-xs py-3 rounded-xl shadow-lg flex items-center justify-center gap-2">
                <span>🎬</span><span>Generate Native 720p Video + Synced Audio (Act 3)</span>
            </button>
        </div>
    </div>

    <div class="lg:col-span-5 bg-gray-900 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col h-[540px]">
        <div class="flex items-center justify-between border-b border-gray-800 pb-2.5 mb-3">
            <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                <span>🧠</span><span>Compiled Storyboard Prompt Preview</span>
            </h3>
            <span class="text-[10px] bg-green-950 text-green-400 px-2 py-0.5 rounded border border-green-800 font-mono">
                PromptCompiler
            </span>
        </div>
        <pre class="flex-1 bg-gray-950 p-3.5 rounded-xl border border-gray-800 text-[10px] font-mono text-gray-300 overflow-y-auto whitespace-pre-wrap custom-scrollbar leading-relaxed">
[ROLE DEFINITIONS]
- Role A (Harry "Gucci"): Harry "Gucci", young wizard with round gold wire-rim Cartier glasses, red Gucci tracksuit [Style: Red Gucci Tracksuit, Cartier Glasses] (Ref: gs://reference-images-jt-trend-trawler/harry_drip.jpeg)
- Role B (Young Draco "Jeezy"): Young Draco "Jeezy", pale blonde rival wizard with slicked-back platinum hair, green velvet blazer [Style: Platinum Slicked Hair, Diamond Iced-Out Chain] (Ref: gs://reference-images-jt-trend-trawler/draco.jpeg)

[AESTHETIC INJECTION]
Concept: Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style
Aesthetic Tags: 2000s Atlanta Trap Disstrack, Heavy 808 Bass Lighting, Vintage Streetwear
Environment: Abandoned urban house with working potion stoves

[AUDIO & VOCAL DIRECTION]
Background Beat: 140 BPM Heavy 808 Trap (ducked at 15% volume under dialogue)
Voice Style (Role A): Fast-paced confident Atlanta rap flow with autotune
Voice Style (Role B): Pompous, cynical British drawl with aggressive rap cadence
Vocal Delivery: High-energy back-and-forth rap battle delivery with synchronized lip-sync

[STORYBOARD SEQUENCE]
- Scene 1 [Role A]: Standing over potion stove cooking potions with baking soda. | Dialogue: "I been cooking potions since first year, bruv!"
- Scene 2 [Role B]: Stepping into room with iced out chain. | Dialogue: "Oh, please.... This is Trap or Die, Potter!"
</pre>
    </div>
</div>
"""

act3_content = """
<div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
    <div class="lg:col-span-8 space-y-3.5">
        <div class="bg-black rounded-2xl border border-gray-800 overflow-hidden shadow-2xl relative">
            <img src="__FRAME_B64__" class="w-full aspect-[16/9] max-h-[340px] object-cover bg-black" alt="Live Gemini Omni Flash Video Frame" />
            <div class="p-3 bg-gray-900/95 border-t border-gray-800 flex items-center justify-between gap-2">
                <div class="flex items-center space-x-2 text-xs">
                    <span class="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
                    <span class="font-bold text-gray-200">Live Parody Cut (720p)</span>
                    <span class="text-[10px] bg-gray-800 text-gray-300 px-2 py-0.5 rounded font-mono">
                        Turn: thread_892d39cb_turn0
                    </span>
                </div>
                <div class="flex items-center gap-2">
                    <button class="text-xs bg-amber-950 hover:bg-amber-900 text-amber-300 border border-amber-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition">
                        <span>💾</span><span>Stitch & Save Master (30–60s) to GCS</span>
                    </button>
                    <button class="text-xs bg-purple-950 hover:bg-purple-900 text-purple-300 border border-purple-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition">
                        <span>➕</span><span>Extend Video / Next Scene</span>
                    </button>
                    <button class="text-xs text-purple-400 font-bold flex items-center gap-1 bg-purple-950/60 border border-purple-800 px-2.5 py-1.5 rounded-lg">
                        <span>⬇️ MP4</span>
                    </button>
                </div>
            </div>
        </div>

        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-3.5 shadow-xl space-y-2">
            <div class="flex items-center justify-between border-b border-gray-800 pb-1.5">
                <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                    <span>🧠</span><span>Final Generation Prompt (Active Version)</span>
                </h3>
                <span class="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800 font-mono">
                    Gemini Omni Directives
                </span>
            </div>
            <pre class="bg-gray-950 p-2.5 rounded-xl border border-gray-800 text-[10px] font-mono text-gray-300 overflow-y-auto whitespace-pre-wrap max-h-28 custom-scrollbar leading-relaxed">
[ROLE DEFINITIONS]
- Role A (Harry "Gucci"): Harry "Gucci", round Cartier glasses, red Gucci tracksuit [Style: Red Gucci Tracksuit, Cartier Glasses] (Ref: gs://reference-images-jt-trend-trawler/harry_drip.jpeg)
- Role B (Young Draco "Jeezy"): Young Draco "Jeezy", platinum hair, green velvet blazer [Style: Platinum Slicked Hair, Diamond Iced-Out Chain] (Ref: gs://reference-images-jt-trend-trawler/draco.jpeg)

[AESTHETIC INJECTION]
Concept: Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style
Aesthetic Tags: 2000s Atlanta Trap Disstrack, Heavy 808 Bass Lighting, Vintage Streetwear
Environment: Abandoned urban house with working potion stoves

[AUDIO & VOCAL DIRECTION]
Background Beat: 140 BPM Heavy 808 Trap (ducked at 15% volume under dialogue)
Voice Style (Role A): Fast-paced confident Atlanta rap flow with autotune
Voice Style (Role B): Pompous, cynical British drawl with aggressive rap cadence
Vocal Delivery: High-energy back-and-forth rap battle delivery with synchronized lip-sync

[STORYBOARD SEQUENCE]
- Scene 1 [Role A]: Standing over potion stove cooking potions with baking soda. | Dialogue: "I been cooking potions since first year, bruv!"
- Scene 2 [Role B]: Stepping into room with iced out chain. | Dialogue: "This is Trap or Die, Potter!"
</pre>
        </div>

        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-3 shadow-xl flex gap-2.5 items-center">
            <div class="text-lg">💬</div>
            <input type="text" readonly value="Direct the scene (e.g. Make Role A's glasses darker and add laser smoke)..." class="flex-1 bg-gray-950 border border-gray-800 rounded-xl p-2 text-xs text-gray-400 font-mono shadow-inner" />
            <button class="bg-gradient-to-r from-amber-500 to-orange-600 text-black font-bold text-xs py-2 px-4 rounded-xl shadow flex items-center gap-1.5">
                <span>⚡</span><span>Apply Delta Edit</span>
            </button>
        </div>
    </div>

    <div class="lg:col-span-4 bg-gray-900 border border-gray-800 rounded-2xl p-4 shadow-xl flex flex-col h-[540px]">
        <div class="flex items-center justify-between mb-3 border-b border-gray-800 pb-2">
            <h3 class="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                <span>🍰</span><span>Version Tree &amp; Timeline</span>
            </h3>
            <span class="text-[10px] bg-amber-950 text-amber-400 px-2 py-0.5 rounded border border-amber-800 font-mono">
                DAG History
            </span>
        </div>

        <div class="flex-1 overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
            <div class="p-3 rounded-xl border bg-amber-950/40 border-amber-500 shadow-md text-left space-y-1.5">
                <div class="flex items-center justify-between text-[10px] font-mono text-gray-400">
                    <span class="font-bold text-amber-300">Turn #1 (thread_892d39cb_turn0)</span>
                    <span class="bg-green-900 text-green-300 px-1.5 py-0.5 rounded">RENDERED</span>
                </div>
                <p class="text-xs font-bold text-gray-200">Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style</p>
                <div class="space-y-1 text-[10px] font-mono">
                    <div class="bg-black/60 p-1.5 rounded border border-gray-800/80 text-pink-300">
                        <span class="font-bold">🔒 Lock:</span> Facial Likeness &amp; Potion Stoves
                    </div>
                    <div class="bg-black/60 p-1.5 rounded border border-gray-800/80 text-purple-300">
                        <span class="font-bold">🎯 Diff:</span> Initial 720p Native Synced Audio
                    </div>
                </div>
            </div>

            <div class="p-3 rounded-xl border bg-gray-950/80 border-gray-800 text-left space-y-1.5 opacity-75">
                <div class="flex items-center justify-between text-[10px] font-mono text-gray-400">
                    <span>Turn #2 (v1_ChdfMVplYXNT..._diff)</span>
                    <span class="bg-purple-900 text-purple-300 px-1.5 py-0.5 rounded">DELTA EDIT</span>
                </div>
                <p class="text-xs font-bold text-gray-300">Add disco strobe lights and iced-out diamond chain</p>
                <div class="space-y-1 text-[10px] font-mono">
                    <div class="bg-black/60 p-1.5 rounded border border-gray-800/80 text-purple-300">
                        <span class="font-bold">🎯 Diff:</span> previous_interaction_id stateful continuation
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

html_files = {
    "imgs/ui_act1_concept_and_cast.jpg": get_html(1, act1_content),
    "imgs/ui_act2_storyboard_directing.jpg": get_html(2, act2_content),
    "imgs/ui_act3_screening_room.jpg": get_html(
        3, act3_content.replace("__FRAME_B64__", frame_b64)
    ),
}

for img_target, html_code in html_files.items():
    file_name = os.path.basename(img_target)
    tmp_html = f"/tmp/readme_html/{file_name}.html"
    tmp_png = f"/tmp/readme_html/{file_name}.png"
    with open(tmp_html, "w") as f:
        f.write(html_code)

    cmd = [
        "/usr/bin/google-chrome",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--virtual-time-budget=2000",
        "--window-size=1600,1000",
        f"--screenshot={tmp_png}",
        f"file://{tmp_html}",
    ]
    subprocess.run(cmd, check=True)

    im = Image.open(tmp_png).convert("RGB")
    dest_path = os.path.join(REPO_DIR, img_target)
    im.save(dest_path, "JPEG", quality=92)
    print(f"Saved {dest_path} with mtime {os.path.getmtime(dest_path)}")

    artifact_dirs = [
        "/usr/local/google/home/jordantotten/.gemini/jetski/brain/3560c909-b993-4b35-8d92-8ae1ffa85ea1",
        "/usr/local/google/home/jordantotten/.gemini/jetski/brain/4b2ceabd-0603-4e86-9966-e874e937e9b7",
        "/usr/local/google/home/jordantotten/.gemini/jetski/brain/0157fe8d-a743-41ec-9ab2-3e2221f21102",
        "/usr/local/google/home/jordantotten/.gemini/jetski/brain/69153085-e742-4580-9407-4d57ab3541ea",
    ]
    for ad in artifact_dirs:
        os.makedirs(ad, exist_ok=True)
        artifact_copy = os.path.join(ad, os.path.basename(img_target))
        im.save(artifact_copy, "JPEG", quality=92)
        print(f"Rendered {img_target} and saved artifact to {artifact_copy}")

print("All screenshots generated successfully!")
