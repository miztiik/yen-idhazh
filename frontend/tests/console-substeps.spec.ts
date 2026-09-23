/** The four sub-steps, printed as figures, against the committed rollup.
 *
 * The rollup commits one figure a reader could not get anywhere else -
 * `unattributed_ms`, the slice of a shard's wall clock that fell outside every
 * item - and four sub-steps that nest inside the steps the timeline already
 * draws. A panel drew all of it as a split per shard until 2026-09-20; the split
 * was under a pixel wide, so it is a printed readout on the Pipeline route now.
 * The oracle here re-derives each figure straight from the committed rollup
 * cells, with none of the reader's own code in the loop, and holds it against
 * the number the page printed.
 *
 * **The pixel rule is the second half of this file.** A split whose narrowest
 * band draws under one pixel at `console.chart_width` is not drawn at all
 * (`docs/concepts/console-design.md`), and the fixture below reaches that state
 * the way the committed ledger does: a sub-step of a few milliseconds beside an
 * item clock of a few hours.
 *
 * The empty state is reached the way the real site reaches it every day until a
 * traced run commits: a rollup with nothing in it but its header. It has to name
 * the day the record begins, or a reader meets a blank readout with no way to
 * tell "not begun yet" from "something broke".
 *
 * The canary build carries the fixture rollup this reads (`build-canary.mjs`),
 * the same split every console spec is built on.
 */

import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { dayShardFiles, readDayShards, type CsvTable } from '../src/lib/server/payload';
import { foldRollup, subStepReadout, SPAN_RECORD_STARTS } from '../src/lib/server/span-rollup';

/** The canary state tree the browser suite is built from. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');
const ROLLUP = join(CANARY, 'span-rollup');

/** The canary rollup, read the way the page reads it.
 *
 * The store is `state/span-rollup/<YYYY>/<MM>/<DD>/<writer>.csv`, so a reader
 * names the store and lets the walk find the files. Naming a file inside it
 * pins a date and a grain, and both have already moved once.
 *
 * Called inside each test and never at module scope: a fixture opened while the
 * module loads fails before any test owns the failure.
 */
function rollup(): CsvTable {
	const table = readDayShards(ROLLUP);
	expect(table.rows.length, 'the canary rollup carries no row - the fixture is missing').toBeGreaterThan(
		0
	);
	return table;
}

/** The track the pixel rule is measured against, which is `console.chart_width`.
 * The same 760 `chart.width_px` carries, so a console page has one answer to how
 * wide a chart starts. */
const TRACK_PX = 760;

/** What the committed rollup itself says the newest run holds, read as raw cells
 * with none of the reader's fold in between.
 *
 * This is the independent side of the oracle: the printed figures are checked
 * against this, not against another call into the code that printed them.
 */
function committed(): {
	runId: string;
	steps: Map<string, number>;
	itemMs: number;
	residualMs: number | null;
	shards: number;
} {
	const rows = rollup().rows;
	// The newest run, by the same rule the reader sorts by: latest date, then the
	// higher run ordinal.
	const keyed = rows.map((row) => ({
		row,
		key: `${row.date ?? ''}-${String(Number(row.run_id?.split('-').at(-1))).padStart(20, '0')}`
	}));
	const runId = keyed.sort((left, right) => left.key.localeCompare(right.key)).at(-1)?.row
		.run_id as string;
	const own = rows.filter((row) => row.run_id === runId);

	const steps = new Map<string, number>();
	let itemMs = 0;
	let residualMs: number | null = null;
	const shards = new Set<number>();
	for (const row of own) {
		const name = row.span_name ?? '';
		const total = Number(row.total_ms);
		if (name === 'item') {
			shards.add(Number(row.shard));
			itemMs += total;
			const cell = row.unattributed_ms ?? '';
			if (cell !== '') residualMs = (residualMs ?? 0) + Number(cell);
			continue;
		}
		steps.set(name, (steps.get(name) ?? 0) + total);
	}
	return { runId, steps, itemMs, residualMs, shards: shards.size };
}

/** Every sub-step figure the page printed, with the numbers it carries. */
async function printedFigures(page: Page): Promise<{ name: string; ms: number; px: number }[]> {
	return page.locator('[data-substep]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			name: node.getAttribute('data-substep') ?? '',
			ms: Number(node.getAttribute('data-substep-ms')),
			px: Number(node.getAttribute('data-substep-px'))
		}))
	);
}

