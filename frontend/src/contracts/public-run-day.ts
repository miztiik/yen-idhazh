// Generated from `backend/idhazh/contracts/public_run_day.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One run of one day, from that day's `run.json`. */
export interface PublicRunRecord {
	run_id: string;

	/** Which run of the day this was. */
	n: number;

	status: string;

	planned: number;

	succeeded: number;

	failed: number;

	skipped: number;

	started_at: string;

	source_list_stale?: boolean;

	/** Items the visual planner posted to the model. */
	decided?: number;

	/** Items the planner decided without posting, because no enabled kind could survive its checks. */
	prefiltered?: number;

	/** Items whose planner reply asked for a chart, whatever the decision became. */
	charts_drafted?: number;

	/** What the planner spent. Null and zero are different facts: a visuals job that never ran spent no measured time, and printing that as zero minutes reads as a stage that was free rather than one that is missing. */
	decision_ms?: number | null;
}

/** One published day: what its runs did, and what the page ended up carrying. */
export interface PublicRunDay {
	version?: string;

	date: string;

	/** Every run of the day, in the order they ran. */
	runs?: PublicRunRecord[];

	/** The committed payload tree as the day's LAST run measured it. Taken from the last run rather than summed: the site is one thing measured once per run, not a new thing each run. */
	site_bytes?: number;

	site_files?: number;

	/** Distinct model ids the day's runs used, in first-seen order. */
	models?: string[];

	/** Articles the day payload carries. The denominator of the site's per-article cost, counted from the same tree site_bytes measures. */
	published_items?: number;

	/** Charts a reader can actually see: a visual of kind chart in state rendered. Counted from the day payload rather than the manifest, because the manifest records what the planner decided and this records what survived to the page. */
	published_charts?: number;
}
