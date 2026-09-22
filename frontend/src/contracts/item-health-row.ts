// Generated from `backend/idhazh/contracts/item_health.py` by `python -m idhazh.contracts.export`.
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
 * What one article's numbers say it could carry, and nothing else.
 *
 * **Three classes, and the count is the point.** The visual programme names
 * five, and only two of them are a question about numbers. `comparative` and
 * `processual` are claims about how an article is written, so they have no
 * query yet and land with the diagram plan. Anything reporting per class before
 * then names three and says so, rather than letting a reader take three for the
 * whole taxonomy.
 *
 * The query rests on the element table's Tier 1 fields alone - `kind`, `value`
 * and `unit` - so it is byte-exact and carries no model judgement.
 * `idhazh.elements.classify` is the query; this is its vocabulary, and
 * `docs/architecture/extraction/elements.md` is the page that owns it.
 *
 * **It is declared here rather than beside the element contract**, with the
 * other closed vocabularies this census row carries, because
 * `contracts/element.py` sits above `contracts/article.py`, which sits above
 * this module. A label a census row persists has to be declared at or below the
 * row's own level, and this is the level.
 */
export const ELEMENT_CLASS = ['chartable', 'narrative', 'unclassified'] as const;

export type ElementClass = (typeof ELEMENT_CLASS)[number];

/**
 * Stable failure vocabulary for item-health rows.
 *
 * **Membership is one member per knob an operator turns, not one per gate.**
 * Four HTTP members answer to one fetch, because the fix for a 404 is not the
 * fix for a rate limit. `output_truncated` and `labels_truncated` are the two
 * output budgets, derived from two different grammars, for the same reason.
 */
export const FAILURE_CODE = ['not_attempted', 'robots_denied', 'robots_unreachable', 'blocked_address', 'http_client_error', 'http_rate_limited', 'http_server_error', 'network_error', 'no_text', 'no_title', 'too_short', 'not_prose', 'boilerplate', 'contaminated', 'paywalled', 'unsupported_form', 'model_unreachable', 'model_refused', 'model_timed_out', 'context_exceeded', 'output_truncated', 'labels_truncated', 'bad_shape', 'length_out_of_range', 'copied_source', 'leaked_address', 'shard_out_of_time', 'unknown'] as const;

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
 * `retention.compact_month` sorts a month's groups by it. The order is free to
 * change: this is a `StrEnum`, so the wire value is the string and never the
 * position.
 */
export const ITEM_STAGE = ['plan', 'fetch', 'extract', 'summarize', 'visual', 'publish'] as const;

export type ItemStage = (typeof ITEM_STAGE)[number];

/**
 * Which workflow job produced a row.
 *
 * Ours to name, so it is a closed set. Every other identifier on a host row is
 * a string the machine chose and cannot be one - see
 * `docs/reference/host-metrics.md`. Refusing anything else is what stops a typo
 * becoming a job nobody can group by.
 *
 * Every value is a job's own id in its workflow file, lowercase, so a reader
 * goes from a row to the steps that wrote it with no lookup table in between.
 * A display name would drift from the thing it identifies.
 *
 * It sits here, at the bottom of the contract graph, because three ledgers and
 * a filename grammar all name a job and none of them owns the vocabulary.
 *
 * **`visuals` is here for the rows and not for a job.** `digest.yml` ran one
 * until 2026-09-13, when the small model, its job and its flag were retired
 * together. Six committed counters rows still carry the value, and a member
 * with no producer left is the only thing that can read them back.
 *
 * **`decide` is here for a filename and not for a column.** `validate.yml`'s
 * gate job writes the validation ledger's segment, and the segment grammar
 * names its writer from this set - so the job belongs here. No row of the three
 * ledgers that carry a `job` column can hold it: that job stands no server up,
 * records no machine and reads no item. Their generated schemas list it because
 * one enum answers "which workflow job" for the whole repository, which is why
 * none of the three is version-stamped for it - a stamp says a shape moved, and
 * theirs did not.
 */
export const SERVER_JOB = ['plan', 'work', 'assemble', 'visuals', 'runtime', 'decide'] as const;

export type ServerJob = (typeof SERVER_JOB)[number];

export const SOURCE_FORM = ['article', 'abstract'] as const;

export type SourceForm = (typeof SOURCE_FORM)[number];

