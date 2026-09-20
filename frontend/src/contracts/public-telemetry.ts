// Generated from `backend/idhazh/contracts/public_telemetry.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Which model call these numbers came from.
 *
 * Four members and not two, because the call structure moves under this
 * vocabulary rather than beside it. `summarize` and `visual_plan` are what the
 * pipeline dispatches today, on two different models in two different jobs.
 * `label` and `summarize_and_plan` are the pair `idhazh.classify.calls` builds,
 * which lands behind a flag first and then becomes the only pair. A reading
 * that spans the flip needs all four names, or the step change in every series
 * reads as a regression rather than as the design change it is.
 */
export const CALL_KIND = ['summarize', 'visual_plan', 'label', 'summarize_and_plan'] as const;

export type CallKind = (typeof CALL_KIND)[number];

/**
 * Stable failure vocabulary for item-health rows.
 *
 * **Membership is one member per knob an operator turns, not one per gate.**
 * Four HTTP members answer to one fetch, because the fix for a 404 is not the
 * fix for a rate limit. `output_truncated` and `labels_truncated` are the two
 * output budgets, derived from two different grammars, for the same reason.
 */
export const FAILURE_CODE = ['not_attempted', 'robots_denied', 'robots_unreachable', 'blocked_address', 'http_client_error', 'http_rate_limited', 'http_server_error', 'network_error', 'no_text', 'no_title', 'too_short', 'not_prose', 'boilerplate', 'paywalled', 'unsupported_form', 'model_unreachable', 'model_refused', 'model_timed_out', 'context_exceeded', 'output_truncated', 'labels_truncated', 'bad_shape', 'length_out_of_range', 'copied_source', 'leaked_address', 'shard_out_of_time', 'unknown'] as const;

export type FailureCode = (typeof FAILURE_CODE)[number];

/** Whether the item reached the digest. */
export const ITEM_OUTCOME = ['ok', 'failed'] as const;

export type ItemOutcome = (typeof ITEM_OUTCOME)[number];

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
 * `retention.fold_month` sorts a month's groups by it. The order is free to
 * change: this is a `StrEnum`, so the wire value is the string and never the
 * position.
 */
export const ITEM_STAGE = ['plan', 'fetch', 'extract', 'summarize', 'visual', 'publish'] as const;

export type ItemStage = (typeof ITEM_STAGE)[number];

/** One planned item on one run, as the console is allowed to read it. */
export interface PublicTelemetryRow {
	version?: string;

	date: string;

	run_id: string;

	item_id: string;

	vertical: string;

	source_id: string;

	stage: ItemStage;

	outcome: ItemOutcome;

	code?: FailureCode | null;

	source_words?: number | null;

	summary_words?: number | null;

	/** Words in the extracted body before extract.truncation_cap_tokens cut it. A count of our own extraction, never the text, so it crosses on the same terms source_words always has. Empty on every row written before 2026-08-28, and empty means unknown rather than uncut. */
	source_words_before_cap?: number | null;

	/** Milliseconds spent fetching the page. Empty where fetch did not run. */
	fetch_ms?: number | null;

	/** Milliseconds spent extracting the body. Empty where extract did not run. */
	extract_ms?: number | null;

	/** Milliseconds the summarizer held the item, prompt and summary together. Empty where summarize did not run. */
	summarize_ms?: number | null;

	/** Milliseconds of that spent reading the prompt. Reading and writing run at different rates, so summarize_ms alone cannot separate them. */
	prefill_ms?: number | null;

	/** Milliseconds of that spent writing the summary. */
	decode_ms?: number | null;

	/** Tokens read. A rate needs its token count beside its milliseconds. */
	input_tokens?: number | null;

	/** Tokens written. */
	output_tokens?: number | null;

	/** Tokens the server answered from its prompt cache rather than reading again, added over every call the row records. Zero is a real answer here and means nothing was cached; empty means the server reported no cache figure at all. Where label_cached_tokens is filled, read the cache per call rather than here: a second call reusing the first call's prompt makes this non-zero on every item. */
	cached_tokens?: number | null;

	/** How many model calls the cells above add up over. Empty on every row published before 2026-09-12. It is what says whether the remainder - the total minus the first call - is one more call or several. */
	model_calls?: number | null;

	/** Which call ran first: summarize, visual_plan, label or summarize_and_plan. It moves when the call structure moves, so a step change in these series reads as the design change it is rather than as a regression. */
	label_kind?: CallKind | null;

