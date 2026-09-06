/** The two chart builders row 13 stops sorting a whole field to read a little.
 *
 * Row 13 of `TODO/20260906-constant-cost-reads-plan.md` takes the full sort out
 * of two derivations that only wanted a small answer from it: `rank` sorted
 * every candidate to keep the top few, and `sizeGain` sorted every manifest to
 * subtract its two ends. Each is now one pass over the field.
 *
 * That is two claims and they share one shape. **The output does not move** -
 * the parity halves hold the new code against a byte-for-byte copy of the old,
 * over randomized inputs that include the ties a bounded selection is easiest to
 * get wrong on. **The work no longer grows with the field** - the counted halves
 * put a read counter on each entry, double the field sixteen-fold, and assert
 * the bounded pass reads an entry a flat number of times while the sort it
 * replaced climbs by about log2 of the field. The counted arm is the red this
 * row turned green: run it against the pre-row code and the flat assertion fails.
 *
 * Nothing here reads a committed ledger. A test that walks the archive costs
 * more every published day (Rule #12), and both shapes are reachable from a
 * built fixture.
 */

import { expect, test } from '@playwright/test';

import { rank, percentOf } from '../src/lib/charts/rank';
import type { RankedDisplay, Rankable, Ranked } from '../src/lib/charts/rank';
import { sizeGain } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';

/** A seeded generator, so the randomized fields reproduce on every machine. A
 * plain linear congruential generator; the numbers only have to vary and
 * repeat. */
function seeded(seed: number): () => number {
	let state = seed >>> 0;
	return () => {
		state = (state * 1_664_525 + 1_013_904_223) >>> 0;
		return state / 4_294_967_296;
	};
}

// --- ranked list ----------------------------------------------------------

type RankFn = <T extends RankedDisplay>(entries: readonly Rankable<T>[], cap: number) => Ranked<T>;

/** `rank()` as it stood before the bounded selection: sort the whole finite
 * set, slice to the cap, fold the discarded tail directly. The oracle holds the
 * new one against this, so a change of order, of a tie, or of a hidden total is
 * a red. */
const sortSliceRank: RankFn = (entries, cap) => {
	const measured = entries.filter((e) => Number.isFinite(e.value));
	const ordered = [...measured].sort(
		(a, b) => b.value - a.value || (b.tiebreak ?? 0) - (a.tiebreak ?? 0) || a.key.localeCompare(b.key)
	);
	const kept = cap > 0 ? ordered.slice(0, cap) : ordered;
	const dropped = ordered.slice(kept.length);
	const max = kept.reduce((high, e) => Math.max(high, e.value), 0);
	return {
		rows: kept.map((e) => {
			const fraction = max > 0 ? e.value / max : 0;
			return { key: e.key, value: e.value, fraction, percent: percentOf(fraction), row: e.row };
		}),
		max,
		hidden: dropped.length,
		hiddenValue: dropped.reduce((sum, e) => sum + e.value, 0),
		empty: kept.length === 0
	};
};

