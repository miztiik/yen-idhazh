/** What the summarizer did on one day's own articles.
 *
 * Every figure is a count of that day's items. Nothing here is a score: a value
 * between zero and one names nothing an operator can pull, so the scorer's own
 * numbers stay in `state/scores.csv` and only their consequences reach the
 * screen. `copiedPct` is the one share on the page and it leaves here already
 * multiplied out, so a raw ratio has no route to the markup.
 *
 * `null` is a designed state and it is not zero. A day the scorer never ran on
 * has summaries nobody counted, a day whose runtime wrote no timing spent no
 * *measured* time, and a day whose rows predate a column's redefinition holds
 * no answer to the question the column asks now; printing any of the three as
 * zero would say the model did nothing.
 *
 * Imports nothing: the browser suite loads this module in plain Node, where no
 * Vite alias resolves, and it reads the same ledgers the page reads.
 */

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
	/** Median share of a summary lifted word for word, as whole percent. */
	copiedPct: number | null;
	/** Median milliseconds the model spent writing one summary. */
	perItemMs: number | null;
	/** Every millisecond the model spent that day. */
	totalMs: number | null;
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
	return {
		date,
		summaries: scored ? scores.length : null,
		notSure: count((row) => row.band === 'low'),
		unsupportedNumbers: count((row) => (measured(row.unsupported_numbers) ?? 0) > 0),
		hedgeDropped: count((row) => flag(row.hedge_dropped)),
		readInPart:
			cutKnown.length === 0
				? null
				: cutKnown.filter((row) => flag(row.truncation_flagged)).length,
		copiedPct: share === null ? null : Math.round(share * 100),
		perItemMs: median(times),
		totalMs: times.length === 0 ? null : times.reduce((total, ms) => total + ms, 0),
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
