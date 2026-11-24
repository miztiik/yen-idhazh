import { expect, test } from '@playwright/test';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { frame } from '../src/lib/charts/frame';
import { binnedDistribution } from '../src/lib/charts/d3/distribution';
import { scoreIntervals } from '../src/lib/charts/d3/scoreIntervals';
import { precisionRecall } from '../src/lib/charts/d3/precisionRecall';
import { judgeCutoffSweep, judgeZoneMatrix } from '../src/lib/console/judge-cutoff-evidence';
import { drawCoverageByOutcome, drawOf, sliceParts } from '../src/lib/console/judge-draw';
import { judgeCanaryDays } from '../src/lib/console/judge-canaries';
import { latestJudgeReadings } from '../src/lib/console/judge-observations';
import { countBandOutcomes, judgeEntropy, judgePairDays, judgeScoreBands } from '../src/lib/console/judge-pair-evidence';
import { judgePool, savedPoolBaseline } from '../src/lib/console/judge-score-pool';
import { judgeObservationRules } from '../src/lib/console/route-console';
import type { Row } from '../src/lib/data/slice-shapes';
import { judgeCanaryTimeline } from '../src/routes/console/judgement/judge-canary-timeline';
import { numberFormat } from './support/number-format';
import { renderConfigured, serverCompiler, type Rewrite } from './support/server-render';

const now = { date: '2026-11-21', run_id: '2026-11-22-101', attempt: 2 };
const prior = { date: '2026-11-20', run_id: '2026-11-21-99', attempt: 1 };
const noReturns = { yes: 0, no: 0, unclear: 0, split: 0, refused: 0 };

function pair(pair_key: string, similarity_score: number, verdict: string | null, verdict_swapped = verdict): Row {
	return { ...now, pair_key, similarity_score, verdict, verdict_swapped, lower_threshold_in_force: 0.7, upper_threshold_in_force: 0.93 };
}

test('draws exact intervals and proportions without confusing a new bound with the one used', () => {
	const { slices, bounds, decided } = drawOf({
		...now, sample_status: 'measured', pairs_drawn: 10, pairs_returned: 8,
		lower_threshold_before: 0.7, upper_threshold_before: 0.93, lower_threshold_after: 0.68, upper_threshold_after: 0.93,
		slice_outcomes: JSON.stringify({ slices: [{ ...noReturns, low: 0.84, high: 0.87, drawn: 10, yes: 5, no: 2, split: 1 }] })
	});
	expect(slices).toHaveLength(1);
	expect(sliceParts(slices![0])).toEqual({ yes: 5, no: 2, split: 1, missing: 2, unclear: 0, refused: 0 });
	const box = frame(440, 220);
	const drawing = scoreIntervals([
		{ date: '2026-11-19', used: [null, null], decided: [], slices: [] },
		{ date: prior.date, used: [0.7, 0.93], decided: [], slices: [] },
		{ date: now.date, used: [bounds!.lower, bounds!.upper], decided: [decided!.lower, decided!.upper],
			slices: [{ low: -1, high: 0.7, parts: [0, 4, 0, 0] }, { low: 0.84, high: 0.87, parts: [5, 2, 1, 2] }] }
	], box, -1, 1, 4, { focus: 0.68, share: 0.2 })!;
	const [tail, mark] = drawing.columns[2].marks;
	const widths = mark.segments.map(({ start, end }) => end - start);
	expect(widths[0] / widths.reduce((a, b) => a + b)).toBeCloseTo(0.5);
	expect(mark.y1).toBe(drawing.axis.scale(0.87));
	expect(tail.y0).toBe(box.bottom);
	expect(tail.y).toBeCloseTo(drawing.axis.scale(-0.15));
	expect(drawing.axis.scale(0.68)).toBeCloseTo(box.bottom - 0.2 * box.innerHeight);
	expect(drawing.axis.scale(1)).toBe(box.top);
	expect(drawing.columns[0].marks).toEqual([]);
	expect(drawing.guides[0].at(-1)).toMatchObject({ y: drawing.axis.scale(0.7), decision: drawing.axis.scale(0.68) });
});

