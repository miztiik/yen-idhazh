/** Every instrument the eval ledger writes, and the console panel that answers for it.
 *
 * The pipeline has scored a faithfulness number and a lead-coverage number on
 * every summary since the first day it published, and neither had ever been
 * drawn. The band was drawn, and a band is a verdict: it says a summary was
 * doubted and never says by how much, so a prompt change that moved every score
 * four points without moving a single band looked like it did nothing.
 *
 * **The map below is the point of this module, not the charts.** `DRAWN_BY`
 * assigns every measured column of the ledger to exactly one panel, and
 * `NOT_A_MEASUREMENT` says of every remaining column why it is not one. The two
 * together must cover the contract exactly - `frontend/tests/console-model-instruments.spec.ts`
 * reads `schemas/eval-row.schema.json` and fails on a column that is in neither,
 * in both, or in a map and not in the contract. So a column added to `EvalRow`
 * next month fails a test instead of quietly going undrawn for a year, which is
 * how `hhem` and `coverage` got here.
 *
 * **Nothing here sets an alarm.** No threshold, no red, no band tint, no
 * polarity. The committed window is fifteen days and the summarizer is about to
 * change twice, so a threshold drawn from it would be a guess wearing a
 * measurement's clothes. Draw the numbers, set no alarm, colour nothing.
 *
 * Relative imports only, and no `$lib` alias, so the browser suite can import
 * this module in plain Node and re-derive every drawn figure from the ledger
 * without standing up Vite.
 */

import type { DayReadout } from '../charts/frame';
import { bandFor, grouped, type SummaryBand } from '../charts/series';
import type { StackSeries } from '../charts/stacked';
import { dayMonth } from '../format';

/** One surface on the console that answers for at least one ledger column.
 *
 * `id` is the `data-eval-panel` value the page carries, so the map is a claim
 * about the built page and not only about this file.
 */
export interface EvalPanel {
	id: string;
	/** The heading a reader sees, verbatim. */
	title: string;
	/** The published route the panel lives on. */
	route: string;
}

export const EVAL_PANELS: readonly EvalPanel[] = [
	{ id: 'daily-figures', title: 'What the model did', route: '/console/model/' },
	{
		id: 'faithfulness',
		title: 'How closely a summary matched its article',
		route: '/console/model/'
	},
	{ id: 'lead-coverage', title: 'How much of the opening survived', route: '/console/model/' },
	{ id: 'recorded-only', title: 'Measured, and nothing acts on it', route: '/console/model/' },
	{ id: 'summary-length', title: 'How long the summaries came out', route: '/console/model/' },
	{ id: 'score-cost', title: 'What checking one summary cost', route: '/console/model/' },
	{
		id: 'new-fact-rate',
		title: 'How often a key point adds to the summary',
		route: '/console/model/'
	}
];

/** Which panel answers for which ledger column.
 *
 * One owner each. A column can inform more than one surface - `band` sets a
 * card, sorts the source list and splits the model-change table - and the owner
 * is the panel that is *about* it, the one an operator opens to ask how that
 * number is doing.
 */
export const DRAWN_BY: Readonly<Record<string, string>> = {
	// The eleven-column table under "What the model did", one row per day.
	band: 'daily-figures',
	truncation_flagged: 'daily-figures',
	extractiveness: 'daily-figures',
	verbatim_run: 'daily-figures',
	unsupported_numbers: 'daily-figures',
	hedge_dropped: 'daily-figures',
	// New here.
	hhem: 'faithfulness',
	hhem_full: 'faithfulness',
	hhem_delta: 'faithfulness',
	coverage: 'lead-coverage',
	compression: 'recorded-only',
	self_repetition: 'recorded-only',
	evidential_density: 'recorded-only',
	speculative_density: 'recorded-only',
	extraction_suspect: 'recorded-only',
	determinism_violation: 'recorded-only',
	// Already drawn, now declared.
	summary_word_count: 'summary-length',
	source_word_count: 'summary-length',
	source_seen_word_count: 'summary-length',
	score_ms: 'score-cost',
	new_fact_rate: 'new-fact-rate'
};

