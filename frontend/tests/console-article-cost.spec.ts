/** What one article costs the machine: the arithmetic, then the panel.
 *
 * The arithmetic tests write the item rows and machine records they read, then
 * write out the answers those rows must produce. The browser tests read only
 * the page and the attributes it publishes beside the printed figures.
 *
 * Pure functions and the rendered page only. No `$app` import and no SvelteKit
 * alias: a spec that reaches one fails the whole file at load instead of
 * failing one test.
 */

import { expect, test, type Page } from './support/door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { seconds } from '../src/lib/charts/machine';
import { grouped } from '../src/lib/charts/series';
import {
	articleCost,
	costTrack,
	runnerHourSeconds,
	type MachineProcessors
} from '../src/lib/console/machine/article-cost';

const CONSOLE = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console: { window_presets: number[] } }
).console;

const WIDEST = Math.max(...CONSOLE.window_presets);

/** The panel's own wording for a signed step, restated here. */
function mib(bytes: number): string {
	const value = bytes / 1024 / 1024;
	const sign = value > 0 ? '+' : value < 0 ? '-' : '';
	return `${sign}${grouped(Number(Math.abs(value).toFixed(1)))} MiB`;
}

/** One item row, with only the cells a figure needs. */
function itemRow(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const row: Record<string, string> = {};
	for (const [key, value] of Object.entries(cells)) row[key] = String(value);
	return row;
}

test.describe('the three costs, as arithmetic', () => {
	test('processor time is the busy share across the LOGICAL processors, not the cores', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 50, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 25, item_total_ms: 2000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 25, item_total_ms: 1000 })
		];
		const cost = articleCost(health, [
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 8 }
		]);
		expect(cost.processorSeconds.from, 'not every offered article was measured').toBe(3);
		expect(cost.processorSeconds.outOf).toBe(3);
		expect(cost.processorSeconds.low).toBeCloseTo(2, 6);
		expect(cost.processorSeconds.mid).toBeCloseTo(4, 6);
		expect(cost.processorSeconds.high).toBeCloseTo(4, 6);
		expect(cost.processors).toEqual([8]);
	});

	test('THE ORACLE: a run whose machine record names no processor count is a dash', () => {
		// The rule, on rows written here rather than found: two articles that both
		// recorded what they kept busy and how long they ran, and a record that
		// reached the machine and left the count empty. Nothing about the runner
		// we usually get may fill it in.
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 80, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 40, item_total_ms: 2000 })
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

	test('articles no machine record answered for are counted, not dropped', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'blind', machine_shard: 0, cpu_busy_pct: 80, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'seen', machine_shard: 0, cpu_busy_pct: 50, item_total_ms: 1000 }),
			itemRow({ date: '2026-08-20', run_id: 'untimed', machine_shard: 0, cpu_busy_pct: 90 })
		];
		const cost = articleCost(health, [
			{ date: '2026-08-20', run_id: 'blind', shard: 0, threads: null },
			{ date: '2026-08-20', run_id: 'seen', shard: 0, threads: 4 }
		]);
		expect(cost.processorSeconds.outOf, 'the unanswered article was dropped').toBe(2);
		expect(cost.processorSeconds.from, 'an unanswered article was treated as measured').toBe(1);
		expect(cost.processorSeconds.mid).toBeCloseTo(2, 6);
	});

	test('a shard whose records agree counts once; one whose records disagree is left out, whichever order they arrive in', () => {
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, cpu_busy_pct: 50, item_total_ms: 2000 })
		];
		// Two machine records for one shard that both name 4 processors: a
		// duplicate write, not a disagreement, and the shard still counts once.
		const agreeing = articleCost(health, [
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 4 },
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 4 }
		]);
		expect(agreeing.processorSeconds.from).toBe(1);
		expect(agreeing.processorSeconds.mid).toBeCloseTo(4, 6);
		expect(agreeing.processors).toEqual([4]);

		// Two machine records that disagree, naming 4 and 8: the shard is left
		// out of the figure, the same whichever order the two records arrive in.
		// Picking whichever comes last would be the pick a refused run's two
		// disagreeing records exist to refuse.
		const forward = articleCost(health, [
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 4 },
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 8 }
		]);
		const backward = articleCost(health, [
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 8 },
			{ date: '2026-08-20', run_id: 'r1', shard: 0, threads: 4 }
		]);
		for (const cost of [forward, backward]) {
			expect(cost.processorSeconds.from).toBe(0);
			expect(cost.processorSeconds.mid).toBeNull();
			expect(cost.processorSeconds.outOf).toBe(1);
			expect(cost.processors).toEqual([]);
		}
	});

	test('model time is reading the prompt and writing the reply, added up', () => {
		const cost = articleCost(
			[
				itemRow({ date: '2026-08-20', run_id: 'r1', prefill_ms: 1200, decode_ms: 800 }),
				itemRow({ date: '2026-08-20', run_id: 'r1', prefill_ms: 100, decode_ms: 300 }),
				itemRow({ date: '2026-08-20', run_id: 'r1', prefill_ms: 1000 })
			],
			[]
		);
		expect(cost.modelSeconds.from).toBe(2);
		expect(cost.modelSeconds.outOf).toBe(2);
		expect(cost.modelSeconds.low).toBeCloseTo(0.4, 6);
		expect(cost.modelSeconds.mid).toBeCloseTo(1.2, 6);
		expect(cost.modelSeconds.high).toBeCloseTo(2, 6);
	});

	test('added memory is a step between neighbours of ONE shard', () => {
		// A step is taken between neighbours; a gap in the numbering is not a
		// step; and a shard boundary is not a step either, because a new shard
		// starts a new model server and its first reading would be a restart.
		const health = [
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 0, llama_rss_bytes: 100 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 1, llama_rss_bytes: 160 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 2, llama_rss_bytes: 140 }),
			// A gap: item 4 follows item 2, so whatever happened at item 3 is not
			// one article's doing.
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 4, llama_rss_bytes: 900 }),
			// A second shard, whose first reading is a fresh server.
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 1, item_index: 0, llama_rss_bytes: 500 }),
			itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 1, item_index: 1, llama_rss_bytes: 510 })
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
			[itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 0, llama_rss_bytes: 100 })],
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

