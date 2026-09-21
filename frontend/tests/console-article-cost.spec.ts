/** What one article costs the machine: the arithmetic, then the panel.
 *
 * Every figure below is recomputed here from the fixture's own item rows and
 * machine records, never read back off the module's output - an assertion
 * against a module's own answer only proves the module agrees with itself.
 *
 * Two fixtures, because the canary cannot state every case. It records no
 * resident memory at all, so the step between one article and the next is
 * driven from bounded rows written in this file; and it carries exactly one
 * machine record with no processor count, which is the case the panel has to
 * print a dash for rather than assume the runner we usually get.
 *
 * Pure functions and the committed canary only, except where a test names a
 * page. No `$app` import and no SvelteKit alias: a spec that reaches one fails
 * the whole file at load instead of failing one test.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { seconds } from '../src/lib/charts/machine';
import { grouped } from '../src/lib/charts/series';
import {
	articleCost,
	costTrack,
	runnerHourSeconds,
	type MachineProcessors
} from '../src/lib/console/machine/article-cost';
import { readDayShards } from '../src/lib/server/payload';

/** The canary tree the browser suite is built from. The page under the browser
 * was built from this tree, so reading the committed one would compare a
 * drawing of one ledger against the arithmetic of another. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

const CONSOLE = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console: { window_presets: number[] } }
).console;

const WIDEST = Math.max(...CONSOLE.window_presets);

function canaryHealth(): Record<string, string>[] {
	return readDayShards(join(CANARY, 'item-health'), -1).rows;
}

/** The canary's machine records as the join needs them.
 *
 * Mapped here rather than through the page's own reader, so the test states
 * what a machine record is instead of borrowing the module's idea of it.
 */
function canaryMachines(): MachineProcessors[] {
	return readDayShards(join(CANARY, 'host-fingerprint'), -1).rows.map((row) => ({
		date: row.date ?? '',
		run_id: row.run_id ?? '',
		shard: Number(row.shard ?? '0'),
		threads: row.threads === undefined || row.threads === '' ? null : Number(row.threads)
	}));
}

const within = (row: Record<string, string>, start: string, end: string) =>
	(row.date ?? '') >= start && (row.date ?? '') <= end;

const middle = (values: number[]): number => {
	const sorted = [...values].sort((left, right) => left - right);
	const at = (sorted.length - 1) / 2;
	const low = Math.floor(at);
	return sorted[low] + (sorted[Math.ceil(at)] - sorted[low]) * (at - low);
};

/** Processor-seconds an article, worked out here from three readings.
 *
 * `column` is the machine record's own name for the count, so the same
 * arithmetic can be run against the logical processors and against the cores
 * and the two answers compared.
 */
function processorSecondsFrom(
	health: readonly Record<string, string>[],
	counts: ReadonlyMap<string, number>
): number[] {
	const found: number[] = [];
	for (const row of health) {
		const busy = Number(row.cpu_busy_pct ?? '');
		const total = Number(row.item_total_ms ?? '');
		if (!(row.cpu_busy_pct ?? '') || !(row.item_total_ms ?? '') || total <= 0) continue;
		const count = counts.get(`${row.date ?? ''}|${row.run_id ?? ''}|${row.shard ?? ''}`);
		if (count === undefined) continue;
		found.push((busy / 100) * count * (total / 1000));
	}
	return found;
}

/** Each machine record's count under the column named, keyed the way an item
 * row finds it. Records that left the column empty are absent, not zero. */
function countsBy(column: string): Map<string, number> {
	const found = new Map<string, number>();
	for (const row of readDayShards(join(CANARY, 'host-fingerprint'), -1).rows) {
		const value = row[column] ?? '';
		if (value === '') continue;
		found.set(`${row.date ?? ''}|${row.run_id ?? ''}|${row.shard ?? ''}`, Number(value));
	}
	return found;
}

/** One item row, with only the cells a figure needs. */
function itemRow(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const row: Record<string, string> = {};
	for (const [key, value] of Object.entries(cells)) row[key] = String(value);
	return row;
}

