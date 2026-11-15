/** One selected view feeds every retained card in one pass.
 *
 * A bounded input moves each column independently, so a card cannot borrow a
 * neighbour's movement or date range and pass on equal canary readings.
 */

import { expect, test } from '@playwright/test';

import { sparklineShape } from '../src/lib/charts/sparkline';
import { buildCardTrends } from '../src/lib/console/model-cards';
import { cardModelRule, cardTrendDays } from '../src/lib/console/model/cards';
import type { ModelRule } from '../src/lib/charts/d3/model-rule';

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
	test('a mini chart keeps its recent readings and warns only about changes inside its own history', () => {
		const days = [
			{ date: '2030-04-01' }, { date: '2030-05-20' }, { date: '2030-06-01' },
			{ date: '2030-06-11' }, { date: '2030-06-14' }
		];
		const rule: ModelRule = { changes: [
			{ date: '2030-04-01', kind: 'settings', words: 'The old runtime changed.' },
			{ date: '2030-05-20', kind: 'settings', words: 'The older prompt changed.' },
			{ date: '2030-06-11', kind: 'settings', words: 'The prompt changed.' },
			{ date: '2030-06-12', kind: 'checker', words: 'The checker changed.' }
		], note: 'The settings record starts partway through the selected window.' };
		for (const start of ['2030-03-17', '2030-05-16', '2030-06-01']) {
			const recent = cardTrendDays(days.filter((day) => day.date >= start));
			expect(recent.map((day) => day.date)).toEqual(['2030-06-01', '2030-06-11', '2030-06-14']);
			const card = cardModelRule(rule, recent.map((day) => day.date));
			if ('declined' in card) throw new Error('A recorded card rule was declined.');
			expect(card.changes.map((change) => change.date)).toEqual(['2030-06-11']);
			expect(card.note).toContain('2030-06-12');
			expect(card.note).not.toMatch(/2030-04-01|2030-05-20|partway/);
		}
		const sparse = cardModelRule(rule, ['2030-06-14']);
		expect(sparse).toEqual({ changes: [], note: null });
		expect(cardModelRule(rule, [])).toEqual({ changes: [], note: null });
		const unavailable = { declined: 'No dated settings record is available for this card.' };
		expect(cardModelRule(unavailable, ['2030-06-14'])).toEqual(unavailable);
	});

	test('every card carries the movement of its own column, not a neighbour', () => {
		const trends = buildCardTrends(KEYS, WINDOW, read, []);

		// Each is its own column's movement, computed by the same function the page
		// draws the line with. A builder that returned one column for every key -
		// returning one column for every key fails at the first mismatch.
		expect(trends.get('steep')?.marks.movement).toBe(sparklineShape([10, 20, 40]).movement);
		expect(trends.get('falling')?.marks.movement).toBe(sparklineShape([100, 50, 25]).movement);
		expect(trends.get('gentle')?.marks.movement).toBe(sparklineShape([10, 20, 30]).movement);
		// `sparse` is null on the first day, so its line is the two days it drew.
		expect(trends.get('sparse')?.marks.movement).toBe(sparklineShape([9, 18]).movement);
		// And each drawn point keeps the day it was taken on, so the strip under the
		// line heads every value with its own date.
		expect(trends.get('sparse')?.marks.dates).toEqual(['2026-08-02', '2026-08-03']);
		expect(trends.get('steep')?.marks.dates).toEqual(WINDOW.map((day) => day.date));

		// And the four are genuinely four numbers, so the assertions above are not
		// four ways of reading one column.
		const moved = KEYS.map((key) => String(trends.get(key)?.marks.movement));
		expect(new Set(moved).size).toBe(KEYS.length);
	});

	test('a swap lands on each column by that column drawn days', () => {
		const swaps = [{ date: '2026-08-02', model: 'b' }];
		const trends = buildCardTrends(KEYS, WINDOW, read, swaps);

		// `steep` drew all three days, so 2026-08-02 is the middle of three, its
		// second point. The sentence names the day the way the strip heads it.
		expect(trends.get('steep')?.rules).toEqual([
			{ point: 1, label: 'The model changed to b on 2 Aug 2026.' }
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

		// One read per day per column, however many cards there are.
		expect(reads).toBe(WINDOW.length * KEYS.length);
	});
});
