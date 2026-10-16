/** Actual native cost and Hardware readers preserve independent numeric and absence oracles. */
import { expect, test, type Page } from './support/door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { nativeItemCost } from '../src/lib/console/pipelines/item-cost';
import { labelHeldMedian, reuseChecks, reuseSeries } from '../src/lib/console/machine/records';
import { itemCostQuery } from '../src/lib/console/queries/pipelines';
import { promptReuseQuery } from '../src/lib/console/queries/machine';
import { rangeFor, type RouteReach } from '../src/lib/console/queries/window';
import type { Row } from '../src/lib/data/ledger';
import { ONE_DAYS } from './support/pipelines-span';
import { dayBefore, openRetained } from './support/retained-telemetry';
import { telemetryRow } from './support/telemetry-row';

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };
const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

test.describe('what the actual native item clocks cost', () => {
	test('an instrument that did not run is absent, while zero is a measurement', () => {
		const cost = nativeItemCost([
			{ prefill_ms: 4000, decode_ms: 2000, input_tokens: 100, cached_tokens: 0, output_tokens: 10 },
			{ prefill_ms: null, decode_ms: '', input_tokens: null, cached_tokens: null, output_tokens: null },
			{ prefill_ms: 0, decode_ms: 0 }
		]);
		expect(cost.rows).toBe(3);
		expect(cost.reading).toMatchObject({ n: 2, fastest: 0, slowest: 4000 });
		expect(cost.writing).toMatchObject({ n: 2, fastest: 0, slowest: 2000 });
		expect(cost.readPairs).toBe(1);
		expect(cost.writePairs).toBe(1);
		expect(cost.msPerReadToken).toBe(40);
		expect(cost.msPerWrittenToken).toBe(200);
	});

	test('each pooled rate uses its own complete pairs, not all clocks or a mean of item rates', () => {
		const cost = nativeItemCost([
			{ prefill_ms: 1000, input_tokens: 10, cached_tokens: 0, decode_ms: null, output_tokens: 10 },
			{ prefill_ms: 1000, input_tokens: 100, cached_tokens: 0, decode_ms: 500, output_tokens: 10 },
			{ prefill_ms: 9000, input_tokens: null, cached_tokens: 0, decode_ms: 500, output_tokens: 90 },
			{ prefill_ms: null, input_tokens: 90_000, cached_tokens: 0, decode_ms: 9000, output_tokens: null }
		]);
		expect(cost.reading?.n).toBe(3);
		expect(cost.writing?.n).toBe(3);
		expect(cost.readPairs).toBe(2);
		expect(cost.writePairs).toBe(2);
		expect(cost.msPerReadToken).toBeCloseTo(2000 / 110, 10);
		expect(cost.msPerWrittenToken).toBe(10);
		expect(cost.writeCostRatio).toBeCloseTo(0.55, 10);
	});

	test('cached tokens leave the fresh-read divisor, but an unknown cache never becomes zero', () => {
		const cost = nativeItemCost([
			{ prefill_ms: 1000, input_tokens: 1000, cached_tokens: 900 },
			{ prefill_ms: 9000, input_tokens: 1000, cached_tokens: null }
		]);
		expect(cost.reading?.n).toBe(2);
		expect(cost.readPairs).toBe(1);
		expect(cost.unknownCache).toBe(1);
		expect(cost.msPerReadToken).toBe(10);
		expect(cost.msPerWrittenToken).toBeNull();
		expect(cost.writeCostRatio).toBeNull();
	});

	test('invalid cache pairs and a zero fresh-token divisor do not supply a rate', () => {
		const cost = nativeItemCost([
			{ prefill_ms: 1000, input_tokens: 100, cached_tokens: 100 },
			{ prefill_ms: 1000, input_tokens: 100, cached_tokens: 101 },
			{ prefill_ms: 1000, input_tokens: 100, cached_tokens: -1 },
			{ prefill_ms: -1, input_tokens: 100, cached_tokens: 0 },
			{ decode_ms: 1000, output_tokens: 0 }
		]);
		expect(cost.readPairs).toBe(0);
		expect(cost.writePairs).toBe(0);
		expect(cost.msPerReadToken).toBeNull();
		expect(cost.msPerWrittenToken).toBeNull();
	});

	test('even token cohorts use the native upper middle, not an interpolated half token', () => {
		const cost = nativeItemCost([
			{ input_tokens: 1687, output_tokens: 10 }, { input_tokens: 1688, output_tokens: 11 }
		]);
		expect(cost.promptTokens).toBe(1688);
		expect(cost.writtenTokens).toBe(11);
	});

	test('both histograms share a time domain and an empty cohort supplies no domain or ratio', () => {
		const cost = nativeItemCost([{ prefill_ms: 1000, decode_ms: 4000 }, { prefill_ms: 2000, decode_ms: 8000 }]);
		expect(cost.domain).toEqual([1, 16]);
		const absent = nativeItemCost([]);
		expect(absent).toMatchObject({ rows: 0, reading: null, writing: null, readPairs: 0, writePairs: 0, writeCostRatio: null });
		expect(absent.domain).toBeUndefined();
	});
});

