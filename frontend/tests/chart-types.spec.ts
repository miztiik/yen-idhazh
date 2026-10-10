/** The shared chart contracts, over fixed rows and the real server-rendered components. */
import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { serverCompiler } from './support/server-render';
import { telemetryRow } from './support/telemetry-row';
import { frame } from '../src/lib/charts/frame';
import { rankedList, rankedGeometry } from '../src/lib/charts/d3/rankedList';
import { rank } from '../src/lib/charts/rank';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { checkedRule, ruleEvents, type ModelRule } from '../src/lib/charts/d3/model-rule';
import { distribution } from '../src/lib/charts/d3/distribution';
import { partsOfOne } from '../src/lib/charts/d3/partsOfOne';
import { tileStrip, tileWindow } from '../src/lib/charts/d3/tileStrip';
import { pairedScatter } from '../src/lib/charts/d3/pairedScatter';
import { flow } from '../src/lib/charts/d3/flow';
import { emptyState } from '../src/lib/charts/d3/empty';
import { readoutOf } from '../src/lib/charts/readout';
import { SERIES_TOKENS } from '../src/lib/console/series-tokens';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const box = frame(390, 220);
const declined: ModelRule = { declined: 'This question has no settings comparison record.' };
const points = [
	{ date: '2026-09-01', value: 2, spread: { low: 1, high: 4 } },
	{ date: '2026-09-02', value: 3, spread: { low: 2, high: 5 } },
	{ date: '2026-09-03', value: 1, spread: { low: 0, high: 2 } }
];
const options = { frame: box, density: 6, valueTicks: 4, padding: 0.2 };
const common = { empty: emptyState('quiet', 'Nothing recorded.'), name: 'contract', label: 'Contract rows', width: 390, height: 220 };

async function draw(name: string, props: Record<string, unknown>): Promise<string> {
	const compiled = serverCompiler(path.join(frontend, 'test-results', 'chart-types', name));
	const files: readonly [string, string][] = [
		['Reserved', 'src/lib/components/Reserved.svelte'],
		['EmptyState', 'src/lib/charts/d3/EmptyState.svelte'],
		['ChartReadout', 'src/lib/components/ChartReadout.svelte'],
		['RankedList', 'src/lib/components/RankedList.svelte'],
		['Sparkline', 'src/lib/components/Sparkline.svelte']
	];
	const rewrites = files.flatMap(([child]) => [
		[`./${child}.svelte`, `./${child}.server.mjs`] as const,
		[`$lib/components/${child}.svelte`, `./${child}.server.mjs`] as const
	]);
	for (const [child, file] of files) await compiled(file, child, rewrites);
	const file = ['RankedList', 'KpiCard', 'FailureList', 'TimeHistogram'].includes(name)
		? `src/lib/components/${name}.svelte` : `src/lib/charts/d3/${name}.svelte`;
	const module = await compiled(file, name, rewrites);
	const loaded = await import(pathToFileURL(module).href);
	const html = render(loaded.default, { props }).body;
	for (const match of html.matchAll(/data-readout-none="([^"]+)"/g)) {
		expect(match[1].endsWith('; agreed with Susan')).toBe(true);
	}
	return html;
}

test('a range shares the divisor with ends and named rules; short rows rank last and draw no mark', async () => {
	const geometry = rankedList([
		{ label: 'short', value: 50, range: { high: 80, count: 12 } },
		{ label: 'range', value: 20, range: { high: 40, count: 20 }, status: 'on the floor' },
		{ label: 'ends', value: 10, ends: { end: 60 } }
	], { minCount: 20, rules: [{ at: 100, label: 'Memory ceiling' }] });
	expect(geometry?.max).toBe(100);
	expect(geometry?.rows.map((row) => row.label)).toEqual(['range', 'ends', 'short']);
	expect(geometry?.rows[0].range).toMatchObject({ medianWidth: '20.0000%', notchWidth: '40.0000%' });
	expect(geometry?.rows[1].ends).toEqual({ valuePercent: '10.0000%', endPercent: '60.0000%' });
	const html = await draw('RankedList', { geometry, caption: 'Rows', maxText: '100 units', unmeasuredNote: 'Not measured.', emptyNote: 'No rows.' });
	expect(html).toContain('Too few: 12 of the 20 articles a row needs.');
	const shortRow = html.split('data-ranked-row="short"')[1];
	expect(shortRow).not.toContain('class="range-fill');
	expect(html).toContain('Memory ceiling');
	expect(html).toContain('on the floor');
	expect(html).toContain('data-chart-type="rankedList"');
	expect(html).toContain('data-readout-none=');
	expect(html).toContain('inline-size: 10.0000%; background: var(--chart-1)');
});

