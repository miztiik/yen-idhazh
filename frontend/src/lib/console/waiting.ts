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
 * | `refused` | the page or the engine would not run the question | change the question |
 *
 * **Telling `missing` from `unreachable` is the whole reason this file exists.**
 * Before it, both drew an unmarked gap, so a quiet pipeline and a broken fetch
 * were the same picture - which is the one thing this page is for (Susan).
 *
 * The sentences live here rather than in the components so that three panels
 * saying the same thing say it the same way, and so a change of wording is one
 * edit rather than a hunt.
 */
import { MONTHS, shortDate } from '$lib/format';
import { megabytes } from '$lib/assist/session';
import { grouped } from '$lib/charts/series';
import { monthsInWindow, type TimeWindow } from '$lib/charts/viewport';
import { nameSpan } from '$lib/console/span-words';
import type { AskRefusal } from '$lib/data/ledger';
import type { UnansweredDays } from '$lib/data/slice-shapes';
import { isDay } from '$lib/data/slice-shapes';

export type PanelState = 'ready' | 'loading' | 'quiet' | 'missing' | 'unreachable' | 'refused';

/** A panel's state, plus the one nothing only its chart can see.
 *
 * `too-few` is not a fetch state, so `panelState` never returns it: every
 * month arrived and the rows are real, but there are fewer of them than the
 * chart needs before its shape means anything - a histogram of eight readings
 * is a claim. It has its own word because `unreachable` already means a fetch
 * that failed, and a floor missed is not a failure.
 */
export type ChartState = PanelState | 'too-few';

/** Day-ledger panels name their settled state inside each reserved frame. */
export const STATE_WORDS = {
	quiet: 'Nothing recorded.',
	missing: 'Not published yet.',
	unreachable: 'Did not arrive.'
} as const;

export interface RouteStanding {
	state: 'loading' | 'ok' | 'quiet' | 'missing' | 'unreachable';
	days: number;
	through: string | null;
	missing: number;
	unreachable: number;
	shimmer: boolean;
}

export function routeStanding(reading: RouteStanding): string {
	if (!Number.isInteger(reading.days) || reading.days < 1) throw new Error('A route standing needs a positive day count.');
	if (reading.state === 'loading') return reading.shimmer ? 'Fetching the record.' : '';
	if (reading.state === 'unreachable') {
		return `Part of the record did not arrive, so ${reading.unreachable} ${reading.unreachable === 1 ? 'panel has' : 'panels have'} nothing to draw.`;
	}
	if (reading.state === 'missing') {
		return `${reading.missing} ${reading.missing === 1 ? 'panel reads' : 'panels read'} a record this site has not published yet, so ${reading.missing === 1 ? 'it has' : 'they have'} nothing to draw.`;
	}
	if (reading.state === 'quiet') return `Nothing was recorded in ${nameSpan(reading.days)}.`;
	if (!isDay(reading.through)) throw new Error('A loaded route standing must name the day its panels reach.');
	return `The panels below reach ${shortDate(reading.through)}.`;
}

export interface RecordWindow {
	asked: number;
	first: string | null;
	through: string | null;
}

/** Freshness is anchored on the returned record, never on the current clock. */
export function recordWindowSentence(record: RecordWindow): string {
	if (!Number.isSafeInteger(record.asked) || record.asked < 1) throw new Error('A record window needs a positive preset.');
	if (record.first === null || record.through === null) return '';
	if (!isDay(record.first) || !isDay(record.through)) throw new Error('A record window needs ordered UTC days.');
	const start = Date.parse(`${record.first}T00:00:00Z`);
	const end = Date.parse(`${record.through}T00:00:00Z`);
	if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) throw new Error('A record window needs ordered UTC days.');
	const dayMs = 86_400_000;
	const available = Math.floor((end - start) / dayMs) + 1;
	const days = Math.min(record.asked, available);
	const shown = `Showing ${days} ${days === 1 ? 'day' : 'days'}, to ${shortDate(record.through)}.`;
	if (available >= record.asked) return shown;
	const fills = new Date(start + (record.asked - 1) * dayMs).toISOString().slice(0, 10);
	return `${shown} The record starts on ${shortDate(record.first)}; the ${record.asked}-day window fills on ${shortDate(fills)}.`;
}

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
	const read = `Nothing was recorded in ${nameSpan(days)}.`;
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