/** Every remaining column, and why no panel owes it a number.
 *
 * Each of these says *which* row this is, not *how it went*. A panel drawing one
 * would draw an identifier over time, which is a chart of nothing. Two of them -
 * `model_id` and `pipeline_fingerprint` - do reach the page, as the boundary the
 * model-change panel splits on rather than as a reading, and that is why they
 * are here and not above.
 */
export const NOT_A_MEASUREMENT: Readonly<Record<string, string>> = {
	version: 'The schema stamp the row was written under.',
	date: 'Which day. It is the x axis of every panel above, never a value on one.',
	run_id: 'Which execution wrote the row.',
	item_id: 'Which slot on that day\'s page the summary was published in.',
	url_key: 'The key the ledger joins to the published item on.',
	source_url: 'The address the article was read from.',
	title: 'The headline, carried so a row can be read without a second file.',
	vertical: 'Which desk the article belongs to.',
	model_id: 'Which model wrote the summary. The model-change panel splits on it.',
	pipeline_fingerprint:
		'A digest of the declared settings. The model-change panel splits on it; it has no direction to plot.',
	output_digest: 'A digest of the summary, kept so a re-run can be proved identical.',
	source_digest: 'A digest of the article text, kept for the same reason.',
	scorer_version: 'Which checker ran. It says the instrument changed, not that the summaries did.',
	scored_at: 'When the check ran, which is not always the day it scored.',
	attempt:
		'Which try wrote the row. Measured 2026-09-06 over 6,966 rows: every one of them is the first try.'
};

/** The ledger rows this module reads, as the CSV reader hands them over. */
export type EvalInput = Readonly<Record<string, string | undefined>>;

/** An instrument the pipeline records and nothing acts on. */
export interface RecordedInstrument {
	/** The ledger column. */
	id: string;
	label: string;
	unit: 'percent' | 'per-thousand-words';
	/** What the number is, and which way is bad, in the reader's words. */
	note: string;
}

/** Four numbers the checker writes down and no band, no card and no rule reads.
 *
 * Order is the order they are drawn in, and it is deliberate: the two lengths
 * first, because they are about the summary, then the two marker counts, which
 * are about the article and are read against each other rather than alone.
 */
export const RECORDED: readonly RecordedInstrument[] = [
	{
		id: 'compression',
		label: 'Summary length against article length',
		unit: 'percent',
		note: 'Neither direction is wrong on its own - a short article and a long one are asked for different lengths.'
	},
	{
		id: 'self_repetition',
		label: 'Summary text that repeats itself',
		unit: 'percent',
		note: 'The share of four-word runs the summary had already used. Up is the bad direction, and nothing bands it.'
	},
	{
		id: 'evidential_density',
		label: 'Article says who reported it',
		unit: 'per-thousand-words',
		note: 'Phrases like "according to". Read against the line below, never alone.'
	},
	{
		id: 'speculative_density',
		label: 'Article hedges',
		unit: 'per-thousand-words',
		note: 'Phrases like "may" and "could". Read against the line above, never alone.'
	}
];

/** An instrument that either fired on a summary or did not. */
export interface FlagInstrument {
	id: string;
	label: string;
	note: string;
}

export const FLAGS: readonly FlagInstrument[] = [
	{
		id: 'extraction_suspect',
		label: 'Article text looked wrong to the checker',
		note: 'Set when the body read like navigation furniture rather than an article.'
	},
	{
		id: 'determinism_violation',
		label: 'The same input gave a different summary',
		note: 'Set when a re-run of one item did not reproduce its own output.'
	}
];

/** One day of the ledger, reduced to what the three panels draw.
 *
 * Percents are whole numbers, and that is the whole reason the reductions happen
 * here rather than in the page: a raw score between zero and one is the checker's
 * unit, not a reader's, and it has never once told anybody what to do.
 */
