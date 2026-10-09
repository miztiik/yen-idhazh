import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { chartNotes, chooseChart, chooseDateSeriesDays, countChartNotes, openingType, resolveRoles, type ChosenRoles, type ExplorerChartType, type ExplorerShapeBounds } from '../src/lib/console/explorer/shape';
import { AT_MOST_SENTENCE, CHART_KINDS, MOST_ROLES, SERIES_TOKENS, chartKind, pillFace, pillName, roleOptions } from '../src/lib/console/explorer/chart-roles';
import { roleRowLines, roleSlotsPerLine } from '../src/lib/console/explorer/role-row';
import { tooFewSentence } from '../src/lib/console/waiting';
import { iconsConfig } from '../src/lib/server/config';
import type { Column, Row } from '../src/lib/data/slice-shapes';
import { inZone } from './support/in-zone';
import { serverCompiler } from './support/server-render';
import { partsOfOne } from '../src/lib/charts/d3/partsOfOne';
import { tileStrip } from '../src/lib/charts/d3/tileStrip';
import { flow } from '../src/lib/charts/d3/flow';
import { frame } from '../src/lib/charts/frame';
import { truthValue } from '../src/lib/console/explorer/shape';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const bounds: ExplorerShapeBounds = {
	chartMinRows: 3,
	rankMax: 3,
	fleetMinRows: 4,
	bandwidthMinKinds: 3,
	seriesFloorShare: 0.05
};

/** What the Chart tab's box draws for an answer before the reader chooses anything. */
function shape(columns: readonly Column[], rows: readonly Row[]) {
	return chooseChart(columns, rows, bounds).shape;
}

/** The chart an answer opens on, and the columns each of its roles holds, by role word. */
function opened(columns: readonly Column[], rows: readonly Row[], type: ExplorerChartType | null = null, roles: ChosenRoles = {}) {
	const chart = chooseChart(columns, rows, bounds, type, roles);
	return { type: chart.type, roles: Object.fromEntries(chart.roles.map((state) => [state.role.word, state.chosen])) };
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

test('a date answer with several rows on one UTC day draws no date chart and says why, naming the column', () => {
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
		reason: 'Nothing here to draw: the answer has several rows a UTC day in "day". Group by day in the question to draw it over time.'
	});
});

test('a date column holding a day the chart cannot place draws no date chart and names the column and that day', () => {
	const held: [string, string][] = [
		['infinity', 'Nothing here to draw: the column "day" holds infinity, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.'],
		['-infinity', 'Nothing here to draw: the column "day" holds -infinity, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.'],
		['12345-01-01', 'Nothing here to draw: the column "day" holds 12345-01-01, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.'],
		['0044-03-15 (BC)', 'Nothing here to draw: the column "day" holds 0044-03-15 (BC), and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.']
	];
	for (const [day, reason] of held) {
		expect(shape([
			{ name: 'day', type: 'DATE' },
			{ name: 'items', type: 'INTEGER' }
		], [
			{ day: '2026-10-01', items: '1' },
			{ day, items: '2' },
			{ day: '2026-10-03', items: '3' }
		]), day).toEqual({ kind: 'none', code: 'unplaceable-day', reason });
	}

	// A NULL is no day rather than a day the chart cannot place, so the sentence names the value after it.
	expect(shape([
		{ name: 'day', type: 'DATE' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ day: null, items: '1' },
		{ day: 'infinity', items: '2' },
		{ day: '2026-10-03', items: '3' }
	])).toEqual({
		kind: 'none',
		code: 'unplaceable-day',
		reason: 'Nothing here to draw: the column "day" holds infinity, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.'
	});

	expect(shape([
		{ name: 'at', type: 'TIMESTAMP WITH TIME ZONE' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ at: '2026-10-01 00:00:00+00', items: '1' },
		{ at: 'infinity', items: '2' }
	])).toEqual({
		kind: 'none',
		code: 'unplaceable-day',
		reason: 'Nothing here to draw: the column "at" holds infinity, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.'
	});
});

test('a row whose day is NULL is left out of the date chart, and every figure counts only the rows with a day', () => {
	const columns: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'items', type: 'INTEGER' }];
	expect(shape(columns, [
		{ day: '2026-10-01', items: '3' },
		{ day: null, items: '40' },
		{ day: '2026-10-02', items: '5' },
		{ day: '2026-10-03', items: '8' }
	])).toMatchObject({ kind: 'chart', type: 'dateSeries', days: 3, rowsWithNoDay: 1, tooFew: false, mainFigure: { column: 'items', value: 8, date: '2026-10-03' } });

	expect(shape(columns, [
		{ day: '2026-10-01', items: '3' },
		{ day: null, items: '4' },
		{ day: '2026-10-02', items: '5' }
	]), 'two days and a row with no day are under a floor of three days').toMatchObject({ type: 'dateSeries', days: 2, rowsWithNoDay: 1, tooFew: true });

	expect(shape(columns, [
		{ day: null, items: '1' },
		{ day: '2026-10-01', items: '3' },
		{ day: null, items: '2' },
		{ day: '2026-10-02', items: '5' },
		{ day: '2026-10-03', items: '8' }
	]), 'two rows with no day are not two rows on one UTC day').toMatchObject({ type: 'dateSeries', days: 3, rowsWithNoDay: 2 });

	expect(shape([
		{ name: 'day', type: 'DATE' },
		{ name: 'a', type: 'INTEGER' },
		{ name: 'b', type: 'INTEGER' }
	], [
		{ day: '2026-10-01', a: '100', b: '80' },
		{ day: '2026-10-02', a: '90', b: '70' },
		{ day: null, a: '100000', b: '1' },
		{ day: '2026-10-03', a: '80', b: '60' }
	]), 'a number on a row with no day makes no other column too flat to draw').toMatchObject({ seriesColumns: ['a', 'b'], flatColumns: [] });
});

