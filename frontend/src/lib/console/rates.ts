/** What do reading and writing cost for the same recorded amount of work? */
import type { Row } from '../data/ledger';

/** The ledger reports milliseconds; the old throughput caller prints tokens a second. */
const MS_PER_SECOND = 1000;

function measured(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The existing server caller's two independent rates, including its absent-cache behavior. */
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
				? evaluated / (prefillMs / MS_PER_SECOND)
				: null,
		write:
			decodeMs !== null && decodeMs > 0 && written !== null && written > 0
				? written / (decodeMs / MS_PER_SECOND)
				: null
	};
}

/** A typed door cell that was actually recorded; an empty string is not zero. */
export function finiteCell(value: Row[string] | undefined): number | null {
	if (typeof value !== 'number' && typeof value !== 'string') return null;
	if (typeof value === 'string' && value.trim() === '') return null;
	const number = Number(value);
	return Number.isFinite(number) ? number : null;
}

/** The same upper middle and percentile index as eval-instruments.at(), never interpolation. */
export function nearestRank(values: readonly number[], fraction: number): number | null {
	if (!Number.isFinite(fraction) || fraction < 0 || fraction > 1) {
		throw new Error('percentile fraction must be between zero and one');
	}
	if (values.some((value) => !Number.isFinite(value))) throw new Error('percentile holds a non-finite value');
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	return sorted[Math.min(sorted.length - 1, Math.floor(fraction * sorted.length))];
}

export interface QualifiedWork {
	readonly freshInput: number;
	readonly output: number;
	readonly readMsPerToken: number;
	readonly writeMsPerToken: number;
}

/** Unlike legacy itemRates, comparable work requires all five instrument cells. */
export function qualifyingWork(row: Row): QualifiedWork | null {
	const prefill = finiteCell(row.prefill_ms);
	const input = finiteCell(row.input_tokens);
	const cached = finiteCell(row.cached_tokens);
	const decode = finiteCell(row.decode_ms);
	const output = finiteCell(row.output_tokens);
	if (prefill === null || input === null || cached === null || decode === null || output === null ||
		prefill < 0 || decode < 0 || cached < 0 || input - cached <= 0 || output <= 0) return null;
	const freshInput = input - cached;
	return { freshInput, output, readMsPerToken: prefill / freshInput, writeMsPerToken: decode / output };
}

export interface ReferenceWork {
	readonly cpuModel: string | null;
	readonly referenceRows: number;
	readonly qualifying: number;
	readonly unqualified: number;
	readonly unnamedMachine: number;
	readonly freshInput: number | null;
	readonly output: number | null;
}

/** Most qualifying articles wins; a tie uses the machine's name, not input order. */
export function referenceWork(rows: readonly Row[]): ReferenceWork {
	const counts = new Map<string, number>();
	const work: QualifiedWork[] = [];
	let unnamedMachine = 0;
	for (const row of rows) {
		const recorded = qualifyingWork(row);
		if (recorded === null) continue;
		work.push(recorded);
		if (typeof row.cpu_model !== 'string' || row.cpu_model.trim() === '') unnamedMachine += 1;
		else counts.set(row.cpu_model, (counts.get(row.cpu_model) ?? 0) + 1);
	}
	const reference = [...counts].sort(([a, n], [b, m]) => m - n || (a < b ? -1 : a > b ? 1 : 0))[0];
	return {
		cpuModel: reference?.[0] ?? null, referenceRows: reference?.[1] ?? 0,
		qualifying: work.length, unqualified: rows.length - work.length, unnamedMachine,
		freshInput: nearestRank(work.map((item) => item.freshInput), 0.5),
		output: nearestRank(work.map((item) => item.output), 0.5)
	};
}

/** Price the fixed typical article with a day's or run's qualifying reference readings. */
export function typicalSeconds(rows: readonly Row[], reference: ReferenceWork): {
	readonly read: number | null; readonly write: number | null; readonly from: number; readonly outOf: number
} {
	const work = rows.flatMap((row) => {
		if (reference.cpuModel === null || row.cpu_model !== reference.cpuModel) return [];
		const recorded = qualifyingWork(row);
		return recorded === null ? [] : [recorded];
	});
	const read = nearestRank(work.map((item) => item.readMsPerToken), 0.5);
	const write = nearestRank(work.map((item) => item.writeMsPerToken), 0.5);
	return {
		read: read === null || reference.freshInput === null ? null : read * reference.freshInput / MS_PER_SECOND,
		write: write === null || reference.output === null ? null : write * reference.output / MS_PER_SECOND,
		from: work.length, outOf: rows.length
	};
}
