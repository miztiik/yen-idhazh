/** The roles of each chart the Data explorer draws: which of an answer's columns can fill each
 * role, and how a role's pill names what fills it.
 *
 * `CHART_KINDS` is the one place the explorer's chart types, their order on the `Draw it as`
 * switch and their roles are written. The switch draws one tile for each type, the role row one
 * slot for each role of the type with the most roles, and the date chart one line for each of
 * the series colours, so a type with a fourth role or a fifth colour is one edit here and none in
 * the layout. The roles, their words and which columns fit each are Susan's (2026-10-07).
 */

// Relative, not `$lib`: the logic suite imports this module in plain Node.
import type { Column } from '../../data/slice-shapes';
import { classifyType, isDay, isNumber } from './type-family';

export type ExplorerChartType = 'dateSeries' | 'rankedList' | 'pairedScatter' | 'distribution';

export type RoleId = 'date' | 'lines' | 'name' | 'rankBy' | 'across' | 'up' | 'values';

/** The columns a role can take: a date or a timestamp, a whole number or a decimal, or any column. */
export type RoleTakes = 'day' | 'number' | 'any';

export type ChartRole = {
	id: RoleId;
	/** The word the pill prints before its column: eight characters at most, the room a pill gives it. */
	word: string;
	takes: RoleTakes;
	/** The role takes several columns, each a checkbox, at most one for each series colour. */
	several: boolean;
	/** The chart cannot draw without a column here. A role it can do without draws as today without one. */
	needed: boolean;
	/** The list offers `Row number` first, which names each row by its place in the answer. */
	rowNumber: boolean;
};

export type ChartKind = {
	type: ExplorerChartType;
	/** The word on the type's tile and the start of its chart's accessible name. */
	option: 'Over time' | 'Ranked' | 'Paired' | 'Spread';
	icon: 'shape-series' | 'shape-ranked' | 'shape-scatter' | 'shape-distribution';
	roles: readonly ChartRole[];
};

/** One line in a role's list: the column's name and engine type, or `Row number`, whose type is null. */
export type RoleOption = { value: string; name: string; type: string | null };

function role(id: RoleId, word: string, takes: RoleTakes, extra: Partial<Pick<ChartRole, 'several' | 'needed' | 'rowNumber'>> = {}): ChartRole {
	return { id, word, takes, several: false, needed: true, rowNumber: false, ...extra };
}

export const CHART_KINDS: readonly ChartKind[] = [
	{ type: 'dateSeries', option: 'Over time', icon: 'shape-series', roles: [role('date', 'Date', 'day'), role('lines', 'Lines', 'number', { several: true })] },
	{ type: 'rankedList', option: 'Ranked', icon: 'shape-ranked', roles: [role('name', 'Name', 'any'), role('rankBy', 'Rank by', 'number')] },
	{ type: 'pairedScatter', option: 'Paired', icon: 'shape-scatter', roles: [role('across', 'Across', 'number'), role('up', 'Up', 'number'), role('name', 'Name', 'any', { needed: false, rowNumber: true })] },
	{ type: 'distribution', option: 'Spread', icon: 'shape-distribution', roles: [role('values', 'Values', 'number')] }
];

/** The most roles any chart has: the number of slots the role row holds, empty slots included. */
export const MOST_ROLES = Math.max(...CHART_KINDS.map((kind) => kind.roles.length));

/** The explorer's series colours, in the order a several-column role's checked columns take them.
 * Their count is the most columns such a role holds. */
export const SERIES_TOKENS = ['--chart-1', '--chart-2', '--chart-3', '--chart-4'] as const;

/** What a several-column list says while it holds as many columns as there are series colours. */
export const AT_MOST_SENTENCE = 'Four at most. Uncheck one to choose another.';

/** The words a pill prints for a role with nothing in it. */
export const NONE = 'None';

/** The line that names each point by its row's place in the answer. Its value is empty, which no
 * column's name is, so it is never mistaken for a column. */
export const ROW_NUMBER: RoleOption = { value: '', name: 'Row number', type: null };

export function chartKind(type: ExplorerChartType): ChartKind {
	const kind = CHART_KINDS.find((one) => one.type === type);
	if (kind === undefined) throw new Error(`The Data explorer draws no chart type ${type}.`);
	return kind;
}

function takes(role: ChartRole, column: Column): boolean {
	if (role.takes === 'any') return true;
	const family = classifyType(column.type);
	return role.takes === 'day' ? isDay(family) : isNumber(family);
}

/** Every column that can fill `role`, in the order the answer holds them and named as the engine
 * names them, with `Row number` first where the role offers it. Nothing is sorted. */
export function roleOptions(role: ChartRole, columns: readonly Column[]): RoleOption[] {
	const fitting = columns.filter((column) => takes(role, column)).map((column) => ({ value: column.name, name: column.name, type: column.type }));
	return role.rowNumber ? [ROW_NUMBER, ...fitting] : fitting;
}

/** What a closed pill prints after its role word: the chosen column, `None` when nothing is
 * chosen, and for several columns the first in the answer's order and how many more there are,
 * as `summary_ms, 2 more`. `chosen` holds the chosen values in the answer's order. */
export function pillFace(options: readonly RoleOption[], chosen: readonly string[]): { name: string; more: string } {
	if (chosen.length === 0) return { name: NONE, more: '' };
	const first = options.find((option) => option.value === chosen[0])?.name ?? chosen[0];
	return { name: first, more: chosen.length > 1 ? `, ${chosen.length - 1} more` : '' };
}

/** A pill's accessible name: its role word and every chosen name whole, which the closed face
 * may cut short. */
export function pillName(role: ChartRole, options: readonly RoleOption[], chosen: readonly string[]): string {
	const names = chosen.map((value) => options.find((option) => option.value === value)?.name ?? value);
	return `${role.word}: ${names.length === 0 ? NONE : names.join(', ')}`;
}
