/** How a chart builds its readout without a second key or invented readings. */
import { expect, test } from '@playwright/test';
import { factsOf, readoutOf } from '../src/lib/charts/readout';
import { hoverPosition, hoverReading } from '../src/lib/charts/readout-hover';
import { readoutView } from '../src/lib/charts/readout-view';
import { frame } from '../src/lib/charts/frame';
import { dateSeries, formatNumber, numberFormat } from './support/number-format';
import { clocksChart } from '../src/lib/charts/machine';
import { pathToFileURL } from 'node:url';
import { distribution } from '../src/lib/charts/d3/distribution';
import { emptyState } from '../src/lib/charts/d3/empty';
import { consoleConfig } from '../src/lib/server/config';
import { renderConfigured, serverCompiler, type Rewrite } from './support/server-render';
import { diskReads, type DiskReads } from '../src/lib/console/machine/disk-reads';

test('column hover and standing readings preserve zeros, partial readings and dated events', () => {
	const readout = readoutOf({
		type: 'dateSeries', columns: ['First UTC day', 'Unmeasured UTC day', 'Last UTC day'],
		series: [
			{ label: 'Read', swatch: 'var(--chart-1)', values: [0, null, null], format: (value) => `${value} tokens` },
			{ label: 'Written', swatch: 'var(--chart-2)', values: [null, null, 4], format: (value) => `${value} tokens` }
		],
		events: { lines: [[{ label: 'Run 1', value: 'failed', swatch: null }], [], []] },
		notMeasured: 'No token reading.', resting: 'last'
	});
	const first = hoverReading({ name: 'tokens', readout }, 0)!;
	expect(first.heading).toBe('First UTC day');
	expect(first.entries.map(({ label, value }) => [label, value])).toEqual([
		['Read', '0 tokens'], ['Written', 'No token reading.'], ['Run 1', 'failed']
	]);
	expect(first).toEqual(readoutView(readout, 0));
	expect(hoverReading({ name: 'tokens', readout }, 1)?.entries).toEqual([
		{ label: 'No token reading.', value: '', swatch: null, reserve: 0 }
	]);
});

test('record hover follows a visible tile offset and never invents a missing record', () => {
	const record = factsOf('Actual shard', [
		{ label: 'Seconds', value: 0, format: (value) => `${value} s` },
		{ label: 'Clock', value: null }
	], 'Not measured.');
	const source = { name: 'shards', readout: [null, record], offset: 1 };
	expect(hoverReading(source, 0)?.heading).toBe('Actual shard');
	expect(hoverReading(source, 0)?.entries.map(({ value }) => value)).toEqual(['0 s', 'Not measured.']);
	expect(hoverReading(source, 1)).toBeNull();
	expect(hoverReading({ name: 'absent', readout: null }, 0)).toBeNull();
	expect(hoverReading({ name: 'empty', readout: [] }, 0)).toBeNull();
});

test('a pointer reading fits inside the viewport and moves above a low pointer', () => {
	const viewport = { width: 390, height: 844 };
	const box = { width: 240, height: 120 };
	const corner = hoverPosition({ x: 380, y: 820 }, box, viewport, 12);
	expect(corner).toEqual({ left: 138, top: 688 });
	expect(corner.left + box.width).toBeLessThanOrEqual(viewport.width - 12);
	expect(corner.top + box.height).toBeLessThan(820);
	expect(hoverPosition({ x: 0, y: 0 }, box, viewport, 12)).toEqual({ left: 12, top: 12 });
});

