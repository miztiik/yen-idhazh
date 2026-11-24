/** What did the judge record for this digest, without joining different attempts? */
import type { LedgerReach, Row } from '../data/ledger';
import { isDay } from '../data/slice-shapes';
import { daysBetween, type TimeWindow } from '../charts/viewport';
import { formatNumber, MAX_SIGNIFICANT_DIGITS, type NumberFormatConfig } from '../number-format';
import { compareRuns } from './queries/shared';
import type { Range } from './queries/window';
import type { Answer } from './voices/record';

export interface JudgeIdentity {
	readonly date: string;
	readonly run: string;
	readonly attempt: number;
}

export interface JudgeReading {
	readonly identity: JudgeIdentity;
	readonly cells: Row;
}

export function judgeRange(window: TimeWindow, reach: LedgerReach): Range | null {
	if (reach.state !== 'ok') return null;
	const from = window.start > reach.first ? window.start : reach.first;
	const to = window.end < reach.through ? window.end : reach.through;
	return from > to ? null : { from, to, days: daysBetween(from, to), asked: daysBetween(window.start, window.end) };
}

function identityOf(row: Row): JudgeIdentity | null {
	const { date, run_id: run, attempt } = row;
	if (typeof date !== 'string' || !isDay(date) || typeof run !== 'string' ||
		typeof attempt !== 'number' || !Number.isSafeInteger(attempt) || attempt < 1) return null;
	const runDay = /^(\d{4}-\d{2}-\d{2})-\d+$/.exec(run)?.[1];
	return runDay !== undefined && isDay(runDay) ? { date, run, attempt } : null;
}

export function latestJudgeReadings(rows: readonly Row[]): ReadonlyMap<string, JudgeReading> {
	const latest = new Map<string, JudgeReading>();
	let unidentified = 0;
	for (const cells of rows) {
		const identity = identityOf(cells);
		if (identity === null) { unidentified++; continue; }
		const prior = latest.get(identity.date)?.identity;
		const order = prior === undefined ? 1 : compareRuns(identity.run, prior.run);
		if (order > 0 || (order === 0 && prior !== undefined && identity.attempt > prior.attempt)) {
			latest.set(identity.date, { identity, cells });
		}
	}
	if (unidentified > 0) console.warn(`[judgement] ${unidentified} packed threshold-history rows had no usable date, run and attempt.`);
	return latest;
}

export function exactJudgeDay(rows: readonly Row[], identity: JudgeIdentity): Row | null {
	return rows.find((row) => matchesJudgeAttempt(row, identity)) ?? null;
}

export function matchesJudgeAttempt(row: Row, identity: JudgeIdentity): boolean {
	return row.date === identity.date && row.run_id === identity.run && row.attempt === identity.attempt;
}

export function selectedJudgeDate(calendar: readonly string[], held: string | null, readings: ReadonlyMap<string, JudgeReading>): string {
	if (held !== null && calendar.includes(held)) return held;
	return calendar.findLast((date) => readings.has(date)) ?? calendar[calendar.length - 1]!;
}

export function judgeDayAbsence(date: string, answer: Answer, reach: LedgerReach | null): string {
	if (answer === 'pending') return 'Loading chart data...';
	if (answer.state === 'unreachable' || ('lostDays' in answer && answer.lostDays.includes(date))) return 'Did not arrive.';
	if (answer.state === 'missing' || (reach?.state === 'ok' && date > reach.through)) return 'Not published yet.';
	return 'Not recorded.';
}

