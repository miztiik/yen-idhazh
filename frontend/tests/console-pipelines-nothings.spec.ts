/** Private build-time panels distinguish a measured quiet day from no source. */
import { expect, test } from './support/door-page';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { serverCompiler, type Rewrite } from './support/server-render';
import { BUILD_TIME } from './support/panel-drivers/pipelines';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DAY = { date: '2030-06-01', reached: 0, asked: 0, drafted: 0, published: 0, items: 0, plannerMinutes: null, minutesPerChart: null };
const PANELS = [
	['at-a-glance', 'AtAGlance'], ['run-health', 'RunHealth'], ['site-cost-per-item', 'SiteCostPerItem'],
	['chart-drawing', 'ChartDrawing'], ['extraction', 'Extraction']
] as const;

function words(html: string) {
	return html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

for (const [id, name] of PANELS) {
	test(`${id}: the real source renders quiet and absent inputs differently`, async ({}, info) => {
		const compiled = serverCompiler(info.outputPath('components'));
		const lib = (file: string) => pathToFileURL(join(FRONTEND, 'src', 'lib', `${file}.ts`)).href;
		const rewrite: Rewrite[] = [
			'charts/frame', 'charts/readout', 'charts/viewport', 'charts/indexed-runs', 'charts/series', 'charts/glance',
			'charts/theme', 'charts/run-yield', 'charts/day-slots', 'charts/d3/dateSeries', 'charts/d3/empty',
			'charts/d3/model-rule', 'charts/d3/flow', 'charts/d3/rankedList',
			'console/daily-figures', 'console/run-square', 'console/span-words', 'format'
		].map((file) => [`$lib/${file}`, lib(file)] as const);
		for (const pure of ['at-a-glance', 'site-cost-per-item', 'chart-drawing', 'extraction']) {
			rewrite.push([`./${pure}`, lib(`console/pipelines/${pure}`)]);
		}
		for (const [file, child] of [
			['src/lib/components/Panel.svelte', 'Panel'],
			['src/lib/components/ChartReadout.svelte', 'ChartReadout'],
			['src/lib/components/KpiCard.svelte', 'KpiCard'],
			['src/lib/components/TargetBar.svelte', 'TargetBar'],
			['src/lib/components/Sparkline.svelte', 'Sparkline'],
			['src/lib/components/Reserved.svelte', 'Reserved'],
			['src/lib/components/RankedList.svelte', 'RankedList'],
			['src/lib/components/RunSquares.svelte', 'RunSquares'],
			['src/lib/components/RunYield.svelte', 'RunYield'],
			['src/lib/charts/d3/EmptyState.svelte', 'EmptyState'],
			['src/lib/charts/d3/DateSeries.svelte', 'DateSeries'],
			['src/lib/charts/d3/Flow.svelte', 'Flow'],
			['src/routes/console/RunHealthPanel.svelte', 'RunHealthPanel']
		] as const) {
			const module = await compiled(file, child, [
				...rewrite, ['./EmptyState.svelte', pathToFileURL(join(info.outputPath('components'), 'EmptyState.server.mjs')).href],
				['./ChartReadout.svelte', pathToFileURL(join(info.outputPath('components'), 'ChartReadout.server.mjs')).href]
			]);
			rewrite.push([`$lib/${file.slice('src/lib/'.length)}`, pathToFileURL(module).href]);
			if (child === 'RunHealthPanel') rewrite.push(['../../../routes/console/RunHealthPanel.svelte', pathToFileURL(module).href]);
		}
		const module = await compiled(`src/lib/console/pipelines/${name}.svelte`, name, rewrite);
		const component = (await import(pathToFileURL(module).href)).default;
		const appearance = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'appearance.json'), 'utf8'));
		const common = {
			knobs: appearance.console, chart: appearance.chart, window: { start: DAY.date, end: DAY.date },
			viewport: { start: DAY.date, end: DAY.date },
			windowDays: 1, days: 1, rule: { declined: 'one distribution, not a date axis' },
			floorPct: 70, height: appearance.console.chart_height, width: appearance.console.chart_width,
			tickDensity: appearance.chart.tick_density, readoutMaxShare: appearance.chart.readout_max_share
		};
		const inputs: Record<string, { quiet: Record<string, unknown>; absent: Record<string, unknown> }> = {
			'at-a-glance': { quiet: { days: [DAY] }, absent: { days: [] } },
			'run-health': {
				quiet: { yieldDays: [{ date: DAY.date, itemsPlanned: 0, itemsPublished: 0, itemsFailed: 0 }], grid: [{ date: DAY.date, squares: [] }] },
				absent: { yieldDays: [], grid: [] }
			},
			'site-cost-per-item': {
				quiet: { manifests: [{ date: DAY.date, records: [], siteBytes: null }], publishedItems: { [DAY.date]: 0 }, sizeBytes: null },
				absent: { manifests: [], publishedItems: {}, sizeBytes: null }
			},
			'chart-drawing': { quiet: { days: [DAY] }, absent: { days: [] } },
			extraction: {
				quiet: { rows: [], evaluations: [], nativeState: 'quiet', evaluationsState: 'quiet', yieldDays: [{ date: DAY.date, chartable: 0, charted: 0 }],
					publishedShare: { measuredDays: 1, unused: 0, chartablePublished: 0, unusedPct: null } },
				absent: { rows: [], evaluations: null, nativeState: 'missing', evaluationsState: 'missing', yieldDays: [],
					publishedShare: { measuredDays: 0, unused: 0, chartablePublished: 0, unusedPct: null } }
			}
		};
		const quiet = render(component, { props: { ...common, ...inputs[id].quiet } }).body;
		const absent = render(component, { props: { ...common, ...inputs[id].absent } }).body;
		expect(words(quiet)).not.toBe(words(absent));
		expect(words(absent)).toContain('unavailable');
		expect(absent).toContain('data-comparison=');
		expect(quiet).not.toContain('NaN');
		expect(absent).not.toContain('NaN');
	});
}

test('every private build-time panel has a real source-render check', () => {
	expect(BUILD_TIME).toEqual(PANELS.map(([id]) => id));
});