export interface EvalDay {
	date: string;
	/** Summaries the ledger holds for that day. */
	scored: number;
	/** Summaries that day carrying a faithfulness score. */
	matched: number;
	/** Faithfulness, whole percent: the lower quarter, the middle, the upper quarter. */
	matchLow: number | null;
	matchMid: number | null;
	matchHigh: number | null;
	/** Summaries that score differently when the whole article is used instead. */
	widerDiffers: number;
	/** The widest such gap that day, in whole percentage points. */
	widestGap: number;
	/** Summaries that day carrying a lead-coverage score. */
	led: number;
	/** Lead coverage of the middle summary, whole percent. */
	leadMid: number | null;
	/** Summaries whose lead coverage fell under the floor. */
	leadUnder: number;
	/** That share as a whole percent of the day's led summaries. */
	leadUnderPct: number | null;
	/** The middle summary's reading on each recorded instrument, in its own unit. */
	recorded: Readonly<Record<string, number | null>>;
	/** How many summaries each flag fired on. */
	fired: Readonly<Record<string, number>>;
}

/** The distinct-published counts a run settled for one day.
 *
 * The three figures a re-score or a scored-then-dropped item would inflate if
 * counted off the ledger rows, so they are counted over the day's published set
 * once, at publication, and read back here. Keyed by date in the map `evalDays`
 * and `modelWork` take. Defined in the console layer both reducers already reach,
 * so neither has to import a server type to name the shape it is handed.
 */
export interface DayScoredCounts {
	/** Distinct published items the checker scored - replaces the row count. */
	scored: number;
	/** Of those, the ones whose identical inputs produced different words. */
	determinismViolations: number;
	/** Of those, the ones whose source read like page furniture. */
	extractionSuspect: number;
}

/** A cell that is present and reads as a number, or null.
 *
 * An absent cell and a cell holding a blank are the same fact - the checker did
 * not write a reading - and both have to stay out of a median rather than enter
 * it as a zero.
 */