test('a date column that holds only NULL draws no chart and says so', () => {
	expect(shape([
		{ name: 'day', type: 'DATE' },
		{ name: 'items', type: 'INTEGER' }
	], [
		{ day: null, items: '1' },
		{ day: null, items: '2' }
	])).toEqual({
		kind: 'none',
		code: 'no-day',
		reason: 'Nothing here to draw: the column "day" holds only null. Give "day" a date in the question to draw it over time.'
	});

	expect(shape([
		{ name: 'at', type: 'TIMESTAMP WITH TIME ZONE' },
		{ name: 'items', type: 'BIGINT' }
	], [{ at: null, items: '1' }])).toEqual({
		kind: 'none',
		code: 'no-day',
		reason: 'Nothing here to draw: the column "at" holds only null. Give "at" a date in the question to draw it over time.'
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

test('a timestamp with a time zone sits on the date axis by its UTC day, not the day the engine printed', () => {
	// On a page in India the engine prints a fixed +05, so 23:30 UTC on 16 Aug prints as 04:30 on 17 Aug.
	inZone('Asia/Kolkata', () => {
		expect(new Date('2026-08-17T00:00:00Z').getTimezoneOffset(), 'the run is not in India time').toBe(-330);
		const columns: Column[] = [{ name: 'at', type: 'TIMESTAMP WITH TIME ZONE' }, { name: 'rows', type: 'BIGINT' }];
		const rows: Row[] = [{ at: '2026-08-17 04:30:00+05', rows: '3' }, { at: '2026-08-17 06:00:00+05', rows: '5' }];
		expect(chooseDateSeriesDays('at', rows, []).map(({ day, row }) => [day, row?.rows ?? null])).toEqual([['2026-08-16', '3'], ['2026-08-17', '5']]);
		expect(shape(columns, rows)).toMatchObject({ kind: 'chart', type: 'dateSeries', mainFigure: { column: 'rows', value: 5, date: '2026-08-17' } });
		// 23:00 UTC on the last day of 1969, an instant before 1970, stays on that day.
		expect(chooseDateSeriesDays('at', [{ at: '1970-01-01 04:00:00+05', rows: '1' }], []).map(({ day }) => day)).toEqual(['1969-12-31']);
	});
});

test('where the page picks no chart, the box says the reader can choose one, in place of the old advice to drop columns', () => {
	// Three number columns, and two number columns with two text columns, were the old "too many"
	// cases. The reader can now choose a chart and its columns, so the box says so (Susan's B3).
	const notPicked = {
		kind: 'none',
		code: 'not-picked',
		reason: 'The page does not pick a chart for these columns. Choose one under Draw it as.'
	};
	expect(shape([
		{ name: 'a', type: 'INTEGER' },
		{ name: 'b', type: 'INTEGER' },
		{ name: 'c', type: 'INTEGER' }
	], [{ a: 1, b: 2, c: 3 }])).toEqual(notPicked);

	expect(shape([
		{ name: 'x', type: 'INTEGER' },
		{ name: 'y', type: 'INTEGER' },
		{ name: 'name', type: 'VARCHAR' },
		{ name: 'family', type: 'VARCHAR' }
	], [{ x: 1, y: 2, name: 'a', family: 'b' }])).toEqual(notPicked);
	expect(chooseChart([{ name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }, { name: 'c', type: 'INTEGER' }], [{ a: 1, b: 2, c: 3 }], bounds).type, 'a tile was checked').toBeNull();
});

test('an answer the page ranks can be drawn as a spread on the reader\'s press, with nothing fetched', () => {
	const columns: Column[] = [{ name: 'source', type: 'VARCHAR' }, { name: 'items', type: 'INTEGER' }];
	const rows: Row[] = [{ source: 'a', items: 5 }, { source: 'b', items: 2 }, { source: 'c', items: 1 }];
	expect(chooseChart(columns, rows, bounds)).toMatchObject({ type: 'rankedList', shape: { kind: 'chart', type: 'rankedList' } });
	expect(chooseChart(columns, rows, bounds, 'distribution')).toMatchObject({ type: 'distribution', shape: { kind: 'chart', type: 'distribution', valueColumn: 'items' } });
});

test('a timestamp of any precision is a day column, so a TIMESTAMP_NS day column draws over time', () => {
	for (const type of ['TIMESTAMP_S', 'TIMESTAMP_MS', 'TIMESTAMP_NS']) {
		expect(shape([
			{ name: 'day', type },
			{ name: 'rows', type: 'BIGINT' }
		], [
			{ day: '2026-08-17 00:00:00', rows: '3' },
			{ day: '2026-08-18 00:00:00', rows: '5' },
			{ day: '2026-08-19 00:00:00', rows: '8' }
		]), type).toMatchObject({ kind: 'chart', type: 'dateSeries', dateColumn: 'day', seriesColumns: ['rows'] });
	}
});

test('an enum names a ranked row, as text does', () => {
	expect(shape([
		{ name: 'verdict', type: "ENUM('kept', 'cut')" },
		{ name: 'items', type: 'BIGINT' }
	], [
		{ verdict: 'kept', items: '5' },
		{ verdict: 'cut', items: '2' }
	])).toMatchObject({ kind: 'chart', type: 'rankedList', labelColumn: 'verdict', valueColumn: 'items' });
});

test('every whole number the engine prints is a number to the chart, and a list of numbers is not one', () => {
	for (const type of ['UHUGEINT', 'BIGNUM']) {
		expect(shape([
			{ name: 'source', type: 'VARCHAR' },
			{ name: 'n', type }
		], [
			{ source: 'a', n: '5' },
			{ source: 'b', n: '2' }
		]), type).toMatchObject({ kind: 'chart', type: 'rankedList', valueColumn: 'n' });
	}
	expect(shape([
		{ name: 'source', type: 'VARCHAR' },
		{ name: 'shares', type: 'DECIMAL(18,4)[]' }
	], [{ source: 'a', shares: '[0.5000, 0.2500]' }])).toEqual({
		kind: 'none',
		code: 'no-number',
		reason: 'Nothing here to draw: the answer has no number in it.'
	});
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
	let draw: (columns: readonly Column[], rows: readonly Row[], selectedType: ExplorerChartType | null, roles?: ChosenRoles, capped?: boolean, lostDays?: readonly string[]) => string;
	let pick: (props: Record<string, unknown>) => string;

	/** The path of the date chart's first series: one `M` for each run of days it joins. */
	function dateLine(body: string): string {
		return body.match(/data-date-series-marks="data-explorer-shape"[\s\S]*?<path d="([^"]*)"/)?.[1] ?? '';
	}

	/** The words of the panel's main figure, footnote or no-chart box, as the page prints them. */
	function printed(body: string, part: 'shape-foot' | 'shape-lede' | 'shape-none'): string | undefined {
		return body.match(new RegExp(`class="${part}[^"]*"[^>]*>([^<]*)<`))?.[1];
	}

	/** Every note the foot under the drawing prints, in order. */
	function footNotes(body: string): string[] {
		return [...body.matchAll(/class="shape-foot[^"]*"[^>]*>([^<]*)</g)].map((note) => note[1]);
	}

	test.beforeAll(async ({}, testInfo) => {
		// The build defines the icon line weight from config (`vite.config.ts`); a component rendered outside the build needs the same global.
		Object.assign(globalThis, { __ICON_STROKE_PX__: iconsConfig().stroke_px });
		// One directory a worker: a module rewritten while another worker imports it is read half-written.
		const compiled = serverCompiler(path.join(frontend, 'test-results', 'explorer-shape-panel', String(testInfo.workerIndex)));
		await compiled('src/lib/components/Reserved.svelte', 'Reserved', []);
		await compiled('src/lib/charts/d3/EmptyState.svelte', 'EmptyState', [['$lib/components/Reserved.svelte', './Reserved.server.mjs']]);
		await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
		for (const chart of ['DateSeries', 'Distribution', 'PairedScatter', 'PartsOfOne', 'TileStrip', 'Flow']) {
			await compiled(`src/lib/charts/d3/${chart}.svelte`, chart, [
				['./EmptyState.svelte', './EmptyState.server.mjs'],
				['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs']
			]);
		}
		await compiled('src/lib/components/RankedList.svelte', 'RankedList', []);
		await compiled('src/lib/icons/Icon.svelte', 'Icon', [['./generated', '$lib/icons/generated']]);
		await compiled('src/lib/console/explorer/ColumnType.svelte', 'ColumnType', []);
		const picker = await compiled('src/lib/console/explorer/ColumnPicker.svelte', 'ColumnPicker', [
			['$lib/icons/Icon.svelte', './Icon.server.mjs'],
			['$lib/console/explorer/ColumnType.svelte', './ColumnType.server.mjs']
		]);
		const panel = await compiled('src/lib/console/explorer/ShapePanel.svelte', 'ShapePanel', [
			['$lib/charts/d3/DateSeries.svelte', './DateSeries.server.mjs'],
			['$lib/charts/d3/Distribution.svelte', './Distribution.server.mjs'],
			['$lib/charts/d3/PairedScatter.svelte', './PairedScatter.server.mjs'],
			['$lib/charts/d3/PartsOfOne.svelte', './PartsOfOne.server.mjs'],
			['$lib/charts/d3/TileStrip.svelte', './TileStrip.server.mjs'],
			['$lib/charts/d3/Flow.svelte', './Flow.server.mjs'],
			['$lib/components/RankedList.svelte', './RankedList.server.mjs'],
			['$lib/console/explorer/ColumnPicker.svelte', './ColumnPicker.server.mjs'],
			['./shape', '$lib/console/explorer/shape'],
			['./answer', '$lib/console/explorer/answer']
		]);
		const component = (await import(pathToFileURL(panel).href)).default;
		draw = (columns, rows, selectedType, roles = {}, capped = false, lostDays = []) => render(component, {
			props: { chart: chooseChart(columns, rows, bounds, selectedType, roles), columns, rows, lostDays, bounds, floorHeight: 200, capped, maxRows: 1000, onRoles: () => {} }
		}).body;
		const pickerComponent = (await import(pathToFileURL(picker).href)).default;
		pick = (props) => render(pickerComponent, { props: { onChange: () => {}, ...props } }).body;
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

	test('the three added charts draw shared geometry, carry readouts and no native tooltip', () => {
		const columns: Column[] = [{ name: 'stage', type: 'VARCHAR' }, ...['arrived', 'went', 'lost'].map((name) => ({ name, type: 'INTEGER' }))];
		const rows: Row[] = [{ stage: 'first', arrived: '10', went: '8', lost: '2' }, { stage: 'last', arrived: '8', went: '6', lost: '2' }];
		const bars = draw(columns, rows, 'partsOfOne');
		const geometry = partsOfOne(rows.map((row) => ({ label: String(row.stage), parts: ['arrived', 'went', 'lost'].map((label) => ({ label, value: Number(row[label]) })) })), { order: ['arrived', 'went', 'lost'], overlapping: true, tokens: SERIES_TOKENS });
		expect(bars).toContain('data-parts-overlapping="yes"');
		expect(bars).not.toContain('class="parts-total"');
		for (const row of geometry!.rows) for (const segment of row.segments) expect(bars).toContain(`inline-size: ${segment.size}`);
		expect(bars).toContain('first: 10 arrived');
		const listed = draw(columns, rows, 'flow');
		const shared = flow(rows.map((row) => ({ label: String(row.stage), arrived: Number(row.arrived), left: Number(row.went), drops: [{ label: 'lost', count: Number(row.lost) }] })), { frame: frame(760, 200), narrow: true, nodeWidth: 12, nodeGap: 8 });
		expect(shared?.kind).toBe('stepped');
		expect(listed).toContain('data-flow-shape="stepped"');
		expect(listed).toContain('6 of 10 went through every stage');
		const unbalanced = draw(columns, [{ ...rows[0], went: '9' }, rows[1]], 'flow');
		expect(unbalanced).toContain('first counts 10 arriving and 11 leaving, so the counts are not one flow and the stages are listed rather than drawn.');
		const dates: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'ok', type: 'BOOLEAN' }];
		const days: Row[] = [{ day: '2026-10-01', ok: 'true' }, { day: '2026-10-02', ok: 'false' }, { day: '2026-10-03', ok: null }];
		const tiles = draw(dates, days, 'tileStrip');
		const strip = tileStrip(days.map((row) => ({ date: String(row.day), state: truthValue(row, 'ok') === null ? 'absent' : truthValue(row, 'ok') ? 'fired' : 'quiet' })));
		for (const tile of strip!.tiles) expect(tiles).toContain(`data-tile-state="${tile.state}"`);
		expect(tiles).toContain('"ok" was true on 1 of 3 UTC days');
		for (const body of [bars, listed, tiles]) {
			expect(body).toContain('data-readout="data-explorer-shape"');
			expect(body).not.toMatch(/\stitle=|<title>/);
		}
	});

	test('Which days keeps a lost day and NULL absent, and side-by-side NULL omits only its bar', () => {
		const columns: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'ok', type: 'BOOLEAN' }];
		const tiles = draw(columns, [{ day: '2026-10-01', ok: 'true' }, { day: '2026-10-03', ok: null }, { day: '2026-10-04', ok: 'false' }], 'tileStrip', {}, false, ['2026-10-02']);
		expect(tiles.match(/data-tile-state="absent"/g)).toHaveLength(2);
		expect(tiles.match(/data-tile-state="quiet"/g)).toHaveLength(1);
		expect(tiles).toContain('"ok" was true on 1 of 4 UTC days');
		const bars = draw([{ name: 'name', type: 'VARCHAR' }, { name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }], [{ name: 'first', a: '8', b: null }, { name: 'last', a: '4', b: '2' }], 'partsOfOne');
		expect(bars.match(/class="parts-segment /g)).toHaveLength(3);
		expect(bars.match(/class="parts-row /g)).toHaveLength(2);
		expect(bars).toContain('data-readout-row="b"');
		expect(bars).toContain('null');
	});

	test('a zero-only drawn prefix names its cap, without claiming later positive rows are zero', () => {
		const columns: Column[] = [{ name: 'name', type: 'VARCHAR' }, { name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }];
		const rows: Row[] = Array.from({ length: 4 }, (_, index) => ({ name: `row ${index}`, a: index === 3 ? '8' : '0', b: null }));
		const body = draw(columns, rows, 'partsOfOne');
		expect(body).toContain('Nothing here to draw: every bar you checked is 0 or null in the first 3 rows. The remaining rows are in the table.');
		expect(body).not.toContain('data-chart-type=');
		expect(body).not.toContain('data-lede=');
		expect(chooseChart(columns, rows, { ...bounds, rankMax: 1 }, 'partsOfOne').shape).toMatchObject({ reason: 'Nothing here to draw: every bar you checked is 0 or null in the first row. The remaining rows are in the table.' });
		expect(chooseChart(columns, rows.map((row) => ({ ...row, a: '0' })), bounds, 'partsOfOne').shape).toMatchObject({ reason: 'Nothing here to draw: every bar you checked is 0 or null on every row.' });
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
		expect(dateLine(body).match(/M/g)?.length, 'the line joined the days either side of the NULL').toBe(2);
	});

	test('a floor counts readings, so a NULL can leave a chart too few to draw, and the sentence names the floor it missed', () => {
		expect(draw([{ name: 'latency', type: 'DOUBLE' }], [
			{ latency: '10' },
			{ latency: '20' },
			{ latency: null },
			{ latency: '30' }
		], 'distribution')).toContain('Only 3 of the 4 readings this chart needs are in the answer, so it is not drawn.');

		expect(draw([{ name: 'host', type: 'VARCHAR' }, { name: 'ms', type: 'DOUBLE' }, { name: 'tokens', type: 'DOUBLE' }], [
			{ host: 'a', ms: '10', tokens: '100' },
			{ host: 'a', ms: '20', tokens: '150' },
			{ host: 'b', ms: '30', tokens: '120' },
			{ host: 'b', ms: '40', tokens: '90' },
			{ host: 'c', ms: null, tokens: '60' }
		], 'pairedScatter')).toContain('Only 2 of the 3 names this chart needs are in the answer, so it is not drawn.');
	});

	test('the date chart draws every row with a day, and its note says how many rows hold null in the day column', () => {
		const columns: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'rows', type: 'INTEGER' }];
		const body = draw(columns, [
			{ day: '2026-08-17', rows: '3' },
			{ day: null, rows: '4' },
			{ day: '2026-08-18', rows: '5' },
			{ day: '2026-08-19', rows: '8' }
		], 'dateSeries');
		expect(body).toContain('data-readout-columns="3"');
		expect(dateLine(body).match(/M/g)?.length, 'the line did not run through the three days unbroken').toBe(1);
		expect(printed(body, 'shape-lede')).toBe('8 rows on 2026-08-19');
		expect(printed(body, 'shape-foot')).toBe('1 row holds null in the column "day", so the chart does not draw it. It is in the table.');

		expect(printed(draw(columns, [
			{ day: null, rows: '1' },
			{ day: '2026-08-17', rows: '3' },
			{ day: null, rows: '2' },
			{ day: '2026-08-18', rows: '5' },
			{ day: null, rows: '6' },
			{ day: '2026-08-19', rows: '8' }
		], 'dateSeries'), 'shape-foot')).toBe('3 rows hold null in the column "day", so the chart does not draw them. They are in the table.');

		expect(draw(columns, [
			{ day: '2026-08-17', rows: '3' },
			{ day: null, rows: '4' },
			{ day: '2026-08-18', rows: '5' }
		], 'dateSeries'), 'the floor counted the row with no day as a day').toContain('Only 2 of the 3 UTC days this chart needs are in the answer, so it is not drawn.');
	});

	test('beside a row with no day, a NULL number still breaks the line on its own day and is still no reading in the spread', () => {
		const columns: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'rows', type: 'INTEGER' }];
		const rows: Row[] = [
			{ day: '2026-08-17', rows: '3' },
			{ day: '2026-08-18', rows: '5' },
			{ day: '2026-08-19', rows: null },
			{ day: null, rows: '7' },
			{ day: '2026-08-20', rows: '8' },
			{ day: '2026-08-21', rows: '9' }
		];
		const body = draw(columns, rows, 'dateSeries');
		expect(body).toContain('data-readout-columns="5"');
		expect(dateLine(body).match(/M/g)?.length, 'the line joined the days either side of the NULL number').toBe(2);
		expect(printed(body, 'shape-foot')).toBe('1 row holds null in the column "day", so the chart does not draw it. It is in the table.');
		// The spread needs no day, so it draws the row with no day, and the NULL number is still no reading.
		expect(chooseChart(columns, rows, bounds).shape).toMatchObject({ type: 'dateSeries', days: 5, rowsWithNoDay: 1 });
		expect(chooseChart(columns, rows, bounds, 'distribution').shape).toMatchObject({ type: 'distribution', readings: 5 });
	});

	test('a date column that holds only NULL puts its sentence in the chart room and draws no chart', () => {
		const body = draw([{ name: 'day', type: 'DATE' }, { name: 'rows', type: 'INTEGER' }], [
			{ day: null, rows: '3' },
			{ day: null, rows: '5' }
		], 'dateSeries');
		expect(printed(body, 'shape-none')).toBe('Nothing here to draw: the column "day" holds only null. Give "day" a date in the question to draw it over time.');
		expect(body).not.toContain('data-chart-type');
	});

	test('T3: Lines holds four columns at most, so the unchecked boxes say so without being disabled, and the list foot says why', () => {
		const lines = chartKind('dateSeries').roles[1];
		const options = ['a', 'b', 'c', 'd', 'e', 'f'].map((name) => ({ value: name, name, type: 'BIGINT' }));
		const four = pick({ role: lines, options, chosen: ['a', 'b', 'c', 'd'], max: SERIES_TOKENS.length });
		const boxes = [...four.matchAll(/<input[^>]*data-line[^>]*>/g)].map((input) => input[0]);
		expect(boxes, 'the list is not six checkboxes').toHaveLength(6);
		expect(boxes.every((input) => input.includes('type="checkbox"'))).toBe(true);
		expect(boxes.map((input) => /aria-disabled="true"/.test(input))).toEqual([false, false, false, false, true, true]);
		expect(four, 'a box was disabled, which a keyboard skips').not.toMatch(/<input[^>]* disabled/);
		expect(four).toContain('Four at most. Uncheck one to choose another.');
		const three = pick({ role: lines, options, chosen: ['a', 'b', 'c'], max: SERIES_TOKENS.length });
		expect(three).not.toContain('aria-disabled="true"');
		expect(three).not.toContain('Four at most.');
	});

	test('T3: the checked lines draw in the answer\'s order, the first in the first series colour, whatever order they were checked in', () => {
		const body = draw([{ name: 'day', type: 'DATE' }, { name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }, { name: 'c', type: 'INTEGER' }], [
			{ day: '2026-08-17', a: '3', b: '4', c: '5' },
			{ day: '2026-08-18', a: '5', b: '6', c: '7' },
			{ day: '2026-08-19', a: '8', b: '9', c: '10' }
		], 'dateSeries', { dateSeries: { lines: ['c', 'a'] } });
		expect([...body.matchAll(/stroke="var\((--chart-\d)\)"/g)].map((line) => line[1])).toEqual(['--chart-1', '--chart-2']);
		expect([...body.matchAll(/data-readout-row="([^"]*)"/g)].map((row) => row[1])).toEqual(['a', 'c']);
		expect(body).toContain('aria-label="Over time: day, a, c"');
		expect(printed(body, 'shape-lede'), 'the main figure reads the first checked line').toBe('8 a on 2026-08-19');
	});

	test('T4: the boxes for a chart the answer cannot fill, a chart the page does not pick, and no number say Susan\'s words', () => {
		const words: Column[] = [{ name: 'host', type: 'VARCHAR' }, { name: 'kind', type: 'VARCHAR' }];
		const one: Column[] = [{ name: 'host', type: 'VARCHAR' }, { name: 'ms', type: 'DOUBLE' }];
		const oneRow = [{ host: 'a', ms: '1' }];
		expect(printed(draw(one, oneRow, 'dateSeries'), 'shape-none')).toBe('Nothing here to draw: Over time needs a date or timestamp column for Date, and a number column for Lines. The ledgers keep their dates as text: CAST(date AS DATE) in the question makes a date column.');
		expect(printed(draw([{ name: 'ms', type: 'DOUBLE' }], [{ ms: '1' }], 'rankedList'), 'shape-none')).toBe('Nothing here to draw: Ranked needs a number column to rank by, and one more column for Name.');
		expect(printed(draw(one, oneRow, 'pairedScatter'), 'shape-none')).toBe('Nothing here to draw: Paired needs two number columns, one for Across and one for Up.');
		for (const type of CHART_KINDS.map((kind) => kind.type)) {
			expect(printed(draw(words, [{ host: 'a', kind: 'b' }], type), 'shape-none'), `${type} with no number`).toBe('Nothing here to draw: the answer has no number in it.');
		}
		expect(printed(draw(words, [{ host: 'a', kind: 'b' }], null), 'shape-none')).toBe('Nothing here to draw: the answer has no number in it.');
		expect(printed(draw([{ name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }, { name: 'c', type: 'INTEGER' }], [{ a: '1', b: '2', c: '3' }], null), 'shape-none')).toBe('The page does not pick a chart for these columns. Choose one under Draw it as.');
	});

	test('T4: the foot names the flat lines while they are the page\'s own, the rows with no day, and a capped answer, and no reason for the chart', () => {
		const columns: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'a', type: 'INTEGER' }, { name: 'tiny', type: 'INTEGER' }, { name: 'small', type: 'INTEGER' }];
		const rows: Row[] = [
			{ day: '2026-08-17', a: '100', tiny: '1', small: '2' },
			{ day: '2026-08-18', a: '90', tiny: '1', small: '3' },
			{ day: null, a: '80', tiny: '1', small: '2' },
			{ day: '2026-08-19', a: '80', tiny: '2', small: '4' }
		];
		expect(footNotes(draw(columns.slice(0, 3), rows, 'dateSeries', {}, true))).toEqual([
			'"tiny" is left out: it is under 5% of "a", so it would draw flat.',
			'1 row holds null in the column "day", so the chart does not draw it. It is in the table.',
			'Drawn from the first 1000 rows.'
		]);
		expect(footNotes(draw(columns, rows, 'dateSeries'))[0]).toBe('2 number columns are left out: each is under 5% of "a", so each would draw flat.');
		const picked = draw(columns, rows, 'dateSeries', { dateSeries: { lines: ['a'] } });
		expect(footNotes(picked), 'the flat-line note stayed after the reader picked the lines').toEqual(['1 row holds null in the column "day", so the chart does not draw it. It is in the table.']);
		expect(picked).not.toContain('Drawn over time because');
		expect(picked).not.toContain('Drawn: the first four number columns');
	});
});

test('T1: every answer the existing cases draw opens on the same chart with the same columns', () => {
	expect(opened([{ name: 'day', type: 'DATE' }, { name: 'scored', type: 'INTEGER' }], [
		{ day: '2026-10-01', scored: 3 },
		{ day: '2026-10-02', scored: 5 },
		{ day: '2026-10-03', scored: 8 }
	])).toEqual({ type: 'dateSeries', roles: { Date: ['day'], Lines: ['scored'] } });
	expect(opened([{ name: 'source', type: 'VARCHAR' }, { name: 'items', type: 'INTEGER' }], [
		{ source: 'a', items: 5 },
		{ source: 'b', items: 2 }
	])).toEqual({ type: 'rankedList', roles: { Name: ['source'], 'Rank by': ['items'] } });
	expect(opened([{ name: 'host', type: 'VARCHAR' }, { name: 'ms', type: 'DOUBLE' }, { name: 'tokens', type: 'DOUBLE' }], [
		{ host: 'a', ms: 10, tokens: 100 }
	])).toEqual({ type: 'pairedScatter', roles: { Across: ['ms'], Up: ['tokens'], Name: ['host'] } });
	expect(opened([{ name: 'ms', type: 'DOUBLE' }, { name: 'tokens', type: 'DOUBLE' }], [{ ms: 10, tokens: 100 }]), 'with no text column each row is its own point')
		.toEqual({ type: 'pairedScatter', roles: { Across: ['ms'], Up: ['tokens'], Name: [''] } });
	expect(opened([{ name: 'latency', type: 'DOUBLE' }], [{ latency: 10 }])).toEqual({ type: 'distribution', roles: { Values: ['latency'] } });
	// A date chart the page refuses still opens as the date chart, holding that date column (Susan's B2).
	for (const day of ['infinity', null]) {
		expect(opened([{ name: 'day', type: 'DATE' }, { name: 'items', type: 'INTEGER' }], [{ day, items: '1' }]), String(day)).toEqual({ type: 'dateSeries', roles: { Date: ['day'], Lines: ['items'] } });
	}
	expect(opened([{ name: 'source', type: 'VARCHAR' }], [{ source: 'a' }]), 'no number checks no tile').toEqual({ type: null, roles: {} });
});

test('T2: each role lists exactly the columns of its family, in the answer\'s order, named as the engine names them', () => {
	const columns: Column[] = [
		{ name: 'label', type: 'VARCHAR' },
		{ name: 'n', type: 'BIGINT' },
		{ name: 'clock', type: 'TIME' },
		{ name: 'shares', type: 'BIGINT[]' },
		{ name: 'day', type: 'DATE' },
		{ name: 'f', type: 'DOUBLE' },
		{ name: 'stamped', type: 'TIMESTAMP_NS' },
		{ name: 'zoned', type: 'TIMESTAMP WITH TIME ZONE' },
		{ name: 'ok', type: 'BOOLEAN' }
	];
	const listed = (type: ExplorerChartType, index: number) => roleOptions(chartKind(type).roles[index], columns).map((option) => option.name);
	expect(listed('dateSeries', 0), 'Date').toEqual(['day', 'stamped', 'zoned']);
	expect(listed('dateSeries', 1), 'Lines').toEqual(['n', 'f']);
	expect(listed('rankedList', 0), 'Name').toEqual(columns.map((column) => column.name));
	expect(listed('rankedList', 1), 'Rank by').toEqual(['n', 'f']);
	expect(listed('pairedScatter', 0), 'Across').toEqual(['n', 'f']);
	expect(listed('pairedScatter', 1), 'Up').toEqual(['n', 'f']);
	expect(listed('pairedScatter', 2), 'Paired Name').toEqual(['Row number', ...columns.map((column) => column.name)]);
	expect(listed('distribution', 0), 'Values').toEqual(['n', 'f']);
	expect(roleOptions(chartKind('dateSeries').roles[0], columns).map((option) => option.type)).toEqual(['DATE', 'TIMESTAMP_NS', 'TIMESTAMP WITH TIME ZONE']);
});

test('T3: a several-column role keeps at most one column for each series colour, and a choice keeps only the columns the answer still has', () => {
	const columns: Column[] = [{ name: 'day', type: 'DATE' }, ...['a', 'b', 'c', 'd', 'e'].map((name) => ({ name, type: 'INTEGER' }))];
	const rows: Row[] = [{ day: '2026-08-17', a: '1', b: '1', c: '1', d: '1', e: '1' }];
	const lines = (chosen: readonly string[]) => resolveRoles('dateSeries', columns, rows, bounds, { lines: chosen }).find((state) => state.role.id === 'lines');
	expect(lines(['a', 'b', 'c', 'd', 'e'])?.chosen).toEqual(['a', 'b', 'c', 'd']);
	expect(lines(['e', 'b'])?.chosen, 'not in the answer\'s order').toEqual(['b', 'e']);
	expect(lines(['b', 'gone'])).toMatchObject({ chosen: ['b'], byReader: true });
	expect(lines(['gone']), 'a role whose columns are all gone takes its default').toMatchObject({ chosen: ['a', 'b', 'c', 'd'], byReader: false });
	expect(lines([]), 'unchecking every line is a choice too').toMatchObject({ chosen: [], byReader: true });
	expect(SERIES_TOKENS).toHaveLength(4);
});

test('T4: every sentence for a pick that cannot draw is Susan\'s, word for word, from the smallest answer that causes it', () => {
	const day = (type: ExplorerChartType | null, columns: readonly Column[], rows: readonly Row[], roles: ChosenRoles = {}) => chooseChart(columns, rows, bounds, type, roles).shape;
	const dated: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'a', type: 'INTEGER' }];
	expect(day('dateSeries', dated, [{ day: '2026-08-17', a: '1' }], { dateSeries: { lines: [] } })).toMatchObject({ code: 'no-line-checked', reason: 'Nothing here to draw: Over time needs a column checked under Lines.' });
	expect(day('dateSeries', dated, [{ day: '2026-08-17', a: null }])).toMatchObject({ code: 'lines-all-null', reason: 'Nothing here to draw: every line you checked is null on every day.' });
	expect(day('dateSeries', dated, [{ day: '2026-08-17', a: '1' }, { day: '2026-08-17', a: '2' }])).toMatchObject({ reason: 'Nothing here to draw: the answer has several rows a UTC day in "day". Group by day in the question to draw it over time.' });
	const named: Column[] = [{ name: 'host', type: 'VARCHAR' }, { name: 'ms', type: 'BIGINT' }];
	expect(day('rankedList', named, [{ host: 'a', ms: '1' }, { host: 'a', ms: '2' }])).toMatchObject({ code: 'repeated-name', reason: 'Nothing here to draw: "a" is in more than one row of "host", and each row here needs its own name. Group by "host" in the question to draw it.' });
	expect(day('rankedList', named, [{ host: null, ms: '1' }, { host: null, ms: '2' }]), 'a NULL name is the name null').toMatchObject({ reason: 'Nothing here to draw: "null" is in more than one row of "host", and each row here needs its own name. Group by "host" in the question to draw it.' });
	expect(day('rankedList', named, [{ host: 'a', ms: '3' }, { host: 'b', ms: '-12345' }])).toMatchObject({ code: 'below-zero', reason: 'Nothing here to draw: "ms" holds -12,345, below zero, and this chart measures from zero.' });
	expect(day('rankedList', named, [{ host: 'a', ms: '0' }, { host: 'b', ms: null }])).toMatchObject({ code: 'all-zero', reason: 'Nothing here to draw: every value in "ms" is 0 or null.' });
	expect(day('distribution', [{ name: 'host', type: 'VARCHAR' }, { name: 'day', type: 'DATE' }, { name: 'ms', type: 'BIGINT' }], [{ host: 'a', day: '2026-08-17', ms: '1' }], { distribution: { values: ['day'] } }), 'a date is never offered to a number role').toMatchObject({ type: 'distribution', valueColumn: 'ms' });
	// The floors: every too-few sentence says where it counted, and no other caller's words change.
	expect(tooFewSentence(1, 3, 'UTC days', 'in the answer')).toBe('Only 1 of the 3 UTC days this chart needs is in the answer, so it is not drawn.');
	expect(tooFewSentence(2, 160, 'readings')).toBe('Only 2 of the 160 readings this chart needs are in this window, so it is not drawn.');
	// The closed face of a several-column pill (pill A1 to A5), and the accessible name that holds every name whole.
	const options = ['summary_ms', 'b', 'c', 'd'].map((name) => ({ value: name, name, type: 'BIGINT' }));
	expect([0, 1, 2, 3, 4].map((count) => pillFace(options, options.slice(0, count).map((option) => option.value)))).toEqual([
		{ name: 'None', more: '' },
		{ name: 'summary_ms', more: '' },
		{ name: 'summary_ms', more: ', 1 more' },
		{ name: 'summary_ms', more: ', 2 more' },
		{ name: 'summary_ms', more: ', 3 more' }
	]);
	expect(pillName(chartKind('dateSeries').roles[1], options, ['summary_ms', 'c'])).toBe('Lines: summary_ms, c');
	expect(pillName(chartKind('dateSeries').roles[0], [], [])).toBe('Date: None');
	expect(pillFace(roleOptions(chartKind('pairedScatter').roles[2], []), [''])).toEqual({ name: 'Row number', more: '' });
	expect(chartNotes({ kind: 'none', code: 'no-number', reason: '' }, bounds, true, 1000), 'a box that draws nothing has no notes').toEqual([]);
});

