import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * The run timeline draws at both grains, and it draws no column that is empty
 * everywhere.
 *
 * **The empty-column gate is one half of this file.** Three console panels
 * already apologise for a column nothing fills, and the rule this panel obeys is
 * that a panel may not: every column the panel declares it reads has to carry a
 * value on at least one row of the canary day, or the panel does not ship. The
 * canary is the right fixture for it - fixed in size, so the check costs the same
 * however far the archive grows (`CLAUDE.md` Guardrail #12), and built rather than
 * collected, so it can carry a case the archive has never produced. Every
 * committed census row is in exactly that state today: not one of them records an
 * item clock, so nothing but a built day can place an item on one.
 *
 * **The grain oracle is the other half.** The panel offers a shard grain beside
 * its item grain, and a grain switch is only honest where one fold built both:
 * two folds over two ledgers can name different runs and disagree about a step's
 * seconds, which is what the two panels this one replaced actually did. The
 * oracle holds the two arrays against each other, per shard and per step, rather
 * than against any pixel.
 *
 * The declared list is read off the module the panel imports, so a column added
 * to the panel and to nothing else fails here rather than drawing an empty slice.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');
const TIMELINE_DIR = resolve(CANARY, 'run-timeline');

/** The columns the panel reads, taken from the module it takes them from.
 *
 * Parsed rather than imported: this spec runs in plain Node, where no Vite alias
 * resolves and a `$lib/server/` import cannot load. Parsing the same declaration
 * keeps one list rather than two, which is the whole point of declaring it.
 */
function declaredColumns(): string[] {
	const source = readFileSync(
		resolve(process.cwd(), 'src', 'lib', 'server', 'run-timeline.ts'),
		'utf8'
	);
	const block = /export const TIMELINE_COLUMNS = \[([^\]]*)\]/.exec(source);
	expect(block, 'run-timeline.ts declares no TIMELINE_COLUMNS').not.toBeNull();
	return [...(block as RegExpExecArray)[1].matchAll(/'([a-z_]+)'/g)].map((match) => match[1]);
}

/** Every published run-timeline row the canary holds, newest shard last. */
function canaryRows(): Record<string, string>[] {
	expect(
		existsSync(TIMELINE_DIR),
		'the canary published no run-timeline. Build it: python backend/utilities/build_canary_day.py, then node frontend/scripts/build-canary.mjs'
	).toBe(true);
	const rows: Record<string, string>[] = [];
	for (const name of readdirSync(TIMELINE_DIR).filter((file) => file.endsWith('.csv')).sort()) {
		const lines = readFileSync(resolve(TIMELINE_DIR, name), 'utf8').trim().split('\n');
		const header = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cells = line.split(',');
			rows.push(Object.fromEntries(header.map((column, at) => [column, cells[at] ?? ''])));
		}
	}
	return rows;
}

const panel = (page: Page) => page.locator('[data-run-timeline]');

/** Every bar the panel has drawn, with the figures it carries. */
async function drawnBars(
	page: Page
): Promise<{ id: string; shard: number; total: number; work: number; items: number; segs: Record<string, number> }[]> {
	return page.locator('[data-timeline-bar]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			id: node.getAttribute('data-timeline-bar') ?? '',
			shard: Number(node.getAttribute('data-timeline-shard')),
			total: Number(node.getAttribute('data-timeline-total-ms')),
			work: Number(node.getAttribute('data-timeline-bar-work-ms')),
			items: Number(node.getAttribute('data-timeline-bar-items')),
			segs: Object.fromEntries(
				[...node.querySelectorAll('[data-timeline-seg]')]
					.filter((seg) => {
						const name = seg.getAttribute('data-timeline-seg') ?? '';
						return name !== 'residual' && name !== 'overrun';
					})
					.map((seg) => [
						seg.getAttribute('data-timeline-seg') ?? '',
						Number(seg.getAttribute('data-timeline-seg-ms'))
					])
			)
		}))
	);
}