test.describe('the ranked list caps without a full sort', () => {
	test('THE ORACLE: capping matches sorting everything and slicing, ties and all', () => {
		const rng = seeded(20260913);
		// A small pool of values, keys and tiebreaks, so equal magnitudes and true
		// ties - equal value, equal tiebreak, equal key - come up often. That is
		// the case a bounded selection is easiest to get wrong on, and the distinct
		// `row` labels below make the test see which tied entry was kept.
		for (let round = 0; round < 400; round += 1) {
			const n = 1 + Math.floor(rng() * 24);
			const entries: Rankable<RankedDisplay>[] = Array.from({ length: n }, (_, i) => {
				const roll = rng();
				const value =
					roll < 0.08
						? Number.NaN
						: roll < 0.12
							? Number.POSITIVE_INFINITY
							: Math.floor(rng() * 6) - 2;
				return {
					key: `k${Math.floor(rng() * 5)}`,
					value,
					tiebreak: Math.floor(rng() * 3),
					row: { label: `row-${i}`, value: String(value) }
				};
			});
			for (const cap of [0, 1, 2, 3, n - 1, n, n + 3]) {
				expect(rank(entries, cap), `n=${n} cap=${cap} round=${round}`).toEqual(
					sortSliceRank(entries, cap)
				);
			}
		}
	});

	test('the discarded tail is not sorted, and a full sort would be', () => {
		const cap = 8;
		// Each entry counts every read of its own magnitude. A bounded selection
		// reads an entry a fixed number of times whatever the field holds; a full
		// sort reads it about log2(n) times. Across a 16x field the sort climbs by
		// roughly log2(16) = 4, doubled by the two-sided compare, and the bounded
		// pass does not move.
		const perEntry = (build: RankFn, n: number): number => {
			let reads = 0;
			const rng = seeded(n);
			const entries: Rankable<RankedDisplay>[] = Array.from({ length: n }, (_, i) => {
				const magnitude = Math.floor(rng() * n * 4);
				return {
					key: `k${i}`,
					get value() {
						reads += 1;
						return magnitude;
					},
					row: { label: `row-${i}`, value: String(magnitude) }
				};
			});
			const ranked = build(entries, cap);
			expect(ranked.rows.length, `the cap held at n=${n}`).toBe(cap);
			return reads / n;
		};

		// The optimization: reads per entry do not climb with the field.
		const boundedClimb = perEntry(rank, 6400) - perEntry(rank, 400);
		expect(
			boundedClimb,
			`the bounded selection climbed by ${boundedClimb.toFixed(2)} reads an entry over a 16x field`
		).toBeLessThan(2);

		// The full sort it replaced climbs about four. Asserted so the arm above
		// cannot pass by measuring nothing: if the sort stopped growing, this
		// oracle would prove nothing about the bounded pass.
		const sortedClimb = perEntry(sortSliceRank, 6400) - perEntry(sortSliceRank, 400);
		expect(
			sortedClimb,
			`the full sort read an entry ${sortedClimb.toFixed(2)} more times over a 16x field`
		).toBeGreaterThan(3);
	});
});

// --- site size gain -------------------------------------------------------

type GainFn = (manifests: readonly RunSummary[]) => number | null;

function manifest(date: string, siteBytes: number): RunSummary {
	return { date, runs: 1, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}

/** `YYYY-MM-DD`, counting forward from a fixed first day. */
function dayISO(index: number): string {
	const at = new Date(Date.UTC(2026, 0, 1));
	at.setUTCDate(at.getUTCDate() + index);
	return at.toISOString().slice(0, 10);
}

/** `sizeGain()` as it stood before the single pass: sort the whole set by date,
 * subtract the ends. The oracle holds the new one against this. */
const sortEndpointsGain: GainFn = (manifests) => {
	const ordered = [...manifests].sort((a, b) => a.date.localeCompare(b.date));
	if (ordered.length < 2) return null;
	return ordered[ordered.length - 1].siteBytes - ordered[0].siteBytes;
};

test.describe('the size gain reads the ends without a full sort', () => {
	test('THE ORACLE: the gain is the latest date less the earliest, ties and all', () => {
		const rng = seeded(20260914);
		// Dates drawn from a small set, so the same date lands on several manifests
		// with different sizes - the tie the single pass has to resolve the way a
		// stable sort did, or it subtracts the wrong day's bytes.
		const dates = ['2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04'];
		for (let round = 0; round < 400; round += 1) {
			const n = Math.floor(rng() * 6); // 0..5, so the under-two (null) case is covered
			const manifests = Array.from({ length: n }, () =>
				manifest(dates[Math.floor(rng() * dates.length)], Math.floor(rng() * 5_000_000))
			);
			expect(sizeGain(manifests), `round=${round} n=${n}`).toBe(sortEndpointsGain(manifests));
		}
	});

	test('date reads per manifest stay flat, and a full sort would climb', () => {
		// Each manifest counts every read of its own date. The single pass reads a
		// manifest a fixed number of times; a sort reads it about log2(n) times.
		const perManifest = (build: GainFn, n: number): number => {
			let reads = 0;
			const rng = seeded(n);
			const manifests: RunSummary[] = Array.from({ length: n }, (_, i) => {
				const date = dayISO(Math.floor(rng() * n));
				return {
					...manifest(date, i),
					get date() {
						reads += 1;
						return date;
					}
				};
			});
			build(manifests);
			return reads / n;
		};

		const passClimb = perManifest(sizeGain, 6400) - perManifest(sizeGain, 400);
		expect(
			passClimb,
			`the single pass climbed by ${passClimb.toFixed(2)} reads a manifest over a 16x field`
		).toBeLessThan(2);

		const sortedClimb = perManifest(sortEndpointsGain, 6400) - perManifest(sortEndpointsGain, 400);
		expect(
			sortedClimb,
			`the full sort read a manifest ${sortedClimb.toFixed(2)} more times over a 16x field`
		).toBeGreaterThan(3);
	});
});
