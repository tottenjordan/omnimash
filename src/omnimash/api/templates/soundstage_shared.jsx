// Mode 5: Commercial Soundstage — Shared Constants, Media Security, & Fetch Helpers (Modular JSX Partial)

const SOUNDSTAGE_MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const SOUNDSTAGE_MAX_MEDIA_URI_CHARS = 14 * 1024 * 1024;
const SOUNDSTAGE_HEX_PATTERN = /^#[0-9A-Fa-f]{6}$/;
const SOUNDSTAGE_DATA_IMAGE_PATTERN = /^data:image\/(png|jpeg|jpg|webp|svg\+xml);base64,[A-Za-z0-9+/=\s]+$/i;
const SOUNDSTAGE_HTTP_URL_PATTERN = new RegExp("^https?://", "i");
const SOUNDSTAGE_GS_URL_PATTERN = new RegExp("^gs://", "i");
const SOUNDSTAGE_LOCAL_MEDIA_PATTERN = new RegExp("^/(static|api/media-proxy)(/|$|\\?)");
const SOUNDSTAGE_NEUTRAL_DEFAULT_TAGLINE = "Precision crafted for quiet architectural mastery.";

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

const SOUNDSTAGE_FALLBACK_PLATE_DATA_URI = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NDAgMzYwIj48cmVjdCB3aWR0aD0iNjQwIiBoZWlnaHQ9IjM2MCIgZmlsbD0iIzA5MGEwZiIvPjxyZWN0IHg9IjIwIiB5PSIyMCIgd2lkdGg9IjYwMCIgaGVpZ2h0PSIzMjAiIHJ4PSIxNiIgZmlsbD0iIzE3MWEyNCIgc3Ryb2tlPSIjZTExZDQ4IiBzdHJva2Utb3BhY2l0eT0iMC41IiBzdHJva2Utd2lkdGg9IjIiLz48Y2lyY2xlIGN4PSIzMjAiIGN5PSIxNDIiIHI9IjQyIiBmaWxsPSIjMjkyNTI0IiBzdHJva2U9IiNmNWYyZWIiIHN0cm9rZS1vcGFjaXR5PSIwLjQiIHN0cm9rZS13aWR0aD0iMiIvPjxwYXRoIGQ9Ik0yNDQgMjU2IEMyNDQgMjEyIDM5NiAyMTIgMzk2IDI1NiBaIiBmaWxsPSIjMjkyNTI0IiBzdHJva2U9IiNmNWYyZWIiIHN0cm9rZS1vcGFjaXR5PSIwLjMiIHN0cm9rZS13aWR0aD0iMiIvPjx0ZXh0IHg9IjMyMCIgeT0iMzAyIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjZjVmMmViIiBmb250LWZhbWlseT0ibW9ub3NwYWNlIiBmb250LXNpemU9IjEzIiBsZXR0ZXItc3BhY2luZz0iMiI+U09VTkRTVEFHRSBTVFVESU8gQU5DSE9SIExPQ0tFRDwvdGV4dD48L3N2Zz4=";

const SOUNDSTAGE_PROD_STAGES = [
    { id: "brief", label: "1. Brief" },
    { id: "world", label: "2. World" },
    { id: "story", label: "3. Story" },
    { id: "cast", label: "4. Cast Gate" },
    { id: "boards", label: "5. 3×3 Boards" },
    { id: "filming", label: "6. Filming" },
    { id: "premiere", label: "7. Premiere" }
];

const SOUNDSTAGE_FILMING_TIERS = ["360p", "720p", "4k"];

const SOUNDSTAGE_FORMAT_META = {
    "30s": { id: "30s", label: "30s Master (16:9)", aspectLabel: "16:9 Master Broadcast", field: "master_30s_16x9_url", isVertical: false },
    "15s": { id: "15s", label: "15s Cutdown (9:16)", aspectLabel: "9:16 Social Vertical", field: "cutdown_15s_9x16_url", isVertical: true },
    "6s": { id: "6s", label: "6s Bumper (9:16)", aspectLabel: "9:16 High-Impact Bumper", field: "bumper_6s_9x16_url", isVertical: true }
};