test.describe('the sub-step readout prints what the rollup committed', () => {
	test('THE ORACLE: every printed figure is the rollup cell, summed over the run', async ({
		page
	}) => {
		const cells = committed();
		expect(cells.steps.size, 'the canary rollup carries no sub-step row').toBeGreaterThan(0);

		await page.goto('/console/');
		const readout = page.locator('[data-substeps]');
		await expect(readout).toHaveCount(1);
		// The canary carries a rollup, so an empty readout here is a broken read
		// rather than a state to tolerate - an assertion that returned early on it
		// would pass having checked nothing.
		await expect(readout).not.toHaveAttribute('data-substeps', 'empty');
		await expect(readout).toHaveAttribute('data-substeps', cells.runId);

		const figures = await printedFigures(page);
		expect(figures.length, 'the readout printed no sub-step').toBe(cells.steps.size);
		for (const [name, ms] of cells.steps) {
			const figure = figures.find((one) => one.name === name);
			expect(figure, `${name} was not printed`).toBeTruthy();
			expect(figure!.ms, `${name} printed the wrong milliseconds`).toBe(ms);
		}

		// The item time and the overhead are the two disjoint halves of the shards'
		// wall clock, and the readout carries all three so the sum can be checked
		// off the page rather than taken on trust.
		expect(Number(await readout.getAttribute('data-substep-item-ms'))).toBe(cells.itemMs);
		const residual = (await readout.getAttribute('data-substep-residual-ms')) ?? '';
		expect(residual === '' ? null : Number(residual)).toBe(cells.residualMs);
		expect(Number(await readout.getAttribute('data-substep-wall-ms'))).toBe(
			cells.itemMs + (cells.residualMs ?? 0)
		);
		expect(Number(await readout.getAttribute('data-substep-named-ms'))).toBe(
			[...cells.steps.values()].reduce((sum, ms) => sum + ms, 0)
		);
	});

	test('a step with no committed row gets no figure and no key', async ({ page }) => {
		// `robots` stood in a legend across every committed shard row that never
		// carried it. A key for an absent series is a claim the data does not
		// support, so the readout is built from the rows and never from a list.
		const cells = committed();
		await page.goto('/console/');
		const figures = await printedFigures(page);
		for (const name of ['robots', 'tag', 'render_prompt', 'parse_reply']) {
			expect(
				figures.some((one) => one.name === name),
				`${name} is printed without a committed row, or committed without a figure`
			).toBe(cells.steps.has(name));
		}
	});

	test('the readout names the record start when it is empty, and the run when it is not', async ({
		page
	}) => {
		await page.goto('/console/');
		const readout = page.locator('[data-substeps]');
		const runId = await readout.getAttribute('data-substeps');
		if (runId === 'empty') {
			await expect(readout.locator('[data-substeps-empty]')).toContainText(SPAN_RECORD_STARTS);
		} else {
			await expect(readout).toContainText(runId as string);
		}
	});
});

