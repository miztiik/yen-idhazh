import { expect, test } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { chooseDateSeriesDays, chooseExplorerShape, chooseExplorerShapes, type ExplorerChartType, type ExplorerShapeBounds } from '../src/lib/console/explorer/shape';
import type { Column, Row } from '../src/lib/data/slice-shapes';
import { serverCompiler } from './support/server-render';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const bounds: ExplorerShapeBounds = {
	chartMinRows: 3,
	rankMax: 3,
	fleetMinRows: 4,
	bandwidthMinKinds: 3,
	seriesFloorShare: 0.05
};

function shape(columns: readonly Column[], rows: readonly Row[]) {
	return chooseExplorerShape(columns, rows, bounds);
}

test('the five documented answer cases choose their chart type or neutral sentence', () => {
	expect(shape([
		{ name: 'day', type: 'DATE' },
		{ name: 'scored', type: 'INTEGER' }
	], [
		{ day: '2026-10-01', scored: 3 },
		{ day: '2026-10-02', scored: 5 },
		{ day: '2026-10-03', scored: 8 }
	])).toMatchObject({ kind: 'chart', type: 'dateSeries', dateColumn: 'day', seriesColumns: ['scored'], tooFew: false });

	expect(shape([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ source: 'a', items: 5 },
		{ source: 'b', items: 2 },
		{ source: 'c', items: 1 },
		{ source: 'd', items: 1 }
	])).toMatchObject({ kind: 'chart', type: 'rankedList', labelColumn: 'source', valueColumn: 'items', rowsDrawn: 3, moreRows: 1 });

	expect(shape([
		{ name: 'host', type: 'VARCHAR' },
		{ name: 'ms', type: 'DOUBLE' },
		{ name: 'tokens', type: 'DOUBLE' }
	], [
		{ host: 'a', ms: 10, tokens: 100 },
		{ host: 'b', ms: 20, tokens: 150 },
		{ host: 'c', ms: 30, tokens: 120 },
		{ host: 'd', ms: 40, tokens: 90 }
	])).toMatchObject({ kind: 'chart', type: 'pairedScatter', xColumn: 'ms', yColumn: 'tokens', subjectColumn: 'host', tooFew: false });

	expect(shape([
		{ name: 'latency', type: 'DOUBLE' }
	], [
		{ latency: 10 },
		{ latency: 20 },
		{ latency: 30 },
		{ latency: 40 }
	])).toMatchObject({ kind: 'chart', type: 'distribution', valueColumn: 'latency', median: 25, tooFew: false });

	expect(shape([
		{ name: 'source', type: 'VARCHAR' }
	], [{ source: 'a' }])).toEqual({
		kind: 'none',
		code: 'no-number',
		reason: 'Nothing here to draw: the answer has no number in it.'
	});
});

test('cells arrive as text, as the door returns them, and still give each chart its figures', () => {
	// The door casts every cell to text (plan section 2.5 rule 8). Fixtures with JavaScript
	// numbers hid that the main figures read none of them.
	expect(shape([
		{ name: 'day', type: 'DATE' },
		{ name: 'scored', type: 'INTEGER' }
	], [
		{ day: '2026-10-01', scored: '3' },
		{ day: '2026-10-02', scored: '5' },
		{ day: '2026-10-03', scored: '8' }
	])).toMatchObject({ type: 'dateSeries', mainFigure: { column: 'scored', value: 8, date: '2026-10-03' } });

	expect(shape([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'items', type: 'BIGINT' }
	], [
		{ source: 'a', items: '5' },
		{ source: 'b', items: '12' },
		{ source: 'c', items: '1' }
	])).toMatchObject({ type: 'rankedList', mainFigure: { label: 'b', value: 12, column: 'items' } });

	expect(shape([
		{ name: 'latency', type: 'DOUBLE' }
	], [
		{ latency: '10.5' },
		{ latency: 'null' },
		{ latency: '30.5' },
		{ latency: null },
		{ latency: '20.5' }
	])).toMatchObject({ type: 'distribution', median: 20.5, mainFigure: 'Half of latency is at or under 20.5' });

	expect(shape([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'change', type: 'INTEGER' }
	], [
		{ source: 'a', change: '4' },
		{ source: 'b', change: '-2' },
		{ source: 'c', change: '1' },
		{ source: 'd', change: '3' }
	]), 'a negative number in text is negative, so the answer is not ranked').toMatchObject({ type: 'distribution' });
});

