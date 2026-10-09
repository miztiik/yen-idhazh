/** What the Data explorer's chart draws for an answer: the chart the page opens on, the columns
 * each role holds, and the shape a chart takes with them - or the one sentence its box says when
 * those columns cannot draw it.
 *
 * Until the reader presses a tile or picks a column, each answer opens on the chart its own
 * columns choose, first match wins (`openingType`), with each role holding the columns that rule
 * has always drawn. After that the reader's chart and columns hold across runs, while the answer
 * still has each column in a family the role takes. Every chart is offered on every answer, and
 * one these columns cannot support draws nothing and says what it needs, so the page still never
 * draws a story the columns do not tell. The sentences are Susan's (2026-10-07).
 */

// Relative, not `$lib`: the logic suite imports this module in plain Node.
import type { Column, DateStamp, Row } from '../../data/slice-shapes';
import { plural } from '../../format';
import { printCell } from './answer';
import { CHART_KINDS, ROW_NUMBER, SERIES_TOKENS, chartKind, roleOptions, type ChartRole, type ExplorerChartType, type RoleId, type RoleOption } from './chart-roles';
import { classifyType, isDay, isNumber, type TypeFamily } from './type-family';
import { readUtcDay } from './utc-instant';

export type { ExplorerChartType } from './chart-roles';

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
	/** The checked lines, in the answer's order; the first takes the first series colour. */
	seriesColumns: readonly string[];
	/** Number columns the page's own lines leave out because they would draw flat. Empty once the
	 *  reader has picked the lines, because the sentence explains a choice the reader did not make. */
	flatColumns: readonly { name: string; share: number; largestColumn: string }[];
	/** UTC days the answer has a row for: the days the floor counts. */
	days: number;
	/** Rows whose day is NULL: the chart does not draw them, and its note says how many. */
	rowsWithNoDay: number;
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
	/** The column that names each point, or null where each row is its own point. */
	subjectColumn: string | null;
	/** Rows with a number in both columns: the points drawn. */
	readings: number;
	/** Distinct names among those rows. */
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

export type NoShapeCode =
	| 'no-number'
	| 'not-picked'
	| 'unfilled'
	| 'unplaceable-day'
	| 'no-day'
	| 'several-rows-per-day'
	| 'no-line-checked'
	| 'lines-all-null'
	| 'repeated-name'
	| 'below-zero'
	| 'all-zero';

export type NoShape = { kind: 'none'; reason: string; code: NoShapeCode };

export type ExplorerShape = DateSeriesShape | RankedListShape | PairedScatterShape | DistributionShape | NoShape;

/** The columns the reader picked, by chart and then by role, kept on the page for as long as it is
 *  open. Never saved with a question and never carried in a link. */
export type ChosenRoles = Partial<Record<ExplorerChartType, Partial<Record<RoleId, readonly string[]>>>>;

/** One role of the chart drawn: the columns it can take, and the ones it holds, in the answer's order. */
export type RoleState = { role: ChartRole; options: readonly RoleOption[]; chosen: readonly string[]; byReader: boolean };

/** The chart a tile shows checked - null for none - its roles in order, and what its box draws. */
export type ExplorerChart = { type: ExplorerChartType | null; roles: readonly RoleState[]; shape: ExplorerShape };

const NO_NUMBER: NoShape = { kind: 'none', code: 'no-number', reason: 'Nothing here to draw: the answer has no number in it.' };

const NOT_PICKED: NoShape = { kind: 'none', code: 'not-picked', reason: 'The page does not pick a chart for these columns. Choose one under Draw it as.' };

/** What each chart needs, the same whichever of its roles is empty: the empty pill shows which. */
const NEEDS: Record<ExplorerChartType, string> = {
	dateSeries: 'Nothing here to draw: Over time needs a date or timestamp column for Date, and a number column for Lines.',
	rankedList: 'Nothing here to draw: Ranked needs a number column to rank by, and one more column for Name.',
	pairedScatter: 'Nothing here to draw: Paired needs two number columns, one for Across and one for Up.',
	distribution: 'Nothing here to draw: Spread needs a number column for Values.'
};

/** Said after a chart's needs when the answer has no date or timestamp column for it. */
const DATES_ARE_TEXT = 'The ledgers keep their dates as text: CAST(date AS DATE) in the question makes a date column.';