test('disk-read captions qualify a same-run mix of locking requests without claiming none', async ({}, info) => {
	const compiled = serverCompiler(info.outputPath('disk-reads'));
	const rewrite: Rewrite[] = [
		['$lib/components/Panel.svelte', './Panel.server.mjs'],
		['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs'],
		...['charts/machine', 'charts/readout', 'charts/series', 'number-format-context', 'console/span-words', 'format']
			.map((file) => [`$lib/${file}`, new URL(`../src/lib/${file}.ts`, import.meta.url).href] as const)
	];
	await compiled('src/lib/components/Panel.svelte', 'Panel', rewrite);
	await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', rewrite);
	const module = await compiled('src/lib/console/machine/DiskReadsPanel.svelte', 'DiskReadsPanel', rewrite);
	const component = (await import(pathToFileURL(module).href)).default;
	const caption = (reads: DiskReads) => renderConfigured(component, {
		props: { reads, days: 14, windowDays: 14, readoutMaxShare: 1 }
	}).body.replace(/<!--[\s\S]*?-->/g, '')
		.match(/<p[^>]*data-disk-read-pinning="[^"]+"[^>]*>([\s\S]*?)<\/p>/)?.[1].trim();

	const rows = [
		{ date: '2026-09-04', run_id: '2026-09-04-1', weights_pinned: 'True' },
		{ date: '2026-09-04', run_id: '2026-09-04-1', weights_pinned: 'False' }
	];
	const marks = { marked: 1, named: 1 };
	const sameRun = diskReads(rows, marks);
	expect(sameRun.pinning).toEqual({ held: 0, loose: 1, silent: 0 });
	expect(caption(sameRun)).toBe('1 run included a recorded non-locking setting. Applied locking is unmeasured.');

	const acrossRuns = diskReads([
		...rows, { date: '2026-09-04', run_id: '2026-09-04-2', weights_pinned: 'True' }
	], marks);
	expect(acrossRuns.pinning).toEqual({ held: 1, loose: 1, silent: 0 });
	expect(caption(acrossRuns)).toBe('1 of 2 runs recorded only locking requests; 1 run included a non-locking setting. Applied locking is unmeasured.');
});

test.describe('rendered distribution readings', () => {
	let drawDistribution: (props: Record<string, unknown>) => string;
	let drawAge: (props: Record<string, unknown>) => string;
	test.beforeAll(async ({}, info) => {
		const compiled = serverCompiler(info.outputPath('distribution'));
		const rewrite: Rewrite[] = [
			['./EmptyState.svelte', './EmptyState.server.mjs'],
			['$lib/components/Reserved.svelte', './Reserved.server.mjs'],
			['$lib/charts/d3/Distribution.svelte', './Distribution.server.mjs'],
			['./article-age', new URL('../src/lib/console/pipelines/article-age.ts', import.meta.url).href]
		];
		await compiled('src/lib/components/Reserved.svelte', 'Reserved', rewrite);
		await compiled('src/lib/charts/d3/EmptyState.svelte', 'EmptyState', rewrite);
		const distributionModule = await compiled('src/lib/charts/d3/Distribution.svelte', 'Distribution', rewrite);
		const ageModule = await compiled('src/lib/console/pipelines/ArticleAge.svelte', 'ArticleAge', rewrite);
		const distributionComponent = (await import(pathToFileURL(distributionModule).href)).default;
		const ageComponent = (await import(pathToFileURL(ageModule).href)).default;
		const markup = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');
		drawDistribution = (props) => markup(renderConfigured(distributionComponent, { props }).body);
		drawAge = (props) => markup(renderConfigured(ageComponent, { props }).body);
	});

	test('the cumulative curve, rendered share, axis and mark ARIA use the same percentage units', () => {
		const geometry = distribution([1, 2, 2, 2], {
			frame: frame(600, 240), minValues: 4, valueTicks: 4, scale: 'linear',
			domain: [0, 2], number_format: numberFormat
		});
		if (geometry === null) throw new Error('Four measured readings must draw at the four-reading floor.');
		const html = drawDistribution({
			geometry, empty: emptyState('quiet', 'No readings.'), name: 'shares',
			label: 'Measured values and cumulative share', width: 600, height: 240
		});
		for (const bin of geometry.bins) {
			expect(html).toContain(`aria-label="${formatNumber(bin.x0)} to ${formatNumber(bin.x1)}: ${formatNumber(bin.count, { exact: true })} rows, ${formatNumber(bin.share, { si: false })}% at or below"`);
		}
		expect(html).toContain(`d="${geometry.cumulative}"`);
		expect(html).toMatch(/data-readout-row="share"[^>]*><dd[^>]*>At or below<\/dd><dd[^>]*>100%<\/dd>/);
		expect(html).toContain('>100%</text>');
		expect(html).not.toContain('10,000%');
	});

	test('source age names work start and retains successful feed times, exclusions and the logarithmic-zero note', () => {
		const knobs = consoleConfig();
		const feedTime = { time_source: 'feed', published_at: '2030-06-15T00:00:00Z' };
		const rows = [
			...Array.from({ length: knobs.fleet_min_rows }, () => ({
				...feedTime, outcome: 'ok', item_started_at: '2030-06-15T02:00:00Z'
			})),
			{ ...feedTime, outcome: 'ok', item_started_at: '2030-06-15T00:00:00Z' },
			{ ...feedTime, outcome: 'ok', time_source: 'first_seen', item_started_at: '2030-06-15T03:00:00Z' },
			{ ...feedTime, outcome: 'ok', item_started_at: '2030-06-14T23:00:00Z' },
			{ ...feedTime, outcome: 'ok', item_started_at: null },
			{ ...feedTime, outcome: 'failed', item_started_at: '2030-06-15T04:00:00Z' }
		];
		const html = drawAge({ rows, knobs });
		expect(html).toContain('data-chart-type="distribution"');
		expect(html).toContain('aria-label="Source age at work start in hours, logarithmic scale; inferred and future times excluded"');
		expect(html).toContain('Source age at work start: articles over a day old against newer ones');
		expect(html).toContain(`${knobs.fleet_min_rows + 1} source-stated publication times are measured.`);
		expect(html).toContain(`1 of ${knobs.fleet_min_rows + 4} successful items have inferred times`);
		expect(html).toContain('1 have no usable source time; 1 have a publication time after work started.');
		expect(html).toContain('1 items started at their stated publication time: zero hours has no position on a logarithmic axis');
		expect(html).not.toContain('when we published');
	});
});