test('a date answer with several rows on one UTC day draws no date chart and says why', () => {
	expect(shape([
		{ name: 'day', type: 'TIMESTAMP' },
		{ name: 'items', type: 'INTEGER' },
		{ name: 'source', type: 'VARCHAR' }
	], [
		{ day: '2026-10-02 01:00:00', items: 1, source: 'a' },
		{ day: '2026-10-02 02:00:00', items: 2, source: 'b' }
	])).toEqual({
		kind: 'none',
		code: 'several-rows-per-day',
		reason: 'Nothing here to draw: the answer has several rows a UTC day. Group by day in the question to draw it over time.'
	});
});

test('date charts draw four number columns and name columns that would draw flat', () => {
	const result = shape([
		{ name: 'day', type: 'DATE' },
		{ name: 'a', type: 'INTEGER' },
		{ name: 'b', type: 'INTEGER' },
		{ name: 'c', type: 'INTEGER' },
		{ name: 'd', type: 'INTEGER' },
		{ name: 'e', type: 'INTEGER' },
		{ name: 'tiny', type: 'INTEGER' }
	], [
		{ day: '2026-10-01', a: 100, b: 80, c: 60, d: 40, e: 20, tiny: 1 },
		{ day: '2026-10-02', a: 90, b: 70, c: 50, d: 30, e: 10, tiny: 2 },
		{ day: '2026-10-03', a: 80, b: 60, c: 40, d: 20, e: 5, tiny: 3 }
	]);
	expect(result).toMatchObject({
		kind: 'chart',
		type: 'dateSeries',
		seriesColumns: ['a', 'b', 'c', 'd'],
		omittedColumns: ['e'],
		flatColumns: [{ name: 'tiny', share: 0.03, largestColumn: 'a' }]
	});
});

test('a lost day between the days an answer has rows for joins the date axis with no row', () => {
	const rows: Row[] = [
		{ day: '2026-08-20', rows: '8' },
		{ day: '2026-08-17', rows: '3' },
		{ day: '2026-08-18', rows: '5' }
	];
	expect(chooseDateSeriesDays('day', rows, ['2026-08-19'])).toEqual([
		{ day: '2026-08-17', row: rows[1] },
		{ day: '2026-08-18', row: rows[2] },
		{ day: '2026-08-19', row: null },
		{ day: '2026-08-20', row: rows[0] }
	]);
});

test('a lost day outside the answer\'s first and last day, or one the answer has a row for, adds no day', () => {
	const rows: Row[] = [
		{ day: '2026-08-17', rows: '3' },
		{ day: '2026-08-18', rows: '5' },
		{ day: '2026-08-20', rows: '8' }
	];
	// Two ledgers both lost 19 Aug. One of them also lost 18 Aug, which still has a row, and a day at each end.
	const days = chooseDateSeriesDays('day', rows, ['2026-08-16', '2026-08-18', '2026-08-19', '2026-08-19', '2026-08-21']);
	expect(days.map(({ day, row }) => [day, row?.rows ?? null])).toEqual([
		['2026-08-17', '3'],
		['2026-08-18', '5'],
		['2026-08-19', null],
		['2026-08-20', '8']
	]);
	expect(chooseDateSeriesDays('day', [], ['2026-08-19']), 'lost days alone draw nothing').toEqual([]);
});

test('a timestamp answer sits on the date axis by its UTC day', () => {
	const rows: Row[] = [
		{ day: '2026-08-17 00:00:00', rows: '3' },
		{ day: '2026-08-19 00:00:00', rows: '8' }
	];
	expect(chooseDateSeriesDays('day', rows, ['2026-08-18']).map(({ day, row }) => [day, row?.rows ?? null])).toEqual([
		['2026-08-17', '3'],
		['2026-08-18', null],
		['2026-08-19', '8']
	]);
});