test('the foot keeps room for each note the answer can give, counted from the answer alone', () => {
	const dated: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }];
	const level: Row[] = [{ day: '2026-08-17', a: '100', b: '90' }, { day: '2026-08-18', a: '80', b: '70' }];
	expect(countChartNotes(dated, level, bounds, false), 'an answer with no note').toBe(0);
	expect(countChartNotes(dated, [], bounds, false), 'a quiet answer').toBe(0);
	expect(countChartNotes(dated, [{ day: '2026-08-17', a: '100', b: '1' }, { day: '2026-08-18', a: '80', b: '2' }], bounds, false), 'a flat number column').toBe(1);
	expect(countChartNotes(dated, [...level, { day: null, a: '60', b: '50' }], bounds, false), 'a null day').toBe(1);
	expect(countChartNotes(dated, level, bounds, true), 'a capped answer').toBe(1);
	expect(countChartNotes(dated, [{ day: '2026-08-17', a: '100', b: '1' }, { day: null, a: '80', b: '2' }], bounds, true), 'all three').toBe(3);
	expect(countChartNotes([{ name: 'name', type: 'VARCHAR' }, { name: 'a', type: 'INTEGER' }], [{ name: 'x', a: '1' }, { name: null, a: '0' }], bounds, false), 'no date column, so no flat line and no missing day').toBe(0);
	// Every row has a day under `first`, the date column Over time opens on, so that chart shows no
	// note. Under `second` only the rows where `b` is small have a day, so there `b` would draw flat
	// and a row is left out: the answer can give both notes, and the reader's pick decides only
	// which of them show.
	const twoDates: Column[] = [{ name: 'first', type: 'DATE' }, { name: 'second', type: 'DATE' }, { name: 'a', type: 'INTEGER' }, { name: 'b', type: 'INTEGER' }];
	const shifted: Row[] = [
		{ first: '2026-08-17', second: null, a: '100', b: '90' },
		{ first: '2026-08-18', second: '2026-08-18', a: '100', b: '1' },
		{ first: '2026-08-19', second: '2026-08-19', a: '90', b: '1' },
		{ first: '2026-08-20', second: '2026-08-20', a: '95', b: '2' }
	];
	const notesUnder = (date: string) => chartNotes(chooseChart(twoDates, shifted, bounds, 'dateSeries', { dateSeries: { date: [date] } }).shape, bounds, false, 1000);
	expect(notesUnder('first'), 'Over time on the first date column shows a note').toEqual([]);
	expect(notesUnder('second')).toEqual([
		'"b" is left out: it is under 5% of "a", so it would draw flat.',
		'1 row holds null in the column "second", so the chart does not draw it. It is in the table.'
	]);
	expect(countChartNotes(twoDates, shifted, bounds, false), 'the flat column under the second date column was not counted').toBe(2);
});