test('daily coverage uses recorded outcomes, and never paints a refusal or unknown return as MAYBE', () => {
	const summary = { pairs_drawn: 10, pairs_returned: 8, sample_tp: 2, sample_fp: 1, sample_fn: 1, sample_tn: 0 };
	const draw = { ...summary, sample_status: 'measured', slice_outcomes: JSON.stringify({ slices: [
		{ low: 0.7, high: 0.8, drawn: 10, yes: 3, no: 1, split: 1, unclear: 1, refused: 2 }
	] }) };
	expect(drawCoverageByOutcome(summary, draw)).toEqual({ yes: 3, no: 1, maybe: 2, refused: 2, missing: 2, unclassified: 0 });
	expect(drawCoverageByOutcome(summary, null)).toEqual({ yes: 3, no: 1, maybe: null, refused: null, missing: 2, unclassified: 4 });
	expect(drawCoverageByOutcome({ ...summary, pairs_returned: null }, null)).toBeNull();
});

const setVersion = (version: string) => JSON.stringify({ 'judges/content-similarity-canaries.json': version });
const canaryReference = {
	date: '2026-11-22', run_id: '2026-11-23-1', attempt: 2,
	config_versions: setVersion('2026-11-19'),
	canary_expectations: '{"same-1":"YES","same-2":"YES","unclear-1":"UNCLEAR","unclear-2":"UNCLEAR","different-1":"NO","different-2":"NO"}',
	canary_answers: '{"same-1":["YES","YES"],"same-2":["YES","YES"],"unclear-1":["NO","NO"],"unclear-2":["NO","NO"],"different-1":["NO","NO"],"different-2":["NO","NO"]}',
	canary_kappa: 0.5, canary_kappa_pairs: 6
};

test('canary lines use fixed endpoints, keep incomplete days visible, and never bridge a gap or set change', () => {
	const days = ['20', '21', '22', '23', '24', '25', '26', '27'].map((day) => `2026-11-${day}`);
	const complete = { canary_expectations: '{"same":"YES"}', canary_answers: '{"same":["YES","YES"]}' };
	const older = { ...complete, config_versions: setVersion('2026-11-18') };
	const recent = { ...complete, config_versions: canaryReference.config_versions };
	const mixed = { ...recent, canary_expectations: '{"a":"YES","b":"YES","c":"YES","d":"YES"}',
		canary_answers: '{"a":["NO","NO"],"b":["UNCLEAR","UNCLEAR"],"c":["YES","YES"],"d":["UNCLEAR","UNCLEAR"]}' };
	const readings = latestJudgeReadings([
		older, older, canaryReference, mixed, { canary_answers: canaryReference.canary_answers },
		{ ...recent, canary_answers: '{"same":[null,"YES"]}' }, recent, { ...recent, config_versions: null }
	].map((cells, index) => ({ ...canaryReference, ...cells, date: days[index],
		canary_expectations: 'canary_expectations' in cells ? cells.canary_expectations : null })));
	const box = frame(520, 108);
	const plot = judgeCanaryTimeline(judgeCanaryDays(days, readings), box, 6);
	const [same, unclear, different] = plot.timelines;
	expect(same.columns[2].point).toEqual({ y: box.top, incomplete: false });
	expect(unclear.columns[2].point).toEqual({ y: plot.stripBottom, incomplete: false });
	expect(different.columns[2].point).toEqual({ y: box.top, incomplete: false });
	expect([same, unclear, different].map(({ columns }) => columns[2].segments.map(({ band }) => band)))
		.toEqual([['YES'], ['NO'], ['NO']]);
	const segments = same.columns[3].segments;
	const height = box.bottom - plot.blockTop;
	expect(segments.map(({ band, height: part }) => [band, part / height]))
		.toEqual([['YES', 0.25], ['UNCLEAR', 0.5], ['NO', 0.25]]);
	expect(same.columns[3].point?.y).toBeCloseTo(plot.stripBottom - (plot.stripBottom - box.top) * 0.25);
	expect(same.columns[4]).toMatchObject({ point: null, segments: [] });
	expect(same.columns[5]).toMatchObject({ point: { y: plot.stripBottom, incomplete: true }, segments: [{ band: 'invalid' }] });
	expect(same.columns[7].point?.y).toBe(box.top);
	expect(same.path.match(/M/g)).toHaveLength(2);
	expect(same.path.match(/L/g)).toHaveLength(2);
	expect(plot.changes).toEqual([{ date: days[2], x: (same.columns[1].x + same.columns[2].x) / 2 }]);
});

