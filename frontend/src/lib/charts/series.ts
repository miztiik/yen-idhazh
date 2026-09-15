import { dayMonth } from '../format';
import { daysBetween, daysInWindow, type TimeWindow } from './viewport';

/** The published projection's header, in `PUBLIC_COLUMNS` order.
 *
 * `backend/idhazh/publish_telemetry.py` owns the list. This is the reader's
 * copy of it, and `parseTelemetryCsv` refuses a file whose header disagrees.
 */
export const TELEMETRY_COLUMNS = [
	'date',
	'run_id',
	'item_id',
	'vertical',
	'source_id',
	'stage',
	'outcome',
	'code',
	'source_words',
	'summary_words',
	'source_words_before_cap',
	'fetch_ms',
	'extract_ms',
	'summarize_ms',
	'prefill_ms',
	'decode_ms',
	'input_tokens',
	'output_tokens',
	'cached_tokens',
	'model_calls',
	'label_kind',
	'label_prefill_ms',
	'label_decode_ms',
	'label_input_tokens',
	'label_output_tokens',
	'label_cached_tokens',
	'summary_kind',
	'summary_prefill_ms',
	'summary_decode_ms',
	'summary_input_tokens',
	'summary_output_tokens',
	'summary_cached_tokens',
	'queue_wait_ms',
	'label_ms',
	'summary_ms',
	'visual_plan_ms',
	'visual_plan_ms_is_estimate',
	'faithfulness_ms',
	'model_wait_ms',
	'item_total_ms',
	'stage_gap_ms',
	'visual_plan_tokens_written',
	'label_prefill_tokens_per_s',
	'label_decode_tokens_per_s',
	'summary_prefill_tokens_per_s',
	'summary_decode_tokens_per_s',
	'cpu_model',
	'cpu_busy_pct',
	'load_1m'
] as const;

export type TelemetryColumn = (typeof TELEMETRY_COLUMNS)[number];

export interface TelemetryRow {
	date: string;
	run_id: string;
	item_id: string;
	vertical: string;
	source_id: string;
	stage: string;
	outcome: string;
	code: string;
	/** Words the model was given: the body after the cap cut it. */
	source_words: number | null;
	summary_words: number | null;
	/** Words the body held before the cap. Null on every run before 2026-08-28,
	 * and on any run the cap never fired for. */
	source_words_before_cap: number | null;
	/** Milliseconds the fetch took. Null where the stage never ran. */
	fetch_ms: number | null;
	/** Milliseconds the extract took. Null where the stage never ran. */
	extract_ms: number | null;
	/** Milliseconds the summarizer held the item. Null where it never ran. */
	summarize_ms: number | null;
	/** The part of `summarize_ms` spent reading the prompt. */
	prefill_ms: number | null;
	/** The part of `summarize_ms` spent writing the summary. */
	decode_ms: number | null;
	input_tokens: number | null;
	output_tokens: number | null;
	/** Tokens the server answered from its prompt cache, added over every call the
	 * row records. Zero means nothing was cached; null means the server reported no
	 * figure at all. Ask `label_cached_tokens` instead when the question is whether
	 * the cache answered: a second call reusing the first call's prompt makes this
	 * non-zero on every item. */
	cached_tokens: number | null;
	/** How many model calls the totals above add up over. Null on every row
	 * published before 2026-09-12. It is what says how many of the two call slots
	 * below are filled. */
	model_calls: number | null;
	/** Which call ran first: `summarize`, `visual_plan`, `label` or
	 * `summarize_and_plan`. Empty where no split was published. */
	label_kind: string;
	/** The first call's own share of each total. Both calls are published now, so
	 * nothing here has to be derived by subtracting: the writer refuses a row whose
	 * totals are not the sum of its calls.
	 * `label_prefill_ms` is a duration and never a rate - a prompt token costs more
	 * the deeper into the context it sits, so a per-call tok/s cannot be compared
	 * with another call's. */
	label_prefill_ms: number | null;
	label_decode_ms: number | null;
	label_input_tokens: number | null;
	label_output_tokens: number | null;
	/** Prompt tokens the first call reused. Zero is the cold-slot answer and is a
	 * measurement; null means no split was published for this row. */
	label_cached_tokens: number | null;
	/** Which call ran second, or empty where the item made one call. */
	summary_kind: string;
	/** The second call's own share of each total. Small prefill on a warm slot,
	 * because that prompt is the first call's prompt extended. */
	summary_prefill_ms: number | null;
	summary_decode_ms: number | null;
	summary_input_tokens: number | null;
	summary_output_tokens: number | null;
	summary_cached_tokens: number | null;
	/** How long the item waited before its worker started it, its own fetch and
	 * extract subtracted. Outside `item_total_ms`, so it is not a band: the stage
	 * fetches every item and then runs the model over them in a different order,
	 * and counting the wait would charge each item for the queue ahead of it. */
	queue_wait_ms: number | null;
	/** Wall time of the label call. A slice of `summarize_ms`, never an addition
	 * to it - which is why neither this nor `summary_ms` is one of the stages
	 * `stage_gap_ms` subtracts. */
	label_ms: number | null;
	/** Wall time of the summarize-and-plan call. The other slice. */
	summary_ms: number | null;
	/** Wall time attributed to the visual plan, which is decoded inside the
	 * second call. A share of `summary_ms` and not a clock of its own. */
	visual_plan_ms: number | null;
	/** `'True'` where `visual_plan_ms` was apportioned rather than timed. A page
	 * that draws the plan's share has to be able to mark it as an estimate. */
	visual_plan_ms_is_estimate: string;
	/** Wall time of the model-free faithfulness scorers. */
	faithfulness_ms: number | null;
	/** Time spent waiting on the model server rather than being served. Inside
	 * `summarize_ms`, so a rising wait with a flat decode rate is a queue. */
	model_wait_ms: number | null;
	/** What the item cost, from the item starting to the item ending with
	 * `queue_wait_ms` taken out. The denominator every stage share is taken
	 * against. */
	item_total_ms: number | null;
	/** `item_total_ms` minus fetch, extract, summarize and faithfulness. The only
	 * cell that can catch a regression in a step nobody named, and signed on
	 * purpose: negative means two clocks overlapped. */
	stage_gap_ms: number | null;
	/** Output tokens of the second call that belong to the plan, not the summary. */
	visual_plan_tokens_written: number | null;
	/** Per-call throughput. A total cannot say whether the model slowed or the
	 * work grew; a rate beside the tokens written can. */
	label_prefill_tokens_per_s: number | null;
	label_decode_tokens_per_s: number | null;
	summary_prefill_tokens_per_s: number | null;
	summary_decode_tokens_per_s: number | null;
	/** The processor the runner reported. A throughput number with no machine
	 * beside it is not a measurement. Empty where the run recorded none. */
	cpu_model: string;
	/** Mean busy share of every processor over this item. */
	cpu_busy_pct: number | null;
	/** One-minute load average when the item ended. */
	load_1m: number | null;
}