const PANEL = '[data-windowed="machine-article-cost"]';

async function numericCost(
	page: Page,
	name: 'processor' | 'memory' | 'model',
	cell: 'low' | 'mid' | 'high' | 'from' | 'outof'
): Promise<number> {
	return Number(
		(await page.locator(`${PANEL} [data-article-cost="${name}"]`).getAttribute(`data-cost-${cell}`)) ??
			'NaN'
	);
}

test.describe('the panel', () => {
	test('printed values match the figures the page publishes beside them', async ({ page }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const processorMid = await numericCost(page, 'processor', 'mid');
		const modelMid = await numericCost(page, 'model', 'mid');
		expect(processorMid, 'the processor figure did not publish a number').toBeGreaterThan(0);
		expect(modelMid, 'the model figure did not publish a number').toBeGreaterThan(0);
		await expect(page.locator(`${PANEL} [data-article-cost="processor"]`)).toHaveAttribute(
			'data-cost-state',
			'measured'
		);
		await expect(page.locator(`${PANEL} [data-article-cost="model"]`)).toHaveAttribute(
			'data-cost-state',
			'measured'
		);
		const processor = page.locator(`${PANEL} [data-article-cost="processor"]`);
		await expect(processor.locator('[data-article-cost-value="processor"]')).toHaveText(
			seconds(processorMid)
		);
		await expect(page.locator(`${PANEL} [data-article-cost-value="model"]`)).toHaveText(
			seconds(modelMid)
		);

		for (const name of ['processor', 'model'] as const) {
			const low = await numericCost(page, name, 'low');
			const mid = await numericCost(page, name, 'mid');
			const high = await numericCost(page, name, 'high');
			expect(low, `${name} low is above the middle figure`).toBeLessThanOrEqual(mid);
			expect(high, `${name} high is below the middle figure`).toBeGreaterThanOrEqual(mid);
			expect(await numericCost(page, name, 'from'), `${name} has no measured articles`).toBeGreaterThan(
				0
			);
			expect(await numericCost(page, name, 'outof'), `${name} counts fewer offered articles than measured`).toBeGreaterThanOrEqual(
				await numericCost(page, name, 'from')
			);
		}
	});

	test('the processor card publishes measured and offered counts in the words', async ({ page }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const processor = page.locator(`${PANEL} [data-article-cost="processor"]`);
		const measured = await processor.getAttribute('data-cost-from');
		const offered = await processor.getAttribute('data-cost-outof');
		expect(measured, 'the processor card published no measured count').not.toBeNull();
		expect(offered, 'the processor card published no offered count').not.toBeNull();
		await expect(processor).toContainText(grouped(Number(measured)));
		await expect(processor).toContainText(grouped(Number(offered)));
		expect(Number(offered), 'the card offered fewer articles than it measured').toBeGreaterThanOrEqual(
			Number(measured)
		);
	});

	test('processor time is printed beside the hour it has to fit inside', async ({ page }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const processor = page.locator(`${PANEL} [data-article-cost="processor"]`);
		const counts = ((await processor.getAttribute('data-cost-processors')) ?? '')
			.split(' ')
			.filter((value) => value !== '')
			.map(Number);
		const hour = runnerHourSeconds(counts);
		expect(hour, 'the page published no processor count').not.toBeNull();
		const many = hour! / (await numericCost(page, 'processor', 'mid'));
		const said = many < 10 ? many.toFixed(1) : grouped(Math.round(many));

		await expect(processor).toContainText(`${grouped(hour!)} processor-seconds`);
		await expect(processor).toContainText(`${said} articles at the middle figure`);
	});

	test('the added-memory printout matches the figure the page publishes beside it', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const memory = page.locator(`${PANEL} [data-article-cost="memory"]`);
		await expect(memory).toHaveAttribute('data-cost-state', 'measured');
		const mid = await numericCost(page, 'memory', 'mid');
		const low = await numericCost(page, 'memory', 'low');
		const high = await numericCost(page, 'memory', 'high');
		expect(low, 'the memory low is above the middle figure').toBeLessThanOrEqual(mid);
		expect(high, 'the memory high is below the middle figure').toBeGreaterThanOrEqual(mid);
		expect(await numericCost(page, 'memory', 'from'), 'the memory card has no measured steps').toBeGreaterThan(
			0
		);
		expect(Number((await memory.getAttribute('data-cost-shards')) ?? 'NaN')).toBeGreaterThan(0);
		await expect(memory.locator('[data-article-cost-value="memory"]')).toHaveText(
			mib(mid)
		);
	});

	test('a figure no written row can fill is an absence, not a zero', () => {
		const cost = articleCost(
			[itemRow({ date: '2026-08-20', run_id: 'r1', machine_shard: 0, item_index: 0 })],
			[]
		);
		expect(cost.addedBytes.from).toBe(0);
		expect(cost.addedBytes.outOf).toBe(0);
		expect(cost.addedBytes.mid, 'the missing memory step was reported as zero').toBeNull();
	});

	test('a card with no middle figure prints a dash, never a zero, at every preset', async ({ page }) => {
		// A zero would say every article cost nothing, which is a claim about the
		// machine rather than about the ledger. Which cards have a figure is the
		// window's own fact; the rule is the same for each card at each preset.
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		for (const preset of CONSOLE.window_presets) {
			await widen(page, preset);
			for (const name of ['processor', 'memory', 'model'] as const) {
				const card = page.locator(`${PANEL} [data-article-cost="${name}"]`);
				const value = card.locator(`[data-article-cost-value="${name}"]`);
				if ((await card.getAttribute('data-cost-mid')) === '') {
					await expect(card.locator('.value'), `${name} at ${preset} days prints no dash`).toHaveText('-');
					await expect(value, `${name} at ${preset} days prints a figure it does not have`).toHaveCount(0);
				} else {
					await expect(value, `${name} at ${preset} days prints no figure`).toHaveCount(1);
				}
			}
		}
	});

	test('the panel names what it cannot answer, and the measurement that would', async ({
		page
	}) => {
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