/** The sentence a chart below its floor prints.
 *
 * It names the floor, from the value the panel passed in, and how many rows
 * there were, so an operator can tell a window that is too short from a
 * pipeline that stopped. `noun` is the plural the floor counts - `readings`,
 * `kinds` - because "fewer than 160" alone does not say of what. `place` says
 * where the rows were counted: a windowed panel counts `in this window`, and
 * the Data explorer, which draws an answer rather than a window, passes
 * `in the answer`.
 */
export function tooFewSentence(have: number, floor: number, noun: string, place = 'in this window'): string {
	const are = have === 1 ? 'is' : 'are';
	return `Only ${grouped(have)} of the ${grouped(floor)} ${noun} this chart needs ${are} ${place}, so it is not drawn.`;
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

function mb(bytes: number): string {
	return `${megabytes(bytes)} MB`;
}

/** The sentence a refused written question prints in the answer panel. */
export function refusedSentence(because: AskRefusal): string {
	if (because.kind === 'statements') return `Run one statement at a time. This has ${because.count}.`;
	if (because.kind === 'not-read-only') return `Only questions run here: start with SELECT, WITH, DESCRIBE, SUMMARIZE or EXPLAIN. This starts with ${because.word}.`;
	if (because.kind === 'too-long') return `This question is ${because.chars} characters long; the most this page runs is ${because.max}.`;
	if (because.kind === 'over-ceiling') return `These days would fetch ${mb(because.bytes)} from ${because.files} files, and one question may fetch ${mb(because.max)}. Pick fewer days or fewer ledgers.`;
	return 'The engine could not run this:';
}


export function explorerIdleSentence(): string {
	return 'Press Run and the answer appears here, as a table.';
}

export function explorerQuietSentence(): string {
	return 'Your question ran and matched no rows.';
}

export function explorerMissingSentence(ledger: string, published: boolean, explainUnasked = true): string {
	return published
		? `${ledger} is not packed yet.`
		: `${ledger} is not on this site yet${explainUnasked ? ', so nothing was asked of it' : ''}.`;
}

export function explorerUnreachableSentence(ledger: string | null, day: string | null, fault: string | null): string {
	if (fault === 'engine') {
		return 'The query engine did not start in this browser. A current version of Chrome, Edge, Firefox or Safari runs it.';
	}
	if (fault === null) return `${ledger ?? 'The ledger'} for ${day ?? 'that day'} did not arrive, so the question did not run.`;
	return `No file on this site holds ${ledger ?? 'the ledger'} for ${day ?? 'that day'}.`;
}

/** The note an answer prints when the repository, the committed `state/` the archive address points
 *  at, could not give it a ledger's older days: one sentence a ledger, each naming the ledger's
 *  first day on this site, where its answer starts, then one retry. Each sentence stays true
 *  whether the host did not answer, a file was not there, an index could not be read or a file
 *  arrived at the wrong size, and it names the repository rather than a host, because the address
 *  is a config value. The retry is a retry, not a fix: Run alone repeats a file the page remembers
 *  was not there, and Refresh forgets it (Reader and Jony, 2026-10-07). */
export function explorerUnansweredNote(unanswered: readonly UnansweredDays[]): string {
	const lines = unanswered.map(
		({ ledger, before }) => `Days of the ${ledger} record before ${shortDate(before)} are not in this answer, because this page could not read them from the repository.`
	);
	return [...lines, 'Press Refresh, then Run, to try again.'].join(' ');
}

export function explorerChartIdleSentence(): string {
	return 'If the answer holds a number, it is drawn here.';
}
