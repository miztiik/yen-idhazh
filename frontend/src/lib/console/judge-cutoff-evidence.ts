/** What changes when the selected attempt's scores are read at another cutoff? */
import type { DrawBounds } from './judge-draw';
import type { JudgePair } from './judge-pair-evidence';

export const SCORE_ZONES = ['yes', 'maybe', 'no'] as const;
export type ScoreZone = (typeof SCORE_ZONES)[number];

export function judgeZoneMatrix(pairs: readonly JudgePair[], { lower, upper }: DrawBounds) {
	const matrix: Record<ScoreZone, Record<ScoreZone, number>> = {
		yes: { yes: 0, maybe: 0, no: 0 },
		maybe: { yes: 0, maybe: 0, no: 0 },
		no: { yes: 0, maybe: 0, no: 0 }
	};
	let refused = 0, unclear = 0, split = 0;
	for (const { score, outcome } of pairs) {
		if (outcome === 'refused') { refused++; continue; }
		if (outcome === 'unclear') unclear++;
		if (outcome === 'split') split++;
		const zone = score < lower ? 'no' : score >= upper ? 'yes' : 'maybe';
		const reference = outcome === 'yes' || outcome === 'no' ? outcome : 'maybe';
		matrix[reference][zone]++;
	}
	return { matrix, refused, unclear, split };
}

export interface CutoffReading {
	readonly cutoff: number;
	readonly tp: number;
	readonly fp: number;
	readonly fn: number;
	readonly tn: number;
	readonly precision: number | null;
	readonly recall: number | null;
}

function cutoffReading(cutoff: number, tp: number, predicted: number, positives: number, n: number): CutoffReading {
	return {
		cutoff, tp, fp: predicted - tp, fn: positives - tp, tn: n - positives - (predicted - tp),
		precision: predicted > 0 ? tp / predicted : null, recall: positives > 0 ? tp / positives : null
	};
}

export function judgeCutoffSweep(pairs: readonly JudgePair[]) {
	const binary = pairs.filter(({ outcome }) => outcome === 'yes' || outcome === 'no')
		.sort((a, b) => b.score - a.score);
	const positives = binary.filter(({ outcome }) => outcome === 'yes').length;
	const points: CutoffReading[] = [];
	let tp = 0;
	for (const [at, pair] of binary.entries()) {
		if (pair.outcome === 'yes') tp++;
		if (binary[at + 1]?.score !== pair.score) {
			points.push(cutoffReading(pair.score, tp, at + 1, positives, binary.length));
		}
	}
	function atCutoff(cutoff: number): CutoffReading {
		const held = points.findLast((reading) => reading.cutoff >= cutoff);
		return cutoffReading(cutoff, held?.tp ?? 0, held === undefined ? 0 : held.tp + held.fp, positives, binary.length);
	}
	return { points, atCutoff, binary: binary.length, positives, excluded: pairs.length - binary.length };
}
