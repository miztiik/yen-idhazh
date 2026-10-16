/** Explicit chart contracts are checked on the real client components and keyboard readouts. */
import { test, expect } from './support/browser';
import { clientCode, drawClient } from './support/console-window/client-render';
import { failureRuleRows } from '../src/lib/console/failure-rules';
import { SERIES_TOKENS } from '../src/lib/console/series-tokens';

let code: string;
test.beforeAll(async () => {
	code = await clientCode([
		['FailureList', './src/lib/components/FailureList.svelte'],
		['StageTimings', './src/lib/components/StageTimings.svelte'],
		['TimeHistogram', './src/lib/components/TimeHistogram.svelte'],
		['DurationStack', './tests/fixtures/panels/DurationStack.svelte'],
		['KpiCard', './src/lib/components/KpiCard.svelte']
	]);
});

test('every card names its rule and a caller may name its range', async ({ page }) => {
	const rule = { changes: [], note: 'No settings changed in this window.' };
	await drawClient(page, code, 'KpiCard', {
		label: 'Recorded articles', value: '8', rule
	});
	await expect(page.locator('[data-model-rule]')).toHaveCount(1);
	await expect(page.locator('[data-model-rule]')).toHaveAttribute('data-model-rule-name', 'kpi-Recorded articles');
	await drawClient(page, code, 'KpiCard', {
		label: 'Unchanged card', value: '8', rule
	});
	await expect(page.locator('[data-model-rule]')).toHaveAttribute('data-model-rule', 'yes');
	await expect(page.locator('[data-model-rule-empty]')).toHaveText('No settings changed in this window.');
	await drawClient(page, code, 'KpiCard', {
		label: 'Recorded articles', value: '8',
		rule,
		ruleName: 'owner-count', ruleRange: { from: '2030-06-01', to: '2030-06-02' }
	});
	await expect(page.locator('[data-model-rule]')).toHaveAttribute('data-model-rule-name', 'owner-count');
	await expect(page.locator('[data-model-rule]')).toHaveAttribute('data-model-rule-from', '2030-06-01');
	await expect(page.locator('[data-model-rule]')).toHaveAttribute('data-model-rule-to', '2030-06-02');
});

test('the stage choices change only the identity-free rule ranking', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	await drawClient(page, code, 'FailureList', {
		ranking: failureRuleRows([
			{ date: '2026-09-01', stage: 'fetch', outcome: 'failed', code: 'blocked', failed_rule: 'Source permission' },
			{ date: '2026-09-02', stage: 'fetch', outcome: 'failed', code: 'network', failed_rule: null },
			{ date: '2026-09-02', stage: 'extract', outcome: 'failed', code: 'blank', failed_rule: 'Empty body' }
		]),
		window: { start: '2026-09-01', end: '2026-09-02' }, stages: { options: ['fetch', 'extract'], chosen: 'fetch' },
		max: 20, readoutMaxShare: 1
	});
	await expect(page.locator('[data-failed-rule-divisor]')).toContainText('2 recorded failures at fetch');
	await expect(page.locator('[data-failed-rule-unknown]')).toContainText('1 of 2');
	await page.getByRole('radio', { name: 'extract', exact: true }).check();
	await expect(page.locator('[data-failed-rule-divisor]')).toContainText('1 recorded failure at extract');
	await expect(page.locator('[data-failure-ledger]')).toContainText('Empty body');
	await expect(page.locator('[data-failure-ledger]')).not.toContainText('Source permission');
	await expect(page.locator('[data-failure-item], [data-source-losses], [data-failure-rows]')).toHaveCount(0);
	await page.locator('[data-failure-ranking]').focus();
	await page.keyboard.press('ArrowLeft');
	await expect(page.locator('[data-readout="failed-rule-trends"]')).toContainText('0 failures');
	expect(errors).toEqual([]);
});

