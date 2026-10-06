import type { Column, DateStamp, Row } from '../../data/slice-shapes';
import { classifyType, isDay, isNumber, type TypeFamily } from './type-family';
import { readUtcDay } from './utc-instant';

export type ExplorerChartType = 'dateSeries' | 'rankedList' | 'pairedScatter' | 'distribution';

export type ExplorerShapeBounds = {
	chartMinRows: number;
	rankMax: number;
	fleetMinRows: number;
	bandwidthMinKinds: number;
	seriesFloorShare: number;
};

export type DateSeriesShape = {
	kind: 'chart';
	type: 'dateSeries';
	option: 'Over time';
	icon: 'shape-series';
	dateColumn: string;
	seriesColumns: readonly string[];
	omittedColumns: readonly string[];
	flatColumns: readonly { name: string; share: number; largestColumn: string }[];
	tooFew: boolean;
	mainFigure: { column: string; value: number; date: string } | null;
	comparison: string;
};

export type RankedListShape = {
	kind: 'chart';
	type: 'rankedList';
	option: 'Ranked';
	icon: 'shape-ranked';
	labelColumn: string;
	valueColumn: string;
	rowsDrawn: number;
	moreRows: number;
	mainFigure: { label: string; value: number; column: string } | null;
	comparison: string;
};

export type PairedScatterShape = {
	kind: 'chart';
	type: 'pairedScatter';
	option: 'Paired';
	icon: 'shape-scatter';
	xColumn: string;
	yColumn: string;
	subjectColumn: string | null;
	/** Rows with a number in both columns: the points drawn. */
	readings: number;
	/** Distinct subjects among those rows. */
	subjects: number;
	tooFew: boolean;
	mainFigure: string;
	comparison: string;
};

export type DistributionShape = {
	kind: 'chart';
	type: 'distribution';
	option: 'Spread';
	icon: 'shape-distribution';
	valueColumn: string;
	/** Rows with a number in the column: the values drawn. */
	readings: number;
	tooFew: boolean;
	median: number | null;
	mainFigure: string | null;
	comparison: string;
};

export type NoShape = {
	kind: 'none';
	reason: string;
	code: 'no-number' | 'unplaceable-day' | 'several-rows-per-day' | 'too-many-numbers' | 'too-many-text-columns' | 'no-fit';
};

export type ExplorerShape = DateSeriesShape | RankedListShape | PairedScatterShape | DistributionShape | NoShape;

function columnsOf(columns: readonly Column[], holds: (family: TypeFamily) => boolean): string[] {
	return columns.filter((column) => holds(classifyType(column.type))).map((column) => column.name);
}

/** A cell's number, or `null` when it holds none. The door returns every cell as text and a
 *  SQL NULL as `null`, so a number column's cell arrives as `'8'` or `'1.5'`; a number is
 *  accepted too. A NULL, text that is not a finite number, and an integer past the safe range
 *  are `null`: a missing reading is left out of a chart, never drawn as a zero. */
export function numericValue(row: Row, column: string): number | null {
	const value = row[column];
	const parsed = typeof value === 'number' ? value : typeof value === 'string' && value.trim() !== '' ? Number(value) : Number.NaN;
	if (!Number.isFinite(parsed)) return null;
	return Number.isInteger(parsed) && !Number.isSafeInteger(parsed) ? null : parsed;
}

/** The UTC day a date or a timestamp cell falls on, read from the instant its text names. */
function dayValue(value: unknown): DateStamp | null {
	return typeof value === 'string' ? readUtcDay(value) : null;
}

/** The first cell in a date column that falls on no UTC day from year 1 to 9999, as the engine
 *  printed it and the table shows it, or `null` when every row falls on such a day. `infinity`, a
 *  year past 9999, a date `(BC)` and a NULL, which the table prints as `null`, are such cells. */
function firstUnplaceableDay(rows: readonly Row[], dateColumn: string): string | null {
	const row = rows.find((one) => dayValue(one[dateColumn]) === null);
	if (row === undefined) return null;
	const value = row[dateColumn];
	return value === null || value === undefined ? 'null' : String(value);
}

function hasSeveralRowsPerUtcDay(rows: readonly Row[], dateColumn: string): boolean {
	return new Set(rows.map((row) => dayValue(row[dateColumn]))).size < rows.length;
}

