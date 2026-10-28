// Mode 5: Commercial Soundstage — 10-Step Editorial Intake & Express Canvas (Modular JSX Partial)

const SOUNDSTAGE_MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const SOUNDSTAGE_HEX_PATTERN = /^#[0-9A-Fa-f]{6}$/;

const SOUNDSTAGE_WORLD_TERRITORIES = [
    { place_name: "New York · SoHo", x: 232, y: 136, temperature_c: 18, condition: "Clear autumn dusk · Cast-iron facade rim light", lighting_directive: "35mm prime lens, directional golden-hour street canyon shafts with soft bounce fill", cultural_pulse: "Creative loft energy across cobblestone blocks and gallery thresholds" },
    { place_name: "Los Angeles · Silver Lake", x: 146, y: 152, temperature_c: 22, condition: "Golden-hour haze · Warm canyon rim light", lighting_directive: "Anamorphic 40mm cinema lens, warm sun-drenched hillside glow", cultural_pulse: "Modernist courtyard calm and West Coast studio craft" },
    { place_name: "São Paulo · Jardins", x: 288, y: 268, temperature_c: 24, condition: "Tropical dusk · Lush concrete gallery shadows", lighting_directive: "35mm cinema prime, brutalist concrete chiaroscuro with warm canopy bounce", cultural_pulse: "Verdant modernist architecture meeting cosmopolitan evening poise" },
    { place_name: "Reykjavik · Harbor", x: 356, y: 84, temperature_c: 7, condition: "Sub-arctic blue hour · Basalt mist reflections", lighting_directive: "50mm prime lens, crisp silver-blue twilight over dark volcanic basalt", cultural_pulse: "Elemental Nordic clarity and quiet geothermal warmth" },
    { place_name: "London · Soho", x: 392, y: 118, temperature_c: 14, condition: "Blue-hour drizzle · Warm brass doorway reflections", lighting_directive: "35mm cinema lens, moody blue-hour ambience balanced by warm practical spill", cultural_pulse: "Tailored heritage craft colliding with contemporary nocturnal culture" },
    { place_name: "Paris · Le Marais", x: 404, y: 128, temperature_c: 19, condition: "Luminous morning · Soft limestone courtyard diffusion", lighting_directive: "50mm cinema prime, diffused natural skylight across warm Haussmann stone", cultural_pulse: "Effortless atelier refinement and unhurried morning cafe poise" },
    { place_name: "Milan · Brera", x: 422, y: 136, temperature_c: 21, condition: "Warm late afternoon · Sunlit travertine colonnade", lighting_directive: "Anamorphic 40mm lens, rich amber architectural chiaroscuro and stone speculars", cultural_pulse: "Tactile industrial design heritage and aperitivo-hour elegance" },
    { place_name: "Seoul · Hannam", x: 654, y: 146, temperature_c: 17, condition: "Crisp evening · Hillside glass & warm amber spill", lighting_directive: "35mm anamorphic prime, sleek architectural glass reflections at dusk", cultural_pulse: "Hyper-curated gallery precision and kinetic metropolitan poise" },
    { place_name: "Kyoto · Higashiyama", x: 676, y: 154, temperature_c: 15, condition: "Misty dawn · Cedar eaves and damp slate flagstones", lighting_directive: "50mm cinema lens, tranquil silver-amber dawn light through timber lattices", cultural_pulse: "Contemplative artisanal mastery and timeless material harmony" },
    { place_name: "Tokyo · Aoyama", x: 690, y: 150, temperature_c: 16, condition: "Crisp twilight · Golden-hour wet asphalt reflections", lighting_directive: "Anamorphic 35mm cinema lens, warm tungsten glow against slate twilight blue", cultural_pulse: "Precision evening rhythm where architectural minimalism meets metropolitan flow" }
];

const SOUNDSTAGE_PALETTE_PRESETS = [
    { label: "Obsidian & Sienna", primary_hex: "#1A222D", primary_name: "Obsidian Slate", secondary_hex: "#C4633B", secondary_name: "Sienna Saddle", neutral_hex: "#EAE6DF", neutral_name: "Chalk Travertine" },
    { label: "Brera Travertine & Espresso", primary_hex: "#2A211B", primary_name: "Espresso Walnut", secondary_hex: "#B86B3A", secondary_name: "Burnished Copper", neutral_hex: "#F2EDE4", neutral_name: "Brera Travertine" },
    { label: "Kyoto Cedar & Alabaster", primary_hex: "#2C332E", primary_name: "Cypress Basalt", secondary_hex: "#B98352", secondary_name: "Aged Cedar", neutral_hex: "#F4F1EA", neutral_name: "Satin Alabaster" },
    { label: "Nocturne Cobalt & Quartz", primary_hex: "#192334", primary_name: "Nocturne Cobalt", secondary_hex: "#3B82C4", secondary_name: "Cerulean Accent", neutral_hex: "#F3F5F8", neutral_name: "Frosted Quartz" }
];

const SOUNDSTAGE_INSPIRATION_CHIPS = [
    { label: "Aoyama Grand Tourer", subject: "Atelier Kuroda Motors", dna: "Sculpted nocturnal grand touring coupe gliding through wet Tokyo twilight" },
    { label: "Brera Botanical Aperitif", subject: "Casa Solari Milano", dna: "Chilled artisanal citrus-bitter glass bottle on sunlit travertine" },
    { label: "Trapwarts Arcane Wand", subject: "Trapwarts Alchemical Guild", dna: "Parody luxury commercial for a hand-carved obsidian spellcraft wand" },
    { label: "Kyoto Pour-Over System", subject: "Higashiyama Precision Craft", dna: "Countertop dual-boiler brushed gunmetal espresso ritual at dawn" }
];

const SOUNDSTAGE_DEFAULT_LANGUAGES = [
    { code: "en", label: "English", vocal_cadence: "Measured, intimate international cinema baritone with crisp articulation" },
    { code: "ja", label: "Japanese", vocal_cadence: "Poised, resonant Tokyo editorial narration with calm rhythmic pauses" },
    { code: "fr", label: "French", vocal_cadence: "Warm Parisian atelier cadence with effortless velvet phrasing" },
    { code: "it", label: "Italian", vocal_cadence: "Expressive Milanese architectural warmth with crisp consonant poise" },
    { code: "es", label: "Spanish", vocal_cadence: "Luminous contemporary cinema narration with confident rhythmic cadence" }
];

const SOUNDSTAGE_STEPS = [
    { num: 1, shortLabel: "Subject", title: "Step 1 · Subject or Brand", subtitle: "Name the commercial house, studio label, or parody universe." },
    { num: 2, shortLabel: "Offering", title: "Step 2 · Hero Offering & Physics", subtitle: "Select or define the physical offering and verify deduced ergonomics." },
    { num: 3, shortLabel: "Territory", title: "Step 3 · Filming Territory", subtitle: "Anchor architectural geography and local cultural rhythm." },
    { num: 4, shortLabel: "Atmosphere", title: "Step 4 · Weather & Lighting", subtitle: "Lock micro-climate, optical lens mood, and daylight equilibrium." },
    { num: 5, shortLabel: "Emblem", title: "Step 5 · Studio Mark & End-Card Plate", subtitle: "Verify WCAG contrast backing plate or synthesize a clean geometric emblem." },
    { num: 6, shortLabel: "Palette", title: "Step 6 · 60 / 30 / 10 Color Lock", subtitle: "Enforce architectural set, wardrobe, and hero plinth color ratios." },
    { num: 7, shortLabel: "Moment", title: "Step 7 · Cultural Moment", subtitle: "Frame the human threshold ritual driving the 3-act arc." },
    { num: 8, shortLabel: "Cadence", title: "Step 8 · Language & Vocal Cadence", subtitle: "Set spoken narration tongue and acoustic pacing." },
    { num: 9, shortLabel: "Packshot", title: "Step 9 · Hero Reference / Packshot", subtitle: "Lock a 1:1 visual object anchor for Act 2 and Act 3 payoff." },
    { num: 10, shortLabel: "Sign-Off", title: "Step 10 · Ready Sign-Off", subtitle: "Review every brief decision, confirm resolution tier, and roll cameras." }
];