	/** Milliseconds the first call spent reading its prompt. A duration and never a rate: a prompt token costs more the deeper into the context it sits, so a per-call tok/s cannot be compared with another call's. The item's blended rate is the one that composes. */
	label_prefill_ms?: number | null;

	label_decode_ms?: number | null;

	label_input_tokens?: number | null;

	label_output_tokens?: number | null;

	/** Prompt tokens the first call reused. Zero is the cold-slot answer and is a measurement; empty means no split was published for this row. */
	label_cached_tokens?: number | null;

	/** Which call ran second, or empty where the item made one call. The pair of kinds is what lets a reader see a two-call item as two calls rather than inferring it from a subtraction. */
	summary_kind?: CallKind | null;

	/** Milliseconds the second call spent reading its prompt. Small on a warm slot, because that prompt is the first call's prompt extended and the server answers the shared head from its cache. */
	summary_prefill_ms?: number | null;

	summary_decode_ms?: number | null;

	summary_input_tokens?: number | null;

	summary_output_tokens?: number | null;

	summary_cached_tokens?: number | null;

	/** How long the item waited before its worker started it - its own fetch and extract subtracted, because both are work rather than waiting. It sits outside item_total_ms rather than inside it. */
	queue_wait_ms?: number | null;

	/** Wall time of the label call, on our own stopwatch around the request. It is a slice of summarize_ms, never an addition to it, and label_prefill_ms plus label_decode_ms taken off it is the part the server did not claim. */
	label_ms?: number | null;

	/** Wall time of the summarize-and-plan call, on the same stopwatch. The other slice of summarize_ms. */
	summary_ms?: number | null;

	/** Wall time attributed to producing the visual plan. The plan is decoded inside the summarize-and-plan call, so this is a share of summary_ms and not a clock of its own - visual_plan_ms_is_estimate says which. */
	visual_plan_ms?: number | null;

	/** True where visual_plan_ms was apportioned out of the second call rather than timed on its own. An estimate that does not say it is one is the failure this column exists to prevent (Guardrail #10), and a page drawing the plan's share has to be able to mark it. */
	visual_plan_ms_is_estimate?: boolean | null;

	/** Wall time of the model-free faithfulness scorers. */
	faithfulness_ms?: number | null;

	/** Time the item spent waiting on the model server rather than being served. It is inside summarize_ms, so a rising wait with a flat decode rate is a queue and never a slower model. */
	model_wait_ms?: number | null;

	/** What the item cost, from the item starting to the item ending with queue_wait_ms taken out. The denominator every stage share on the page is taken against, and the reason the wait is excluded: the stage runs its fetch loop and its model loop in different orders, so the raw clock counts the whole queue ahead of each item and a column summed across a shard reported the shard's own duration once per item. */
	item_total_ms?: number | null;

	/** item_total_ms minus every named stage. **This is the one cell that can catch a regression in a step nobody named**, which is why it is published rather than derived by a reader who would have to know the list. It is signed on purpose: a negative value means two named stages overlapped, or two clocks disagreed, and clamping it to zero would hide exactly that. */
	stage_gap_ms?: number | null;

	/** Output tokens of the second call that belong to the visual plan rather than to the summary. Empty where the run asked for no plan. */
	visual_plan_tokens_written?: number | null;

	/** Prefill throughput of the label call, over the tokens the server really evaluated - the input minus whatever the cache already held. */
	label_prefill_tokens_per_s?: number | null;

	/** Decode throughput of the label call. */
	label_decode_tokens_per_s?: number | null;

	/** Prefill throughput of the summarize-and-plan call, over the tokens the server really evaluated. A warm slot answers almost the whole prompt from the cache, and that shows up in summary_cache_pct rather than here: this cell is about the machine, so counting the skipped tokens as work would make a cache hit read as a fast server. */
	summary_prefill_tokens_per_s?: number | null;

	/** Decode throughput of the summarize-and-plan call. */
	summary_decode_tokens_per_s?: number | null;

	/** The processor the runner reported, verbatim. Constant inside a shard and carried per row anyway, because the shard-grain counters that hold it are read at build time and never published for a browser to join against. It is 32 of the row's raw bytes and 1.54 of its gzipped bytes, so it is the first cell to drop if the published cap ever binds. */
	cpu_model?: string | null;

	/** Mean busy share of every processor over this item. Busy ticks over available ticks across the item, so it is a figure a reader can add up. */
	cpu_busy_pct?: number | null;

	/** One-minute load average when the item ended. */
	load_1m?: number | null;
}
