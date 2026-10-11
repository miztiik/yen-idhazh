/** Hardware reads only the declared public records and preserves the independent count refusal. */
import { expect, test, type Page } from './support/door-page';
import * as queries from '../src/lib/console/queries/machine';
import type { Row } from '../src/lib/data/ledger';
import { buildRows, serveToPage } from './support/ledger-lifecycle';
import { machineRecordState } from './support/machine-record-state';

const DAY = '2026-08-20', RUN = `${DAY}-1`;
const PANELS = ['two-clocks', 'processor-lost', 'disk-reads', 'machine-cards', 'slower-machines',
	'platform-mix', 'slowest-articles', 'tail-trend', 'closest-to-memory', 'memory-held',
	'context-headroom', 'article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost'];

function cells(ledger: string): Row {
	return Object.fromEntries(Object.values(queries).filter((query) => query.ledger === ledger)
		.flatMap((query) => query.columns).map((name) => [name, null]));
}

async function fixture(page: Page, count: number | null, conflict = false, hostConflict = false) {
	const root = test.info().outputPath('machine-records');
	await buildRows(root, 'host-fingerprint', [{ covers: DAY, rows: (hostConflict ? [0, 1, 0] : [0, 1]).map((shard, index) => ({
		...cells('host-fingerprint'), date: DAY, run_id: RUN, job: 'work', shard,
		fingerprint: '0123456789abcdef', cpu_model: 'Fixture CPU', cores: index === 2 ? 8 : 4, threads: 8,
		model_load_ms: 1000, job_seconds: 30, server_prompt_tokens: 100, server_prompt_seconds: 1
	})) }]);
	await buildRows(root, 'item-health', [{ covers: DAY, rows: [0, 1].map((shard) => ({
		...cells('item-health'), date: DAY, run_id: RUN, item_id: `article-${shard}`, source_id: 'fixture',
		machine_job: 'work', machine_shard: shard, cpu_model: 'Fixture CPU',
		item_index: shard, input_tokens: 100, cached_tokens: 0, output_tokens: 20,
		prefill_ms: 2000, decode_ms: 500, item_total_ms: 4000, fetch_ms: 500, extract_ms: 500,
		summarize_ms: 2000, faithfulness_ms: 500, stage_gap_ms: 500, queue_wait_ms: 100,
		label_input_tokens: 100, label_cached_tokens: 10, summary_input_tokens: 200, summary_cached_tokens: 40,
		n_ctx_configured: 8192, n_parallel: 2, os_mem_total_bytes: 16 * 2 ** 30,
		os_mem_available_min_bytes: 6 * 2 ** 30, os_mem_available_bytes: 6 * 2 ** 30
	})) }]);
	await buildRows(root, 'run-shards', [{ covers: DAY, rows: [
		{ date: DAY, run_id: RUN, shards: count },
		...(conflict ? [{ date: DAY, run_id: RUN, shards: 3 }] : [])
	] }]);
	for (const ledger of ['host-fingerprint', 'item-health', 'run-shards'] as const) {
		await serveToPage(page.context(), root, ledger);
	}
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panels="machine"]')).not.toHaveAttribute('data-route-state', 'loading');
}