function computeWcagRelativeLuminance(hexColor) {
    const clean = SOUNDSTAGE_HEX_PATTERN.test(String(hexColor || "").trim()) ? String(hexColor).trim().slice(1) : "1A222D";
    const ch = [0, 2, 4].map((idx) => {
        const c = parseInt(clean.slice(idx, idx + 2), 16) / 255;
        return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}

function computeWcagContrastRatio(lumA, lumB) {
    return (Math.max(lumA, lumB) + 0.05) / (Math.min(lumA, lumB) + 0.05);
}

function buildSoundstagePaletteDirective(pal) {
    const pName = (pal && pal.primary_name) || "Obsidian Slate";
    const pHex = (pal && pal.primary_hex) || "#1A222D";
    const sName = (pal && pal.secondary_name) || "Sienna Saddle";
    const sHex = (pal && pal.secondary_hex) || "#C4633B";
    const nName = (pal && pal.neutral_name) || "Chalk Travertine";
    const nHex = (pal && pal.neutral_hex) || "#EAE6DF";
    return `60% ${pName} (${pHex}) architectural & set surfaces / 30% ${sName} (${sHex}) wardrobe & practical props / 10% ${nName} (${nHex}) foundational hero surface`;
}

function readSoundstageFileAsDataUrl(file, addToast, onLoaded) {
    if (!file) return;
    if (file.size > SOUNDSTAGE_MAX_UPLOAD_BYTES) {
        if (addToast) addToast("Image exceeds 10 MiB limit. Choose an image under 10 MiB.", "error");
        return;
    }
    const reader = new FileReader();
    reader.onload = () => { if (typeof reader.result === "string") onLoaded(reader.result); };
    reader.onerror = () => { if (addToast) addToast("Could not read selected image file.", "error"); };
    reader.readAsDataURL(file);
}

function SoundstageWorldMap({ territory, suggestedTerritories, onSelectTerritory, onCustomTerritoryChange }) {
    const mergedSuggestions = Array.isArray(suggestedTerritories) ? suggestedTerritories : [];
    const lookupSpec = (placeName) => {
        const lower = String(placeName || "").toLowerCase();
        return mergedSuggestions.find((t) => String(t.place_name || "").toLowerCase() === lower)
            || SOUNDSTAGE_WORLD_TERRITORIES.find((t) => t.place_name.toLowerCase() === lower)
            || null;
    };
    return (
        <div id="soundstage-world-map" className="space-y-4">
            <div className="rounded-xl border border-stone-800 bg-[#07080d] p-3 overflow-hidden">
                <svg viewBox="0 0 800 380" role="group" aria-label="Global Filming Territory Map" className="w-full h-auto max-h-72 select-none">
                    <rect x="0" y="0" width="800" height="380" fill="#07080d" />
                    {[76, 152, 228, 304].map((gy) => (<line key={`lat_${gy}`} x1="20" y1={gy} x2="780" y2={gy} stroke="#191d28" strokeWidth="1" strokeDasharray="3 5" />))}
                    {[160, 320, 480, 640].map((gx) => (<line key={`lon_${gx}`} x1={gx} y1="16" x2={gx} y2="364" stroke="#191d28" strokeWidth="1" strokeDasharray="3 5" />))}
                    <path d="M58,84 L112,62 L188,60 L246,84 L274,116 L248,154 L220,176 L192,196 L158,184 L124,158 L84,126 Z" fill="#141926" stroke="#2c354b" strokeWidth="1.2" />
                    <path d="M276,52 L334,46 L348,74 L308,88 L278,76 Z" fill="#141926" stroke="#2c354b" strokeWidth="1.1" />
                    <path d="M226,208 L274,204 L318,238 L328,278 L296,326 L262,354 L244,324 L236,262 Z" fill="#141926" stroke="#2c354b" strokeWidth="1.2" />
                    <path d="M374,86 L412,68 L458,66 L488,88 L484,126 L454,148 L414,152 L380,138 Z" fill="#161c2b" stroke="#313b54" strokeWidth="1.2" />
                    <path d="M384,164 L446,160 L492,184 L510,232 L488,292 L452,332 L416,304 L404,244 L378,204 Z" fill="#141926" stroke="#2c354b" strokeWidth="1.2" />
                    <path d="M492,76 L576,64 L668,68 L732,96 L722,148 L694,182 L646,206 L588,204 L538,182 L502,142 Z" fill="#151b29" stroke="#2e384f" strokeWidth="1.2" />
                    <path d="M684,132 L704,138 L700,164 L680,160 Z" fill="#182032" stroke="#384563" strokeWidth="1.1" />
                    <path d="M626,252 L696,246 L734,274 L724,316 L668,326 L628,298 Z" fill="#141926" stroke="#2c354b" strokeWidth="1.2" />
                    {SOUNDSTAGE_WORLD_TERRITORIES.map((pin) => {
                        const isSelected = String(territory || "").toLowerCase() === pin.place_name.toLowerCase();
                        const fillHex = isSelected ? "#e11d48" : "#a8a29e";
                        return (
                            <g key={pin.place_name} role="button" tabIndex={0} aria-label={`Select filming territory ${pin.place_name}`} onClick={() => onSelectTerritory(lookupSpec(pin.place_name) || pin)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectTerritory(lookupSpec(pin.place_name) || pin); } }} className="cursor-pointer">
                                <circle cx={pin.x} cy={pin.y} r={isSelected ? 11 : 6} fill={fillHex} fillOpacity={isSelected ? "0.28" : "0.14"} />
                                <circle cx={pin.x} cy={pin.y} r={isSelected ? 4.5 : 3} fill={fillHex} stroke="#f5f2eb" strokeWidth={isSelected ? "1.4" : "0.6"} />
                            </g>
                        );
                    })}
                </svg>
            </div>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Curated global territory pins">
                {SOUNDSTAGE_WORLD_TERRITORIES.map((pin) => {
                    const isSelected = String(territory || "").toLowerCase() === pin.place_name.toLowerCase();
                    const cls = isSelected ? "bg-rose-600/25 text-rose-100 border-rose-500 font-semibold" : "bg-stone-900/80 text-stone-300 border-stone-800 hover:border-stone-600 hover:text-stone-100";
                    return (<button key={pin.place_name} type="button" onClick={() => onSelectTerritory(lookupSpec(pin.place_name) || pin)} className={`px-3 py-1.5 rounded-lg text-xs border transition ${cls}`}>{pin.place_name}</button>);
                })}
            </div>
            {mergedSuggestions.length !== 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {mergedSuggestions.map((spec) => {
                        const isSelected = String(territory || "").toLowerCase() === String(spec.place_name || "").toLowerCase();
                        const cls = isSelected ? "border-rose-500/70 bg-rose-950/20" : "border-stone-800 bg-stone-950/60 hover:border-stone-600";
                        return (
                            <button key={spec.place_name} type="button" onClick={() => onSelectTerritory(spec)} className={`text-left rounded-xl p-3.5 border transition space-y-1 ${cls}`}>
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-bold text-stone-100">{spec.place_name}</span>
                                    <span className="text-xs font-mono text-rose-300">{spec.temperature_c}°C</span>
                                </div>
                                <p className="text-xs text-stone-300">{spec.condition}</p>
                            </button>
                        );
                    })}
                </div>
            )}
            <div>
                <label htmlFor="soundstage-input-territory" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Custom Territory or District</label>
                <input id="soundstage-input-territory" type="text" value={territory} onChange={(e) => onCustomTerritoryChange(e.target.value)} placeholder="e.g., Tokyo · Aoyama or Zurich · Paradeplatz" className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2.5 text-sm text-stone-100 focus:border-rose-500" />
            </div>
        </div>
    );
}