const SOUNDSTAGE_VARIATION_AXES = [
    { axis: "place", label: "Place", description: "Repoint filming territory & micro-climate", chips: ["Milan · Brera", "Kyoto · Higashiyama", "Reykjavik · Harbor"] },
    { axis: "cast", label: "Cast", description: "Recast lead commercial persona in isolated session", chips: ["Seasoned Horologist", "Contemporary Architect", "Nocturnal Couturier"] },
    { axis: "offering", label: "Offering", description: "Adapt edition & physical hero packshot", chips: ["Limited Collector Edition", "Travel Ritual Kit", "Nocturne Reserve"] }
];

const SOUNDSTAGE_CANONICAL_SUBSHOTS = [
    { shot_id: "1.1", act_index: 0, default_start_sec: 0.0, default_duration_sec: 3.3 },
    { shot_id: "1.2", act_index: 0, default_start_sec: 3.3, default_duration_sec: 3.4 },
    { shot_id: "1.3", act_index: 0, default_start_sec: 6.7, default_duration_sec: 3.3 },
    { shot_id: "2.1", act_index: 1, default_start_sec: 0.0, default_duration_sec: 3.3 },
    { shot_id: "2.2", act_index: 1, default_start_sec: 3.3, default_duration_sec: 3.4 },
    { shot_id: "2.3", act_index: 1, default_start_sec: 6.7, default_duration_sec: 3.3 },
    { shot_id: "3.1", act_index: 2, default_start_sec: 0.0, default_duration_sec: 3.3 },
    { shot_id: "3.2", act_index: 2, default_start_sec: 3.3, default_duration_sec: 3.4 },
    { shot_id: "3.3", act_index: 2, default_start_sec: 6.7, default_duration_sec: 3.3 }
];

function cleanSoundstageOptionalText(val) {
    const trimmed = String(val === null || val === undefined ? "" : val).trim();
    return trimmed || null;
}

function isAllowedSoundstageMediaUri(rawUrl) {
    const trimmed = String(rawUrl || "").trim();
    if (!trimmed || trimmed.length > SOUNDSTAGE_MAX_MEDIA_URI_CHARS) return false;
    return SOUNDSTAGE_HTTP_URL_PATTERN.test(trimmed)
        || SOUNDSTAGE_GS_URL_PATTERN.test(trimmed)
        || SOUNDSTAGE_LOCAL_MEDIA_PATTERN.test(trimmed)
        || SOUNDSTAGE_DATA_IMAGE_PATTERN.test(trimmed);
}

function getSafeSoundstageMediaUrl(rawUrl, getDisplayableRefUrl) {
    const trimmed = String(rawUrl || "").trim();
    if (!isAllowedSoundstageMediaUri(trimmed)) return "";
    if (SOUNDSTAGE_DATA_IMAGE_PATTERN.test(trimmed)) return trimmed;
    return typeof getDisplayableRefUrl === "function" ? getDisplayableRefUrl(trimmed) : trimmed;
}

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

function sanitizeSoundstageIdentifier(raw, fallback) {
    const cleaned = String(raw || "").trim().replace(/[^A-Za-z0-9_-]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "").slice(0, 128);
    return cleaned || fallback;
}

function computePlanSignature(b, safeProjectName, safeSessionName) {
    return JSON.stringify({
        projectName: safeProjectName || "",
        sessionName: safeSessionName || "",
        subject: cleanSoundstageOptionalText(b && b.subject) || "",
        offering: cleanSoundstageOptionalText(b && b.offering) || "",
        territory: cleanSoundstageOptionalText(b && b.territory) || "",
        weatherCondition: cleanSoundstageOptionalText(b && b.weatherCondition) || "",
        tagline: cleanSoundstageOptionalText(b && b.tagline) || "",
        palette: (b && b.palette) || null,
        moment: cleanSoundstageOptionalText(b && b.moment) || "",
        language: cleanSoundstageOptionalText(b && b.language) || "English",
        vocalCadence: cleanSoundstageOptionalText(b && b.vocalCadence) || "",
        customDna: cleanSoundstageOptionalText(b && b.customDna) || ""
    });
}