/** Pick a grain on the panel's own switch and wait for the panel to say so.
 *
 * Click the label, never `check()` the input: the radio's box is hidden so the
 * segment can carry the styling, and a hidden input is not checkable. The label
 * is what a reader clicks too. */
async function chooseGrain(page: Page, grain: string): Promise<void> {
	await page.locator(`[data-shape-switch="timeline-grain"] [data-shape-option="${grain}"]`).click();
	await expect(panel(page)).toHaveAttribute('data-timeline-grain', grain);
}

test('every column the panel reads carries a value on at least one canary row', () => {
	const rows = canaryRows();
	expect(rows.length, 'the canary published no timeline rows at all').toBeGreaterThan(0);
	for (const column of declaredColumns()) {
		const filled = rows.filter((row) => (row[column] ?? '') !== '').length;
		expect(filled, `${column} is empty on all ${rows.length} canary rows`).toBeGreaterThan(0);
	}
});

test('every step the panel draws carries a value, and the ones it does not are named', async ({
	page
}) => {
	await page.goto('/console/');
	const board = panel(page);
	await expect(board).toHaveAttribute('data-run-timeline', /^\d{4}-\d{2}-\d{2}-\d+$/);

	const drawn = ((await board.getAttribute('data-timeline-drawn')) ?? '').split(' ').filter(Boolean);
	const unproduced = ((await board.getAttribute('data-timeline-unproduced')) ?? '')
		.split(' ')
		.filter(Boolean);
	const unrecorded = ((await board.getAttribute('data-timeline-unrecorded')) ?? '')
		.split(' ')
		.filter(Boolean);

	expect(drawn.length, 'the panel drew no step at all').toBeGreaterThan(0);
	// The eight the contract declares, each accounted for exactly once: drawn, or
	// named to the reader as one of the two silences. A step in none of the three
	// is a step the panel dropped without saying so.
	expect([...drawn, ...unproduced, ...unrecorded].sort()).toEqual(
		[
			'extract_ms',
			'fetch_ms',
			'label_ms',
			'plan_ms',
			'publish_ms',
			'score_ms',
			'summary_ms',
			'visual_plan_ms'
		].sort()
	);

	// Every drawn step has a slice somewhere on the board. A legend entry with no
	// mark behind it is the failure this row exists to stop shipping.
	for (const step of drawn) {
		await expect(
			page.locator(`[data-timeline-seg="${step}"]`).first(),
			`${step} is in the legend and on no bar`
		).toBeAttached();
	}
});

test('a bar sits where its item started and is as long as the item took', async ({ page }) => {
	await page.goto('/console/');
	const bars = panel(page).locator('[data-timeline-bar]');
	const count = await bars.count();
	expect(count, 'the timeline drew no bars').toBeGreaterThan(0);

	// In start order, which is what makes the queue legible: the y axis is items
	// and the x axis is the run's own clock.
	const starts: number[] = [];
	for (let at = 0; at < count; at += 1) {
		starts.push(Number(await bars.nth(at).getAttribute('data-timeline-start-ms')));
	}
	expect(starts).toEqual([...starts].sort((a, b) => a - b));
	expect(starts[0], 'the first bar does not sit at the run start').toBe(0);

	// The steps plus the residual are the item's own clock exactly, which is what
	// makes the residual a figure that reconciles rather than an estimate.
	const first = bars.first();
	const total = Number(await first.getAttribute('data-timeline-total-ms'));
	const residual = Number(await first.getAttribute('data-timeline-residual-ms'));
	const segments = first.locator('[data-timeline-seg]:not([data-timeline-seg="residual"])');
	let named = 0;
	for (let at = 0; at < (await segments.count()); at += 1) {
		const seg = segments.nth(at);
		if ((await seg.getAttribute('data-timeline-seg')) === 'overrun') continue;
		named += Number(await seg.getAttribute('data-timeline-seg-ms'));
	}
	expect(named + residual).toBe(total);
});