/** One mark on the compression plot, derived in the browser from a telemetry
 * row. Never inlined into the page and never persisted anywhere. */
export interface CompressionPoint {
	date: string;
	item_id: string;
	/** The article's own length, before anything cut it. */
	source_words: number;
	/** What the model was given, after the cut. Absent where nothing was cut, so
	 * the one field and `truncation_flagged` cannot end up disagreeing about
	 * whether this article lost any text. */
	source_seen_words?: number;
	summary_words: number;
	truncation_flagged: boolean;
}

/** One day's rows that the plot could not place, and how many.
 *
 * Counted per date rather than listed per row: the sentence needs a number for
 * whatever window is open, and a date with a count carries that in a dozen
 * bytes where one entry per row carried eleven bytes each.
 */
export interface UnplottedDay {
	date: string;
	n: number;
}

/** The rows this plot is about: an item that reached a reader.
 *
 * `backend/idhazh/telemetry.py` writes `publish` + `ok` for exactly two ends -
 * an item with a summary, and an article the extractor kept but never asked the
 * model about. The second has no summary length, so `placeRow` drops it. Every
 * other row is a failure or an item the run threw away, and neither is an
 * article whose summary anyone can measure.
 */
export function published(row: TelemetryRow): boolean {
	return row.stage === 'publish' && row.outcome === 'ok';
}

/** Where one telemetry row sits on the compression plot, or why it sits nowhere.
 *
 * One decision, three outcomes, because the plot and the sentence under it read
 * the same answer. Counting the unplaced rows anywhere else would let the two
 * disagree about the same row on the same day.
 */
export type Placed =
	| { kind: 'point'; point: CompressionPoint }
	| { kind: 'no-length'; date: string }
	| { kind: 'no-summary' };

/** The article's own length: before the cap where a run wrote one down, and
 * what survived where it did not.
 *
 * This is `Article.full_source_words()` on the reading side. An empty cell is
 * not a zero - every run before 2026-08-28 left the pre-cap cell blank.
 */
export function articleWords(row: TelemetryRow): number {
	return row.source_words_before_cap ?? row.source_words ?? 0;
}

/** Read the same way `Article.full_source_words()` reads it: the length before
 * the cap where the run wrote one down, and the length that survived where it
 * did not. So the cut is the comparison of two cells of one row and nothing
 * else - no flag whose meaning has changed, and no test against the cap itself,
 * which moves whenever the cap moves.
 */
export function placeRow(row: TelemetryRow): Placed {
	const seen = row.source_words;
	const before = row.source_words_before_cap;
	const cut = before !== null && seen !== null && before > seen;
	const sourceWords = articleWords(row);
	if (sourceWords <= 0) return { kind: 'no-length', date: row.date };
	const summaryWords = row.summary_words ?? 0;
	if (summaryWords <= 0) return { kind: 'no-summary' };
	return {
		kind: 'point',
		point: {
			date: row.date,
			item_id: row.item_id,
			source_words: sourceWords,
			// Carried only where the model saw something other than the whole
			// article, so a number repeating "nothing was cut" never ships.
			...(cut ? { source_seen_words: seen as number } : {}),
			summary_words: summaryWords,
			truncation_flagged: cut
		}
	};
}

/** The plot and the sentence under it, out of one pass over the rows.
 *
 * It takes the rows the viewport already holds. Those are seeded to the open
 * window and grown by month fetch, so the plot costs the page nothing beyond
 * the telemetry that was on it anyway - and it draws whatever the operator has
 * panned to rather than whatever the build inlined.
 *
 * One mark per article per day, never one per row: a re-run writes a second row
 * for an article an earlier run already published, and two marks for one
 * article is the same measurement drawn twice. The run that read the most of it
 * is the one kept, with both of its lengths, because a length before the cap
 * from one run against a length after it from another measures nothing. It is
 * the rule `sourceCuts` reads the same ledger by, so the plot and the source
 * table cannot disagree about how many articles a day had.
 */
export function compressionView(rows: readonly TelemetryRow[]): {
	points: CompressionPoint[];
	unplotted: UnplottedDay[];
} {
	const perArticle = new Map<string, TelemetryRow>();
	for (const row of rows) {
		if (!published(row)) continue;
		const key = `${row.date}-${row.item_id}`;
		const held = perArticle.get(key);
		if (held === undefined || articleWords(row) > articleWords(held)) perArticle.set(key, row);
	}

	const points: CompressionPoint[] = [];
	const missing = new Map<string, number>();
	for (const row of perArticle.values()) {
		const placed = placeRow(row);
		if (placed.kind === 'point') points.push(placed.point);
		else if (placed.kind === 'no-length') {
			missing.set(placed.date, (missing.get(placed.date) ?? 0) + 1);
		}
	}
	return {
		points: points.sort((a, b) => a.date.localeCompare(b.date)),
		unplotted: [...missing.entries()]
			.map(([date, n]) => ({ date, n }))
			.sort((a, b) => a.date.localeCompare(b.date))
	};
}