test('timing-rule inspection keeps both events on a changed day', async ({ page }) => {
	await drawClient(page, code, 'StageTimings', {
		days: ['2026-09-01', '2026-09-02'].map((date) => ({
			date, items: 1, fetch: { ms: 10, timed: 1, total: 1 },
			extract: { ms: 20, timed: 1, total: 1 }, summarize: { ms: 100, timed: 1, total: 1 }
		})),
		span: { start: '2026-09-01', end: '2026-09-02' }, height: 220, width: 390,
		tickDensity: 6, readoutMaxShare: 1,
		rule: { changes: [
			{ date: '2026-09-02', kind: 'settings', words: 'The summary prompt changed.' },
			{ date: '2026-09-02', kind: 'checker', words: 'The score checker changed.' }
		], note: 'Compared with the preceding recorded settings.' }
	});
	await expect(page.locator('[data-readout="timings"]')).toContainText('The summary prompt changed.');
	await expect(page.locator('[data-readout="timings"]')).toContainText('The score checker changed.');
	await expect(page.locator('[data-model-rule-line]')).toHaveCount(1);
	await expect(page.locator('svg[data-chart="stage-timings"]')).toHaveAttribute('data-chart-name', 'timings');
	await page.locator('[data-timing="plot"]').focus();
	await page.keyboard.press('ArrowLeft');
	await expect(page.locator('[data-readout="timings"]')).not.toContainText('The summary prompt changed.');
	await page.keyboard.press('ArrowRight');
	await expect(page.locator('[data-readout="timings"]')).toContainText('The score checker changed.');
});

test('histogram bars and inspection swatches use the same named quantity', async ({ page }) => {
	await drawClient(page, code, 'TimeHistogram', {
		times: { n: 2, median: 1000, p95: 2000, fastest: 500, slowest: 2000,
			bins: [{ from: 0, to: 1, n: 1, throughPct: 50 }, { from: 1, to: 2, n: 1, throughPct: 100 }] },
		name: 'reading', subject: 'Seconds to read a prompt', verb: 'read', noun: 'prompt', nouns: 'prompts',
		noRuleReason: 'This pooled window has no date axis.', width: 390, height: 220,
		barToken: SERIES_TOKENS['reading-prompt']
	});
	await expect(page.locator('[data-hist-bin] rect').first()).toHaveAttribute('fill', 'var(--chart-6)');
	expect(await page.locator('[data-readout-row="Read in this band"] .readout-swatch').evaluate((node) => (node as HTMLElement).style.background)).toBe('var(--chart-6)');
	await expect(page.locator('[data-histogram="cumulative"]')).toHaveAttribute('stroke', 'var(--chart-3)');
	await expect(page.locator('svg[data-chart="time-histogram"]')).toHaveAttribute('data-chart-name', 'reading');
});

for (const width of [390, 1440]) {
	test(`elapsed markers stay inside the ${width}px frame and retain a zero beside an unknown day`, async ({ page }) => {
		await page.setViewportSize({ width, height: 900 });
		await drawClient(page, code, 'DurationStack', { width: width - 24 });
		await expect(page.locator('[data-stack-elapsed]')).toHaveCount(2);
		await expect(page.locator('[data-model-rule-name="item-time"]')).toHaveAttribute('data-model-rule-from', '2026-09-01');
		await expect(page.locator('[data-model-rule-name="item-time"]')).toHaveAttribute('data-model-rule-to', '2026-09-03');
		await expect(page.locator('[data-stack-overlap]')).toHaveCount(1);
		await expect(page.locator('[data-stack-elapsed="2026-09-02"]')).toHaveAttribute('data-elapsed-value', '0');
		await expect(page.locator('[data-stack-elapsed="2026-09-03"]')).toHaveCount(0);
		await expect(page.locator('[data-stack-reconciliation-key]')).toContainText('Solid crossbar: Elapsed time');
		await page.locator('[data-chart-name="item-time"]').focus();
		await page.keyboard.press('ArrowLeft');
		await page.keyboard.press('ArrowLeft');
		await expect(page.locator('[data-readout-row="Elapsed time"]')).toContainText('5');
		await expect(page.locator('[data-readout-row="Overlap"]')).toContainText('3');
		expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
	});
}