test.describe('Hardware owns the native cached-input readings', () => {
	test('label and summary calls keep distinct measured zero, held text and fresh text', () => {
		const rows: Row[] = [{
			date: '2026-09-12', label_input_tokens: 1497, label_cached_tokens: 0, label_cache_pct: 0,
			summary_input_tokens: 2389, summary_cached_tokens: 1493, summary_cache_pct: 62.49
		}];
		expect(promptReuseQuery.columns).toContain('label_cached_tokens');
		expect(promptReuseQuery.columns).toContain('summary_cached_tokens');
		expect(labelHeldMedian(rows)).toBe(0);
		expect(reuseSeries(rows).map((series) => series.points[0].value)).toEqual([0, 896]);
		const checks = reuseChecks(rows);
		expect(checks[0]).toEqual({ call: 'label', ours: 0, server: 0, count: 1 });
		expect(checks[1]).toMatchObject({ call: 'summary', server: 62.49, count: 1 });
		expect(checks[1].ours).toBeCloseTo(100 * 1493 / 2389, 10);
	});

	test('pooled held share and the middle request remain independent readings', () => {
		const rows: Row[] = [
			{ date: '2026-09-12', label_input_tokens: 90_000, label_cached_tokens: 0, label_cache_pct: 0 },
			{ date: '2026-09-12', label_input_tokens: 1000, label_cached_tokens: 900, label_cache_pct: 90 },
			{ date: '2026-09-12', label_input_tokens: 1000, label_cached_tokens: 900, label_cache_pct: 90 }
		];
		const check = reuseChecks(rows)[0];
		expect(check.count).toBe(3);
		expect(check.ours).toBeCloseTo(100 * 1800 / 92_000, 10);
		expect(check.server).toBe(90);
		expect(labelHeldMedian(rows)).toBe(900);
	});

	test('unknown per-call cache cannot fall back to item totals or become read whole', () => {
		const rows: Row[] = [
			{ date: '2026-09-12', input_tokens: 4000, cached_tokens: 1000, label_cached_tokens: null,
				summary_input_tokens: 1000, summary_cached_tokens: null },
			{ date: '2026-09-13', label_input_tokens: 1000, label_cached_tokens: 0,
				summary_input_tokens: 1000, summary_cached_tokens: 1000 }
		];
		expect(reuseSeries(rows).map((series) => series.points.map((point) => point.value))).toEqual([
			[null, 0], [null, 0]
		]);
		expect(reuseChecks(rows).map((check) => [check.count, check.ours])).toEqual([[1, 0], [1, 100]]);
		expect(labelHeldMedian(rows.slice(0, 1))).toBeNull();
	});
});

test('the native cost query asks its closed window at the common record end, not the build clock', () => {
	const reach: RouteReach = { through: '2030-06-15', ledgers: {
		'item-health': { state: 'ok', first: '2030-03-01', through: '2030-06-16', lastRows: null, fault: null }
	} };
	expect([1, 7, 14, 30, 90].map((days) => rangeFor(itemCostQuery, days, reach, PRESETS))).toEqual([
		{ from: '2030-06-15', to: '2030-06-15', days: 1, asked: 1 },
		{ from: '2030-06-09', to: '2030-06-15', days: 7, asked: 7 },
		{ from: '2030-06-02', to: '2030-06-15', days: 14, asked: 14 },
		{ from: '2030-05-17', to: '2030-06-15', days: 30, asked: 30 },
		{ from: '2030-03-18', to: '2030-06-15', days: 90, asked: 90 }
	]);
});

async function hydrated(page: Page) {
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', String(days));
}

async function drawn(page: Page) {
	return page.locator('[data-windowed="item-cost"]').evaluate((node) => {
		const histogram = (name: string) => {
			const chart = node.querySelector(`[data-histogram="${name}"]`);
			if (chart === null) return null;
			return {
				n: Number(chart.getAttribute('data-histogram-n')),
				bars: [...chart.querySelectorAll('[data-hist-bin]')].map((bin) =>
					Number(bin.getAttribute('data-hist-bin-n')))
			};
		};
		return {
			days: Number(node.getAttribute('data-window-days')),
			says: (node.textContent ?? '').replace(/\s+/g, ' ').trim(),
			reading: histogram('item-reading'), writing: histogram('item-writing')
		};
	});
}