test.describe('the three costs, as arithmetic', () => {
	test('processor time is the busy share across the LOGICAL processors, not the cores', () => {
		// The kernel counts every logical processor on one line, so the share it
		// reports is a share of all of them. Taking it across the cores instead
		// would halve every figure on a machine that runs two threads a core -
		// which is what the canary's records describe, so the two answers here
		// are genuinely different numbers and the test can tell them apart.
		const health = canaryHealth();
		const byThreads = processorSecondsFrom(health, countsBy('threads'));
		const byCores = processorSecondsFrom(health, countsBy('cores'));
		expect(byThreads.length, 'the canary resolved no article to a machine record').toBeGreaterThan(
			0
		);

		const cost = articleCost(health, canaryMachines());
		expect(cost.processorSeconds.from).toBe(byThreads.length);
		expect(cost.processorSeconds.mid).toBeCloseTo(middle(byThreads), 6);
		expect(cost.processorSeconds.low).toBeCloseTo(Math.min(...byThreads), 6);
		expect(cost.processorSeconds.high).toBeCloseTo(Math.max(...byThreads), 6);
		expect(
			middle(byCores),
			'the canary describes a machine whose cores and logical processors are the same number, so this proves nothing'
		).not.toBeCloseTo(middle(byThreads), 6);
	});

	test('THE ORACLE: a run whose machine record names no processor count is a dash', () => {
		// The rule, on rows written here rather than found: two articles that both
		// recorded what they kept busy and how long they ran, and a record that
		// reached the machine and left the count empty. Nothing about the runner
		// we usually get may fill it in.
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, cpu_busy_pct: 80, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, cpu_busy_pct: 40, item_total_ms: 2000 })
		];
		const blind = articleCost(health, [
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: null }
		]);
		expect(blind.processorSeconds.mid, 'a processor count was assumed from nothing').toBeNull();
		expect(blind.processorSeconds.low).toBeNull();
		expect(blind.processorSeconds.high).toBeNull();
		expect(blind.processorSeconds.from).toBe(0);
		// And the two articles are still counted as offered, so the panel can say
		// how many it could not answer for rather than pretending they were never
		// there.
		expect(blind.processorSeconds.outOf).toBe(2);
		expect(blind.processors).toEqual([]);

		// The same two rows against a record that names four processors: 0.8 of
		// four for one second, and 0.4 of four for two seconds.
		const seen = articleCost(health, [{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 4 }]);
		expect(seen.processorSeconds.low).toBeCloseTo(3.2, 6);
		expect(seen.processorSeconds.high).toBeCloseTo(3.2, 6);
		expect(seen.processorSeconds.from).toBe(2);
		expect(seen.processors).toEqual([4]);
	});

	test('the canary carries that case, so the page is drawing a real absence', () => {
		// The rule above is stated on rows this file wrote. This one proves the
		// fixture the browser runs on actually holds a machine record with no
		// count, which is what makes the gap the panel prints a real number.
		const machines = canaryMachines();
		const blind = machines.filter((machine) => machine.threads === null);
		expect(blind.length, 'the canary names a count on every machine record').toBeGreaterThan(0);

		const cost = articleCost(canaryHealth(), machines);
		expect(
			cost.processorSeconds.outOf - cost.processorSeconds.from,
			'the canary resolved every article, so the unresolved arm asserts nothing'
		).toBeGreaterThan(0);
	});

	test('model time is reading the prompt and writing the reply, added up', () => {
		const health = canaryHealth();
		const expected = health
			.filter((row) => (row.prefill_ms ?? '') !== '' && (row.decode_ms ?? '') !== '')
			.map((row) => (Number(row.prefill_ms) + Number(row.decode_ms)) / 1000);
		expect(expected.length, 'no canary article recorded both halves').toBeGreaterThan(0);

		const cost = articleCost(health, canaryMachines());
		expect(cost.modelSeconds.from).toBe(expected.length);
		expect(cost.modelSeconds.outOf).toBe(expected.length);
		expect(cost.modelSeconds.mid).toBeCloseTo(middle(expected), 6);
		expect(cost.modelSeconds.low).toBeCloseTo(Math.min(...expected), 6);
		expect(cost.modelSeconds.high).toBeCloseTo(Math.max(...expected), 6);
	});

	test('added memory is a step between neighbours of ONE shard', () => {
		// Three things this has to get right, and the canary records no resident
		// memory at all, so they are stated on rows written here. A step is taken
		// between neighbours; a gap in the numbering is not a step; and a shard
		// boundary is not a step either, because a new shard starts a new model
		// server and its first reading is a restart rather than an article.
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, item_index: 0, llama_rss_bytes: 100 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, item_index: 1, llama_rss_bytes: 160 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, item_index: 2, llama_rss_bytes: 140 }),
			// A gap: item 4 follows item 2, so whatever happened at item 3 is not
			// one article's doing.
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, item_index: 4, llama_rss_bytes: 900 }),
			// A second shard, whose first reading is a fresh server.
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 1, item_index: 0, llama_rss_bytes: 500 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', shard: 1, item_index: 1, llama_rss_bytes: 510 })
		];
		const cost = articleCost(health, []);
		expect(cost.addedBytes.from, 'a gap or a shard boundary was counted as a step').toBe(3);
		expect(cost.shards).toBe(2);
		expect(cost.addedBytes.low).toBe(-20);
		expect(cost.addedBytes.mid).toBe(10);
		expect(cost.addedBytes.high).toBe(60);
	});

	test('a shard with one article has no step, and says so rather than reporting zero', () => {
		const cost = articleCost(
			[itemRow({ date: '2026-08-20', run_id: 'r1', shard: 0, item_index: 0, llama_rss_bytes: 100 })],
			[]
		);
		expect(cost.addedBytes.from).toBe(0);
		expect(cost.addedBytes.mid).toBeNull();
		expect(cost.shards).toBe(0);
	});

	test('the track holds zero, so a step that gave memory back is on the giving side', () => {
		const track = costTrack({ low: -100, mid: -50, high: 300, from: 3, outOf: 3 }, 400);
		expect(track).not.toBeNull();
		expect(track!.floor).toBe(-100);
		expect(track!.ceiling).toBe(300);
		// Zero is a quarter along a track running -100 to 300, and a middle of -50
		// sits an eighth along - to the LEFT of zero, which is the whole point.
		expect(track!.zero).toBe('25.0000%');
		expect(track!.at).toBe('12.5000%');
		expect(track!.drawn).toBe(true);
	});

	test('a track whose readings all agree draws no band, and is not a line too thin to see', () => {
		const track = costTrack({ low: 10, mid: 10, high: 10, from: 4, outOf: 4 }, 400);
		expect(track!.drawn).toBe(false);
		expect(track!.length).toBe('0.0000%');
	});

	test('a runner-hour is quoted on the smallest machine the span ran on', () => {
		// The hour a cost has to fit inside is the one the smallest machine
		// supplies; quoting the biggest would make every figure look cheaper than
		// it is on the machine that matters.
		expect(runnerHourSeconds([4])).toBe(14400);
		expect(runnerHourSeconds([8, 4])).toBe(14400);
		expect(runnerHourSeconds([])).toBeNull();
	});
});