/** Where the explorer counts what a floor needs: the rows of one answer, not a window of days. */
export const IN_THE_ANSWER = 'in the answer';

function namesOf(columns: readonly Column[], holds: (family: TypeFamily) => boolean): string[] {
	return columns.filter((column) => holds(classifyType(column.type))).map((column) => column.name);
}

function columnOf(columns: readonly Column[], name: string): Column {
	return columns.find((column) => column.name === name) ?? { name, type: 'VARCHAR' };
}

/** A cell as the answer table prints it, `null` included. */
function printed(columns: readonly Column[], row: Row, name: string): string {
	return printCell(columnOf(columns, name), row[name]).text;
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

/** The first value in a date column that falls on no UTC day from year 1 to 9999, as the engine
 *  printed it and the table shows it, or `null` when every value falls on such a day. `infinity`, a
 *  year past 9999 and a date `(BC)` are such values. A NULL is not: it is no day at all, so the date
 *  chart leaves its row out instead. */
function firstUnplaceableDay(rows: readonly Row[], dateColumn: string): string | null {
	const value = rows.map((row) => row[dateColumn]).find((one) => one !== null && one !== undefined && dayValue(one) === null);
	return value === undefined ? null : String(value);
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

/** The chart an answer opens on before the reader chooses: the first type its columns fit, in the
 *  order the mark-shapes page gives, or null where none fits. A date column that holds a day the
 *  chart cannot place, only NULL, or several rows a UTC day still opens the date chart, whose box
 *  then says why it draws nothing. What this rule picks does not change with the reader's choices. */
export function openingType(columns: readonly Column[], rows: readonly Row[]): ExplorerChartType | null {
	const dateColumns = namesOf(columns, isDay);
	const numericColumns = namesOf(columns, isNumber);
	const textColumns = namesOf(columns, (family) => family === 'text');
	if (numericColumns.length === 0) return null;
	if (dateColumns.length === 1) return 'dateSeries';
	if (numericColumns.length === 1 && textColumns.length === 1 && rows.every((row) => (numericValue(row, numericColumns[0]) ?? 0) >= 0)) return 'rankedList';
	if (numericColumns.length === 2 && textColumns.length <= 1) return 'pairedScatter';
	if (numericColumns.length === 1) return 'distribution';
	return null;
}

/** The number columns a date chart draws by default, and the ones it leaves out because they would
 *  draw flat: a column whose largest value is under `share` of the largest column's. Read from the
 *  rows the chart draws. */
function lineSplit(numbers: readonly string[], rows: readonly Row[], share: number) {
	const largestByColumn = new Map<string, number>(numbers.map((column) => [column, Math.max(0, ...rows.map((row) => numericValue(row, column) ?? 0))]));
	const largestColumn = [...largestByColumn.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? numbers[0];
	const largestValue = largestByColumn.get(largestColumn) ?? 0;
	const usable = numbers.filter((column) => largestValue === 0 || (largestByColumn.get(column) ?? 0) >= largestValue * share);
	const flat = numbers
		.filter((column) => !usable.includes(column))
		.map((name) => ({ name, share: largestValue === 0 ? 0 : (largestByColumn.get(name) ?? 0) / largestValue, largestColumn }));
	return { usable, flat };
}

/** The rows a date chart draws: those with a day in `dateColumn`, or every row where there is none. */
function datedRowsOf(rows: readonly Row[], dateColumn: string | undefined): readonly Row[] {
	return dateColumn === undefined ? rows : rows.filter((row) => dayValue(row[dateColumn]) !== null);
}

/** The rows a date chart leaves out because `dateColumn` gives them no day. */
function rowsWithNoDayIn(rows: readonly Row[], dateColumn: string): number {
	return rows.length - datedRowsOf(rows, dateColumn).length;
}

/** The page's own column for one role (Table A), given the roles before it, which a later role's
 *  choice may depend on: the date chart's lines are read from the rows with a day, and the ranked
 *  list ranks by a number that does not name its rows. */
function defaultFor(type: ExplorerChartType, role: RoleId, held: Partial<Record<RoleId, readonly string[]>>, columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds): string[] {
	const numbers = namesOf(columns, isNumber);
	const texts = namesOf(columns, (family) => family === 'text');
	const one = (name: string | undefined): string[] => (name === undefined ? [] : [name]);
	if (type === 'dateSeries' && role === 'date') return one(namesOf(columns, isDay)[0]);
	if (type === 'dateSeries' && role === 'lines') return lineSplit(numbers, datedRowsOf(rows, held.date?.[0]), bounds.seriesFloorShare).usable.slice(0, SERIES_TOKENS.length);
	if (type === 'rankedList' && role === 'name') return one(texts[0] ?? columns.find((column) => !isNumber(classifyType(column.type)))?.name ?? columns[0]?.name);
	if (type === 'rankedList' && role === 'rankBy') return one(numbers.find((name) => name !== held.name?.[0]));
	if (type === 'pairedScatter' && role === 'across') return one(numbers[0]);
	if (type === 'pairedScatter' && role === 'up') return one(numbers[1]);
	if (type === 'pairedScatter' && role === 'name') return [texts[0] ?? ROW_NUMBER.value];
	if (type === 'distribution' && role === 'values') return one(numbers[0]);
	return [];
}

/** Each role of `type`, holding the reader's columns where this answer still has them in a family
 *  the role takes, and the page's own pick where it does not. A several-column role keeps the
 *  reader's columns that are left, in the answer's order, and keeps none where the reader checked
 *  none. */
export function resolveRoles(type: ExplorerChartType, columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds, chosen: Partial<Record<RoleId, readonly string[]>> = {}): RoleState[] {
	const held: Partial<Record<RoleId, readonly string[]>> = {};
	return chartKind(type).roles.map((role) => {
		const options = roleOptions(role, columns);
		const offered = options.map((option) => option.value);
		const picked = chosen[role.id];
		const kept = picked === undefined ? [] : offered.filter((value) => picked.includes(value));
		const holds = picked !== undefined && (kept.length > 0 || (role.several && picked.length === 0));
		const state: RoleState = holds
			? { role, options, chosen: kept.slice(0, role.several ? SERIES_TOKENS.length : 1), byReader: true }
			: { role, options, chosen: defaultFor(type, role.id, held, columns, rows, bounds), byReader: false };
		held[role.id] = state.chosen;
		return state;
	});
}

function chosenOf(roles: readonly RoleState[], id: RoleId): readonly string[] {
	return roles.find((state) => state.role.id === id)?.chosen ?? [];
}

/** The sentence for a chart whose roles these columns cannot fill, with the cast that makes a date
 *  column where the chart needs one and the answer has none. */
function unfilled(type: ExplorerChartType, roles: readonly RoleState[]): NoShape {
	const noDay = roles.some((state) => state.role.takes === 'day' && state.options.length === 0);
	return { kind: 'none', code: 'unfilled', reason: noDay ? `${NEEDS[type]} ${DATES_ARE_TEXT}` : NEEDS[type] };
}

function dateSeriesShape(roles: readonly RoleState[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	const dateColumn = chosenOf(roles, 'date')[0];
	const lines = roles.find((state) => state.role.id === 'lines');
	if (dateColumn === undefined || lines === undefined || lines.options.length === 0) return unfilled('dateSeries', roles);
	const unplaceable = firstUnplaceableDay(rows, dateColumn);
	if (unplaceable !== null) {
		return {
			kind: 'none',
			code: 'unplaceable-day',
			reason: `Nothing here to draw: the column "${dateColumn}" holds ${unplaceable}, and the chart can show only days from year 1 to year 9999. Keep only those days in the question to draw it over time.`
		};
	}
	const datedRows = datedRowsOf(rows, dateColumn);
	const rowsWithNoDay = rowsWithNoDayIn(rows, dateColumn);
	if (datedRows.length === 0 && rowsWithNoDay > 0) {
		return {
			kind: 'none',
			code: 'no-day',
			reason: `Nothing here to draw: the column "${dateColumn}" holds only null. Give "${dateColumn}" a date in the question to draw it over time.`
		};
	}
	if (hasSeveralRowsPerUtcDay(datedRows, dateColumn)) {
		return {
			kind: 'none',
			code: 'several-rows-per-day',
			reason: `Nothing here to draw: the answer has several rows a UTC day in "${dateColumn}". Group by day in the question to draw it over time.`
		};
	}
	const seriesColumns = lines.chosen;
	if (seriesColumns.length === 0) return { kind: 'none', code: 'no-line-checked', reason: 'Nothing here to draw: Over time needs a column checked under Lines.' };
	if (datedRows.every((row) => seriesColumns.every((column) => numericValue(row, column) === null))) {
		return { kind: 'none', code: 'lines-all-null', reason: 'Nothing here to draw: every line you checked is null on every day.' };
	}
	const numbers = lines.options.map((option) => option.value);
	const flatColumns = lines.byReader ? [] : lineSplit(numbers, datedRows, bounds.seriesFloorShare).flat;
	const firstSeries = seriesColumns[0];
	const latest = [...datedRows].sort((left, right) => String(right[dateColumn]).localeCompare(String(left[dateColumn])))[0];
	const value = firstNumber(latest, firstSeries);
	return {
		kind: 'chart',
		type: 'dateSeries',
		option: 'Over time',
		icon: 'shape-series',
		dateColumn,
		seriesColumns,
		flatColumns,
		days: datedRows.length,
		rowsWithNoDay,
		tooFew: datedRows.length < bounds.chartMinRows,
		mainFigure: latest && value !== null ? { column: firstSeries, value, date: dayValue(latest[dateColumn]) ?? String(latest[dateColumn]) } : null,
		comparison: `${firstSeries} on each day against the other days in the span`
	};
}

function rankedListShape(roles: readonly RoleState[], columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	const labelColumn = chosenOf(roles, 'name')[0];
	const valueColumn = chosenOf(roles, 'rankBy')[0];
	if (labelColumn === undefined || valueColumn === undefined) return unfilled('rankedList', roles);
	const ranked = rows.filter((row) => numericValue(row, valueColumn) !== null);
	const names = new Set<string>();
	for (const row of ranked) {
		const name = printed(columns, row, labelColumn);
		if (names.has(name)) {
			return {
				kind: 'none',
				code: 'repeated-name',
				reason: `Nothing here to draw: "${name}" is in more than one row of "${labelColumn}", and each row here needs its own name. Group by "${labelColumn}" in the question to draw it.`
			};
		}
		names.add(name);
	}
	const negative = ranked.find((row) => (numericValue(row, valueColumn) ?? 0) < 0);
	if (negative !== undefined) {
		return {
			kind: 'none',
			code: 'below-zero',
			reason: `Nothing here to draw: "${valueColumn}" holds ${printed(columns, negative, valueColumn)}, below zero, and this chart measures from zero.`
		};
	}
	if (ranked.every((row) => numericValue(row, valueColumn) === 0)) {
		return { kind: 'none', code: 'all-zero', reason: `Nothing here to draw: every value in "${valueColumn}" is 0 or null.` };
	}
	const leader = biggestRow(rows, valueColumn);
	const value = firstNumber(leader, valueColumn);
	const rowsDrawn = Math.min(ranked.length, bounds.rankMax);
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

function pairedScatterShape(roles: readonly RoleState[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	const xColumn = chosenOf(roles, 'across')[0];
	const yColumn = chosenOf(roles, 'up')[0];
	if (xColumn === undefined || yColumn === undefined) return unfilled('pairedScatter', roles);
	const named = chosenOf(roles, 'name')[0];
	const subjectColumn = named === undefined || named === ROW_NUMBER.value ? null : named;
	const drawn = rows.filter((row) => numericValue(row, xColumn) !== null && numericValue(row, yColumn) !== null);
	const subjects = subjectColumn === null ? drawn.length : new Set(drawn.map((row) => String(row[subjectColumn]))).size;
	return {
		kind: 'chart',
		type: 'pairedScatter',
		option: 'Paired',
		icon: 'shape-scatter',
		xColumn,
		yColumn,
		subjectColumn,
		readings: drawn.length,
		subjects,
		tooFew: drawn.length < bounds.fleetMinRows || subjects < bounds.bandwidthMinKinds,
		mainFigure: `${drawn.length} rows of ${yColumn} against ${xColumn}`,
		comparison: `${yColumn} against ${xColumn}`
	};
}

function distributionShape(roles: readonly RoleState[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	const valueColumn = chosenOf(roles, 'values')[0];
	if (valueColumn === undefined) return unfilled('distribution', roles);
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

/** What `type` draws with the columns its roles hold: a chart, or the one reason it cannot. */
export function chartShape(type: ExplorerChartType, roles: readonly RoleState[], columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds): ExplorerShape {
	if (type === 'dateSeries') return dateSeriesShape(roles, rows, bounds);
	if (type === 'rankedList') return rankedListShape(roles, columns, rows, bounds);
	if (type === 'pairedScatter') return pairedScatterShape(roles, rows, bounds);
	return distributionShape(roles, rows, bounds);
}

function fills(roles: readonly RoleState[]): boolean {
	return roles.every((state) => !state.role.needed || state.chosen.length > 0);
}

/** The chart the Chart tab shows for an answer: the reader's type when there is one, else the
 *  type the answer opens on, with each role resolved and what the box draws. With no type the box
 *  says whether another chart can be filled from these columns; when none can, it says so
 *  whichever tile is checked, because pressing another would not help. */
export function chooseChart(columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds, chosenType: ExplorerChartType | null = null, chosenRoles: ChosenRoles = {}): ExplorerChart {
	const type = chosenType ?? openingType(columns, rows);
	const fillable = CHART_KINDS.some((kind) => fills(resolveRoles(kind.type, columns, rows, bounds)));
	if (type === null) return { type, roles: [], shape: fillable ? NOT_PICKED : NO_NUMBER };
	const roles = resolveRoles(type, columns, rows, bounds, chosenRoles[type] ?? {});
	return { type, roles, shape: fillable ? chartShape(type, roles, columns, rows, bounds) : NO_NUMBER };
}

/** The sentences under a drawn chart, each only while it is true: the number columns the page's own
 *  lines leave out as too flat to draw, the rows a date chart leaves out because their day is NULL,
 *  and that the drawing reads only the first rows of an answer that stopped at its cap. */
export function chartNotes(shape: ExplorerShape, bounds: ExplorerShapeBounds, capped: boolean, maxRows: number): string[] {
	if (shape.kind === 'none') return [];
	const notes: string[] = [];
	if (shape.type === 'dateSeries' && shape.flatColumns.length > 0) {
		const share = Number((bounds.seriesFloorShare * 100).toFixed(1));
		const largest = shape.flatColumns[0].largestColumn;
		notes.push(
			shape.flatColumns.length === 1
				? `"${shape.flatColumns[0].name}" is left out: it is under ${share}% of "${largest}", so it would draw flat.`
				: `${shape.flatColumns.length} number columns are left out: each is under ${share}% of "${largest}", so each would draw flat.`
		);
	}
	if (shape.type === 'dateSeries' && shape.rowsWithNoDay > 0) {
		notes.push(
			shape.rowsWithNoDay === 1
				? `1 row holds null in the column "${shape.dateColumn}", so the chart does not draw it. It is in the table.`
				: `${shape.rowsWithNoDay} rows hold null in the column "${shape.dateColumn}", so the chart does not draw them. They are in the table.`
		);
	}
	if (capped) notes.push(`Drawn from the first ${plural(maxRows, 'row', 'rows')}.`);
	return notes;
}

/** The columns one role of the date chart can take, in the answer's order. */
function dateChartColumns(id: RoleId, columns: readonly Column[]): string[] {
	const role = chartKind('dateSeries').roles.find((one) => one.id === id);
	return role === undefined ? [] : roleOptions(role, columns).map((option) => option.value);
}

/** How many of the notes under a drawn chart this answer can give, whatever chart and columns the
 *  reader picks: the room the foot keeps. It reads the answer alone - its columns, its rows and
 *  whether it stopped at its cap - with the tests the notes themselves are written from, so it may
 *  count a note that never shows but never misses one that can: a number column the page's own
 *  lines leave out as flat under some column the `Date` role can take, a row with no day in some
 *  such column, and the cap. */
export function countChartNotes(columns: readonly Column[], rows: readonly Row[], bounds: ExplorerShapeBounds, capped: boolean): number {
	const dateColumns = dateChartColumns('date', columns);
	const numbers = dateChartColumns('lines', columns);
	const flat = dateColumns.some((dateColumn) => lineSplit(numbers, datedRowsOf(rows, dateColumn), bounds.seriesFloorShare).flat.length > 0);
	const noDay = dateColumns.some((dateColumn) => rowsWithNoDayIn(rows, dateColumn) > 0);
	return [flat, noDay, capped].filter(Boolean).length;
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
