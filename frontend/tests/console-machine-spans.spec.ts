/** The span breakdown panel: the drawn residual against the committed rollup.
 *
 * The panel exists to draw one figure a reader could not get anywhere else -
 * `unattributed_ms`, the slice of a shard's wall clock that fell outside every
 * item. The oracle here re-derives that figure straight from the committed
 * rollup cells, with none of the panel's own code in the loop, and holds it
 * against the number the page drew. If the two ever part, the panel is drawing a
 * residual that does not reconcile, which is the one thing it must never do.
 *
 * The empty state is reached the way the real site reaches it every day until a
 * traced run commits: a rollup with nothing in it but its header. It has to name
 * the day the record begins, or a reader meets a blank panel with no way to tell
 * "not begun yet" from "something broke".
 *
 * The canary build carries the fixture rollup this reads (`build-canary.mjs`);
 * the committed rollup is empty, so the real page shows the empty state and this
 * spec runs against the fixture, the same split every console-machine spec is
 * built on.
 */

import { expect, test, type Page } from '@playwright/test';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { readShards } from '../src/lib/server/payload';
import { foldRollup, spanBreakdown, SPAN_RECORD_STARTS } from '../src/lib/server/span-rollup';

/** The canary state tree the browser suite is built from. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');
const ROLLUP = join(CANARY, 'span-rollup');

/** What the committed rollup itself says each shard's item row holds, read as
 * raw cells with none of the reader's fold in between. This is the independent
 * side of the oracle: the drawn number is checked against this, not against
 * another call into the code that drew it. */
function committedItemRows(): Map<number, { item: number; residual: number | null }> {
	const table = readShards(ROLLUP);
	const items = table.rows.filter((row) => row.span_name === 'item');
	return new Map(
		items.map((row) => [
			Number(row.shard),
			{
				item: Number(row.total_ms),
				residual: (row.unattributed_ms ?? '') === '' ? null : Number(row.unattributed_ms)
			}
		])
	);
}

/** Every shard bar the panel drew, with the figures it carries. */
async function drawnBars(page: Page): Promise<
	{ shard: number; wall: number; item: number; residual: string; segs: { kind: string; ms: number }[] }[]
> {
	return page.locator('[data-span-shard]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			shard: Number(node.getAttribute('data-span-shard')),
			wall: Number(node.getAttribute('data-span-wall-ms')),
			item: Number(node.getAttribute('data-span-item-ms')),
			residual: node.getAttribute('data-span-residual-ms') ?? '',
			segs: [...node.querySelectorAll('[data-span-seg]')].map((seg) => ({
				kind: seg.getAttribute('data-span-seg') ?? '',
				ms: Number(seg.getAttribute('data-span-seg-ms'))
			}))
		}))
	);
}

test.describe('the span breakdown draws a residual that reconciles', () => {
	test('THE ORACLE: the drawn residual is the rollup\'s unattributed_ms, cell for cell', async ({
		page
	}) => {
		const committed = committedItemRows();
		expect(committed.size, 'the canary rollup carries no item row - the fixture is missing').toBeGreaterThan(0);

		await page.goto('/console/machine/');
		const board = page.locator('[data-span-board]');
		await expect(board).toHaveCount(1);
		// The canary carries a rollup, so an empty board here is a broken read
		// rather than a state to tolerate - an assertion that returned early on it
		// would pass having checked nothing.
		await expect(board).not.toHaveAttribute('data-span-board', 'empty');

		const bars = await drawnBars(page);
		expect(bars.length, 'the panel drew no shard').toBe(committed.size);

		for (const [shard, cell] of committed) {
			const bar = bars.find((one) => one.shard === shard);
			expect(bar, `shard ${shard} was not drawn`).toBeTruthy();

			// The whole point: the drawn residual is the committed unattributed_ms.
			const drawnResidual = bar!.residual === '' ? null : Number(bar!.residual);
			expect(drawnResidual, `shard ${shard} drew the wrong residual`).toBe(cell.residual);
			expect(bar!.item, `shard ${shard} drew the wrong item time`).toBe(cell.item);

			// item + residual = wall, the fold's invariant, read straight off the
			// page - and every drawn slice sums to that same wall clock, so the bar
			// accounts for every millisecond and invents none.
			const wall = cell.item + (cell.residual ?? 0);
			expect(bar!.wall, `shard ${shard} drew the wrong wall clock`).toBe(wall);
			expect(bar!.item + (drawnResidual ?? 0)).toBe(bar!.wall);
			expect(
				bar!.segs.reduce((sum, seg) => sum + seg.ms, 0),
				`shard ${shard}'s slices do not sum to its wall clock`
			).toBe(wall);
		}
	});

	test('the residual is drawn beside the stages, as the last slice of the bar', async ({ page }) => {
		await page.goto('/console/machine/');
		const bars = await drawnBars(page);
		expect(bars.length).toBeGreaterThan(0);
		for (const bar of bars) {
			if (bar.residual === '') continue;
			// Overhead is not a stage and is never buried inside the item work: it is
			// the right-hand end of the bar, beside the stages, so a reader sees at a
			// glance how much of the clock nothing filled.
			expect(bar.segs.at(-1)?.kind, `shard ${bar.shard} did not draw the residual last`).toBe(
				'residual'
			);
		}
	});

	test('the populated panel names the day the span record begins', async ({ page }) => {
		await page.goto('/console/machine/');
		// The flip is a discontinuity: the record started on a day, and a reader
		// must be told which, on the surface that draws it.
		await expect(page.locator('[data-span-board]')).toContainText(SPAN_RECORD_STARTS);
	});
});

