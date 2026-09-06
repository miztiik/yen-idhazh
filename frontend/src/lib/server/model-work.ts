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

import { distribution, quantile, type Distribution, type WriteBin } from '../charts/series';
import type { MovementPolarity } from '../charts/theme';
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
	return values.length === 0 ? null : quantile([...values].sort((a, b) => a - b), 0.5);
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

/** Did the checker doubt this summary - any one of the three signals.
 *
 * One predicate, because the ranked list of sources and the swap row under it
 * both ask this question and two spellings of it would let one surface call a
 * summary doubted while the other did not.
 *
 * The three are never blended into a score, and everywhere the count is shown
 * the three are shown beside it. They have different causes and different
 * fixes: a low band is the grader's own confidence, an unsupported number is a
 * fabrication, and a dropped hedge is a certainty the article did not have.
 * One blended figure would hide which of the three fired, which is the only
 * part an operator can act on.
 */
export function doubted(row: Record<string, string>): boolean {
	return (
		row.band === 'low' ||
		(measured(row.unsupported_numbers) ?? 0) > 0 ||
		flag(row.hedge_dropped)
	);
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

/** Every day the pipeline that wrote the summaries was not the one before it.
 *
 * The stamp compared is `pipeline_fingerprint`: a digest over the declared
 * inputs that can move an output - the weights, the quantisation, the llama.cpp
 * build, the chat template, the prompt, the output schema, the truncation cap,
 * the decoding settings, and the extractor and sanitizer versions
 * (`backend/idhazh/contracts/fingerprint.py`).
 *
 * `model_id` cannot stand in for it. Measured 2026-08-27 over 2,232 rows the
 * stamp moved four times while every row named one model, so a slug attributes
 * a changed number to an unchanged pipeline - which is why
 * `docs/concepts/evaluation.md` segments on the stamp too.
 *
 * A day is a boundary when it ran a stamp the previous scored day did not run.
 * A day that only stopped using one of yesterday's stamps changed nothing and
 * is not a boundary. A day carrying several stamps is one boundary, because a
 * day is one column and a change inside it cannot be placed any finer.
 *
 * Derived over the whole ledger and never over a window, so a chart opening on
 * the day after a change still knows the change happened.
 */
export function pipelineChanges(scores: Record<string, string>[]): string[] {
	const stamps = new Map<string, Set<string>>();
	for (const row of scores) {
		const date = row.date ?? '';
		const stamp = row.pipeline_fingerprint ?? '';
		if (date === '' || stamp === '') continue;
		stamps.set(date, (stamps.get(date) ?? new Set<string>()).add(stamp));
	}
	const dates = [...stamps.keys()].sort();
	const changes: string[] = [];
	for (let index = 1; index < dates.length; index += 1) {
		const before = stamps.get(dates[index - 1]) as Set<string>;
		const now = stamps.get(dates[index]) as Set<string>;
		if ([...now].some((stamp) => !before.has(stamp))) changes.push(dates[index]);
	}
	return changes;
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

/** The binning both routes draw, re-exported so the Summaries route's own
 * types keep their address. It moved to `$lib/charts/series` on 2026-09-05,
 * when the Pipelines route needed the same doublings for the two model clocks
 * and could not reach a `$lib/server/` module to get them. */
export type { Distribution, WriteBin };

/** How long one summary took, over every article the runtime timed in a window.
 *
 * One entry per timed attempt, not per article - the same rows the `Time to
 * write one` card takes its median over. A re-run really did spend the time
 * again, and a chart of what the machine spent that counts a second attempt
 * once would not add up to the model minutes printed beside it.
 */
export interface WriteTimes extends Distribution {
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
	const spread = distribution(summarizeMs(rows));
	if (spread === null) return null;

	return {
		...spread,
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
 *
 * It is drawn as the same distribution the writing clock is drawn as. Two
 * numbers out of 4,100 checks cannot say whether the tail is long or thin, and
 * the tail is what decides whether the scorer fits the job it runs in.
 */
export interface ScoreCost extends Distribution {
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
	const values = cells.filter((ms): ms is number => ms !== null && ms > 0);
	const spread = distribution(values);
	if (spread === null) return null;
	return {
		...spread,
		untimed: cells.length - values.length,
		days: window.days,
		start: window.start,
		end: window.end
	};
}

/** One article's two rates, or null where the runtime reported no timing.
 *
 * Cached prompt tokens are taken out of the read count. Leaving them in reports
 * a rate the machine never ran at: it did not read them.
 *
 * It lives here rather than beside the throughput candle that draws it, because
 * the model-change panel compares the same two rates either side of a swap.
 * Two spellings of "the read rate" would let one surface take cached tokens out
 * and the other leave them in.
 */
export function itemRates(row: Record<string, string>): {
	read: number | null;
	write: number | null;
} {
	const prefillMs = measured(row.prefill_ms);
	const decodeMs = measured(row.decode_ms);
	const prompt = measured(row.input_tokens);
	const written = measured(row.output_tokens);
	const evaluated = prompt === null ? null : prompt - (measured(row.cached_tokens) ?? 0);
	return {
		read:
			prefillMs !== null && prefillMs > 0 && evaluated !== null && evaluated > 0
				? evaluated / (prefillMs / 1000)
				: null,
		write:
			decodeMs !== null && decodeMs > 0 && written !== null && written > 0
				? written / (decodeMs / 1000)
				: null
	};
}

/** The source each article came from, keyed by the article.
 *
 * The score ledger records the address and the title and never the feed, so the
 * source a summary belongs to is a join onto the item-health ledger, which
 * records `source_id`. `url_key` is the key both carry and it is stable across
 * runs; `item_id` is a slot on a page and only holds inside one day.
 *
 * Measured 2026-09-01 over the committed ledgers: 3,959 of 4,110 scored rows
 * join, and every day from 2026-08-24 joins at 100 percent. The 151 that do not
 * are the two oldest scored days, written before item-health carried them. So
 * the join is complete over any window an operator opens, and the count that
 * did not join is printed rather than quietly dropped.
 */
export function sourceByUrlKey(health: Record<string, string>[]): Map<string, string> {
	const found = new Map<string, string>();
	for (const row of health) {
		const key = row.url_key ?? '';
		const sourceId = row.source_id ?? '';
		if (key === '' || sourceId === '') continue;
		found.set(key, sourceId);
	}
	return found;
}

/** One source, and how often the checker doubted what the model wrote from it. */
export interface SourceDoubt {
	sourceId: string;
	/** Summaries carrying at least one of the three signals. The ranking. */
	doubted: number;
	/** The three signals, counted apart. A summary can carry more than one, so
	 * these three do not add up to `doubted` and are never stacked. */
	notSure: number;
	unsupportedNumbers: number;
	hedgeDropped: number;
	/** The summaries every count above is out of. The denominator, carried
	 * rather than inferred: 2 doubted of 3 and 40 of 400 are different facts and
	 * the count alone cannot tell them apart. */
	summaries: number;
	/** `doubted` as whole percent of `summaries`, or null under the floor. A
	 * share over three summaries is the second summary. */
	sharePct: number | null;
}

/** The ranked list, and the sentences that cover what it left out. */
export interface SourceDoubts {
	/** The worst sources by doubted summaries, worst first. */
	rows: SourceDoubt[];
	/** Sources the cap did not reach, and the doubts they hold between them. */
	moreSources: number;
	moreDoubted: number;
	/** Scored summaries in the window no source could be found for. */
	unattributed: number;
	/** Sources the window scored anything from, and summaries it scored. */
	sources: number;
	summaries: number;
	/** Summaries the checker doubted, over every source. */
	doubted: number;
	days: number;
	start: string;
	end: string;
}

/** Which sources the checker doubts, over the window the page is showing.
 *
 * Sorted by the COUNT of doubted summaries and never by the share. A share sort
 * puts a source with 2 doubted of 3 above one with 40 of 400, and it is the
 * forty that reached a reader. The page states that rule, because a ranking
 * whose rule is not on the page can only be read for order.
 *
 * A tie is broken by the source's own name. A second criterion would be a
 * second ranking nobody declared, and the alphabet at least cannot be mistaken
 * for a judgement.
 *
 * A source with nothing doubted is left out rather than ranked at zero: it can
 * never reach the top of a list ordered by count, so a row for it would be a
 * row that says the list is longer than it is.
 */
export function sourceDoubts(
	scores: Record<string, string>[],
	health: Record<string, string>[],
	window: DayWindow,
	options: { limit: number; minForShare: number }
): SourceDoubts {
	const sourceOf = sourceByUrlKey(health);
	const rows = within(scores, window);

	const per = new Map<string, SourceDoubt>();
	let unattributed = 0;
	for (const row of rows) {
		const sourceId = sourceOf.get(row.url_key ?? '');
		if (sourceId === undefined) {
			unattributed += 1;
			continue;
		}
		const at = per.get(sourceId) ?? {
			sourceId,
			doubted: 0,
			notSure: 0,
			unsupportedNumbers: 0,
			hedgeDropped: 0,
			summaries: 0,
			sharePct: null
		};
		at.summaries += 1;
		if (row.band === 'low') at.notSure += 1;
		if ((measured(row.unsupported_numbers) ?? 0) > 0) at.unsupportedNumbers += 1;
		if (flag(row.hedge_dropped)) at.hedgeDropped += 1;
		if (doubted(row)) at.doubted += 1;
		per.set(sourceId, at);
	}

	const found = [...per.values()]
		.filter((source) => source.doubted > 0)
		.map((source) => ({
			...source,
			sharePct:
				source.summaries < options.minForShare
					? null
					: Math.round((source.doubted / source.summaries) * 100)
		}))
		.sort((a, b) => b.doubted - a.doubted || a.sourceId.localeCompare(b.sourceId));

	const rest = found.slice(options.limit);
	return {
		rows: found.slice(0, options.limit),
		moreSources: rest.length,
		moreDoubted: rest.reduce((total, source) => total + source.doubted, 0),
		unattributed,
		sources: per.size,
		summaries: rows.length,
		doubted: [...per.values()].reduce((total, source) => total + source.doubted, 0),
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
 * the rows can share an axis on: a median in seconds, a length in words, a
 * count in a hundred summaries and a token rate have no common scale, and the
 * question is the same for all of them - did it move, and which way.
 */
export interface SwapMeasure {
	label: string;
	unit: 'seconds' | 'words' | 'percent' | 'per-hundred' | 'tokens-a-second';
	/** Null where that side of the boundary recorded the measure at all.
	 *
	 * Not zero. A measure the older model never wrote down is not a comparison,
	 * and drawing it as a move from nothing would be a claim about a run nobody
	 * instrumented. The panel names it as unmeasured instead.
	 */
	before: number | null;
	after: number | null;
	/** After over before. Null where either side recorded nothing, and null
	 * where the before side is zero - a move away from nothing has no size. */
	ratio: number | null;
	/** Which direction is the good one. Declared here, with the measure, so the
	 * chart never decides it. Four of the ten have no agreed direction: a
	 * shorter summary is what a smaller model was picked for, more copying is
	 * not obviously worse than more invention, and the two token rates are set
	 * by the runner a shard landed on as much as by the model. */
	polarity: MovementPolarity;
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

/** A rate over rows, or null where no row was there to take it over.
 *
 * Zero and null are different answers. Zero is "none of these summaries did
 * it"; null is "nothing on this side of the boundary was asked".
 */
function share(
	rows: Record<string, string>[],
	of: (row: Record<string, string>) => boolean
): number | null {
	return rows.length === 0 ? null : (rows.filter(of).length / rows.length) * 100;
}

interface SideMeasure {
	label: string;
	unit: SwapMeasure['unit'];
	value: number | null;
	polarity: MovementPolarity;
}

function sideMeasures(
	scores: Record<string, string>[],
	health: Record<string, string>[],
	bands: readonly SummaryBand[]
): SideMeasure[] {
	const times = summarizeMs(health);
	const words = scores
		.map((row) => measured(row.summary_word_count))
		.filter((count): count is number => count !== null);
	const copies = scores.map(copied);
	const rates = health.map(itemRates);
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
			value: times.length === 0 ? null : (quantile([...times].sort((a, b) => a - b), 0.5)) / 1000,
			polarity: 'lower-is-better'
		},
		{
			label: 'Summary length',
			unit: 'words',
			value: median(words),
			// The bands in config say what length was ASKED for, so neither longer
			// nor shorter is better on its own - the measure two rows down is the
			// one that carries a verdict about length.
			polarity: 'no-agreed-direction'
		},
		{
			label: 'Copied, not rewritten',
			unit: 'percent',
			value: copies.length === 0 ? null : (median(copies) as number) * 100,
			// No agreed threshold, and more copying is not obviously worse than more
			// invention. The model route already refuses to tint this one.
			polarity: 'no-agreed-direction'
		},
		{
			label: 'Summaries the checker doubted',
			unit: 'per-hundred',
			// The same predicate the ranked list of sources above it uses, so the
			// panel and the list cannot disagree about what a doubt is.
			value: share(scores, doubted),
			polarity: 'lower-is-better'
		},
		{
			label: 'Marked "not sure"',
			unit: 'per-hundred',
			value: share(scores, (row) => row.band === 'low'),
			polarity: 'lower-is-better'
		},
		{
			label: 'Numbers not in the article',
			unit: 'per-hundred',
			value: share(scores, (row) => (measured(row.unsupported_numbers) ?? 0) > 0),
			polarity: 'lower-is-better'
		},
		{
			label: '"Maybe" told as fact',
			unit: 'per-hundred',
			value: share(scores, (row) => flag(row.hedge_dropped)),
			polarity: 'lower-is-better'
		},
		{
			label: 'Outside the length we asked for',
			unit: 'per-hundred',
			value: scores.length === 0 ? null : (outside.length / scores.length) * 100,
			polarity: 'lower-is-better'
		},
		{
			label: 'Reading the article',
			unit: 'tokens-a-second',
			value: median(rates.map((rate) => rate.read).filter((r): r is number => r !== null)),
			// A shard's read rate is set by the runner it landed on as much as by
			// the model: the committed runtime ledger holds one run whose fastest
			// shard read 4.35 times faster than its slowest, on one config. So the
			// figure is a fact about the machine and never a verdict on the swap.
			polarity: 'no-agreed-direction'
		},
		{
			label: 'Writing the summary',
			unit: 'tokens-a-second',
			value: median(rates.map((rate) => rate.write).filter((r): r is number => r !== null)),
			polarity: 'no-agreed-direction'
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
		measures: left.map((measure, index) => {
			const before = measure.value;
			const after = right[index].value;
			return {
				label: measure.label,
				unit: measure.unit,
				polarity: measure.polarity,
				before,
				after,
				// Both sides have to have recorded it, and the before side has to be
				// something. A measure only one side wrote down is not a comparison,
				// and a move away from nothing has no size.
				ratio: before === null || after === null || before === 0 ? null : after / before
			};
		}),
		enough: beforeScores.length >= minArticles && afterScores.length >= minArticles
	};
}
