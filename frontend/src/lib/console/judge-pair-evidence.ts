/** Which outcomes and score-band counts can the exact packed attempt support? */
import type { Row } from '../data/slice-shapes';
import { drawBounds, judgeScore, SCORE_MAX, SCORE_MIN, type DrawBounds } from './judge-draw';
import { judgeCount, matchesJudgeAttempt, verdictOf, type JudgeReading } from './judge-observations';

export const PAIR_OUTCOMES = ['yes', 'no', 'unclear', 'split', 'refused'] as const;
export type PairOutcome = (typeof PAIR_OUTCOMES)[number];
export type OutcomeCounts = Record<PairOutcome, number>;
export type ClassifiedOutcome = Exclude<PairOutcome, 'refused'>;

export interface JudgePair {
	readonly score: number;
	readonly outcome: PairOutcome;
}

export interface JudgePairDay {
	readonly state: 'ready';
	readonly pairs: readonly JudgePair[];
	readonly bounds: DrawBounds | null;
	readonly settings: string | null;
}

export type PairDay = JudgePairDay | { readonly state: 'invalid' | 'incomplete' };

function outcomeOf(forward: unknown, swapped: unknown): PairOutcome | null {
	const a = verdictOf(forward), b = verdictOf(swapped);
	if ((a === null && forward !== null) || (b === null && swapped !== null)) return null;
	if (a === null || b === null) return 'refused';
	if (a !== b) return 'split';
	return a === 'YES' ? 'yes' : a === 'NO' ? 'no' : 'unclear';
}

const SETTING_FIELDS = [
	'scorer_model', 'cosine_weight', 'judge_model', 'prompt_digest', 'grammar_digest',
	'judge_policy_version', 'judge_temperature'
] as const;

function uniformSettings(rows: readonly Row[]): string | null {
	const values = SETTING_FIELDS.map((field) => rows[0]?.[field]);
	if (values.some((value) => value == null || value === '')) return null;
	return rows.every((row) => SETTING_FIELDS.every((field, at) => row[field] === values[at]))
		? JSON.stringify(values) : null;
}

function pairDay(rows: readonly Row[], expected: number | null): PairDay {
	const keys = new Set<string>();
	const pairs: JudgePair[] = [];
	for (const { pair_key: key, similarity_score, verdict, verdict_swapped } of rows) {
		const score = judgeScore(similarity_score), outcome = outcomeOf(verdict, verdict_swapped);
		if (typeof key !== 'string' || !key || keys.has(key) || score === null || outcome === null) {
			return { state: 'invalid' };
		}
		keys.add(key);
		pairs.push({ score, outcome });
	}
	if (expected !== null && pairs.length !== expected) return { state: 'incomplete' };
	const first = drawBounds(rows[0]?.lower_threshold_in_force, rows[0]?.upper_threshold_in_force);
	const bounds = first !== null && rows.every((row) =>
		row.lower_threshold_in_force === first.lower && row.upper_threshold_in_force === first.upper) ? first : null;
	return { state: 'ready', pairs, bounds, settings: uniformSettings(rows) };
}

export function judgePairDays(rows: readonly Row[], readings: ReadonlyMap<string, JudgeReading>): ReadonlyMap<string, PairDay> {
	const byDate = new Map<string, Row[]>();
	for (const row of rows) {
		const reading = typeof row.date === 'string' ? readings.get(row.date) : undefined;
		if (!reading || !matchesJudgeAttempt(row, reading.identity)) continue;
		const day = byDate.get(reading.identity.date);
		if (day) day.push(row);
		else byDate.set(reading.identity.date, [row]);
	}
	return new Map([...byDate].map(([date, pairs]) =>
		[date, pairDay(pairs, judgeCount(readings.get(date)?.cells.pairs_returned))]));
}

export interface ScoreBand {
	readonly low: number;
	readonly high: number;
}

export function judgeScoreBands(binCount: number): ScoreBand[] {
	return [{ low: SCORE_MIN, high: 0 }, ...Array.from({ length: binCount }, (_, at) =>
		({ low: at / binCount, high: (at + 1) / binCount }))];
}

export function countBandOutcomes(pairs: readonly JudgePair[], bands: readonly ScoreBand[]): OutcomeCounts[] {
	const counts: OutcomeCounts[] = bands.map(() => ({ yes: 0, no: 0, unclear: 0, split: 0, refused: 0 }));
	for (const { score, outcome } of pairs) {
		const at = bands.findIndex(({ low, high }) => score >= low && (score < high || high === SCORE_MAX));
		if (at === -1) throw new RangeError('A recorded score must fit a fixed judge band.');
		counts[at][outcome]++;
	}
	return counts;
}

export function outcomeTotal(counts: OutcomeCounts): number {
	return PAIR_OUTCOMES.reduce((total, outcome) => total + counts[outcome], 0);
}

export const MAX_ENTROPY_BITS = Math.log2(3);

export function judgeEntropy({ yes, no, unclear, split }: OutcomeCounts): number | null {
	const maybe = unclear + split;
	const eligible = yes + no + maybe;
	if (!eligible) return null;
	return [yes, maybe, no].reduce((bits, n) => {
		const share = n / eligible;
		return n ? bits - share * Math.log2(share) : bits;
	}, 0);
}