test('the Canaries panel keeps three timelines and exact selected-day answers without a table', async ({}, testInfo) => {
	const compile = serverCompiler(testInfo.outputPath('canary-chart'));
	const href = (file: string) => pathToFileURL(resolve(file)).href;
	const rewrites: Rewrite[] = ['charts/frame', 'charts/label-context', 'charts/readout', 'charts/readout-view',
		'console/judge-canaries', 'format', 'number-format'].map((file) => [`$lib/${file}`, href(`src/lib/${file}.ts`)]);
	for (const file of ['components/Panel', 'components/ChartReadout']) {
		const name = file.split('/').at(-1)!;
		rewrites.push([`$lib/${file}.svelte`, href(await compile(`src/lib/${file}.svelte`, name, rewrites))]);
	}
	const route = 'src/routes/console/judgement';
	const details = await compile(`${route}/JudgeCanaryDetails.svelte`, 'JudgeCanaryDetails', rewrites);
	const module = await compile(`${route}/JudgeCanaryChart.svelte`, 'JudgeCanaryChart', [
		...rewrites, ['./JudgeCanaryDetails.svelte', href(details)], ['./judge-trial-style', href(`${route}/judge-trial-style.ts`)],
		['./judge-canary-timeline', href(`${route}/judge-canary-timeline.ts`)]
	]);
	const { default: chart } = await import(href(module));
	const plot = (rows: Row[]) => renderConfigured(chart, { props: {
		selected: canaryReference.date, calendar: [canaryReference.date], readings: latestJudgeReadings(rows),
		noteFor: () => 'Unavailable', knobs: { chart_width: 520 },
		chart: { number_format: numberFormat, readout_max_share: 1, sparkline_height_px: 36, tick_density: 6 }
	} }).body.replace(/<!--[\s\S]*?-->/g, '');
	const measured = plot([canaryReference, { ...canaryReference, attempt: 1, canary_expectations: '{"earlier":"YES"}' }]);
	expect(measured.match(/data-chart-name="judge-canaries-(yes|unclear|no)"/g)).toEqual([
		'data-chart-name="judge-canaries-yes"', 'data-chart-name="judge-canaries-unclear"', 'data-chart-name="judge-canaries-no"'
	]);
	expect(measured.match(/\d\/2 matched/g)).toEqual(['2/2 matched', '0/2 matched', '2/2 matched']);
	expect(measured).toMatch(/Expected: UNCLEAR\s+\u00b7\s*Original: NO\s+\u00b7 Reversed: NO/);
	expect(measured).not.toContain('<table');
	expect(plot([{ ...canaryReference, canary_expectations: null }])).toContain('The observed answers are not graded.');
	expect(plot([])).not.toContain('data-chart-type="canaryTimeline"');
});

