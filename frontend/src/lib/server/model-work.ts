/** What the summarizer did on one day's own articles, and what the cap cost.
 *
 * Every figure is a count of that day's items. Nothing here is a score: a value
 * between zero and one names nothing an operator can pull, so the scorer's own
 * numbers stay in `state/scores.csv` and only their consequences reach the
 * screen. `copiedPct` is the one share on the page and it leaves here already
 * multiplied out, so a raw ratio has no route to the markup.
 *
 * The source table lives here too rather than in a module of its own: it reads
 * the same two ledgers, and it needs the same one definition of what a cut is.
 * Two definitions of a cut on one page is how the page starts disagreeing with
 * itself.
 *
 * `null` is a designed state and it is not zero. A day the scorer never ran on
 * has summaries nobody counted, a day whose runtime wrote no timing spent no
 * *measured* time, and a day whose rows predate a column's redefinition holds
 * no answer to the question the column asks now; printing any of the three as
 * zero would say the model did nothing.
 *
 * Imports nothing at runtime: the browser suite loads this module in plain
 * Node, where no Vite alias resolves, and it reads the same ledgers the page
 * reads. The one import below is a type, which the compiler erases, and it is
 * written relative for the same reason.
 */

import type { SummaryBand } from './config';

/** The ledger stamp from which `truncation_flagged` means extract cut the body.
 *
 * A row stamped before this carries the same column under an older meaning: the
 * gap between two faithfulness scores. That is a different fact about a
 * different thing, so the two cannot be added together - one number over two
 * questions is not a count. A day made only of older rows therefore reads as
 * unknown.
 *
 * The stamp compared is the row's own `version` cell, the date-stamp
 * `CLAUDE.md` section 11 puts on every persisted shape. That format is
 * ASCII-sortable on purpose, so a plain string compare orders a stamp carrying
 * a time correctly against a bare date: `2026-08-27T20:30` is before
 * `2026-08-28`, and `2026-08-28T09:00` is after it. A row with no stamp at all
 * reads as older, which is the safe direction.
 *
 * Not a config knob. It records when a shipped column changed meaning, and a
 * run that moved it would make the page lie about rows already committed.
 */
export const CUT_FLAG_MEANS_A_CUT_FROM = '2026-08-28';

/** One day, as the two committed ledgers describe it. */
export interface ModelDay {
	date: string;
	/** Rows the score ledger holds for the day. Null where it holds none. */
	summaries: number | null;
	/** Summaries we told a reader not to trust - the lowest confidence band. */
	notSure: number | null;
	/** Summaries asserting a figure the article never gave. */
	unsupportedNumbers: number | null;
	/** Summaries that turned the article's "might" into "did". */
	hedgeDropped: number | null;
	/** Summaries written from the start of an article extract cut short.
	 *
	 * Counted over the day's rows stamped `CUT_FLAG_MEANS_A_CUT_FROM` or later,
	 * and null where the day holds none of those. An older row's flag answers a
	 * different question, so it is not counted and not read as a zero.
	 */
	readInPart: number | null;
	/** The same articles as a share of the day's own count, as whole percent.
	 *
	 * The denominator is the rows the flag still means something on, never the
	 * day's whole ledger: a share whose top and bottom answer two questions is
	 * not a share. Null wherever `readInPart` is.
	 *
	 * It ships per day and never per run. Measured 2026-08-29 over 19 committed
	 * runs the count is 1 to 12 cuts of 160 to 200 items, and that swing is the
	 * article mix on the run rather than anything the cap did.
	 */
	readInPartPct: number | null;
	/** The summaries the two figures above are out of.
	 *
	 * The share's own denominator, carried rather than inferred. In a table it
	 * sat one column away on the same row; on a card there is no row, and a share
	 * whose denominator is off the screen invites a trend that is not there.
	 *
	 * It is the rows the flag still answers for, never the day's whole ledger, so
	 * it can read lower than `summaries` on a day holding rows from both sides of
	 * `CUT_FLAG_MEANS_A_CUT_FROM`. Null wherever `readInPart` is.
	 */
	readInPartOf: number | null;
	/** Median share of a summary lifted word for word, as whole percent. */
	copiedPct: number | null;
	/** Median milliseconds the model spent writing one summary. */
	perItemMs: number | null;
	/** The same median over the articles that were cut short.
	 *
	 * A cut article is the longest prompt the machine sees, so this is the figure
	 * that says whether raising the cap still leaves the day inside its gap
	 * between runs. Null where the day cut nothing the runtime timed.
	 */
	perItemCutMs: number | null;
	/** Every millisecond the model spent that day. */
	totalMs: number | null;
	/** Items the model refused because the whole prompt did not fit.
	 *
	 * Null where no health row exists. Zero is a measurement here and is the
	 * expected reading: at a cap of 2,500 tokens no prompt can reach the window,
	 * so anything above zero says the cap moved past what the machine can read.
	 */
	refusedForLength: number | null;
	/** Items whose run ended in a failure. Null where no health row exists. */
	failed: number | null;
	/** Every model id the day's score rows name, so a swap can be spotted. */
	models: string[];
}

