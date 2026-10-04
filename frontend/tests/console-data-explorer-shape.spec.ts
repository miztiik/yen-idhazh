import { expect, test } from '@playwright/test';

import { chooseExplorerShape, chooseExplorerShapes, type ExplorerShapeBounds } from '../src/lib/console/explorer/shape';
import type { Column, Row } from '../src/lib/data/slice-shapes';

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
