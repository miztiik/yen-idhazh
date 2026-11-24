/** What was actually drawn, and which recorded score bounds were in force? */
import type { Row } from '../data/slice-shapes';
import { judgeCount, judgeNumber, judgeSlices, type SliceOutcome } from './judge-observations';

export const SCORE_MIN = -1;
export const SCORE_MAX = 1;

export function judgeScore(value: unknown): number | null {
	const n = judgeNumber(value);
	return n !== null && n >= SCORE_MIN && n <= SCORE_MAX ? n : null;
}

export function sliceParts(slice: SliceOutcome) {
	const { yes, no, unclear, split, refused, drawn } = slice;
	return { yes, no, unclear, split, refused, missing: drawn - yes - no - unclear - split - refused };
}

export interface DrawBounds {
	readonly lower: number;
	readonly upper: number;
}

export function drawBounds(lower: unknown, upper: unknown): DrawBounds | null {
	const lo = judgeScore(lower), hi = judgeScore(upper);
	return lo !== null && hi !== null && lo < hi ? { lower: lo, upper: hi } : null;
}

export function drawOf(row: Row | null) {
	const bounds = drawBounds(row?.lower_threshold_before, row?.upper_threshold_before);
	const decided = drawBounds(row?.lower_threshold_after, row?.upper_threshold_after);
	const drawn = judgeCount(row?.pairs_drawn), returned = judgeCount(row?.pairs_returned);
	const saved = row?.sample_status === 'measured' ? judgeSlices(row.slice_outcomes) : null;
	const slices = saved !== null && saved.every((slice) => slice.drawn > 0) &&
		saved.reduce((n, slice) => n + slice.drawn, 0) === drawn &&
		saved.reduce((n, slice) => n + slice.drawn - sliceParts(slice).missing, 0) === returned ? saved : null;
	return { bounds, decided, drawn, returned, slices };
}

export type JudgeDraw = ReturnType<typeof drawOf>;