function buildSoundstagePlanPayload(brief, safeSessionName, safeProjectName, ov = {}) {
    return {
        subject: cleanSoundstageOptionalText(brief.subject) || "Artisan Studio",
        offering: cleanSoundstageOptionalText(ov.offering !== undefined ? ov.offering : brief.offering),
        territory: cleanSoundstageOptionalText(ov.territory !== undefined ? ov.territory : brief.territory),
        weather_condition: cleanSoundstageOptionalText(ov.weather_condition !== undefined ? ov.weather_condition : brief.weatherCondition),
        tagline: cleanSoundstageOptionalText(ov.tagline !== undefined ? ov.tagline : brief.tagline),
        palette_hexes: ov.palette_hexes || brief.palette,
        moment: cleanSoundstageOptionalText(ov.moment !== undefined ? ov.moment : brief.moment),
        language: cleanSoundstageOptionalText(ov.language !== undefined ? ov.language : brief.language) || "English",
        vocal_cadence: cleanSoundstageOptionalText(ov.vocal_cadence !== undefined ? ov.vocal_cadence : brief.vocalCadence),
        emblem_url: cleanSoundstageOptionalText(brief.emblemUrl),
        packshot_url: cleanSoundstageOptionalText(brief.packshotUrl),
        custom_dna: cleanSoundstageOptionalText(brief.customDna),
        manual_board_gate: brief.manualBoardGate,
        resolution: brief.resolution,
        session_name: safeSessionName,
        project_name: safeProjectName
    };
}

function mergeSoundstageDiscoveryBrief(prev, disc, liveEdits) {
    const next = { ...prev };
    if (!liveEdits.offering && disc.suggested_offerings && disc.suggested_offerings[0]) next.offering = disc.suggested_offerings[0].name;
    if (!liveEdits.territory && disc.suggested_territories && disc.suggested_territories[0]) {
        const t0 = disc.suggested_territories[0];
        next.territory = t0.place_name;
        next.temperatureC = t0.temperature_c;
        if (!liveEdits.weatherCondition) next.weatherCondition = t0.condition;
        next.lightingDirective = t0.lighting_directive;
        next.culturalPulse = t0.cultural_pulse;
    }
    if (!liveEdits.palette && disc.palette) next.palette = disc.palette;
    if (!liveEdits.moment && disc.cultural_moments && disc.cultural_moments[0]) next.moment = disc.cultural_moments[0].title || disc.cultural_moments[0].label || prev.moment;
    if (!liveEdits.language && disc.spoken_languages && disc.spoken_languages[0]) {
        const l0 = disc.spoken_languages[0];
        if (l0.label) next.language = l0.label;
        if (!liveEdits.vocalCadence && l0.vocal_cadence) next.vocalCadence = l0.vocal_cadence;
    }
    if (!liveEdits.tagline && disc.tagline) next.tagline = disc.tagline;
    return next;
}

function buildSoundstageExpressOverrides(disc, brief, liveEdits) {
    const firstOff = disc.suggested_offerings && disc.suggested_offerings[0] && disc.suggested_offerings[0].name;
    const firstTerr = disc.suggested_territories && disc.suggested_territories[0];
    const firstMoment = disc.cultural_moments && disc.cultural_moments[0] && (disc.cultural_moments[0].title || disc.cultural_moments[0].label);
    const firstLang = disc.spoken_languages && disc.spoken_languages[0];
    return {
        offering: liveEdits.offering ? brief.offering : (firstOff || brief.offering),
        territory: liveEdits.territory ? brief.territory : ((firstTerr && firstTerr.place_name) || brief.territory),
        weather_condition: liveEdits.weatherCondition ? brief.weatherCondition : ((firstTerr && firstTerr.condition) || brief.weatherCondition),
        tagline: liveEdits.tagline ? brief.tagline : (disc.tagline || brief.tagline),
        palette_hexes: liveEdits.palette ? brief.palette : (disc.palette || brief.palette),
        moment: liveEdits.moment ? brief.moment : (firstMoment || brief.moment),
        language: liveEdits.language ? brief.language : ((firstLang && firstLang.label) || brief.language),
        vocal_cadence: liveEdits.vocalCadence ? brief.vocalCadence : ((firstLang && firstLang.vocal_cadence) || brief.vocalCadence)
    };
}

