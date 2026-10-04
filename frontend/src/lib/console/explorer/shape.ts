import type { Column, Row } from '../../data/slice-shapes';

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
	tooFew: boolean;
	median: number | null;
	mainFigure: string | null;
	comparison: string;
};

export type NoShape = {
	kind: 'none';
	reason: string;
	code: 'no-number' | 'several-rows-per-day' | 'too-many-numbers' | 'too-many-text-columns' | 'no-fit';
};

export type ExplorerShape = DateSeriesShape | RankedListShape | PairedScatterShape | DistributionShape | NoShape;

const DATE_TYPES = new Set(['DATE', 'TIMESTAMP', 'TIMESTAMP WITH TIME ZONE', 'TIMESTAMPTZ']);
const NUMERIC_TYPES = new Set(['TINYINT', 'SMALLINT', 'INTEGER', 'INT', 'BIGINT', 'HUGEINT', 'UTINYINT', 'USMALLINT', 'UINTEGER', 'UBIGINT', 'FLOAT', 'DOUBLE', 'REAL', 'DECIMAL', 'NUMERIC']);
const TEXT_TYPES = new Set(['VARCHAR', 'TEXT', 'STRING', 'UUID']);

function normalizedType(column: Column): string {
	return column.type.trim().replace(/\(.*/, '').toUpperCase();
}

function columnsOf(columns: readonly Column[], types: ReadonlySet<string>): string[] {
	return columns.filter((column) => types.has(normalizedType(column))).map((column) => column.name);
}

function numericValue(row: Row, column: string): number | null {
	const value = row[column];
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function dayValue(value: unknown): string | null {
	if (typeof value !== 'string') return null;
	const day = value.slice(0, 10);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
	return new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) === day ? day : null;
}

function hasSeveralRowsPerUtcDay(rows: readonly Row[], dateColumn: string): boolean {
	const days = new Set<string>();
	for (const row of rows) {
		const day = dayValue(row[dateColumn]);
		if (day === null) return true;
		if (days.has(day)) return true;
		days.add(day);
	}
	return false;
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

export function chooseExplorerShape(columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	const dateColumns = columnsOf(columns, DATE_TYPES);
	const numericColumns = columnsOf(columns, NUMERIC_TYPES);
	const textColumns = columnsOf(columns, TEXT_TYPES);

	if (numericColumns.length === 0) {
		return { kind: 'none', code: 'no-number', reason: 'Nothing here to draw: the answer has no number in it.' };
	}

	if (dateColumns.length === 1 && numericColumns.length > 0) {
		const dateColumn = dateColumns[0];
		if (hasSeveralRowsPerUtcDay(rows, dateColumn)) {
			return {
				kind: 'none',
				code: 'several-rows-per-day',
				reason: 'Nothing here to draw: the answer has several rows a UTC day. Group by day in the question to draw it over time.'
			};
		}
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

	if (numericColumns.length === 1 && textColumns.length === 1 && rows.every((row) => (numericValue(row, numericColumns[0]) ?? 0) >= 0)) {
		const valueColumn = numericColumns[0];
		const labelColumn = textColumns[0];
		const leader = biggestRow(rows, valueColumn);
		const value = firstNumber(leader, valueColumn);
		return {
			kind: 'chart',
			type: 'rankedList',
			option: 'Ranked',
			icon: 'shape-ranked',
			labelColumn,
			valueColumn,
			rowsDrawn: Math.min(rows.length, bounds.rankMax),
			moreRows: Math.max(0, rows.length - bounds.rankMax),
			mainFigure: leader && value !== null ? { label: String(leader[labelColumn]), value, column: valueColumn } : null,
			comparison: `each ${labelColumn} against the largest`
		};
	}

	if (numericColumns.length === 2 && textColumns.length <= 1) {
		const [xColumn, yColumn] = numericColumns;
		const subjects = textColumns.length === 1 ? new Set(rows.map((row) => String(row[textColumns[0]]))).size : rows.length;
		return {
			kind: 'chart',
			type: 'pairedScatter',
			option: 'Paired',
			icon: 'shape-scatter',
			xColumn,
			yColumn,
			subjectColumn: textColumns[0] ?? null,
			tooFew: rows.length < bounds.fleetMinRows || subjects < bounds.bandwidthMinKinds,
			mainFigure: `${rows.length} rows of ${yColumn} against ${xColumn}`,
			comparison: `${yColumn} against ${xColumn}`
		};
	}

	if (numericColumns.length === 1) {
		const valueColumn = numericColumns[0];
		const values = rows.map((row) => numericValue(row, valueColumn)).filter((value): value is number => value !== null);
		const middle = median(values);
		return {
			kind: 'chart',
			type: 'distribution',
			option: 'Spread',
			icon: 'shape-distribution',
			valueColumn,
			tooFew: rows.length < bounds.fleetMinRows,
			median: middle,
			mainFigure: middle === null ? null : `Half of ${valueColumn} is at or under ${middle}`,
			comparison: `each band of ${valueColumn} against the share of rows at or below it`
		};
	}

	if (numericColumns.length >= 3) {
		return {
			kind: 'none',
			code: 'too-many-numbers',
			reason: `Nothing here to draw: ${numericColumns.length} number columns are more than one chart can show. Keep one or two in the question.`
		};
	}

	if (numericColumns.length === 2 && textColumns.length > 1) {
		return {
			kind: 'none',
			code: 'too-many-text-columns',
			reason: `Nothing here to draw: two number columns pair up with at most one text column naming each point, and this answer has ${textColumns.length}.`
		};
	}

	return { kind: 'none', code: 'no-fit', reason: 'Nothing here to draw: the answer has no number in it.' };
}