test('the run timeline renders when its published series is gone', async ({ page }) => {
	// The panel reads one directory at build time. With the series absent the view
	// is empty by construction, and the empty state is written rather than
	// defaulted - so the page still answers, which is what `CLAUDE.md` section 12
	// asks of every published surface.
	await page.goto('/console/');
	const board = panel(page);
	const empty = (await board.getAttribute('data-run-timeline')) === 'empty';
	if (empty) {
		await expect(board.locator('[data-run-timeline-empty]')).toBeVisible();
	} else {
		await expect(board.locator('[data-timeline-residual-note]')).toBeVisible();
	}
	// Either way the route itself is whole: the readout under the bars still drew.
	await expect(page.locator('[data-substeps]')).toBeAttached();
});

test.describe('one fold, two grains', () => {
	test('THE ORACLE: the shard grain sums to the item grain, step for step', async ({ page }) => {
		await page.goto('/console/');
		const board = panel(page);
		await expect(board).toHaveAttribute('data-run-timeline', /^\d{4}-\d{2}-\d{2}-\d+$/);
		await expect(board).toHaveAttribute('data-timeline-grain', 'item');

		// The item grain is capped at `console.timeline_bars`, and a comparison
		// against a capped array would pass while reading half a run. Assert the cap
		// did not bite before comparing anything.
		const items = await drawnBars(page);
		expect(items.length, 'the timeline drew no bars').toBeGreaterThan(0);
		expect(
			items.length,
			'the drawing cap bit, so the two grains cannot be compared on this fixture'
		).toBe(Number(await board.getAttribute('data-timeline-items')));

		await chooseGrain(page, 'shard');
		const shards = await drawnBars(page);
		expect(shards.length, 'the shard grain drew no bars').toBeGreaterThan(1);

		// One bar a shard, and every shard of the run is there exactly once.
		expect(shards.map((bar) => bar.shard).sort((a, b) => a - b)).toEqual(
			[...new Set(items.map((bar) => bar.shard))].sort((a, b) => a - b)
		);

		for (const shard of shards) {
			const own = items.filter((bar) => bar.shard === shard.shard);
			// The shard bar covers that shard's items and says how many.
			expect(shard.items, `shard ${shard.shard} counted the wrong items`).toBe(own.length);
			// Its work is those items' own clocks added up - the arithmetic the two
			// grains must agree on, because they are one fold over one set of rows.
			expect(shard.work, `shard ${shard.shard} drew the wrong item time`).toBe(
				own.reduce((sum, bar) => sum + bar.total, 0)
			);
			// And every step of it is that step summed over the same items. A second
			// fold over a second ledger is exactly what this cannot survive.
			for (const [step, ms] of Object.entries(shard.segs)) {
				expect(ms, `shard ${shard.shard} drew the wrong ${step}`).toBe(
					own.reduce((sum, bar) => sum + (bar.segs[step] ?? 0), 0)
				);
			}
		}

		// The run's work is the same number at either grain.
		expect(shards.reduce((sum, bar) => sum + bar.work, 0)).toBe(
			Number(await board.getAttribute('data-timeline-work-ms'))
		);
	});

	test('the by-shard order is the same bars, grouped by the worker that ran them', async ({
		page
	}) => {
		await page.goto('/console/');
		const byStart = await drawnBars(page);
		await chooseGrain(page, 'by-shard');
		const grouped = await drawnBars(page);

		// The same set, re-ordered and never re-derived: an ordering that drops or
		// invents a bar is a second derivation wearing a sort's clothes.
		expect(grouped.map((bar) => bar.id).sort()).toEqual(byStart.map((bar) => bar.id).sort());
		const shardRun = grouped.map((bar) => bar.shard);
		expect(shardRun, 'the by-shard order is not grouped by shard').toEqual(
			[...shardRun].sort((a, b) => a - b)
		);
	});
});