test('no-chart reasons follow the first matching documented case', () => {
	expect(shape([
		{ name: 'a', type: 'INTEGER' },
		{ name: 'b', type: 'INTEGER' },
		{ name: 'c', type: 'INTEGER' }
	], [{ a: 1, b: 2, c: 3 }])).toEqual({
		kind: 'none',
		code: 'too-many-numbers',
		reason: 'Nothing here to draw: 3 number columns are more than one chart can show. Keep one or two in the question.'
	});

	expect(shape([
		{ name: 'x', type: 'INTEGER' },
		{ name: 'y', type: 'INTEGER' },
		{ name: 'name', type: 'VARCHAR' },
		{ name: 'family', type: 'VARCHAR' }
	], [{ x: 1, y: 2, name: 'a', family: 'b' }])).toEqual({
		kind: 'none',
		code: 'too-many-text-columns',
		reason: 'Nothing here to draw: two number columns pair up with at most one text column naming each point, and this answer has 2.'
	});
});

test('an answer can qualify for more than one chart type for the operator switch', () => {
	const result = chooseExplorerShapes([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ source: 'a', items: 5 },
		{ source: 'b', items: 2 },
		{ source: 'c', items: 1 }
	], bounds);
	expect(result.map((shape) => shape.kind === 'chart' ? shape.type : shape.code)).toEqual(['rankedList', 'distribution']);
	expect(chooseExplorerShape([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ source: 'a', items: 5 },
		{ source: 'b', items: 2 },
		{ source: 'c', items: 1 }
	], bounds)).toMatchObject({ kind: 'chart', type: 'rankedList' });
});

test('a NULL is no reading: the spread and paired floors, the paired figure and the ranked tail count only rows with a number', () => {
	expect(shape([{ name: 'latency', type: 'DOUBLE' }], [
		{ latency: '10' },
		{ latency: null },
		{ latency: '20' },
		{ latency: '30' }
	])).toMatchObject({ type: 'distribution', readings: 3, tooFew: true });

	expect(shape([
		{ name: 'host', type: 'VARCHAR' },
		{ name: 'ms', type: 'DOUBLE' },
		{ name: 'tokens', type: 'DOUBLE' }
	], [
		{ host: 'a', ms: '10', tokens: '100' },
		{ host: 'b', ms: null, tokens: '150' },
		{ host: 'c', ms: '30', tokens: '120' },
		{ host: 'd', ms: '40', tokens: null },
		{ host: 'e', ms: '50', tokens: '90' }
	])).toMatchObject({ type: 'pairedScatter', readings: 3, subjects: 3, tooFew: true, mainFigure: '3 rows of tokens against ms' });

	expect(shape([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ source: 'a', items: '5' },
		{ source: 'b', items: null },
		{ source: 'c', items: '1' }
	])).toMatchObject({ type: 'rankedList', rowsDrawn: 2, moreRows: 1 });
});

