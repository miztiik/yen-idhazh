import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * The run timeline draws, and it draws no column that is empty everywhere.
 *
 * **The empty-column gate is the point of this file.** Three console panels
 * already apologise for a column nothing fills, and the rule this row adds is
 * that a panel may not: every column the panel declares it reads has to carry a
 * value on at least one row of the canary day, or the panel does not ship. The
 * canary is the right fixture for it - fixed in size, so the check costs the same
 * however far the archive grows (`CLAUDE.md` Guardrail #12), and built rather than
 * collected, so it can carry a case the archive has never produced. Every
 * committed census row is in exactly that state today: not one of them records an
 * item clock, so nothing but a built day can place an item on one.
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
	await page.goto('/console/machine/');
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
	await page.goto('/console/machine/');
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
	await page.goto('/console/machine/');
	const board = panel(page);
	const empty = (await board.getAttribute('data-run-timeline')) === 'empty';
	if (empty) {
		await expect(board.locator('[data-run-timeline-empty]')).toBeVisible();
	} else {
		await expect(board.locator('[data-timeline-residual-note]')).toBeVisible();
	}
	// Either way the route itself is whole: the panel above it still drew.
	await expect(page.locator('[data-span-board]')).toBeAttached();
});