test('every role word fits the eight characters a pill gives it, and the role table holds four roles at most', () => {
	const words = CHART_KINDS.flatMap((kind) => kind.roles.map((role) => role.word));
	expect(words.filter((word) => word.length > 8)).toEqual([]);
	expect(CHART_KINDS.map((kind) => kind.option)).toEqual(['Over time', 'Ranked', 'Paired', 'Spread', 'Side by side', 'Which days', 'Flow']);
	expect(MOST_ROLES).toBe(4);
	expect(openingType([{ name: 'x', type: 'DOUBLE' }], [{ x: '1' }])).toBe('distribution');
});

test('the role row\'s lines by band follow the most roles any chart has, against the slots a line holds', () => {
	expect(roleRowLines(4, [1, 2, 3, 4])).toEqual([4, 2, 2, 1]);
	expect(roleRowLines(3, [1, 2, 3, 4])).toEqual([3, 2, 1, 1]);
	expect(roleSlotsPerLine(3, [1, 2, 3, 4])).toEqual([1, 2, 3, 3]);
	expect(roleSlotsPerLine(4, [1, 2, 3, 4])).toEqual([1, 2, 3, 4]);
});

test('T5: no file under the explorer\'s folder imports a d3 package, so d3 does the maths and Svelte draws', () => {
	const folder = path.join(frontend, 'src', 'lib', 'console', 'explorer');
	const files = readdirSync(folder).filter((name) => /\.(ts|svelte)$/.test(name));
	expect(files.length, 'the explorer folder was not read').toBeGreaterThan(10);
	const importing = files.filter((name) => /from\s+['"]d3(-[a-z-]+)?['"]/.test(readFileSync(path.join(folder, name), 'utf8')));
	expect(importing).toEqual([]);
});

test('the three new role defaults and refusals match Tables F, G and M', () => {
	const cols: Column[] = [{ name: 'name', type: 'VARCHAR' }, ...['a', 'b', 'c', 'd', 'e', 'f'].map((name) => ({ name, type: 'INTEGER' }))];
	const rows: Row[] = [{ name: 'first', a: '10', b: '8', c: '2', d: '0', e: '0', f: '0' }];
	expect(opened(cols, rows, 'partsOfOne').roles).toEqual({ Name: ['name'], Bars: ['a', 'b', 'c', 'd'] });
	expect(opened(cols, rows, 'flow').roles).toEqual({ Stage: ['name'], Arrived: ['a'], 'Went on': ['b'], Dropped: ['c', 'd', 'e', 'f'] });
	const picked = (type: ExplorerChartType, data: readonly Row[], roles: ChosenRoles = {}) => chooseChart(cols, data, bounds, type, roles).shape;
	expect(picked('partsOfOne', rows, { partsOfOne: { bars: ['a'] } })).toMatchObject({ reason: 'Nothing here to draw: Side by side needs two columns checked under Bars.' });
	expect(picked('partsOfOne', [{ name: 'first', a: '0', b: null, c: '0', d: '0' }])).toMatchObject({ reason: 'Nothing here to draw: every bar you checked is 0 or null on every row.' });
	for (const type of ['partsOfOne', 'flow'] as const) {
		expect(picked(type, [rows[0], rows[0]])).toMatchObject({ reason: 'Nothing here to draw: "first" is in more than one row of "name", and each row here needs its own name. Group by "name" in the question to draw it.' });
		expect(picked(type, [{ ...rows[0], b: '-2' }])).toMatchObject({ reason: 'Nothing here to draw: "b" holds -2, below zero, and this chart measures from zero.' });
	}
	expect(picked('flow', [{ ...rows[0], b: null }])).toMatchObject({ reason: 'Nothing here to draw: "b" is null at the stage "first", and a flow needs every count.' });
	expect(picked('flow', [{ ...rows[0], a: '0' }])).toMatchObject({ reason: 'Nothing here to draw: nothing arrived at the first stage, "first".' });
	const dates: Column[] = [{ name: 'day', type: 'DATE' }, { name: 'ok', type: 'BOOLEAN' }];
	const days = (data: Row[]) => chooseChart(dates, data, bounds, 'tileStrip').shape;
	expect(opened(dates, [{ day: '2026-10-01', ok: 'true' }], 'tileStrip').roles).toEqual({ Date: ['day'], 'Mark if': ['ok'] });
	expect(days([{ day: '2026-10-01', ok: null }])).toMatchObject({ reason: 'Nothing here to draw: "ok" is null on every day.' });
	expect(days([{ day: null, ok: 'true' }])).toMatchObject({ reason: 'Nothing here to draw: the column "day" holds only null. Give "day" a date in the question to mark it day by day.' });
	expect(days([{ day: 'infinity', ok: 'true' }])).toMatchObject({ reason: 'Nothing here to draw: the column "day" holds infinity, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to mark it day by day.' });
	expect(days([{ day: '2026-10-01', ok: 'true' }, { day: '2026-10-01', ok: 'false' }])).toMatchObject({ reason: 'Nothing here to draw: the answer has several rows a UTC day in "day". Group by day in the question to mark it day by day.' });
	const incomplete = [{ name: 'name', type: 'VARCHAR' }, { name: 'a', type: 'INTEGER' }];
	for (const [type, reason] of [
		['partsOfOne', 'Nothing here to draw: Side by side needs two number columns for Bars, and one more column for Name.'],
		['flow', 'Nothing here to draw: Flow needs two number columns, one for Arrived and one for Went on, and one more column for Stage.'],
		['tileStrip', 'Nothing here to draw: Which days needs a date or timestamp column for Date, and a true/false column to mark the days. The ledgers keep their dates as text: CAST(date AS DATE) in the question makes a date column.']
	] as const) expect(chooseChart(incomplete, [{ name: 'first', a: '1' }], bounds, type).shape).toMatchObject({ reason });
	expect(() => tileStrip([{ date: '2026-10-01', state: 'fired', reading: 1 }])).toThrow('A tile with a reading needs fill and naming thresholds.');
});
