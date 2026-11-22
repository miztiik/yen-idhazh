/** Does Judgement distinguish an absent read, a null reading and a real zero? */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { renderConfigured as render } from './support/server-render';
import { serverCompiler, type Rewrite } from './support/server-render';
import { judgeNothings, type Nothing, type PanelReading } from './support/panel-gates';
import {
	DRIFT_STATUS, PROBABILITY_STATUS, SAMPLE_STATUS, judgeCanaries, judgeCoverage, judgeDayAbsence, judgeStatus,
	judgeSlices, psiInterpretation, psiNumber
} from '../src/lib/console/judge-observations';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { frame, MARGIN } from '../src/lib/charts/frame';
import { readoutView } from '../src/lib/charts/readout-view';
import { judgeSliceColumns, judgeSliceEvidence } from '../src/routes/console/judgement/judge-slice-chart';
import { numberFormat } from './support/number-format';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PANELS = [
	['merged-stories', 'MergedStoriesPanel'],
	['holdout-margin', 'HoldoutMargin']
] as const;

function words(html: string): string {
	return html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ')
		.replace(/&(?:#39|apos);/g, "'").replace(/&quot;/g, '"')
		.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
		.replace(/\s+/g, ' ').trim();
}

test('a missing ledger, an unpublished day, a legacy row and no measurement are different', () => {
	const day = '2026-08-20';
	const reach = { state: 'ok', first: '2026-08-01', through: '2026-08-19', lastRows: null, fault: null } as const;
	expect(judgeDayAbsence(day, 'pending', null)).toContain('Loading');
	expect(judgeDayAbsence(day, { state: 'missing', fault: 'not-packed' }, null)).toBe('Not published yet.');
	expect(judgeDayAbsence(day, { state: 'quiet' }, reach)).toBe('Not published yet.');
	expect(judgeDayAbsence('2026-08-18', { state: 'quiet' }, reach)).toBe('Not recorded.');
	expect(judgeStatus(null, DRIFT_STATUS)).toBe('Not recorded.');
	expect(judgeStatus('empty_pool', DRIFT_STATUS)).toContain('eligible score pool was empty');
	expect(judgeStatus('no_reference_fit', PROBABILITY_STATUS)).toContain('No comparable prior fit');
	expect(judgeStatus('no_eligible_pairs', PROBABILITY_STATUS)).toContain('No new agreed pairs');
	expect(judgeStatus('not_filed', SAMPLE_STATUS)).toContain('no verdict batch was filed');
	expect(judgeCoverage({ pairs_drawn: 12, pairs_returned: null }).stack).toBeNull();
	expect(judgeCoverage({ pairs_drawn: 12, pairs_returned: 0, sample_tp: 0, sample_fp: 0, sample_fn: 0, sample_tn: 0 }).stack).toEqual([0, 0, 12]);
});

test('sampled ranges keep exact drawn totals and binary denominators, while a gap has no stack', () => {
	const slices = judgeSlices(JSON.stringify({ slices: [
		{ low: 0.7, high: 0.8, drawn: 8, yes: 2, no: 3, unclear: 1, split: 1, refused: 0 },
		{ low: 0.9, high: 0.92, drawn: 4, yes: 0, no: 0, unclear: 0, split: 0, refused: 0 }
	] }))!;
	const { ranges, readout } = judgeSliceEvidence(slices, numberFormat);
	const plot = judgeSliceColumns(ranges, frame(900, 220), 6, numberFormat)!;
	expect(plot.axis.domain[0]).toBe(0);
	expect(readout.columns).toEqual(['0.7 to 0.8', '0.8 to 0.9', '0.9 to 0.92']);
	expect(plot.columns.map(({ top, total, segments }) => [top, total, segments.length])).toEqual([
		[plot.axis.scale(8), '8', 4], [plot.axis.scale(0), null, 0], [plot.axis.scale(4), '4', 1]
	]);
	const facts = (index: number) => readoutView(readout, index)?.entries.map(({ label, value }) => [label, value]);
	expect(facts(0)).toEqual([
		['Drawn', '8'], ['Agreed YES', '2'], ['Agreed NO', '3'], ['Other returned', '2'],
		['Did not return', '1'], ['YES of agreed', '2 of 5 (40%)']
	]);
	expect(facts(1)).toEqual([['Not drawn', '']]);
	expect(facts(2)).toContainEqual(['Did not return', '4']);
	expect(facts(2)).toContainEqual(['YES of agreed', 'No agreed YES or NO']);
	expect(judgeSliceColumns(ranges, frame(170, 220, MARGIN, { fontSize: 16, leading: 20, tracking: 0 }), 6, numberFormat)).toBeNull();
});

test('both configured PSI guides are Moderate, near-boundary labels preserve the side, and calendar gaps break the line', () => {
	const low = 0.1, high = 0.25;
	expect([0, 0.09999, low, high, 0.25001].map((value) => psiInterpretation(value, low, high))).toEqual([
		'No significant drift', 'No significant drift',
		'Moderate drift (investigation needed)', 'Moderate drift (investigation needed)',
		'Significant drift (retrain or re-calibrate)'
	]);
	for (const value of [0.099999, 0.100001, 0.249999, 0.250001]) {
		expect(psiNumber(value, low, high, numberFormat)).toBe(String(value));
	}
	const plot = dateSeries([{ label: 'PSI', token: '--chart-measure', points: [
		{ date: '2026-08-17', value: null }, { date: '2026-08-18', value: 0 },
		{ date: '2026-08-19', value: null }, { date: '2026-08-20', value: 0.7 }
	] }], {
		frame: frame(360, 210, MARGIN), density: 4, valueTicks: 4, padding: 0.25, number_format: numberFormat,
		rule: { declined: 'Incoming scores do not compare summary settings.' },
		rules: [{ at: low, label: 'lower guide' }, { at: high, label: 'upper guide' }]
	})!;
	expect(plot.axis.domain[0]).toBe(0);
	expect(plot.lines[0].points.map(({ date, alone }) => [date, alone])).toEqual([
		['2026-08-18', true], ['2026-08-20', true]
	]);
	expect(plot.lines[0].points[1].y).toBeLessThan(plot.rules[1].y);
});

test('known-answer states grade only against the recorded key', () => {
	const cells = {
		canary_expectations: '{"a":"YES","b":"YES","c":"NO","d":"UNCLEAR","e":"NO"}',
		canary_answers: '{"a":["YES","YES"],"b":["NO","NO"],"c":["YES","NO"],"d":[null,"YES"]}',
		canary_kappa_pairs: 2
	};
	expect(judgeCanaries(cells).items.map(({ outcome }) => outcome)).toEqual(['Matched', 'Differed', 'Split', 'Refused', 'Missing']);
	expect(judgeCanaries(cells)).toMatchObject({ matches: 1, eligible: 2, kappa: null });
	const legacy = judgeCanaries({ canary_answers: cells.canary_answers });
	expect(legacy.graded).toBe(false);
	expect(legacy.items[0]).toMatchObject({ expected: null, forward: 'YES', swapped: 'YES', outcome: 'Not graded' });
});

for (const [id, name] of PANELS) {
	test(`${id}: empty and absent real inputs say different things`, async ({}, testInfo) => {
		const compiled = serverCompiler(testInfo.outputPath('components'));
		const lib = (file: string) => pathToFileURL(join(FRONTEND, 'src', 'lib', file)).href;
		const rewrite: Rewrite[] = [
			'charts/frame', 'charts/readout', 'charts/viewport',
			'charts/series', 'console/merged-stories',
			'console/span-words', 'console/holdout', 'format'
		].map((file) => [`$lib/${file}`, lib(`${file}.ts`)] as const);
		for (const child of ['Panel', 'ChartReadout', 'WindowCoverage']) {
			const module = await compiled(`src/lib/components/${child}.svelte`, child, [
				...rewrite, ['../charts/readout', lib('charts/readout.ts')]
			]);
			rewrite.push([`$lib/components/${child}.svelte`, pathToFileURL(module).href]);
		}
		const module = await compiled(`src/routes/console/judgement/${name}.svelte`, name, rewrite);
		const component = (await import(pathToFileURL(module).href)).default;
		const appearance = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'appearance.json'), 'utf8'));
		const similarity = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'idhazh.json'), 'utf8')).assemble.same_story;
		const axis = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'console', 'judgement.json'), 'utf8')).knobs;
		const common = {
			viewport: { start: '2030-06-01', end: '2030-06-30' },
			height: appearance.console.chart_height, width: appearance.console.chart_width,
			tickDensity: appearance.chart.tick_density, readoutMaxShare: appearance.chart.readout_max_share
		};
		const marks = {
			line: similarity.floor_min, axisBelow: axis.holdout_axis_below_line, axisAbove: axis.holdout_axis_above_line,
			skipped: [], marked: 0, weights: { cosineWeight: similarity.cosine_weight ?? 1 }
		};
		const inputs: Record<string, { empty: Record<string, unknown>; absent: Record<string, unknown> }> = {
			'merged-stories': { empty: { days: [] }, absent: { days: null } },
			'holdout-margin': {
				empty: { ...marks, marks: [], agreedScores: [] },
				absent: { ...marks, marks: null, agreedScores: null }
			}
		};
		const html = (input: Record<string, unknown>) => render(component, { props: { ...common, ...input } }).body;
		const empty = html(inputs[id].empty);
		const absent = html(inputs[id].absent);
		expect(empty).toContain(`data-console-panel-id="${id}"`);
		expect(absent).toContain('data-empty="missing"');
		expect(absent).not.toContain('data-chart-type=');
		expect(words(empty)).not.toBe(words(absent));
		expect(words(absent)).toContain('unavailable');
		for (const markup of [empty, absent]) {
			expect(markup).toContain('data-panel-question=');
			expect(markup).toContain('data-model-rule="no"');
			expect(markup).toContain(`data-model-rule-name="${id}"`);
			expect(markup.match(/data-comparison=/g)).toHaveLength(1);
			expect(markup).toMatch(/data-comparison="[^"]+ against [^"]+"/);
			expect(markup).toMatch(/data-readout-(?:none|records|columns)=/);
		}
		// Gate 8 reads words and placeholder treatment only; SSR has no rendered ground.
		const reading = (markup: string): PanelReading => ({
			id, nothing: { words: words(markup), ground: null }
		} as PanelReading);
		const readings = { quiet: reading(empty), missing: reading(absent) } as Record<Nothing, PanelReading>;
		expect(judgeNothings(id, readings, ['quiet', 'missing']).pass).toBe(true);
		expect(empty.match(/data-lede(?:\s|=|>)/g)).toHaveLength(1);
		expect(absent.match(/data-lede(?:\s|=|>)/g)).toHaveLength(1);
	});
}
