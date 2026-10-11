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
import { failureRuleRows, failureRules } from '../src/lib/console/failure-rules';

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
		['Sparkline', 'src/lib/components/Sparkline.svelte'],
		['FailureRuleRanking', 'src/lib/components/FailureRuleRanking.svelte']
	];
	const rewrites = files.flatMap(([child]) => [
		[`./${child}.svelte`, `./${child}.server.mjs`] as const,
		[`$lib/components/${child}.svelte`, `./${child}.server.mjs`] as const
	]);
	for (const [child, file] of files) await compiled(file, child, rewrites);
	const file = ['RankedList', 'KpiCard', 'FailureList', 'TimeHistogram', 'StageTimings'].includes(name)
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
	const coloured = await draw('TimeHistogram', { ...props, domain: [0.5, 8], barToken: SERIES_TOKENS['reading-prompt'] });
	expect(shared).toContain('fill="var(--chart-1)"');
	expect(coloured).toContain('fill="var(--chart-6)"');
	expect(coloured).toContain('stroke="var(--chart-3)"');
	expect(coloured).toContain('var(--chart-6)');
	expect(medianX(coloured)).toBe(medianX(shared));
	await expect(draw('TimeHistogram', { ...props, domain: [0, 8] })).rejects.toThrow(/positive/);
	await expect(draw('TimeHistogram', { ...props, domain: [1, 8] })).rejects.toThrow(/contain/);
	await expect(draw('TimeHistogram', { ...props, domain: [0.5, 1] })).rejects.toThrow(/contain/);
});

test('identity-free rule rankings count rows and unknown rules, never sources or invented item identities', async () => {
	const rows = failureRuleRows([
		{ date: '2026-09-01', stage: 'fetch', outcome: 'failed', code: 'network', failed_rule: 'Retry limit' },
		{ date: '2026-09-01', stage: 'fetch', outcome: 'failed', code: 'network', failed_rule: 'Retry limit' },
		{ date: '2026-09-02', stage: 'fetch', outcome: 'failed', code: 'blocked', failed_rule: 'Source permission' },
		{ date: '2026-09-02', stage: 'fetch', outcome: 'failed', code: 'Retry limit', failed_rule: null },
		{ date: '2026-09-03', stage: 'fetch', outcome: 'ok', code: null, failed_rule: '' },
		{ date: '2026-09-03', stage: 'extract', outcome: 'failed', code: 'blank', failed_rule: 'Empty body' }
	]);
	const window = { start: '2026-09-01', end: '2026-09-03' };
	expect(rows[4].code).toBeNull();
	expect(() => failureRuleRows([{ date: '2026-09-01', stage: 'fetch', outcome: 'ok', failed_rule: null }])).toThrow(/code string or null/);
	expect(() => failureRuleRows([{ date: '2026-09-01', stage: 'fetch', outcome: 'ok', code: 0, failed_rule: null }])).toThrow(/code string or null/);
	expect(failureRules(rows, window, 'fetch')).toEqual({
		dates: ['2026-09-01', '2026-09-02', '2026-09-03'], rows: 5, failed: 4, unknown: 1,
		rules: [
			{ label: 'Retry limit', count: 2, daily: [2, 0, 0], last: '2026-09-01' },
			{ label: 'Source permission', count: 1, daily: [0, 1, 0], last: '2026-09-02' }
		]
	});
	const props = { ranking: rows, window, stages: { options: ['fetch', 'extract'], chosen: 'fetch' },
		selectedCode: null, max: 20, sourceMax: 20, readoutMaxShare: 1 };
	const html = await draw('FailureList', props);
	expect(html).toContain('2 of 4 failures');
	expect(html).toMatch(/1 of 4 failures at fetch\s+has no recorded failed rule\./);
	expect(html).not.toContain('Empty body');
	expect(html).not.toMatch(/data-failure-(item|source|rows)=|data-source-losses/);
	expect(html).toContain('not distinct articles');
	expect(html.match(/type="radio"/g)?.length).toBe(2);
	const extracted = await draw('FailureList', { ...props, stages: { options: ['fetch', 'extract'], chosen: 'extract' } });
	expect(extracted).toContain('Empty body');
	expect(extracted).not.toContain('Retry limit');
	const unnamed = await draw('FailureList', { ...props, ranking: rows.map((row) => ({ ...row, failed_rule: '' })) });
	expect(unnamed).toMatch(/4 of 4 failures at fetch\s+have no recorded failed rule\./);
	expect(unnamed).not.toContain('data-readout="failed-rule-trends"');
	expect(() => failureRuleRows([{ date: '2026-02-30', stage: 'fetch', outcome: 'failed', code: '', failed_rule: null }])).toThrow(/UTC date/);
	expect(() => failureRuleRows([{ date: '2026-09-01', stage: 'fetch', outcome: 'failed', code: '' }])).toThrow(/failed_rule/);
	await expect(draw('FailureList', { ...props, stages: { options: ['fetch'], chosen: 'extract' } })).rejects.toThrow(/chosen stage/);
});

