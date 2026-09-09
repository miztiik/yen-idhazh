/** What a console panel is doing while it has no rows, and what it says.
 *
 * Until 2026-09-09 the console inlined its telemetry, so a panel either had its
 * rows or the pipeline had never written any, and one sentence covered both.
 * The rows arrive by fetch now, which splits that one nothing into four:
 *
 * | State | What happened | What the operator should do |
 * | --- | --- | --- |
 * | `loading` | the month files are in the air | wait |
 * | `quiet` | every month arrived and the window is genuinely empty | widen it |
 * | `missing` | the pipeline never wrote those months | nothing - it is real |
 * | `unreachable` | a month was asked for and did not come back | retry it |
 *
 * **Telling `missing` from `unreachable` is the whole reason this file exists.**
 * Before it, both drew an unmarked gap, so a quiet pipeline and a broken fetch
 * were the same picture - which is the one thing this page is for (Susan,
 * plan row #12).
 *
 * The sentences live here rather than in the components so that three panels
 * saying the same thing say it the same way, and so a change of wording is one
 * edit rather than a hunt.
 */
import { MONTHS } from '$lib/format';
import { monthsInWindow, type TimeWindow } from '$lib/charts/viewport';

export type PanelState = 'ready' | 'loading' | 'quiet' | 'missing' | 'unreachable';

/** What became of one month file the open window reaches into. */
export type MonthState = 'held' | 'loading' | 'missing' | 'unreachable';

export interface MonthOutcome {
	/** `YYYY-MM`. */
	month: string;
	state: MonthState;
}

/** `2026-07` as `July 2026`. A month id is a key, never a sentence. */
export function monthName(month: string): string {
	const index = Number(month.slice(5, 7)) - 1;
	const name = MONTHS[index];
	return name === undefined ? month : `${name} ${month.slice(0, 4)}`;
}

/** A list of month names as English: one, `A and B`, or `A, B and C`. */
export function nameMonths(months: readonly string[]): string {
	const names = months.map(monthName);
	if (names.length === 0) return '';
	if (names.length === 1) return names[0] as string;
	return `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`;
}

export interface WindowReach {
	window: TimeWindow;
	/** Every month the pipeline wrote a shard for - the band's own list. */
	published: readonly string[];
	/** Months whose shard is in hand. */
	held: readonly string[];
	/** Months a fetch is in flight for. */
	loading: readonly string[];
	/** Months a fetch was tried for and failed. */
	unreachable: readonly string[];
}

/** One row per month the open window touches, in date order.
 *
 * A month the band does not list is `missing` and is never fetched: asking for
 * it would only produce a 404 and a gap the chart already draws.
 */
export function monthOutcomes(reach: WindowReach): MonthOutcome[] {
	const published = new Set(reach.published);
	const held = new Set(reach.held);
	const loading = new Set(reach.loading);
	const unreachable = new Set(reach.unreachable);
	return monthsInWindow(reach.window).map((month) => {
		if (!published.has(month)) return { month, state: 'missing' as const };
		if (held.has(month)) return { month, state: 'held' as const };
		if (unreachable.has(month)) return { month, state: 'unreachable' as const };
		if (loading.has(month)) return { month, state: 'loading' as const };
		// Published, not held, not in the air and not refused: the fetch has not
		// been started yet, which from the outside is indistinguishable from one
		// that has. Both are a wait.
		return { month, state: 'loading' as const };
	});
}

export function monthsIn(outcomes: readonly MonthOutcome[], state: MonthState): string[] {
	return outcomes.filter((entry) => entry.state === state).map((entry) => entry.month);
}

/** Which of the five states a panel is in.
 *
 * The order is the order an operator can act on. A wait outranks everything,
 * because a panel that named a gap while its months were still arriving would
 * be wrong in a second. A failed fetch outranks a real gap, because only one of
 * the two is worth a retry. `ready` is last and it is the common case: rows in
 * the window means the panel draws, gaps and all.
 */
export function panelState(outcomes: readonly MonthOutcome[], rowsInWindow: number): PanelState {
	if (outcomes.some((entry) => entry.state === 'loading')) return 'loading';
	if (outcomes.some((entry) => entry.state === 'unreachable')) return 'unreachable';
	if (rowsInWindow > 0) return 'ready';
	if (outcomes.some((entry) => entry.state === 'missing')) return 'missing';
	return 'quiet';
}

/** The one preset that would fill an empty window, or null where none would.
 *
 * The narrowest preset wider than the one in force whose span reaches a month
 * that has rows. Naming the widest would tell an operator to pay for months he
 * does not need; naming none at all leaves him with a dead end.
 */
export function wideningPreset(
	days: number,
	presets: readonly number[],
	published: readonly string[],
	reachOf: (days: number) => TimeWindow
): number | null {
	const has = new Set(published);
	for (const preset of [...presets].sort((a, b) => a - b)) {
		if (preset <= days) continue;
		if (monthsInWindow(reachOf(preset)).some((month) => has.has(month))) return preset;
	}
	return null;
}

/** The sentence a quiet panel prints.
 *
 * It says two things and no more: the window was read, and it held nothing. The
 * preset is the only action there is, so it is named with the span it reaches.
 */
export function quietSentence(days: number, widen: number | null): string {
	const read = `Nothing was recorded in these ${days} days.`;
	return widen === null
		? `${read} No wider window reaches a day that has anything.`
		: `${read} The ${widen}-day window reaches back to months that do.`;
}

/** The sentence a panel with a real gap prints.
 *
 * No alarm and no retry: there is nothing to fetch and nothing went wrong. What
 * it has to stop is an operator reading a marked span as a dip.
 */
export function missingSentence(months: readonly string[]): string {
	const was = months.length === 1 ? 'was' : 'were';
	return `${nameMonths(months)} ${was} never recorded, so the chart marks that span as a gap rather than a dip.`;
}

/** The sentence a panel with a failed fetch prints.
 *
 * It names the month, because a retry needs a subject, and it says what is on
 * the screen, because the drawing is still true of the months that did arrive.
 */
export function unreachableSentence(months: readonly string[], heldDays: number): string {
	const did = months.length === 1 ? 'did' : 'did';
	const drawn =
		heldDays === 0
			? 'so this panel has nothing left to draw'
			: `so this panel is drawn from the ${heldDays} ${heldDays === 1 ? 'day' : 'days'} that did arrive`;
	return `${nameMonths(months)} ${did} not arrive, ${drawn}.`;
}

/** The label on the retry, which carries its own subject.
 *
 * `Try again` is shorter and it is what the shape asks for, but a button read
 * out of the sentence above it then names nothing. The month is three words and
 * it makes the control true on its own.
 */
export function retryLabel(months: readonly string[]): string {
	return `Try ${nameMonths(months)} again`;
}
