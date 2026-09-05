/** Why the checker doubted a summary, day by day.
 *
 * The band says how far to trust an item. This says what is wrong with it. The
 * five reasons are counted apart and never pooled into one doubt count: pooled,
 * an operator learns how often the checker stopped and never learns which
 * defect to go and fix.
 *
 * **The source is the committed day payload, not the score ledger.**
 * `band_reason` is decided in `backend/idhazh/evals/score.py` and published on
 * the item. `state/scores/` carries the inputs the reason is decided from -
 * `hhem`, `coverage`, `unsupported_numbers`, `hedge_dropped` - and the band, and
 * no reason column at all. Re-deriving the reason from those inputs would be a
 * second copy of `verdict()` in a second language, and the day the two disagree
 * the page is wrong about the item a reader was shown.
 *
 * Pure on purpose. The route reads the payloads; every count, sentence and
 * series is worked out here, where a plain-Node test can drive it over the whole
 * committed corpus rather than over the one published day the canary holds.
 */

// Relative, not `$lib`: the browser suite imports this module in plain Node,
// where no Vite alias exists to resolve one.
import type { DayReadout } from '../charts/frame';
import { dayMonth } from '../format';
import { grouped } from '../charts/series';
import type { StackSeries } from '../charts/stacked';
import type { ChartToken } from '../charts/theme';

/** One reason, as the page draws and names it. */
export interface DoubtReason {
	/** The identifier `BandReason` publishes. Never printed. */
	id: string;
	/** What it means, in words a person would say out loud. */
	label: string;
	token: ChartToken;
}

/** The five, in the order the checker decides them.
 *
 * That order is the one rule already written down - `verdict()` tests an
 * unsupported figure first because nothing else in the row can see it, then the
 * faithfulness score, then the two counterweights - so a reader who learns the
 * legend once has learnt how an item gets its band.
 *
 * All five are declared here whether or not the corpus holds one. A list built
 * from the days on record would lose a series on the first quiet window and
 * nobody would see it go.
 */
export const REASONS: readonly DoubtReason[] = [
	{ id: 'unsupported_number', label: 'Numbers not in the article', token: '--chart-1' },
	{ id: 'faithfulness', label: 'Does not match the article', token: '--chart-2' },
	{ id: 'not_scored', label: 'Never checked', token: '--chart-3' },
	{ id: 'lead_missing', label: 'Left out the opening facts', token: '--chart-4' },
	{ id: 'hedge_dropped', label: '"Maybe" told as fact', token: '--chart-5' }
];

/** One published item, reduced to the two cells this panel reads. */
export interface ReasonItem {
	band: string | null;
	reason: string | null;
}

/** One committed day, as the route hands it over. */
export interface ReasonInput {
	date: string;
	items: readonly ReasonItem[];
}

/** One drawn column. */
export interface ReasonDay {
	date: string;
	/** Every summary the day published. The denominator of every share here. */
	items: number;
	/** Summaries carrying a reason. **This is the column total**, and it is what
	 * the five counts sum to. It is not the count of doubtful items - see
	 * `unexplained`. */
	explained: number;
	/** Summaries the checker doubted and wrote no reason for.
	 *
	 * Not a sixth reason and never drawn as one. `band_reason` was added to the
	 * published item after the first days were published, so an old day carries a
	 * band with nothing beside it. Drawing those as a series would invent a
	 * defect the checker never named; leaving them out silently would make three
	 * days look clean. They are counted here and said in a sentence.
	 */
	unexplained: number;
	/** One count per reason id, every reason present whatever its value. */
	counts: Record<string, number>;
}

const DOUBTFUL = new Set(['medium', 'low']);

/** Every day counted, oldest first. The chart reads left to right. */
export function reasonDays(input: readonly ReasonInput[]): ReasonDay[] {
	return input
		.map((day) => {
			const counts: Record<string, number> = {};
			for (const reason of REASONS) counts[reason.id] = 0;
			let explained = 0;
			let unexplained = 0;
			for (const item of day.items) {
				const reason = item.reason ?? '';
				if (reason !== '' && reason in counts) {
					counts[reason] += 1;
					explained += 1;
				} else if (DOUBTFUL.has(item.band ?? '')) {
					unexplained += 1;
				}
			}
			return { date: day.date, items: day.items.length, explained, unexplained, counts };
		})
		.sort((a, b) => a.date.localeCompare(b.date));
}

/** The days inside a span, ends included. */
export function reasonsWithin(
	days: readonly ReasonDay[],
	span: { start: string; end: string }
): ReasonDay[] {
	return days.filter((day) => day.date >= span.start && day.date <= span.end);
}

/** What the whole window holds, so a sentence never re-walks the days itself. */
export interface ReasonTotals {
	days: number;
	items: number;
	explained: number;
	unexplained: number;
	/** Days carrying at least one doubtful summary with no reason. */
	unexplainedDays: number;
	counts: Record<string, number>;
}

