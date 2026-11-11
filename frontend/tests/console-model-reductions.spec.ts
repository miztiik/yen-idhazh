/** Native Summaries reductions and rule boundaries over recorded slices; no browser or site build. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { callEnding } from '../src/lib/console/model/call-ending';
import { faithfulness } from './support/number-format';
import { sourceDoubts } from '../src/lib/console/model/source-doubts';
import { summaryLength } from '../src/lib/console/model/summary-length';
import { modelThroughput } from '../src/lib/console/model/model-throughput';
import { modelRuleFor } from '../src/lib/console/model/panels';
import { cost } from '../src/lib/console/model/cost';
import { completeModelRule, ruleEvents } from '../src/lib/charts/d3/model-rule';
import { failureRuleRows, failureRules } from '../src/lib/console/failure-rules';
import { settingsRules } from '../src/lib/console/settings-moved';
import { BAND_UNREAD } from '../src/lib/console/band';
import { summarizeConfig } from '../src/lib/server/config';
import type { SliceResult, Row } from '../src/lib/data/ledger';

function recorded(name: string): Row[] {
	const answer = JSON.parse(readFileSync(resolve('..', 'tests', 'fixtures', 'console', 'model', `${name}.json`), 'utf8')) as SliceResult;
	expect(answer.state).toBe('ok');
	return answer.rows;
}

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

test('retained metric trends keep model identities and dated setting changes', () => {
	const from = '2030-06-10';
	const to = '2030-06-14';
	const score = (date: string, model_id: string, summary_words: number): Row => ({
		date, run_id: `${date}-1`, model_id, summary_words, source_words_before_cap: 500, compression: 0.2
	});
	const scores = [score(from, 'before-model', 100), score(to, 'after-model', 50)];
	const lengths = summaryLength(scores, summarizeConfig().bands);
	expect(lengths.map(({ model, median }) => ({ model, median }))).toEqual([
		{ model: 'before-model', median: 100 }, { model: 'after-model', median: 50 }
	]);
	const throughput = modelThroughput(scores.map((row) => ({
		...row, input_tokens: 100, cached_tokens: 0, output_tokens: 100, prefill_ms: 1000, decode_ms: 2000
	})), { start: from, end: to });
	expect(throughput.map((day) => ({ date: day.date, read: day.read.median, write: day.write.median }))).toEqual([
		{ date: from, read: 100, write: 50 }, { date: to, read: 100, write: 50 }
	]);
	const shell = { ...BAND_UNREAD,
		settingsMoved: { compared_from: from, changes: [{ date: to, inputs: ['model_sha256'] }] },
		checkerMoved: { compared_from: from, changes: [] }
	};
	for (const [id, dates] of [
		['model-throughput', throughput.map((day) => day.date)],
		['summary-length', lengths.map((run) => run.date)]
	] as const) {
		const rule = completeModelRule(modelRuleFor(id, shell, { from, to, days: 5, asked: 7 }), dates);
		expect(rule).toMatchObject({
			changes: [{ date: to, kind: 'settings', words: 'the weights changed on this day' }], note: null
		});
	}
});

test('the faithfulness scale stays bounded, never hides a measurement and keeps missing readings null', () => {
	const reduce = (hhem: number | null) => faithfulness([{ date: '2030-06-14', hhem }],
		{ high: 80, low: 50 }, { step: 5, floorMax: 75 });
	const high = reduce(0.97);
	expect(high.floor).toBe(75);
	expect(high.rules.map((rule) => rule.at)).toEqual([80]);
	expect(high.series[0].points[0]).toMatchObject({ value: 97, spread: { low: 97, high: 97 } });
	const low = reduce(0.42);
	expect(low.floor).toBe(40);
	expect(low.floor).toBeLessThanOrEqual(low.days[0].matchLow!);
	expect(low.rules.map((rule) => rule.at)).toEqual([80, 50]);
	const missing = reduce(null);
	expect(missing.floor).toBe(75);
	expect(missing.days[0].matched).toBe(0);
	expect(missing.series[0].points).toEqual([{ date: '2030-06-14', value: null }]);
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
	expect(settingsRules(shell, { from: '2026-08-20', to: '2026-08-20' }, 'none', 'this one day')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written inside this one day.'
	});
});
