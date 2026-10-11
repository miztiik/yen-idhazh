import { expect, test } from './support/door-page';
import { readFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { callEnding } from '../src/lib/console/model/call-ending';
import { faithfulness } from '../src/lib/console/model/faithfulness';
import { sourceDoubts } from '../src/lib/console/model/source-doubts';
import { summaryLength } from '../src/lib/console/model/summary-length';
import { modelChange } from '../src/lib/console/model/model-change';
import { modelThroughput } from '../src/lib/console/model/model-throughput';
import { cost } from '../src/lib/console/model/cost';
import { completeModelRule, ruleEvents } from '../src/lib/charts/d3/model-rule';
import { failureRuleRows, failureRules } from '../src/lib/console/failure-rules';
import { settingsRules } from '../src/lib/console/settings-moved';
import { BAND_UNREAD } from '../src/lib/console/band';
import { consoleConfig, summarizeConfig } from '../src/lib/server/config';
import { buildLedger, buildRows, serveToPage } from './support/ledger-lifecycle';
import type { SliceResult, Row } from '../src/lib/data/ledger';

function recorded(name: string): Row[] {
	const answer = JSON.parse(readFileSync(resolve('..', 'tests', 'fixtures', 'console', 'model', `${name}.json`), 'utf8')) as SliceResult;
	expect(answer.state).toBe('ok');
	return answer.rows;
}
const panelIds = ['model-cards', 'model-throughput', 'call-ending', 'refusing-rule', 'doubt-reasons', 'faithfulness',
	'source-doubts', 'write-cost', 'score-cost', 'summary-length', 'model-change'];

test('sparse rules retain every dated fact without moving a boundary onto another measured day', () => {
	const full = completeModelRule({ changes: [
		{ date: '2030-06-12', kind: 'settings', words: 'The prompt changed.' },
		{ date: '2030-06-13', kind: 'checker', words: 'The checker changed.' },
		{ date: '2030-06-14', kind: 'settings', words: 'The runtime changed.' }
	], note: null }, ['2030-06-11', '2030-06-14']);
	if ('declined' in full) throw new Error('A recorded rule was declined.');
	expect(full.changes.map((change) => change.date)).toEqual(['2030-06-14']);
	expect(full.note).toContain('2030-06-12');
	expect(full.note).toContain('2030-06-13');
	expect(ruleEvents(full, ['2030-06-11', '2030-06-14']).lines[1]?.[0]?.value).toBe('The runtime changed.');
});

test('source attribution takes the later URL score and refuses unknown small shares instead of drawing zero', () => {
	const scores: Row[] = [
		{ date: '2030-06-12', url_key: 'same', band: 'high', unsupported_numbers: 0, hedge_dropped: false, evidential_density: 0.1, speculative_density: 0.1 },
		{ date: '2030-06-14', url_key: 'same', band: 'low', unsupported_numbers: 1, hedge_dropped: true, evidential_density: 0.004, speculative_density: 0.009 },
		{ date: '2030-06-14', url_key: 'orphan', band: 'low', unsupported_numbers: 0, hedge_dropped: false, evidential_density: null, speculative_density: null }
	];
	const result = sourceDoubts(scores, [{ url_key: 'same', source_id: 'matching-source' }],
		{ start: '2030-06-01', end: '2030-06-14', days: 14 }, { limit: 10, minForShare: 5 });
	expect(result.rows).toHaveLength(1);
	expect(result.rows[0]).toMatchObject({ sourceId: 'matching-source', summaries: 1, doubted: 1, sharePct: null, evidential: 4, speculative: 9 });
	expect(result.unattributed).toBe(1);
	expect(result.geometry?.rows[0].refused).toContain('Too few');
});

test('model change compares the newest dated set difference and independent date populations', () => {
	const score = (date: string, model_id: string): Row => ({
		date, model_id, summary_words: 100, source_words_before_cap: 500, source_words: 500,
		extractiveness: null, verbatim_run: null, band: 'high', unsupported_numbers: 0, hedge_dropped: false
	});
	const result = modelChange([
		score('2030-06-10', 'a'), score('2030-06-10', 'b'), score('2030-06-12', 'a'),
		score('2030-06-14', 'c')
	], [{ date: '2030-06-11', summarize_ms: 1000 }, { date: '2030-06-15', summarize_ms: 3000 }],
	summarizeConfig().bands, 1);
	expect(result?.at).toBe('2030-06-14');
	expect(result?.before.model).toBe('a');
	expect(result?.after.model).toBe('c');
	expect(result?.measures.find((measure) => measure.label === 'Time to write one')).toMatchObject({ before: 1, after: 3 });
	expect(result?.measures.find((measure) => measure.label === 'Copied, not rewritten')).toMatchObject({ before: null, after: null });
});

test('recorded native slices drive all eligible model reducers without broadening cells', () => {
	const endingRows = recorded('callEndingQuery');
	const ending = callEnding(endingRows);
	const cells = endingRows.flatMap((r) => [r.summary_finish_reason, r.label_finish_reason]).filter((v) => v !== null && v !== '');
	expect(ending.calls).toBe(cells.length);
	expect(ending.length).toBe(cells.filter((v) => v === 'length').length);
	expect(ending.series[0].token).toBe('--chart-4');
	expect(ending.series.reduce((total, s) => total + s.points.reduce((n, p) => n + (p.value ?? 0), 0), 0)).toBe(cells.length);
	const score = faithfulness(recorded('faithfulnessQuery'), { high: 80, low: 50 }, { step: 5, floorMax: 75 });
	expect(score.days.length).toBeGreaterThan(0);
	for (const day of score.days) {
		expect(day.matchLow).toBeLessThanOrEqual(day.matchMid!);
		expect(day.matchHigh).toBeGreaterThanOrEqual(day.matchMid!);
	}
	expect(cost(recorded('writeCostQuery'), 'summarize_ms').times?.n).toBeGreaterThan(0);
	expect(cost(recorded('scoreCostQuery'), 'score_ms').untimed).toBeGreaterThanOrEqual(0);
	const lengths = summaryLength(recorded('summaryLengthQuery'), summarizeConfig().bands);
	expect(lengths.length).toBeGreaterThan(0);
	expect(new Set(lengths.map((r) => r.runId)).size).toBe(lengths.length);
	expect(modelThroughput(recorded('modelThroughputQuery'), { start: '2026-08-01', end: '2026-08-20' }).length).toBeGreaterThan(0);
	const rules = failureRuleRows(recorded('failedRuleQuery'));
	expect(rules.some((row) => row.code === null)).toBe(true);
	expect(failureRules(rules, { start: '2026-08-01', end: '2026-08-20' }, 'summarize').failed).toBeGreaterThanOrEqual(0);
	const sources = sourceDoubts(recorded('sourceDoubtsQuery'), [], { start: '2026-08-01', end: '2026-08-20', days: 20 }, { limit: 10, minForShare: 1 });
	expect(sources.unattributed).toBeGreaterThan(0);
	expect(sources.rows).toEqual([]);
	expect(sources.share).toBeNull();
	expect(modelChange(recorded('modelChangeQuery'), recorded('modelChangeItemsQuery'), summarizeConfig().bands, 1)).toBeNull();
});

test('the score-only checker rule and every-change rule retain distinct dated meanings', () => {
	const shell = { ...BAND_UNREAD,
		settingsMoved: { compared_from: '2026-08-01', changes: [] },
		checkerMoved: { compared_from: '2026-08-01', changes: [
			{ date: '2026-08-23', score_moved: false }, { date: '2026-08-24', score_moved: false },
			{ date: '2026-08-26', score_moved: true }, { date: '2026-08-29', score_moved: true },
			{ date: '2026-09-24', score_moved: false }
		] }
	};
	const window = { from: '2026-08-01', to: '2026-09-30' };
	const score = settingsRules(shell, window, 'score');
	const every = settingsRules(shell, window, 'every');
	if ('declined' in score || 'declined' in every) throw new Error('Recorded rules were declined.');
	expect(score.changes.map((c) => c.date)).toEqual(['2026-08-26', '2026-08-29']);
	expect(every.changes.map((c) => c.date)).toEqual(['2026-08-23', '2026-08-24', '2026-08-26', '2026-08-29', '2026-09-24']);
});

test('the integrated Summaries route reads the native record and keeps all panels in declared order', async ({ page }) => {
	await page.goto('/console/model/');
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
			days: [{ ago: 2, state: 'lost', setAside: 2 }, { ago: 0, state: 'empty' }] });
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
