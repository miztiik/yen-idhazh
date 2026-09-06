/** The six build reductions row 2 replaces, and the two things that must hold.
 *
 * Row 2 of `TODO/20260906-constant-cost-reads-plan.md` turns repeated
 * reductions into single passes over the same input: the config accessors, the
 * date and run buckets in `model-work`, the run-to-health join in
 * `runtime-counters`, the per-article band ladder, the per-bin scans in
 * `distribution`, and the daily buckets in `failureSeries`.
 *
 * **Byte-identical output is the hard requirement** - this row changes no
 * number on any page - so half of this file compares what the reductions
 * return against `fixtures/one-pass-golden.json`, captured from the
 * implementation the row replaced. Regenerating that file is an admission that
 * the output moved and needs the reason written down:
 *
 * ```powershell
 * $env:IDHAZH_WRITE_ONE_PASS_GOLDEN = '1'; npm run test:logic
 * ```
 *
 * The other half counts visits. A reduction that reads the whole input again
 * for every run, every article or every bin costs more as the input grows, and
 * the only way to see that from outside is to count the reads and double the
 * input. The audit measured the run-to-health join precisely: 4 runs over 16
 * health rows cost 64 checks, 8 over 32 cost 256, and 16 over 64 cost 1,024 -
 * doubling both dimensions quadrupled the work. Those three arms are below.
 *
 * Nothing here reads a committed ledger. A test that walks the archive costs
 * more every published day (Rule #12), and every shape this row is about is
 * reachable from a built fixture.
 */

import { expect, test } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { distribution, quantile, type Distribution } from '../src/lib/charts/series';
import { frameConfig, summarizeConfig } from '../src/lib/server/config';
import { failureSeries } from '../src/lib/charts/series';
import { modelByDate, modelWork, runLengths, sourceCuts } from '../src/lib/server/model-work';
import { machineCounters, type MachineLimits } from '../src/lib/server/runtime-counters';
import type { SummaryBand, TelemetryRow } from '../src/lib/charts/series';
import {
	BANDS,
	counterRows,
	dayOf,
	healthRows,
	scoreRows,
	telemetryRows,
	timings,
	type Sizes
} from './support/reduction-input';

const HERE = dirname(fileURLToPath(import.meta.url));
const GOLDEN = join(HERE, 'fixtures', 'one-pass-golden.json');

/** The two ceilings the machine page reads a counter against. Fixed here so a
 * config edit cannot move the golden. */
const LIMITS: MachineLimits = { contextWindow: 8_192, jobTimeoutSeconds: 150 * 60 };

/** One ledger big enough that a repeated reduction and a single pass disagree
 * about the work, and small enough to read in a diff. */
const PARITY: Sizes = { runs: 8, shards: 4, items: 96 };

const TELEMETRY_DAYS = 6;
const TELEMETRY_PER_DAY = 20;
const WINDOW = { start: dayOf(0), end: dayOf(TELEMETRY_DAYS - 1) };

/** Everything the six reductions return over one input. */
function reductions(): Record<string, unknown> {
	const counters = counterRows(PARITY);
	const health = healthRows(PARITY);
	const scores = scoreRows(PARITY);
	return {
		machineCounters: machineCounters(counters, health, LIMITS),
		modelWork: modelWork(scores, health),
		modelByDate: [...modelByDate(scores)],
		runLengths: runLengths(scores, BANDS),
		sourceCuts: sourceCuts(health, { days: TELEMETRY_DAYS, limit: 4 }),
		failureSeries: failureSeries(telemetryRows(TELEMETRY_DAYS, TELEMETRY_PER_DAY), WINDOW),
		distribution: distribution(timings(400))
	};
}

/** A row whose named cell counts every read of itself.
 *
 * Key order is preserved, because a fixture that reordered the cells would be
 * a different input from the one the golden was taken over.
 */
function countingRows<T extends Record<string, unknown>>(
	rows: readonly T[],
	cell: keyof T & string,
	onRead: () => void
): T[] {
	return rows.map((row) => {
		const seen = {} as Record<string, unknown>;
		for (const [key, value] of Object.entries(row)) {
			if (key === cell) {
				Object.defineProperty(seen, key, {
					enumerable: true,
					configurable: true,
					get: () => {
						onRead();
						return value;
					}
				});
			} else {
				seen[key] = value;
			}
		}
		return seen as T;
	});
}

test.describe('the reductions return what they returned before', () => {
	test('every one of the six is byte-identical to the golden', () => {
		const found = `${JSON.stringify(reductions(), null, '\t')}\n`;

		if (process.env.IDHAZH_WRITE_ONE_PASS_GOLDEN) {
			mkdirSync(dirname(GOLDEN), { recursive: true });
			writeFileSync(GOLDEN, found, 'utf8');
		}

		expect(existsSync(GOLDEN), `${GOLDEN} is missing`).toBe(true);
		expect(found).toBe(readFileSync(GOLDEN, 'utf8'));
	});

	test('the golden covers a ledger the reductions had something to do', () => {
		// A golden taken over an input every reduction returned nothing for would
		// pass whatever the implementation did.
		const found = reductions();
		const counters = found.machineCounters as { runs: unknown[]; refused: unknown[] };
		expect(counters.runs.length).toBe(PARITY.runs);
		expect(counters.refused).toEqual([]);
		expect((found.modelWork as unknown[]).length).toBeGreaterThan(0);
		expect((found.runLengths as unknown[]).length).toBe(PARITY.runs);
		expect((found.sourceCuts as { rows: unknown[] }).rows.length).toBeGreaterThan(0);
		expect((found.distribution as Distribution).bins.length).toBeGreaterThan(4);
	});
});

