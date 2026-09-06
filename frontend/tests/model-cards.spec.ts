/** One selected view feeds every model card, built in one pass.
 *
 * Row #15 of `TODO/20260906-constant-cost-reads-plan.md` (Finding 107) turns the
 * model route's per-card trend - drawn eleven times, once for each card, each
 * time re-walking the open window - into a single pass that fills every card's
 * line together. The output does not move: the arithmetic is the one the eleven
 * passes ran. What this file protects is that it stays that way, and that a card
 * reads its OWN column rather than a neighbour's.
 *
 * The route cannot prove this against the canary day. That fixture runs one
 * model start to finish over two days, and every one of the eleven columns is
 * either a single day or two equal days, so every drawn line is empty or flat
 * and every movement is null - the page has nothing per-column to disagree
 * about. So the selected-view builder is lifted into `$lib/console/model-cards`
 * and driven here from a window built to move each column its own way.
 *
 * Nothing here reads a committed ledger. A test that walks the archive costs
 * more every published day (Rule #12); this window is three rows, written down.
 */

import { expect, test } from '@playwright/test';

import { sparklineMarks } from '../src/lib/charts/sparkline';
import { buildCardTrends } from '../src/lib/console/model-cards';

/** A fabricated model window, oldest first the way the route holds it. Each
 * column moves its own way, so a builder that copied one column onto the rest
 * cannot pass by luck; `sparse` is null on the first day, so it draws two points
 * where the others draw three and a swap lands on it differently. */
type FakeDay = {
	date: string;
	steep: number;
	falling: number;
	gentle: number;
	sparse: number | null;
};

const WINDOW: FakeDay[] = [
	{ date: '2026-08-01', steep: 10, falling: 100, gentle: 10, sparse: null },
	{ date: '2026-08-02', steep: 20, falling: 50, gentle: 20, sparse: 9 },
	{ date: '2026-08-03', steep: 40, falling: 25, gentle: 30, sparse: 18 }
];

const KEYS = ['steep', 'falling', 'gentle', 'sparse'] as const;

const read = (day: FakeDay, key: string): number | null =>
	(day as unknown as Record<string, number | null>)[key];

test.describe('a model card reads one selected view, in one pass', () => {
	test('every card carries the movement of its own column, not a neighbour', () => {
		const trends = buildCardTrends(KEYS, WINDOW, read, []);

		// Each is its own column's movement, computed by the same function the page
		// draws the line with. A builder that returned one column for every key -
		// the drift eleven separate passes invited - fails at the first mismatch.
		expect(trends.get('steep')?.marks.movement).toBe(sparklineMarks([10, 20, 40]).movement);
		expect(trends.get('falling')?.marks.movement).toBe(sparklineMarks([100, 50, 25]).movement);
		expect(trends.get('gentle')?.marks.movement).toBe(sparklineMarks([10, 20, 30]).movement);
		// `sparse` is null on the first day, so its line is the two days it drew.
		expect(trends.get('sparse')?.marks.movement).toBe(sparklineMarks([9, 18]).movement);

		// And the four are genuinely four numbers, so the assertions above are not
		// four ways of reading one column.
		const moved = KEYS.map((key) => String(trends.get(key)?.marks.movement));
		expect(new Set(moved).size).toBe(KEYS.length);
	});

	test('a swap lands on each column by that column drawn days', () => {
		const swaps = [{ date: '2026-08-02', model: 'b' }];
		const trends = buildCardTrends(KEYS, WINDOW, read, swaps);

		// `steep` drew all three days, so 2026-08-02 is the middle of three, at 1/2.
		expect(trends.get('steep')?.rules).toEqual([
			{ at: 0.5, label: 'The model changed to b on 2026-08-02.' }
		]);
		// `sparse` drew only 2026-08-02 and 2026-08-03, so the swap is its first
		// drawn day. A rule across the left edge would say the ground moved before
		// the line began, so none is drawn - the column's own dates decide, not the
		// window's. A builder that shared one date list across the cards would draw
		// one here.
		expect(trends.get('sparse')?.rules).toEqual([]);
	});

	test('the window is read once per cell, whatever the card count', () => {
		let reads = 0;
		const counted = (day: FakeDay, key: string): number | null => {
			reads += 1;
			return read(day, key);
		};

		buildCardTrends(KEYS, WINDOW, counted, []);

		// One read per day per column and no more. The eleven passes this replaces
		// read the whole window once for each card; here a cell is touched once
		// however many cards there are.
		expect(reads).toBe(WINDOW.length * KEYS.length);
	});
});
