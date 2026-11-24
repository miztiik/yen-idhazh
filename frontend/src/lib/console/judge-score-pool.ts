/** Which saved full-pool bins and exact reference sources are available to compare? */
import type { Row } from '../data/slice-shapes';
import { isDay } from '../data/slice-shapes';
import { sha256Hex } from '../assist/weights';
import { judgeCount, judgeCompact } from './judge-observations';
import { judgeScore, SCORE_MAX, SCORE_MIN } from './judge-draw';

// Bound to ScorePoolHistogram's native maximum by the panel contract check.
export const MAX_SCORE_BINS = 200;
const SHA256 = /^[0-9a-f]{64}$/;

export interface JudgePool {
	readonly stamp: string;
	readonly edges: readonly number[];
	readonly counts: readonly number[];
	readonly total: number;
}

export function judgePool(cell: Row[string] | undefined): JudgePool | null {
	const saved = judgeCompact(cell);
	if (typeof saved?.stamp !== 'string' || !SHA256.test(saved.stamp) ||
		!Array.isArray(saved.edges) || !Array.isArray(saved.counts) ||
		saved.counts.length < 1 || saved.counts.length > MAX_SCORE_BINS ||
		saved.edges.length !== saved.counts.length + 1) return null;
	const edges: number[] = [];
	for (const edge of saved.edges) {
		const x = judgeScore(edge);
		if (x === null || (edges.at(-1) ?? -Infinity) >= x) return null;
		edges.push(x);
	}
	if (edges[0] !== SCORE_MIN || edges.at(-1) !== SCORE_MAX) return null;
	const counts: number[] = [];
	let total = 0;
	for (const value of saved.counts) {
		const n = judgeCount(value);
		if (n === null) return null;
		total += n;
		counts.push(n);
	}
	return Number.isSafeInteger(total) ? { stamp: saved.stamp, edges, counts, total } : null;
}

interface PoolSource {
	readonly date: string;
	readonly run_id: string;
	readonly histogram_sha256: string;
}

function sourceOf(value: unknown): PoolSource | null {
	if (typeof value !== 'object' || value === null ||
		!('date' in value) || typeof value.date !== 'string' || !isDay(value.date) ||
		!('run_id' in value) || typeof value.run_id !== 'string' ||
		!('histogram_sha256' in value) || typeof value.histogram_sha256 !== 'string' ||
		!SHA256.test(value.histogram_sha256)) return null;
	return { date: value.date, run_id: value.run_id, histogram_sha256: value.histogram_sha256 };
}

export async function savedPoolBaseline(
	target: JudgePool, evidence: Row[string] | undefined, rows: readonly Row[]
): Promise<JudgePool | null> {
	const saved = judgeCompact(evidence);
	if (!Array.isArray(saved?.sources) || saved.sources.length === 0 ||
		saved.sources.length !== saved.required_days) return null;
	const days = new Set<string>();
	const counts = target.counts.map(() => 0);
	const encoder = new TextEncoder();
	for (const entry of saved.sources) {
		const source = sourceOf(entry);
		if (source === null || days.has(source.date)) return null;
		days.add(source.date);
		const matches = new Set(rows.filter((row) => row.date === source.date && row.run_id === source.run_id)
			.map((row) => row.score_pool_histogram).filter((value): value is string => typeof value === 'string'));
		let found: JudgePool | null = null;
		for (const text of matches) {
			if (await sha256Hex(encoder.encode(text).buffer) === source.histogram_sha256) {
				found = judgePool(text);
				break;
			}
		}
		if (!found || !found.total || found.stamp !== target.stamp || found.edges.length !== target.edges.length ||
			found.edges.some((edge, index) => edge !== target.edges[index])) return null;
		for (const [index, count] of found.counts.entries()) counts[index] += count;
	}
	const total = counts.reduce((sum, n) => sum + n, 0);
	return Number.isSafeInteger(total) ? { stamp: target.stamp, edges: target.edges, counts, total } : null;
}