test('a ranked row refuses mixed marks and a range without its article floor', () => {
	for (const extra of [
		{ segments: [{ label: 'part', value: 1, token: '--chart-1' }], range: { high: 2, count: 20 } },
		{ segments: [], ends: { end: 2 } },
		{ range: { high: 2, count: 20 }, ends: { end: 2 } }
	]) expect(() => rankedList([{ label: 'mixed', value: 1, ...extra }], { minCount: 20 })).toThrow(/segments|range|ends/);
	expect(() => rankedList([{ label: 'range', value: 1, range: { high: 2, count: 20 } }], {})).toThrow(/minCount/);
	expect(rankedList([{ label: 'a', value: 3 }, { label: 'b', value: 1 }], { order: 'smallest-first' })?.rows.map((row) => row.label)).toEqual(['b', 'a']);
});

test('settings and checker share a boundary, keep both readout rows, and never print their words on the plot', async () => {
	const rule: ModelRule = { changes: [
		{ date: '2026-09-02', kind: 'settings', words: 'The summary prompt changed.' },
		{ date: '2026-09-02', kind: 'checker', words: 'The score checker changed.' },
		{ date: '2026-09-03', kind: 'checker', words: 'The checker changed again.' }
	], note: 'Compared with the preceding recorded day.' };
	const geometry = dateSeries([{ label: 'Count', token: '--chart-1', points }], { ...options, rule, domain: [0, 10], rules: [{ at: 6, label: 'Target' }] });
	expect(geometry?.boundaries).toEqual([
		{ date: '2026-09-02', x: ((geometry?.columns[0] ?? 0) + (geometry?.columns[1] ?? 0)) / 2, kind: 'settings' },
		{ date: '2026-09-03', x: ((geometry?.columns[1] ?? 0) + (geometry?.columns[2] ?? 0)) / 2, kind: 'checker' }
	]);
	const events = ruleEvents(rule, points.map((point) => point.date));
	expect(events.lines[1].map((event) => event.label)).toEqual(['Settings changed', 'Checker changed']);
	const readout = readoutOf({ type: 'dateSeries', columns: points.map((point) => point.date), series: [{ label: 'Count', swatch: 'var(--chart-1)', values: points.map((point) => point.value), format: String }], notMeasured: 'Not recorded.', resting: 1 });
	const html = await draw('DateSeries', { ...common, geometry, readout });
	expect(html).toContain('data-model-rule="yes"');
	expect(html).toContain('stroke-dasharray="3 3"');
	expect(html).toContain('stroke-dasharray="1 3"');
	expect(html).toContain('The summary prompt changed.');
	expect(html).toContain('The score checker changed.');
	expect(html.split('</svg>')[0]).not.toContain('The summary prompt changed.');
	expect(html).toContain('data-model-rule-note');
	expect(html).toContain('data-series-spread="Count"');
	expect(html.indexOf('data-series-spread')).toBeLessThan(html.indexOf('data-date-series-marks'));
	expect(geometry?.axis.domain).toEqual([0, 10]);
	expect(geometry?.rules[0].y).toBeCloseTo(box.bottom - 0.6 * box.innerHeight);
	const alreadyPresent = { ...readout, events: events.lines };
	const once = await draw('DateSeries', { ...common, geometry, readout: alreadyPresent });
	expect(once.match(/The summary prompt changed\./g)?.length).toBe(1);
	expect(await draw('DateSeries', { ...common, geometry })).toContain('data-readout="contract"');
});

test('a first-column boundary stays inside the frame; no changes print their note; short declines fail', async () => {
	expect(() => checkedRule({ declined: 'No dates here.' })).toThrow(/five words/);
	const geometry = dateSeries([{ label: 'Count', token: '--chart-1', points }], { ...options, rule: { changes: [{ date: '2026-09-01', kind: 'settings', words: 'The prompt changed.' }], note: null } });
	expect(geometry?.boundaries[0].x).toBe(box.left);
	const none = dateSeries([{ label: 'Count', token: '--chart-1', points }], { ...options, rule: { changes: [], note: 'No settings changed in this window.' } });
	expect(await draw('DateSeries', { ...common, geometry: none })).toContain('data-model-rule-empty');
	expect(await draw('DateSeries', { ...common, geometry: dateSeries([{ label: 'Count', token: '--chart-1', points }], { ...options, rule: declined }) })).toContain('data-model-rule="no"');
	expect(() => dateSeries([{ label: 'Count', token: '--chart-1', points }], { ...options, rule: declined, domain: [0, 2] })).toThrow(/domain/);
	const stacked = [
		{ label: 'First', token: '--chart-1' as const, points: [{ date: '2026-09-01', value: 2 }] },
		{ label: 'Second', token: '--chart-2' as const, points: [{ date: '2026-09-01', value: 6 }] }
	];
	expect(() => dateSeries(stacked, { ...options, stacked: true, rule: declined, domain: [5, 10] })).toThrow(/domain/);
	const stack = dateSeries(stacked, { ...options, stacked: true, rule: declined, domain: [0, 10] });
	expect(stack?.bars[0].height).toBeCloseTo(box.innerHeight * 0.2);
	expect(stack?.bars[1].height).toBeCloseTo(box.innerHeight * 0.6);
});