/** The tier IS the ranking weight (docs/architecture/sources/discovery.md). */
export const SOURCE_TIER = [1, 2, 3] as const;

export type SourceTier = (typeof SOURCE_TIER)[number];

/**
 * Which clock the time on an item came from.
 *
 * `rank.appeared_at` prefers the feed's own date and falls back to when we
 * first saw the address. Both answers used to land in one field, so nothing
 * downstream could tell them apart - and the fallback is the one a reader
 * would want flagged, because it is our clock and not the publisher's.
 */
export const TIME_SOURCE = ['feed', 'first_seen', 'unknown'] as const;

export type TimeSource = (typeof TIME_SOURCE)[number];

/** One item, one run, one terminal outcome. */
export interface ItemHealthRow {
	version?: string;

	date: string;

	run_id: string;

	item_id: string;

	url_key: string;

	canonical_url: string;

	vertical: string;

	source_id: string;

	stage: ItemStage;

	outcome: ItemOutcome;

	code?: FailureCode | null;

	http_status?: number | null;

	source_chars?: number | null;

	source_words?: number | null;

	summary_words?: number | null;

	/** Our own one-line reason, on any failed row. Never source text (Guardrail #11). Two hundred characters used to be the cap and it cut the exception message off before the part that said what broke, so a person debugging a failure had to reproduce it to read it. */
	detail?: string | null;

	fetch_ms?: number | null;

	extract_ms?: number | null;

	summarize_ms?: number | null;

	prefill_ms?: number | null;

	decode_ms?: number | null;

	input_tokens?: number | null;

	output_tokens?: number | null;

	cached_tokens?: number | null;

	/** Words in the extracted body before extract.truncation_cap_tokens cut it, taken from Article.source_word_count. source_words is the same counter after the cut, so source_words_before_cap > source_words is the cut and nothing else. A count, never the text. Null before 2026-08-28. */
	source_words_before_cap?: number | null;

	/** Which worker of the run produced this row, numbered the way stages.common.shard_of numbers them. state/host-fingerprint/ carries the same number at the job grain, so a per-shard rate can be read against the machine that ran it. Null means no worker claimed the row: assemble writes the day's census from one job and cannot know which machine an item was for, and every row written before 2026-08-30 predates the column. Never read an empty cell as shard 0. */
	shard?: number | null;

	/** Which workflow job's machine took this row's readings - never which job wrote the row. With `shard` this is the whole of `HOST_FINGERPRINT_KEY`, so an item resolves to exactly one host record. Null on the same terms as `shard`: assemble writes the day's census and cannot know whose machine an item ran on, and every row written before this column predates it. */
	job?: ServerJob | null;

	/** Did every element span cut its own characters out of the article text? Empty means the pass never ran, because the item carried no text. False means it ran and the table would not re-slice, which degrades this item alone. The two cells after this one are filled only when it is true. */
	span_integrity?: boolean | null;

	/** Tier 1 elements the candidate pass kept for this article, after the rule that settles two passes claiming one span and after elements.max_per_article. A count, never the elements. Null before 2026-09-08 and whenever span_integrity is not true. */
	elements_found?: number | null;

	/** What the article's own numbers say it could carry: chartable, narrative, or unclassified. Three classes and not five - the other two are claims about language and have no query yet. Null on the same terms as elements_found. */
	element_class?: ElementClass | null;

	/** How many model calls this row records the cost of. Empty on every row written before 2026-09-12, which recorded a total and no split. It is the count of filled call slots below, so a reader of the narrower published projection can tell what the remainder it derives covers. */
	model_calls?: number | null;

	/** Which call the stage made first. Empty where no split was recorded. */
	label_kind?: CallKind | null;

	label_prefill_ms?: number | null;

	label_decode_ms?: number | null;

	label_input_tokens?: number | null;

	label_output_tokens?: number | null;

	/** Prompt tokens the first call reused. Zero here is the cold-slot answer and is a measurement; empty means no split was recorded at all. */
	label_cached_tokens?: number | null;

	/** Which call the stage made second, or empty where it made one. */
	summary_kind?: CallKind | null;

	summary_prefill_ms?: number | null;

	summary_decode_ms?: number | null;

	summary_input_tokens?: number | null;

	summary_output_tokens?: number | null;

