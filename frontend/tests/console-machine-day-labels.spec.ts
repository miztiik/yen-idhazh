/** Hardware charts name one day and keep their existing keyboard and measured layout. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import { windowOfDays } from '../src/lib/charts/viewport';

import type { DiskReadDay, DiskReads } from '../src/lib/console/machine/disk-reads';
import { memoryHeld } from '../src/lib/console/machine/memory-held';

import { windowed } from './support/console-window/controls';
import { windowDates, labelOf, stripOf, said } from './support/console-window/readout';
import { DRAWN_THROUGH as JUDGED_THROUGH } from './support/console-window/readout';

import { serverPanels } from './support/console-window/server-panels';
import { clientCode, drawClient } from './support/console-window/client-render';

function diskDay(date: string): DiskReadDay {
	return {
		date,
		reads: 0,
		counted: 10,
		excluded: 0,
		copiesHigh: 4e9,
		copiesLow: 3.5e9,
		copiesFell: 0.125,
		state: 'quiet'
	};
}

/** The disk-reads panel's span, every day quiet. */
function diskReads(days: DiskReadDay[]): DiskReads {
	return {
		days,
		recorded: days.length,
		fired: 0,
		reads: 0,
		worst: null,
		pinning: { held: 0, loose: 0, silent: 0 }
	};
}

const GIB = 1024 ** 3;

/** One row of the item ledger carrying the machine's own reading, split by
 * process where `split` says so, or carrying none at all. */
function healthRow(date: string, reading: 'split' | 'whole' | 'none'): Record<string, string> {
	const row: Record<string, string> = { date, item_id: `${date}-a` };
	if (reading === 'none') return row;
	row.os_mem_total_bytes = String(16 * GIB);
	row.os_mem_available_bytes = String(6 * GIB);
	if (reading === 'split') {
		row.llama_rss_anon_bytes = String(4 * GIB);
		row.python_rss_anon_bytes = String(GIB);
	}
	return row;
}

/** One run's tokens, priced at the rate below. */
function runWork(date: string, input: number, output: number) {
	return { runId: `${date}-1`, date, input, output, prefillMs: null, decodeMs: null, items: 40 };
}

/** What the cost panel is handed around its runs, as the Hardware route hands it. */
function costProps(preset: number, runs: ReturnType<typeof runWork>[]): Record<string, unknown> {
	return {
		runs,
		totals: {
			input: runs.reduce((sum, run) => sum + run.input, 0),
			output: runs.reduce((sum, run) => sum + run.output, 0),
			items: runs.reduce((sum, run) => sum + run.items, 0)
		},
		configured: { currency: 'USD', inputPerMillion: 0.5, outputPerMillion: 1.5 },
		svg: null,
		grid: { left: 48, right: 12 },
		chart: CHART,
		windowDays: preset,
		days: preset
	};
}
function latencyRun(date: string, run: number) {
	return { runId: `${date}-${run}`, date, items: 120, ms: [1000, 1500, 2000, 2500, 4000] };
}