test.describe('the run-to-health join visits each row once', () => {
	/** The three arms the audit measured, doubling both dimensions. */
	const ARMS: Sizes[] = [
		{ runs: 4, shards: 2, items: 16 },
		{ runs: 8, shards: 2, items: 32 },
		{ runs: 16, shards: 2, items: 64 }
	];

	function visitsFor(sizes: Sizes): number {
		let visits = 0;
		const health = countingRows(healthRows(sizes), 'run_id', () => {
			visits += 1;
		});
		const found = machineCounters(counterRows(sizes), health, LIMITS);
		// Every run has to be accepted, or a lower count would be the refusal
		// rather than the reduction.
		expect(found.refused, `refused runs at ${sizes.runs} runs`).toEqual([]);
		expect(found.runs.length).toBe(sizes.runs);
		return visits;
	}

	test('a run does not scan the whole health ledger', () => {
		for (const sizes of ARMS) {
			const visits = visitsFor(sizes);
			expect(
				visits,
				`${sizes.runs} runs over ${sizes.items} health rows read run_id ${visits} times; ` +
					`the join before this row read it ${sizes.runs * sizes.items} times`
			).toBe(sizes.items);
		}
	});

	test('doubling both dimensions doubles the work rather than quadrupling it', () => {
		const counted = ARMS.map(visitsFor);
		expect(counted[1] / counted[0]).toBe(2);
		expect(counted[2] / counted[1]).toBe(2);
	});
});

test.describe('the failure denominators are counted in one pass', () => {
	test("a row's outcome is read once, not once per stage", () => {
		let reads = 0;
		const rows = telemetryRows(TELEMETRY_DAYS, TELEMETRY_PER_DAY);
		const counted = countingRows(rows as unknown as Record<string, unknown>[], 'outcome', () => {
			reads += 1;
		}) as unknown as TelemetryRow[];

		const series = failureSeries(counted, WINDOW);
		expect(series.length).toBe(3);
		expect(series[0].days.length).toBe(TELEMETRY_DAYS);
		expect(
			reads,
			`each of the ${rows.length} rows was read ${reads / rows.length} times`
		).toBe(rows.length);
	});
});

test.describe('the band ladder is prepared once', () => {
	function ladderReads(sizes: Sizes): { reads: number; articles: number } {
		let reads = 0;
		const bands = countingRows(BANDS as unknown as Record<string, unknown>[], 'min_source_words', () => {
			reads += 1;
		}) as unknown as SummaryBand[];
		const scores = scoreRows(sizes);
		runLengths(scores, bands);
		return { reads, articles: scores.length };
	}

	test('an extra article costs one look down the ladder and no re-sort', () => {
		const small = ladderReads({ runs: 2, shards: 2, items: 8 });
		const large = ladderReads({ runs: 2, shards: 2, items: 16 });
		const perArticle = (large.reads - small.reads) / (large.articles - small.articles);
		expect(
			perArticle,
			`each extra article read the ladder ${perArticle} times; the ladder holds ${BANDS.length} rungs`
		).toBeLessThanOrEqual(BANDS.length);
	});
});

test.describe('the histogram bins in one pass over the sorted values', () => {
	test('every bin holds what a full scan would put in it', () => {
		const values = timings(400);
		const found = distribution(values);
		expect(found).not.toBeNull();
		const spread = found as Distribution;

		for (const bin of spread.bins) {
			const scanned = values.filter((ms) => ms / 1000 >= bin.from && ms / 1000 < bin.to).length;
			expect(bin.n, `the bin from ${bin.from}s to ${bin.to}s`).toBe(scanned);
		}
		// The trimmed bars still hold every value, because trimming only drops
		// empty ones.
		expect(spread.bins.reduce((total, bin) => total + bin.n, 0)).toBe(values.length);

		// The two rules are taken over the values and never off the bars.
		const sorted = [...values].sort((a, b) => a - b);
		expect(spread.median).toBe(quantile(sorted, 0.5));
		expect(spread.p95).toBe(quantile(sorted, 0.95));
		expect(spread.n).toBe(values.length);
	});
});

test.describe('the config files are read once', () => {
	test('two calls hand back the same parsed block', () => {
		// A block the merge passes through by reference. Re-reading the file would
		// hand back a new array every call.
		expect(summarizeConfig().bands).toBe(summarizeConfig().bands);
		expect(frameConfig().breakpoints_px).toBe(frameConfig().breakpoints_px);
	});

	test('the committed values still resolve', () => {
		expect(summarizeConfig().bands.length).toBeGreaterThan(0);
		expect(frameConfig().breakpoints_px).toHaveLength(3);
		// Ascending, which is the order the ladder readers rely on.
		const bands = summarizeConfig().bands;
		for (let index = 1; index < bands.length; index += 1) {
			expect(bands[index].min_source_words).toBeGreaterThan(bands[index - 1].min_source_words);
		}
	});
});