test('stage timings preserve structured rule availability and both kinds of readout event without changing legacy defaults', async () => {
	const props = {
		days: [
			{ date: '2026-09-01', items: 1, fetch: { ms: 20, timed: 1, total: 1 },
				extract: { ms: 0, timed: 1, total: 1 }, summarize: { ms: 1000, timed: 1, total: 1 } },
			{ date: '2026-09-02', items: 1, fetch: { ms: 30, timed: 1, total: 1 },
				extract: { ms: null, timed: 0, total: 1 }, summarize: { ms: 2000, timed: 1, total: 1 } }
		],
		span: { start: '2026-09-01', end: '2026-09-02' },
		height: 220, width: 390, tickDensity: 6, readoutMaxShare: 1
	};
	const old = await draw('StageTimings', { ...props, modelChanges: ['2026-09-02'] });
	expect(old).toContain('data-model-rule="yes"');
	expect(old).toContain('data-model-rule-label="2026-09-02"');
	const rule: ModelRule = { changes: [
		{ date: '2026-09-01', kind: 'checker', words: 'The scoring weights changed.' },
		{ date: '2026-09-02', kind: 'settings', words: 'The summary prompt changed.' },
		{ date: '2026-09-02', kind: 'checker', words: 'The score checker changed.' }
	], note: 'Compared with the preceding recorded settings.' };
	const html = await draw('StageTimings', { ...props, rule });
	expect(html).toContain('data-model-rule-kind="checker"');
	expect(html).toContain('stroke-dasharray="1 3"');
	expect(html).toContain('The summary prompt changed.');
	expect(html).toContain('The score checker changed.');
	expect(html).not.toContain('data-model-rule-label=');
	expect(html.split('</svg>')[0]).not.toContain('The summary prompt changed.');
	expect(html).toContain('data-timing-zero-key');
	const unavailable = await draw('StageTimings', { ...props, rule: declined });
	expect(unavailable).toContain('data-model-rule="no"');
	expect(unavailable).toContain(declined.declined);
	expect(unavailable).not.toContain('data-model-rule-empty');
	const empty = await draw('StageTimings', { ...props, rule: { changes: [], note: 'No settings changed in this window.' } });
	expect(empty).toContain('data-model-rule="yes"');
	expect(empty).toContain('No settings changed in this window.');
	await expect(draw('StageTimings', { ...props, rule, modelChanges: ['2026-09-01'] })).rejects.toThrow(/not both/);
});

test('elapsed reconciliation leaves stage heights intact and draws overlap beside, not below, their stack', async () => {
	const dated = (values: readonly (number | null)[]) => values.map((value, index) => ({
		date: `2026-09-0${index + 1}`, value
	}));
	const series = [
		{ label: 'Fetch', token: SERIES_TOKENS.fetch, points: dated([2, 0, null]) },
		{ label: 'Summarize', token: SERIES_TOKENS.summarize, points: dated([6, 0, null]) }
	];
	const reconciliation = {
		elapsed: { label: 'Elapsed time', token: '--color-text-tertiary' as const, points: dated([5, 0, null]) },
		overlap: { label: 'Overlap', token: '--color-text-secondary' as const, points: dated([3, 0, null]) }
	};
	const geometry = dateSeries(series, { ...options, stacked: true, rule: declined, reconciliation });
	const reference = dateSeries(series, { ...options, stacked: true, rule: declined });
	expect(geometry?.bars).toEqual(reference?.bars);
	expect(geometry?.reconciliation?.marks).toHaveLength(2);
	const first = geometry!.reconciliation!.marks[0];
	expect(first.elapsed).toBe(5);
	expect(first.overlap).toBe(3);
	expect(first.y).toBe(geometry?.axis.scale(5));
	expect(first.top).toBe(geometry?.axis.scale(8));
	expect(first.bracket).toBeGreaterThan(first.end);
	expect(first.bracket).toBeLessThanOrEqual(box.right);
	expect(geometry?.reconciliation?.marks[1].y).toBe(box.bottom);
	const html = await draw('DateSeries', { ...common, geometry });
	expect(html).toContain('data-stack-overlap="2026-09-01"');
	expect(html).toContain('data-elapsed-value="5"');
	expect(html).toContain('Solid crossbar: Elapsed time.');
	expect(html).toContain('Bracket beside the stack: Overlap');
	expect(html).not.toContain('data-stack-elapsed="2026-09-03"');
	expect(html).not.toContain('data-stack-overlap="2026-09-02"');
	expect(html).toContain('data-readout="contract"');
	const supplied = readoutOf({
		type: 'dateSeries', columns: ['first', 'second', 'third'],
		series: [{ label: 'Fetch', swatch: 'var(--chart-1)', values: [2, 0, null], format: (value) => `${value} ms` }],
		notMeasured: 'Not recorded.', resting: 'first'
	});
	const supplemented = await draw('DateSeries', { ...common, geometry, readout: supplied });
	expect(supplemented).toContain('data-readout-row="Elapsed time"');
	expect(supplemented).toContain('data-readout-row="Overlap"');
	expect(supplemented).toContain('2 ms');
	await expect(draw('DateSeries', { ...common, geometry, readout: { ...supplied, columns: ['first'] } })).rejects.toThrow(/every drawn day/);
	expect(() => dateSeries(series, { ...options, rule: declined, reconciliation })).toThrow(/stacked durations/);
	expect(() => dateSeries(series, { ...options, stacked: true, rule: declined, reconciliation: {
		...reconciliation, elapsed: { ...reconciliation.elapsed, points: dated([7, 0, null]) }
	} })).toThrow(/do not equal/);
	expect(() => dateSeries(series, { ...options, stacked: true, rule: declined, reconciliation: {
		...reconciliation, overlap: { ...reconciliation.overlap, points: dated([null, 0, null]) }
	} })).toThrow(/every stage/);
	expect(() => dateSeries(series, { ...options, stacked: true, rule: declined, reconciliation: {
		...reconciliation, overlap: { ...reconciliation.overlap, points: dated([-3, 0, null]) }
	} })).toThrow(/non-negative/);
	expect(() => dateSeries([{ ...series[0], points: dated([-1]) }], { ...options, stacked: true, rule: declined })).toThrow(/negative part/);
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