test.describe('the reader folds the committed rollup', () => {
	test('the canary rollup folds to one run whose bars reconcile', () => {
		const runs = foldRollup(readShards(ROLLUP));
		expect(runs.length, 'the canary rollup folded to no run').toBeGreaterThan(0);

		const view = spanBreakdown(runs[0]);
		expect(view.empty).toBe(false);
		expect(view.shards.length).toBeGreaterThan(1);
		expect(view.recordStarts).toBe(SPAN_RECORD_STARTS);

		for (const bar of view.shards) {
			// item + residual = wall, and every slice sums to it - the same invariant
			// the fold enforces on the backend, checked here on the read side.
			expect(bar.itemMs + (bar.residualMs ?? 0)).toBe(bar.wallMs);
			expect(bar.segments.reduce((sum, seg) => sum + seg.ms, 0)).toBe(bar.wallMs);
			// The four sub-steps sit inside the item time, so the rest of it is never
			// negative: a bar can only draw slices that add up to a real clock.
			const other = bar.segments.find((seg) => seg.kind === 'other');
			expect(other, `shard ${bar.shard} drew no rest-of-item slice`).toBeTruthy();
			expect(other!.ms).toBeGreaterThanOrEqual(0);
		}
	});

	test('it reads the ledger through STATE_ROOT, so a fixture tree can replace it', () => {
		// The canary suite builds a site out of fixture runs by pointing STATE_ROOT
		// at a copy. A path built any other way reads the real ledger anyway, and
		// the canary silently draws the wrong tree.
		const source = readFileSync(
			join(process.cwd(), 'src', 'lib', 'server', 'span-rollup.ts'),
			'utf8'
		);
		expect(source).toContain("join(STATE_ROOT, 'span-rollup')");
	});
});

test.describe('an empty rollup is a named empty state, never a blank panel', () => {
	test('a rollup truncated to its header folds to an empty breakdown that names the record start', () => {
		// The real state the panel is in every day until a traced run commits: the
		// file exists with its header and no data rows. Read it back the way the
		// reader does and the breakdown is empty - and still carries the day the
		// record begins, which is the whole of what the empty panel prints.
		const header = readFileSync(join(ROLLUP, '2026-09.csv'), 'utf8').split('\n')[0];
		const dir = mkdtempSync(join(tmpdir(), 'span-rollup-header-'));
		writeFileSync(join(dir, '2026-09.csv'), header + '\n');

		const runs = foldRollup(readShards(dir));
		expect(runs.length, 'a header-only rollup folded to a run').toBe(0);

		const view = spanBreakdown(runs[0] ?? null);
		expect(view.empty).toBe(true);
		expect(view.shards).toEqual([]);
		expect(view.recordStarts).toBe(SPAN_RECORD_STARTS);
	});
});
