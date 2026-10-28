// Mode 5: Commercial Soundstage — Production & Premiere Room (Modular JSX Partial)

function SoundstageProductionRoom({
    activeRun,
    onEditBrief,
    fullscreenFocus,
    setFullscreenFocus,
    getDisplayableRefUrl
}) {
    const plan = (activeRun && activeRun.plan) || {};
    const identity = plan.identity || {};
    const palette = plan.palette || {
        primary_hex: "#1A222D",
        primary_name: "Obsidian Slate",
        secondary_hex: "#C4633B",
        secondary_name: "Sienna Saddle",
        neutral_hex: "#EAE6DF",
        neutral_name: "Chalk Travertine",
        production_design_directive: ""
    };
    const physics = plan.physics || {};
    const refKit = (activeRun && activeRun.reference_kit) || {};
    const leadCastDisplayUrl = refKit.lead_cast_url
        ? getDisplayableRefUrl(refKit.lead_cast_url)
        : "";
    const emblemDisplayUrl = refKit.emblem_url
        ? getDisplayableRefUrl(refKit.emblem_url)
        : "";
    const packshotDisplayUrl = refKit.packshot_url
        ? getDisplayableRefUrl(refKit.packshot_url)
        : "";
    const progressPct = activeRun && typeof activeRun.progress_pct === "number"
        ? activeRun.progress_pct
        : 20;

    return (
        <section
            id="soundstage-production-room"
            aria-label="Commercial Soundstage Production Room"
            className="sstage-canvas rounded-2xl p-6 sm:p-8 border border-stone-800/80 shadow-2xl space-y-6"
        >
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-stone-800/80 pb-5">
                <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono uppercase tracking-widest text-rose-400 font-semibold">
                            Mode 5 · Commercial Soundstage
                        </span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-rose-950/80 text-rose-200 border border-rose-800/60">
                            {(activeRun && activeRun.stage) || "cast_ready"} · {progressPct}%
                        </span>
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-stone-900 text-stone-300 border border-stone-700/70">
                            {(activeRun && activeRun.resolution) || "720p"}
                        </span>
                    </div>
                    <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-100">
                        {identity.display_subject || "Commercial Campaign"} — {identity.display_offering || "Signature Edition"}
                    </h2>
                    <p className="text-xs sm:text-sm text-stone-300 max-w-3xl">
                        {identity.display_tagline || "3-Act continuous-shot commercial soundstage ready for storyboard synthesis and filming."}
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-2.5">
                    <button
                        type="button"
                        id="soundstage-btn-edit-brief"
                        onClick={onEditBrief}
                        className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition"
                    >
                        ← Edit Brief
                    </button>
                    <button
                        type="button"
                        id="soundstage-prod-btn-fullscreen"
                        onClick={() => setFullscreenFocus(!fullscreenFocus)}
                        className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-stone-900 hover:bg-stone-800 text-stone-200 border border-stone-700 transition"
                    >
                        {fullscreenFocus ? "Exit Fullscreen Focus" : "Fullscreen Focus"}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="sstage-card rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                        <h3 className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">
                            Lead Cast &amp; Kit Anchors
                        </h3>
                        <span className="text-xs font-mono text-rose-300">
                            Handle: {identity.omni_safe_cast_handle || "Vanguard"}
                        </span>
                    </div>
                    {leadCastDisplayUrl ? (
                        <img
                            src={leadCastDisplayUrl}
                            alt="Lead commercial cast turnaround reference"
                            className="w-full h-36 object-cover rounded-lg border border-stone-800 bg-black/50"
                        />
                    ) : (
                        <div className="w-full h-36 rounded-lg border border-stone-800 bg-stone-950/70 flex items-center justify-center text-xs text-stone-400">
                            Cast reference locked for 3-act filming
                        </div>
                    )}
                    <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-stone-300">
                        <span className="px-2 py-0.5 rounded bg-stone-900 border border-stone-800">
                            {emblemDisplayUrl ? "Emblem Ready" : "Clean End-Card"}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-stone-900 border border-stone-800">
                            {packshotDisplayUrl ? "Packshot Locked" : "Auto Packshot"}
                        </span>
                    </div>
                </div>

                <div className="sstage-card rounded-xl p-4 space-y-3">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">
                        60 / 30 / 10 Color Lock
                    </h3>
                    <div className="h-4 w-full rounded-md overflow-hidden flex border border-stone-700/80">
                        <div style={{ width: "60%", backgroundColor: palette.primary_hex }} title={palette.primary_name} />
                        <div style={{ width: "30%", backgroundColor: palette.secondary_hex }} title={palette.secondary_name} />
                        <div style={{ width: "10%", backgroundColor: palette.neutral_hex }} title={palette.neutral_name} />
                    </div>
                    <p className="text-xs text-stone-300 leading-relaxed">
                        {palette.production_design_directive || `${palette.primary_name} / ${palette.secondary_name} / ${palette.neutral_name}`}
                    </p>
                </div>

                <div className="sstage-card rounded-xl p-4 space-y-3">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-stone-300 font-semibold">
                        Offering Physics &amp; Deliverables
                    </h3>
                    <div className="flex flex-wrap gap-1.5 text-xs font-mono">
                        <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-200 border border-stone-700/80">
                            {physics.archetype || "HANDHELD_CPG_OR_OBJECT"}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-300 border border-stone-800">
                            {physics.ergonomic_role || "ACTIVE_USER_OR_CONSUMER"}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-stone-900 text-stone-300 border border-stone-800">
                            {physics.physical_scale || "HANDHELD_10_TO_30CM"}
                        </span>
                    </div>
                    <p className="text-xs text-stone-300">
                        Run ID: <span className="font-mono text-stone-200">{(activeRun && activeRun.run_id) || "pending"}</span>
                    </p>
                    <p className="text-xs text-stone-400">
                        Target Conform Suite: 30s Master · 15s Cutdown · 6s Bumper (Gemini Omni 1.1 Flash)
                    </p>
                </div>
            </div>
        </section>
    );
}