/** Where the cut fell, and over which days it was the cut in force. */
export interface CapLine {
	words: number;
	/** Oldest and newest day in view that was cut at this length. */
	first: string;
	last: string;
}

/** What one cap line says about itself.
 *
 * A lone cap needs no date at all - it is the cut, over the whole window. Where
 * there are several the labels read as a handover: the oldest names the last
 * day it applied, and each later one names the first day it did.
 *
 * The source-cut range plot is the only caller. The compression scatter was the
 * other one and this row retired it, along with `capsInView` and `seenWords`;
 * the range plot derives its own cut points in `capPoints`.
 */
export function capLabel(caps: readonly CapLine[], index: number): string {
	const cap = caps[index];
	const words = `cut at ${grouped(cap.words)} words`;
	if (caps.length === 1) return words;
	return index === 0
		? `${words} (to ${dayMonth(cap.last)})`
		: `${words} (from ${dayMonth(cap.first)})`;
}

/** Thousands separated by hand, because `toLocaleString` reads the machine's
 * locale and two builds have to agree. */
export function grouped(value: number): string {
	return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export interface SummaryBand {
	min_source_words: number;
	target_words_min: number;
	target_words_max: number;
}

/** Where a summary landed against the band its own article asks for. */
export type BandPlace = 'inside' | 'short' | 'long';

/** One article placed against that band.
 *
 * The question the section asks is how far from the target a summary landed, so
 * the distance is what it ranks on. The two lengths ride along because the
 * outlier list prints them, not because anything is ordered by them.
 */
export interface BandPlacement {
	date: string;
	item_id: string;
	source_words: number;
	summary_words: number;
	place: BandPlace;
	/** Words from the nearer bound of the band. Zero inside it. */
	distance: number;
	band: SummaryBand;
}

/** One day's three-way split. */
export interface BandDay {
	date: string;
	inside: number;
	short: number;
	long: number;
	/** The three above, summed. A column whose parts do not reach the day's own
	 * count of placeable summaries is mis-binning articles. */
	items: number;
}

/** The band an article of this length was written to.
 *
 * The longest band the article reaches, which is how `SummarizeConfig.band_for`
 * reads the same ladder on the producing side. Two readings of one ladder would
 * put an article in one band on the page and another in the prompt, and nothing
 * on screen would look wrong.
 */
export function bandFor(bands: readonly SummaryBand[], sourceWords: number): SummaryBand | null {
	if (bands.length === 0) return null;
	let chosen = bands[0];
	for (const band of bands) {
		if (sourceWords >= band.min_source_words) chosen = band;
	}
	return chosen;
}

export function placeInBand(
	point: CompressionPoint,
	bands: readonly SummaryBand[]
): BandPlacement | null {
	const band = bandFor(bands, point.source_words);
	if (band === null) return null;
	const short = point.summary_words < band.target_words_min;
	const long = point.summary_words > band.target_words_max;
	return {
		date: point.date,
		item_id: point.item_id,
		source_words: point.source_words,
		summary_words: point.summary_words,
		place: short ? 'short' : long ? 'long' : 'inside',
		distance: short
			? band.target_words_min - point.summary_words
			: long
				? point.summary_words - band.target_words_max
				: 0,
		band
	};
}

/** Every article the window holds that a band can be read for. */
export function bandPlacements(
	points: readonly CompressionPoint[],
	bands: readonly SummaryBand[],
	window: TimeWindow
): BandPlacement[] {
	const placed: BandPlacement[] = [];
	for (const point of rowsInWindow([...points], window)) {
		const one = placeInBand(point, bands);
		if (one !== null) placed.push(one);
	}
	return placed;
}

/** The three-way split, one column a day, across the whole window.
 *
 * Every day the window covers gets a column, including a day nothing published.
 * A chart drawn only over the days that have rows closes the gap a missed day
 * left, and a missed day is a fact the operator came here to see.
 */
export function bandSplit(placed: readonly BandPlacement[], window: TimeWindow): BandDay[] {
	const byDate = new Map<string, BandDay>();
	for (const date of daysInWindow(window)) {
		byDate.set(date, { date, inside: 0, short: 0, long: 0, items: 0 });
	}
	for (const one of placed) {
		const day = byDate.get(one.date);
		if (day === undefined) continue;
		day[one.place] += 1;
		day.items += 1;
	}
	return [...byDate.values()];
}

/** The articles furthest outside their band, worst first.
 *
 * Ranked by distance, never by date. The longer article breaks a tie, then the
 * date and the id, so two equal misses cannot swap places between builds and
 * move the prerendered page for no reason.
 */
export function bandOutliers(placed: readonly BandPlacement[]): BandPlacement[] {
	return placed
		.filter((one) => one.place !== 'inside')
		.sort(
			(a, b) =>
				b.distance - a.distance ||
				b.source_words - a.source_words ||
				a.date.localeCompare(b.date) ||
				a.item_id.localeCompare(b.item_id)
		);
}

/** The article lengths one band covers, as a reader says them.
 *
 * Read off the ladder rather than the band, because a band records only the
 * length it starts at - the length it stops at is the next rung's floor, and
 * the last rung has no ceiling at all.
 */
export function bandSpan(bands: readonly SummaryBand[], index: number): string {
	const next = bands[index + 1];
	if (next === undefined) return `${grouped(bands[index].min_source_words)} and over`;
	if (index === 0) return `under ${grouped(next.min_source_words)}`;
	return `${grouped(bands[index].min_source_words)} to ${grouped(next.min_source_words - 1)}`;
}

/** One stage's day: the median, and the counts behind it.
 *
 * `ms` is null where nothing was timed. Zero is a measurement - a cheap stage
 * finishes inside a millisecond clock's own resolution - so the two facts
 * cannot share a value. `timed` against `total` carries the third one: a day
 * timed in full and a day timed in part are not the same day either.
 */
export interface StageTiming {
	ms: number | null;
	timed: number;
	total: number;
}

/** One day's median milliseconds per stage, over the item-health census.
 *
 * The three stages an item waits on, and only those. Scoring is timed too and
 * it is not here: it runs after the summary is written, so nothing waits on it
 * and a fourth line on a critical-path chart read as a fourth constraint. It is
 * on the Model route, beside the cost of writing the summary it checks.
 */
export interface StageTimingDay {
	date: string;
	items: number;
	fetch: StageTiming;
	extract: StageTiming;
	summarize: StageTiming;
}

/** The spread of one day's per-item rates. A candle, never an average.
 *
 * The spread is the point. A worker summarises its short articles first and its
 * long ones last, so the slowest item of a day is several times slower than the
 * fastest, and a single number hides the fact that the two ends moved apart.
 */
export interface RateSpread {
	min: number;
	p25: number;
	median: number;
	p75: number;
	max: number;
}

/** One run's median rates. Four of these sit behind a day's candle. */
export interface ThroughputRun {
	runId: string;
	items: number;
	read: number;
	write: number;
}

export interface ThroughputDay {
	date: string;
	items: number;
	read: RateSpread;
	write: RateSpread;
	/** The whole day's tokens over the whole day's milliseconds. Weighted by
	 * work done, unlike the median, which weighs a release note like a feature. */
	readTps: number;
	writeTps: number;
	cacheHitPct: number;
	runs: ThroughputRun[];
	/** What wrote the day, where a ledger says. Two days on different models are
	 * two measurements, so nothing compares them. */
	model: string | null;
}

/** One stage's day: what reached it, what died there, and how big the day was.
 *
 * `reached` is the denominator, and it is not the day. An item that died at
 * fetch never reached extract, so dividing extract's failures by the day's
 * items understates every stage after the first. Measured 2026-08-30 over the
 * 4,167 rows of the committed projection: extract reads 10.4 percent against
 * the day and 12.3 percent against the 3,499 items that got as far as extract.
 *
 * `planned` is the day itself, repeated on all three stages, and it is the
 * height of the day's column. Keeping both means a rate and a volume can be
 * drawn on one chart without either one being recomputed from the other.
 */
export interface StageFailureDay {
	date: string;
	planned: number;
	reached: number;
	failures: number;
	rate: number | null;
	codes: Record<string, number>;
}

export interface StageFailureSeries {
	stage: 'fetch' | 'extract' | 'summarize';
	label: string;
	days: StageFailureDay[];
}

export const FAILURE_STAGES: StageFailureSeries['stage'][] = ['fetch', 'extract', 'summarize'];

/** The steps an item's clock is split into, bottom of the stack first.
 *
 * `key` is what a test names and `label` is what a reader sees. The order is
 * the order the work happens in, so reading the stack bottom to top is reading
 * the item's life in order.
 *
 * **`gap` is the one that matters most.** It is `stage_gap_ms` - the item's own
 * wall clock minus every stage the pipeline named - so anything a later change
 * adds without timing it lands there and is visible the day it appears. A
 * split that dropped it would look complete and be wrong by however much
 * nobody measured.
 *
 * `model` is the same idea one level down: the summarize stage's time that
 * neither call claimed. On a run that published no per-call split it is the
 * whole stage, which is the honest reading - the stage was timed, the calls
 * inside it were not.
 */
export const TIME_BANDS = [
	{ key: 'fetch', label: 'Fetch' },
	{ key: 'extract', label: 'Extract' },
	{ key: 'label', label: 'Label call' },
	{ key: 'summary', label: 'Summary' },
	{ key: 'plan', label: 'Visual plan' },
	{ key: 'model', label: 'Model, unsplit' },
	{ key: 'faithfulness', label: 'Faithfulness' },
	{ key: 'gap', label: 'Unattributed' }
] as const;

export type TimeBandKey = (typeof TIME_BANDS)[number]['key'];

/** One day of the item-time split.
 *
 * `ms` is the MEAN milliseconds an item spent in each band, not the median, and
 * that is the whole reason this shape exists. Medians do not add: a stack of
 * per-stage medians draws a column whose height is not the median item, so
 * every share it prints is wrong by an amount nobody can see. Means add
 * exactly, so the bands sum to `total` and a reader can take a share off the
 * chart. The spread is answered elsewhere - the stage-timing chart is a median
 * with its quartiles - and this one answers composition.
 *
 * `items` counts the rows that carried `item_total_ms`, and it is the
 * denominator of every band. A row with no item clock is not in the average at
 * all: counting it would divide real milliseconds by items nobody timed and
 * shrink every band on the day a new instrument was rolled out.
 *
 * A band can be negative. `stage_gap_ms` is signed on purpose - below zero
 * means two named stages overlapped or two clocks disagreed - and clamping it
 * would hide exactly the fault it exists to show.
 */
export interface TimeSplitDay {
	date: string;
	/** Rows on this day that carried an item clock. */
	items: number;
	/** Mean milliseconds an item took, end to end. The sum of `ms`. */
	total: number;
	/** Mean milliseconds an item spent in each band, in `TIME_BANDS` order. */
	ms: number[];
}

function msCell(value: number | null): number {
	return value ?? 0;
}

/** One item's milliseconds, split into the bands, in `TIME_BANDS` order.
 *
 * The bands are built to add up to `item_total_ms` whatever the row carries.
 * `label_ms` and `summary_ms` are a split of `summarize_ms` rather than stages
 * beside it, so they are taken out of the stage and what is left is `model`;
 * `visual_plan_ms` is decoded inside the second call, so it is taken out of
 * `summary`. A row missing any of those reads the missing cell as zero and the
 * time stays in the wider band it belongs to, which is why an unsplit run draws
 * its whole model stage as `model` rather than losing it.
 */
export function itemTimeBands(row: TelemetryRow): number[] {
	const summarize = msCell(row.summarize_ms);
	const label = msCell(row.label_ms);
	const summary = msCell(row.summary_ms);
	const plan = msCell(row.visual_plan_ms);
	return [
		msCell(row.fetch_ms),
		msCell(row.extract_ms),
		label,
		summary - plan,
		plan,
		summarize - label - summary,
		msCell(row.faithfulness_ms),
		msCell(row.stage_gap_ms)
	];
}

/** Where the day's items spent their time, one entry per day in the window.
 *
 * A day with no timed row is present with `items: 0` and every band at zero, so
 * the column keeps its place on the axis: a day dropped from the array shifts
 * every day after it and draws a gap as if it were the next day along.
 */
export function timeSplit(rows: TelemetryRow[], window: TimeWindow): TimeSplitDay[] {
	const summed = new Map<string, { items: number; ms: number[] }>();
	for (const row of rowsInWindow(rows, window)) {
		if (row.item_total_ms === null) continue;
		let day = summed.get(row.date);
		if (day === undefined) {
			day = { items: 0, ms: TIME_BANDS.map(() => 0) };
			summed.set(row.date, day);
		}
		day.items += 1;
		const bands = itemTimeBands(row);
		for (let index = 0; index < bands.length; index += 1) {
			day.ms[index] += bands[index];
		}
	}
	return daysInWindow(window).map((date) => {
		const day = summed.get(date);
		if (day === undefined || day.items === 0) {
			return { date, items: 0, total: 0, ms: TIME_BANDS.map(() => 0) };
		}
		const ms = day.ms.map((total) => total / day.items);
		return { date, items: day.items, total: ms.reduce((sum, band) => sum + band, 0), ms };
	});
}

function parseCsv(text: string): string[][] {
	const rows: string[][] = [];
	let row: string[] = [];
	let cell = '';
	let quoted = false;
	for (let index = 0; index < text.length; index += 1) {
		const ch = text[index];
		if (quoted) {
			if (ch === '"' && text[index + 1] === '"') {
				cell += '"';
				index += 1;
			} else if (ch === '"') {
				quoted = false;
			} else {
				cell += ch;
			}
		} else if (ch === '"') {
			quoted = true;
		} else if (ch === ',') {
			row.push(cell);
			cell = '';
		} else if (ch === '\n' || (ch === '\r' && text[index + 1] === '\n')) {
			if (ch === '\r') index += 1;
			row.push(cell);
			rows.push(row);
			row = [];
			cell = '';
		} else {
			cell += ch;
		}
	}
	if (cell !== '' || row.length > 0) {
		row.push(cell);
		rows.push(row);
	}
	return rows.filter((cells) => cells.some((cellText) => cellText !== ''));
}

function numberCell(value: string): number | null {
	if (value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

export function parseTelemetryCsv(text: string): TelemetryRow[] {
	const rows = parseCsv(text);
	const header = rows[0] ?? [];
	// A prefix, not an equality, on purpose: a cached bundle must keep reading a
	// shard that grew a column. `backend/tests/contracts/` holds the
	// prefix against the writer, so tightening this buys nothing and breaks that.
	if (TELEMETRY_COLUMNS.some((name, index) => header[index] !== name)) {
		throw new Error('telemetry projection header did not match the contract');
	}
	return rows.slice(1).map((cells) => ({
		date: cells[0] ?? '',
		run_id: cells[1] ?? '',
		item_id: cells[2] ?? '',
		vertical: cells[3] ?? '',
		source_id: cells[4] ?? '',
		stage: cells[5] ?? '',
		outcome: cells[6] ?? '',
		code: cells[7] ?? '',
		source_words: numberCell(cells[8] ?? ''),
		summary_words: numberCell(cells[9] ?? ''),
		source_words_before_cap: numberCell(cells[10] ?? ''),
		fetch_ms: numberCell(cells[11] ?? ''),
		extract_ms: numberCell(cells[12] ?? ''),
		summarize_ms: numberCell(cells[13] ?? ''),
		prefill_ms: numberCell(cells[14] ?? ''),
		decode_ms: numberCell(cells[15] ?? ''),
		input_tokens: numberCell(cells[16] ?? ''),
		output_tokens: numberCell(cells[17] ?? ''),
		cached_tokens: numberCell(cells[18] ?? ''),
		model_calls: numberCell(cells[19] ?? ''),
		label_kind: cells[20] ?? '',
		label_prefill_ms: numberCell(cells[21] ?? ''),
		label_decode_ms: numberCell(cells[22] ?? ''),
		label_input_tokens: numberCell(cells[23] ?? ''),
		label_output_tokens: numberCell(cells[24] ?? ''),
		label_cached_tokens: numberCell(cells[25] ?? ''),
		summary_kind: cells[26] ?? '',
		summary_prefill_ms: numberCell(cells[27] ?? ''),
		summary_decode_ms: numberCell(cells[28] ?? ''),
		summary_input_tokens: numberCell(cells[29] ?? ''),
		summary_output_tokens: numberCell(cells[30] ?? ''),
		summary_cached_tokens: numberCell(cells[31] ?? ''),
		queue_wait_ms: numberCell(cells[32] ?? ''),
		label_ms: numberCell(cells[33] ?? ''),
		summary_ms: numberCell(cells[34] ?? ''),
		visual_plan_ms: numberCell(cells[35] ?? ''),
		visual_plan_ms_is_estimate: cells[36] ?? '',
		faithfulness_ms: numberCell(cells[37] ?? ''),
		model_wait_ms: numberCell(cells[38] ?? ''),
		item_total_ms: numberCell(cells[39] ?? ''),
		stage_gap_ms: numberCell(cells[40] ?? ''),
		visual_plan_tokens_written: numberCell(cells[41] ?? ''),
		label_prefill_tokens_per_s: numberCell(cells[42] ?? ''),
		label_decode_tokens_per_s: numberCell(cells[43] ?? ''),
		summary_prefill_tokens_per_s: numberCell(cells[44] ?? ''),
		summary_decode_tokens_per_s: numberCell(cells[45] ?? ''),
		cpu_model: cells[46] ?? '',
		cpu_busy_pct: numberCell(cells[47] ?? ''),
		load_1m: numberCell(cells[48] ?? '')
	}));
}

export function telemetryCsv(rows: TelemetryRow[]): string {
	const body = rows.map((row) =>
		TELEMETRY_COLUMNS.map((column) => {
			const value = row[column];
			return value === null ? '' : String(value);
		}).join(',')
	);
	return `${TELEMETRY_COLUMNS.join(',')}\n${body.join('\n')}${body.length ? '\n' : ''}`;
}

export function datesIn(rows: TelemetryRow[]): string[] {
	return [...new Set(rows.map((row) => row.date).filter(Boolean))].sort();
}

export function rowsInWindow<T extends { date: string }>(rows: T[], window: TimeWindow): T[] {
	return rows.filter((row) => row.date >= window.start && row.date <= window.end);
}

/** What one day of rows adds up to, before the stages are laid out in order. */
interface DayTally {
	/** Every row the day holds. */
	planned: number;
	/** Rows that left `plan`, which is the first stage's denominator. */
	reached: number;
	/** Failures, one count per `FAILURE_STAGES` entry. */
	failures: number[];
	/** The codes behind those failures, one record per `FAILURE_STAGES` entry,
	 * in the order the rows arrived. */
	codes: Record<string, number>[];
}

function emptyTally(): DayTally {
	return {
		planned: 0,
		reached: 0,
		failures: FAILURE_STAGES.map(() => 0),
		codes: FAILURE_STAGES.map(() => ({}) as Record<string, number>)
	};
}

/** One pass over the window's rows, then the stages laid out in pipeline order.
 *
 * Every fact a day's three columns need is counted while the rows go past, so a
 * row is read once rather than once for the day's size and again for each
 * stage. The buckets are filled in place too: rebuilding a day's array as
 * `[...held, row]` copies every row already in it, and a day with many rows is
 * the day this chart is opened for.
 */
export function failureSeries(rows: TelemetryRow[], window: TimeWindow): StageFailureSeries[] {
	const stageAt = new Map<string, number>(FAILURE_STAGES.map((stage, index) => [stage, index]));
	const tallied = new Map<string, DayTally>();
	for (const row of rowsInWindow(rows, window)) {
		let day = tallied.get(row.date);
		if (day === undefined) {
			day = emptyTally();
			tallied.set(row.date, day);
		}
		day.planned += 1;
		// A row that never left `plan` was never fetched, so it belongs to no
		// stage's denominator - only to the day's size.
		if (row.stage !== 'plan') day.reached += 1;
		if (row.outcome !== 'failed') continue;
		const index = stageAt.get(row.stage);
		if (index === undefined) continue;
		day.failures[index] += 1;
		const key = row.code || 'unknown';
		day.codes[index][key] = (day.codes[index][key] ?? 0) + 1;
	}
	// Down the pipeline order, because each stage's denominator is whatever the
	// stage before it let through.
	const perDay = daysInWindow(window).map((date) => {
		const day = tallied.get(date) ?? emptyTally();
		let reached = day.reached;
		return FAILURE_STAGES.map((_stage, index) => {
			const failures = day.failures[index];
			const drawn: StageFailureDay = {
				date,
				planned: day.planned,
				reached,
				failures,
				rate: reached === 0 ? null : failures / reached,
				codes: day.codes[index]
			};
			reached -= failures;
			return drawn;
		});
	});
	return FAILURE_STAGES.map((stage, index) => ({
		stage,
		label: stage,
		days: perDay.map((day) => day[index])
	}));
}

export function failedRows(
	rows: TelemetryRow[],
	window: TimeWindow,
	code: string | null,
	cause: string | null = null,
	source: string | null = null
): TelemetryRow[] {
	return rowsInWindow(rows, window)
		.filter((row) => row.outcome === 'failed')
		.filter((row) => code === null || row.code === code)
		.filter((row) => cause === null || causeKey(row) === cause)
		.filter((row) => source === null || row.source_id === source)
		.sort((a, b) => b.date.localeCompare(a.date) || a.item_id.localeCompare(b.item_id));
}

/** A stage and a code, which is the pair an operator acts on.
 *
 * An empty code reads as `unknown` here and nowhere else, so the ledger and the
 * rows behind it can never disagree about which cause a row belongs to.
 */
export function causeKey(row: TelemetryRow): string {
	return `${row.stage}/${row.code || 'unknown'}`;
}

/** A key for one drawn row of the failed-item list.
 *
 * The index is in it because a run writes a row per stage for an item, so a run
 * and an item together repeat. A keyed each over a repeated key throws, the
 * update is abandoned part-way, and the rows already on screen stay - which
 * reads as a filter letting foreign causes through rather than as an error.
 * Measured 2026-08-30 against the committed projection: selecting
 * `extract/paywalled` left `fetch/http_client_error` rows in the table.
 */
export function failureRowKey(row: TelemetryRow, index: number): string {
	return `${index}-${row.run_id}-${row.item_id}-${row.stage}-${row.code}`;
}

/** One cause of failure, and everything the ledger prints about it. */
export interface FailureCause {
	/** `stage/code`. What a selected row hands back, and what `failedRows`
	 * filters on. */
	key: string;
	stage: string;
	code: string;
	count: number;
	/** One count per day of the window, oldest first, so the trend line and the
	 * count beside it are read off the same rows. */
	daily: number[];
	/** Distinct sources this cause reached. */
	sources: number;
	/** The newest day it fired. */
	last: string;
	/** Days between that and the window's end. Zero is the newest day in view.
	 * Measured against the window rather than against the clock, because this
	 * page is prerendered and a build-time "today" goes stale on the shelf. */
	lastAgo: number;
}

export interface FailureLedger {
	causes: FailureCause[];
	/** Every failed row in the window. The causes' counts sum to exactly this. */
	failed: number;
	/** Distinct sources with any row in the window, failed or not. This is the
	 * denominator breadth is read against: one cause on 1 of 47 sources is a
	 * site that changed its markup, and the same count on 40 of 47 is the
	 * extractor. */
	sourcesSeen: number;
	/** Rows of any kind in the window. Zero means the ledger cannot answer,
	 * which is a different fact from nothing having failed. */
	rows: number;
}

/** Failures grouped by cause, over one window.
 *
 * Uncapped on purpose. The cap is a display choice, and a ledger that dropped
 * its tail here would report a sum smaller than the rows it is drawn from.
 */
export function failureLedger(rows: TelemetryRow[], window: TimeWindow): FailureLedger {
	const inWindow = rowsInWindow(rows, window);
	const days = daysInWindow(window);
	const slot = new Map(days.map((date, index) => [date, index]));
	const sourcesSeen = new Set<string>();

	interface Held {
		stage: string;
		code: string;
		count: number;
		daily: number[];
		sources: Set<string>;
		last: string;
	}
	const held = new Map<string, Held>();

	let failed = 0;
	for (const row of inWindow) {
		if (row.source_id) sourcesSeen.add(row.source_id);
		if (row.outcome !== 'failed') continue;
		failed += 1;
		const key = causeKey(row);
		let cause = held.get(key);
		if (cause === undefined) {
			cause = {
				stage: row.stage,
				code: row.code || 'unknown',
				count: 0,
				daily: days.map(() => 0),
				sources: new Set<string>(),
				last: row.date
			};
			held.set(key, cause);
		}
		cause.count += 1;
		const index = slot.get(row.date);
		if (index !== undefined) cause.daily[index] += 1;
		if (row.source_id) cause.sources.add(row.source_id);
		if (row.date > cause.last) cause.last = row.date;
	}

	return {
		causes: [...held.entries()].map(([key, cause]) => ({
			key,
			stage: cause.stage,
			code: cause.code,
			count: cause.count,
			daily: cause.daily,
			sources: cause.sources.size,
			last: cause.last,
			lastAgo: daysBetween(cause.last, window.end) - 1
		})),
		failed,
		sourcesSeen: sourcesSeen.size,
		rows: inWindow.length
	};
}

/** One source, and the articles its failures cost the digest over one window.
 *
 * The item rows below the ledger name a source per row and nothing above them
 * says which source cost the most, so this is the one column of that table no
 * surface answers. Measured 2026-09-01 over the committed projection, a
 * thirty-day window holds 60 sources with a loss and 778 lost articles.
 */
export interface SourceLoss {
	/** `source_id`, the same string the item rows name. */
	key: string;
	/** Distinct articles that failed. One article per source per day, the rule
	 * `compressionView` reads the same ledger by, so the two surfaces cannot
	 * disagree about how many articles a day held. */
	lost: number;
	/** Distinct articles the window saw from this source, failed or not. The
	 * denominator the count is read against: 42 of 42 is a source that stopped
	 * working, and 42 of 500 is a bad afternoon. */
	articles: number;
	/** Causes those failures fell under. One is usually a site that changed its
	 * markup; several is usually something else. */
	causes: number;
	/** The one cause, where there is only one. Ten rows each printing `1 cause`
	 * is a column that says nothing; the cause's own name is the fact behind the
	 * number, and it is only a fact while the count is one. */
	cause: string | null;
	/** The newest day it lost one. */
	last: string;
	/** Days between that and the window's end. Zero is the newest day in view,
	 * measured against the window rather than against the clock, because this
	 * page is prerendered and a build-time "today" goes stale on the shelf. */
	lastAgo: number;
}

export interface SourceLossLedger {
	sources: SourceLoss[];
	/** Articles lost across every source. An article belongs to one source, so
	 * the sources' counts sum to exactly this. */
	lost: number;
	/** Rows of any kind in the window. Zero means the ledger cannot answer,
	 * which is a different fact from nothing having been lost. */
	rows: number;
}

/** Sources ranked by what their failures cost, over one window.
 *
 * Uncapped, for the same reason `failureLedger` is: the cap is a display choice
 * and a ledger that dropped its tail here would report a sum smaller than the
 * rows it was drawn from.
 */
export function sourceLosses(rows: TelemetryRow[], window: TimeWindow): SourceLossLedger {
	const inWindow = rowsInWindow(rows, window);

	interface Held {
		lost: Set<string>;
		articles: Set<string>;
		causes: Set<string>;
		last: string;
	}
	const held = new Map<string, Held>();

	for (const row of inWindow) {
		const source = row.source_id;
		if (!source) continue;
		let entry = held.get(source);
		if (entry === undefined) {
			entry = { lost: new Set(), articles: new Set(), causes: new Set(), last: '' };
			held.set(source, entry);
		}
		const article = `${row.date}-${row.item_id}`;
		entry.articles.add(article);
		if (row.outcome !== 'failed') continue;
		entry.lost.add(article);
		entry.causes.add(causeKey(row));
		if (row.date > entry.last) entry.last = row.date;
	}

	const sources = [...held.entries()]
		.filter(([, entry]) => entry.lost.size > 0)
		.map(([key, entry]) => ({
			key,
			lost: entry.lost.size,
			articles: entry.articles.size,
			causes: entry.causes.size,
			cause: entry.causes.size === 1 ? [...entry.causes][0] : null,
			last: entry.last,
			lastAgo: daysBetween(entry.last, window.end) - 1
		}));

	return {
		sources,
		lost: sources.reduce((total, source) => total + source.lost, 0),
		rows: inWindow.length
	};
}

/** The axis the model-swap comparison shares, as fractions of the plot width.
 *
 * Every row is drawn against its own value on the older model, so no change is
 * 100 percent on all of them and that point is the axis centre. Symmetric on
 * purpose: an axis running 78 to 120 would draw a fifth off as a longer track
 * than a fifth on, and the whole panel is a reader comparing seven track
 * lengths.
 *
 * Pure arithmetic, so the geometry can be checked in Node without a browser.
 */
export interface SwapScale {
	/** Percentage points either side of no change. */
	half: number;
	/** Low, no change, high. */
	ticks: [number, number, number];
	/** A percent to a share of the plot, 0 at the left edge and 1 at the right. */
	at: (percent: number) => number;
}

export function swapScale(percents: readonly number[], minHalf = 25): SwapScale {
	const half = Math.max(minHalf, ...percents.map((percent) => Math.abs(percent - 100)));
	return {
		half,
		ticks: [100 - half, 100, 100 + half],
		at: (percent: number) => (percent - (100 - half)) / (half * 2)
	};
}

/** Where one source's row of the length range plot sits, in chart pixels. */
export interface RangeMarks {
	/** The shortest, the middle and the longest article of that source. */
	x0: number;
	xMid: number;
	x1: number;
	/** Where the text past the cut point starts, held inside the row's own span.
	 *
	 * Equal to `x1` where nothing this source published reached the cut point,
	 * so the emphasised segment has no length and draws nothing.
	 */
	xCut: number;
	/** True where the longest article ran past the cut point. */
	past: boolean;
}

/** One row of the length range plot, placed.
 *
 * Pure arithmetic over a scale somebody else built, so the plot's geometry can
 * be checked in Node against an identity scale. The clamp is the part worth
 * having in one place: a cut point left of a source's shortest article would
 * otherwise draw the emphasised segment starting outside the track it belongs
 * to, which reads as text lost from an article that is not on the row.
 */
export function rangeMarks(
	range: { min: number; median: number; max: number },
	capWords: number | null,
	scale: (words: number) => number
): RangeMarks {
	const x0 = scale(range.min);
	const xMid = scale(range.median);
	const x1 = scale(range.max);
	const past = capWords !== null && range.max > capWords;
	return {
		x0,
		xMid,
		x1,
		xCut: past ? Math.min(x1, Math.max(x0, scale(capWords as number))) : x1,
		past
	};
}

// ---------------------------------------------------------------------------
// How long one thing took, as a distribution
// ---------------------------------------------------------------------------

/** The value at a fraction of the way through a sorted list, interpolated. */
export function quantile(sorted: readonly number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** One bar of a time histogram.
 *
 * `from` and `to` are whole seconds and `from` is zero on the first bar, which
 * is the one holding everything under a second. The edges double, so a bar is
 * one doubling wide wherever it sits on the axis - which is what lets a
 * distribution running from a third of a second to twelve minutes be read at
 * all.
 */
export interface WriteBin {
	/** Lower edge, whole seconds. Zero means "under one second". */
	from: number;
	/** Upper edge, whole seconds. The bar holds `from <= t < to`. */
	to: number;
	n: number;
	/** Every item finished in `to` seconds or less, as whole percent. */
	throughPct: number;
}

/** How long one thing took, over every one of them a clock recorded.
 *
 * The bars and the two rules, and nothing about which window they came from -
 * that belongs to the caller, which knows what it asked for. Four panels draw
 * this shape over four different clocks: the model reading a prompt and writing
 * a summary on Pipelines, and the whole model call and the checker's own clock
 * on Summaries. It is the same question every time - how long did one take, and
 * how bad does it get - so it is one binning and one pair of rules rather than
 * four that can drift apart.
 *
 * The median and the 95th are taken over the values themselves and never off
 * the bars: a percentile read out of a bin is a guess at where inside the bin
 * it fell, and these two are the figures somebody quotes.
 */
export interface Distribution {
	bins: WriteBin[];
	/** Timings behind the chart. The denominator for every bar. */
	n: number;
	/** Milliseconds. */
	median: number;
	p95: number;
	slowest: number;
	fastest: number;
}

/** The bars and the rules, or null where nothing was timed.
 *
 * Null is the empty state and it is not a chart of zeroes. Nothing measured it;
 * it did not run instantly.
 *
 * It lives here rather than beside the first panel that drew it because a
 * browser cannot import `$lib/server/`, and the Pipelines route bins the two
 * model clocks in the same doublings the Summaries route bins its own in.
 */
export function distribution(values: readonly number[]): Distribution | null {
	const sorted = [...values].sort((a, b) => a - b);
	if (sorted.length === 0) return null;

	// The first edge is one second, so every label on the axis is a whole
	// number. Everything below it shares one bar, labelled the way the console
	// spells a measurement that rounds away.
	const top = Math.max(1, sorted[sorted.length - 1] / 1000);
	const edges = [0, 1];
	while (edges[edges.length - 1] <= top) edges.push(edges[edges.length - 1] * 2);

	const bins: WriteBin[] = [];
	let through = 0;
	// One advancing cursor down the sorted values rather than a full scan per
	// bin. The values are ascending and the edges are ascending, so every value
	// belongs to the bin the cursor is standing in.
	let cursor = 0;
	// Anything below the first edge belongs to no bin, which is what a full scan
	// did too: the first bin asks for `>= from` and every later one starts at or
	// above one second.
	while (cursor < sorted.length && sorted[cursor] / 1000 < edges[0]) cursor += 1;
	for (let index = 0; index < edges.length - 1; index += 1) {
		const from = edges[index];
		const to = edges[index + 1];
		const opened = cursor;
		while (cursor < sorted.length && sorted[cursor] / 1000 < to) cursor += 1;
		const n = cursor - opened;
		through += n;
		bins.push({ from, to, n, throughPct: Math.round((through / sorted.length) * 100) });
	}

	// Leading and trailing empty bars are axis, not data. A gap between two
	// occupied bars stays: it is the distribution saying nothing landed there.
	const first = bins.findIndex((bin) => bin.n > 0);
	const last = bins.length - 1 - [...bins].reverse().findIndex((bin) => bin.n > 0);

	return {
		bins: bins.slice(first, last + 1),
		n: sorted.length,
		median: quantile(sorted, 0.5),
		p95: quantile(sorted, 0.95),
		slowest: sorted[sorted.length - 1],
		fastest: sorted[0]
	};
}
