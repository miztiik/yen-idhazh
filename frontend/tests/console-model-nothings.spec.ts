/** Do the two private Summaries panels distinguish quiet records from absent records? */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { renderConfigured as render } from './support/server-render';
import { serverCompiler, type Rewrite } from './support/server-render';
import { judgeNothings, type Nothing, type PanelReading } from './support/panel-gates';
import type { RecordRead } from '../src/lib/console/recording';

const PANELS = [['model-cards', 'Cards'], ['doubt-reasons', 'Reasons']] as const;
const words = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ')
	.replace(/\s+/g, ' ').trim();

for (const [id, name] of PANELS) {
	test(`${id}: real quiet and absent inputs give different answers`, async ({}, info) => {
		const compiled = serverCompiler(info.outputPath('components'));
		const lib = (file: string) => pathToFileURL(resolve('src', 'lib', `${file}.ts`)).href;
		const rewrite: Rewrite[] = [
			['./cards', lib('console/model/cards')], ['./model-rule', lib('console/model/model-rule')],
			['../model-cards', lib('console/model-cards')], ['../eval-instruments', lib('console/eval-instruments')],
			['../doubt-reasons', lib('console/doubt-reasons')], ['./doubt-reasons', lib('console/model/doubt-reasons')],
			['../span-words', lib('console/span-words')], ['../../format', lib('format')],
			['../../charts/d3/dateSeries', lib('charts/d3/dateSeries')],
			['../../charts/d3/empty', lib('charts/d3/empty')], ['../../charts/frame', lib('charts/frame')],
			['../../charts/label-context', lib('charts/label-context')],
			['../../components/KpiCard.svelte', './KpiCard.server.mjs'],
			['../../components/Sparkline.svelte', './Sparkline.server.mjs'],
			['./Series.svelte', './Series.server.mjs'], ['../../charts/d3/DateSeries.svelte', './DateSeries.server.mjs'],
			['./EmptyState.svelte', './EmptyState.server.mjs'],
			['$lib/components/Reserved.svelte', './Reserved.server.mjs'],
			['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs'],
			['../charts/readout', lib('charts/readout')]
		];
		for (const [file, child] of [
			['components/ChartReadout', 'ChartReadout'], ['components/Reserved', 'Reserved'], ['components/KpiCard', 'KpiCard'],
			['components/Sparkline', 'Sparkline'], ['charts/d3/EmptyState', 'EmptyState'],
			['charts/d3/DateSeries', 'DateSeries'], ['console/model/Series', 'Series']
		]) await compiled(`src/lib/${file}.svelte`, child, rewrite);
		const module = await compiled(`src/lib/console/model/${name}.svelte`, name, rewrite);
		const component = (await import(pathToFileURL(module).href)).default;
		const appearance = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8'));
		const read: RecordRead = { state: 'read', first: '2030-06-01', through: '2030-06-14',
			lastRows: null, lostDays: [], setAside: {} };
		const common = { start: '2030-06-01', end: '2030-06-14', instruments: [], windowDays: 14,
			rule: { declined: 'No dated settings record is available in this fixture.' },
			checkerRule: { declined: 'No dated checker record is available in this fixture.' }, chart: appearance.chart };
		const markup = (days: null | []) => render(component, { props: { ...common, days, reads: { article: read, score: read } } }).body;
		const quiet = markup([]);
		const missing = markup(null);
		expect(quiet).toContain(`data-${id === 'model-cards' ? 'model-cards' : 'doubt-reasons'}-empty="quiet"`);
		expect(missing).toContain('unavailable');
		for (const html of [quiet, missing]) {
			expect(html.match(/data-lede(?:\s|=|>)/g)).toHaveLength(1);
			expect(html.match(/data-comparison=/g)).toHaveLength(1);
			expect(html).toContain('data-readout-none=');
			expect(html).not.toContain('data-chart-type=');
		}
		const reading = (html: string): PanelReading => ({ id, nothing: { words: words(html), ground: null } } as PanelReading);
		expect(judgeNothings(id, { quiet: reading(quiet), missing: reading(missing) } as Record<Nothing, PanelReading>,
			['quiet', 'missing']).pass).toBe(true);
		if (id === 'model-cards') {
			const previous = render(component, { props: { ...common, days: [] } }).body;
			expect(previous).toContain('data-model-cards-empty="missing"');
			expect(words(previous)).toContain('unavailable in this window');
			expect(previous).not.toContain('data-kpi=');
			expect(previous).not.toContain('data-chart-type=');
			for (const absent of [
				{ state: 'not-packed' },
				{ state: 'unreadable', at: null, fault: null },
				{ ...read, through: '2030-06-13' },
				{ ...read, first: '2030-06-15', through: '2030-06-15' },
				{ ...read, lostDays: ['2030-06-14'] },
				{ ...read, setAside: { '2030-06': 1 } }
			] satisfies RecordRead[]) {
				const html = render(component, { props: {
					...common, days: [], start: '2030-06-14', end: '2030-06-14', windowDays: 1,
					reads: { article: read, score: absent }
				} }).body;
				expect(html).toContain('data-model-cards-empty="missing"');
				expect(words(html)).toContain('unavailable in this window');
				expect(words(html)).not.toContain('No model work');
				expect(html).not.toContain('data-kpi=');
			}
			const outside = { ...read, lostDays: ['2030-06-01'], setAside: { '2030-05': 1 } };
			const html = render(component, { props: {
				...common, days: [], start: '2030-06-14', end: '2030-06-14', windowDays: 1,
				reads: { article: outside, score: read }
			} }).body;
			expect(html).toContain('data-model-cards-empty="quiet"');
			expect(words(quiet)).toContain('No model readings were recorded in this window.');
		}
	});
}