test('log distributions bin by decade and common domains place the same rule at the same pixel', async () => {
	const opts = { frame: box, minValues: 1, valueTicks: 4, scale: 'log' as const, domain: [1, 1000] as [number, number], rules: [{ at: 100, label: 'Limit' }] };
	const a = distribution([1, 2, 9, 10, 99, 100, 999], opts);
	const b = distribution([10, 20], opts);
	expect(a?.bins.map((bin) => [bin.x0, bin.x1, bin.count])).toEqual([[1, 10, 3], [10, 100, 2], [100, 1000, 2]]);
	expect(a?.rules[0].x).toBe(b?.rules[0].x);
	expect(() => distribution([0, 1], opts)).toThrow(/positive/);
	expect(() => distribution([2000], opts)).toThrow(/domain/);
	const html = await draw('Distribution', { ...common, geometry: a });
	expect(html).toContain('Limit');
	expect(html).toContain('data-chart-type="distribution"');
	expect(html).toContain('data-readout-columns="3"');
	expect(html).toContain('data-readout-row="share"');
});

test('ninety days keep readable newest tiles and report the earlier three states truthfully', async () => {
	const tiles = Array.from({ length: 90 }, (_, index) => ({
		date: new Date(Date.UTC(2026, 6, 1 + index)).toISOString().slice(0, 10),
		state: index < 2 ? 'fired' as const : index < 5 ? 'absent' as const : 'quiet' as const
	}));
	const geometry = tileStrip(tiles);
	expect(geometry).not.toBeNull();
	const visible = tileWindow(geometry!, 390, 6);
	expect(visible.tiles.length).toBe(49);
	expect(visible.overflow).toBe('41 earlier days: 2 fired, 36 quiet, 3 not recorded.');
	expect((390 - (visible.tiles.length - 1) * 2) / visible.tiles.length).toBeGreaterThanOrEqual(6);
	expect(visible.tiles.at(-1)?.date).toBe(tiles.at(-1)?.date);
	const html = await draw('TileStrip', { ...common, geometry, tileMinPx: 6 });
	expect(html.match(/data-tile-state=/g)?.length).toBe(49);
	expect(html).toContain(visible.overflow!);
	expect(html).toContain('data-tile-axis');
	expect(html).not.toContain(' title=');
	expect(tileWindow(geometry!, 390).tiles.length).toBe(90);
	expect(() => tileStrip([{ date: '2026-09-01', state: 'fired', reading: 1 }])).toThrow(/thresholds/);
});

test('quantity colours are explicit, keyed by name, while omitted part colours and flow counts stay unchanged', async () => {
	const rows = [{ label: 'one', parts: [{ label: 'reply', value: 2 }, { label: 'prompt', value: 3 }] }];
	const geometry = partsOfOne(rows, { order: ['reply', 'prompt'], quantityByLabel: { prompt: 'reading-prompt', reply: 'writing-reply' } });
	expect(geometry?.key.map((part) => part.token)).toEqual(['--chart-7', '--chart-6']);
	expect(partsOfOne(rows, { order: ['reply', 'prompt'] })?.key.map((part) => part.token)).toEqual(['--chart-1', '--chart-2']);
	expect(() => partsOfOne(rows, { order: ['reply', 'prompt'], tokens: ['--chart-1', '--chart-2'], quantityByLabel: { prompt: 'reading-prompt', reply: 'writing-reply' } })).toThrow(/both/);
	expect(SERIES_TOKENS).toMatchObject({ fetch: '--chart-1', extract: '--chart-2', summarize: '--chart-3', 'label-call': '--chart-4', 'summary-call': '--chart-5', 'visual-plan': '--chart-6', checking: '--chart-7', other: '--chart-8', 'queue-wait': '--chart-axis', 'free-memory': null });
	expect(await draw('PartsOfOne', { ...common, geometry })).toContain('data-readout-none=');
	const stages = [{ label: 'fetch', arrived: 10, left: 8, drops: [{ label: 'failed', count: 2 }] }, { label: 'extract', arrived: 8, left: 7, drops: [{ label: 'failed', count: 1 }] }];
	const flowed = flow(stages, { frame: box, narrow: true, nodeWidth: 12, nodeGap: 16 });
	expect(await draw('Flow', { ...common, geometry: flowed })).toContain('data-chart-type="flow"');
});

