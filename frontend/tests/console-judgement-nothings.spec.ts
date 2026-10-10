/** Do the six build-time panels distinguish empty evidence from absent evidence? */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { serverCompiler, type Rewrite } from './support/server-render';
import { judgeNothings, type Nothing, type PanelReading } from './support/panel-gates';
import { BUILD_TIME } from './support/panel-drivers/judgement';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PANELS = [
	['merged-stories', 'MergedStoriesPanel'],
	['merge-line', 'MergeLinePlot'],
	['judge-agreement', 'JudgeAgreement'],
	['record-gates', 'RecordGates'],
	['verdict-split', 'VerdictSplit'],
	['holdout-margin', 'HoldoutMargin']
] as const;

function words(html: string): string {
	return html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ')
		.replace(/&(?:#39|apos);/g, "'").replace(/&quot;/g, '"')
		.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
		.replace(/\s+/g, ' ').trim();
}

for (const [id, name] of PANELS) {
	test(`${id}: empty and absent real inputs say different things`, async ({}, testInfo) => {
		const compiled = serverCompiler(testInfo.outputPath('components'));
		const lib = (file: string) => pathToFileURL(join(FRONTEND, 'src', 'lib', file)).href;
		const rewrite: Rewrite[] = [
			'charts/frame', 'charts/readout', 'charts/viewport', 'charts/indexed-runs',
			'charts/series', 'charts/targetbar', 'console/merge-line',
			'console/span-words', 'console/verdict-split', 'console/holdout', 'format'
		].map((file) => [`$lib/${file}`, lib(`${file}.ts`)] as const);
		for (const child of ['Panel', 'ChartReadout', 'TargetBar']) {
			const module = await compiled(`src/lib/components/${child}.svelte`, child, [
				...rewrite, ['../charts/readout', lib('charts/readout.ts')]
			]);
			rewrite.push([`$lib/components/${child}.svelte`, pathToFileURL(module).href]);
		}
		const module = await compiled(`src/routes/console/judgement/${name}.svelte`, name, rewrite);
		const component = (await import(pathToFileURL(module).href)).default;
		const appearance = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'appearance.json'), 'utf8'));
		const similarity = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'idhazh.json'), 'utf8')).assemble.same_story;
		const tuning = similarity.adaptive_dedup_threshold;
		const common = {
			viewport: { start: '2030-06-01', end: '2030-06-30' },
			height: appearance.console.chart_height, width: appearance.console.chart_width,
			tickDensity: appearance.chart.tick_density, readoutMaxShare: appearance.chart.readout_max_share
		};
		const inputs: Record<string, { empty: Record<string, unknown>; absent: Record<string, unknown> }> = {
			'merged-stories': { empty: { days: [] }, absent: { days: null } },
			'merge-line': {
				empty: { days: [], knobs: tuning, builtWith: similarity.floor_min, markedApart: null },
				absent: { days: null, knobs: tuning, builtWith: similarity.floor_min, markedApart: null }
			},
			'judge-agreement': {
				empty: { days: [], limits: { disagreementMax: tuning.disagreement_max, unclearMax: tuning.unclear_max }, attemptsFloor: appearance.console.min_attempts_for_rate },
				absent: { days: null, limits: { disagreementMax: tuning.disagreement_max, unclearMax: tuning.unclear_max }, attemptsFloor: appearance.console.min_attempts_for_rate }
			},
			'record-gates': {
				empty: { days: [], dates: [], gates: { minimumNegatives: tuning.minimum_negatives, minimumDays: tuning.minimum_days, minimumAboveLine: tuning.minimum_above_line } },
				absent: { days: null, dates: [], gates: { minimumNegatives: tuning.minimum_negatives, minimumDays: tuning.minimum_days, minimumAboveLine: tuning.minimum_above_line } }
			},
			'verdict-split': {
				empty: { record: { bandLow: tuning.band_low, bandHigh: tuning.band_high, binWidth: tuning.bin_width ?? 0.001, daysCounted: 0, slots: [] }, applied: similarity.floor_min, discardShare: tuning.discard_share, axisMultiple: appearance.console.precision_axis_multiple, figures: { inBand: 0, judged: 0, usable: 0 } },
				absent: { record: null, applied: similarity.floor_min, discardShare: tuning.discard_share, axisMultiple: appearance.console.precision_axis_multiple, figures: { inBand: null, judged: null, usable: null } }
			},
			'holdout-margin': {
				empty: { marks: [], agreedScores: [], skipped: [], marked: 0, applied: similarity.floor_min, maxDownStep: tuning.max_down_bins * (tuning.bin_width ?? 0.001), fitted: false, weights: { cosineWeight: tuning.cosine_weight ?? 1, fittedOn: null }, scored: null },
				absent: { marks: null, agreedScores: null, skipped: [], marked: 0, applied: similarity.floor_min, maxDownStep: tuning.max_down_bins * (tuning.bin_width ?? 0.001), fitted: false, weights: { cosineWeight: tuning.cosine_weight ?? 1, fittedOn: null }, scored: null }
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
			expect(markup.match(/data-comparison=/g)).toHaveLength(1);
			expect(markup).toMatch(/data-comparison="[^"]+ against [^"]+"/);
			expect(markup).toMatch(/data-readout-(?:none|records|columns)=/);
		}
		if (id === 'verdict-split') {
			expect(empty.match(/data-verdict-cell=/g)).toHaveLength(4);
			expect(empty.match(/data-verdict-figure=/g)).toHaveLength(3);
			expect(empty).toContain('Eligible to merge');
			expect(absent).not.toContain('data-verdict-cell=');
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

test('every judged build-time panel has a component-state check', () => {
	expect(BUILD_TIME).toEqual(PANELS.map(([id]) => id));
	const config = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'console', 'judgement.json'), 'utf8'));
	expect(config.judged).toEqual(BUILD_TIME);
	expect(config.panel_groups).toEqual([{ id: 'judgement', title: '', panels: BUILD_TIME }]);
});