/** The chart knobs a Hardware panel reads, drawn at one size. */
const CHART = { width_px: 760, height_px: 220, tick_density: 6, readout_max_share: 1 };
test.describe("at one day no sentence needs a second day, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "DiskReadsPanel-TailTrendPanel-MemoryHeldPanel-CounterfactualCostPanel", String(testInfo.workerIndex)), [['src/lib/console/machine/DiskReadsPanel.svelte', 'DiskReadsPanel'], ['src/lib/console/machine/TailTrendPanel.svelte', 'TailTrendPanel'], ['src/lib/console/machine/MemoryHeldPanel.svelte', 'MemoryHeldPanel'], ['src/lib/console/machine/CounterfactualCostPanel.svelte', 'CounterfactualCostPanel']]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

test('THE ORACLE: the disk-reads panel names one date and this one day, and no keys, at one day', async ({
	page
}) => {
	await draw(page, 'DiskReadsPanel', {
		reads: diskReads([diskDay(JUDGED_THROUGH)]),
		days: 1,
		windowDays: 1,
		readoutMaxShare: 1
	});
	expect(await said(page, '[data-disk-copies-track] + p')).toBe(
		'How far the memory holding disk copies fell, 2030-06-15'
	);
	expect(await labelOf(page, '[data-windowed="machine-disk-reads"] [role="group"]')).toBe(
		'Waits for the disk and disk copies, for this one day.'
	);
	expect(await labelOf(page, '[data-disk-read-track]')).toBe(
		'Waits for the disk, one tile for this one day'
	);
	expect(await labelOf(page, '[data-disk-copies-track]')).toBe(
		"How far the machine's disk copies fell, the same day"
	);
	expect(await stripOf(page, 'disk-reads')).toEqual({ heading: '15 Jun 2030', hint: null });
});

test('the disk-reads panel ranges over seven days and names its keys', async ({ page }) => {
	await draw(page, 'DiskReadsPanel', {
		reads: diskReads(windowDates(7).map(diskDay)),
		days: 7,
		windowDays: 7,
		readoutMaxShare: 1
	});
	expect(await said(page, '[data-disk-copies-track] + p')).toBe(
		'How far the memory holding disk copies fell, 2030-06-09 to 2030-06-15'
	);
	expect(await labelOf(page, '[data-windowed="machine-disk-reads"] [role="group"]')).toBe(
		'Waits for the disk and disk copies, one day a column. Left and Right read a day, Escape returns to rest.'
	);
	expect(await labelOf(page, '[data-disk-read-track]')).toBe('Waits for the disk, one tile a day');
	expect(await labelOf(page, '[data-disk-copies-track]')).toBe(
		"How far the machine's disk copies fell, the same days"
	);
	expect(await stripOf(page, 'disk-reads')).toEqual({
		heading: '15 Jun 2030, the newest day',
		hint: 'Point at a day to read both tracks. Left and Right step through the days, Escape returns to the worst.'
	});
});

/** The latency panel's props around its runs, at one window. */
function latencyProps(preset: number, rows: ReturnType<typeof latencyRun>[]): Record<string, unknown> {
	const viewport = windowOfDays(JUDGED_THROUGH, preset, 'right');
	return {
		rows,
		start: viewport.start,
		end: viewport.end,
		modelChanges: [],
		moved: [],
		chart: CHART,
		windowDays: preset,
		days: preset,
		floor: 50,
		tooFew: []
	};
}

const LATENCY =
	'Per-item model time at the 50th, 75th, 90th, 95th and 99th percentile, one plot each and one mark per run';

test('THE ORACLE: the latency plots name their one date once, with no count', async ({ page }) => {
	await draw(
		page,
		'TailTrendPanel',
		latencyProps(1, [latencyRun(JUDGED_THROUGH, 1), latencyRun(JUDGED_THROUGH, 2)])
	);
	expect(await labelOf(page, '[data-latency-runs]')).toBe(
		`${LATENCY}, 15 Jun 2030. All five plots share one scale.`
	);
});

test('the latency plots range over their dates and count seven days', async ({ page }) => {
	await draw(page, 'TailTrendPanel', latencyProps(7, [latencyRun('2030-06-10', 1), latencyRun(JUDGED_THROUGH, 1)]));
	expect(await labelOf(page, '[data-latency-runs]')).toBe(
		`${LATENCY}, 10 Jun 2030 to 15 Jun 2030, over 7 days. All five plots share one scale.`
	);
});

/** The memory panel's props around the rows a case builds, at one window. */
function memoryProps(preset: number, rows: Record<string, string>[]): Record<string, unknown> {
	const viewport = windowOfDays(JUDGED_THROUGH, preset, 'right');
	return { record: memoryHeld(rows), start: viewport.start, end: viewport.end, days: preset };
}

test('THE ORACLE: the memory panel speaks of this one day, counts 1 day, and says no reading began before it', async ({
	page
}) => {
	await draw(page, 'MemoryHeldPanel', memoryProps(1, [healthRow(JUDGED_THROUGH, 'whole')]));
	expect(await said(page, '[data-memory-shapes]')).toBe(
		'This one day draws one held part rather than splitting it, because no run that wrote the day recorded what each process holds on its own.'
	);
	// One day of ledger has no day before the reading began.
	await expect(page.locator('[data-memory-begins]')).toHaveCount(0);

	await draw(page, 'MemoryHeldPanel', memoryProps(1, [healthRow(JUDGED_THROUGH, 'split')]));
	expect(await said(page, '[data-memory-shapes]')).toBe(
		'This one day splits the held part into what each process holds on its own.'
	);

	await draw(page, 'MemoryHeldPanel', memoryProps(1, [healthRow(JUDGED_THROUGH, 'none')]));
	expect(await said(page, '[data-machine-panel-empty="memory-held"]')).toBe(
		'No day this ledger holds recorded what the machine itself had, so there is nothing to split up. Read over 1 day.'
	);
});

test('the memory panel speaks of every day here, and counts the days it read', async ({ page }) => {
	const two = ['2030-06-10', JUDGED_THROUGH];
	await draw(page, 'MemoryHeldPanel', memoryProps(7, two.map((date) => healthRow(date, 'whole'))));
	expect(await said(page, '[data-memory-shapes]')).toBe(
		'Every day here draws one held part rather than splitting it, because no run that wrote these days recorded what each process holds on its own.'
	);
	expect(await said(page, '[data-memory-begins]')).toBe(
		"The machine's own reading begins on 2030-06-10, over 2 days of ledger; a day before it draws no bar rather than an empty one."
	);

	await draw(page, 'MemoryHeldPanel', memoryProps(7, two.map((date) => healthRow(date, 'split'))));
	expect(await said(page, '[data-memory-shapes]')).toBe(
		'Every day here splits the held part into what each process holds on its own.'
	);

	await draw(page, 'MemoryHeldPanel', memoryProps(7, windowDates(7).map((date) => healthRow(date, 'none'))));
	expect(await said(page, '[data-machine-panel-empty="memory-held"]')).toBe(
		'No day this ledger holds recorded what the machine itself had, so there is nothing to split up. Read over 7 days.'
	);
});

test('THE ORACLE: the cost panel measures its one column, and its empty chart names this one day', async ({
	page
}) => {
	// Reading 0.50 and writing 0.30: the smaller half is 37.5 percent of the column.
	await draw(page, 'CounterfactualCostPanel', costProps(1, [runWork(JUDGED_THROUGH, 1_000_000, 200_000)]));
	await expect(page.locator('[data-shape-option="daily"]')).toHaveText('This one day');
	await expect(page.locator('[data-shape-option="running"]')).toHaveText('Running total');
	expect(await said(page, '[data-cost-measured]')).toBe(
		'The smaller half measures 37.5 percent of the column, so both halves draw as bands rather than as a printed figure.'
	);
	expect(
		((await page.locator('[data-chart-pending]').innerText()) ?? '').replace(/\s+/g, ' ').trim()
	).toBe("This chart is loading. This one day's numbers are below.");
	expect(await stripOf(page, 'counterfactual-cost')).toEqual({ heading: '15 Jun 2030', hint: null });

	// Writing 1,339 tokens is 0.4 percent of the column, under a pixel.
	await draw(page, 'CounterfactualCostPanel', costProps(1, [runWork(JUDGED_THROUGH, 1_000_000, 1_339)]));
	expect(await said(page, '[data-cost-measured]')).toBe(
		'Reading and writing are one column here. The smaller half measures 0.4 percent of the column, which draws under a pixel, and a band a browser paints nothing for teaches a reader the half is zero.'
	);

	await draw(page, 'CounterfactualCostPanel', costProps(1, [runWork(JUDGED_THROUGH, 0, 0)]));
	expect(await said(page, '[data-cost-measured]')).toBe(
		'Nothing split in this one day, so the column carries no bands.'
	);
});

test('the cost panel measures against its busiest and tallest of several columns', async ({ page }) => {
	// Bands of 0.50, 0.30, 1.00 and 0.75 under a tallest column of 1.75.
	await draw(
		page,
		'CounterfactualCostPanel',
		costProps(7, [runWork('2030-06-10', 1_000_000, 200_000), runWork(JUDGED_THROUGH, 2_000_000, 500_000)])
	);
	await expect(page.locator('[data-shape-option="daily"]')).toHaveText('Day by day');
	await expect(page.locator('[data-shape-option="running"]')).toHaveText('Running total');
	expect(await said(page, '[data-cost-measured]')).toBe(
		'The smaller half of the busiest day measures 17.1 percent of the tallest column, so both halves draw as bands rather than as a printed figure.'
	);
	expect(
		((await page.locator('[data-chart-pending]').innerText()) ?? '').replace(/\s+/g, ' ').trim()
	).toBe("This chart is loading. The newest day's numbers are below.");
	expect(await stripOf(page, 'counterfactual-cost')).toEqual({
		heading: '15 Jun 2030, the newest day',
		hint: 'Point at a day to read it. Left and Right step through them, Escape returns to the newest.'
	});

	await draw(
		page,
		'CounterfactualCostPanel',
		costProps(7, [runWork('2030-06-10', 1_000_000, 1_339), runWork(JUDGED_THROUGH, 1_000_000, 1_339)])
	);
	expect(await said(page, '[data-cost-measured]')).toBe(
		'Reading and writing are one column here. The smaller half measures 0.4 percent of the tallest day, which draws under a pixel, and a band a browser paints nothing for teaches a reader the half is zero.'
	);

	await draw(page, 'CounterfactualCostPanel', costProps(7, [runWork('2030-06-10', 0, 0), runWork(JUDGED_THROUGH, 0, 0)]));
	expect(await said(page, '[data-cost-measured]')).toBe(
		'Nothing split in this window, so the columns carry no bands.'
	);
});
test.describe("remaining one-day words and keys on generated records", () => {

let browserCode: string;
test.beforeAll(async () => { browserCode = await clientCode([["ProcessorLost","./src/lib/console/machine/ProcessorLostPanel.svelte"]]); });
async function drawRecord(page: Page, name: string, props: Record<string, unknown>) {
  await drawClient(page, browserCode, name, props);
}

for (const state of ['quiet', 'named', 'no-day'] as const) {
	test(`THE ORACLE: one-day processor tiles say where keys go when ${state}`, async ({ page }) => {
		const tile = { key: JUDGED_THROUGH, label: '15 Jun 2030', short: '15', state: 'quiet', worstPct: 0, says: 'under 1%', from: 2, outOf: 2 };
		const days = state === 'no-day' ? [] : [tile];
		await drawRecord(page, 'ProcessorLost', {
			span: { days, from: days.length * 2, outOf: days.length * 2, named: state === 'named' ? tile : null, daysRecording: days.length },
			run: { runId: '2030-06-14-1', date: '2030-06-14', from: 4, outOf: 4,
				shards: [0, 1].map((shard) => ({ ...tile, key: String(shard), label: `Part ${shard}`, short: String(shard) })) },
			days: 1, windowDays: 1, markedAt: 1, namedAt: 5, readoutMaxShare: 1
		});
		const group = page.locator('.grains');
		const strip = page.locator('[data-readout="processor-lost"] [data-readout-subject]');
		await expect(group).toHaveAttribute('aria-label', state === 'no-day'
			? 'The share of the processor lost, one tile per part of the newest run. There is no tile for this one day. Arrow keys move between tiles. Escape returns to the first tile.'
			: "The share of the processor lost, one tile for this one day and one per part of the newest run. Arrow keys move between tiles. Escape returns to the day's tile.");
		await expect(strip).toHaveText(state === 'no-day' ? 'Part 0, the first tile' : '15 Jun 2030, this one day');
		await expect(page.locator('[data-readout-hint="processor-lost"]')).toHaveText(state === 'no-day'
			? 'Point at a tile to read it. Arrow keys move between tiles. Escape returns to the first tile.'
			: "Point at a tile to read it. Arrow keys move between tiles. Escape returns to the day's tile.");
		await group.focus();
		await group.press('End');
		await expect(strip).toHaveText('Part 1');
		await group.press('ArrowLeft');
		await expect(strip).toHaveText('Part 0');
		await group.press('Escape');
		await expect(strip).toHaveText(state === 'no-day' ? 'Part 0, the first tile' : '15 Jun 2030, this one day');
	});
}

test('THE ORACLE: seven-day processor words remain unchanged', async ({ page }) => {
	const tile = { key: JUDGED_THROUGH, label: '15 Jun 2030', short: '15', state: 'quiet', worstPct: 0, says: 'under 1%', from: 2, outOf: 2 };
	await drawRecord(page, 'ProcessorLost', {
		span: { days: [tile], from: 2, outOf: 2, named: null, daysRecording: 1 },
		run: { runId: null, date: null, from: 0, outOf: 0, shards: [] },
		days: 7, windowDays: 7, markedAt: 1, namedAt: 5, readoutMaxShare: 1
	});
	await expect(page.locator('.grains')).toHaveAttribute('aria-label', 'The share of the processor lost, one tile a day and one a shard of the newest run. Arrow keys read a tile, Escape returns to rest.');
	await expect(page.locator('[data-readout="processor-lost"] [data-readout-subject]')).toHaveText('15 Jun 2030, the newest day');
	await expect(page.locator('[data-readout-hint="processor-lost"]')).toHaveText('Point at a tile to read it. Left and Right step along a row, Up and Down move between days and shards, Escape returns to rest.');
});
});
});
