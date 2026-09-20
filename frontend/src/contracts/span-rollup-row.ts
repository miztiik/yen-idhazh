// Generated from `backend/idhazh/contracts/span_rollup.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * The five spans a shard commits a count and a duration for.
 *
 * This is the committed subset of `telemetry.SpanName`, and it lives in the
 * contract rather than beside the tracer because a committed column's ids are a
 * contract: a reader a year from now parses `span_name` against this enum, not
 * against the tracer's wider list. `telemetry` derives its filter from this
 * enum, so the two cannot drift and this is the one place the committed set is
 * written down.
 *
 * Declared in the order the fold emits them - the `item` parent first, then the
 * four sub-steps in the order the pipeline runs them.
 */
export const ROLLUP_SPAN = ['item', 'robots', 'tag', 'render_prompt', 'parse_reply'] as const;

export type RollupSpan = (typeof ROLLUP_SPAN)[number];

/** One `(date, run_id, shard, span_name)` group's span count and summed duration. */
export interface SpanRollupRow {
	version?: string;

	date: string;

	run_id: string;

	/** Which work shard of the run these spans came from. */
	shard: number;

	/** Which of the five committed spans this row folds, as the enum spells it. */
	span_name: RollupSpan;

	/** How many spans of this name the shard opened. At least one: a name with no span produces no row rather than a zero row, so an absent row reads as never opened and never as opened-and-measured-nothing. */
	count: number;

	/** Every span of this name added together, in whole milliseconds. A total and not a mean, because a mean cannot be re-summed across shards and the reconciliation that reads this row needs the sum. Zero is possible and honest: a counted span can round to nothing. */
	total_ms: number;

	/** The shard's wall clock minus the time inside its item spans, in whole milliseconds - the overhead between and around items that no span covers. Carried on the `item` row only; null on the other four spans and on any row written before this field existed. Null reads as not-this-row, never as zero overhead measured. */
	unattributed_ms?: number | null;
}