export function judgeNumber(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function judgeShare(numerator: number | null, denominator: number | null, config: NumberFormatConfig): string | null {
	return numerator !== null && denominator !== null && denominator > 0
		? `${formatNumber(100 * numerator / denominator, config, { si: false })}%` : null;
}

export function judgeCount(value: unknown): number | null {
	const number = judgeNumber(value);
	return number !== null && Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function total(parts: readonly (number | null)[]): number | null {
	return parts.some((part) => part === null) ? null : parts.reduce<number>((sum, part) => sum + (part ?? 0), 0);
}

export function judgeCutoff(cells: Row) {
	const tp = judgeCount(cells.sample_tp), fp = judgeCount(cells.sample_fp);
	const fn = judgeCount(cells.sample_fn), tn = judgeCount(cells.sample_tn);
	return { tp, fp, fn, tn, binary: total([tp, fp, fn, tn]), predicted: total([tp, fp]), judgeYes: total([tp, fn]) };
}

export function judgeCoverage(cells: Row) {
	const drawn = judgeCount(cells.pairs_drawn), returned = judgeCount(cells.pairs_returned);
	const { binary } = judgeCutoff(cells);
	const other = returned !== null && binary !== null && binary <= returned ? returned - binary : null;
	const lost = drawn !== null && returned !== null && returned <= drawn ? drawn - returned : null;
	return { drawn, returned, binary, other, lost, stack: other !== null && lost !== null ? [binary, other, lost] : null };
}

export const SAMPLE_STATUS = {
	measured: null,
	not_filed: 'Not measured: no verdict batch was filed for this attempt.',
	draw_mismatch: 'Not measured: the draw and the filed verdicts did not match.'
} as const;

export const DRIFT_STATUS = {
	measured: null,
	no_histogram: 'Not measured: no full-pool histogram was recorded.',
	empty_pool: 'Not measured: the eligible score pool was empty.',
	insufficient_baseline: 'Not measured: too few comparable baseline days.'
} as const;

export const PROBABILITY_STATUS = {
	measured: null,
	no_reference_fit: 'Not measured: No comparable prior fit.',
	no_eligible_pairs: "Not measured: No new agreed pairs in the prior fit's score range."
} as const;

export function judgeStatus(cell: Row[string] | undefined, names: Readonly<Record<string, string | null>>): string {
	if (cell == null) return 'Not recorded.';
	if (typeof cell !== 'string' || !Object.hasOwn(names, cell)) return 'Did not arrive as a recognized reading.';
	return names[cell] ?? 'Not measured: the saved reading is unavailable.';
}

function object(value: unknown): Record<string, unknown> | null {
	return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function judgeCompact(cell: Row[string] | undefined): Record<string, unknown> | null {
	if (typeof cell !== 'string') return null;
	try { return object(JSON.parse(cell)); }
	catch (error) {
		if (!(error instanceof SyntaxError)) throw error;
		return null; // The panel names unusable saved evidence, rather than claiming zero.
	}
}

export interface SliceOutcome {
	low: number;
	high: number;
	drawn: number;
	yes: number;
	no: number;
	unclear: number;
	split: number;
	refused: number;
}

export function judgeSlices(cell: Row[string] | undefined): SliceOutcome[] | null {
	const saved = judgeCompact(cell);
	if (!Array.isArray(saved?.slices)) return null;
	const slices: SliceOutcome[] = [];
	for (const entry of saved.slices) {
		const row = object(entry);
		if (row === null) return null;
		const low = judgeNumber(row.low), high = judgeNumber(row.high);
		const drawn = judgeCount(row.drawn), yes = judgeCount(row.yes), no = judgeCount(row.no);
		const unclear = judgeCount(row.unclear), split = judgeCount(row.split), refused = judgeCount(row.refused);
		if (low === null || high === null || low < -1 || high > 1 || low >= high ||
			(slices.at(-1)?.high ?? -1) > low || drawn === null || yes === null || no === null ||
			unclear === null || split === null || refused === null || yes + no + unclear + split + refused > drawn) return null;
		slices.push({ low, high, drawn, yes, no, unclear, split, refused });
	}
	return slices;
}

export function judgeDriftBaseline(cell: Row[string] | undefined) {
	const row = judgeCompact(cell);
	if (!Array.isArray(row?.sources)) return null;
	const required = judgeCount(row.required_days);
	const days: string[] = [];
	for (const source of row.sources) {
		const date = object(source)?.date;
		if (typeof date !== 'string' || !isDay(date)) return null;
		days.push(date);
	}
	return required === null ? null : { first: days.at(-1), last: days[0], days: days.length, required };
}

export function judgeProbabilityEvidence(cell: Row[string] | undefined) {
	const row = judgeCompact(cell);
	if (row === null) return null;
	const { source_date, source_run_id } = row;
	const pairs = judgeCount(row.pairs), yes = judgeCount(row.yes), bins = judgeCount(row.bins);
	if (typeof source_date !== 'string' || !isDay(source_date) || typeof source_run_id !== 'string' ||
		pairs === null || yes === null || yes > pairs || bins === null) return null;
	return { date: source_date, run: source_run_id, pairs, yes, bins };
}

const VERDICTS = ['YES', 'NO', 'UNCLEAR'] as const;
export type Verdict = (typeof VERDICTS)[number];
export function verdictOf(cell: unknown): Verdict | null {
	return VERDICTS.find((verdict) => verdict === cell) ?? null;
}

export function psiInterpretation(value: number, low: number, high: number): string {
	if (value < low) return 'No significant drift';
	if (value <= high) return 'Moderate drift (investigation needed)';
	return 'Significant drift (retrain or re-calibrate)';
}

export function judgeDecimal(value: number, config: NumberFormatConfig): string {
	return formatNumber(value, { ...config, significant_digits: MAX_SIGNIFICANT_DIGITS }, { si: false });
}

export function psiNumber(value: number, low: number, high: number, config: NumberFormatConfig): string {
	// Print the configured boundary as-is and never round a nearby point across or onto it.
	for (let digits = config.significant_digits; digits <= MAX_SIGNIFICANT_DIGITS; digits++) {
		const rounded = Number(value.toPrecision(digits));
		if (Math.sign(rounded - low) === Math.sign(value - low) &&
			Math.sign(rounded - high) === Math.sign(value - high)) {
			return formatNumber(value, { ...config, significant_digits: digits }, { si: false });
		}
	}
	return judgeDecimal(value, config);
}
