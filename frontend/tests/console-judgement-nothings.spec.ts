/** Do the two build-time Judgement panels distinguish empty evidence from absent evidence? */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { renderConfigured as render } from './support/server-render';
import { serverCompiler, type Rewrite } from './support/server-render';
import { judgeNothings, type Nothing, type PanelReading } from './support/panel-gates';

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

for (const [id, name] of PANELS) {
	test(`${id}: empty and absent real inputs say different things`, async ({}, testInfo) => {
		const compiled = serverCompiler(testInfo.outputPath('components'));
		const lib = (file: string) => pathToFileURL(join(FRONTEND, 'src', 'lib', file)).href;
		const rewrite: Rewrite[] = [
			'charts/frame', 'charts/readout', 'charts/viewport',
			'charts/series', 'console/merged-stories',
			'console/span-words', 'console/holdout', 'format'
		].map((file) => [`$lib/${file}`, lib(`${file}.ts`)] as const);
		for (const child of ['Panel', 'ChartReadout']) {
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
