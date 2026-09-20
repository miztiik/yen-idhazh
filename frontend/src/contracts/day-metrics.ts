// Generated from `backend/idhazh/contracts/day_metrics.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * How the day's published items split across the confidence bands.
 *
 * Additive. Every published item carries exactly one band, so the three counts
 * partition the published set and a window's band counts are the daily counts
 * added up.
 */
export interface DayBands {
	/** Items the checker did not doubt. */
	high: number;

	medium: number;

	low: number;
}

/**
 * One numeric instrument aggregated over the day, split by how it combines.
 *
 * `count` and `total` are additive: sum both over a window and divide once for
 * the window's mean, which is a mean over items and never a mean of daily
 * means. The quartiles and the range are the day's own and are NOT additive - a
 * reader shows a daily quartile or recomputes an exact one from a value
 * population this record does not carry. A day that measured nothing carries the
 * count 0, the total 0.0 and no order statistic; empty is not zero.
 */
export interface DayDistribution {
	/** Items that carried a value. Additive. */
	count: number;

	/** The values added up. Additive. */
	total: number;

	/** The day's lower quartile. Not additive. */
	p25?: number | null;

	/** The day's median. Not additive. */
	p50?: number | null;

	/** The day's upper quartile. Not additive. */
	p75?: number | null;

	/** The day's smallest value. Not additive. */
	minimum?: number | null;

	/** The day's largest value. Not additive. */
	maximum?: number | null;
}

/**
 * What the candidate pass found on the day, and what the page drew from it.
 *
 * Every count is additive across days, so a window is a sum and never a re-walk.
 * The two rates a reader wants are not stored, because a rate is not additive:
 * `idhazh.evals.metrics` derives both from these counts, and the console does
 * the same arithmetic on the same cells.
 *
 * **Three classes and not five.** `comparative` and `processual` are claims
 * about how an article is written rather than about its numbers, so they have
 * no query yet and land with the diagram plan. `unclassified` is that gap
 * stated plainly rather than folded into `narrative`, which would report an
 * article carrying two figures as one carrying none.
 */
export interface DayExtraction {
	/** Planned items whose article carried text, so the pass ran on them. The denominator of the integrity rate, and never the published set. */
	items: number;

	/** Of those, the ones where every element span cut its own characters. */
	span_integrity_pass: number;

	/** Tier 1 elements the pass kept, added over the day. The extractor's own signal: it falls when the patterns stop matching, whatever the planner does. */
	elements_found: number;

	/** Items whose numbers could have made a chart. */
	chartable: number;

	/** Items stating no quantity at all. */
	narrative: number;

	/** Items with quantities but no unit shared widely enough. */
	unclassified: number;

	/** Chartable items that reached the day's published set. The denominator of the unused rate: an item that never published cannot carry a chart, and counting it would blame the planner for a fetch that failed. */
	chartable_published: number;

	/** Of those, the ones a reader can see a rendered chart on. */
	chartable_charted: number;
}

/**
 * One measured eval-row column, aggregated over the day.
 *
 * `column` names the eval-row column (an entry from `INSTRUMENT_COLUMNS`); the
 * reducer joins on it. `stat` carries the aggregate, additive and non-additive
 * parts kept apart by `DayDistribution`.
 */
export interface DayInstrument {
	column: string;

	stat: DayDistribution;
}

/**
 * How close the day's own item vectors sat to the committed label vectors.
 *
 * **Neither end of this is better than the other, and nothing here is a
 * grade.** The cosine between a 384-dimension int8 item vector and a label
 * vector is uncalibrated - one encodes a news sentence and the other a
 * definitional one - so a fixed threshold would be a number somebody picked
 * (Carmack). Only a change says anything, and a day file cannot hold a change:
 * it holds the level, and a reducer over a window is what reads a change out
 * of two of them.
 *
 * **No label is picked and no per-item value survives.** The closest label is
 * computed and thrown away; `nearest` is the aggregate and nothing anywhere
 * says what one item scored. A verdict that reaches no reader and selects
 * nothing to publish is not a `CLAUDE.md` section 0a deviation, and the
 * moment either half of that stopped being true this would need everything a
 * classifier needs.
 *
 * **The two rulers travel with the reading**, because a number is only
 * comparable against another number taken under the same ones. `taxonomy_digest`
 * pins the words that were encoded; `encoder_ref` pins the weights that
 * encoded them. Two different values of either inside one window is a step in
 * the ruler and not a change in the days, so a reducer refuses the comparison
 * rather than drawing it.
 */
export interface DayLabelSimilarity {
	/** The digest of the label sentences the vectors were built from, exactly as `config/taxonomy-vectors.bin` carries it. A vocabulary edit moves it. */
	taxonomy_digest: string;

	/** Which weights encoded both sides, as `<embedder id>/<encoder directory>`. The id alone does not move when the weights move, so it is not an encoder identity on its own. */
	encoder_ref: string;

	/** The day's distribution of each item's cosine to its closest label vector. `count` and `total` are additive, so a window mean is a sum over items and never a mean of daily means; `count` is also the denominator, and it moves on its own when the share of items the encoder could read moves. */
	nearest: DayDistribution;
}