test('an exact attempt is counted once, with threshold-edge zones and binary cutoff ties', () => {
	const rows = [
		pair('a', 0.93, 'YES'), pair('b', 0.93, 'NO'), pair('c', 0.7, 'YES', 'NO'),
		pair('d', 0.69, 'UNCLEAR'), pair('e', 0.68, null), pair('f', 0.5, 'YES')
	];
	const readings = latestJudgeReadings([{ ...now, pairs_returned: rows.length }]);
	const days = judgePairDays([{ ...rows[0], attempt: 1 }, ...rows], readings);
	const day = days.get(now.date);
	expect(day?.state).toBe('ready');
	if (day?.state !== 'ready' || day.bounds === null) throw new Error('Expected the complete exact-attempt draw.');
	expect(judgeZoneMatrix(day.pairs, day.bounds)).toEqual({
		matrix: { yes: { yes: 1, maybe: 0, no: 1 }, maybe: { yes: 0, maybe: 1, no: 1 }, no: { yes: 1, maybe: 0, no: 0 } },
		refused: 1, unclear: 1, split: 1
	});
	const sweep = judgeCutoffSweep(day.pairs);
	expect(sweep.points.map(({ cutoff }) => cutoff)).toEqual([0.93, 0.5]);
	expect(sweep.atCutoff(0.93)).toMatchObject({ tp: 1, fp: 1, fn: 1, tn: 0, precision: 0.5, recall: 0.5 });
	expect(sweep.atCutoff(1)).toMatchObject({ precision: null, recall: 0 });
	const plot = precisionRecall(sweep.points, [{ ...sweep.atCutoff(0.7), shape: 'lower' }], frame(400, 200), 4);
	expect(plot?.markers[0]).toMatchObject({ shape: 'lower', x: plot?.x.scale(0.5), y: plot?.y.scale(0.5) });
	expect(judgePairDays([...rows, rows[0]], readings).get(now.date)).toEqual({ state: 'invalid' });
	expect(judgePairDays(rows.slice(1), readings).get(now.date)).toEqual({ state: 'incomplete' });
});

test('entropy counts MAYBE as a class and does not turn absent or refused evidence into consensus', () => {
	const bands = judgeScoreBands(10);
	const [underflow, first, second] = countBandOutcomes([
		{ score: -0.02, outcome: 'refused' }, { score: 0, outcome: 'split' },
		{ score: 0.1, outcome: 'yes' }, { score: 0.1, outcome: 'no' }, { score: 0.2, outcome: 'unclear' }
	], bands);
	expect(judgeEntropy(underflow)).toBeNull();
	expect(judgeEntropy(first)).toBe(0);
	expect(judgeEntropy(second)).toBeCloseTo(1, 12);
	expect(judgeEntropy({ ...noReturns, yes: 2, no: 2, unclear: 1, split: 1, refused: 30 })).toBeCloseTo(Math.log2(3), 12);
});

test('full-pool geometry preserves saved edges and verifies the exact reference histogram', async () => {
	const stamp = 'a'.repeat(64);
	const current = judgePool(JSON.stringify({ stamp, edges: [-1, 0, 0.75, 1], counts: [1000, 49, 1] }))!;
	const old = JSON.stringify({ stamp, edges: current.edges, counts: [800, 12, 3] });
	const digest = createHash('sha256').update(old).digest('hex');
	const tags = JSON.stringify({ required_days: 1, sources: [{ date: prior.date, run_id: prior.run_id, histogram_sha256: digest }] });
	const reference = await savedPoolBaseline(current, tags, [
		{ ...prior, run_id: now.run_id, score_pool_histogram: old },
		{ ...prior, score_pool_histogram: old }
	]);
	expect(reference?.total).toBe(815);
	expect(await savedPoolBaseline(current, tags, [
		{ ...prior, score_pool_histogram: old.replace('800', '801') }
	])).toBeNull();
	const geometry = binnedDistribution(current.edges, current.counts, reference!.counts, {
		frame: frame(400, 200), minValues: 1, valueTicks: 4, number_format: numberFormat
	});
	expect(geometry?.bins.map(({ x0, x1, count, reference }) => [x0, x1, count, reference?.count]))
		.toEqual([[-1, 0, 1000, 800], [0, 0.75, 49, 12], [0.75, 1, 1, 3]]);
	expect(geometry?.bins[0].percent).toBeCloseTo(100 * 1000 / 1050);
	expect(judgePool(old.replace('0.75', '0'))).toBeNull();
});

test('the trial is off without an explicit valid switch and bin count', () => {
	const old = { psi_moderate_min: 0.1, psi_significant_above: 0.25, judge_thin_sample_pairs: 20 };
	expect(judgeObservationRules(old).trialBins).toBeNull();
	expect(judgeObservationRules({ ...old, judge_visual_trial_enabled: 1, judge_visual_trial_score_bins: 8 }).trialBins).toBe(8);
	expect(() => judgeObservationRules({ ...old, judge_visual_trial_enabled: 1 })).toThrow(/score_bins/);
	expect(() => judgeObservationRules({ ...old, judge_visual_trial_context_share: 1 })).toThrow(/context_share/);
});