test('kept cards and failure lists keep omitted-prop behaviour, while the card can lead and declare its rule', async () => {
	const ordinary = await draw('KpiCard', { label: 'Count', value: '12' });
	expect(ordinary).not.toContain('data-lede');
	expect(ordinary).not.toContain('data-model-rule');
	const lede = await draw('KpiCard', { label: 'Count', value: '12', lede: true, rule: declined });
	expect(lede).toContain('data-lede');
	expect(lede).toContain('data-model-rule="no"');
	const failure = { rows: [], window: { start: '2026-09-01', end: '2026-09-03' }, selectedCode: null, max: 20, sourceMax: 20, readoutMaxShare: 1 };
	expect(await draw('FailureList', failure)).not.toContain('data-failure-stages');
	expect(await draw('FailureList', { ...failure, stages: { options: ['fetch', 'extract'], chosen: 'extract' } })).toContain('data-failure-stages');
	const rows = [
		{ ...telemetryRow({ date: '2026-09-01', stage: 'fetch', outcome: 'failed', code: 'old-fetch' }), failed_rule: 'Fetch rule' },
		{ ...telemetryRow({ date: '2026-09-01', stage: 'extract', outcome: 'failed', code: 'old-extract' }), failed_rule: 'Extract rule' }
	];
	const picked = await draw('FailureList', { ...failure, rows, stages: { options: ['fetch', 'extract'], chosen: 'extract' } });
	expect(picked).toContain('Extract rule');
	expect(picked).not.toContain('Fetch rule');
	expect(picked).not.toContain('old-extract');
	expect(picked.match(/type="radio"/g)?.length).toBe(2);
	const kept = await draw('FailureList', { ...failure, rows });
	expect(kept).toContain('old-fetch');
	expect(kept).toContain('old-extract');
	expect(kept).not.toContain('Extract rule');
	const geometry = rankedGeometry(rank([{ key: 'stable', value: 2, row: { label: 'Stable name', value: '2 articles' } }], 20));
	expect(geometry.rows[0].row.value).toBe('2 articles');
});

test('kept time histograms share an optional positive domain and refuse one that clips a bin', async () => {
	const props = {
		times: { n: 3, median: 1000, p95: 2000, bins: [
			{ from: 0, to: 1, n: 1, throughPct: 100 / 3 },
			{ from: 1, to: 2, n: 2, throughPct: 100 }
		] },
		name: 'writing',
		subject: 'Seconds to write',
		verb: 'written',
		noRuleReason: 'This pooled window has no date axis.',
		width: 390,
		height: 220
	};
	const shared = await draw('TimeHistogram', { ...props, domain: [0.5, 8] });
	const other = await draw('TimeHistogram', { ...props, times: { ...props.times, bins: [...props.times.bins, { from: 2, to: 4, n: 0, throughPct: 100 }] }, domain: [0.5, 8] });
	const medianX = (html: string) => html.match(/<line x1="([^"]+)"[^>]*data-hist-rule="median"/)?.[1];
	expect(medianX(shared)).toBeDefined();
	expect(medianX(shared)).toBe(medianX(other));
	await expect(draw('TimeHistogram', { ...props, domain: [0, 8] })).rejects.toThrow(/positive/);
	await expect(draw('TimeHistogram', { ...props, domain: [1, 8] })).rejects.toThrow(/contain/);
	await expect(draw('TimeHistogram', { ...props, domain: [0.5, 1] })).rejects.toThrow(/contain/);
});

test('scatter readout uses the same recorded facts, and tokens retain the exact approved theme values', async () => {
	const geometry = pairedScatter([{ label: 'a', x: 1, y: 2 }, { label: 'b', x: 2, y: 3 }], { frame: box, minRows: 1, minSubjects: 1, valueTicks: 4 });
	const html = await draw('PairedScatter', { ...common, geometry });
	expect(html).toContain('data-chart-type="pairedScatter"');
	expect(html).toContain('data-readout-records="2"');
	expect(html).toContain('data-readout-subject');
	const tokens = readFileSync(path.join(frontend, 'src', 'styles', 'tokens.css'), 'utf8');
	expect(tokens).toContain('--chart-6: #1ab6ff;');
	expect(tokens.match(/--chart-spread-mix: 0\.30;/g)?.length).toBe(2);
});