/**
 * Why each doubted item did not reach the top band.
 *
 * Additive. A `high` item has no reason; every `medium` or `low` item falls
 * into exactly one bucket here, so the six counts partition the doubted set.
 * `unattributed` is a doubted item the checker recorded no reason for - a real
 * category the Model page counts separately, not the same fact as `not_scored`
 * (which is a recorded reason meaning no faithfulness score exists).
 */
export interface DayReasons {
	unsupported_number: number;

	not_scored: number;

	lead_missing: number;

	hedge_dropped: number;

	faithfulness: number;

	/** Doubted, with no band_reason on the published item. Never source text. */
	unattributed: number;
}

/**
 * One source's day, counted so the reader can rank and combine without a re-walk.
 *
 * Every count is additive within a source: sum a source's `published` over a
 * window for its window total. The reader combines days by keying on
 * `source_id`, then re-ranks - the ranking itself is non-additive, which is why
 * the whole per-source list is stored rather than a daily top list.
 */
export interface DaySource {
	source_id: string;

	/** Items this source contributed to the day. */
	published: number;

	/** Of those, the ones not in the top band. */
	doubted: number;

	/** Of those, the ones extract cut at the cap. */
	truncated: number;
}

/**
 * One pipeline stage's wall-clock over the day's items.
 *
 * `timed` and `sum_ms` are additive - a window's total stage time is the daily
 * totals added up, and a mean is `sum_ms` over `timed`. The three percentiles
 * are the day's own and are NOT additive: a median of daily medians is not the
 * window's median (the Model page's own caveat). A reader shows a daily
 * percentile or recomputes an exact one from a value population this record
 * does not carry. Empty percentiles are not zero: a stage that timed nothing
 * carries none of the four figures.
 */
export interface DayStageTiming {
	stage: ItemStage;

	/** Items that recorded milliseconds at this stage. Additive. */
	timed: number;

	/** Every timed item added up. Additive. */
	sum_ms?: number | null;

	/** The day's median. Not additive. */
	p50_ms?: number | null;

	/** The day's 90th percentile. Not additive. */
	p90_ms?: number | null;

	/** The day's slowest item. Not additive. */
	max_ms?: number | null;
}

/**
 * The model's token clock for the day, so a rate survives without a runtime log.
 *
 * Every field is additive: sum the milliseconds and the token counts over a
 * window and divide once for the window's prefill and decode rates. Reading the
 * prompt and writing the summary run at different rates, so their milliseconds
 * are kept apart. Null on the day facts when no item timed a token.
 */
export interface DayThroughput {
	/** Items that recorded any token count. The denominator. */
	items: number;

	/** Milliseconds reading prompts, added over the day. */
	prefill_ms: number;

	/** Milliseconds writing summaries, added over the day. */
	decode_ms: number;

	input_tokens: number;

	output_tokens: number;

	cached_tokens: number;
}

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

/** Everything a run settled about one published day, for a later reducer to read. */
export interface DayMetrics {
	version?: string;

	date: string;

	/** The ordinal of the newest run that published this day - DigestDay.runs[-1].n, the same number introduced_by_run counts up. A record whose revision is behind the day's own newest run is stale and must be rewritten (Fowler). */
	revision: number;

	/** Runs that published this day. Additive. */
	runs: number;

	/** The model that wrote the day's summaries. Not additive - a per-day attribute a reader compares against the next day to find a model change (finding 70). */
	model_id: string;

	/** Items in the day's published set. Additive. */
	items_published: number;

	/** Items the day's runs planned. Additive. */
	items_planned: number;

	/** Planned items that never reached the digest. Additive. */
	items_failed: number;

	/** Visuals that rendered on the day. Additive. */
	visuals_rendered: number;

	/** Published items extract cut at the truncation cap (finding 68). Additive. */
	items_truncated: number;

	/** Published items the checker gave a faithfulness score. Additive. */
	summaries_scored: number;

	/** Scored items whose identical inputs produced different words. Additive. */
	determinism_violations: number;

	/** Scored items whose source read like page furniture. Additive. */
	extraction_suspect: number;

	/** Distinct sources that contributed a published item. Not additive - two days may share a source, so a reader combines the `sources` list rather than adding this across days. Equal to the length of `sources`. */
	sources_present: number;

	/** Distinct addresses the feeds offered the day, before what it had published or failed on (finding 62). Not additive - two days may repeat an address, so a reader treats a sum as an upper bound. Null on a day that recorded none. */
	addresses_considered?: number | null;

	bands: DayBands;

	reasons: DayReasons;

	/** The day's token clock, or null when no item timed a token. Additive parts. */
	throughput?: DayThroughput | null;

	/** One entry per pipeline stage the day timed (findings 75, note 33). */
	stage_timing?: DayStageTiming[];

	/** One entry per measured eval-row column (finding 74, note 38). */
	instruments?: DayInstrument[];

	/** One entry per source that published (findings 67, 68, 73). */
	sources?: DaySource[];

	/** What the candidate pass found and what the page drew from it, or null on a record written before 2026-09-08. Additive parts. */
	extraction?: DayExtraction | null;

	/** How close the day's item vectors sat to the committed label vectors, or null when the day carried no vectors, the label vectors are not committed in this checkout, or the record was written before 2026-09-13. Not a grade and not a verdict: neither end of it is better than the other. */
	label_similarity?: DayLabelSimilarity | null;
}
