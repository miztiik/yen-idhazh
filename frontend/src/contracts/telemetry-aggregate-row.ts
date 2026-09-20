// Generated from `backend/idhazh/contracts/telemetry_aggregate.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * The pipeline's stage vocabulary - one name per step an item passes through.
 *
 * **Three contracts take this type and only one of them means "terminal".**
 * `ItemHealthRow.stage` is the census column and records where an item
 * STOPPED, so it takes `TERMINAL_STAGES` and refuses anything else.
 * `DayStageTiming.stage` names the step a clock was read at, and
 * `telemetry.event(src=...)` names the step that logged a line. Neither of
 * those two is an ending, and neither is exhaustive - `publish_day_metrics`
 * times three of these names and one emitter writes one of them.
 *
 * Declaration order is the funnel a person reads down, and
 * `retention.compact_month` sorts a month's groups by it. The order is free to
 * change: this is a `StrEnum`, so the wire value is the string and never the
 * position.
 */
export const ITEM_STAGE = ['plan', 'fetch', 'extract', 'summarize', 'visual', 'publish'] as const;

export type ItemStage = (typeof ITEM_STAGE)[number];

/** One `(date, stage)` pair, summarised from one month of item-health rows. */
export interface TelemetryAggregateRow {
	version?: string;

	date: string;

	stage: ItemStage;

	/** Rows the shard held for this date and stage, counted as they were written. A run that executed twice under one run id really does leave two rows for one item, and the fold reproduces that rather than deciding for a later reader which of them to believe. */
	items: number;

	/** Of those rows, the ones whose outcome was not ok. The numerator. */
	failed: number;

	/** Of those rows, the ones that recorded any milliseconds at all. The denominator the four figures below are taken over, which is never the row count: a plan-stage row times nothing, and a row written before the timing columns existed times nothing either. */
	timed: number;

	/** Nearest-rank median of fetch, extract and summarize milliseconds added up per row. Empty when no row at this stage recorded any - empty is not zero. */
	p50_ms?: number | null;

	/** Nearest-rank 90th percentile. */
	p90_ms?: number | null;

	/** The slowest row of the group. */
	max_ms?: number | null;

	/** Every timed row added together, so a day's total stage time survives the fold. A percentile cannot be re-added into a total; this can. */
	sum_ms?: number | null;
}