/** A day, or the divider that marks the day the model changed.
 *
 * The divider carries a date and an id and nothing else. An arrow or a delta
 * across it would claim the swap caused whatever moved, which no committed
 * figure supports.
 */
export type ModelRow =
	| { kind: 'day'; day: ModelDay }
	| { kind: 'swap'; date: string; model: string };

/** Python writes `True` and `False`; a hand-written fixture may write either. */
function flag(value: string | undefined): boolean {
	return value === 'True' || value === 'true';
}

function measured(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

function median(values: number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function byDate(rows: Record<string, string>[]): Map<string, Record<string, string>[]> {
	const grouped = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const date = row.date ?? '';
		if (!date) continue;
		grouped.set(date, [...(grouped.get(date) ?? []), row]);
	}
	return grouped;
}

/** Every millisecond the day's runtime wrote down for the summarize stage. */
function summarizeMs(health: Record<string, string>[]): number[] {
	return health
		.map((row) => measured(row.summarize_ms))
		.filter((ms): ms is number => ms !== null && ms > 0);
}
/** How much of one summary was lifted word for word.
 *
 * The larger of the two copying measures, because they miss opposite things: a
 * summary can score low on scattered four-word overlap and still lift one whole
 * paragraph. Taking the larger cannot under-report copying, which is the only
 * direction that matters here.
 */
function copied(row: Record<string, string>): number {
	return Math.max(measured(row.extractiveness) ?? 0, measured(row.verbatim_run) ?? 0);
}

function day(
	date: string,
	scores: Record<string, string>[],
	health: Record<string, string>[]
): ModelDay {
	const scored = scores.length > 0;
	const times = summarizeMs(health);
	const share = median(scores.map(copied));
	const count = (of: (row: Record<string, string>) => boolean) =>
		scored ? scores.filter(of).length : null;
	// Only the rows whose cut flag still means a cut. The rest answer an older
	// question, so they are excluded from the count rather than folded into it.
	const cutKnown = scores.filter((row) => (row.version ?? '') >= CUT_FLAG_MEANS_A_CUT_FROM);
	const readInPart =
		cutKnown.length === 0 ? null : cutKnown.filter((row) => flag(row.truncation_flagged)).length;
	return {
		date,
		summaries: scored ? scores.length : null,
		notSure: count((row) => row.band === 'low'),
		unsupportedNumbers: count((row) => (measured(row.unsupported_numbers) ?? 0) > 0),
		hedgeDropped: count((row) => flag(row.hedge_dropped)),
		readInPart,
		// Over the rows the flag still answers for, not over the day. Dividing by
		// the whole ledger would shrink the share by however many older rows the
		// day happens to carry, which is a property of the migration and not of
		// the articles.
		readInPartPct:
			readInPart === null ? null : Math.round((readInPart / cutKnown.length) * 100),
		readInPartOf: readInPart === null ? null : cutKnown.length,
		copiedPct: share === null ? null : Math.round(share * 100),
		perItemMs: median(times),
		perItemCutMs: median(summarizeMs(health.filter(wasCut))),
		totalMs: times.length === 0 ? null : times.reduce((total, ms) => total + ms, 0),
		refusedForLength:
			health.length === 0 ? null : health.filter((row) => row.code === 'context_exceeded').length,
		failed: health.length === 0 ? null : health.filter((row) => row.outcome === 'failed').length,
		models: [...new Set(scores.map((row) => row.model_id ?? '').filter((id) => id !== ''))].sort()
	};
}

/** A divider wherever two neighbouring days name different models.
 *
 * Days arrive newest first, so the divider is pushed after the newer of the
 * pair: everything above the line ran on the id the line names. A day whose
 * model is unknown ends the comparison rather than inventing a swap.
 */
function withSwaps(days: ModelDay[]): ModelRow[] {
	const rows: ModelRow[] = [];
	days.forEach((newer, index) => {
		rows.push({ kind: 'day', day: newer });
		const older = days[index + 1];
		if (older === undefined) return;
		if (newer.models.length === 0 || older.models.length === 0) return;
		if (newer.models.join(' ') === older.models.join(' ')) return;
		rows.push({ kind: 'swap', date: newer.date, model: newer.models.join(', ') });
	});
	return rows;
}

/** One row per day the model worked, newest first.
 *
 * A day earns a row by having summaries: score rows, or a runtime that timed
 * the summarize stage. A day the pipeline found no article on gets no row at
 * all, because a row of zeroes reads as a day that went badly rather than a day
 * with nothing in it.
 */
export function modelWork(
	scores: Record<string, string>[],
	health: Record<string, string>[]
): ModelRow[] {
	const scored = byDate(scores);
	const worked = byDate(health);
	const ran = [...worked.entries()]
		.filter(([, rows]) => summarizeMs(rows).length > 0)
		.map(([date]) => date);
	const dates = [...new Set([...scored.keys(), ...ran])].sort().reverse();
	return withSwaps(
		dates.map((date) => day(date, scored.get(date) ?? [], worked.get(date) ?? []))
	);
}

/** The model id each date's score rows name, for the days that name one.
 *
 * The candle needs it to know when two days ran on different models and must
 * not be compared. It is read from the score ledger rather than the item-health
 * ledger, which records no model at all.
 */
export function modelByDate(scores: Record<string, string>[]): Map<string, string> {
	const found = new Map<string, string>();
	for (const [date, rows] of byDate(scores)) {
		const ids = [...new Set(rows.map((row) => row.model_id ?? '').filter((id) => id !== ''))].sort();
		if (ids.length > 0) found.set(date, ids.join(', '));
	}
	return found;
}

/** How long the article was before the cap cut it, against how long it stayed.
 *
 * The cut is the comparison between two cells of one row and nothing else. The
 * alternative was testing the post-cap count against the cap itself, which
 * moves whenever the cap moves - so a window spanning a cap change mixes two
 * cut points, and an article whose body happens to end on the boundary reads as
 * cut. See `docs/architecture/sources/item-health.md`.
 *
 * An empty cell is not a zero. A run before 2026-08-28 measured no length at
 * all, and reading that as zero would call every one of its articles cut.
 */
export function cutWords(before: number | null, after: number | null): number | null {
	if (before === null || after === null || before <= after) return null;
	return before - after;
}

/** The same test against one item-health row. */
export function wasCut(row: Record<string, string>): boolean {
	return cutWords(measured(row.source_words_before_cap), measured(row.source_words)) !== null;
}

/** One article, however many runs wrote a row for it.
 *
 * A row is one item on one run, so counting rows counts a re-run twice and the
 * table's own sentence says "how many articles". The run that read the most of
 * an article is the one kept, and the pair of lengths stays on that one row -
 * a `before` from one run against an `after` from another is not a measurement
 * of anything.
 */
interface Article {
	sourceId: string;
	/** The day the kept row was written. It dates the cut point, never the
	 * article: two runs of one day read the same body. */
	date: string;
	before: number | null;
	after: number | null;
}

/** The spread of one source's article lengths, in words.
 *
 * Three numbers rather than an average. The reason a source is on this list is
 * its long tail, and a mean length hides exactly that: two sources averaging
 * 1,400 words are a different problem when one of them never passes 2,000 and
 * the other reaches 30,000.
 *
 * Taken over the articles a run measured before the cut. A row that recorded no
 * length is left out rather than counted as an article of no length.
 */
export interface LengthRange {
	min: number;
	median: number;
	max: number;
}

/** What the cap cost one source over the window. */
export interface SourceCut {
	sourceId: string;
	/** Articles this source lost text on. */
	cut: number;
	/** Articles this source published, cut or not. The denominator. */
	articles: number;
	/** Where this source's measured articles sit on the length axis.
	 *
	 * Always present: a source reaches this list only by having a cut article,
	 * and a cut is two recorded lengths compared, so at least one length exists.
	 */
	lengths: LengthRange;
}

/** What the cut removed, over the articles it removed anything from. */
export interface CutCost {
	n: number;
	median: number;
	max: number;
}

/** One cut point, and the days it was the cut in force.
 *
 * The same shape the compression plot's cap lines carry, so one label writer
 * serves both drawings.
 */
export interface CapPoint {
	words: number;
	first: string;
	last: string;
}

/** The source table, and the two sentences under it. */
export interface SourceCuts {
	/** The worst sources by article count, longest list first. */
	rows: SourceCut[];
	/** Sources the list did not reach, and the cuts they hold between them. */
	moreSources: number;
	moreCuts: number;
	/** True once any row in the window recorded a length before the cut.
	 *
	 * False and "no article was cut" are different states: one says the ledger
	 * cannot answer yet, the other says it answered no.
	 */
	measured: boolean;
	cost: CutCost | null;
	/** Where the cut fell, read off the articles that were cut.
	 *
	 * One entry per distinct post-cap length in the window, oldest first - the
	 * same rule the compression plot reads its own lines by, so the two
	 * drawings of one fact cannot disagree. A window can span a change to
	 * `extract.truncation_cap_tokens`, and over the committed ledger a thirty-day
	 * one does: rows cut at 1,923 words sit beside rows cut at 3,846.
	 *
	 * Derived from the same two cells `cutWords` compares and never from the
	 * setting behind them. The direction that matters is the other one - a
	 * setting-derived rule draws even when nothing in the window was cut at all,
	 * and this one cannot.
	 */
	caps: CapPoint[];
	days: number;
	/** Every article in the window, cut or not.
	 *
	 * The denominator. At a seven-day window it runs as low as six articles, and
	 * a table of shares over six articles has to say so or it reads like a rate. */
	articles: number;
}

/** How many sources the table names.
 *
 * Measured 2026-08-29 over the committed ledger: 46 sources lost an article in
 * a seven-day window and the worst seven hold 69 of 153 cuts, 45 percent. Past
 * ten the tail is sources with a single cut, and one cut in a week is not
 * something an operator does anything about.
 */
export const SOURCE_CUT_ROWS = 10;

/** How much the cap is costing, by source, over the window the page is showing.
 *
 * Sorted by how many articles it cost each source, never by the share. Measured
 * 2026-08-29 over the committed ledger, the shares run 3 to 67 percent on
 * denominators of 6 to 38 articles, so a share sort puts a source with 4 cuts
 * of 6 above one with 17 of 38 - and it is the seventeen that cost the digest
 * the articles.
 *
 * The window ends on the newest day the ledger holds rather than on the build
 * clock, so the table says the same thing on a rebuild of an old tree as it did
 * the day that tree was written. That is also why panning the telemetry
 * viewport does not move this table: it follows the window's length, and the
 * section says so.
 */
export function sourceCuts(
	health: Record<string, string>[],
	options: { days: number; limit: number }
): SourceCuts {
	const dates = health.map((row) => row.date ?? '').filter((date) => date !== '');
	const newest = dates.length === 0 ? '' : dates.reduce((a, b) => (a > b ? a : b));
	const first = windowStart(newest, options.days);
	const inWindow = health.filter((row) => (row.date ?? '') >= first && (row.date ?? '') <= newest);

	const articles = new Map<string, Article>();
	for (const row of inWindow) {
		const sourceId = row.source_id ?? '';
		if (sourceId === '') continue;
		// `url_key` is the stable article key; `item_id` is derived from the
		// address and is only stable within a day. Joining on the wrong one
		// merges two articles or splits one.
		const key = `${sourceId}\u0000${row.url_key ?? row.item_id ?? ''}`;
		const before = measured(row.source_words_before_cap);
		const held = articles.get(key);
		if (held === undefined) {
			articles.set(key, {
				sourceId,
				date: row.date ?? '',
				before,
				after: measured(row.source_words)
			});
			continue;
		}
		if (before !== null && (held.before === null || before > held.before)) {
			held.before = before;
			held.after = measured(row.source_words);
			held.date = row.date ?? '';
		}
	}

	const bySource = new Map<string, Article[]>();
	for (const article of articles.values()) {
		bySource.set(article.sourceId, [...(bySource.get(article.sourceId) ?? []), article]);
	}

	const lost: number[] = [];
	const found: SourceCut[] = [];
	for (const [sourceId, group] of bySource) {
		const cut = group
			.map((article) => cutWords(article.before, article.after))
			.filter((words): words is number => words !== null);
		if (cut.length === 0) continue;
		lost.push(...cut);
		const lengths = group
			.map((article) => article.before)
			.filter((words): words is number => words !== null);
		found.push({
			sourceId,
			cut: cut.length,
			articles: group.length,
			lengths: spread(lengths)
		});
	}

	found.sort((a, b) => b.cut - a.cut || a.sourceId.localeCompare(b.sourceId));
	const rows = found.slice(0, options.limit);
	const rest = found.slice(options.limit);
	const sorted = [...lost].sort((a, b) => a - b);

	return {
		rows,
		moreSources: rest.length,
		moreCuts: rest.reduce((total, source) => total + source.cut, 0),
		measured: inWindow.some((row) => measured(row.source_words_before_cap) !== null),
		cost:
			sorted.length === 0
				? null
				: {
						n: sorted.length,
						median: sorted[Math.floor(sorted.length / 2)],
						max: sorted[sorted.length - 1]
					},
		// Over every article in the window, including the sources the list did not
		// reach: the cut point is a fact about the window, not about ten rows.
		caps: capPoints([...articles.values()]),
		days: options.days,
		articles: articles.size
	};
}

/** One entry per distinct post-cap length among the cut articles, oldest first.
 *
 * Read straight off the articles rather than off the compression plot's points.
 * It is written out here rather than imported because this module imports
 * nothing at runtime, and so that retiring that plot cannot take this rule with
 * it.
 */
function capPoints(articles: Article[]): CapPoint[] {
	const spans = new Map<number, { first: string; last: string }>();
	for (const article of articles) {
		if (cutWords(article.before, article.after) === null) continue;
		const words = article.after as number;
		const span = spans.get(words);
		if (span === undefined) {
			spans.set(words, { first: article.date, last: article.date });
			continue;
		}
		if (article.date < span.first) span.first = article.date;
		if (article.date > span.last) span.last = article.date;
	}
	return [...spans.entries()]
		.map(([words, span]) => ({ words, first: span.first, last: span.last }))
		.sort((a, b) => a.first.localeCompare(b.first) || a.words - b.words);
}

/** The shortest, the middle and the longest of a set of lengths.
 *
 * The median is rounded to a whole word. Two middles averaged can land on a
 * half, and the console prints no decimal anywhere - half a word is not a
 * length anybody can act on.
 */
function spread(values: number[]): LengthRange {
	const sorted = [...values].sort((a, b) => a - b);
	const middle = median(sorted);
	return {
		min: sorted[0] ?? 0,
		median: middle === null ? 0 : Math.round(middle),
		max: sorted[sorted.length - 1] ?? 0
	};
}

function windowStart(end: string, days: number): string {
	if (end === '') return '';
	const at = new Date(`${end}T00:00:00Z`);
	at.setUTCDate(at.getUTCDate() - (days - 1));
	return at.toISOString().slice(0, 10);
}

/** A span of days, named once and passed to every panel that draws it.
 *
 * The page decides where a window starts and ends - one control, one answer -
 * and a panel is handed the answer rather than working it out again. Two
 * panels on one screen deriving the same span two ways is how they start
 * disagreeing about which days they drew.
 */
export interface DayWindow {
	start: string;
	end: string;
	days: number;
}

function within(rows: Record<string, string>[], window: DayWindow): Record<string, string>[] {
	return rows.filter((row) => {
		const date = row.date ?? '';
		return date >= window.start && date <= window.end;
	});
}

function quantile(sorted: number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** One bar of the write-time histogram.
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
	/** Every article written in `to` seconds or less, as whole percent. */
	throughPct: number;
}

/** How long one summary took, over every article the runtime timed in a window.
 *
 * The median and the 95th are taken over the values themselves and never off
 * the bars: a percentile read out of a bin is a guess at where inside the bin
 * it fell, and the two rules on this chart are the figures somebody quotes.
 *
 * One entry per timed attempt, not per article - the same rows the `Time to
 * write one` card takes its median over. A re-run really did spend the time
 * again, and a chart of what the machine spent that counts a second attempt
 * once would not add up to the model minutes printed beside it.
 */
export interface WriteTimes {
	bins: WriteBin[];
	/** Articles behind the chart. The denominator for every bar. */
	n: number;
	/** Milliseconds. */
	median: number;
	p95: number;
	slowest: number;
	fastest: number;
	/** The days the window covers, and the days in it that timed anything. */
	days: number;
	timedDays: number;
	start: string;
	end: string;
}

/** The bars, the two rules and the counts behind them, or null for a window the
 * runtime timed nothing in.
 *
 * Null is the empty state and it is not a chart of zeroes. A window with no
 * timing did not run fast; nothing measured it.
 */
export function writeTimes(
	health: Record<string, string>[],
	window: DayWindow
): WriteTimes | null {
	const rows = within(health, window);
	const values = summarizeMs(rows).sort((a, b) => a - b);
	if (values.length === 0) return null;

	// The first edge is one second, so every label on the axis is a whole
	// number. Everything below it shares one bar, labelled the way the console
	// spells a measurement that rounds away.
	const top = Math.max(1, values[values.length - 1] / 1000);
	const edges = [0, 1];
	while (edges[edges.length - 1] <= top) edges.push(edges[edges.length - 1] * 2);

	const bins: WriteBin[] = [];
	let through = 0;
	for (let index = 0; index < edges.length - 1; index += 1) {
		const from = edges[index];
		const to = edges[index + 1];
		const n = values.filter((ms) => ms / 1000 >= from && ms / 1000 < to).length;
		through += n;
		bins.push({ from, to, n, throughPct: Math.round((through / values.length) * 100) });
	}

	// Leading and trailing empty bars are axis, not data. A gap between two
	// occupied bars stays: it is the distribution saying nothing landed there.
	const first = bins.findIndex((bin) => bin.n > 0);
	const last = bins.length - 1 - [...bins].reverse().findIndex((bin) => bin.n > 0);

	return {
		bins: bins.slice(first, last + 1),
		n: values.length,
		median: quantile(values, 0.5),
		p95: quantile(values, 0.95),
		slowest: values[values.length - 1],
		fastest: values[0],
		days: window.days,
		timedDays: new Set(
			rows.filter((row) => (measured(row.summarize_ms) ?? 0) > 0).map((row) => row.date ?? '')
		).size,
		start: window.start,
		end: window.end
	};
}

/** What scoring one summary cost, after the summary was written.
 *
 * It is not a stage of the run. The scorer reads a summary the model has
 * already finished, so nothing waits on it - which is why it is here and not
 * beside fetch, extract and summarize, where a fourth bar read as a fourth
 * constraint.
 */
export interface ScoreCost {
	/** Summaries the scorer timed. */
	n: number;
	/** Milliseconds. */
	median: number;
	p95: number;
	/** Rows carrying the zero the column defaulted to before it was written.
	 *
	 * Not a measurement of no time: they are rows the scorer never timed, and
	 * they are left out of the figures rather than counted as instant.
	 */
	untimed: number;
	days: number;
	start: string;
	end: string;
}

export function scoreCost(
	scores: Record<string, string>[],
	window: DayWindow
): ScoreCost | null {
	const cells = within(scores, window).map((row) => measured(row.score_ms));
	const values = cells.filter((ms): ms is number => ms !== null && ms > 0).sort((a, b) => a - b);
	if (values.length === 0) return null;
	return {
		n: values.length,
		median: quantile(values, 0.5),
		p95: quantile(values, 0.95),
		untimed: cells.length - values.length,
		days: window.days,
		start: window.start,
		end: window.end
	};
}

/** The band the summarizer was asked to write to, for an article of this length.
 *
 * The highest band the article clears, which is how `backend/idhazh/summarize.py`
 * picks it. A length nothing covers has no ask, and null says so.
 */
function askFor(bands: readonly SummaryBand[], sourceWords: number): SummaryBand | null {
	let found: SummaryBand | null = null;
	for (const band of [...bands].sort((a, b) => a.min_source_words - b.min_source_words)) {
		if (sourceWords >= band.min_source_words) found = band;
	}
	return found;
}

/** How long one run's summaries came out, in three numbers and never in one
 * mark per article.
 *
 * A mark per article draws its dense middle as a solid block, and the marks
 * that block hides are the only ones anybody acts on - a summary of three
 * words, or one twice the length that was asked for. Three marks a run keep
 * both ends and lose the block.
 */
export interface RunLength {
	runId: string;
	date: string;
	/** What wrote the run, where the ledger names one. */
	model: string | null;
	/** Summaries behind the three marks. */
	items: number;
	/** Summary length, words. */
	low: number;
	median: number;
	high: number;
	/** The narrowest and widest the run's own articles were asked for, read
	 * through each article's own length. Null where no article in the run
	 * recorded one. */
	askLow: number | null;
	askHigh: number | null;
}

/** One entry per run the score ledger holds a summary for, oldest first. */
export function runLengths(
	scores: Record<string, string>[],
	bands: readonly SummaryBand[]
): RunLength[] {
	const byRun = new Map<string, Record<string, string>[]>();
	for (const row of scores) {
		const runId = row.run_id ?? '';
		if (runId === '') continue;
		byRun.set(runId, [...(byRun.get(runId) ?? []), row]);
	}

	const found: RunLength[] = [];
	for (const [runId, rows] of byRun) {
		const words = rows
			.map((row) => measured(row.summary_word_count))
			.filter((count): count is number => count !== null)
			.sort((a, b) => a - b);
		if (words.length === 0) continue;
		const asks = rows
			.map((row) => measured(row.source_word_count) ?? measured(row.source_seen_word_count))
			.filter((count): count is number => count !== null)
			.map((count) => askFor(bands, count))
			.filter((band): band is SummaryBand => band !== null);
		const models = [...new Set(rows.map((row) => row.model_id ?? '').filter((id) => id !== ''))];
		found.push({
			runId,
			date: rows[0].date ?? '',
			model: models.length === 0 ? null : models.sort().join(', '),
			items: words.length,
			low: words[0],
			median: Math.round(quantile(words, 0.5)),
			high: words[words.length - 1],
			askLow: asks.length === 0 ? null : Math.min(...asks.map((band) => band.target_words_min)),
			askHigh: asks.length === 0 ? null : Math.max(...asks.map((band) => band.target_words_max))
		});
	}
	return found.sort((a, b) => a.runId.localeCompare(b.runId));
}

/** One measure, on each side of the day the model changed.
 *
 * `ratio` is the after over the before, so 1 is no change. It is the only thing
 * the seven rows can share an axis on: a median in seconds, a length in words
 * and a count in a hundred summaries have no common scale, and the question is
 * the same for all seven - did it move, and which way.
 */
export interface SwapMeasure {
	label: string;
	unit: 'seconds' | 'words' | 'percent' | 'per-hundred';
	before: number;
	after: number;
	/** After over before. Null where the before side is zero, because a move
	 * away from nothing has no size. */
	ratio: number | null;
}

/** The newest day the model changed, and what each side measured.
 *
 * Two models over two article sets is two measurements and not a trend, so both
 * article counts print and the panel refuses to draw at all where either side
 * is thin. The days on each side are the days the ledger holds, not a window:
 * a swap is a point in time and its two sides are however much ran on each
 * model.
 */
export interface ModelSwap {
	/** The first day the newer model ran. */
	at: string;
	before: { model: string; articles: number; from: string; to: string };
	after: { model: string; articles: number; from: string; to: string };
	measures: SwapMeasure[];
	/** False where either side holds fewer articles than the floor. The panel
	 * then prints both counts and draws nothing. */
	enough: boolean;
}

function share(rows: Record<string, string>[], of: (row: Record<string, string>) => boolean): number {
	return rows.length === 0 ? 0 : (rows.filter(of).length / rows.length) * 100;
}

function sideMeasures(
	scores: Record<string, string>[],
	health: Record<string, string>[],
	bands: readonly SummaryBand[]
): { label: string; unit: SwapMeasure['unit']; value: number }[] {
	const times = summarizeMs(health).sort((a, b) => a - b);
	const words = scores
		.map((row) => measured(row.summary_word_count))
		.filter((count): count is number => count !== null)
		.sort((a, b) => a - b);
	const copies = scores.map(copied).sort((a, b) => a - b);
	const outside = scores.filter((row) => {
		const wrote = measured(row.summary_word_count);
		const read = measured(row.source_word_count) ?? measured(row.source_seen_word_count);
		if (wrote === null || read === null) return false;
		const ask = askFor(bands, read);
		return ask !== null && (wrote < ask.target_words_min || wrote > ask.target_words_max);
	});
	return [
		{
			label: 'Time to write one',
			unit: 'seconds',
			value: times.length === 0 ? 0 : quantile(times, 0.5) / 1000
		},
		{
			label: 'Summary length',
			unit: 'words',
			value: words.length === 0 ? 0 : quantile(words, 0.5)
		},
		{
			label: 'Copied, not rewritten',
			unit: 'percent',
			value: copies.length === 0 ? 0 : quantile(copies, 0.5) * 100
		},
		{ label: 'Marked "not sure"', unit: 'per-hundred', value: share(scores, (row) => row.band === 'low') },
		{
			label: 'Numbers not in the article',
			unit: 'per-hundred',
			value: share(scores, (row) => (measured(row.unsupported_numbers) ?? 0) > 0)
		},
		{
			label: '"Maybe" told as fact',
			unit: 'per-hundred',
			value: share(scores, (row) => flag(row.hedge_dropped))
		},
		{
			label: 'Outside the length we asked for',
			unit: 'per-hundred',
			value: scores.length === 0 ? 0 : (outside.length / scores.length) * 100
		}
	];
}

export function modelSwap(
	scores: Record<string, string>[],
	health: Record<string, string>[],
	bands: readonly SummaryBand[],
	minArticles: number
): ModelSwap | null {
	const onDate = modelByDate(scores);
	const dates = [...onDate.keys()].sort();
	let at = '';
	for (let index = 1; index < dates.length; index += 1) {
		if (onDate.get(dates[index]) !== onDate.get(dates[index - 1])) at = dates[index];
	}
	if (at === '') return null;

	const older = dates.filter((date) => date < at);
	const newer = dates.filter((date) => date >= at);
	const beforeDates = new Set(older);
	const afterDates = new Set(newer);
	const beforeScores = scores.filter((row) => beforeDates.has(row.date ?? ''));
	const afterScores = scores.filter((row) => afterDates.has(row.date ?? ''));
	const beforeHealth = health.filter((row) => beforeDates.has(row.date ?? ''));
	const afterHealth = health.filter((row) => afterDates.has(row.date ?? ''));

	const left = sideMeasures(beforeScores, beforeHealth, bands);
	const right = sideMeasures(afterScores, afterHealth, bands);
	return {
		at,
		before: {
			model: onDate.get(older[older.length - 1]) ?? '',
			articles: beforeScores.length,
			from: older[0],
			to: older[older.length - 1]
		},
		after: {
			model: onDate.get(newer[newer.length - 1]) ?? '',
			articles: afterScores.length,
			from: newer[0],
			to: newer[newer.length - 1]
		},
		measures: left.map((measure, index) => ({
			label: measure.label,
			unit: measure.unit,
			before: measure.value,
			after: right[index].value,
			ratio: measure.value === 0 ? null : right[index].value / measure.value
		})),
		enough: beforeScores.length >= minArticles && afterScores.length >= minArticles
	};
}
