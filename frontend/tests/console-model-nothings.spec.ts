/** Do the private Summaries cards distinguish quiet records from absent records? */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { renderConfigured as render } from './support/server-render';
import { serverCompiler, type Rewrite } from './support/server-render';
import { judgeNothings, type Nothing, type PanelReading } from './support/panel-gates';
import type { RecordRead } from '../src/lib/console/recording';
import type { ModelDay } from '../src/lib/server/model-work';
import type { RuleChange } from '../src/lib/charts/d3/model-rule';

const PANELS = [['model-cards', 'Cards']] as const;
const words = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ')
	.replace(/\s+/g, ' ').trim();

for (const [id, name] of PANELS) {
	test(`${id}: real private inputs retain readings and distinguish quiet from absent`, async ({}, info) => {
		const compiled = serverCompiler(info.outputPath('components'));
		const lib = (file: string) => pathToFileURL(resolve('src', 'lib', `${file}.ts`)).href;
		const rewrite: Rewrite[] = [
			['./cards', lib('console/model/cards')], ['./model-rule', lib('console/model/model-rule')],
			['../model-cards', lib('console/model-cards')], ['../eval-instruments', lib('console/eval-instruments')],
			['../span-words', lib('console/span-words')], ['../../format', lib('format')],
			['../../charts/d3/dateSeries', lib('charts/d3/dateSeries')],
			['../../charts/d3/empty', lib('charts/d3/empty')], ['../../charts/frame', lib('charts/frame')],
			['../../charts/label-context', lib('charts/label-context')],
			['../../components/KpiCard.svelte', './KpiCard.server.mjs'],
			['../../components/Sparkline.svelte', './Sparkline.server.mjs'],
			['./EmptyState.svelte', './EmptyState.server.mjs'],
			['$lib/components/Reserved.svelte', './Reserved.server.mjs'],
			['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs'],
			['../charts/readout', lib('charts/readout')]
		];
		for (const [file, child] of [
			['components/ChartReadout', 'ChartReadout'], ['components/Reserved', 'Reserved'], ['components/KpiCard', 'KpiCard'],
			['components/Sparkline', 'Sparkline']
		]) await compiled(`src/lib/${file}.svelte`, child, rewrite);
		const module = await compiled(`src/lib/console/model/${name}.svelte`, name, rewrite);
		const component = (await import(pathToFileURL(module).href)).default;
		const appearance = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8'));
		const read: RecordRead = { state: 'read', first: '2030-06-01', through: '2030-06-14',
			lastRows: null, lostDays: [], setAside: {} };
		const common = { start: '2030-06-01', end: '2030-06-14', instruments: [], windowDays: 14,
			rule: { declined: 'No dated settings record is available in this fixture.' }, chart: appearance.chart };
		const markup = (days: null | []) => render(component, { props: { ...common, days, reads: { article: read, score: read } } }).body;
		const quiet = markup([]);
		const missing = markup(null);
		expect(quiet).toContain('data-model-cards-empty="quiet"');
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

			const day = (date: string): ModelDay => ({
				date, summaries: 20, readInPart: null, readInPartPct: null, readInPartOf: null,
				perItemMs: date === '2030-06-14' ? 1000 : null, perItemCutMs: null,
				totalMs: date === '2030-06-12' ? null : 20000,
				refusedForLength: 0, failed: 0, models: ['recorded-model']
			});
			const days = ['2030-04-01', '2030-05-20', '2030-06-01', '2030-06-11', '2030-06-12', '2030-06-14'].map(day);
			const changes: readonly RuleChange[] = [
				{ date: '2030-04-01', kind: 'settings', words: 'The old runtime changed.' },
				{ date: '2030-05-20', kind: 'settings', words: 'The older prompt changed.' },
				{ date: '2030-06-12', kind: 'settings', words: 'The current prompt changed.' }
			];
			for (const [windowDays, start] of [[90, '2030-03-17'], [30, '2030-05-16'], [14, '2030-06-01']] as const) {
				const selected = changes.filter((change) => change.date >= start);
				const populated = render(component, { props: {
					...common, days, start, windowDays, reads: { article: read, score: read },
					rule: { changes: selected, note: 'The change record is incomplete before this window.' }
				} }).body;
				expect(populated.match(/data-model-cards-note(?:\s|=|>)/g)).toHaveLength(1);
				expect(populated.match(/Point at or focus a line/g)).toHaveLength(1);
				expect(populated).not.toContain('data-readout-hint=');
				expect(populated).toContain('data-model-cards-rule-history');
				for (const change of selected) {
					expect(populated.match(new RegExp(`data-model-card-change="${change.date}"`, 'g'))).toHaveLength(1);
					expect(populated).toContain(change.words);
				}
				const cards = populated.split('data-chart="cards"')[1].split('data-model-cards-rule-note')[0];
				expect(cards).not.toMatch(/The old runtime|The older prompt|record is incomplete/);
				expect(cards).not.toMatch(/data-readout-row="(?:Settings|Checker) changed"/);
				expect(cards).toContain('aria-describedby="model-card-changes"');
				expect(cards).not.toMatch(/data-model-rule-line="2030-(?:04-01|05-20)"/);
				const minutes = cards.split('data-kpi="Model minutes"')[1].split('data-kpi=')[0];
				expect(minutes).toContain('Nothing here measured that day');
				expect(minutes).toContain('2030-06-12');
				expect(minutes).not.toContain('data-model-rule-line="2030-06-12"');
				const summaries = cards.split('data-kpi="Published summaries checked"')[1].split('data-kpi=')[0];
				expect(summaries).toContain('data-model-rule-line="2030-06-12"');
				expect(summaries).not.toContain('data-model-rule-kind="checker"');
				expect(populated).toContain('No measured days for this card.');
				expect(populated).toContain('Only one measured day; no trend yet.');
				const readout = summaries.split('data-readout="model-summaries"')[1].split('</dl>')[0];
				expect(words(readout)).not.toContain('Published summaries checked');
				expect(words(readout)).toContain('14 Jun 2030');
				expect(readout).toContain('>20<');
			}
		}
	});
}