async function openNativeCost(page: Page) {
	await openRetained(page, ({ end }) => Array.from({ length: 8 }, (_, ago) =>
		Array.from({ length: 8 }, (_, item) => telemetryRow({
			date: dayBefore(end, ago), item_id: `cost-${ago}-${item}`,
			prefill_ms: 1000, decode_ms: 4000, input_tokens: 100, cached_tokens: 10, output_tokens: 40
		}))).flat());
}

test.describe('the real native item-cost component', () => {
	test('THE ORACLE: native cost retains the measured clock and sends prompt reuse to Hardware', async ({ page }) => {
		await openNativeCost(page);
		const panel = page.locator('[data-windowed="item-cost"]');
		await expect(panel).toBeVisible();
		await expect(panel.locator('[data-item-cost-share]'), 'the retired prompt-share carrier returned').toHaveCount(0);
		await expect(panel.locator('[data-item-cost-pairs]')).toContainText('Prompt reuse is on');
		await expect(panel.getByRole('link', { name: 'Hardware' })).toHaveAttribute('href', '/console/machine/');
		await expect(panel.locator('[data-item-cost-lead]')).toHaveText('4.00 seconds to write one summary.');
	});

	test('the section draws the window the control set, and every item it counted is in a bar', async ({ page }) => {
		await openNativeCost(page);
		await hydrated(page);
		for (const preset of PRESETS) {
			await setWindow(page, preset);
			const marks = await drawn(page);
			expect(marks.days).toBe(preset);
			expect(marks.says).not.toMatch(ONE_DAYS);
			for (const [name, shown] of [['reading', marks.reading], ['writing', marks.writing]] as const) {
				expect(shown, `${name} has no positive cohort`).not.toBeNull();
				if (shown === null) throw new Error(`${name} has no positive cohort`);
				expect(shown.n).toBe(Math.min(preset, 8) * 8);
				expect(shown.bars.reduce((total, n) => total + n, 0)).toBe(shown.n);
			}
		}
	});

	test('the two clocks are drawn apart, and no chart pools them', async ({ page }) => {
		await openNativeCost(page);
		const section = page.locator('[data-windowed="item-cost"]');
		await expect(section.locator('[data-histogram="item-reading"]')).toHaveCount(1);
		await expect(section.locator('[data-histogram="item-writing"]')).toHaveCount(1);
		await expect(section.locator('[data-histogram-n]')).toHaveCount(2);
	});

	test('the reading chart counts prompts, and never calls one a summary', async ({ page }) => {
		await openNativeCost(page);
		const chart = page.locator('[data-histogram="item-reading"]');
		const label = (await chart.locator('svg').getAttribute('aria-label')) ?? '';
		const said = `${await chart.innerText()} ${label}`.toLowerCase();
		expect(said).toContain('prompt');
		expect(said).not.toContain('summar');
	});

	test('paired clock counts follow the window without restoring the retired prompt-share trend', async ({ page }) => {
		await openNativeCost(page);
		await hydrated(page);
		const note = page.locator('[data-item-cost-pairs]');
		for (const preset of PRESETS) {
			await setWindow(page, preset);
			await expect(note).toHaveCount(1);
			const said = (await note.innerText()).replace(/\s+/g, ' ').trim();
			const pairs = Math.min(preset, 8) * 8;
			expect(said).toContain(`Reading: ${pairs} paired clocks and fresh-token counts; writing: ${pairs} paired clocks and output counts.`);
			await expect(page.locator('[data-item-cost-share-note], [data-item-cost-share]')).toHaveCount(0);
		}
	});

	test('unmeasured native clocks have no bars and unknown cache is never counted as zero', async ({ page }) => {
		await openRetained(page, ({ end }) => [telemetryRow({ date: end, input_tokens: 100 })]);
		const section = page.locator('[data-windowed="item-cost"]');
		await expect(section.locator('[data-item-cost-lead]')).toHaveText('No summary-writing clock was measured.');
		await expect(section.locator('[data-item-cost="item-reading"]')).toHaveText('No prompt clock was measured.');
		await expect(section.locator('[data-item-cost="item-writing"]')).toHaveText('No summary clock was measured.');
		await expect(section.locator('[data-histogram-n]')).toHaveCount(0);
		await expect(section.locator('[data-item-cost-pairs]')).toContainText('1 prompts have no recorded cache count and are not treated as read whole.');
	});
});
