/** One native Summaries journey and independent real-ledger transport boundaries, not a presentation matrix. */
import { expect, test } from './support/door-page';
import { mkdirSync } from 'node:fs';
import { consoleConfig } from '../src/lib/server/config';
import { buildLedger, buildRows, serveToPage } from './support/ledger-lifecycle';

const panelIds = ['model-cards', 'model-throughput', 'call-ending', 'refusing-rule', 'doubt-reasons', 'faithfulness',
	'source-doubts', 'write-cost', 'score-cost', 'summary-length', 'model-change'];

test('the integrated Summaries route reads the native record and keeps all panels in declared order', async ({ page }) => {
	await page.goto('/console/model/');
	await expect(page).toHaveTitle(/Summaries/);
	await expect(page.locator('[data-console-panels="model"]')).toHaveAttribute('data-route-state', 'ok');
	expect(await page.locator('[data-console-panel-id]').evaluateAll((nodes) => nodes.map((n) => n.getAttribute('data-console-panel-id')))).toEqual(panelIds);
	await expect(page.locator('[data-model-cards] [data-kpi]')).toHaveCount(12);
	await expect(page.locator('[data-console-panel-id="recorded-only"]')).toHaveCount(0);
	await expect(page.locator('[data-candle]')).not.toHaveCount(0);
	await expect(page.locator('[data-run-length]')).not.toHaveCount(0);
	await expect(page.locator('[data-histogram="write-times"]')).toHaveCount(1);
	await expect(page.locator('[data-match-day]')).not.toHaveCount(0);
	await page.locator('[data-model-table-control] > summary').click();
	await expect(page.locator('[data-instrument="coherence"]')).not.toHaveCount(0);
	await expect(page.locator('[data-instrument="semantic_coverage"]').first()).toHaveText('not measured');
	for (const id of ['model-cards', 'source-doubts', 'summary-length']) {
		await expect(page.locator(`[data-console-panel-id="${id}"]`)).toContainText('Nothing acts on these numbers.');
	}
	await page.locator('[data-window-preset="7"]').click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	const queries = page.locator('[data-model-query]');
	await expect(queries).toHaveCount(9);
	for (const query of await queries.all()) {
		const id = await query.getAttribute('data-model-query');
		const requested = id === 'model-change' ? Math.max(...consoleConfig().window_presets) : 7;
		await expect(query).toHaveAttribute('data-query-asked', String(requested));
		await expect(query).toHaveAttribute('data-query-state', 'ready');
	}
	await expect(page.locator('[data-model="table"] caption')).toContainText('7 days');
	expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
	await page.locator('a[href*="/console/machine/"]').first().click();
	await expect(page).toHaveTitle(/Hardware/);
});

for (const state of ['quiet', 'missing', 'unreachable'] as const) {
	test(`native records show the ${state} state without inventing zero readings`, async ({ page, context }, info) => {
		const root = info.outputPath(`native-${state}`);
		mkdirSync(root, { recursive: true });
		for (const ledger of ['item-health', 'summary-quality-evals'] as const) {
			if (state !== 'missing') await buildRows(root, ledger, [{ covers: '2026-08-20', rows: [] }]);
			await serveToPage(context, root, ledger);
		}
		if (state === 'unreachable') {
			await context.route('**/state/compact/*/index/daily.json', (route) => route.abort('failed'));
		}

		await page.goto('/console/model/');
		await expect(page.locator('[data-console-panels="model"]')).toHaveAttribute('data-route-state', state);
		for (const id of panelIds.filter((id) => !['model-cards', 'doubt-reasons'].includes(id))) {
			await expect(page.locator(`[data-console-panel-id="${id}"] [data-empty-state]`))
				.toHaveText(state === 'quiet' ? 'Nothing recorded.' : state === 'missing' ? 'Not published yet.' : 'Did not arrive.');
			await expect(page.locator(`[data-console-panel-id="${id}"] [data-lede]`)).toHaveCount(0);
		}
	});
}

test('pending native doors keep the waiting frame without a settled answer', async ({ page }) => {
	await page.route('**/state/compact/*/index/*.json', () => {});
	await page.goto('/console/model/');
	await expect(page.locator('[data-console-panels="model"]')).toHaveAttribute('data-route-state', 'loading');
	for (const id of panelIds.filter((id) => !['model-cards', 'doubt-reasons'].includes(id))) {
		await expect(page.locator(`[data-console-panel-id="${id}"] [data-reserved]`)).toHaveAttribute('data-panel-state', 'loading');
		await expect(page.locator(`[data-console-panel-id="${id}"] [data-lede]`)).toHaveCount(0);
	}
});

test('a quiet native window still names lost days and unread files', async ({ page, context }, info) => {
	const root = info.outputPath('native-partial');
	mkdirSync(root, { recursive: true });
	for (const ledger of ['item-health', 'summary-quality-evals'] as const) {
		await buildLedger(root, { ledger, pinned: '2026-08-20',
			days: [{ ago: 2, state: 'lost', setAside: 2 }, { ago: 1, state: 'empty' }, { ago: 0, state: 'empty' }] });
		await serveToPage(context, root, ledger);
	}
	await page.goto('/console/model/');
	await expect(page.locator('[data-console-panels="model"]')).toHaveAttribute('data-route-state', 'quiet');
	for (const id of panelIds.filter((id) => !['model-cards', 'doubt-reasons'].includes(id))) {
		const panel = page.locator(`[data-console-panel-id="${id}"]`);
		await expect(panel.locator('[data-record-note]').first()).toContainText('18 Aug 2026');
		await expect(panel).toContainText('set aside');
		await expect(panel.locator('[data-lede]')).toHaveCount(0);
	}
});