function buildSoundstageSummaryRows(brief) {
    const hasValidEmblem = Boolean(getSafeSoundstageMediaUrl(brief.emblemUrl, null));
    const hasValidPackshot = Boolean(getSafeSoundstageMediaUrl(brief.packshotUrl, null));
    const displayLang = cleanSoundstageOptionalText(brief.language) || "English";
    return [
        { step: 1, label: "Subject / Brand", value: cleanSoundstageOptionalText(brief.subject) || "Unset" },
        { step: 2, label: "Hero Offering", value: cleanSoundstageOptionalText(brief.offering) || "Signature Edition" },
        { step: 3, label: "Filming Territory", value: cleanSoundstageOptionalText(brief.territory) || "Tokyo · Aoyama" },
        { step: 4, label: "Weather & Atmosphere", value: `${brief.temperatureC}°C · ${cleanSoundstageOptionalText(brief.weatherCondition) || "Balanced Cinema Daylight"}` },
        { step: 5, label: "Studio Emblem", value: hasValidEmblem ? "Custom / Synthesized Studio Mark Locked" : "Clean Typographic End-Card Plate" },
        { step: 6, label: "60 / 30 / 10 Palette", value: `${brief.palette.primary_name} (${brief.palette.primary_hex}) · ${brief.palette.secondary_name} · ${brief.palette.neutral_name}` },
        { step: 7, label: "Cultural Moment", value: cleanSoundstageOptionalText(brief.moment) || "Threshold Ritual" },
        { step: 8, label: "Language & Cadence", value: `${displayLang} · ${cleanSoundstageOptionalText(brief.vocalCadence) || "Measured cinema cadence"}` },
        { step: 9, label: "Hero Packshot", value: hasValidPackshot ? "1:1 Hero Packshot Anchor Locked" : "Auto-Synthesize Hero Packshot on Cast Stage" }
    ];
}

function readSoundstageFileAsDataUrl(file, addToast, onLoaded) {
    if (!file) return;
    if (file.size > SOUNDSTAGE_MAX_UPLOAD_BYTES) {
        if (addToast) addToast("Image exceeds 10 MiB limit. Choose an image under 10 MiB.", "error");
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        const res = typeof reader.result === "string" ? reader.result : "";
        if (!SOUNDSTAGE_DATA_IMAGE_PATTERN.test(res)) {
            if (addToast) addToast("Unsupported image format. Upload PNG, JPEG, WebP, or SVG.", "error");
            return;
        }
        onLoaded(res);
    };
    reader.onerror = () => { if (addToast) addToast("Could not read selected image file.", "error"); };
    reader.readAsDataURL(file);
}

async function postSoundstageJson(url, payload) {
    const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const rawText = await resp.text();
    let data = {};
    if (rawText) {
        try {
            data = JSON.parse(rawText);
        } catch (_err) {
            data = {};
        }
    }
    if (!resp.ok) {
        let detailMsg = "";
        if (data && Array.isArray(data.detail)) {
            detailMsg = data.detail
                .map((d) => (d && typeof d === "object" ? (d.msg || JSON.stringify(d)) : String(d)))
                .join("; ");
        } else if (data && typeof data.detail === "string") {
            detailMsg = data.detail;
        } else if (data && data.detail && typeof data.detail === "object") {
            detailMsg = data.detail.message || data.detail.msg || JSON.stringify(data.detail);
        } else if (rawText && rawText.trim()) {
            detailMsg = rawText.trim().slice(0, 200);
        }
        throw new Error(detailMsg || `Soundstage request failed (${resp.status})`);
    }
    return data;
}

function isSoundstageFilmingStage(stage) {
    return stage === "filming_acts" || stage === "conforming" || stage === "critic_evaluated";
}

function resolveDefaultSoundstageStage(run) {
    if (!run) return "cast";
    if (run.stage === "completed" || Boolean(run.deliverables)) return "premiere";
    if (isSoundstageFilmingStage(run.stage)) return "filming";
    if (run.stage === "boards_ready") return "boards";
    return "cast";
}

function handleSoundstagePlateImgError(e) {
    if (e && e.currentTarget && e.currentTarget.src !== SOUNDSTAGE_FALLBACK_PLATE_DATA_URI) {
        e.currentTarget.src = SOUNDSTAGE_FALLBACK_PLATE_DATA_URI;
    }
}

