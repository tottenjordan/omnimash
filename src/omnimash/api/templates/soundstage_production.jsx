// Mode 5: Commercial Soundstage — 7-Stage Editorial Production Room (Modular JSX Partial)

function SoundstageBriefStageView({ plan }) {
    const brief = (plan && plan.brief) || {};
    const physics = (plan && plan.physics) || {};
    const laws = physics.act_causality_laws || {};
    const briefCards = [
        { label: "Campaign Objective", value: brief.objective || "Establish calm architectural desirability across 3 continuous acts." },
        { label: "Target Audience", value: brief.audience || "Design-literate cultural tastemakers and studio directors." },
        { label: "Key Cultural Tension", value: brief.key_tension || "Noise and haste versus tactile material stillness." },
        { label: "Core Proposition", value: brief.proposition || "Precision craft anchored in authentic physical ergonomics." }
    ];

    return (
        <div id="soundstage-view-brief" className="space-y-5">
            <div className="sstage-card rounded-xl p-5 sm:p-6 space-y-4">
                <div className="space-y-1 border-b border-stone-800/80 pb-4">
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Stage 1 · Executive Creative Brief</span>
                    <h3 className="text-lg sm:text-xl font-bold text-stone-100">{brief.title || "30-Second Commercial Soundstage Treatment"}</h3>
                    <p className="text-xs sm:text-sm text-stone-300 leading-relaxed">{brief.sonic_and_visual_direction || "Anamorphic 35mm continuous-shot choreography with ducked instrumental score."}</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                    {briefCards.map((item) => (
                        <div key={item.label} className="sstage-elevated rounded-xl p-4 space-y-1.5">
                            <span className="text-xs font-mono uppercase tracking-wider text-stone-400">{item.label}</span>
                            <p className="text-xs sm:text-sm text-stone-100 leading-relaxed">{item.value}</p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="sstage-card rounded-xl p-5 sm:p-6 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">First-Principles Offering Physics &amp; Causality Gates</span>
                        <h3 className="text-base font-bold text-stone-100 mt-0.5">Deduced Ergonomics &amp; 3-Act Physical Laws</h3>
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-xs font-mono">
                        <span className="px-2.5 py-1 rounded bg-rose-950/80 text-rose-200 border border-rose-800/70">{physics.archetype || "HANDHELD_CPG_OR_OBJECT"}</span>
                        <span className="px-2.5 py-1 rounded bg-stone-900 text-stone-200 border border-stone-700">{physics.ergonomic_role || "ACTIVE_USER_OR_CONSUMER"}</span>
                        <span className="px-2.5 py-1 rounded bg-stone-900 text-stone-300 border border-stone-800">{physics.physical_scale || "HANDHELD_10_TO_30CM"}</span>
                        <span className="px-2.5 py-1 rounded bg-stone-900 text-stone-300 border border-stone-800">{physics.thermal_state || "AMBIENT_SOLID"}</span>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                    {[1, 2, 3].map((actNum) => (
                        <div key={actNum} className="sstage-elevated rounded-xl p-4 space-y-1.5">
                            <span className="text-xs font-mono font-bold text-rose-300">Act {actNum} Causality Law</span>
                            <p className="text-xs text-stone-200 leading-relaxed">{laws[String(actNum)] || laws[actNum] || "Maintain strict physical continuity and clean spatial separation."}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function SoundstageWorldStageView({ plan }) {
    const territory = (plan && plan.territory) || {};
    const palette = (plan && plan.palette) || {
        primary_hex: "#1A222D",
        primary_name: "Obsidian Slate",
        secondary_hex: "#C4633B",
        secondary_name: "Sienna Saddle",
        neutral_hex: "#EAE6DF",
        neutral_name: "Chalk Travertine",
        production_design_directive: ""
    };
    const identity = (plan && plan.identity) || {};
    const swatches = [
        { pct: "60%", role: "Architectural & Set Surfaces", name: palette.primary_name, hex: palette.primary_hex },
        { pct: "30%", role: "Wardrobe & Practical Props", name: palette.secondary_name, hex: palette.secondary_hex },
        { pct: "10%", role: "Hero Plinth & End-Card Plate", name: palette.neutral_name, hex: palette.neutral_hex }
    ];

    return (
        <div id="soundstage-view-world" className="space-y-5">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="sstage-card rounded-xl p-5 space-y-3">
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Stage 2 · Filming Territory &amp; Atmosphere</span>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-lg font-bold text-stone-100">{territory.place_name || "Tokyo · Aoyama"}</h3>
                        <span className="text-xs font-mono px-2.5 py-1 rounded bg-stone-900 text-stone-200 border border-stone-700">
                            {typeof territory.temperature_c === "number" ? territory.temperature_c : 16}°C
                        </span>
                    </div>
                    <p className="text-xs font-mono text-rose-200">{territory.condition || "Crisp twilight atmosphere"}</p>
                    <div className="space-y-2 pt-2 border-t border-stone-800/80 text-xs text-stone-300">
                        <p><strong className="text-stone-100">Optical &amp; Lighting:</strong> {territory.lighting_directive || "35mm cinema prime lens"}</p>
                        <p><strong className="text-stone-100">Cultural Pulse:</strong> {territory.cultural_pulse || "Architectural evening poise"}</p>
                    </div>
                </div>

                <div className="sstage-card rounded-xl p-5 space-y-3.5">
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">60 / 30 / 10 Production Design Color Lock</span>
                    <div className="h-5 w-full rounded-lg overflow-hidden flex border border-stone-700">
                        <div style={{ width: "60%", backgroundColor: palette.primary_hex }} title={palette.primary_name} />
                        <div style={{ width: "30%", backgroundColor: palette.secondary_hex }} title={palette.secondary_name} />
                        <div style={{ width: "10%", backgroundColor: palette.neutral_hex }} title={palette.neutral_name} />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        {swatches.map((sw) => (
                            <div key={sw.pct} className="sstage-elevated rounded-lg p-3 space-y-1.5">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-mono font-bold text-stone-100">{sw.pct}</span>
                                    <span className="w-4 h-4 rounded border border-stone-600" style={{ backgroundColor: sw.hex }} />
                                </div>
                                <p className="text-xs font-semibold text-stone-100">{sw.name}</p>
                                <p className="text-xs font-mono text-stone-400">{sw.hex} · {sw.role}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="sstage-card rounded-xl p-5 space-y-4">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Dual-Layer Brand &amp; Cast Safety Architecture</span>
                    <h3 className="text-base font-bold text-stone-100 mt-0.5">Verbatim Brand Lockup vs. Trademark-Scrubbed Omni Prompt Descriptors</h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="sstage-elevated rounded-xl p-4 space-y-2">
                        <span className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">Layer A · Verbatim UI &amp; End-Card Lockup</span>
                        <p className="text-xs text-stone-200"><strong>Display Subject:</strong> {identity.display_subject || "Artisan House"}</p>
                        <p className="text-xs text-stone-200"><strong>Display Offering:</strong> {identity.display_offering || "Signature Edition"}</p>
                        <p className="text-xs text-stone-200"><strong>Display Tagline:</strong> {identity.display_tagline || "Precision crafted."}</p>
                    </div>
                    <div className="sstage-elevated rounded-xl p-4 space-y-2">
                        <span className="text-xs font-mono uppercase tracking-wider text-emerald-300 font-semibold">Layer B · Omni-Safe Prompt Descriptors</span>
                        <p className="text-xs text-stone-200"><strong>Safe Cast Handle (@Image3):</strong> <span className="font-mono text-rose-200">{identity.omni_safe_cast_handle || "Vanguard"}</span></p>
                        <p className="text-xs text-stone-200"><strong>Safe Offering (@Image4):</strong> {identity.omni_safe_offering_descriptor || "Sculpted hero object"}</p>
                        <p className="text-xs text-stone-200"><strong>Safe World Descriptor:</strong> {identity.omni_safe_world_descriptor || "Architectural studio sanctuary"}</p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function SoundstageStoryStageView({ plan }) {
    const acts = Array.isArray(plan && plan.acts) ? plan.acts : [];

    return (
        <div id="soundstage-view-story" className="space-y-5">
            <div className="sstage-card rounded-xl p-5 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Stage 3 · 30-Second Master Voiceover Arc ({(plan && plan.language) || "English"})</span>
                    <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-emerald-950/80 text-emerald-200 border border-emerald-700/60">3 Acts × 10s Continuous Shots</span>
                </div>
                <p className="text-sm sm:text-base font-medium text-stone-100 italic leading-relaxed">
                    &ldquo;{(plan && plan.voiceover_full_script) || "Measured commercial narration across three tactile acts."}&rdquo;
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {acts.map((act) => (
                    <div key={act.act_number} className="sstage-card rounded-xl p-5 flex flex-col justify-between space-y-4">
                        <div className="space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-xs font-mono font-bold text-rose-300">Act {act.act_number} · {act.time_window}</span>
                                <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-200 border border-emerald-700/60">Pre-Flight Passed</span>
                            </div>
                            <h3 className="text-base font-bold text-stone-100">{act.title}</h3>
                            <p className="text-xs text-stone-300 leading-relaxed">{act.narrative_summary}</p>
                            <div className="sstage-elevated rounded-lg p-3 space-y-1.5 text-xs">
                                <p className="text-stone-100"><strong>VO:</strong> {act.voiceover_line || "(Pure instrumental beat)"}</p>
                                <p className="text-stone-300"><strong>Score:</strong> {act.audio_score}</p>
                                <p className="text-stone-400"><strong>Foley:</strong> {act.sound_effects}</p>
                            </div>
                            <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono">
                                <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-200 border border-stone-700">{"<FIRST_FRAME>"} {act.first_frame_shot_id}</span>
                                <span className="text-stone-400">→</span>
                                <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-200 border border-stone-700">{"<LAST_FRAME>"} {act.last_frame_shot_id}</span>
                            </div>
                        </div>

                        <details className="bg-stone-950/90 rounded-lg border border-stone-800 p-2.5 text-xs">
                            <summary className="cursor-pointer font-mono text-stone-200 font-semibold">Inspect 4-Block Omni Meta-Prompt</summary>
                            <pre className="mt-2.5 text-xs font-mono text-stone-300 whitespace-pre-wrap max-h-56 overflow-y-auto custom-scrollbar">{act.compiled_omni_prompt}</pre>
                        </details>
                    </div>
                ))}
            </div>
        </div>
    );
}

function SoundstageCastGateView({
    activeRun,
    manualBoardGate,
    setManualBoardGate,
    isBusy,
    onCastAction,
    onSelectCandidate,
    onHydrateVaultChar,
    onApproveCast,
    vaultCharacters,
    getDisplayableRefUrl
}) {
    const plan = (activeRun && activeRun.plan) || {};
    const identity = plan.identity || {};
    const leadChar = plan.lead_character || {};
    const refKit = (activeRun && activeRun.reference_kit) || {};
    const [wardrobeNote, setWardrobeNote] = useState(leadChar.wardrobe || "");
    const [tweakNote, setTweakNote] = useState("");
    const runIdKey = (activeRun && activeRun.run_id) || "";

    useEffect(() => {
        setWardrobeNote((plan.lead_character && plan.lead_character.wardrobe) || "");
        setTweakNote("");
    }, [runIdKey, leadChar.wardrobe]);

    const leadUrl = getSafeSoundstageMediaUrl(refKit.lead_cast_url, getDisplayableRefUrl);
    const candidates = Array.isArray(refKit.lead_cast_candidates) ? refKit.lead_cast_candidates : [];
    const emblemUrl = getSafeSoundstageMediaUrl(refKit.emblem_url, getDisplayableRefUrl);
    const packshotUrl = getSafeSoundstageMediaUrl(refKit.packshot_url, getDisplayableRefUrl);
    const vaultList = Array.isArray(vaultCharacters) ? vaultCharacters : [];

    return (
        <div id="soundstage-cast-gate" className="space-y-5">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                <div className="lg:col-span-5 sstage-card rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Stage 4 · Smart Cast Gate (@Image3)</span>
                        <span className="text-xs font-mono px-2.5 py-0.5 rounded bg-stone-900 text-rose-200 border border-stone-700">Handle: {identity.omni_safe_cast_handle || "Vanguard"}</span>
                    </div>

                    {leadUrl ? (
                        <img src={leadUrl} alt="Lead commercial cast turnaround reference" onError={handleSoundstagePlateImgError} className="w-full h-56 object-cover rounded-xl border border-stone-800 bg-black" />
                    ) : (
                        <div className="w-full h-56 rounded-xl border border-stone-800 bg-stone-950 flex items-center justify-center text-xs text-stone-400">Synthesizing 2K turnaround reference...</div>
                    )}

                    {candidates.length !== 0 && (
                        <div className="grid grid-cols-3 gap-2">
                            {candidates.map((candUrl, idx) => {
                                const safeCand = getSafeSoundstageMediaUrl(candUrl, getDisplayableRefUrl);
                                const isChosen = candUrl === refKit.lead_cast_url;
                                const candCls = isChosen ? "rounded-lg overflow-hidden border-2 border-rose-500" : "rounded-lg overflow-hidden border border-stone-800 opacity-75 hover:opacity-100";
                                return (
                                    <button key={candUrl + "::" + idx} type="button" data-cast-candidate={idx + 1} aria-pressed={isChosen} disabled={isBusy} onClick={() => onSelectCandidate(candUrl)} className={candCls + " disabled:opacity-50"}>
                                        <img src={safeCand || SOUNDSTAGE_FALLBACK_PLATE_DATA_URI} alt={"Cast candidate " + (idx + 1)} onError={handleSoundstagePlateImgError} className="w-full h-16 object-cover bg-black" />
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    <div className="sstage-elevated rounded-lg p-3.5 space-y-1.5 text-xs">
                        <p className="text-stone-200"><strong>Wardrobe:</strong> {leadChar.wardrobe || "Tailored studio wardrobe"}</p>
                        <p className="text-stone-300"><strong>Vocal Cadence:</strong> {leadChar.voice_style || "Measured cinema baritone"}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3 pt-1">
                        <div className="sstage-elevated rounded-lg p-2.5 space-y-1.5">
                            <span className="text-xs font-mono text-stone-300 block">Studio Emblem</span>
                            {emblemUrl ? <img src={emblemUrl} alt="Studio emblem kit anchor" onError={handleSoundstagePlateImgError} className="w-full h-16 object-contain rounded bg-stone-950" /> : <span className="text-xs font-mono text-stone-400 block py-4 text-center">Typographic Plate</span>}
                        </div>
                        <div className="sstage-elevated rounded-lg p-2.5 space-y-1.5">
                            <span className="text-xs font-mono text-stone-300 block">Hero Packshot (@Image4)</span>
                            {packshotUrl ? <img src={packshotUrl} alt="Hero packshot kit anchor" onError={handleSoundstagePlateImgError} className="w-full h-16 object-cover rounded bg-stone-950" /> : <span className="text-xs font-mono text-stone-400 block py-4 text-center">Auto-Synthesize</span>}
                        </div>
                    </div>
                </div>

                <div className="lg:col-span-7 space-y-4">
                    <div className="sstage-card rounded-xl p-5 space-y-4">
                        <h3 className="text-base font-bold text-stone-100">Casting Adjustments &amp; Wardrobe Direction</h3>
                        <div className="flex flex-wrap gap-2">
                            <button type="button" id="soundstage-btn-recast" disabled={isBusy} onClick={() => onCastAction({ action: "recast", candidate_count: 2 })} className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-100 border border-stone-700 transition disabled:opacity-50">Recast (2 Takes)</button>
                            <button type="button" id="soundstage-btn-cast-older" disabled={isBusy} onClick={() => onCastAction({ action: "older", candidate_count: 1 })} className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-100 border border-stone-700 transition disabled:opacity-50">Older (+12 Yrs Poise)</button>
                            <button type="button" id="soundstage-btn-cast-younger" disabled={isBusy} onClick={() => onCastAction({ action: "younger", candidate_count: 1 })} className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-100 border border-stone-700 transition disabled:opacity-50">Younger (Contemporary)</button>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <label htmlFor="soundstage-input-cast-wardrobe" className="block text-xs font-mono text-stone-300">Wardrobe Directive</label>
                                <input id="soundstage-input-cast-wardrobe" type="text" value={wardrobeNote} onChange={(e) => setWardrobeNote(e.target.value)} className="w-full rounded-lg bg-stone-950 border border-stone-700 px-3 py-2 text-xs text-stone-100" />
                            </div>
                            <div className="space-y-1">
                                <label htmlFor="soundstage-input-cast-tweak" className="block text-xs font-mono text-stone-300">Facial / Styling Tweak</label>
                                <input id="soundstage-input-cast-tweak" type="text" value={tweakNote} onChange={(e) => setTweakNote(e.target.value)} placeholder="e.g., Silver rim-frame spectacles" className="w-full rounded-lg bg-stone-950 border border-stone-700 px-3 py-2 text-xs text-stone-100" />
                            </div>
                        </div>
                        <button type="button" id="soundstage-btn-cast-tweak" disabled={isBusy} onClick={() => onCastAction({ action: "tweak", wardrobe_note: cleanSoundstageOptionalText(wardrobeNote), tweak_note: cleanSoundstageOptionalText(tweakNote), candidate_count: 1 })} className="px-4 py-2 rounded-lg text-xs font-bold bg-stone-100 hover:bg-white text-stone-950 transition disabled:opacity-50">
                            Apply Wardrobe &amp; Look Tweak
                        </button>
                    </div>

                    <div id="soundstage-vault-cast-picker" className="sstage-card rounded-xl p-5 space-y-3">
                        <div className="flex items-center justify-between gap-2">
                            <h3 className="text-sm font-bold text-stone-100">Hydrate Lead from Character Vault</h3>
                            <span className="text-xs font-mono text-stone-400">Safe Dual-Layer Handle Mapping</span>
                        </div>
                        {vaultList.length === 0 ? (
                            <p className="text-xs text-stone-400">No saved vault characters detected in active project.</p>
                        ) : (
                            <div className="flex flex-wrap gap-2">
                                {vaultList.map((charObj) => {
                                    const charLabel = charObj.name || charObj.role_id || "Character";
                                    return (
                                        <button key={charLabel} type="button" data-vault-char={charLabel} disabled={isBusy} onClick={() => onHydrateVaultChar(charObj)} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-950 hover:bg-stone-800 text-stone-200 border border-stone-700 transition disabled:opacity-50">
                                            {charLabel}
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    <div className="sstage-card rounded-xl p-5 space-y-4 border-rose-900/50">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <span className="text-xs font-semibold text-stone-100 block">Pause at 3×3 Storyboard Gate before filming</span>
                                <span className="text-xs text-stone-400 block">When off, clean 9-plate DOMA checks auto-advance straight into 3-act filming.</span>
                            </div>
                            <button type="button" id="soundstage-cast-toggle-manual-boards" role="switch" aria-label="Pause at 3x3 Storyboard Gate before filming" aria-checked={manualBoardGate} onClick={() => setManualBoardGate(!manualBoardGate)} className="sstage-switch">
                                <span className="sstage-switch-thumb" />
                            </button>
                        </div>
                        <button type="button" id="soundstage-btn-approve-cast" disabled={isBusy} onClick={onApproveCast} className="w-full py-3 px-5 rounded-xl text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg transition disabled:opacity-50">
                            {isBusy ? "Synthesizing 3×3 Storyboard Plates..." : "Use this lead & Draw 3×3 Storyboard →"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function SoundstageBoardsGateView({
    activeRun,
    isBusy,
    redrawingShotId,
    onDrawAllBoards,
    onRedrawTile,
    onRollCameras,
    getDisplayableRefUrl
}) {
    const [tileNotes, setTileNotes] = useState({});
    const plan = (activeRun && activeRun.plan) || {};
    const tiles = Array.isArray(plan.boards) ? plan.boards : [];
    const boardsMap = (activeRun && activeRun.boards) || {};
    const checksMap = (activeRun && activeRun.board_checks) || {};
    const hasBoards = Object.keys(boardsMap).length !== 0;

    return (
        <div id="soundstage-boards-gate" className="space-y-5">
            <div className="sstage-card rounded-xl p-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Stage 5 · 3×3 Storyboard Continuity &amp; Isolation Gate</span>
                    <h3 className="text-base sm:text-lg font-bold text-stone-100 mt-0.5">9 Canonical Keyframe Plates (1.1 – 3.3) · Dual-Keyframe Act Anchors</h3>
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                    {!hasBoards && (
                        <button type="button" id="soundstage-btn-draw-boards" disabled={isBusy} onClick={onDrawAllBoards} className="px-4 py-2.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow transition disabled:opacity-50">
                            {isBusy ? "Drawing 9 Plates..." : "Draw 3×3 Storyboard Plates →"}
                        </button>
                    )}
                    <button type="button" id="soundstage-btn-redraw-all-boards" disabled={isBusy} onClick={onDrawAllBoards} className="px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition disabled:opacity-50">
                        Redraw All 9 Plates
                    </button>
                    <button type="button" id="soundstage-btn-roll-cameras" disabled={isBusy} onClick={onRollCameras} className="px-4 py-2.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow transition disabled:opacity-50">
                        Roll Cameras (Film 3 Acts) →
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {tiles.map((tile) => {
                    const shotUrl = getSafeSoundstageMediaUrl(boardsMap[tile.shot_id], getDisplayableRefUrl);
                    const check = checksMap[tile.shot_id];
                    const isoBadgeCls = tile.has_person
                        ? "px-2 py-0.5 rounded bg-stone-900 text-stone-200 border border-stone-700"
                        : "px-2 py-0.5 rounded bg-rose-950/80 text-rose-200 border border-rose-800/70";
                    const checkPassed = !check || check.passed !== false;
                    const checkCls = checkPassed
                        ? "px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-200 border border-emerald-700/60"
                        : "px-2 py-0.5 rounded bg-amber-950/80 text-amber-200 border border-amber-700/70";
                    const checkText = !check ? "Pending Plate" : (checkPassed ? "DOMA Passed" : ("Flagged: " + (check.flagged_reason || "Review continuity")));

                    return (
                        <div key={tile.shot_id} data-board-shot={tile.shot_id} className="sstage-card rounded-xl p-4 flex flex-col justify-between space-y-3">
                            <div className="space-y-2.5">
                                <div className="flex items-center justify-between gap-2 text-xs font-mono">
                                    <span className="font-bold text-stone-100">Shot {tile.shot_id} · {tile.timecode_range}</span>
                                    <span className="text-stone-400">{tile.framing}</span>
                                </div>
                                {shotUrl ? (
                                    <img src={shotUrl} alt={"Storyboard plate " + tile.shot_id} onError={handleSoundstagePlateImgError} className="w-full aspect-video object-cover rounded-lg border border-stone-800 bg-black" />
                                ) : (
                                    <div className="w-full aspect-video rounded-lg border border-stone-800 bg-stone-950 flex items-center justify-center text-xs font-mono text-stone-400">Plate {tile.shot_id} Awaiting Synthesis</div>
                                )}
                                <div className="flex flex-wrap gap-1.5 text-xs font-mono">
                                    <span className={isoBadgeCls}>{tile.has_person ? "Lead Cast (@Image3)" : "Human-Free Macro (@Image4 Only)"}</span>
                                    <span className={checkCls}>{checkText}</span>
                                </div>
                                <p className="text-xs text-stone-300 leading-relaxed">{tile.action}</p>
                            </div>

                            <div className="flex items-center gap-1.5 pt-2 border-t border-stone-800/80">
                                <input type="text" aria-label={"Director note for shot " + tile.shot_id} value={tileNotes[tile.shot_id] || ""} onChange={(e) => setTileNotes((prev) => ({ ...prev, [tile.shot_id]: e.target.value }))} placeholder="Surgical note..." className="flex-1 rounded-lg bg-stone-950 border border-stone-700 px-2.5 py-1.5 text-xs text-stone-100" />
                                <button type="button" data-redraw-shot={tile.shot_id} disabled={isBusy} onClick={() => onRedrawTile(tile.shot_id, tileNotes[tile.shot_id] || "")} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-100 border border-stone-700 transition disabled:opacity-50">
                                    {redrawingShotId === tile.shot_id ? "Drawing..." : "Redraw Frame"}
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function useSoundstageProductionController({ activeRun, setActiveRun, addToast }) {
    const [activeStageTab, setActiveStageTab] = useState(() => resolveDefaultSoundstageStage(activeRun));
    const [manualBoardGate, setManualBoardGate] = useState(() => Boolean(activeRun && activeRun.manual_board_gate));
    const [prodError, setProdError] = useState("");
    const [isBusy, setIsBusy] = useState(false);
    const [redrawingShotId, setRedrawingShotId] = useState("");
    const [isFilming, setIsFilming] = useState(false);
    const [liveProgressPct, setLiveProgressPct] = useState(() => (activeRun && typeof activeRun.progress_pct === "number" ? activeRun.progress_pct : 20));
    const [liveStageLabel, setLiveStageLabel] = useState(() => (activeRun && activeRun.stage) || "cast_ready");
    const [liveEvents, setLiveEvents] = useState(() => (activeRun && Array.isArray(activeRun.events) ? activeRun.events : []));

    const lastRunIdRef = useRef((activeRun && activeRun.run_id) || "");
    const eventSourceRef = useRef(null);
    const pollTimerRef = useRef(null);
    const mountedRef = useRef(true);

    const cleanupFilmingStreams = () => {
        if (eventSourceRef.current) { try { eventSourceRef.current.close(); } catch (_err) {} eventSourceRef.current = null; }
        if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
    };

    useEffect(() => {
        mountedRef.current = true;
        return () => { mountedRef.current = false; cleanupFilmingStreams(); };
    }, []);

    useEffect(() => {
        if (!activeRun || !activeRun.run_id) return;
        setLiveProgressPct(typeof activeRun.progress_pct === "number" ? activeRun.progress_pct : 20);
        setLiveStageLabel(activeRun.stage || "cast_ready");
        if (Array.isArray(activeRun.events)) setLiveEvents(activeRun.events);
        if (lastRunIdRef.current !== activeRun.run_id) {
            cleanupFilmingStreams(); setIsFilming(false);
            lastRunIdRef.current = activeRun.run_id;
            setActiveStageTab(resolveDefaultSoundstageStage(activeRun));
            setManualBoardGate(Boolean(activeRun.manual_board_gate));
            setProdError("");
        }
    }, [activeRun]);

    const startFilmingRun = async (runId, resolutionOverride) => {
        if (!runId || isFilming) return;
        cleanupFilmingStreams(); setProdError(""); setIsFilming(true); setActiveStageTab("filming");
        let finalized = false;

        const reconcileStatus = async () => {
            if (finalized || !mountedRef.current) return;
            try {
                const resp = await fetch("/api/soundstage/" + encodeURIComponent(runId) + "/status");
                if (!resp.ok || finalized || !mountedRef.current) return;
                const snap = await resp.json();
                if (finalized || !mountedRef.current) return;
                setLiveProgressPct(snap.progress_pct || 0);
                setLiveStageLabel(snap.stage || "filming_acts");
                if (Array.isArray(snap.events)) setLiveEvents(snap.events);
                if (snap.stage === "completed") {
                    finalized = true; cleanupFilmingStreams(); setIsFilming(false);
                    setActiveRun(snap); setActiveStageTab("premiere");
                    if (addToast) addToast("30s Master, 15s Cutdown, and 6s Bumper ready in Premiere!", "success");
                } else if (snap.stage === "failed") {
                    finalized = true; cleanupFilmingStreams(); setIsFilming(false);
                    setActiveRun(snap); setProdError(snap.error || "Soundstage filming failed.");
                }
            } catch (_err) {}
        };

        try {
            const queued = await postSoundstageJson("/api/soundstage/run", {
                run_id: runId,
                resolution: resolutionOverride || (activeRun && activeRun.resolution) || "720p",
                async_execution: true
            });
            if (!mountedRef.current) return;
            setActiveRun(queued); setLiveProgressPct(queued.progress_pct || 32); setLiveStageLabel(queued.stage || "filming_acts");
            if (typeof EventSource !== "undefined") {
                const es = new EventSource("/api/soundstage/" + encodeURIComponent(runId) + "/events");
                eventSourceRef.current = es;
                es.addEventListener("progress", (ev) => {
                    if (finalized || !mountedRef.current) return;
                    try {
                        const p = JSON.parse(ev.data || "{}");
                        if (typeof p.progress_pct === "number") setLiveProgressPct(p.progress_pct);
                        if (p.stage) setLiveStageLabel(p.stage);
                        setLiveEvents((prev) => (prev.some((item) => item.event_id === p.event_id) ? prev : [...prev, p]));
                    } catch (_e) {}
                });
                const onTerminal = () => { reconcileStatus(); };
                es.addEventListener("complete", onTerminal);
                es.addEventListener("idle", onTerminal);
                es.addEventListener("timeout", onTerminal);
                es.addEventListener("error", onTerminal);
            }
            pollTimerRef.current = setInterval(reconcileStatus, 250);
            await reconcileStatus();
        } catch (err) {
            finalized = true; cleanupFilmingStreams(); setIsFilming(false);
            setProdError(err.message || "Could not start Commercial Soundstage filming.");
        }
    };

    const handleCastAction = async (extraPayload) => {
        if (!activeRun || isBusy) return;
        setIsBusy(true); setProdError("");
        try { setActiveRun(await postSoundstageJson("/api/soundstage/cast", { run_id: activeRun.run_id, ...extraPayload })); }
        catch (err) { setProdError(err.message || "Cast update failed."); }
        finally { setIsBusy(false); }
    };

    const handleHydrateVaultChar = async (charObj) => {
        if (!activeRun || !charObj || isBusy) return;
        const slug = charObj.name || charObj.role_id || "Character";
        setIsBusy(true); setProdError("");
        try {
            await postSoundstageJson("/api/characters/save", {
                character: {
                    role_id: charObj.role_id || "Role A", name: slug, description: charObj.description || "",
                    reference_url: charObj.reference_url || null, aesthetic_tags: Array.isArray(charObj.aesthetic_tags) ? charObj.aesthetic_tags : [],
                    voice_style: charObj.voice_style || "", wardrobe: charObj.wardrobe || "",
                    image_role: charObj.image_role || "Character Reference", is_offscreen_narrator: Boolean(charObj.is_offscreen_narrator)
                },
                session_name: activeRun.session_name, project_name: activeRun.project_name, is_library: true
            });
            setActiveRun(await postSoundstageJson("/api/soundstage/cast", { run_id: activeRun.run_id, action: "vault", vault_character_slug: slug }));
            if (addToast) addToast("Hydrated " + slug + " into Lead Cast Gate.", "success");
        } catch (err) { setProdError(err.message || "Vault character hydration failed."); }
        finally { setIsBusy(false); }
    };

    const handleApproveCastAndDrawBoards = async () => {
        if (!activeRun || isBusy) return;
        setIsBusy(true); setProdError("");
        try {
            const boardsRun = await postSoundstageJson("/api/soundstage/boards", { run_id: activeRun.run_id, manual_board_gate: manualBoardGate });
            setActiveRun(boardsRun);
            const flagged = Array.isArray(boardsRun.flagged_shot_ids) ? boardsRun.flagged_shot_ids : [];
            if (boardsRun.auto_advance_filming && !boardsRun.manual_board_gate && flagged.length === 0) {
                setIsBusy(false);
                await startFilmingRun(boardsRun.run_id, boardsRun.resolution);
                return;
            }
            setActiveStageTab("boards");
        } catch (err) { setProdError(err.message || "Storyboard synthesis failed."); }
        finally { setIsBusy(false); }
    };

    const handleDrawOrRedrawBoards = async (shotId, directorNote) => {
        if (!activeRun || isBusy) return;
        setIsBusy(true); setRedrawingShotId(shotId || ""); setProdError("");
        try {
            const updated = await postSoundstageJson("/api/soundstage/boards", {
                run_id: activeRun.run_id, shot_id: shotId || null,
                director_note: cleanSoundstageOptionalText(directorNote), manual_board_gate: shotId ? true : manualBoardGate
            });
            setActiveRun(updated);
        } catch (err) { setProdError(err.message || "Could not synthesize storyboard plate."); }
        finally { setIsBusy(false); setRedrawingShotId(""); }
    };

    const handleSwitchStage = (nextStage, nextRun) => {
        if (nextRun && nextRun.run_id) {
            cleanupFilmingStreams(); setIsFilming(false);
            lastRunIdRef.current = nextRun.run_id;
            setActiveRun(nextRun); setManualBoardGate(Boolean(nextRun.manual_board_gate));
        }
        setActiveStageTab(nextStage);
    };

    return {
        activeStageTab, setActiveStageTab, manualBoardGate, setManualBoardGate, prodError, setProdError,
        isBusy, redrawingShotId, isFilming, liveProgressPct, liveStageLabel, liveEvents,
        startFilmingRun, handleCastAction, handleHydrateVaultChar, handleApproveCastAndDrawBoards, handleDrawOrRedrawBoards, handleSwitchStage
    };
}

function SoundstageProductionRoom({
    activeRun,
    setActiveRun,
    onEditBrief,
    fullscreenFocus,
    setFullscreenFocus,
    sessionName,
    setSessionName,
    vaultCharacters,
    addToast,
    getDisplayableRefUrl,
    onPromoteToMode2,
    onPromoteToMode3
}) {
    const pCtrl = useSoundstageProductionController({ activeRun, setActiveRun, addToast });
    const plan = (activeRun && activeRun.plan) || {};
    const identity = plan.identity || {};
    const headerPct = pCtrl.isFilming ? pCtrl.liveProgressPct : ((activeRun && typeof activeRun.progress_pct === "number") ? activeRun.progress_pct : 20);

    return (
        <section id="soundstage-production-room" aria-label="Commercial Soundstage Production Room" className="sstage-canvas rounded-2xl p-5 sm:p-8 border border-stone-800/80 shadow-2xl space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-stone-800/80 pb-5">
                <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Mode 5 · Commercial Soundstage</span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-rose-950/80 text-rose-200 border border-rose-800/60">{(pCtrl.isFilming ? pCtrl.liveStageLabel : (activeRun && activeRun.stage)) || "cast_ready"} · {headerPct}%</span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-900 text-stone-300 border border-stone-700/70">{(activeRun && activeRun.resolution) || "720p"}</span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-950 text-stone-400 border border-stone-800">{(activeRun && activeRun.run_id) || "pending"}</span>
                        <span id="soundstage-session-badge" className="text-xs font-mono px-2 py-0.5 rounded bg-stone-950 text-stone-300 border border-stone-800">{(activeRun && activeRun.session_name) || sessionName || "default_session"}</span>
                        {activeRun && activeRun.parent_run_id && (
                            <span id="soundstage-forked-badge" className="text-xs font-mono px-2.5 py-0.5 rounded bg-amber-950/80 text-amber-200 border border-amber-700/70">
                                Forked Variation ({activeRun.variation_axis || "place"}) · Parent {activeRun.parent_run_id}
                            </span>
                        )}
                    </div>
                    <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-100">
                        {identity.display_subject || "Commercial Campaign"} — {identity.display_offering || "Signature Edition"}
                    </h2>
                    <p className="text-xs sm:text-sm text-stone-300 max-w-3xl">{identity.display_tagline || "3-Act continuous-shot commercial soundstage."}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                    <button type="button" id="soundstage-btn-edit-brief" onClick={onEditBrief} className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition">← Edit Brief</button>
                    <button type="button" id="soundstage-prod-btn-fullscreen" onClick={() => setFullscreenFocus(!fullscreenFocus)} className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition">{fullscreenFocus ? "Exit Fullscreen Focus" : "Fullscreen Focus"}</button>
                </div>
            </div>

            {pCtrl.prodError && (
                <div role="alert" className="rounded-xl bg-rose-950/80 border border-rose-500/80 px-4 py-3 flex items-center justify-between gap-4 text-xs text-rose-100">
                    <span>{pCtrl.prodError}</span>
                    <button type="button" onClick={() => pCtrl.setProdError("")} className="font-mono text-rose-200 hover:text-white">Dismiss ✕</button>
                </div>
            )}

            <nav id="soundstage-stage-rail" aria-label="Soundstage 7-stage production rail" className="flex items-center gap-1.5 overflow-x-auto pb-1 custom-scrollbar">
                {SOUNDSTAGE_PROD_STAGES.map((st) => {
                    const isCurrent = pCtrl.activeStageTab === st.id;
                    const tabCls = isCurrent
                        ? "px-3.5 py-2 rounded-xl text-xs font-bold bg-rose-600 text-white shadow border border-rose-400/70 shrink-0 transition"
                        : "px-3.5 py-2 rounded-xl text-xs font-semibold bg-stone-900/90 text-stone-300 hover:text-white hover:bg-stone-800 border border-stone-800 shrink-0 transition";
                    return (
                        <button key={st.id} type="button" data-stage-tab={st.id} aria-current={isCurrent ? "step" : undefined} onClick={() => pCtrl.setActiveStageTab(st.id)} className={tabCls}>
                            {st.label}
                        </button>
                    );
                })}
            </nav>

            {pCtrl.activeStageTab === "brief" && <SoundstageBriefStageView plan={plan} />}
            {pCtrl.activeStageTab === "world" && <SoundstageWorldStageView plan={plan} />}
            {pCtrl.activeStageTab === "story" && <SoundstageStoryStageView plan={plan} />}
            {pCtrl.activeStageTab === "cast" && (
                <SoundstageCastGateView
                    activeRun={activeRun}
                    manualBoardGate={pCtrl.manualBoardGate}
                    setManualBoardGate={pCtrl.setManualBoardGate}
                    isBusy={pCtrl.isBusy || pCtrl.isFilming}
                    onCastAction={pCtrl.handleCastAction}
                    onSelectCandidate={(candUrl) => pCtrl.handleCastAction({ action: "select", custom_image_url: candUrl })}
                    onHydrateVaultChar={pCtrl.handleHydrateVaultChar}
                    onApproveCast={pCtrl.handleApproveCastAndDrawBoards}
                    vaultCharacters={vaultCharacters}
                    getDisplayableRefUrl={getDisplayableRefUrl}
                />
            )}
            {pCtrl.activeStageTab === "boards" && (
                <SoundstageBoardsGateView
                    activeRun={activeRun}
                    isBusy={pCtrl.isBusy || pCtrl.isFilming}
                    redrawingShotId={pCtrl.redrawingShotId}
                    onDrawAllBoards={() => pCtrl.handleDrawOrRedrawBoards(null, null)}
                    onRedrawTile={(shotId, note) => pCtrl.handleDrawOrRedrawBoards(shotId, note)}
                    onRollCameras={() => pCtrl.startFilmingRun(activeRun.run_id, activeRun.resolution)}
                    getDisplayableRefUrl={getDisplayableRefUrl}
                />
            )}
            {pCtrl.activeStageTab === "filming" && (
                <SoundstageFilmingStageView
                    activeRun={activeRun}
                    liveProgressPct={pCtrl.liveProgressPct}
                    liveStageLabel={pCtrl.liveStageLabel}
                    liveEvents={pCtrl.liveEvents}
                    isFilming={pCtrl.isFilming}
                    onStartFilming={pCtrl.startFilmingRun}
                />
            )}
            {pCtrl.activeStageTab === "premiere" && (
                <SoundstagePremiereStageView
                    activeRun={activeRun}
                    setActiveRun={setActiveRun}
                    setSessionName={setSessionName}
                    setFullscreenFocus={setFullscreenFocus}
                    onSwitchStage={pCtrl.handleSwitchStage}
                    onSetError={pCtrl.setProdError}
                    addToast={addToast}
                    getDisplayableRefUrl={getDisplayableRefUrl}
                    onPromoteToMode2={onPromoteToMode2}
                    onPromoteToMode3={onPromoteToMode3}
                />
            )}
        </section>
    );
}