test.describe('a band under one pixel is a printed figure, not a segment', () => {
	test('THE ORACLE: a sub-1px split prints its figure and draws no band', () => {
		// The state the committed ledger is in on every row: a sub-step of a few
		// milliseconds beside an item clock of a few hours. Built rather than
		// collected, so the case is here whatever the archive later holds.
		const readout = subStepReadout(
			{
				runId: '2026-09-18-1',
				date: '2026-09-18',
				shards: [
					{
						shard: 0,
						itemCount: 38,
						itemMs: 9_381_313,
						residualMs: 501,
						wallMs: 9_381_814,
						stages: [
							{ name: 'tag', count: 20, totalMs: 21 },
							{ name: 'render_prompt', count: 36, totalMs: 301 },
							{ name: 'parse_reply', count: 18, totalMs: 36 }
						],
						namedMs: 358,
						otherItemMs: 9_380_955
					}
				]
			},
			TRACK_PX
		);

		expect(readout.empty).toBe(false);
		// Every figure is under a pixel, so the split is printed. The narrowest is
		// the one the rule is measured on.
		expect(readout.smallestPx).toBeLessThan(1);
		expect(readout.printed).toBe(true);
		for (const step of readout.steps) expect(step.px).toBeLessThan(1);
		// Printed means the figure survives: three steps, three millisecond
		// readings, none of them lost with the drawing they cannot have.
		expect(readout.steps.map((step) => step.ms)).toEqual([21, 301, 36]);
		expect(readout.namedMs).toBe(358);
		expect(readout.itemMs).toBe(9_381_313);
		expect(readout.residualMs).toBe(501);
		expect(readout.wallMs).toBe(9_381_814);
	});

	test('a split wide enough to paint is not marked printed', () => {
		// The other side of the same rule, so `printed` is a measurement and not a
		// constant: one shard whose sub-steps are a fifth of its clock each.
		const readout = subStepReadout(
			{
				runId: '2026-09-18-2',
				date: '2026-09-18',
				shards: [
					{
						shard: 0,
						itemCount: 4,
						itemMs: 1000,
						residualMs: 0,
						wallMs: 1000,
						stages: [
							{ name: 'tag', count: 4, totalMs: 200 },
							{ name: 'render_prompt', count: 4, totalMs: 300 }
						],
						namedMs: 500,
						otherItemMs: 500
					}
				]
			},
			TRACK_PX
		);
		expect(readout.printed).toBe(false);
		expect(readout.smallestPx).toBeGreaterThan(1);
	});

	test('no sub-step is drawn as a band on the page, at either width', async ({ page }) => {
		// The other half of the rule, asserted where the marks actually are. A step
		// printed AND drawn is the same seconds counted twice, and a step under a
		// pixel drawn at all is a legend entry with no mark. The canary's split is
		// the wide case, so this holds on the side of the rule a fixture cannot
		// reach through the page - and it holds by construction rather than by
		// width, which is what the readout promises.
		await page.goto('/console/');
		const printed = await page
			.locator('[data-substep]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-substep') ?? ''));
		expect(printed.length, 'the readout printed no sub-step').toBeGreaterThan(0);
		for (const name of printed) {
			await expect(
				page.locator(`[data-timeline-seg="${name}"]`),
				`${name} is drawn as a band as well as printed`
			).toHaveCount(0);
		}
	});
});

test.describe('the reader folds the committed rollup', () => {
	test('the canary rollup folds to one run whose figures reconcile', () => {
		const runs = foldRollup(rollup());
		expect(runs.length, 'the canary rollup folded to no run').toBeGreaterThan(0);

		const view = subStepReadout(runs[0], TRACK_PX);
		expect(view.empty).toBe(false);
		expect(view.shardCount).toBeGreaterThan(1);
		expect(view.recordStarts).toBe(SPAN_RECORD_STARTS);

		// item + residual = wall, the fold's invariant, checked on the read side;
		// and the four nest inside the item time rather than beside it, so they can
		// never outrun it.
		expect(view.itemMs + (view.residualMs ?? 0)).toBe(view.wallMs);
		expect(view.namedMs).toBeLessThanOrEqual(view.itemMs);
		expect(view.namedMs).toBe(view.steps.reduce((sum, step) => sum + step.ms, 0));
		// Every step says where it runs, because none of the four is a step of its
		// own and a figure read as a stage is a figure added twice.
		for (const step of view.steps) expect(step.inside.length).toBeGreaterThan(0);
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

test.describe('an empty rollup is a named empty state, never a blank readout', () => {
	test('a rollup truncated to its header folds to an empty readout that names the record start', () => {
		// The real state the readout is in every day until a traced run commits: one
		// writer's file carries its header and no data rows. Read it back the way the
		// reader does and the readout is empty - and still carries the day the
		// record begins, which is the whole of what the empty state prints.
		const shards = dayShardFiles(ROLLUP);
		expect(shards.length, 'the canary rollup carries no shard - the fixture is missing').toBeGreaterThan(
			0
		);
		const header = readFileSync(shards[0].path, 'utf8').split('\n')[0];
		const dir = mkdtempSync(join(tmpdir(), 'span-rollup-header-'));
		const day = join(dir, '2026', '09', '06');
		mkdirSync(day, { recursive: true });
		writeFileSync(join(day, '2026-09-06-1-1-assemble-00.csv'), header + '\n');

		const runs = foldRollup(readDayShards(dir));
		expect(runs.length, 'a header-only rollup folded to a run').toBe(0);

		const view = subStepReadout(runs[0] ?? null, TRACK_PX);
		expect(view.empty).toBe(true);
		expect(view.steps).toEqual([]);
		expect(view.recordStarts).toBe(SPAN_RECORD_STARTS);
	});
});