test.describe('the strip is the key', () => {
	test('native dated marks build their key from the measured series', () => {
		const dates = ['2026-09-01', '2026-09-02'];
		const geometry = dateSeries([
			{ label: 'Fetch', token: '--chart-1', points: dates.map((date, index) => ({ date, value: [2, 1][index] })) },
			{ label: 'Extract', token: '--chart-2', points: dates.map((date, index) => ({ date, value: [1, 5][index] })) }
		], { frame: frame(600, 240), stacked: true, density: 6, valueTicks: 4, padding: 0.2, rule: { changes: [], note: null } });
		expect(geometry?.readout.columns).toEqual(dates);
		expect(geometry?.readout.series.map((one) => [one.label, one.swatch, one.values])).toEqual([
			['Fetch', 'var(--chart-1)', ['2', '1']],
			['Extract', 'var(--chart-2)', ['1', '5']]
		]);
	});

	test('dated readouts share the configured precision with their axes', () => {
		const values = [5_953, 0.0030226000000000003];
		for (const value of values) {
			const geometry = dateSeries([{
				label: 'Measured', token: '--chart-1',
				points: [{ date: '2026-09-01', value }]
			}], {
				frame: frame(600, 240), density: 6, valueTicks: 4, padding: 0.2,
				rule: { changes: [], note: null }
			});
			expect(geometry?.readout.series[0].values).toEqual([formatNumber(value)]);
		}
	});

	test('the native clock ranking retains both independently read instruments beside the gap', () => {
		const pairs = [
			{ label: 'shard 0', ledger: 12.5, server: 12.4, gapPct: 0.8, agrees: true },
			{ label: 'shard 1', ledger: 9.5, server: 9.9, gapPct: 4.0, agrees: true }
		];
		const geometry = clocksChart(pairs, 5, numberFormat);
		expect(geometry?.rows.map((row) => [row.label, row.value])).toEqual([['shard 1', 4], ['shard 0', 0.8]]);
		expect(geometry?.rules.map((rule) => rule.at)).toEqual([5]);
		expect(geometry?.rows.map((row) => row.row.value)).toEqual(['4%', '0.8%']);
		expect(geometry?.rows.map((row) => row.row.context)).toEqual([
			`item ledger ${formatNumber(9.5)}; server ${formatNumber(9.9)} tokens a second`,
			`item ledger ${formatNumber(12.5)}; server ${formatNumber(12.4)} tokens a second`
		]);
		const precise = clocksChart([{ label: 'shard', ledger: 3, server: 2.99, gapPct: 1 / 3, agrees: true }],
			5, { ...numberFormat, significant_digits: 2 });
		expect(precise?.rows[0].row.value).toBe('0.33%');
		expect(precise?.rows[0].value).toBe(1 / 3);
	});

	test('a strip is built from the labels, so it cannot be a different length', () => {
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue', 'Wed'],
			series: [
				{
					label: 'Read',
					swatch: 'var(--chart-1)',
					values: [0, 10, 20],
					format: (value) => `${value}`
				},
				{
					label: 'Written',
					swatch: 'var(--chart-4)',
					values: [0, 1, 2],
					format: (value) => `${value}`
				}
			],
			notMeasured: 'Nothing was read on this day',
			resting: 'last'
		});
		expect(strip.columns).toEqual(['Mon', 'Tue', 'Wed']);
		expect(strip.series.map((one) => [one.label, one.swatch, one.values[2]])).toEqual([
			['Read', 'var(--chart-1)', '20'],
			['Written', 'var(--chart-4)', '2']
		]);
		expect(strip.resting).toBe(2);
		// A series one reading short is one day's numbers under another day's
		// heading, so the builder refuses it rather than printing it.
		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon', 'Tue'],
				series: [{ label: 'Read', swatch: null, values: [1], format: String }],
				notMeasured: 'Nothing was read on this day',
				resting: 'last'
			})
		).toThrow(/1 readings for 2 columns/);
	});

	test('a missing reading prints the not-measured word, never a dash or a zero', () => {
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue'],
			series: [
				{ label: 'Read', swatch: null, values: [null, 4], format: String },
				{ label: 'Never read', swatch: null, values: [null, null], format: String }
			],
			notMeasured: 'Nothing was read on this day',
			resting: 'newest'
		});
		expect(strip.series[0].values).toEqual([null, '4']);
		expect(strip.notMeasured).toBe('Nothing was read on this day');
		// A key for a series the window never measured is a claim the data does
		// not support, so it has no entry at all.
		expect(strip.series.map((one) => one.label)).toEqual(['Read']);
		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon'],
				series: [{ label: 'Read', swatch: null, values: ['-'], format: String }],
				notMeasured: 'Nothing was read on this day',
				resting: 'last'
			})
		).toThrow(/hand null/);
	});

	test("a column's own reason overrides the shared not-measured word", () => {
		// Judgement's agreement chart carries two reasons a column holds no
		// reading: a day whose row read no pair, and a day with no row at all
		// (row L55). One word for every chart that does not need the distinction,
		// a reason per column for the one that does.
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue', 'Wed'],
			series: [{ label: 'Read', swatch: null, values: [1, null, null], format: String }],
			notMeasured: 'Nothing was read on this day',
			notMeasuredAt: [null, 'No readings came in for this day', null],
			resting: 'first'
		});
		// Omitted at Mon, where there is a reading to print instead. Named at
		// Tue. Falls back to the shared word at Wed, where the chart named none.
		expect(strip.notMeasuredAt).toEqual([null, 'No readings came in for this day', null]);

		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon', 'Tue'],
				series: [{ label: 'Read', swatch: null, values: [null, null], format: String }],
				notMeasured: 'Nothing was read on this day',
				notMeasuredAt: [null],
				resting: 'last'
			})
		).toThrow(/1 reasons for 2 columns/);
	});
});
