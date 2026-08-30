import { dayMonth } from '../format';
import { daysInWindow, type TimeWindow } from './viewport';

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
	'source_words_before_cap'
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

/** One day's median milliseconds per stage, over the item-health census. */
export interface StageTimingDay {
	date: string;
	items: number;
	fetch: StageTiming;
	extract: StageTiming;
	summarize: StageTiming;
	score: StageTiming;
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
	// shard that grew a column. `backend/tests/test_contracts.py` holds the
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
		source_words_before_cap: numberCell(cells[10] ?? '')
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

export function failureSeries(rows: TelemetryRow[], window: TimeWindow): StageFailureSeries[] {
	const byDate = new Map<string, TelemetryRow[]>();
	for (const row of rowsInWindow(rows, window)) {
		byDate.set(row.date, [...(byDate.get(row.date) ?? []), row]);
	}
	// One pass per day, down the pipeline order, because each stage's denominator
	// is whatever the stage before it let through.
	const perDay = daysInWindow(window).map((date) => {
		const group = byDate.get(date) ?? [];
		// A row that never left `plan` was never fetched, so it belongs to no
		// stage's denominator - only to the day's size.
		let reached = group.filter((row) => row.stage !== 'plan').length;
		return FAILURE_STAGES.map((stage) => {
			const failures = group.filter((row) => row.outcome === 'failed' && row.stage === stage);
			const codes: Record<string, number> = {};
			for (const row of failures) {
				const key = row.code || 'unknown';
				codes[key] = (codes[key] ?? 0) + 1;
			}
			const day: StageFailureDay = {
				date,
				planned: group.length,
				reached,
				failures: failures.length,
				rate: reached === 0 ? null : failures.length / reached,
				codes
			};
			reached -= failures.length;
			return day;
		});
	});
	return FAILURE_STAGES.map((stage, index) => ({
		stage,
		label: stage,
		days: perDay.map((day) => day[index])
	}));
}

export function failedRows(rows: TelemetryRow[], window: TimeWindow, code: string | null): TelemetryRow[] {
	return rowsInWindow(rows, window)
		.filter((row) => row.outcome === 'failed')
		.filter((row) => code === null || row.code === code)
		.sort((a, b) => b.date.localeCompare(a.date) || a.item_id.localeCompare(b.item_id));
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
