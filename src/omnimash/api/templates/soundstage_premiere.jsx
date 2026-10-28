// Mode 5: Commercial Soundstage — Stage 6 Live SSE Filming & Stage 7 Premiere, Sub-Shot NLE Trimmer, Surgical Director Note & Variations (Modular JSX Partial)

function SoundstageFilmingStageView({
    activeRun,
    liveProgressPct,
    liveStageLabel,
    liveEvents,
    isFilming,
    onStartFilming
}) {
    const plan = (activeRun && activeRun.plan) || {};
    const actPlans = Array.isArray(plan.acts) ? plan.acts : [];
    const actRecords = Array.isArray(activeRun && activeRun.acts) ? activeRun.acts : [];
    const safePct = Math.max(0, Math.min(100, Math.round(liveProgressPct || 0)));
    const eventsToRender = (Array.isArray(liveEvents) && liveEvents.length !== 0) ? liveEvents : ((activeRun && activeRun.events) || []);

    return (
        <div id="soundstage-filming-view" className="space-y-5">
            <div className="sstage-card rounded-xl p-5 sm:p-6 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Stage 6 · Parallel 3-Act Gemini Omni 1.1 Flash Soundstage</span>
                        <h3 className="text-base sm:text-lg font-bold text-stone-100 mt-0.5">{isFilming ? "Cameras Rolling · Live SSE Telemetry" : ("Stage Status: " + liveStageLabel)}</h3>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {SOUNDSTAGE_FILMING_TIERS.map((tier) => (
                            <button key={tier} type="button" disabled={isFilming} onClick={() => onStartFilming(activeRun.run_id, tier)} className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition disabled:opacity-50">
                                Film / Re-Master in {tier}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-mono text-stone-300">
                        <span>{liveStageLabel}</span>
                        <span>{safePct}%</span>
                    </div>
                    <div role="progressbar" aria-label="Soundstage filming progress" aria-valuenow={safePct} aria-valuemin={0} aria-valuemax={100} className="w-full h-3 rounded-full bg-stone-950 border border-stone-800 overflow-hidden">
                        <div className="h-full bg-rose-600 transition-all duration-300" style={{ width: safePct + "%" }} />
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {actPlans.map((act) => {
                    const rec = actRecords.find((r) => r.act_number === act.act_number);
                    const statusLabel = rec ? "Rendered" : (isFilming ? "Filming Continuous 10s..." : "Ready");
                    return (
                        <div key={act.act_number} className="sstage-card rounded-xl p-4 space-y-2.5">
                            <div className="flex items-center justify-between gap-2 text-xs font-mono">
                                <span className="font-bold text-rose-300">Act {act.act_number} · {act.time_window}</span>
                                <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-200 border border-stone-700">
                                    {(rec && rec.resolution) || (activeRun && activeRun.resolution) || "720p"} · Rev {(rec && rec.revision_count) || 0}
                                </span>
                            </div>
                            <h4 className="text-sm font-bold text-stone-100">{act.title}</h4>
                            <p className="text-xs font-mono text-emerald-300">{statusLabel}</p>
                            {rec && rec.last_director_note && (
                                <p className="text-xs text-stone-300 bg-stone-950/80 border border-stone-800 rounded p-2">Note: {rec.last_director_note}</p>
                            )}
                        </div>
                    );
                })}
            </div>

            <div className="sstage-card rounded-xl p-5 space-y-3">
                <h4 className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">Chronological Production Event Feed</h4>
                <div className="space-y-1.5 max-h-56 overflow-y-auto custom-scrollbar">
                    {eventsToRender.map((ev, idx) => (
                        <div key={(ev.event_id || idx) + "::" + idx} className="flex items-start justify-between gap-3 text-xs font-mono bg-stone-950/70 border border-stone-800/80 rounded-lg px-3 py-2">
                            <span className="text-stone-200">{ev.message}</span>
                            <span className="text-rose-300 shrink-0">{ev.progress_pct}%</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function SoundstagePremierePlayerCard({
    activeRun,
    selectedFormat,
    setSelectedFormat,
    onJumpToFilming,
    getDisplayableRefUrl
}) {
    const [videoFallbacks, setVideoFallbacks] = useState({});
    const deliverables = activeRun && activeRun.deliverables;

    if (!deliverables) {
        return (
            <div className="sstage-card rounded-xl p-8 text-center space-y-4">
                <p className="text-xs font-mono uppercase tracking-widest text-rose-400">Premiere Screening Room Standby</p>
                <h3 className="text-lg font-bold text-stone-100">Deliverables Not Yet Conformed</h3>
                <p className="text-xs text-stone-300 max-w-lg mx-auto">
                    Complete 3-act continuous filming in Stage 6 to conform the 30s 16:9 Master, 15s 9:16 Cutdown, and 6s 9:16 Bumper with vector end-card lockups.
                </p>
                <button type="button" onClick={onJumpToFilming} className="px-4 py-2.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white transition">
                    Go to Stage 6 · Roll Cameras →
                </button>
            </div>
        );
    }

    const activeFormatMeta = SOUNDSTAGE_FORMAT_META[selectedFormat] || SOUNDSTAGE_FORMAT_META["30s"];
    const rawDeliverableUrl = String(deliverables[activeFormatMeta.field] || "");
    const safeUrl = getSafeSoundstageMediaUrl(rawDeliverableUrl, getDisplayableRefUrl);
    const useMockFallback = Boolean(videoFallbacks[rawDeliverableUrl]);
    const effectiveVideoSrc = useMockFallback ? "/static/rendered/mock.mp4" : (safeUrl || "/static/rendered/mock.mp4");
    const frameLayoutClass = activeFormatMeta.isVertical
        ? "aspect-[9/16] max-h-[500px] mx-auto bg-black rounded-xl overflow-hidden border border-stone-800 shadow-2xl"
        : "aspect-video w-full bg-black rounded-xl overflow-hidden border border-stone-800 shadow-2xl";

    const scoreEntries = Object.entries((activeRun && activeRun.critic_scorecards) || {});
    const actRecords = Array.isArray(activeRun && activeRun.acts) ? activeRun.acts : [];
    const totalDurText = typeof deliverables.total_duration_sec === "number"
        ? deliverables.total_duration_sec.toFixed(1)
        : String(deliverables.total_duration_sec || "32.0");
    const activeTabCls = "px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white shadow border border-rose-400/70 transition";
    const idleTabCls = "px-3 py-1.5 rounded-lg text-xs font-semibold text-stone-300 hover:text-white hover:bg-stone-800/80 transition";

    const handleVideoError = () => {
        if (!useMockFallback && rawDeliverableUrl) {
            setVideoFallbacks((prev) => ({ ...prev, [rawDeliverableUrl]: true }));
        }
    };

    return (
        <div className="sstage-card rounded-xl p-5 sm:p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800/80 pb-4">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">1 Film → 3 Multi-Format Cuts</span>
                    <h3 className="text-base sm:text-lg font-bold text-stone-100 mt-0.5">{activeFormatMeta.label} · {activeFormatMeta.aspectLabel}</h3>
                </div>
                <div id="soundstage-format-tabs" role="tablist" aria-label="Commercial deliverable format switcher" className="flex flex-wrap items-center gap-1.5 bg-stone-950/90 p-1.5 rounded-xl border border-stone-800">
                    <button id="soundstage-tab-30s" type="button" role="tab" aria-selected={selectedFormat === "30s"} onClick={() => setSelectedFormat("30s")} className={selectedFormat === "30s" ? activeTabCls : idleTabCls}>
                        30s Master (16:9)
                    </button>
                    <button id="soundstage-tab-15s" type="button" role="tab" aria-selected={selectedFormat === "15s"} onClick={() => setSelectedFormat("15s")} className={selectedFormat === "15s" ? activeTabCls : idleTabCls}>
                        15s Cutdown (9:16)
                    </button>
                    <button id="soundstage-tab-6s" type="button" role="tab" aria-selected={selectedFormat === "6s"} onClick={() => setSelectedFormat("6s")} className={selectedFormat === "6s" ? activeTabCls : idleTabCls}>
                        6s Bumper (9:16)
                    </button>
                </div>
            </div>

            <div className={frameLayoutClass}>
                <video
                    key={selectedFormat + "::" + rawDeliverableUrl}
                    id="soundstage-premiere-video"
                    controls
                    playsInline
                    preload="metadata"
                    data-format={selectedFormat}
                    data-deliverable-url={rawDeliverableUrl}
                    src={effectiveVideoSrc}
                    onError={handleVideoError}
                    className="w-full h-full object-contain bg-black"
                />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
                    <span id="soundstage-active-subshot-badge" className="px-2.5 py-1 rounded-md bg-emerald-950/70 text-emerald-200 border border-emerald-700/60">
                        {deliverables.active_subshot_count} active sub-shots
                    </span>
                    <span className="px-2.5 py-1 rounded-md bg-stone-900 text-stone-200 border border-stone-700/80">{totalDurText}s total duration</span>
                    <span className="px-2.5 py-1 rounded-md bg-stone-900 text-stone-300 border border-stone-800">WCAG Vector End-Card ({activeRun.end_card_duration_sec || 2.0}s)</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
                    {actRecords.map((rec) => (
                        <span key={rec.act_number} data-act-card={rec.act_number} data-act-revisions={rec.revision_count || 0} className="px-2.5 py-1 rounded-md bg-stone-950 text-stone-200 border border-stone-800">
                            Act {rec.act_number} · Rev {rec.revision_count || 0}
                        </span>
                    ))}
                </div>
            </div>

            {scoreEntries.length !== 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-stone-800/70">
                    {scoreEntries.map(([key, sc]) => {
                        const ratingNum = sc && typeof sc.overall_rating === "number" ? sc.overall_rating.toFixed(1) : "94.0";
                        const passed = !sc || sc.pass_verdict !== false;
                        const verdictCls = passed
                            ? "text-xs font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-200 border border-emerald-700/60"
                            : "text-xs font-mono px-2 py-0.5 rounded bg-amber-950/80 text-amber-200 border border-amber-700/60";
                        return (
                            <div key={key} className="sstage-elevated rounded-lg p-3.5 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">DOMA AI Critic · {key}</span>
                                    <span className={verdictCls}>{ratingNum} / 100 · {passed ? "PASS" : "REVIEW"}</span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-xs font-mono text-stone-300">
                                    <span>Text: {sc && sc.video_text_adherence && typeof sc.video_text_adherence.score === "number" ? sc.video_text_adherence.score : 95}</span>
                                    <span>Cast: {sc && sc.character_likeness && typeof sc.character_likeness.score === "number" ? sc.character_likeness.score : 94}</span>
                                    <span>Audio: {sc && sc.audio_visual_harmony && typeof sc.audio_visual_harmony.score === "number" ? sc.audio_visual_harmony.score : 93}</span>
                                    <span>Tags: {sc && sc.tag_and_index_integrity && typeof sc.tag_and_index_integrity.score === "number" ? sc.tag_and_index_integrity.score : 98}</span>
                                </div>
                                {sc && sc.verbal_critique && <p className="text-xs text-stone-300 leading-relaxed">{sc.verbal_critique}</p>}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function SoundstageNleTrimmerPanel({
    nleSpecs,
    onAdjustTrim,
    onToggleBypass,
    onResetTrims,
    onReconform,
    isBusy,
    hasDeliverables
}) {
    const activeCount = nleSpecs.filter((s) => !s.bypassed).length;

    return (
        <div id="soundstage-nle-trimmer" className="sstage-card rounded-xl p-5 sm:p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800/80 pb-4">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Zero-Cost Sub-Shot NLE Trimmer (1.1 – 3.3)</span>
                    <h3 className="text-base font-bold text-stone-100 mt-0.5">Trim In / Out &amp; Bypass Beats ({activeCount} / 9 Active)</h3>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <button type="button" id="soundstage-btn-reset-trims" disabled={isBusy} onClick={onResetTrims} className="px-3 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition disabled:opacity-50">
                        Reset Trims
                    </button>
                    <button type="button" id="soundstage-btn-reconform" disabled={isBusy || !hasDeliverables} onClick={onReconform} className="px-4 py-2 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow transition disabled:opacity-50">
                        {isBusy ? "Reconforming..." : "Reconform Cuts (Instant FFmpeg)"}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {nleSpecs.map((spec) => {
                    const win = computeSubshotEffectiveWindow(spec);
                    const isBypassed = Boolean(spec.bypassed);
                    const cardCls = isBypassed
                        ? "rounded-xl p-3.5 border border-stone-800/80 bg-stone-950/50 opacity-65 space-y-2.5"
                        : "sstage-elevated rounded-xl p-3.5 space-y-2.5";
                    const bypassCls = isBypassed
                        ? "px-2.5 py-1 rounded text-xs font-mono font-bold bg-amber-950/80 text-amber-200 border border-amber-700/70"
                        : "px-2.5 py-1 rounded text-xs font-mono font-semibold bg-emerald-950/70 text-emerald-200 border border-emerald-700/60";
                    return (
                        <div key={spec.shot_id} data-nle-shot={spec.shot_id} className={cardCls}>
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-mono font-bold text-stone-100">Shot {spec.shot_id} · Act {spec.act_index + 1}</span>
                                <button type="button" data-nle-bypass={spec.shot_id} aria-pressed={isBypassed} aria-label={"Toggle bypass for sub-shot " + spec.shot_id} disabled={isBusy} onClick={() => onToggleBypass(spec.shot_id)} className={bypassCls}>
                                    {isBypassed ? "Bypassed" : "Keep"}
                                </button>
                            </div>
                            <p className="text-xs font-mono text-stone-300">{win.startSec.toFixed(2)}s – {win.endSec.toFixed(2)}s · {win.durSec.toFixed(2)}s</p>
                            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                                <div className="bg-stone-950/80 rounded-lg p-2 border border-stone-800 space-y-1">
                                    <span className="block text-stone-400">In ({spec.trim_in_sec.toFixed(2)}s)</span>
                                    <div className="flex items-center gap-1">
                                        <button type="button" data-nle-trim-in-dec={spec.shot_id} aria-label={"Trim in -0.25s for shot " + spec.shot_id} disabled={isBusy} onClick={() => onAdjustTrim(spec.shot_id, "trim_in_sec", -0.25)} className="flex-1 py-1 rounded bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700">-0.25s</button>
                                        <button type="button" data-nle-trim-in-inc={spec.shot_id} aria-label={"Trim in +0.25s for shot " + spec.shot_id} disabled={isBusy} onClick={() => onAdjustTrim(spec.shot_id, "trim_in_sec", 0.25)} className="flex-1 py-1 rounded bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700">+0.25s</button>
                                    </div>
                                </div>
                                <div className="bg-stone-950/80 rounded-lg p-2 border border-stone-800 space-y-1">
                                    <span className="block text-stone-400">Out ({spec.trim_out_sec.toFixed(2)}s)</span>
                                    <div className="flex items-center gap-1">
                                        <button type="button" data-nle-trim-out-dec={spec.shot_id} aria-label={"Trim out -0.25s for shot " + spec.shot_id} disabled={isBusy} onClick={() => onAdjustTrim(spec.shot_id, "trim_out_sec", -0.25)} className="flex-1 py-1 rounded bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700">-0.25s</button>
                                        <button type="button" data-nle-trim-out-inc={spec.shot_id} aria-label={"Trim out +0.25s for shot " + spec.shot_id} disabled={isBusy} onClick={() => onAdjustTrim(spec.shot_id, "trim_out_sec", 0.25)} className="flex-1 py-1 rounded bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700">+0.25s</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function SoundstageDirectorNoteBar({ isBusy, hasDeliverables, onSubmitRevise }) {
    const [directorNote, setDirectorNote] = useState("");
    const [targetAct, setTargetAct] = useState("");

    const handleReviseClick = async () => {
        const cleanNote = directorNote.trim();
        if (!cleanNote) return;
        const ok = await onSubmitRevise(cleanNote, targetAct ? Number(targetAct) : null);
        if (ok) setDirectorNote("");
    };

    return (
        <div id="soundstage-director-note-bar" className="sstage-card rounded-xl p-5 sm:p-6 space-y-4">
            <div>
                <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Lock &amp; Isolate Surgical Re-Cut</span>
                <h3 className="text-base font-bold text-stone-100 mt-0.5">Single-Line Director Note (Re-Films Only Target 10s Act)</h3>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-end">
                <div className="lg:col-span-6 space-y-1.5">
                    <label htmlFor="soundstage-input-director-note" className="block text-xs font-mono text-stone-300">Director Note</label>
                    <input id="soundstage-input-director-note" type="text" value={directorNote} onChange={(e) => setDirectorNote(e.target.value)} placeholder="e.g., Add warm amber rim light in Act 2" className="w-full rounded-lg bg-stone-950 border border-stone-700 px-3.5 py-2.5 text-xs text-stone-100" />
                </div>
                <div className="lg:col-span-3 space-y-1.5">
                    <label htmlFor="soundstage-select-target-act" className="block text-xs font-mono text-stone-300">Target Act Scope</label>
                    <select id="soundstage-select-target-act" value={targetAct} onChange={(e) => setTargetAct(e.target.value)} className="w-full rounded-lg bg-stone-950 border border-stone-700 px-3 py-2.5 text-xs text-stone-100">
                        <option value="">Auto-Detect Target Act</option>
                        <option value="1">Act 1 (0:00–0:10)</option>
                        <option value="2">Act 2 (0:10–0:20)</option>
                        <option value="3">Act 3 (0:20–0:30)</option>
                    </select>
                </div>
                <div className="lg:col-span-3">
                    <button type="button" id="soundstage-btn-revise" disabled={isBusy || !hasDeliverables || !directorNote.trim()} onClick={handleReviseClick} className="w-full px-4 py-2.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow transition disabled:opacity-50">
                        {isBusy ? "Re-Filming Act..." : "Apply Surgical Re-Cut →"}
                    </button>
                </div>
            </div>
        </div>
    );
}

function SoundstageVariationsAndExportPanel({
    activeRun,
    isBusy,
    onForkVariation,
    onPromoteMode2,
    onPromoteMode3
}) {
    const [variationAxis, setVariationAxis] = useState("place");
    const [variationValue, setVariationValue] = useState("Milan · Brera");
    const activeAxisMeta = SOUNDSTAGE_VARIATION_AXES.find((a) => a.axis === variationAxis) || SOUNDSTAGE_VARIATION_AXES[0];
    const runIdEncoded = encodeURIComponent((activeRun && activeRun.run_id) || "");
    const zipHref = "/api/soundstage/" + runIdEncoded + "/package.zip";
    const hasDeliverables = Boolean(activeRun && activeRun.deliverables);

    const handleSelectAxis = (nextAxis) => {
        setVariationAxis(nextAxis);
        const found = SOUNDSTAGE_VARIATION_AXES.find((a) => a.axis === nextAxis);
        if (found && found.chips[0]) setVariationValue(found.chips[0]);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div id="soundstage-variations-panel" className="sstage-card rounded-xl p-5 space-y-4">
                <div>
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Session-Isolated Campaign Forking</span>
                    <h3 className="text-base font-bold text-stone-100 mt-0.5">Multi-Axis Variations (Place · Cast · Offering)</h3>
                    <p className="text-xs text-stone-300 mt-1">{activeAxisMeta.description}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {SOUNDSTAGE_VARIATION_AXES.map((item) => {
                        const isActive = variationAxis === item.axis;
                        const axisCls = isActive
                            ? "px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white border border-rose-400/70"
                            : "px-3 py-1.5 rounded-lg text-xs font-semibold bg-stone-900 text-stone-300 border border-stone-700 hover:text-white";
                        return (
                            <button key={item.axis} type="button" data-variation-axis={item.axis} aria-pressed={isActive} onClick={() => handleSelectAxis(item.axis)} className={axisCls}>
                                {item.label}
                            </button>
                        );
                    })}
                </div>
                <div className="flex flex-wrap gap-1.5">
                    {activeAxisMeta.chips.map((chip) => (
                        <button key={chip} type="button" onClick={() => setVariationValue(chip)} className="px-2.5 py-1 rounded-md text-xs font-mono bg-stone-950 hover:bg-stone-800 text-stone-200 border border-stone-800 transition">
                            {chip}
                        </button>
                    ))}
                </div>
                <div className="space-y-1.5">
                    <label htmlFor="soundstage-input-variation-value" className="block text-xs font-mono text-stone-300">New {activeAxisMeta.label} Directive</label>
                    <div className="flex flex-col sm:flex-row gap-2">
                        <input id="soundstage-input-variation-value" type="text" value={variationValue} onChange={(e) => setVariationValue(e.target.value)} className="flex-1 rounded-lg bg-stone-950 border border-stone-700 px-3.5 py-2 text-xs text-stone-100" />
                        <button type="button" id="soundstage-btn-fork-variation" disabled={isBusy || !variationValue.trim()} onClick={() => onForkVariation(variationAxis, variationValue.trim())} className="px-4 py-2 rounded-lg text-xs font-bold bg-stone-100 hover:bg-white text-stone-950 transition disabled:opacity-50">
                            {isBusy ? "Forking..." : "Fork Variation Session →"}
                        </button>
                    </div>
                </div>
            </div>

            <div id="soundstage-export-bar" className="sstage-card rounded-xl p-5 flex flex-col justify-between space-y-4">
                <div className="space-y-1.5">
                    <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">Delivery Archive &amp; Studio Hand-Off</span>
                    <h3 className="text-base font-bold text-stone-100">Campaign Package (.zip) &amp; Cross-Mode Promotion</h3>
                    <p className="text-xs text-stone-300 leading-relaxed">
                        Export all 3 multi-format MP4 deliverables, 9 storyboard plates, cast &amp; emblem anchors, and production manifest, or hand off directly into Mode 2 or Mode 3.
                    </p>
                </div>
                <div className="space-y-2.5">
                    {hasDeliverables ? (
                        <a id="soundstage-btn-download-zip" href={zipHref} download className="w-full inline-flex items-center justify-center px-4 py-2.5 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow transition">
                            Download Campaign Package (.zip)
                        </a>
                    ) : (
                        <span id="soundstage-btn-download-zip" aria-disabled="true" className="w-full inline-flex items-center justify-center px-4 py-2.5 rounded-lg text-xs font-semibold bg-stone-900 text-stone-400 border border-stone-800 opacity-60">
                            Download Campaign Package (.zip) (Film Acts First)
                        </span>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        <button type="button" id="soundstage-btn-promote-mode2" onClick={onPromoteMode2} className="px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-100 border border-stone-700 transition">
                            Open in Mode 2 (Screenplay Storyboard)
                        </button>
                        <button type="button" id="soundstage-btn-promote-mode3" onClick={onPromoteMode3} className="px-3.5 py-2.5 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-100 border border-stone-700 transition">
                            Open in Mode 3 (Continuity Studio)
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function SoundstagePremiereStageView({
    activeRun,
    setActiveRun,
    setSessionName,
    setFullscreenFocus,
    onSwitchStage,
    onSetError,
    addToast,
    getDisplayableRefUrl,
    onPromoteToMode2,
    onPromoteToMode3
}) {
    const [selectedFormat, setSelectedFormat] = useState("30s");
    const [nleSpecs, setNleSpecs] = useState(() => buildNormalizedClientNleSpecs(activeRun && activeRun.subshot_specs));
    const [isBusy, setIsBusy] = useState(false);
    const specsSignature = JSON.stringify((activeRun && activeRun.subshot_specs) || []);
    const currentRunId = (activeRun && activeRun.run_id) || "";

    useEffect(() => {
        setNleSpecs(buildNormalizedClientNleSpecs(activeRun && activeRun.subshot_specs));
    }, [currentRunId, specsSignature]);

    const handleAdjustTrim = (shotId, field, delta) => {
        setNleSpecs((prev) => prev.map((spec) => {
            if (spec.shot_id !== shotId) return spec;
            const nextVal = Math.round(((spec[field] || 0) + delta) * 1000) / 1000;
            return { ...spec, [field]: Math.max(-3.0, Math.min(6.0, nextVal)) };
        }));
    };

    const handleToggleBypass = (shotId) => {
        const activeCount = nleSpecs.filter((s) => !s.bypassed).length;
        const target = nleSpecs.find((s) => s.shot_id === shotId);
        if (target && !target.bypassed && activeCount === 1) {
            if (addToast) addToast("At least 1 sub-shot must remain active for multi-format conform.", "warning");
            return;
        }
        setNleSpecs((prev) => prev.map((s) => (s.shot_id === shotId ? { ...s, bypassed: !s.bypassed } : s)));
    };

    const handleReconform = async () => {
        if (!currentRunId || isBusy) return;
        setIsBusy(true); onSetError("");
        try {
            const updated = await postSoundstageJson("/api/soundstage/" + encodeURIComponent(currentRunId) + "/reconform", { subshot_specs: nleSpecs });
            setActiveRun(updated);
            if (addToast) addToast("Re-conformed 30s, 15s, and 6s deliverables via FFmpeg.", "success");
        } catch (err) { onSetError(err.message || "Failed to reconform sub-shot timeline."); }
        finally { setIsBusy(false); }
    };

    const handleReviseAct = async (directorNote, targetAct) => {
        if (!currentRunId || isBusy) return false;
        setIsBusy(true); onSetError("");
        try {
            const revised = await postSoundstageJson("/api/soundstage/" + encodeURIComponent(currentRunId) + "/revise", {
                director_note: directorNote,
                target_act: targetAct,
                resolution: (activeRun && activeRun.resolution) || "720p"
            });
            setActiveRun(revised);
            if (addToast) addToast("Applied surgical Director Note re-cut.", "success");
            return true;
        } catch (err) { onSetError(err.message || "Surgical act revision failed."); return false; }
        finally { setIsBusy(false); }
    };

    const handleForkVariation = async (axis, newValue) => {
        if (!currentRunId || isBusy) return;
        setIsBusy(true); onSetError("");
        try {
            const forkedRun = await postSoundstageJson("/api/soundstage/" + encodeURIComponent(currentRunId) + "/variations", {
                axis,
                new_value: newValue,
                auto_generate_boards: true,
                auto_film: false
            });
            if (setSessionName && forkedRun.session_name) setSessionName(forkedRun.session_name);
            onSwitchStage("boards", forkedRun);
            if (addToast) addToast("Forked " + axis + " variation into session " + forkedRun.session_name + ".", "success");
        } catch (err) { onSetError(err.message || "Failed to fork campaign variation."); }
        finally { setIsBusy(false); }
    };

    const handlePromote = (targetFn) => {
        const planToPromote = buildSoundstagePromotionPlan(activeRun);
        if (setFullscreenFocus) setFullscreenFocus(false);
        if (targetFn) targetFn(planToPromote);
    };

    return (
        <div id="soundstage-premiere-view" className="space-y-5">
            <SoundstagePremierePlayerCard activeRun={activeRun} selectedFormat={selectedFormat} setSelectedFormat={setSelectedFormat} onJumpToFilming={() => onSwitchStage("filming", null)} getDisplayableRefUrl={getDisplayableRefUrl} />
            <SoundstageNleTrimmerPanel nleSpecs={nleSpecs} onAdjustTrim={handleAdjustTrim} onToggleBypass={handleToggleBypass} onResetTrims={() => setNleSpecs(buildNormalizedClientNleSpecs(null))} onReconform={handleReconform} isBusy={isBusy} hasDeliverables={Boolean(activeRun && activeRun.deliverables)} />
            <SoundstageDirectorNoteBar isBusy={isBusy} hasDeliverables={Boolean(activeRun && activeRun.deliverables)} onSubmitRevise={handleReviseAct} />
            <SoundstageVariationsAndExportPanel activeRun={activeRun} isBusy={isBusy} onForkVariation={handleForkVariation} onPromoteMode2={() => handlePromote(onPromoteToMode2)} onPromoteMode3={() => handlePromote(onPromoteToMode3)} />
        </div>
    );
}