	summary_cached_tokens?: number | null;

	/** The cap that cut this row, taken from Article.truncated_at_tokens. Filled only where the cut happened, so it is non-null exactly where source_words_before_cap > source_words. It says which cap did the cutting, which the pair of word counts cannot: they say a cut happened and nothing about the setting behind it. Never re-derive this from the configured cap and the tokens-a-word ratio - both move, and the row was written under the pair in force that day. Null before 2026-09-14 and on every uncut row. */
	truncation_cap_tokens?: number | null;

	/** The total the ranker ordered this item by. Empty on a row written before 2026-09-15 and on any item the ranker never scored. */
	selection_score?: number | null;

	/** The source-authority term of selection_score. */
	authority_score?: number | null;

	/** The tier term of selection_score. */
	tier_score?: number | null;

	/** The configured weight of the feed this item came from. */
	feed_weight?: number | null;

	/** The feed's own recorded reliability at the moment of the run, 0 to 1. Read from feed health, so a later read of feed health cannot answer what the ranker actually used on the day. */
	feed_reliability?: number | null;

	/** The lens term of selection_score. */
	lens_bonus?: number | null;

	/** The recency term of selection_score. */
	recency_bonus?: number | null;

	/** The carriage term of selection_score. */
	carriage_step?: number | null;

	/** The watchlist term of selection_score. */
	watchlist_bonus?: number | null;

	/** How many runs have carried this item forward without publishing it. */
	carried_by?: number | null;

	/** Did a watchlist entry match this item? */
	watchlist_hit?: boolean | null;

	/** Did this item reach the published front page? */
	on_front_page?: boolean | null;

	/** The source's tier at the moment of the run. */
	tier?: SourceTier | null;

	/** The source's form at the moment of the run. */
	source_form?: SourceForm | null;

	/** The time the item carries, from whichever clock time_source names. */
	published_at?: string | null;

	/** Which clock published_at came from - feed, first_seen or unknown. A closed set the pipeline mints, so the column is the enum and a producer selects a member rather than spelling one. A clock name nobody declared is refused here rather than folded into a token, which is the difference between a value this project can act on and one it can only read. Null where no run recorded the choice. */
	time_source?: TimeSource | null;

	/** When the worker picked this item up. */
	item_started_at?: string | null;

	/** When the worker wrote this row. */
	item_ended_at?: string | null;

	/** This item's position inside its shard, counting from zero. It is what makes a cold first item legible as a cold first item rather than as a slow one, because the prefix cache is empty only at index 0. */
	item_index?: number | null;

	/** How many items that shard was given. */
	shard_item_count?: number | null;

	/** How long the item waited before its worker started it - its own fetch and extract subtracted, because both are work rather than waiting. Discounted from item_total_ms, so a shard's items do not each count the queue ahead of them. */
	queue_wait_ms?: number | null;

	/** The connect half of fetch_ms. */
	fetch_connect_ms?: number | null;

	/** Time to the first byte of the response body. */
	fetch_ttfb_ms?: number | null;

	/** Time spent fetching or waiting on robots.txt. */
	robots_ms?: number | null;

	/** How many times the fetch was retried. */
	retry_count?: number | null;

	/** Total wall time spent inside retries and their backoff. */
	retry_total_ms?: number | null;

	/** Wall time of the label call: our own stopwatch around the request, so the wait is inside it. Subtract label_prefill_ms and label_decode_ms to get what the server did not claim for itself - transport, and any queue. */
	label_ms?: number | null;

	/** Wall time of the summarize-and-plan call, on the same stopwatch. */
	summary_ms?: number | null;

	/** Wall time attributed to producing the visual plan. The plan is decoded inside the summarize-and-plan call, so this is an apportionment and not a separate clock - visual_plan_ms_is_estimate says which. */
	visual_plan_ms?: number | null;

	/** True where visual_plan_ms was apportioned out of the second call rather than timed on its own. An estimate that does not say it is one is the failure this column exists to prevent (Guardrail #10). */
	visual_plan_ms_is_estimate?: boolean | null;

	/** Wall time of the model-free faithfulness scorers. */
	faithfulness_ms?: number | null;

	/** Time the item spent waiting on the model server rather than being served. */
	model_wait_ms?: number | null;