/** Drive the shared control to a preset and wait for the page to hold it. */
async function widen(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** The span the page says it is drawing, read off the panel that prints it. */
async function shownSpan(page: Page): Promise<{ start: string; end: string }> {
	const said = (await page.locator('[data-windowed="machine-runs"]').innerText())
		.replace(/\s+/g, ' ')
		.trim();
	const dates = /(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})/.exec(said);
	expect(dates, 'the page never says which days it is drawing').not.toBeNull();
	return { start: dates![1], end: dates![2] };
}

const PANEL = '[data-windowed="machine-article-cost"]';

test.describe('the panel, on the canary', () => {
	test('THE ORACLE: every printed figure is the fixture rows recomputed', async ({ page }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const span = await shownSpan(page);
		const health = canaryHealth().filter((row) => within(row, span.start, span.end));
		const expected = processorSecondsFrom(health, countsBy('threads'));
		expect(expected.length, 'the window the page drew holds no measurable article').toBeGreaterThan(
			0
		);

		const processor = page.locator(`${PANEL} [data-article-cost="processor"]`);
		await expect(processor).toHaveAttribute('data-cost-state', 'measured');
		const read = async (name: string) =>
			Number((await processor.getAttribute(`data-cost-${name}`)) ?? 'NaN');
		expect(await read('mid')).toBeCloseTo(middle(expected), 6);
		expect(await read('low')).toBeCloseTo(Math.min(...expected), 6);
		expect(await read('high')).toBeCloseTo(Math.max(...expected), 6);
		expect(await read('from')).toBe(expected.length);

		// And the figure a reader sees is that same number, so the attribute is a
		// handle on the printed value rather than a second answer beside it.
		await expect(processor.locator('[data-article-cost-value="processor"]')).toHaveText(
			seconds(middle(expected))
		);

		const model = page.locator(`${PANEL} [data-article-cost="model"]`);
		const modelSeconds = health
			.filter((row) => (row.prefill_ms ?? '') !== '' && (row.decode_ms ?? '') !== '')
			.map((row) => (Number(row.prefill_ms) + Number(row.decode_ms)) / 1000);
		expect(modelSeconds.length, 'the window holds no article the model timed').toBeGreaterThan(0);
		expect(Number((await model.getAttribute('data-cost-mid')) ?? 'NaN')).toBeCloseTo(
			middle(modelSeconds),
			6
		);
		await expect(model.locator('[data-article-cost-value="model"]')).toHaveText(
			seconds(middle(modelSeconds))
		);
	});

	test('THE ORACLE: articles no machine record answered for are counted, not dropped', async ({
		page
	}) => {
		// The canary holds one machine record that reached the machine and named no
		// processor count. The articles under it are offered and unmeasured, and
		// the panel prints both numbers - a count that quietly excluded them would
		// be a count nobody can check.
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const span = await shownSpan(page);
		const health = canaryHealth().filter((row) => within(row, span.start, span.end));
		const offered = health.filter(
			(row) => (row.cpu_busy_pct ?? '') !== '' && Number(row.item_total_ms ?? '') > 0
		).length;
		const measured = processorSecondsFrom(health, countsBy('threads')).length;
		expect(offered, 'every article resolved, so this asserts nothing').toBeGreaterThan(measured);

		const processor = page.locator(`${PANEL} [data-article-cost="processor"]`);
		await expect(processor).toHaveAttribute('data-cost-outof', String(offered));
		await expect(processor).toHaveAttribute('data-cost-from', String(measured));
		await expect(processor).toContainText(`${measured}`);
		await expect(processor).toContainText(`${offered}`);
	});

	test('processor time is printed beside the hour it has to fit inside', async ({ page }) => {
		// Decision 4: a processor-second is unreadable on its own. The hour is
		// recomputed here from the same machine records the page joined to, and so
		// is the count of articles it buys - a share of an hour rounds to nothing
		// as soon as an article is cheap, and nothing reads as free.
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const counts = [...new Set(countsBy('threads').values())];
		const hour = runnerHourSeconds(counts);
		expect(hour, 'the canary names no processor count at all').not.toBeNull();

		const span = await shownSpan(page);
		const health = canaryHealth().filter((row) => within(row, span.start, span.end));
		const many = hour! / middle(processorSecondsFrom(health, countsBy('threads')));
		const said = many < 10 ? many.toFixed(1) : grouped(Math.round(many));

		const processor = page.locator(`${PANEL} [data-article-cost="processor"]`);
		await expect(processor).toContainText(`${grouped(hour!)} processor-seconds`);
		await expect(processor).toContainText(`${said} articles at the middle figure`);
	});

	test('a figure the fixture cannot fill prints a dash and the reason, not a zero', async ({
		page
	}) => {
		// The canary records no resident memory, so the added-memory figure is the
		// absence. A zero here would say every article added nothing, which is a
		// claim about the machine rather than about the ledger.
		await page.goto('/console/machine/');
		await widen(page, WIDEST);

		const memory = page.locator(`${PANEL} [data-article-cost="memory"]`);
		expect(
			canaryHealth().filter((row) => (row.llama_rss_bytes ?? '') !== '').length,
			'the canary started recording resident memory, so this arm asserts nothing'
		).toBe(0);
		await expect(memory).toHaveAttribute('data-cost-state', 'unrecorded');
		await expect(memory).toHaveAttribute('data-cost-mid', '');
		await expect(memory.locator('.value')).toHaveText('-');
		await expect(memory).toContainText('no step from one article to the next');
		await expect(memory.locator('[data-article-cost-value="memory"]')).toHaveCount(0);
	});

	test('the panel names what it cannot answer, and the measurement that would', async ({
		page
	}) => {
		// Decision 3. The rise belongs to the model call, and nothing in the ledger
		// says which half of it - so the panel says so rather than letting a reader
		// assume it was the prompt.
		await page.goto('/console/machine/');
		const open = page.locator(`${PANEL} [data-article-cost-open="memory-half"]`);
		await expect(open).toContainText('the prompt it read, or the reply it wrote');
		await expect(open).toContainText('at each call boundary');
	});

	test('the panel is under the group that holds what the model spends', async ({ page }) => {
		// The id is the address, and the group is the decision an operator is
		// taking when he reads it. Both are config, and this is what holds the
		// page to them.
		await page.goto('/console/machine/');
		const group = page.locator('[data-console-group="what-the-model-spends"]');
		await expect(group.locator('[data-console-panel-id="article-cost"]')).toHaveCount(1);
		await expect(page.locator('[data-console-panel-id="article-cost"] h3')).toHaveText(
			'What one article costs the machine'
		);
	});
});