function measured(value: string | undefined): number | null {
	if (value === undefined || value.trim() === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The ledger's own spelling of true. Anything else, including a blank, is false. */
function flag(value: string | undefined): boolean {
	return (value ?? '').trim().toLowerCase() === 'true';
}

/** The value at a fraction of a sorted list, by position and never by averaging.
 *
 * Nearest-rank on purpose. An interpolated median is a number no summary
 * actually scored, and the browser oracle has to be able to re-derive this by
 * hand from a shard without reimplementing a quantile rule.
 */
function at(sorted: readonly number[], fraction: number): number {
	const index = Math.min(sorted.length - 1, Math.floor(fraction * sorted.length));
	return sorted[index];
}

/** A score between zero and one, as a whole percent. */
function pct(value: number): number {
	return Math.round(value * 100);
}

/** A per-word rate as a rate per thousand words, to one place.
 *
 * Per word these are 0.003 and 0.011 - two numbers a reader cannot tell apart
 * and neither of which reads as a quantity of anything. Per thousand words they
 * are 3.4 and 11.0 markers, which is a count of phrases in about four pages.
 */
function perThousand(value: number): number {
	return Math.round(value * 10000) / 10;
}

/** Every day the ledger holds, oldest first, reduced.
 *
 * `leadFloor` is `evaluation.lead_coverage_min` from `config/idhazh.json`, handed
 * in rather than read here: this module is imported by the page, by the server
 * load and by the browser oracle in plain Node, and a default sitting in a
 * module variable is how two of those three end up counting against a different
 * number without anything failing.
 *
 * `counts` carries the distinct-published counts a run settled for a day, keyed
 * by date. Where a day is present, the three published-set figures - the scored
 * count and the two flag counts - are taken from it instead of counted off the
 * ledger rows: the ledger dedupes by measurement, so a re-scored item keeps two
 * rows and a scored-then-dropped item keeps one, and either runs the row count
 * high. Every measurement distribution beside them still reads every row, so a
 * re-score still counts twice in a median where it belongs. Omitted, the counts
 * come off the rows exactly as before, which is what the browser oracle and the
 * shared console layout pass.
 *
 * Rows carrying no date are dropped rather than pooled into an empty day: a
 * ledger row with no day is a broken row, and giving it a column would draw it.
 */
export function evalDays(
	rows: readonly EvalInput[],
	leadFloor: number,
	counts?: ReadonlyMap<string, DayScoredCounts>
): EvalDay[] {
	const byDate = new Map<string, EvalInput[]>();
	for (const row of rows) {
		const date = (row.date ?? '').trim();
		if (date === '') continue;
		const found = byDate.get(date);
		if (found) found.push(row);
		else byDate.set(date, [row]);
	}

	const days: EvalDay[] = [];
	for (const date of [...byDate.keys()].sort()) {
		const group = byDate.get(date) ?? [];
		const match: number[] = [];
		const lead: number[] = [];
		let widerDiffers = 0;
		let widestGap = 0;
		let leadUnder = 0;
		const recordedValues = new Map<string, number[]>();
		for (const instrument of RECORDED) recordedValues.set(instrument.id, []);
		const fired: Record<string, number> = {};
		for (const instrument of FLAGS) fired[instrument.id] = 0;

		for (const row of group) {
			const hhem = measured(row.hhem);
			if (hhem !== null) match.push(hhem);
			const delta = measured(row.hhem_delta);
			if (delta !== null && delta !== 0) {
				widerDiffers += 1;
				widestGap = Math.max(widestGap, Math.abs(delta));
			}
			const coverage = measured(row.coverage);
			if (coverage !== null) {
				lead.push(coverage);
				if (coverage < leadFloor) leadUnder += 1;
			}
			for (const instrument of RECORDED) {
				const value = measured(row[instrument.id]);
				if (value !== null) recordedValues.get(instrument.id)?.push(value);
			}
			for (const instrument of FLAGS) {
				if (flag(row[instrument.id])) fired[instrument.id] += 1;
			}
		}

		match.sort((a, b) => a - b);
		lead.sort((a, b) => a - b);
		// The published-set counts, where a run settled them. A flag fires on a
		// distinct published item, not on a ledger row, so a re-scored day counts
		// it once here even though its two rows still both enter the distributions
		// above. Absent, the row counts stand exactly as they did.
		const settled = counts?.get(date);
		if (settled !== undefined) {
			fired.determinism_violation = settled.determinismViolations;
			fired.extraction_suspect = settled.extractionSuspect;
		}
		const recorded: Record<string, number | null> = {};
		for (const instrument of RECORDED) {
			const values = (recordedValues.get(instrument.id) ?? []).sort((a, b) => a - b);
			recorded[instrument.id] =
				values.length === 0
					? null
					: instrument.unit === 'percent'
						? pct(at(values, 0.5))
						: perThousand(at(values, 0.5));
		}

		days.push({
			date,
			// The distinct-published count where the run settled one, the ledger-row
			// count otherwise. A re-scored item keeps two rows and a scored-then-
			// dropped item keeps one, so the row count is not the count of summaries
			// the day published (backend/idhazh/publish_day_metrics.py).
			scored: settled?.scored ?? group.length,
			matched: match.length,
			matchLow: match.length === 0 ? null : pct(at(match, 0.25)),
			matchMid: match.length === 0 ? null : pct(at(match, 0.5)),
			matchHigh: match.length === 0 ? null : pct(at(match, 0.75)),
			widerDiffers,
			widestGap: pct(widestGap),
			led: lead.length,
			leadMid: lead.length === 0 ? null : pct(at(lead, 0.5)),
			leadUnder,
			leadUnderPct: lead.length === 0 ? null : Math.round((leadUnder / lead.length) * 100),
			recorded,
			fired
		});
	}
	return days;
}

export function evalWithin(
	days: readonly EvalDay[],
	span: { start: string; end: string }
): EvalDay[] {
	return days.filter((day) => day.date >= span.start && day.date <= span.end);
}

// --- How often a key point adds a fact, by length band ----------------------
//
// `new_fact_rate` is a per-item share on the eval row, recorded and acted on by
// nothing (the standing trap: best-of-N against it is the Goodhart form of the
// number). It is bucketed by the SummaryBand the article fell in, because the
// shortest band asks for one key point and the longest for five, so redundancy
// is structural at the short end and one pooled figure would hide it. `bandFor`
// reads the same length ladder the summarizer wrote the item under.
//
// The item count and the summed rate ride per day, never the rate itself: a rate
// averaged across days is meaningless, so the window sums the parts and divides
// once. One small object a day over the ladder's rungs, so a wider window filters
// this array and re-aggregates nothing - the same shape `evalDays` keeps.

export interface NewFactDay {
	date: string;
	byBand: Readonly<Record<string, { items: number; sum: number }>>;
}

export function newFactDays(
	rows: readonly EvalInput[],
	bands: readonly SummaryBand[]
): NewFactDay[] {
	const byDate = new Map<string, EvalInput[]>();
	for (const row of rows) {
		const date = (row.date ?? '').trim();
		if (date === '') continue;
		const found = byDate.get(date);
		if (found) found.push(row);
		else byDate.set(date, [row]);
	}

	const days: NewFactDay[] = [];
	for (const date of [...byDate.keys()].sort()) {
		const byBand: Record<string, { items: number; sum: number }> = {};
		for (const row of byDate.get(date) ?? []) {
			const rate = measured(row.new_fact_rate);
			if (rate === null) continue;
			// The length the band was chosen on, pre-cap where the row still knows it,
			// falling back to what the model saw - the same order `band_source_words`
			// reads on the producing side.
			const words = measured(row.source_word_count) ?? measured(row.source_seen_word_count);
			if (words === null) continue;
			const band = bandFor(bands, words);
			if (band === null) continue;
			const key = String(band.min_source_words);
			const bucket = byBand[key] ?? { items: 0, sum: 0 };
			bucket.items += 1;
			bucket.sum += rate;
			byBand[key] = bucket;
		}
		days.push({ date, byBand });
	}
	return days;
}

export function newFactWithin(
	days: readonly NewFactDay[],
	span: { start: string; end: string }
): NewFactDay[] {
	return days.filter((day) => day.date >= span.start && day.date <= span.end);
}

/** One band's reading over a window: the typical item's share of key points that
 * add a fact, and how many items that is out of. */
export interface NewFactReading {
	/** The band's floor word count as a string - the stable key across days. */
	key: string;
	/** The length range a reader sees, e.g. "700-1,999 words". */
	label: string;
	/** Items in the window that fell in this band and carried a rate. */
	items: number;
	/** The average of those items' shares, whole percent, or null where the band
	 * held no item in the window. */
	rate: number | null;
}

export function newFactBands(
	days: readonly NewFactDay[],
	bands: readonly SummaryBand[]
): NewFactReading[] {
	const totals = new Map<string, { items: number; sum: number }>();
	for (const day of days) {
		for (const [key, bucket] of Object.entries(day.byBand)) {
			const running = totals.get(key) ?? { items: 0, sum: 0 };
			running.items += bucket.items;
			running.sum += bucket.sum;
			totals.set(key, running);
		}
	}

	const sorted = [...bands].sort((a, b) => a.min_source_words - b.min_source_words);
	return sorted.map((band, index) => {
		const key = String(band.min_source_words);
		const next = sorted[index + 1];
		const label =
			next === undefined
				? `${grouped(band.min_source_words)}+ words`
				: `${grouped(band.min_source_words)}-${grouped(next.min_source_words - 1)} words`;
		const running = totals.get(key);
		return {
			key,
			label,
			items: running?.items ?? 0,
			rate: running && running.items > 0 ? pct(running.sum / running.items) : null
		};
	});
}

/** The days that carry a faithfulness reading, which is what the plot draws. */
export function matchDays(days: readonly EvalDay[]): EvalDay[] {
	return days.filter((day) => day.matchMid !== null);
}

/** The days that carry a lead-coverage reading. */
export function leadDays(days: readonly EvalDay[]): EvalDay[] {
	return days.filter((day) => day.leadUnderPct !== null);
}

export function evalColumnLabels(days: readonly EvalDay[]): string[] {
	return days.map((day) => dayMonth(day.date));
}

/** The two faithfulness lines, for `stacked()` in its `lines` shape.
 *
 * Two and not five. The middle summary says the level and a quarter below it
 * says the tail, and the tail is the half of the pair that moves: measured
 * 2026-09-06 over the fifteen committed days, the middle sat between 88 and 95
 * percent while the lower quarter swung from 73 to 94.
 *
 * Never stacked. Adding one percentile to another is not a quantity, so the page
 * fixes the shape to lines and offers no switch - the rule `stacked()` states
 * for carrying that switch is that both shapes read the same array honestly, and
 * these do not.
 */
export function matchSeries(days: readonly EvalDay[]): StackSeries[] {
	return [
		{
			label: 'Half of them scored above',
			token: '--chart-6',
			values: days.map((day) => day.matchMid ?? 0)
		},
		{
			label: 'A quarter scored below',
			token: '--chart-7',
			values: days.map((day) => day.matchLow ?? 0)
		}
	];
}

export function matchColumns(days: readonly EvalDay[]): DayReadout[] {
	return days.map((day) => ({
		x: 0,
		date: day.date,
		rows: [
			{
				label: 'Half of them scored above',
				value: `${day.matchMid}%`,
				colour: 'var(--chart-6)'
			},
			{
				label: 'A quarter scored below',
				value: `${day.matchLow}%`,
				colour: 'var(--chart-7)'
			},
			{
				label: 'Summaries checked',
				value: grouped(day.matched),
				colour: 'var(--chart-marker)'
			}
		]
	}));
}

/** One line: the share of a day's summaries that kept too little of the opening.
 *
 * The middle summary's kept share is in the strip and the headline instead. It
 * barely moves - measured 2026-09-06, every one of the fifteen committed days
 * sat between 57 and 64 percent - and a flat line drawn beside a moving one
 * reads as the important one.
 */
export function leadSeries(days: readonly EvalDay[]): StackSeries[] {
	return [
		{
			label: 'Kept too little of the opening',
			token: '--chart-8',
			values: days.map((day) => day.leadUnderPct ?? 0)
		}
	];
}

export function leadColumns(days: readonly EvalDay[]): DayReadout[] {
	return days.map((day) => ({
		x: 0,
		date: day.date,
		rows: [
			{
				label: 'Kept too little of the opening',
				value: `${grouped(day.leadUnder)} of ${grouped(day.led)}`,
				colour: 'var(--chart-8)'
			},
			{
				label: 'The middle summary kept',
				value: `${day.leadMid}%`,
				colour: 'var(--chart-marker)'
			}
		]
	}));
}

/** What the whole window holds, so a sentence never re-walks the days itself. */
export interface EvalTotals {
	days: number;
	scored: number;
	matched: number;
	led: number;
	leadUnder: number;
	widerDiffers: number;
	widestGap: number;
}

export function evalTotals(days: readonly EvalDay[]): EvalTotals {
	let scored = 0;
	let matched = 0;
	let led = 0;
	let leadUnder = 0;
	let widerDiffers = 0;
	let widestGap = 0;
	for (const day of days) {
		scored += day.scored;
		matched += day.matched;
		led += day.led;
		leadUnder += day.leadUnder;
		widerDiffers += day.widerDiffers;
		widestGap = Math.max(widestGap, day.widestGap);
	}
	return { days: days.length, scored, matched, led, leadUnder, widerDiffers, widestGap };
}

/** The middle day of the window, by its own middle summary. */
function middleDay(values: readonly (number | null)[]): number | null {
	const known = values.filter((value): value is number => value !== null).sort((a, b) => a - b);
	return known.length === 0 ? null : at(known, 0.5);
}

export function matchHeadline(days: readonly EvalDay[], windowDays: number): string | null {
	const drawn = matchDays(days);
	if (drawn.length === 0) return null;
	const mid = middleDay(drawn.map((day) => day.matchMid));
	const low = middleDay(drawn.map((day) => day.matchLow));
	if (mid === null || low === null) return null;
	const totals = evalTotals(days);
	return `Over these ${windowDays} days the middle day put half its summaries above ${mid} percent, and a quarter of them under ${low} percent, on ${grouped(totals.matched)} summaries checked.`;
}

/** What the second faithfulness column says, in words.
 *
 * The checker scores the summary twice - once against the text the machine was
 * given, once against the whole article - and the second column exists so a
 * summary that only looks faithful because the article was cut cannot pass. The
 * gap between them is the reading, so the panel says how often there is one.
 */
export function widerNote(days: readonly EvalDay[], windowDays: number): string | null {
	const totals = evalTotals(days);
	if (totals.matched === 0) return null;
	if (totals.widerDiffers === 0) {
		return `Scored against the whole article instead of the part the machine read, every one of these ${grouped(totals.matched)} summaries scores the same. The two readings only part when the article was cut.`;
	}
	return `Scored against the whole article instead of the part the machine read, ${grouped(totals.widerDiffers)} of these ${grouped(totals.matched)} summaries score differently, by up to ${totals.widestGap} points.`;
}

export function leadHeadline(days: readonly EvalDay[], windowDays: number): string | null {
	const drawn = leadDays(days);
	if (drawn.length === 0) return null;
	const mid = middleDay(drawn.map((day) => day.leadMid));
	if (mid === null) return null;
	return `Over these ${windowDays} days the middle summary carried ${mid} percent of the names and figures in its article's opening lines.`;
}

/** What falling under the floor costs a summary, said once, in the panel it governs.
 *
 * The floor is a cap and not a bar: falling under it holds a summary at "fairly
 * sure" and cannot on its own mark one "not sure". A panel that drew it as a
 * failure line would be reporting a verdict the checker does not reach.
 *
 * Stated as the rule rather than as a record. "has never marked one" says the
 * same thing over every day there has ever been, which is a span this panel
 * reads none of - and it is the weaker sentence anyway, because it reports a
 * run of luck where the arithmetic gives a guarantee.
 */
export function leadFloorNote(
	days: readonly EvalDay[],
	windowDays: number,
	leadFloor: number
): string | null {
	const totals = evalTotals(days);
	if (totals.led === 0) return null;
	return `${grouped(totals.leadUnder)} of ${grouped(totals.led)} summaries in these ${windowDays} days kept under ${pct(leadFloor)} percent. That holds a summary at "fairly sure" and cannot on its own mark one "not sure".`;
}

/** One recorded instrument over the window. */
export interface RecordedReading extends RecordedInstrument {
	/** The quietest day, the middle day and the loudest day, each by its own middle summary. */
	low: number | null;
	mid: number | null;
	high: number | null;
	/** Days in the window that carried a reading at all. */
	days: number;
}

/** A day range rather than a window median, because the second cannot be had.
 *
 * A median over the window needs every summary's number, and carrying 6,966 of
 * them into the page to print four figures is not a trade worth making. The
 * middle day's own middle summary, with the quietest and loudest day beside it,
 * is exact, costs one number a day, and says more than a single median would.
 */
export function recordedReadings(days: readonly EvalDay[]): RecordedReading[] {
	return RECORDED.map((instrument) => {
		const known = days
			.map((day) => day.recorded[instrument.id] ?? null)
			.filter((value): value is number => value !== null)
			.sort((a, b) => a - b);
		return {
			...instrument,
			low: known.length === 0 ? null : known[0],
			mid: known.length === 0 ? null : at(known, 0.5),
			high: known.length === 0 ? null : known[known.length - 1],
			days: known.length
		};
	});
}

/** One flag over the window. */
export interface FlagReading extends FlagInstrument {
	fired: number;
	of: number;
}

export function flagReadings(days: readonly EvalDay[]): FlagReading[] {
	const totals = evalTotals(days);
	return FLAGS.map((instrument) => ({
		...instrument,
		fired: days.reduce((sum, day) => sum + (day.fired[instrument.id] ?? 0), 0),
		of: totals.scored
	}));
}

/** How a recorded reading is written, unit included, or a dash where there is none. */
export function recordedText(reading: RecordedReading, value: number | null): string {
	if (value === null) return '-';
	return reading.unit === 'percent' ? `${value}%` : `${value.toFixed(1)} per 1,000 words`;
}