	/** What the item cost, from item_started_at to item_ended_at with queue_wait_ms taken out. The stage fetches every item and then runs the model over them in a different order, so the raw wall clock counts the whole queue ahead of each item and the column summed to the shard's own duration once per item. */
	item_total_ms?: number | null;

	/** item_total_ms minus every named stage. **This is the one column that can catch a regression in a stage nobody named**, which is why it is recorded rather than derived at read time by a reader who would have to know the list. It is signed on purpose: a negative value means two named stages overlapped, or two clocks disagreed, and silently clamping it to zero would hide exactly that. */
	stage_gap_ms?: number | null;

	/** Output tokens of the second call that belong to the visual plan rather than to the summary. Null where the run asked for no plan. */
	visual_plan_tokens_written?: number | null;

	/** label_cached_tokens as a percentage of label_input_tokens. Recorded rather than derived so a reader pooling rows does not have to weight the ratio itself and get it wrong. */
	label_cache_pct?: number | null;

	/** summary_cached_tokens as a percentage of summary_input_tokens. */
	summary_cache_pct?: number | null;

	/** Which llama-server prefix-cache slot served this item, from id_slot on the reply to its FIRST model call. The row holds one set of these three columns for a stage that makes two calls, and the first call is the only one whose slot was last touched by the item before this one. Null where the reply named no slot, which is not the same as slot 0. */
	slot_id?: number | null;

	/** What that slot held once the item's first call had been prefilled, from tokens_cached on the same reply. It is where the item's second call starts from, and then the next item. label_cached_tokens is the other half of the pair and answers the opposite question: what the call read back out. */
	kv_tokens_at_start?: number | null;

	/** Did the item's first call read anything at all out of the slot? Taken from the same timings.cache_n that label_cached_tokens is, so the boolean and the count cannot disagree about one reply. The second call is excluded on purpose: its prompt IS the first one's extended, so it reuses a prefix on every row and says nothing about the item before it. Null where the reply carried no cache_n at all. */
	prefix_shared_with_previous?: boolean | null;

	/** Prefill throughput of the label call, over the tokens the server really evaluated - label_input_tokens minus label_cached_tokens. Counting the cached ones as work makes this and label_cache_pct the same number twice, and reads as a fast server rather than as a cache hit. */
	label_prefill_tokens_per_s?: number | null;

	/** Decode throughput of the label call. */
	label_decode_tokens_per_s?: number | null;

	/** Prefill throughput of the summarize-and-plan call, over the tokens the server really evaluated. This call reuses the label call's prompt almost whole, so the two readings differ by two orders of magnitude: on 2026-09-14 one item read 787 tokens a second over the whole prompt and 8.4 over the 52 tokens that were new. */
	summary_prefill_tokens_per_s?: number | null;

	/** Decode throughput of the summarize-and-plan call. */
	summary_decode_tokens_per_s?: number | null;

	/** Why the label decode stopped, as the server reported it - stop, length, and whatever else the runtime mints. A token and not an enum: the vocabulary belongs to llama-server rather than to this project, and a row that could not be written because the runtime added a reason would lose the whole item over a label. Null where the reply named no reason at all, which is not the same fact as a clean stop. */
	label_finish_reason?: string | null;

	/** Why the summarize-and-plan decode stopped, on the same terms. */
	summary_finish_reason?: string | null;

	/** Did a cut reply have to be recovered before it parsed? A run where this turns true across many items is a budget that no longer fits. */
	recovered?: boolean | null;

	/** The CPU the runner reported, verbatim. */
	cpu_model?: string | null;

	/** The share of the item's processor time that was our own work: busy ticks over available ticks across the whole item, differenced from two reads of /proc/stat. Time the host gave another tenant is taken out and recorded in cpu_steal_pct instead. A row written before 2026-09-20 counted that time as ours, so the two sides of the change are not comparable and nothing can recover the split for a row already written. */
	cpu_busy_pct?: number | null;

	/** Peak CPU busy over the item. */
	cpu_busy_max?: number | null;

	/** Trough CPU busy over the item. */
	cpu_busy_min?: number | null;

	/** The share of the item's processor time the host gave to another tenant, from the same /proc/stat difference cpu_busy_pct is taken from. Neither ours nor idle, which is why it is counted apart from both. Null where the kernel's cpu line stops short of the field: a kernel that does not account stolen time has not told us there was none. */
	cpu_steal_pct?: number | null;

