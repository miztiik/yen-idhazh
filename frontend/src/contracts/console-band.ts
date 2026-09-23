// Generated from `backend/idhazh/contracts/console_band.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One run of the newest day, as the band draws it. */
export interface BandRun {
	health: Health;

	/** What the square means, for a reader who cannot see the colour. */
	label: string;
}

/** The committed tree against the 1 GB Pages cap (`CLAUDE.md` Guardrail #2). */
export interface BandSize {
	/** The committed payload tree at the newest run, or null if unmeasured. */
	bytes?: number | null;

	/** That tree against the cap. Above 1.0 is a site over the cap, not an error. */
	cap_fraction?: number | null;

	/** Megabytes left under the cap. */
	left_mb?: number | null;

	/** Articles to the cap, at the cost the whole record measured. */
	articles_to_cap?: number | null;

	/** Published days the per-article cost was measured over. */
	measured_days?: number;

	sentence: string;
}

/** Whether the newest day worked, in one sentence and one row of squares. */
export interface BandVerdict {
	/** The newest day the manifests hold, or null before any run. */
	date?: string | null;

	sentence: string;

	health: Health;

	/** One square a run, in the order they ran. It says what the sentence cannot: whether one run ate every failure or all five limped. */
	runs?: BandRun[];

	/** Runs past the squares drawn. A day of thirty squares is a chart. */
	more_runs?: number;
}

/** The one worst thing on the whole console, and which route it is on. */
export interface BandWorst {
	id: RouteId;

	label: string;

	href: string;

	sentence: string;
}

/** One route on the strip, carrying its own worst state. */
export interface ConsoleRoute {
	id: RouteId;

	label: string;

	href: string;

	description: string;

	/** The route's own worst state, appended to its label. Null when clear. */
	worst?: string | null;

	/** How loud the route's worst state is: 0 clear, 1 worth knowing, 2 worth a look, 3 broken. Ranked rather than coloured - the strip never takes the health ramp, because a route is a noun. */
	severity: number;

	/** One sentence pointing at the panel another route owns. */
	carries: string;
}

/** Green: it worked. Amber: look at it. Red: it did not work. */
export const HEALTH = ['green', 'amber', 'red'] as const;

export type Health = (typeof HEALTH)[number];

/**
 * The five console routes. The id is the address; the label is the words.
 *
 * `JUDGEMENT` and `VOICES` joined on 2026-09-12. They are declared here before
 * either page draws a panel, because the strip is the console's only
 * navigation and a tab naming a route the band does not carry is a tab the
 * band's own validator refuses.
 */
export const ROUTE_ID = ['pipelines', 'model', 'machine', 'judgement', 'voices'] as const;

export type RouteId = (typeof ROUTE_ID)[number];

/** What every console route carries above its own panels. */
export interface ConsoleBand {
	version?: string;

	generated_at: string;

	verdict: BandVerdict;

	/** Null when every route is clear, which is a state and not an absence. */
	worst?: BandWorst | null;

	size: BandSize;

	/** The strip, in the order it is drawn. */
	routes?: ConsoleRoute[];

	/** Every month a payload shard exists for, oldest first. The console asks for a month by name, so this is the list it picks from - and it is here rather than in a file of its own so the first month is the second hop and not the third. */
	months?: string[];

	/** Always 0. Nothing waits to be compacted, because every writer files its rows under the day those rows name. A payload written before that change can still carry a higher reading. */
	compaction_lag_days?: number;

	/** Always 0, for the reason compaction_lag_days is. A payload written before that change can still carry a higher reading. */
	rows_uncompacted?: number;

	/** The day this run assembled. That is the newest day the record can cover, because this run is the one writing it. Null only on a payload written before the field was always filled. */
	covers_through?: string | null;
}
