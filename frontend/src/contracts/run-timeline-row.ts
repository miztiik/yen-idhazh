// Generated from `backend/idhazh/contracts/run_timeline.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One item's bar: where it starts on the run's clock, and what it spent. */
export interface RunTimelineRow {
	version?: string;

	date: string;

	run_id: string;

	/** Which work shard read and summarised this item. Two bars overlapping on the clock is correct exactly when they sit on different shards, and without this column a reader cannot tell an overlap from a contradiction. The plan and publish steps are not sharded; this names the shard that did the middle. */
	shard: number;

	/** The item this bar is about. An item no shard was given produces no row rather than an empty one, so an absent row reads as never worked. */
	item_id: string;

	/** Milliseconds from the run's start to the moment this item's own work began. An offset and not a timestamp: the reader is asking where on the run's clock the bar sits, and an item that queued forty seconds has to sit forty seconds to the right for the queue to be visible at all. */
	start_offset_ms: number;

	/** How long the bar is - what the item cost once its wait is taken out, which is the same number `ItemHealthRow.item_total_ms` holds and spelled the same way. The wait is `start_offset_ms` and is drawn as position rather than length, so counting it here would draw it twice. */
	item_total_ms: number;

	/** Step 1. What choosing this item cost. Null where nothing timed it. */
	plan_ms?: number | null;

	/** Step 2. Reading the page, as `ItemHealthRow.fetch_ms` spells it. */
	fetch_ms?: number | null;

	/** Step 3. Taking the article out of the page, as the census spells it. */
	extract_ms?: number | null;

	/** Step 4. The label call, on the stopwatch the census spells `label_ms`. */
	label_ms?: number | null;

	/** Step 5. The summarize-and-plan call, on the stopwatch the census spells `summary_ms`. */
	summary_ms?: number | null;

	/** Step 6. What the visual plan cost. The plan is decoded inside the call above, so this is apportioned out of `summary_ms` rather than timed beside it - which is why the residual is signed. */
	visual_plan_ms?: number | null;

	/** Step 7. The model-free scorers, as `EvalRow.score_ms` spells it. */
	score_ms?: number | null;

	/** Step 8. What placing this item in the day cost. Null where nothing timed it. */
	publish_ms?: number | null;

	/** `item_total_ms` minus the eight named steps: the part of the bar no step accounts for. Its own column because a step that absorbed the leftover reads as slower than it was. Signed on purpose - a negative value means two of the eight overlapped or two clocks disagreed, and the apportioned visual plan is a known overlap, so clamping it to zero would hide the one signal that says so. Derived here rather than supplied: a row that omits it gets it filled, and a row that disagrees with the arithmetic is refused. */
	residual_ms: number;
}