	/** One-minute load average when the item ended. */
	load_1m?: number | null;

	/** Resident memory of the model server when the item ended. */
	llama_rss_bytes?: number | null;

	/** The part of the model server's resident set that is not file-backed, as `RssAnon` in `/proc/<pid>/status` reported it. The weights are mapped from a file, so they count inside llama_rss_bytes and inside the page cache at the same time and the two may not be added; this cell can double-count with neither, which is what lets a reader split the machine's memory up and have the parts close. */
	llama_rss_anon_bytes?: number | null;

	/** The model server's high-water resident memory, as `VmHWM` in `/proc/<pid>/status` reported it - the higher of one reading when the item opened and one when it closed. It covers the server's whole life up to that moment, not this item. And it can read lower than an earlier item's: the kernel prints the larger of the current resident set and a stored mark it refreshes only when the process itself gives memory back, so a page the kernel reclaims takes the figure down with it. */
	llama_rss_peak_bytes?: number | null;

	/** How many pages the model server had to wait for off disk across this item, differenced from `/proc/<pid>/stat` at either end. A count over the window and never a rate, because the row already carries the interval. It is the one reading that can see the kernel taking the weights back: those pages are file-backed, so they leave an RSS figure and touch no swap counter on the way out. Null where either end could not be read, and null is not zero. */
	llama_major_faults?: number | null;

	/** Resident memory of the worker process when the item ended. */
	python_rss_bytes?: number | null;

	/** The part of the worker process's resident set that is not file-backed, on the same terms as the model server's. */
	python_rss_anon_bytes?: number | null;

	/** The model this run summarised with. */
	model_id?: string | null;

	/** The quantisation of those weights. */
	model_quantisation?: string | null;

	/** The context window the server was started with. */
	n_ctx_configured?: number | null;

	/** How many prefix-cache slots the server was started with. */
	n_parallel?: number | null;

	/** Threads the server was given. */
	n_threads?: number | null;

	/** The server's prefill batch size. */
	n_batch?: number | null;

	/** Was the server told to lock the weights in memory - `inference.load_mode`, which llama-server spells `-lm`? False is the ordinary setting and says the kernel may reclaim them, which is the state llama_major_faults exists to catch. Recorded because a surface that states the weights are not pinned with nothing on the row to check it against starts lying the day somebody sets the flag. Null on a row written before the column. */
	weights_pinned?: boolean | null;

	/** The output budget the label call ran under. */
	label_budget_tokens?: number | null;

	/** The output budget the summarize-and-plan call ran under. */
	summary_budget_tokens?: number | null;

	/** Did this run ask the second call for a visual plan? */
	run_visual_decision?: boolean | null;

	/** The sampling temperature both calls ran at. */
	temperature?: number | null;

	/** The field a schema refusal named, where the failure was a refusal. Our own field name and never fetched text (Guardrail #11). */
	failed_field?: string | null;

	/** The rule that refused it, named by our own validator. */
	failed_rule?: string | null;

	/** Memory the kernel says a new allocation could have when the item ended, from /proc/meminfo MemAvailable. This is headroom; an RSS mark is not. */
	os_mem_available_bytes?: number | null;

	/** What the machine has, from /proc/meminfo MemTotal. Constant within a job; recorded per item so a row means something on its own. */
	os_mem_total_bytes?: number | null;

	/** Page cache when the item ended, from /proc/meminfo Cached. Most of the model weights sit here, so a drop is the kernel evicting what the next item has to read again. */
	os_mem_cached_bytes?: number | null;

	/** Swap left when the item ended, from /proc/meminfo SwapFree. A fall here is the machine in trouble before the cgroup kill. */
	os_swap_free_bytes?: number | null;

	/** Swap this machine has, from /proc/meminfo SwapTotal. Constant inside a job, so it is read paired with os_swap_free_bytes off one row and never as a distribution of its own. Recorded because a free figure of zero says 'no swap on this box' and 'swap fully consumed' equally, and only the second is an emergency. */
	os_swap_total_bytes?: number | null;

	/** Lowest MemAvailable seen while the model was working on this item, from /proc/meminfo sampled by that item's own watch. The closest this item took the machine to its limit. */
	os_mem_available_min_bytes?: number | null;
}