function buildNormalizedClientNleSpecs(rawSpecs) {
    const byId = {};
    (Array.isArray(rawSpecs) ? rawSpecs : []).forEach((s) => {
        if (s && s.shot_id) byId[String(s.shot_id)] = s;
    });
    return SOUNDSTAGE_CANONICAL_SUBSHOTS.map((def) => {
        const cur = byId[def.shot_id] || {};
        return {
            shot_id: def.shot_id,
            act_index: def.act_index,
            default_start_sec: typeof cur.default_start_sec === "number" ? cur.default_start_sec : def.default_start_sec,
            default_duration_sec: typeof cur.default_duration_sec === "number" ? cur.default_duration_sec : def.default_duration_sec,
            trim_in_sec: typeof cur.trim_in_sec === "number" ? cur.trim_in_sec : 0.0,
            trim_out_sec: typeof cur.trim_out_sec === "number" ? cur.trim_out_sec : 0.0,
            bypassed: Boolean(cur.bypassed)
        };
    });
}

function computeSubshotEffectiveWindow(spec) {
    const minDur = 0.5;
    const actDur = 10.0;
    const maxStart = actDur - minDur;
    const defStart = typeof spec.default_start_sec === "number" ? spec.default_start_sec : 0.0;
    const defDur = typeof spec.default_duration_sec === "number" ? spec.default_duration_sec : 3.3;
    const trimIn = typeof spec.trim_in_sec === "number" ? spec.trim_in_sec : 0.0;
    const trimOut = typeof spec.trim_out_sec === "number" ? spec.trim_out_sec : 0.0;
    const start = Math.min(Math.max(0.0, defStart + trimIn), maxStart);
    const rawEnd = defStart + defDur - trimOut;
    const end = Math.min(Math.max(start + minDur, rawEnd), Math.max(start + minDur, actDur));
    return {
        startSec: Math.round(start * 1000) / 1000,
        endSec: Math.round(end * 1000) / 1000,
        durSec: Math.round((end - start) * 1000) / 1000
    };
}

function buildSoundstagePromotionPlan(activeRun) {
    const plan = (activeRun && activeRun.plan) || {};
    const identity = plan.identity || {};
    const territory = plan.territory || {};
    const palette = plan.palette || {};
    const refKit = (activeRun && activeRun.reference_kit) || {};
    const leadChar = plan.lead_character
        ? { ...plan.lead_character, reference_url: refKit.lead_cast_url || plan.lead_character.reference_url || "" }
        : null;
    const heroRole = plan.hero_offering_role
        ? { ...plan.hero_offering_role, reference_url: refKit.packshot_url || plan.hero_offering_role.reference_url || "" }
        : null;
    const characters = [leadChar, heroRole].filter(Boolean);
    const acts = Array.isArray(plan.acts) ? plan.acts : [];
    const intentSummary = (identity.display_subject || plan.subject || "Commercial") + " — " + (identity.display_offering || plan.offering || "Signature Edition") + " in " + (territory.place_name || "Metropolitan Studio");
    const scenes = acts.map((act, idx) => ({
        scene_number: act.act_number || (idx + 1),
        action: act.narrative_summary || "",
        dialogue: act.voiceover_line || "",
        screenplay_script: act.compiled_omni_prompt || act.narrative_summary || "",
        visual_focus: (act.title || ("Act " + (idx + 1))) + " (" + (act.time_window || "") + ")",
        audio_soundscape: ((act.audio_score || "") + " " + (act.sound_effects || "")).trim()
    }));
    const fullScreenplay = acts.map((act) => "ACT " + act.act_number + " (" + act.time_window + ") — " + act.title + "\n" + act.narrative_summary + "\nVO: " + (act.voiceover_line || "(Instrumental)")).join("\n\n");
    return {
        intent: intentSummary,
        characters,
        vocal_delivery: (leadChar && leadChar.voice_style) || "",
        style_tone: palette.production_design_directive || territory.lighting_directive || "Commercial Cinema 60/30/10",
        screenplay_script: fullScreenplay || plan.voiceover_full_script || intentSummary,
        audio_beat: (acts[0] && acts[0].audio_score) || "",
        scenes
    };
}