export function reasonTotals(days: readonly ReasonDay[]): ReasonTotals {
	const counts: Record<string, number> = {};
	for (const reason of REASONS) counts[reason.id] = 0;
	let items = 0;
	let explained = 0;
	let unexplained = 0;
	let unexplainedDays = 0;
	for (const day of days) {
		items += day.items;
		explained += day.explained;
		unexplained += day.unexplained;
		if (day.unexplained > 0) unexplainedDays += 1;
		for (const reason of REASONS) counts[reason.id] += day.counts[reason.id] ?? 0;
	}
	return { days: days.length, items, explained, unexplained, unexplainedDays, counts };
}

/** The columns' labels, in the date grammar the console's other axes print. */
export function reasonColumnLabels(days: readonly ReasonDay[]): string[] {
	return days.map((day) => dayMonth(day.date));
}

/** One series per reason, for `stacked()`.
 *
 * Every reason is handed over, empty ones included. `stacked()` drops a series
 * that is zero everywhere, so a reason the window never saw costs no band and no
 * colour - and `neverSeenNote` names it in words instead, which is the only way
 * a reader learns it was looked for.
 */
export function reasonSeries(days: readonly ReasonDay[]): StackSeries[] {
	return REASONS.map((reason) => ({
		label: reason.label,
		token: reason.token,
		values: days.map((day) => day.counts[reason.id] ?? 0)
	}));
}

/** Which reasons the window actually saw, in the declared order. */
export function reasonsDrawn(days: readonly ReasonDay[]): DoubtReason[] {
	const totals = reasonTotals(days);
	return REASONS.filter((reason) => totals.counts[reason.id] > 0);
}

/** Every drawn reason at one day, for the strip under the plot.
 *
 * The count and the day's own item count together, because a count with no
 * denominator invites a trend that is not there: 45 doubted of 208 published and
 * 45 of 731 are different facts.
 */
export function reasonColumns(days: readonly ReasonDay[]): DayReadout[] {
	const drawn = reasonsDrawn(days);
	return days.map((day) => ({
		x: 0,
		date: day.date,
		rows: drawn.map((reason) => ({
			label: reason.label,
			value: `${grouped(day.counts[reason.id] ?? 0)} of ${grouped(day.items)}`,
			colour: `var(${reason.token})`
		}))
	}));
}

/** A whole percent, or null where there is nothing to divide. */
function share(part: number, whole: number): number | null {
	return whole > 0 ? Math.round((part / whole) * 100) : null;
}

/** "about one in five", or null where the share is too small to say that way. */
function oneIn(pct: number): string | null {
	if (pct <= 0 || pct > 50) return null;
	return `about one in every ${Math.round(100 / pct)}`;
}

/** The reason given most often, said as a sentence.
 *
 * A percent is not an answer on its own (`CLAUDE.md` section 0b), so the count,
 * the window and what the share means all sit in the same sentence. Null where
 * the window doubted nothing, which the empty state says instead.
 */
export function reasonHeadline(days: readonly ReasonDay[], windowDays: number): string | null {
	const totals = reasonTotals(days);
	if (totals.explained === 0) return null;
	const top = [...REASONS].sort(
		(a, b) => (totals.counts[b.id] ?? 0) - (totals.counts[a.id] ?? 0)
	)[0];
	const count = totals.counts[top.id] ?? 0;
	const pct = share(count, totals.items);
	const rough = pct === null ? null : oneIn(pct);
	const ratio = rough === null ? '' : `, ${rough} published`;
	return `The reason given most often is "${top.label}": ${grouped(count)} summaries in these ${windowDays} days${ratio}.`;
}

/** The days that carry a band and no reason, said as a sentence.
 *
 * Null where every doubtful summary in the window names its own reason, which is
 * every day this pipeline has published since the field was added.
 */
export function unexplainedNote(days: readonly ReasonDay[], windowDays: number): string | null {
	const totals = reasonTotals(days);
	if (totals.unexplained === 0) return null;
	const doubted = totals.explained + totals.unexplained;
	const dayWord = totals.unexplainedDays === 1 ? 'day' : 'days';
	return `${grouped(totals.unexplained)} of the ${grouped(doubted)} doubted summaries in these ${windowDays} days have no reason written down, on ${totals.unexplainedDays} ${dayWord}. Those columns are short by that much: the reason is missing from our record, not from the summary.`;
}

/** The reasons the window never saw, said as a sentence.
 *
 * A series that is zero everywhere draws no band, so without this a reader
 * cannot tell a reason that never fired from a reason nobody thought to look
 * for. Null where every reason drew at least once.
 */
export function neverSeenNote(days: readonly ReasonDay[], windowDays: number): string | null {
	const totals = reasonTotals(days);
	if (totals.days === 0) return null;
	const missing = REASONS.filter((reason) => totals.counts[reason.id] === 0);
	if (missing.length === 0) return null;
	const names = missing.map((reason) => `"${reason.label}"`);
	const list =
		names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`;
	const verb = names.length === 1 ? 'is a reason the checker' : 'are reasons the checker';
	return `${list} ${verb} can give and did not give once in these ${windowDays} days, so ${names.length === 1 ? 'it has' : 'they have'} no line on the chart.`;
}