function median(values: readonly number[]): number | null {
	if (values.length === 0) return null;
	const ordered = [...values].sort((a, b) => a - b);
	const middle = Math.floor(ordered.length / 2);
	return ordered.length % 2 === 1 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function firstNumber(row: Row | undefined, column: string): number | null {
	return row ? numericValue(row, column) : null;
}

function biggestRow(rows: readonly Row[], column: string): Row | undefined {
	return [...rows].sort((left, right) => (firstNumber(right, column) ?? Number.NEGATIVE_INFINITY) - (firstNumber(left, column) ?? Number.NEGATIVE_INFINITY))[0];
}

export function chooseExplorerShapes(columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds): readonly ExplorerShape[] {
	const dateColumns = columnsOf(columns, isDay);
	const numericColumns = columnsOf(columns, isNumber);
	const textColumns = columnsOf(columns, (family) => family === 'text');
	const shapes: ExplorerShape[] = [];

	if (numericColumns.length === 0) {
		return [{ kind: 'none', code: 'no-number', reason: 'Nothing here to draw: the answer has no number in it.' }];
	}

	if (dateColumns.length === 1 && numericColumns.length > 0) {
		const dateColumn = dateColumns[0];
		const unplaceable = firstUnplaceableDay(rows, dateColumn);
		if (unplaceable !== null) {
			return [{
				kind: 'none',
				code: 'unplaceable-day',
				reason: `Nothing here to draw: the column "${dateColumn}" holds ${unplaceable}, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.`
			}];
		}
		if (hasSeveralRowsPerUtcDay(rows, dateColumn)) {
			return [{
				kind: 'none',
				code: 'several-rows-per-day',
				reason: 'Nothing here to draw: the answer has several rows a UTC day. Group by day in the question to draw it over time.'
			}];
		}
		shapes.push(dateSeriesShape(dateColumns[0], numericColumns, rows, bounds));
	}

	if (numericColumns.length === 1 && textColumns.length === 1 && rows.every((row) => (numericValue(row, numericColumns[0]) ?? 0) >= 0)) {
		shapes.push(rankedListShape(textColumns[0], numericColumns[0], rows, bounds));
	}

	if (numericColumns.length === 2 && textColumns.length <= 1) {
		shapes.push(pairedScatterShape(numericColumns, textColumns, rows, bounds));
	}

	if (numericColumns.length === 1) {
		shapes.push(distributionShape(numericColumns[0], rows, bounds));
	}
	if (shapes.length > 0) return shapes;

	if (numericColumns.length >= 3) {
		return [{
			kind: 'none',
			code: 'too-many-numbers',
			reason: `Nothing here to draw: ${numericColumns.length} number columns are more than one chart can show. Keep one or two in the question.`
		}];
	}

	if (numericColumns.length === 2 && textColumns.length > 1) {
		return [{
			kind: 'none',
			code: 'too-many-text-columns',
			reason: `Nothing here to draw: two number columns pair up with at most one text column naming each point, and this answer has ${textColumns.length}.`
		}];
	}

	return [{ kind: 'none', code: 'no-fit', reason: 'Nothing here to draw: the answer has no number in it.' }];
}

export function chooseExplorerShape(columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	return chooseExplorerShapes(columns, rows, bounds)[0];
}

function dateSeriesShape(dateColumn: string, numericColumns: readonly string[], rows: readonly Row[], bounds: ExplorerShapeBounds): DateSeriesShape {
	const largestByColumn = new Map<string, number>();
	for (const column of numericColumns) {
		largestByColumn.set(column, Math.max(0, ...rows.map((row) => numericValue(row, column) ?? 0)));
	}
	const largestColumn = [...largestByColumn.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? numericColumns[0];
	const largestValue = largestByColumn.get(largestColumn) ?? 0;
	const usable = numericColumns.filter((column) => largestValue === 0 || (largestByColumn.get(column) ?? 0) >= largestValue * bounds.seriesFloorShare);
	const seriesColumns = usable.slice(0, 4);
	const omittedColumns = usable.slice(4);
	const flatColumns = numericColumns
		.filter((column) => !usable.includes(column))
		.map((name) => ({ name, share: largestValue === 0 ? 0 : (largestByColumn.get(name) ?? 0) / largestValue, largestColumn }));
	const firstSeries = seriesColumns[0] ?? numericColumns[0];
	const latest = [...rows].sort((left, right) => String(right[dateColumn]).localeCompare(String(left[dateColumn])))[0];
	const value = firstNumber(latest, firstSeries);
	return {
		kind: 'chart',
		type: 'dateSeries',
		option: 'Over time',
		icon: 'shape-series',
		dateColumn,
		seriesColumns,
		omittedColumns,
		flatColumns,
		tooFew: rows.length < bounds.chartMinRows,
		mainFigure: latest && value !== null ? { column: firstSeries, value, date: dayValue(latest[dateColumn]) ?? String(latest[dateColumn]) } : null,
		comparison: `${firstSeries} on each day against the other days in the span`
	};
}

/** One UTC day on the date chart's axis, and the answer's row for it: `null` on a lost day. */
export type DateSeriesDay = { day: DateStamp; row: Row | null };

/** The days the date chart draws, ascending: each UTC day the answer has a row for, and each day a
 *  selected ledger lost that falls between the first and the last of them with no row of its own.
 *
 *  A lost day has no record, so it sits on the axis with no value and the line breaks there,
 *  instead of joining the days either side as if it held data. Any other day without a row stays
 *  off the axis, because the page cannot know what the question would make of a day with no rows.
 *  A lost day before the first day or after the last stays off too, so it never lengthens the chart
 *  or stands beside days the question left out; the note under the span line names every lost day
 *  (Jony, 2026-10-05). */
export function chooseDateSeriesDays(dateColumn: string, rows: readonly Row[], lostDays: readonly DateStamp[]): DateSeriesDay[] {
	const byDay = new Map<DateStamp, Row>();
	for (const row of rows) {
		const day = dayValue(row[dateColumn]);
		if (day !== null) byDay.set(day, row);
	}
	const drawn = [...byDay.keys()].sort();
	if (drawn.length === 0) return [];
	const first = drawn[0];
	const last = drawn[drawn.length - 1];
	const lost = lostDays.filter((day) => first < day && day < last && !byDay.has(day));
	return [...new Set([...drawn, ...lost])].sort().map((day) => ({ day, row: byDay.get(day) ?? null }));
}

function rankedListShape(labelColumn: string, valueColumn: string, rows: readonly Row[], bounds: ExplorerShapeBounds): RankedListShape {
	const leader = biggestRow(rows, valueColumn);
	const value = firstNumber(leader, valueColumn);
	const rowsDrawn = Math.min(rows.filter((row) => numericValue(row, valueColumn) !== null).length, bounds.rankMax);
	return {
		kind: 'chart',
		type: 'rankedList',
		option: 'Ranked',
		icon: 'shape-ranked',
		labelColumn,
		valueColumn,
		rowsDrawn,
		moreRows: rows.length - rowsDrawn,
		mainFigure: leader && value !== null ? { label: String(leader[labelColumn]), value, column: valueColumn } : null,
		comparison: `each ${labelColumn} against the largest`
	};
}

function pairedScatterShape(numericColumns: readonly string[], textColumns: readonly string[], rows: readonly Row[], bounds: ExplorerShapeBounds): PairedScatterShape {
	const [xColumn, yColumn] = numericColumns;
	const drawn = rows.filter((row) => numericValue(row, xColumn) !== null && numericValue(row, yColumn) !== null);
	const subjects = textColumns.length === 1 ? new Set(drawn.map((row) => String(row[textColumns[0]]))).size : drawn.length;
	return {
		kind: 'chart',
		type: 'pairedScatter',
		option: 'Paired',
		icon: 'shape-scatter',
		xColumn,
		yColumn,
		subjectColumn: textColumns[0] ?? null,
		readings: drawn.length,
		subjects,
		tooFew: drawn.length < bounds.fleetMinRows || subjects < bounds.bandwidthMinKinds,
		mainFigure: `${drawn.length} rows of ${yColumn} against ${xColumn}`,
		comparison: `${yColumn} against ${xColumn}`
	};
}

function distributionShape(valueColumn: string, rows: readonly Row[], bounds: ExplorerShapeBounds): DistributionShape {
	const values = rows.map((row) => numericValue(row, valueColumn)).filter((value): value is number => value !== null);
	const middle = median(values);
	return {
		kind: 'chart',
		type: 'distribution',
		option: 'Spread',
		icon: 'shape-distribution',
		valueColumn,
		readings: values.length,
		tooFew: values.length < bounds.fleetMinRows,
		median: middle,
		mainFigure: middle === null ? null : `Half of ${valueColumn} is at or under ${middle}`,
		comparison: `each band of ${valueColumn} against the share of rows at or below it`
	};
}
