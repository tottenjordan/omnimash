// Mode 5: Commercial Soundstage — 10-Step Editorial Intake & Express Canvas (Modular JSX Partial)

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
                            <g key={pin.place_name} data-territory-pin={pin.place_name} aria-pressed={isSelected} onClick={() => onSelectTerritory(lookupSpec(pin.place_name) || pin)} className="cursor-pointer">
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
                    return (<button key={pin.place_name} type="button" aria-pressed={isSelected} onClick={() => onSelectTerritory(lookupSpec(pin.place_name) || pin)} className={`px-3 py-1.5 rounded-lg text-xs border transition ${cls}`}>{pin.place_name}</button>);
                })}
            </div>
            {mergedSuggestions.length !== 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {mergedSuggestions.map((spec) => {
                        const isSelected = String(territory || "").toLowerCase() === String(spec.place_name || "").toLowerCase();
                        const cls = isSelected ? "border-rose-500/70 bg-rose-950/20" : "border-stone-800 bg-stone-950/60 hover:border-stone-600";
                        return (
                            <button key={spec.place_name} type="button" aria-pressed={isSelected} onClick={() => onSelectTerritory(spec)} className={`text-left rounded-xl p-3.5 border transition space-y-1 ${cls}`}>
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

function SoundstageEmblemPlate({ palette, emblemUrl, setEmblemUrl, emblemCandidates, isSynthesizing, isBusy, onSynthesizeEmblem, addToast, getDisplayableRefUrl }) {
    const [plateMode, setPlateMode] = useState("auto");
    const markLum = computeWcagRelativeLuminance(palette && palette.primary_hex) * 0.65 + computeWcagRelativeLuminance(palette && palette.neutral_hex) * 0.35;
    const contrastOnDark = computeWcagContrastRatio(markLum, computeWcagRelativeLuminance("#090A0F"));
    const contrastOnLight = computeWcagContrastRatio(markLum, computeWcagRelativeLuminance("#F5F2EB"));
    const autoPrefersLight = contrastOnLight > contrastOnDark;
    const useLightPlate = plateMode === "light" || (plateMode === "auto" && autoPrefersLight);
    const activeRatio = (useLightPlate ? contrastOnLight : contrastOnDark).toFixed(1);
    const cleanEmblem = cleanSoundstageOptionalText(emblemUrl);
    const displayUrl = getSafeSoundstageMediaUrl(emblemUrl, getDisplayableRefUrl);
    const hasInvalidScheme = Boolean(cleanEmblem && !displayUrl);
    const candidates = Array.isArray(emblemCandidates) ? emblemCandidates : [];

    return (
        <div id="soundstage-emblem-plate" className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-1.5 bg-stone-950 border border-stone-800 rounded-lg p-1" role="group" aria-label="Emblem backing plate contrast mode">
                    {[{ id: "auto", label: "Auto" }, { id: "dark", label: "Dark Plate" }, { id: "light", label: "Light Plate" }].map((opt) => (
                        <button key={opt.id} type="button" aria-pressed={plateMode === opt.id} onClick={() => setPlateMode(opt.id)} className={`px-2.5 py-1 rounded text-xs font-medium transition ${plateMode === opt.id ? "bg-rose-600 text-white" : "text-stone-300 hover:text-white"}`}>{opt.label}</button>
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
                    <input id="soundstage-input-emblem-url" type="text" value={emblemUrl} onChange={(e) => setEmblemUrl(e.target.value)} placeholder="gs://... or https://..." className={`w-full rounded-xl bg-stone-950/90 border px-3 py-2 text-xs text-stone-100 ${hasInvalidScheme ? "border-rose-500" : "border-stone-700/80"}`} />
                </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
                <button type="button" id="soundstage-btn-synthesize-emblem" disabled={isBusy} onClick={onSynthesizeEmblem} className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50">
                    {isSynthesizing ? "Synthesizing Studio Marks..." : "Synthesize Studio Mark"}
                </button>
                {cleanEmblem && (<button type="button" onClick={() => setEmblemUrl("")} className="text-xs text-stone-400 hover:text-stone-200 underline">Clear Emblem</button>)}
            </div>
            {candidates.length !== 0 && (
                <div className="grid grid-cols-3 gap-2.5">
                    {candidates.map((candUrl, idx) => {
                        const safeCand = getSafeSoundstageMediaUrl(candUrl, getDisplayableRefUrl);
                        if (!safeCand) return null;
                        const isSelected = candUrl === emblemUrl;
                        return (
                            <button key={`${candUrl}_${idx}`} type="button" aria-pressed={isSelected} onClick={() => setEmblemUrl(candUrl)} className={`p-2 rounded-xl border transition ${isSelected ? "border-rose-500 bg-rose-950/30" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                                <img src={safeCand} alt={`Emblem candidate ${idx + 1}`} className="h-16 w-full object-contain rounded" />
                            </button>
                        );
                    })}
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
                {SOUNDSTAGE_PALETTE_PRESETS.map((p) => {
                    const isPresetActive = palette.primary_hex === p.primary_hex && palette.secondary_hex === p.secondary_hex && palette.neutral_hex === p.neutral_hex;
                    return (
                        <button key={p.label} type="button" aria-pressed={isPresetActive} onClick={() => applyPatch({ primary_hex: p.primary_hex, primary_name: p.primary_name, secondary_hex: p.secondary_hex, secondary_name: p.secondary_name, neutral_hex: p.neutral_hex, neutral_name: p.neutral_name })} className="px-3 py-1.5 rounded-lg text-xs bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700/80 flex items-center gap-2 transition">
                            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.primary_hex }} />
                            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.secondary_hex }} />
                            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.neutral_hex }} />
                            <span>{p.label}</span>
                        </button>
                    );
                })}
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
    const { brief, setField, summaryRows, setCurrentStep, launchFilm, isLaunchingFilm, isBusy } = ctrl;
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
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" role="group" aria-label="Resolution Tier">
                        {[{ id: "360p", label: "360p Draft" }, { id: "720p", label: "720p Standard" }, { id: "4k", label: "4K Master" }].map((tier) => (
                            <button key={tier.id} type="button" aria-pressed={brief.resolution === tier.id} onClick={() => setField("resolution", tier.id, false)} className={`py-2 px-2.5 rounded-xl text-xs font-mono border transition ${brief.resolution === tier.id ? "bg-rose-600/25 text-rose-100 border-rose-500 font-bold" : "bg-stone-900 text-stone-300 border-stone-800 hover:border-stone-600"}`}>{tier.label}</button>
                        ))}
                    </div>
                </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-stone-800/80">
                <div className="flex items-center gap-3">
                    <button type="button" id="soundstage-toggle-manual-board-gate" role="switch" aria-label="Manual Storyboard Approval Gate before Omni Flash filming" aria-checked={brief.manualBoardGate} onClick={() => setField("manualBoardGate", !brief.manualBoardGate, false)} className="sstage-switch">
                        <span className="sstage-switch-thumb" />
                    </button>
                    <span className="text-xs text-stone-200">Manual Storyboard Approval Gate before Omni Flash filming</span>
                </div>
                <button type="button" id="soundstage-btn-make-film" disabled={isBusy} onClick={() => launchFilm(false)} className="px-6 py-3 rounded-xl text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg transition disabled:opacity-50">
                    {isLaunchingFilm ? "Compiling Plan & Locking Cast..." : "Make the film →"}
                </button>
            </div>
        </div>
    );
}

function SoundstageStepsOneToFour({ ctrl }) {
    const { currentStep, brief, setField, setSubject, selectTerritory, selectInspirationChip, discovery, isDiscovering, isBusy, handleDiscover } = ctrl;
    const physics = (discovery && discovery.physics) || null;
    const offerings = (discovery && Array.isArray(discovery.suggested_offerings)) ? discovery.suggested_offerings : [];

    if (currentStep === 1) {
        return (
            <div className="space-y-4">
                <div>
                    <label htmlFor="soundstage-input-subject" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Subject, Brand House, or Parody Concept</label>
                    <input id="soundstage-input-subject" type="text" value={brief.subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g., Atelier Kuroda Motors, Casa Solari, or Trapwarts Alchemical Guild" className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-4 py-3 text-base text-stone-100 focus:border-rose-500" />
                </div>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Campaign inspiration presets">
                    {SOUNDSTAGE_INSPIRATION_CHIPS.map((chip) => (
                        <button key={chip.label} type="button" aria-pressed={brief.subject === chip.subject} onClick={() => selectInspirationChip(chip)} className="px-3 py-1.5 rounded-lg text-xs bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-800 transition">✦ {chip.label}</button>
                    ))}
                </div>
                <div>
                    <label htmlFor="soundstage-input-dna" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Optional Creative DNA / Aesthetic Hint</label>
                    <input id="soundstage-input-dna" type="text" value={brief.customDna} onChange={(e) => setField("customDna", e.target.value, false)} placeholder="e.g., Anamorphic nocturnal rain, tactile brushed titanium, calm minimalist pacing" className="w-full rounded-xl bg-stone-950/90 border border-stone-800 px-3.5 py-2.5 text-sm text-stone-200" />
                </div>
                <button type="button" id="soundstage-btn-discover" disabled={isBusy} onClick={() => handleDiscover(true)} className="px-5 py-2.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50">
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
                        {offerings.map((item) => {
                            const isSelected = brief.offering === item.name;
                            return (
                                <button key={item.name} type="button" aria-pressed={isSelected} onClick={() => setField("offering", item.name, true)} className={`text-left rounded-xl p-3.5 border transition space-y-1 ${isSelected ? "border-rose-500 bg-rose-950/25" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                                    <span className="text-xs font-mono text-rose-300 block">{item.category || "Hero Edition"}</span>
                                    <span className="text-sm font-bold text-stone-100 block">{item.name}</span>
                                    <span className="text-xs text-stone-300 block">{item.description || item.rationale || ""}</span>
                                </button>
                            );
                        })}
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
                    <button key={cond} type="button" aria-pressed={brief.weatherCondition === cond} onClick={() => setField("weatherCondition", cond, true)} className={`px-3 py-1.5 rounded-lg text-xs border transition ${brief.weatherCondition === cond ? "border-rose-500 bg-rose-950/30 text-rose-100" : "border-stone-800 bg-stone-900 text-stone-300"}`}>{cond}</button>
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
    const { currentStep, brief, setField, discovery, emblemCandidates, packshotCandidates, isSynthesizingEmblem, isSynthesizingPackshot, isBusy, handleSynthesizeAsset } = ctrl;
    if (currentStep === 5) {
        return (<SoundstageEmblemPlate palette={brief.palette} emblemUrl={brief.emblemUrl} setEmblemUrl={(val) => setField("emblemUrl", val, false)} emblemCandidates={emblemCandidates} isSynthesizing={isSynthesizingEmblem} isBusy={isBusy} onSynthesizeEmblem={() => handleSynthesizeAsset("emblem")} addToast={addToast} getDisplayableRefUrl={getDisplayableRefUrl} />);
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
                        const isSelected = brief.moment === title;
                        return (
                            <button key={title} type="button" aria-pressed={isSelected} onClick={() => setField("moment", title, true)} className={`text-left rounded-xl p-3.5 border transition space-y-1 ${isSelected ? "border-rose-500 bg-rose-950/25" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
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
                    {languages.map((lang) => {
                        const isSelected = brief.language === lang.label;
                        return (
                            <button key={lang.code || lang.label} type="button" aria-pressed={isSelected} onClick={() => { setField("language", lang.label, true); if (lang.vocal_cadence) setField("vocalCadence", lang.vocal_cadence, true); }} className={`text-left rounded-xl p-3 border transition space-y-1 ${isSelected ? "border-rose-500 bg-rose-950/25" : "border-stone-800 bg-stone-950/60 hover:border-stone-600"}`}>
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold text-stone-100">{lang.label}</span>
                                    <span className="text-xs font-mono uppercase text-rose-300">{lang.code}</span>
                                </div>
                                <p className="text-xs text-stone-300">{lang.vocal_cadence}</p>
                            </button>
                        );
                    })}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                        <label htmlFor="soundstage-input-language" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Spoken Language</label>
                        <input id="soundstage-input-language" type="text" value={brief.language} onChange={(e) => setField("language", e.target.value, true)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2 text-sm text-stone-100" />
                    </div>
                    <div>
                        <label htmlFor="soundstage-input-cadence" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1">Vocal Cadence &amp; Delivery</label>
                        <input id="soundstage-input-cadence" type="text" value={brief.vocalCadence} onChange={(e) => setField("vocalCadence", e.target.value, true)} className="w-full rounded-xl bg-stone-950/90 border border-stone-700/80 px-3.5 py-2 text-sm text-stone-100" />
                    </div>
                </div>
            </div>
        );
    }
    if (currentStep === 9) {
        const cleanPackshot = cleanSoundstageOptionalText(brief.packshotUrl);
        const displayPackshot = getSafeSoundstageMediaUrl(brief.packshotUrl, getDisplayableRefUrl);
        const hasInvalidPackshot = Boolean(cleanPackshot && !displayPackshot);
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
                        <input id="soundstage-input-packshot-url" type="text" value={brief.packshotUrl} onChange={(e) => setField("packshotUrl", e.target.value, false)} placeholder="gs://... or https://..." className={`w-full rounded-xl bg-stone-950/90 border px-3 py-2 text-xs text-stone-100 ${hasInvalidPackshot ? "border-rose-500" : "border-stone-700/80"}`} />
                    </div>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <button type="button" id="soundstage-btn-synthesize-packshot" disabled={isBusy} onClick={() => handleSynthesizeAsset("packshot")} className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50">
                        {isSynthesizingPackshot ? "Synthesizing Studio Packshots..." : "Synthesize Hero Packshot"}
                    </button>
                    {cleanPackshot && (<button type="button" onClick={() => setField("packshotUrl", "", false)} className="text-xs text-stone-400 hover:text-stone-200 underline">Clear Packshot</button>)}
                </div>
                {packCandidates.length !== 0 && (
                    <div className="grid grid-cols-3 gap-2.5">
                        {packCandidates.map((candUrl, idx) => {
                            const safeCand = getSafeSoundstageMediaUrl(candUrl, getDisplayableRefUrl);
                            if (!safeCand) return null;
                            const isSelected = candUrl === brief.packshotUrl;
                            return (
                                <button key={`${candUrl}_${idx}`} type="button" aria-pressed={isSelected} onClick={() => setField("packshotUrl", candUrl, false)} className={`p-2 rounded-xl border transition ${isSelected ? "border-rose-500 bg-rose-950/30" : "border-stone-800 bg-stone-950/60"}`}>
                                    <img src={safeCand} alt={`Packshot candidate ${idx + 1}`} className="h-20 w-full object-cover rounded" />
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        );
    }
    return (<SoundstageReadySignoff ctrl={ctrl} />);
}

function SoundstageGuidedIntake({ ctrl, fullscreenFocus, setFullscreenFocus, addToast, getDisplayableRefUrl }) {
    const { guidedBriefMode, setGuidedBriefMode, activeRun, setViewMode, currentStep, setCurrentStep, handleStepContinue, brief, setField, setSubject, selectInspirationChip, launchFilm, isLaunchingFilm, isDiscovering, isBusy } = ctrl;
    const stepMeta = SOUNDSTAGE_STEPS[currentStep - 1] || SOUNDSTAGE_STEPS[0];
    const isEarlyStep = currentStep <= 4;

    return (
        <section aria-label="Mode 5 Commercial Soundstage Brief" className="sstage-canvas rounded-2xl p-4 sm:p-8 border border-stone-800/80 shadow-2xl space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-800/80 pb-4">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold block">Mode 5 · Commercial Soundstage</span>
                    <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-100">30s Master + 15s Cutdown + 6s Bumper Campaign Director</h2>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex items-center gap-2 bg-stone-950/90 border border-stone-800 rounded-xl px-3 py-1.5">
                        <span className="text-xs font-medium text-stone-200">Guide the brief</span>
                        <button type="button" id="soundstage-toggle-guided" role="switch" aria-label="Guide the brief" aria-checked={guidedBriefMode} onClick={() => setGuidedBriefMode(!guidedBriefMode)} className="sstage-switch">
                            <span className="sstage-switch-thumb" />
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
                <div id="soundstage-express-canvas" className="sstage-card rounded-2xl p-4 sm:p-6 space-y-5 max-w-3xl mx-auto">
                    <div className="space-y-1">
                        <h3 className="text-lg font-bold text-stone-100">Express Soundstage Canvas</h3>
                        <p className="text-xs text-stone-300">Enter a commercial brand or parody concept. Soundstage automatically deduces offering physics, 60/30/10 palette, and lead cast anchors.</p>
                    </div>
                    <div>
                        <label htmlFor="soundstage-express-subject" className="block text-xs font-mono uppercase tracking-wider text-stone-300 mb-1.5">Subject, Brand, or Parody Concept</label>
                        <input id="soundstage-express-subject" type="text" value={brief.subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g., Atelier Kuroda Motors or Trapwarts Alchemical Guild" className="w-full rounded-xl bg-stone-950 border border-stone-700 px-4 py-3 text-base text-stone-100 focus:border-rose-500" />
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {SOUNDSTAGE_INSPIRATION_CHIPS.map((chip) => (
                            <button key={chip.label} type="button" aria-pressed={brief.subject === chip.subject} onClick={() => selectInspirationChip(chip)} className="px-3 py-1.5 rounded-lg text-xs bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-800 transition">✦ {chip.label}</button>
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
                                    <button key={tier} type="button" aria-pressed={brief.resolution === tier} onClick={() => setField("resolution", tier, false)} className={`px-2.5 py-1 rounded-lg text-xs font-mono border ${brief.resolution === tier ? "bg-rose-600/25 text-rose-100 border-rose-500 font-bold" : "bg-stone-900 text-stone-300 border-stone-800"}`}>{tier}</button>
                                ))}
                            </div>
                            <button type="button" role="switch" aria-checked={brief.manualBoardGate} onClick={() => setField("manualBoardGate", !brief.manualBoardGate, false)} className="text-xs text-stone-300 hover:text-stone-100 px-2.5 py-1 rounded-lg bg-stone-900 border border-stone-800">
                                Manual Board Gate: {brief.manualBoardGate ? "On" : "Off"}
                            </button>
                        </div>
                        <button type="button" id="soundstage-btn-make-film-express" disabled={isBusy} onClick={() => launchFilm(true)} className="px-6 py-3 rounded-xl text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg transition disabled:opacity-50">
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
                    <div className="sstage-card rounded-2xl p-4 sm:p-6 space-y-5">
                        <div className="border-b border-stone-800/80 pb-3.5">
                            <h3 className="text-lg font-bold text-stone-100">{stepMeta.title}</h3>
                            <p className="text-xs text-stone-300 mt-0.5">{stepMeta.subtitle}</p>
                        </div>
                        {isEarlyStep ? (<SoundstageStepsOneToFour ctrl={ctrl} />) : (<SoundstageStepsFiveToTen ctrl={ctrl} addToast={addToast} getDisplayableRefUrl={getDisplayableRefUrl} />)}
                        <div className="flex items-center justify-between pt-4 border-t border-stone-800/80">
                            <button type="button" disabled={currentStep === 1 || isBusy} onClick={() => setCurrentStep(Math.max(1, currentStep - 1))} className="px-4 py-2 rounded-xl text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition disabled:opacity-40">← Previous</button>
                            {currentStep !== 10 && (<button type="button" disabled={isBusy} onClick={handleStepContinue} className="px-4 py-2 rounded-xl text-xs font-semibold bg-stone-100 hover:bg-white text-stone-950 transition disabled:opacity-50">{currentStep === 1 && isDiscovering ? "Discovering..." : "Continue →"}</button>)}
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
    const [draftAssetRun, setDraftAssetRun] = useState(null);
    const [discovery, setDiscovery] = useState(null);
    const [discoveredSubject, setDiscoveredSubject] = useState("");
    const [editedFields, setEditedFields] = useState({});
    const editedFieldsRef = useRef({});
    const busyRef = useRef(false);
    const reqSeqRef = useRef(0);
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
        packshotUrl: "", tagline: SOUNDSTAGE_NEUTRAL_DEFAULT_TAGLINE, resolution: "720p", manualBoardGate: false
    }));

    const isBusy = isDiscovering || isSynthesizingEmblem || isSynthesizingPackshot || isLaunchingFilm;
    const markEdited = (key) => {
        const nextEdits = { ...editedFieldsRef.current, [key]: true };
        editedFieldsRef.current = nextEdits; setEditedFields(nextEdits);
    };
    const setField = (key, value, trackEdit) => {
        if (trackEdit) markEdited(key);
        setBrief((prev) => ({ ...prev, [key]: value }));
    };
    const setSubject = (val) => {
        setBrief((prev) => ({
            ...prev, subject: val,
            offering: editedFieldsRef.current.offering ? prev.offering : "Signature Edition",
            tagline: editedFieldsRef.current.tagline ? prev.tagline : SOUNDSTAGE_NEUTRAL_DEFAULT_TAGLINE
        }));
    };
    const selectTerritory = (spec) => {
        markEdited("territory");
        setBrief((prev) => ({
            ...prev, territory: spec.place_name,
            temperatureC: typeof spec.temperature_c === "number" ? spec.temperature_c : prev.temperatureC,
            weatherCondition: spec.condition || prev.weatherCondition,
            lightingDirective: spec.lighting_directive || prev.lightingDirective,
            culturalPulse: spec.cultural_pulse || prev.culturalPulse
        }));
    };
    const selectInspirationChip = (chip) => {
        reqSeqRef.current += 1;
        editedFieldsRef.current = {}; setEditedFields({});
        setDraftAssetRun(null); setDiscovery(null); setDiscoveredSubject("");
        setBrief((prev) => ({ ...prev, subject: chip.subject, customDna: chip.dna, offering: "Signature Edition", tagline: SOUNDSTAGE_NEUTRAL_DEFAULT_TAGLINE }));
    };
    const safeSessionName = sanitizeSoundstageIdentifier(sessionName, "soundstage_session");
    const safeProjectName = sanitizeSoundstageIdentifier(activeProject, "default_project");

    const validateBriefMediaUrls = (b) => {
        const cleanEmb = cleanSoundstageOptionalText(b.emblemUrl);
        if (cleanEmb && !isAllowedSoundstageMediaUri(cleanEmb)) {
            const msg = "Invalid Studio Emblem URI. Use https://, gs://, /static/, or a PNG/JPEG/WebP/SVG data:image URI.";
            setErrorBanner(msg); if (addToast) addToast(msg, "error"); return false;
        }
        const cleanPack = cleanSoundstageOptionalText(b.packshotUrl);
        if (cleanPack && !isAllowedSoundstageMediaUri(cleanPack)) {
            const msg = "Invalid Hero Packshot URI. Use https://, gs://, /static/, or a PNG/JPEG/WebP/SVG data:image URI.";
            setErrorBanner(msg); if (addToast) addToast(msg, "error"); return false;
        }
        return true;
    };

    const applyDiscoveryDefaults = (disc) => {
        const liveEdits = editedFieldsRef.current;
        setDiscovery(disc);
        setBrief((prev) => mergeSoundstageDiscoveryBrief(prev, disc, liveEdits));
    };

    const handleDiscover = async (advanceStep) => {
        if (busyRef.current) return null;
        const cleanSubj = cleanSoundstageOptionalText(brief.subject);
        if (!cleanSubj) { setErrorBanner("Enter a Subject, Brand House, or Parody Concept to discover the brief."); return null; }
        busyRef.current = true; const mySeq = ++reqSeqRef.current;
        setErrorBanner(""); setIsDiscovering(true);
        try {
            const liveEdits = editedFieldsRef.current;
            const disc = await postSoundstageJson("/api/soundstage/discover", { subject: cleanSubj, offering: liveEdits.offering ? cleanSoundstageOptionalText(brief.offering) : null, territory: liveEdits.territory ? cleanSoundstageOptionalText(brief.territory) : null, custom_dna: cleanSoundstageOptionalText(brief.customDna) });
            if (reqSeqRef.current !== mySeq) return null;
            applyDiscoveryDefaults(disc); setDiscoveredSubject(cleanSubj);
            if (advanceStep) setCurrentStep(2);
            return disc;
        } catch (err) { if (reqSeqRef.current === mySeq) setErrorBanner(err.message || "Discovery failed."); return null; }
        finally { busyRef.current = false; setIsDiscovering(false); }
    };

    const handleStepContinue = async () => {
        if (currentStep === 1) {
            const cleanSubj = cleanSoundstageOptionalText(brief.subject);
            if (!cleanSubj) { setErrorBanner("Enter a Subject, Brand House, or Parody Concept to continue."); return; }
            if (discoveredSubject !== cleanSubj) { await handleDiscover(true); return; }
        }
        setCurrentStep(Math.min(10, currentStep + 1));
    };

    const handleSynthesizeAsset = async (assetAction) => {
        if (busyRef.current || !validateBriefMediaUrls(brief)) return;
        const isEmblem = assetAction === "emblem";
        busyRef.current = true; const mySeq = ++reqSeqRef.current;
        if (isEmblem) setIsSynthesizingEmblem(true); else setIsSynthesizingPackshot(true);
        setErrorBanner("");
        try {
            const sig = computePlanSignature(brief, safeProjectName, safeSessionName);
            let targetRunId = (draftAssetRun && draftAssetRun.signature === sig) ? draftAssetRun.runId : null;
            if (!targetRunId) {
                const draftRun = await postSoundstageJson("/api/soundstage/plan", buildSoundstagePlanPayload(brief, safeSessionName, safeProjectName));
                targetRunId = draftRun.run_id; setDraftAssetRun({ runId: targetRunId, signature: sig });
            }
            const updatedRun = await postSoundstageJson("/api/soundstage/cast", { run_id: targetRunId, action: assetAction, candidate_count: 3 });
            if (reqSeqRef.current !== mySeq) return;
            const kit = updatedRun.reference_kit || {};
            if (isEmblem) { setEmblemCandidates(kit.emblem_candidates || []); if (kit.emblem_url) setField("emblemUrl", kit.emblem_url, false); }
            else { setPackshotCandidates(kit.packshot_candidates || []); if (kit.packshot_url) setField("packshotUrl", kit.packshot_url, false); }
        } catch (err) { if (reqSeqRef.current === mySeq) setErrorBanner(err.message || `Could not synthesize ${assetAction}.`); }
        finally { busyRef.current = false; if (isEmblem) setIsSynthesizingEmblem(false); else setIsSynthesizingPackshot(false); }
    };

    const launchFilm = async (isExpress) => {
        if (busyRef.current || !validateBriefMediaUrls(brief)) return;
        const cleanSubj = cleanSoundstageOptionalText(brief.subject);
        if (!cleanSubj) { setErrorBanner("Enter a Subject, Brand House, or Parody Concept before rolling cameras."); return; }
        busyRef.current = true; const mySeq = ++reqSeqRef.current;
        setErrorBanner(""); setIsLaunchingFilm(true);
        try {
            let planOverrides = {};
            if (isExpress) {
                const disc = await postSoundstageJson("/api/soundstage/discover", { subject: cleanSubj, offering: cleanSoundstageOptionalText(brief.customDna), territory: null, custom_dna: cleanSoundstageOptionalText(brief.customDna) });
                if (reqSeqRef.current !== mySeq) return;
                applyDiscoveryDefaults(disc); setDiscoveredSubject(cleanSubj);
                planOverrides = buildSoundstageExpressOverrides(disc, brief, editedFieldsRef.current);
            }
            const plannedRun = await postSoundstageJson("/api/soundstage/plan", buildSoundstagePlanPayload(brief, safeSessionName, safeProjectName, planOverrides));
            const castReadyRun = await postSoundstageJson("/api/soundstage/cast", { run_id: plannedRun.run_id, action: "generate", candidate_count: 2 });
            if (reqSeqRef.current !== mySeq) return;
            setDraftAssetRun(null); setActiveRun(castReadyRun); setViewMode("production");
            if (addToast) addToast("Commercial Soundstage plan & lead cast locked.", "success");
        } catch (err) { if (reqSeqRef.current === mySeq) setErrorBanner(err.message || "Failed to launch Commercial Soundstage run."); }
        finally { busyRef.current = false; setIsLaunchingFilm(false); }
    };

    const summaryRows = buildSoundstageSummaryRows(brief);

    return {
        viewMode, setViewMode, guidedBriefMode, setGuidedBriefMode, currentStep, setCurrentStep, handleStepContinue,
        activeRun, setActiveRun, discovery, errorBanner, setErrorBanner, emblemCandidates, packshotCandidates,
        isDiscovering, isSynthesizingEmblem, isSynthesizingPackshot, isLaunchingFilm, isBusy,
        brief, setField, setSubject, selectTerritory, selectInspirationChip, handleDiscover, handleSynthesizeAsset, launchFilm, summaryRows
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
                    sessionName={sessionName}
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