function SoundstageEmblemPlate({ palette, emblemUrl, setEmblemUrl, emblemCandidates, isSynthesizing, onSynthesizeEmblem, addToast, getDisplayableRefUrl }) {
    const [plateMode, setPlateMode] = useState("auto");
    const markLum = computeWcagRelativeLuminance(palette && palette.primary_hex) * 0.65 + computeWcagRelativeLuminance(palette && palette.neutral_hex) * 0.35;
    const contrastOnDark = computeWcagContrastRatio(markLum, computeWcagRelativeLuminance("#090A0F"));
    const contrastOnLight = computeWcagContrastRatio(markLum, computeWcagRelativeLuminance("#F5F2EB"));
    const autoPrefersLight = contrastOnLight > contrastOnDark;
    const useLightPlate = plateMode === "light" || (plateMode === "auto" && autoPrefersLight);
    const activeRatio = (useLightPlate ? contrastOnLight : contrastOnDark).toFixed(1);
    const displayUrl = emblemUrl ? getDisplayableRefUrl(emblemUrl) : "";
    const candidates = Array.isArray(emblemCandidates) ? emblemCandidates : [];

    return (
        <div id="soundstage-emblem-plate" className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-1.5 bg-stone-950 border border-stone-800 rounded-lg p-1" role="group" aria-label="Emblem backing plate contrast mode">
                    {[{ id: "auto", label: "Auto" }, { id: "dark", label: "Dark Plate" }, { id: "light", label: "Light Plate" }].map((opt) => (
                        <button key={opt.id} type="button" onClick={() => setPlateMode(opt.id)} className={`px-2.5 py-1 rounded text-xs font-medium transition ${plateMode === opt.id ? "bg-rose-600 text-white" : "text-stone-300 hover:text-white"}`}>{opt.label}</button>
                    ))}
                </div>
                <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-stone-900 border border-stone-700 text-stone-200">
                    WCAG {activeRatio}:1 · {useLightPlate ? "Warm Alabaster Plate" : "Dark Obsidian Plate"}
                </span>
            </div>
            <div className={`rounded-xl border p-6 flex flex-col items-center justify-center min-h-[144px] transition ${useLightPlate ? "bg-[#F5F2EB] text-[#090A0F] border-stone-300" : "bg-[#090A0F] text-[#F5F2EB] border-stone-800"}`}>
                {displayUrl ? (
                    <img src={displayUrl} alt="Studio emblem preview" className="max-h-28 object-contain rounded" />
                ) : (
                    <div className="text-center space-y-1.5">
                        <div className="w-11 h-11 mx-auto rounded-full border-2 flex items-center justify-center font-mono text-xs font-bold" style={{ borderColor: (palette && palette.secondary_hex) || "#C4633B" }}>◆</div>
                        <p className="text-xs font-mono opacity-80">Clean geometric mark or upload custom studio emblem</p>
                    </div>
                )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label htmlFor="soundstage-emblem-upload" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Upload Studio Mark (&lt;= 10 MiB)</label>
                    <input id="soundstage-emblem-upload" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={(e) => readSoundstageFileAsDataUrl(e.target.files && e.target.files[0], addToast, setEmblemUrl)} className="w-full text-xs text-stone-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-stone-800 file:text-stone-100 hover:file:bg-stone-700" />
                </div>
                <div>
                    <label htmlFor="soundstage-input-emblem-url" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">{"Direct Emblem URI (gs://, https://, data:image/)"}</label>
                    <input id="soundstage-input-emblem-url" type="text" value={emblemUrl} onChange={(e) => setEmblemUrl(e.target.value)} placeholder="gs://... or https://..." className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3 py-2 text-xs text-stone-100" />
                </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
                <button type="button" id="soundstage-btn-synthesize-emblem" disabled={isSynthesizing} onClick={onSynthesizeEmblem} className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50">
                    {isSynthesizing ? "Synthesizing Studio Marks..." : "Synthesize Studio Mark"}
                </button>
                {emblemUrl && (<button type="button" onClick={() => setEmblemUrl("")} className="text-xs text-stone-400 hover:text-stone-200 underline">Clear Emblem</button>)}
            </div>
            {candidates.length !== 0 && (
                <div className="grid grid-cols-3 gap-2.5">
                    {candidates.map((candUrl, idx) => (
                        <button key={`${candUrl}_${idx}`} type="button" onClick={() => setEmblemUrl(candUrl)} className={`p-2 rounded-xl border transition ${candUrl === emblemUrl ? "border-rose-500 bg-rose-950/30" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                            <img src={getDisplayableRefUrl(candUrl)} alt={`Emblem candidate ${idx + 1}`} className="h-16 w-full object-contain rounded" />
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

function SoundstagePaletteEditor({ palette, onChangePalette }) {
    const applyPatch = (patch) => {
        const next = { ...palette, ...patch };
        next.production_design_directive = buildSoundstagePaletteDirective(next);
        onChangePalette(next);
    };
    const channels = [
        { hexKey: "primary_hex", nameKey: "primary_name", ratio: "60%", role: "60% Architectural & Set Surfaces" },
        { hexKey: "secondary_hex", nameKey: "secondary_name", ratio: "30%", role: "30% Wardrobe & Practical Props" },
        { hexKey: "neutral_hex", nameKey: "neutral_name", ratio: "10%", role: "10% Foundational Hero Surface" }
    ];
    return (
        <div id="soundstage-palette-editor" className="space-y-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Editorial 60/30/10 palette presets">
                {SOUNDSTAGE_PALETTE_PRESETS.map((p) => (
                    <button key={p.label} type="button" onClick={() => applyPatch({ primary_hex: p.primary_hex, primary_name: p.primary_name, secondary_hex: p.secondary_hex, secondary_name: p.secondary_name, neutral_hex: p.neutral_hex, neutral_name: p.neutral_name })} className="px-3 py-1.5 rounded-lg text-xs bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700/80 flex items-center gap-2 transition">
                        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.primary_hex }} />
                        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.secondary_hex }} />
                        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.neutral_hex }} />
                        <span>{p.label}</span>
                    </button>
                ))}
            </div>
            <div className="h-6 w-full rounded-xl overflow-hidden flex border border-stone-700/80 shadow-inner" aria-label="60 30 10 color ratio bar">
                <div style={{ width: "60%", backgroundColor: palette.primary_hex }} title={`60% ${palette.primary_name}`} />
                <div style={{ width: "30%", backgroundColor: palette.secondary_hex }} title={`30% ${palette.secondary_name}`} />
                <div style={{ width: "10%", backgroundColor: palette.neutral_hex }} title={`10% ${palette.neutral_name}`} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {channels.map((ch) => {
                    const hexVal = String(palette[ch.hexKey] || "#1A222D");
                    const isValidHex = SOUNDSTAGE_HEX_PATTERN.test(hexVal);
                    return (
                        <div key={ch.hexKey} className="sstage-card rounded-xl p-3.5 space-y-2.5">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">{ch.role}</span>
                                <span className="text-xs font-mono text-rose-300">{ch.ratio}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <input type="color" aria-label={`${ch.role} color picker`} value={isValidHex ? hexVal : "#1A222D"} onChange={(e) => applyPatch({ [ch.hexKey]: e.target.value.toUpperCase() })} className="w-9 h-9 rounded cursor-pointer bg-transparent border border-stone-700" />
                                <input type="text" aria-label={`${ch.role} hex value`} value={hexVal} onChange={(e) => applyPatch({ [ch.hexKey]: e.target.value.toUpperCase() })} maxLength={7} className={`flex-1 rounded-lg bg-stone-950 px-2.5 py-1.5 text-xs font-mono text-stone-100 border ${isValidHex ? "border-stone-700" : "border-rose-500"}`} />
                            </div>
                            <input type="text" aria-label={`${ch.role} material name`} value={palette[ch.nameKey] || ""} onChange={(e) => applyPatch({ [ch.nameKey]: e.target.value })} placeholder="Material / Finish Name" className="w-full rounded-lg bg-stone-950 border border-stone-800 px-2.5 py-1.5 text-xs text-stone-200" />
                        </div>
                    );
                })}
            </div>
            <div className="rounded-xl bg-stone-950/80 border border-stone-800 p-3 text-xs font-mono text-stone-300">
                {palette.production_design_directive || buildSoundstagePaletteDirective(palette)}
            </div>
        </div>
    );
}

function SoundstageReadySignoff({ ctrl }) {
    const { brief, setField, summaryRows, setCurrentStep, launchFilm, isLaunchingFilm } = ctrl;
    return (
        <div id="soundstage-ready-signoff" className="space-y-5">
            <div className="rounded-xl border border-stone-800 overflow-hidden divide-y divide-stone-800/90 bg-stone-950/60">
                {summaryRows.map((row) => (
                    <div key={row.step} className="px-4 py-2.5 flex items-center justify-between gap-4">
                        <div className="min-w-0">
                            <span className="text-xs font-mono uppercase tracking-wider text-stone-400 block">{row.step}. {row.label}</span>
                            <span className="text-xs sm:text-sm text-stone-100 font-medium truncate block">{row.value}</span>
                        </div>
                        <button type="button" data-edit-step={row.step} onClick={() => setCurrentStep(row.step)} className="shrink-0 px-2.5 py-1 rounded-lg text-xs font-mono text-rose-300 hover:text-white bg-stone-900 hover:bg-stone-800 border border-stone-700/80 transition">Edit →</button>
                    </div>
                ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label htmlFor="soundstage-input-tagline" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">End-Card Commercial Tagline</label>
                    <input id="soundstage-input-tagline" type="text" value={brief.tagline} onChange={(e) => setField("tagline", e.target.value, true)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2.5 text-sm text-stone-100" />
                </div>
                <div>
                    <span className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Omni Flash Resolution Tier</span>
                    <div className="grid grid-cols-3 gap-2" role="group" aria-label="Resolution Tier">
                        {[{ id: "360p", label: "360p Draft" }, { id: "720p", label: "720p Standard" }, { id: "4k", label: "4K Master" }].map((tier) => (
                            <button key={tier.id} type="button" onClick={() => setField("resolution", tier.id, false)} className={`py-2 px-2.5 rounded-xl text-xs font-mono border transition ${brief.resolution === tier.id ? "bg-rose-600/25 text-rose-100 border-rose-500 font-bold" : "bg-stone-900 text-stone-300 border-stone-800 hover:border-stone-600"}`}>{tier.label}</button>
                        ))}
                    </div>
                </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-stone-800/80">
                <div className="flex items-center gap-3">
                    <button type="button" id="soundstage-toggle-manual-board-gate" role="switch" aria-checked={brief.manualBoardGate} onClick={() => setField("manualBoardGate", !brief.manualBoardGate, false)} className={`w-11 h-6 rounded-full transition p-0.5 flex items-center ${brief.manualBoardGate ? "bg-rose-600 justify-end" : "bg-stone-700 justify-start"}`}>
                        <span className="w-5 h-5 rounded-full bg-white shadow" />
                    </button>
                    <span className="text-xs text-stone-200">Manual Storyboard Approval Gate before Omni Flash filming</span>
                </div>
                <button type="button" id="soundstage-btn-make-film" disabled={isLaunchingFilm} onClick={() => launchFilm(false)} className="px-6 py-3 rounded-xl text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg transition disabled:opacity-50">
                    {isLaunchingFilm ? "Compiling Plan & Locking Cast..." : "Make the film →"}
                </button>
            </div>
        </div>
    );
}

function SoundstageStepsOneToFour({ ctrl }) {
    const { currentStep, brief, setField, selectTerritory, discovery, isDiscovering, handleDiscover } = ctrl;
    const physics = (discovery && discovery.physics) || null;
    const offerings = (discovery && Array.isArray(discovery.suggested_offerings)) ? discovery.suggested_offerings : [];

    if (currentStep === 1) {
        return (
            <div className="space-y-4">
                <div>
                    <label htmlFor="soundstage-input-subject" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Subject, Brand House, or Parody Concept</label>
                    <input id="soundstage-input-subject" type="text" value={brief.subject} onChange={(e) => setField("subject", e.target.value, false)} placeholder="e.g., Atelier Kuroda Motors, Casa Solari, or Trapwarts Alchemical Guild" className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-4 py-3 text-base text-stone-100 focus:border-rose-500" />
                </div>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Campaign inspiration presets">
                    {SOUNDSTAGE_INSPIRATION_CHIPS.map((chip) => (
                        <button key={chip.label} type="button" onClick={() => { setField("subject", chip.subject, false); setField("customDna", chip.dna, false); }} className="px-3 py-1.5 rounded-lg text-xs bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-800 transition">✦ {chip.label}</button>
                    ))}
                </div>
                <div>
                    <label htmlFor="soundstage-input-dna" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Optional Creative DNA / Aesthetic Hint</label>
                    <input id="soundstage-input-dna" type="text" value={brief.customDna} onChange={(e) => setField("customDna", e.target.value, false)} placeholder="e.g., Anamorphic nocturnal rain, tactile brushed titanium, calm minimalist pacing" className="w-full rounded-xl bg-stone-950/90 border border-stone-800 px-3.5 py-2.5 text-sm text-stone-200" />
                </div>
                <button type="button" id="soundstage-btn-discover" disabled={isDiscovering} onClick={() => handleDiscover(true)} className="px-5 py-2.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50">
                    {isDiscovering ? "Analyzing Offering Physics & Palette..." : "Discover Brief & Continue →"}
                </button>
            </div>
        );
    }
    if (currentStep === 2) {
        return (
            <div className="space-y-4">
                {offerings.length !== 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {offerings.map((item) => (
                            <button key={item.name} type="button" onClick={() => setField("offering", item.name, true)} className={`text-left rounded-xl p-3.5 border transition space-y-1 ${brief.offering === item.name ? "border-rose-500 bg-rose-950/25" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                                <span className="text-xs font-mono text-rose-300 block">{item.category || "Hero Edition"}</span>
                                <span className="text-sm font-bold text-stone-100 block">{item.name}</span>
                                <span className="text-xs text-stone-300 block">{item.description || item.rationale || ""}</span>
                            </button>
                        ))}
                    </div>
                )}
                <div>
                    <label htmlFor="soundstage-input-offering" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Hero Offering Name</label>
                    <input id="soundstage-input-offering" type="text" value={brief.offering} onChange={(e) => setField("offering", e.target.value, true)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2.5 text-sm text-stone-100" />
                </div>
                {physics && (
                    <div className="rounded-xl bg-stone-950/80 border border-stone-800 p-3.5 flex flex-wrap items-center gap-2 text-xs font-mono">
                        <span className="text-stone-400">Offering Physics:</span>
                        <span className="px-2 py-0.5 rounded bg-rose-950/70 text-rose-200 border border-rose-800/60">{physics.archetype}</span>
                        <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-200 border border-stone-700">{physics.ergonomic_role}</span>
                        <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-300 border border-stone-800">{physics.physical_scale || physics.scale_class}</span>
                        <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-300 border border-stone-800">thermal: {physics.thermal_state}</span>
                    </div>
                )}
            </div>
        );
    }
    if (currentStep === 3) {
        return (<SoundstageWorldMap territory={brief.territory} suggestedTerritories={discovery && discovery.suggested_territories} onSelectTerritory={selectTerritory} onCustomTerritoryChange={(val) => setField("territory", val, true)} />);
    }
    const presets = ["Crisp twilight · Golden-hour wet asphalt reflections", "Luminous morning · Soft limestone courtyard diffusion", "Blue-hour drizzle · Warm brass doorway reflections", "Warm late afternoon · Sunlit travertine colonnade"];
    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
                <span className="px-3 py-1.5 rounded-xl bg-rose-950/60 border border-rose-800/60 text-rose-200 font-mono text-sm font-bold">{brief.temperatureC}°C</span>
                <button type="button" onClick={() => setField("temperatureC", brief.temperatureC - 2, false)} className="px-2.5 py-1 rounded bg-stone-900 border border-stone-700 text-xs text-stone-200">-2°C</button>
                <button type="button" onClick={() => setField("temperatureC", brief.temperatureC + 2, false)} className="px-2.5 py-1 rounded bg-stone-900 border border-stone-700 text-xs text-stone-200">+2°C</button>
            </div>
            <div className="flex flex-wrap gap-2">
                {presets.map((cond) => (
                    <button key={cond} type="button" onClick={() => setField("weatherCondition", cond, true)} className={`px-3 py-1.5 rounded-lg text-xs border transition ${brief.weatherCondition === cond ? "border-rose-500 bg-rose-950/30 text-rose-100" : "border-stone-800 bg-stone-900 text-stone-300"}`}>{cond}</button>
                ))}
            </div>
            <div>
                <label htmlFor="soundstage-input-weather" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Atmospheric &amp; Micro-Climate Directive</label>
                <input id="soundstage-input-weather" type="text" value={brief.weatherCondition} onChange={(e) => setField("weatherCondition", e.target.value, true)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2.5 text-sm text-stone-100" />
            </div>
            <div className="rounded-xl bg-stone-950/70 border border-stone-800 p-3.5 space-y-1 text-xs text-stone-300">
                <p><strong className="text-stone-200">Optical Lighting:</strong> {brief.lightingDirective}</p>
                <p><strong className="text-stone-200">Cultural Pulse:</strong> {brief.culturalPulse}</p>
            </div>
        </div>
    );
}

function SoundstageStepsFiveToTen({ ctrl, addToast, getDisplayableRefUrl }) {
    const { currentStep, brief, setField, discovery, emblemCandidates, packshotCandidates, isSynthesizingEmblem, isSynthesizingPackshot, handleSynthesizeAsset } = ctrl;
    if (currentStep === 5) {
        return (<SoundstageEmblemPlate palette={brief.palette} emblemUrl={brief.emblemUrl} setEmblemUrl={(val) => setField("emblemUrl", val, false)} emblemCandidates={emblemCandidates} isSynthesizing={isSynthesizingEmblem} onSynthesizeEmblem={() => handleSynthesizeAsset("emblem")} addToast={addToast} getDisplayableRefUrl={getDisplayableRefUrl} />);
    }
    if (currentStep === 6) {
        return (<SoundstagePaletteEditor palette={brief.palette} onChangePalette={(pal) => setField("palette", pal, true)} />);
    }
    if (currentStep === 7) {
        const moments = (discovery && Array.isArray(discovery.cultural_moments) && discovery.cultural_moments.length !== 0)
            ? discovery.cultural_moments
            : [
                { title: "Twilight Threshold Ritual", description: "Transitioning from metropolitan kinetic flow into calm focus." },
                { title: "Golden-Hour Craft Pause", description: "Sensory interlude bathed in directional late-afternoon architectural light." },
                { title: "After-Hours Studio Solitude", description: "Quiet nocturnal mastery when tactile craftsmanship takes center stage." }
            ];
        return (
            <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {moments.map((m) => {
                        const title = m.title || m.label || "Cultural Ritual";
                        return (
                            <button key={title} type="button" onClick={() => setField("moment", title, true)} className={`text-left rounded-xl p-3.5 border transition space-y-1 ${brief.moment === title ? "border-rose-500 bg-rose-950/25" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                                <span className="text-sm font-bold text-stone-100 block">{title}</span>
                                <span className="text-xs text-stone-300 block">{m.description || m.context || ""}</span>
                            </button>
                        );
                    })}
                </div>
                <div>
                    <label htmlFor="soundstage-input-moment" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Cultural Moment or Human Ritual</label>
                    <input id="soundstage-input-moment" type="text" value={brief.moment} onChange={(e) => setField("moment", e.target.value, true)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2.5 text-sm text-stone-100" />
                </div>
            </div>
        );
    }
    if (currentStep === 8) {
        const languages = (discovery && Array.isArray(discovery.spoken_languages) && discovery.spoken_languages.length !== 0) ? discovery.spoken_languages : SOUNDSTAGE_DEFAULT_LANGUAGES;
        return (
            <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {languages.map((lang) => (
                        <button key={lang.code || lang.label} type="button" onClick={() => { setField("language", lang.label, false); if (lang.vocal_cadence) setField("vocalCadence", lang.vocal_cadence, false); }} className={`text-left rounded-xl p-3 border transition space-y-1 ${brief.language === lang.label ? "border-rose-500 bg-rose-950/25" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-bold text-stone-100">{lang.label}</span>
                                <span className="text-xs font-mono uppercase text-rose-300">{lang.code}</span>
                            </div>
                            <p className="text-xs text-stone-300">{lang.vocal_cadence}</p>
                        </button>
                    ))}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                        <label htmlFor="soundstage-input-language" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Spoken Language</label>
                        <input id="soundstage-input-language" type="text" value={brief.language} onChange={(e) => setField("language", e.target.value, false)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2 text-sm text-stone-100" />
                    </div>
                    <div>
                        <label htmlFor="soundstage-input-cadence" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Vocal Cadence &amp; Delivery</label>
                        <input id="soundstage-input-cadence" type="text" value={brief.vocalCadence} onChange={(e) => setField("vocalCadence", e.target.value, false)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2 text-sm text-stone-100" />
                    </div>
                </div>
            </div>
        );
    }
    if (currentStep === 9) {
        const displayPackshot = brief.packshotUrl ? getDisplayableRefUrl(brief.packshotUrl) : "";
        const packCandidates = Array.isArray(packshotCandidates) ? packshotCandidates : [];
        return (
            <div className="space-y-4">
                <div className="rounded-xl border border-stone-800 bg-stone-950/80 p-5 flex flex-col items-center justify-center min-h-[152px]">
                    {displayPackshot ? (<img src={displayPackshot} alt="Hero offering packshot reference" className="max-h-36 object-contain rounded-lg" />) : (<p className="text-xs font-mono text-stone-400 text-center">No custom packshot locked yet — synthesize a studio packshot or upload a 1:1 product photograph.</p>)}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <label htmlFor="soundstage-packshot-upload" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Upload Hero Packshot (&lt;= 10 MiB)</label>
                        <input id="soundstage-packshot-upload" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={(e) => readSoundstageFileAsDataUrl(e.target.files && e.target.files[0], addToast, (url) => setField("packshotUrl", url, false))} className="w-full text-xs text-stone-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-stone-800 file:text-stone-100 hover:file:bg-stone-700" />
                    </div>
                    <div>
                        <label htmlFor="soundstage-input-packshot-url" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Direct Packshot URI</label>
                        <input id="soundstage-input-packshot-url" type="text" value={brief.packshotUrl} onChange={(e) => setField("packshotUrl", e.target.value, false)} placeholder="gs://... or https://..." className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3 py-2 text-xs text-stone-100" />
                    </div>
                </div>
                <button type="button" id="soundstage-btn-synthesize-packshot" disabled={isSynthesizingPackshot} onClick={() => handleSynthesizeAsset("packshot")} className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50">
                    {isSynthesizingPackshot ? "Synthesizing Studio Packshots..." : "Synthesize Hero Packshot"}
                </button>
                {packCandidates.length !== 0 && (
                    <div className="grid grid-cols-3 gap-2.5">
                        {packCandidates.map((candUrl, idx) => (
                            <button key={`${candUrl}_${idx}`} type="button" onClick={() => setField("packshotUrl", candUrl, false)} className={`p-2 rounded-xl border transition ${candUrl === brief.packshotUrl ? "border-rose-500 bg-rose-950/30" : "border-stone-800 bg-stone-950/60"}`}>
                                <img src={getDisplayableRefUrl(candUrl)} alt={`Packshot candidate ${idx + 1}`} className="h-20 w-full object-cover rounded" />
                            </button>
                        ))}
                    </div>
                )}
            </div>
        );
    }
    return (<SoundstageReadySignoff ctrl={ctrl} />);
}

function SoundstageGuidedIntake({ ctrl, fullscreenFocus, setFullscreenFocus, addToast, getDisplayableRefUrl }) {
    const { guidedBriefMode, setGuidedBriefMode, activeRun, setViewMode, currentStep, setCurrentStep, brief, setField, launchFilm, isLaunchingFilm } = ctrl;
    const stepMeta = SOUNDSTAGE_STEPS[currentStep - 1] || SOUNDSTAGE_STEPS[0];
    const isEarlyStep = currentStep <= 4;

    return (
        <section aria-label="Mode 5 Commercial Soundstage Brief" className="sstage-canvas rounded-2xl p-6 sm:p-8 border border-stone-800/80 shadow-2xl space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-800/80 pb-4">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold block">Mode 5 · Commercial Soundstage</span>
                    <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-100">30s Master + 15s Cutdown + 6s Bumper Campaign Director</h2>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex items-center gap-2 bg-stone-950/90 border border-stone-800 rounded-xl px-3 py-1.5">
                        <span className="text-xs font-medium text-stone-200">Guide the brief</span>
                        <button type="button" id="soundstage-toggle-guided" role="switch" aria-checked={guidedBriefMode} onClick={() => setGuidedBriefMode(!guidedBriefMode)} className={`w-10 h-5 rounded-full transition p-0.5 flex items-center ${guidedBriefMode ? "bg-rose-600 justify-end" : "bg-stone-700 justify-start"}`}>
                            <span className="w-4 h-4 rounded-full bg-white shadow" />
                        </button>
                    </div>
                    <button type="button" id="soundstage-btn-fullscreen" onClick={() => setFullscreenFocus(!fullscreenFocus)} className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition">
                        {fullscreenFocus ? "Exit Fullscreen Focus" : "Fullscreen Focus"}
                    </button>
                    {activeRun && (
                        <button type="button" id="soundstage-btn-return-production" onClick={() => setViewMode("production")} className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-rose-950/80 hover:bg-rose-900 text-rose-100 border border-rose-700/70 transition">Return to Production Room →</button>
                    )}
                </div>
            </div>

            {!guidedBriefMode ? (
                <div id="soundstage-express-canvas" className="sstage-card rounded-2xl p-6 space-y-5 max-w-3xl mx-auto">
                    <div className="space-y-1">
                        <h3 className="text-lg font-bold text-stone-100">Express Soundstage Canvas</h3>
                        <p className="text-xs text-stone-300">Enter a commercial brand or parody concept. Soundstage automatically deduces offering physics, 60/30/10 palette, and lead cast anchors.</p>
                    </div>
                    <div>
                        <label htmlFor="soundstage-express-subject" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Subject, Brand, or Parody Concept</label>
                        <input id="soundstage-express-subject" type="text" value={brief.subject} onChange={(e) => setField("subject", e.target.value, false)} placeholder="e.g., Atelier Kuroda Motors or Trapwarts Alchemical Guild" className="w-full rounded-xl bg-stone-950 border border-stone-700 px-4 py-3 text-base text-stone-100 focus:border-rose-500" />
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {SOUNDSTAGE_INSPIRATION_CHIPS.map((chip) => (
                            <button key={chip.label} type="button" onClick={() => { setField("subject", chip.subject, false); setField("customDna", chip.dna, false); }} className="px-3 py-1.5 rounded-lg text-xs bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-800 transition">✦ {chip.label}</button>
                        ))}
                    </div>
                    <div>
                        <label htmlFor="soundstage-express-dna" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Optional 1-Line Creative DNA or Hero Offering Hint</label>
                        <input id="soundstage-express-dna" type="text" value={brief.customDna} onChange={(e) => setField("customDna", e.target.value, false)} placeholder="e.g., Nocturne grand touring coupe in wet Tokyo twilight" className="w-full rounded-xl bg-stone-950 border border-stone-800 px-3.5 py-2.5 text-sm text-stone-200" />
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-stone-800">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="flex items-center gap-1.5" role="group" aria-label="Express Resolution Tier">
                                {["360p", "720p", "4k"].map((tier) => (
                                    <button key={tier} type="button" onClick={() => setField("resolution", tier, false)} className={`px-2.5 py-1 rounded-lg text-xs font-mono border ${brief.resolution === tier ? "bg-rose-600/25 text-rose-100 border-rose-500 font-bold" : "bg-stone-900 text-stone-300 border-stone-800"}`}>{tier}</button>
                                ))}
                            </div>
                            <button type="button" role="switch" aria-checked={brief.manualBoardGate} onClick={() => setField("manualBoardGate", !brief.manualBoardGate, false)} className="text-xs text-stone-300 hover:text-stone-100 px-2.5 py-1 rounded-lg bg-stone-900 border border-stone-800">
                                Manual Board Gate: {brief.manualBoardGate ? "On" : "Off"}
                            </button>
                        </div>
                        <button type="button" id="soundstage-btn-make-film-express" disabled={isLaunchingFilm} onClick={() => launchFilm(true)} className="px-6 py-3 rounded-xl text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg transition disabled:opacity-50">
                            {isLaunchingFilm ? "Launching Soundstage..." : "Make the film →"}
                        </button>
                    </div>
                </div>
            ) : (
                <div id="soundstage-guided-canvas" className="space-y-5">
                    <nav aria-label="10-Step Soundstage Brief Progress" className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-1.5">
                        {SOUNDSTAGE_STEPS.map((st) => {
                            const isCurrent = st.num === currentStep;
                            const cls = isCurrent ? "bg-rose-600/25 text-rose-100 border-rose-500 font-bold" : st.num < currentStep ? "bg-stone-900/90 text-stone-200 border-stone-700" : "bg-stone-950/60 text-stone-400 border-stone-800/80 hover:text-stone-200";
                            return (
                                <button key={st.num} type="button" data-step-rail={st.num} aria-current={isCurrent ? "step" : undefined} onClick={() => setCurrentStep(st.num)} className={`px-2.5 py-2 rounded-xl border text-left transition ${cls}`}>
                                    <span className="text-xs font-mono block opacity-80">{String(st.num).padStart(2, "0")}</span>
                                    <span className="text-xs truncate block">{st.shortLabel}</span>
                                </button>
                            );
                        })}
                    </nav>
                    <div className="sstage-card rounded-2xl p-6 space-y-5">
                        <div className="border-b border-stone-800/80 pb-3.5">
                            <h3 className="text-lg font-bold text-stone-100">{stepMeta.title}</h3>
                            <p className="text-xs text-stone-300 mt-0.5">{stepMeta.subtitle}</p>
                        </div>
                        {isEarlyStep ? (<SoundstageStepsOneToFour ctrl={ctrl} />) : (<SoundstageStepsFiveToTen ctrl={ctrl} addToast={addToast} getDisplayableRefUrl={getDisplayableRefUrl} />)}
                        <div className="flex items-center justify-between pt-4 border-t border-stone-800/80">
                            <button type="button" disabled={currentStep === 1} onClick={() => setCurrentStep(Math.max(1, currentStep - 1))} className="px-4 py-2 rounded-xl text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition disabled:opacity-40">← Previous</button>
                            {currentStep !== 10 && (<button type="button" onClick={() => setCurrentStep(Math.min(10, currentStep + 1))} className="px-4 py-2 rounded-xl text-xs font-semibold bg-stone-100 hover:bg-white text-stone-950 transition">Continue →</button>)}
                        </div>
                    </div>
                </div>
            )}
        </section>
    );
}

function useSoundstageBriefController({ activeProject, sessionName, addToast }) {
    const [viewMode, setViewMode] = useState("intake");
    const [guidedBriefMode, setGuidedBriefMode] = useState(true);
    const [currentStep, setCurrentStep] = useState(1);
    const [activeRun, setActiveRun] = useState(null);
    const [discovery, setDiscovery] = useState(null);
    const [editedFields, setEditedFields] = useState({});
    const [errorBanner, setErrorBanner] = useState("");
    const [emblemCandidates, setEmblemCandidates] = useState([]);
    const [packshotCandidates, setPackshotCandidates] = useState([]);
    const [isDiscovering, setIsDiscovering] = useState(false);
    const [isSynthesizingEmblem, setIsSynthesizingEmblem] = useState(false);
    const [isSynthesizingPackshot, setIsSynthesizingPackshot] = useState(false);
    const [isLaunchingFilm, setIsLaunchingFilm] = useState(false);
    const [brief, setBrief] = useState(() => ({
        subject: "Atelier Kuroda Motors", customDna: "", offering: "Signature Grand Touring Coupe",
        territory: "Tokyo · Aoyama", temperatureC: 16, weatherCondition: "Crisp twilight · Golden-hour wet asphalt reflections",
        lightingDirective: SOUNDSTAGE_WORLD_TERRITORIES[9].lighting_directive, culturalPulse: SOUNDSTAGE_WORLD_TERRITORIES[9].cultural_pulse,
        emblemUrl: "", palette: { ...SOUNDSTAGE_PALETTE_PRESETS[0], production_design_directive: buildSoundstagePaletteDirective(SOUNDSTAGE_PALETTE_PRESETS[0]) },
        moment: "Twilight Threshold Ritual", language: "English", vocalCadence: SOUNDSTAGE_DEFAULT_LANGUAGES[0].vocal_cadence,
        packshotUrl: "", tagline: "Precision crafted for the quiet pulse of Tokyo.", resolution: "720p", manualBoardGate: false
    }));

    const setField = (key, value, trackEdit) => {
        if (trackEdit) setEditedFields((prev) => ({ ...prev, [key]: true }));
        setBrief((prev) => ({ ...prev, [key]: value }));
    };
    const selectTerritory = (spec) => {
        setEditedFields((prev) => ({ ...prev, territory: true }));
        setBrief((prev) => ({
            ...prev, territory: spec.place_name,
            temperatureC: typeof spec.temperature_c === "number" ? spec.temperature_c : prev.temperatureC,
            weatherCondition: spec.condition || prev.weatherCondition,
            lightingDirective: spec.lighting_directive || prev.lightingDirective,
            culturalPulse: spec.cultural_pulse || prev.culturalPulse
        }));
    };
    const safeSessionName = String(sessionName || "soundstage_session").replace(/[^A-Za-z0-9_-]/g, "_") || "soundstage_session";

    const postJson = async (url, payload) => {
        const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error((data && data.detail) || `Soundstage request failed (${resp.status})`);
        return data;
    };

    const applyDiscoveryDefaults = (disc) => {
        setDiscovery(disc);
        setBrief((prev) => {
            const next = { ...prev };
            if (!editedFields.offering && disc.suggested_offerings && disc.suggested_offerings[0]) next.offering = disc.suggested_offerings[0].name;
            if (!editedFields.territory && disc.suggested_territories && disc.suggested_territories[0]) {
                const t0 = disc.suggested_territories[0];
                next.territory = t0.place_name;
                next.temperatureC = t0.temperature_c;
                if (!editedFields.weatherCondition) next.weatherCondition = t0.condition;
                next.lightingDirective = t0.lighting_directive;
                next.culturalPulse = t0.cultural_pulse;
            }
            if (!editedFields.palette && disc.palette) next.palette = disc.palette;
            if (!editedFields.moment && disc.cultural_moments && disc.cultural_moments[0]) next.moment = disc.cultural_moments[0].title || disc.cultural_moments[0].label || prev.moment;
            if (!editedFields.tagline && disc.tagline) next.tagline = disc.tagline;
            return next;
        });
    };

    const handleDiscover = async (advanceStep) => {
        const cleanSubj = String(brief.subject || "").trim();
        if (!cleanSubj) { setErrorBanner("Enter a Subject, Brand House, or Parody Concept to discover the brief."); return null; }
        setErrorBanner(""); setIsDiscovering(true);
        try {
            const disc = await postJson("/api/soundstage/discover", { subject: cleanSubj, offering: editedFields.offering ? brief.offering : null, territory: editedFields.territory ? brief.territory : null, custom_dna: brief.customDna || null });
            applyDiscoveryDefaults(disc);
            if (advanceStep) setCurrentStep(2);
            return disc;
        } catch (err) { setErrorBanner(err.message || "Discovery failed."); return null; } finally { setIsDiscovering(false); }
    };

    const buildPlanPayload = (ov = {}) => ({
        subject: String(brief.subject || "").trim() || "Artisan Studio",
        offering: (ov.offering !== undefined ? ov.offering : brief.offering) || null,
        territory: (ov.territory !== undefined ? ov.territory : brief.territory) || null,
        weather_condition: (ov.weather_condition !== undefined ? ov.weather_condition : brief.weatherCondition) || null,
        tagline: (ov.tagline !== undefined ? ov.tagline : brief.tagline) || null,
        palette_hexes: ov.palette_hexes || brief.palette,
        moment: (ov.moment !== undefined ? ov.moment : brief.moment) || null,
        language: brief.language || "English", vocal_cadence: brief.vocalCadence || null,
        emblem_url: brief.emblemUrl || null, packshot_url: brief.packshotUrl || null,
        custom_dna: brief.customDna || null, manual_board_gate: brief.manualBoardGate,
        resolution: brief.resolution, session_name: safeSessionName, project_name: activeProject || "default_project"
    });

    const handleSynthesizeAsset = async (assetAction) => {
        const isEmblem = assetAction === "emblem";
        if (isEmblem) setIsSynthesizingEmblem(true); else setIsSynthesizingPackshot(true);
        setErrorBanner("");
        try {
            let targetRunId = activeRun && activeRun.run_id;
            if (!targetRunId) {
                const draftRun = await postJson("/api/soundstage/plan", buildPlanPayload());
                setActiveRun(draftRun); targetRunId = draftRun.run_id;
            }
            const updatedRun = await postJson("/api/soundstage/cast", { run_id: targetRunId, action: assetAction, candidate_count: 3 });
            setActiveRun(updatedRun);
            const kit = updatedRun.reference_kit || {};
            if (isEmblem) { setEmblemCandidates(kit.emblem_candidates || []); if (kit.emblem_url) setField("emblemUrl", kit.emblem_url, false); }
            else { setPackshotCandidates(kit.packshot_candidates || []); if (kit.packshot_url) setField("packshotUrl", kit.packshot_url, false); }
        } catch (err) { setErrorBanner(err.message || `Could not synthesize ${assetAction}.`); }
        finally { if (isEmblem) setIsSynthesizingEmblem(false); else setIsSynthesizingPackshot(false); }
    };

    const launchFilm = async (isExpress) => {
        const cleanSubj = String(brief.subject || "").trim();
        if (!cleanSubj) { setErrorBanner("Enter a Subject, Brand House, or Parody Concept before rolling cameras."); return; }
        setErrorBanner(""); setIsLaunchingFilm(true);
        try {
            let planOverrides = {};
            if (isExpress) {
                const disc = await postJson("/api/soundstage/discover", { subject: cleanSubj, offering: brief.customDna || null, territory: null, custom_dna: brief.customDna || null });
                applyDiscoveryDefaults(disc);
                const firstOff = disc.suggested_offerings && disc.suggested_offerings[0] && disc.suggested_offerings[0].name;
                const firstTerr = disc.suggested_territories && disc.suggested_territories[0];
                planOverrides = { offering: firstOff || brief.offering, territory: (firstTerr && firstTerr.place_name) || brief.territory, weather_condition: (firstTerr && firstTerr.condition) || brief.weatherCondition, tagline: disc.tagline || brief.tagline, palette_hexes: disc.palette || brief.palette };
            }
            const plannedRun = await postJson("/api/soundstage/plan", buildPlanPayload(planOverrides));
            const castReadyRun = await postJson("/api/soundstage/cast", { run_id: plannedRun.run_id, action: "generate", candidate_count: 2 });
            setActiveRun(castReadyRun); setViewMode("production");
            if (addToast) addToast("Commercial Soundstage plan & lead cast locked.", "success");
        } catch (err) { setErrorBanner(err.message || "Failed to launch Commercial Soundstage run."); }
        finally { setIsLaunchingFilm(false); }
    };

    const summaryRows = [
        { step: 1, label: "Subject / Brand", value: brief.subject || "Unset" },
        { step: 2, label: "Hero Offering", value: brief.offering || "Signature Edition" },
        { step: 3, label: "Filming Territory", value: brief.territory || "Tokyo · Aoyama" },
        { step: 4, label: "Weather & Atmosphere", value: `${brief.temperatureC}°C · ${brief.weatherCondition}` },
        { step: 5, label: "Studio Emblem", value: brief.emblemUrl ? "Custom / Synthesized Studio Mark Locked" : "Clean Typographic End-Card Plate" },
        { step: 6, label: "60 / 30 / 10 Palette", value: `${brief.palette.primary_name} (${brief.palette.primary_hex}) · ${brief.palette.secondary_name} · ${brief.palette.neutral_name}` },
        { step: 7, label: "Cultural Moment", value: brief.moment },
        { step: 8, label: "Language & Cadence", value: `${brief.language} · ${brief.vocalCadence}` },
        { step: 9, label: "Hero Packshot", value: brief.packshotUrl ? "1:1 Hero Packshot Anchor Locked" : "Auto-Synthesize Hero Packshot on Cast Stage" }
    ];

    return {
        viewMode, setViewMode, guidedBriefMode, setGuidedBriefMode, currentStep, setCurrentStep,
        activeRun, setActiveRun, discovery, errorBanner, setErrorBanner, emblemCandidates, packshotCandidates,
        isDiscovering, isSynthesizingEmblem, isSynthesizingPackshot, isLaunchingFilm,
        brief, setField, selectTerritory, handleDiscover, handleSynthesizeAsset, launchFilm, summaryRows
    };
}

function SoundstageStudio(props) {
    const {
        activeProject, sessionName, setSessionName, vaultCharacters, addToast,
        getDisplayableRefUrl, fullscreenFocus, setFullscreenFocus, onPromoteToMode2, onPromoteToMode3
    } = props;
    const ctrl = useSoundstageBriefController({ activeProject, sessionName, addToast });

    return (
        <div className="space-y-4">
            {ctrl.errorBanner && (
                <div role="alert" className="rounded-xl bg-rose-950/80 border border-rose-500/80 px-4 py-3 flex items-center justify-between gap-4 text-xs text-rose-100">
                    <span>{ctrl.errorBanner}</span>
                    <button type="button" onClick={() => ctrl.setErrorBanner("")} className="font-mono text-rose-200 hover:text-white">Dismiss ✕</button>
                </div>
            )}
            {ctrl.viewMode === "production" && ctrl.activeRun ? (
                <SoundstageProductionRoom
                    activeRun={ctrl.activeRun}
                    setActiveRun={ctrl.setActiveRun}
                    onEditBrief={() => ctrl.setViewMode("intake")}
                    fullscreenFocus={fullscreenFocus}
                    setFullscreenFocus={setFullscreenFocus}
                    setSessionName={setSessionName}
                    vaultCharacters={vaultCharacters}
                    addToast={addToast}
                    getDisplayableRefUrl={getDisplayableRefUrl}
                    onPromoteToMode2={onPromoteToMode2}
                    onPromoteToMode3={onPromoteToMode3}
                />
            ) : (
                <SoundstageGuidedIntake
                    ctrl={ctrl}
                    fullscreenFocus={fullscreenFocus}
                    setFullscreenFocus={setFullscreenFocus}
                    addToast={addToast}
                    getDisplayableRefUrl={getDisplayableRefUrl}
                />
            )}
        </div>
    );
}