test('all fifteen panels draw after public queries arrive, without a manifest request', async ({ page }) => {
	const privateRequests: string[] = [];
	page.on('request', (request) => {
		if (/\/(?:run|plan)\.json|\/state\/.*(?:run-plan|prompt)/.test(request.url())) privateRequests.push(request.url());
	});
	await fixture(page, 2);
	expect(privateRequests).toEqual([]);
	expect(await page.locator('[data-console-panel-id]').evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-console-panel-id')))).toEqual(PANELS);
	await expect(page.locator('[data-machine-refused]')).toHaveCount(0);
	await expect(page.locator('[data-clock-pair]')).toHaveCount(2);
	for (const pair of await page.locator('[data-clock-pair]').all()) {
		await expect(pair).toHaveAttribute('data-clock-gap', '50.00');
		await expect(pair).toHaveAttribute('data-clock-agrees', 'false');
	}
	await expect(page.locator('[data-console-panel-id="closest-to-memory"] [data-lede]')).toHaveText("The tightest article left 6.00 GiB of the machine's 16.00 GiB free.");
	await expect(page.locator('[data-console-panel-id="slowest-articles"]')).toContainText('4.0 seconds');
	const context = page.locator('[data-console-panel-id="context-headroom"]');
	await expect(context.locator('[data-lede]')).toContainText('4.9 percent of the smallest reading limit');
	await expect(context).toContainText('4096 tokens per request slot');
	await expect(context.locator('[data-comparison]')).toHaveText('Each prompt against the reading limit.');
	await expect(page.locator('[data-console-panel-id="prompt-reuse"] [data-lede]')).toHaveText('10 tokens held for the middle label request.');
	for (const call of ['label', 'summary']) {
		await expect(context.locator(`svg[data-chart-name="context-${call}"]`)).toContainText('Reading limit: 4096 tokens per slot');
	}
});

test('a recorded count of one refuses two observed shards; unknown does not invent a denominator', async ({ page }) => {
	await fixture(page, 1);
	await expect(page.locator('[data-machine-refused]')).toHaveAttribute('data-machine-refused', '1');
	await expect(page.locator('[data-refused-run]')).toContainText(RUN);
	await expect(page.locator('[data-clock-pair]')).toHaveCount(0);
});

test('unknown count is retained without refusing or counting observed hosts as the plan', async ({ page }) => {
	await fixture(page, null);
	await expect(page.locator('[data-machine-refused]')).toHaveCount(0);
	await expect(page.locator('[data-clock-pair]')).toHaveCount(2);
	await expect(page.locator('[data-planned-shards]')).toHaveText('The planned shard count was not recorded.');
});

test('existing published host cells still refuse conflicting records after query migration', async ({ page }) => {
	await fixture(page, 2, false, true);
	await expect(page.locator('[data-refused-run]')).toContainText('two machine records that disagree');
	await expect(page.locator('[data-clock-pair]')).toHaveCount(0);
});

test('the standing retries repaired indexes instead of keeping a failed read session', async ({ page }) => {
	await machineRecordState(page, 'unreachable');
	await fixture(page, 2);
	await expect(page.locator('[data-console-retry]')).toBeVisible();
	await page.unrouteAll({ behavior: 'ignoreErrors' });
	await page.locator('[data-console-retry]').click();
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'ok');
	await expect(page.locator('[data-clock-pair]')).toHaveCount(2);
});

test('an unsettled count correction is a visible refusal, not a reactive page crash', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	await fixture(page, 2, true);
	await expect(page.locator('[data-machine-count-refusal]')).toContainText('unsettled corrections');
	await expect(page.locator('[data-panel-query="two-clocks"]')).toHaveAttribute('data-machine-panel-state', 'unreachable');
	expect(errors).toEqual([]);
});

for (const state of ['missing', 'quiet', 'unreachable'] as const) {
	test(`all fifteen panels keep their ${state} state without inventing lost days`, async ({ page }) => {
		await machineRecordState(page, state);
		await page.goto('/console/machine/');
		await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', state);
		for (const id of PANELS) await expect(page.locator(`[data-panel-query="${id}"]`)).toHaveAttribute('data-machine-panel-state', state);
		await expect(page.locator('[data-recording="machine-destroyed"]')).toHaveCount(0);
		await expect(page.locator('[data-machine-refused]')).toHaveCount(0);
	});
}

test('editable counterfactual prices redraw four figures, persist, and reset', async ({ page }) => {
	await fixture(page, 2);
	const total = page.locator('[data-cost="total"] dd');
	async function price(input: number, output: number) {
		for (const [name, value] of [['input', input], ['output', output]] as const) {
			await page.locator(`[data-rate-input="${name}"]`).fill(String(value));
			await page.locator(`[data-rate-input="${name}"]`).press('Tab');
		}
	}
	await price(100, 300);
	await expect(total).toContainText('0.03');
	await price(200, 600);
	await expect(total).toContainText('0.06');
	await page.reload();
	await expect(page.locator('[data-cost-figures]')).toHaveAttribute('data-cost-source', 'yours');
	await expect(total).toContainText('0.06');
	await page.locator('[data-rate-reset]').click();
	await expect(page.locator('[data-cost-figures]')).toHaveAttribute('data-cost-source', 'configured');
});

test('without script the configuration-only shell contains fifteen empty reserved frames', async ({ browser }) => {
	const context = await browser.newContext({ javaScriptEnabled: false });
	const page = await context.newPage();
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panel-id]')).toHaveCount(15);
	await expect(page.locator('[data-panel-query] svg')).toHaveCount(15);
	await expect(page.locator('[data-panel-query] svg rect:not([data-reserved-ground]), [data-panel-query] svg path')).toHaveCount(0);
	await expect(page.locator('[data-console-standing]')).toHaveText('');
	await expect(page.locator('[data-machine-refused], [data-cost-figures]')).toHaveCount(0);
	await context.close();
});