test.describe('the chart panel draws a NULL as no value, never as zero', () => {
	let draw: (columns: readonly Column[], rows: readonly Row[], selectedType: ExplorerChartType) => string;

	test.beforeAll(async ({}, testInfo) => {
		// One directory a worker: a module rewritten while another worker imports it is read half-written.
		const compiled = serverCompiler(path.join(frontend, 'test-results', 'explorer-shape-panel', String(testInfo.workerIndex)));
		await compiled('src/lib/components/Reserved.svelte', 'Reserved', []);
		await compiled('src/lib/charts/d3/EmptyState.svelte', 'EmptyState', [['$lib/components/Reserved.svelte', './Reserved.server.mjs']]);
		await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
		for (const chart of ['DateSeries', 'Distribution', 'PairedScatter']) {
			await compiled(`src/lib/charts/d3/${chart}.svelte`, chart, [
				['./EmptyState.svelte', './EmptyState.server.mjs'],
				['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs']
			]);
		}
		await compiled('src/lib/components/RankedList.svelte', 'RankedList', []);
		const panel = await compiled('src/lib/console/explorer/ShapePanel.svelte', 'ShapePanel', [
			['$lib/charts/d3/DateSeries.svelte', './DateSeries.server.mjs'],
			['$lib/charts/d3/Distribution.svelte', './Distribution.server.mjs'],
			['$lib/charts/d3/PairedScatter.svelte', './PairedScatter.server.mjs'],
			['$lib/components/RankedList.svelte', './RankedList.server.mjs'],
			['./shape', '$lib/console/explorer/shape'],
			['./answer', '$lib/console/explorer/answer']
		]);
		const component = (await import(pathToFileURL(panel).href)).default;
		draw = (columns, rows, selectedType) => render(component, { props: { columns, rows, lostDays: [], bounds, height: 200, selectedType } }).body;
	});

	test('the ranked list leaves the NULL row out and says it is in the table', () => {
		const body = draw([{ name: 'source', type: 'VARCHAR' }, { name: 'items', type: 'INTEGER' }], [
			{ source: 'a', items: '5' },
			{ source: 'b', items: null },
			{ source: 'c', items: '1' }
		], 'rankedList');
		expect(body.match(/data-ranked-row="[^"]*"/g)).toEqual(['data-ranked-row="a"', 'data-ranked-row="c"']);
		expect(body).toContain('1 more row is in the table.');
	});

	test('the paired chart draws no point for a row with a NULL', () => {
		const body = draw([{ name: 'host', type: 'VARCHAR' }, { name: 'ms', type: 'DOUBLE' }, { name: 'tokens', type: 'DOUBLE' }], [
			{ host: 'a', ms: '10', tokens: '100' },
			{ host: 'b', ms: '20', tokens: '150' },
			{ host: 'c', ms: '30', tokens: '120' },
			{ host: 'd', ms: '40', tokens: '90' },
			{ host: 'e', ms: null, tokens: '60' }
		], 'pairedScatter');
		expect(body).toContain('data-readout-records="4"');
		expect(body).toContain('4 rows of tokens against ms');
	});

	test('the spread chart counts no NULL among the readings in its bins', () => {
		const body = draw([{ name: 'latency', type: 'DOUBLE' }], [
			{ latency: '10' },
			{ latency: '20' },
			{ latency: null },
			{ latency: '30' },
			{ latency: '40' }
		], 'distribution');
		const binned = [...body.matchAll(/aria-label="[^"]*: (\d+) rows, /g)].map((bin) => Number(bin[1]));
		expect(binned.length, 'no bin was drawn').toBeGreaterThan(0);
		expect(binned.reduce((sum, count) => sum + count, 0)).toBe(4);
	});

	test('the date chart breaks its line at a day whose number is NULL', () => {
		const body = draw([{ name: 'day', type: 'DATE' }, { name: 'rows', type: 'INTEGER' }], [
			{ day: '2026-08-17', rows: '3' },
			{ day: '2026-08-18', rows: '5' },
			{ day: '2026-08-19', rows: null },
			{ day: '2026-08-20', rows: '8' },
			{ day: '2026-08-21', rows: '9' }
		], 'dateSeries');
		const line = body.match(/data-date-series-marks="data-explorer-shape"[\s\S]*?<path d="([^"]*)"/)?.[1] ?? '';
		expect(line.match(/M/g)?.length, 'the line joined the days either side of the NULL').toBe(2);
	});

	test('a floor counts readings, so a NULL can leave a chart too few to draw, and the sentence names the floor it missed', () => {
		expect(draw([{ name: 'latency', type: 'DOUBLE' }], [
			{ latency: '10' },
			{ latency: '20' },
			{ latency: null },
			{ latency: '30' }
		], 'distribution')).toContain('Only 3 of the 4 readings this chart needs are in this window, so it is not drawn.');

		expect(draw([{ name: 'host', type: 'VARCHAR' }, { name: 'ms', type: 'DOUBLE' }, { name: 'tokens', type: 'DOUBLE' }], [
			{ host: 'a', ms: '10', tokens: '100' },
			{ host: 'a', ms: '20', tokens: '150' },
			{ host: 'b', ms: '30', tokens: '120' },
			{ host: 'b', ms: '40', tokens: '90' },
			{ host: 'c', ms: null, tokens: '60' }
		], 'pairedScatter')).toContain('Only 2 of the 3 subjects this chart needs are in this window, so it is not drawn.');
	});
});
