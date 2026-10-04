
import type { Column, Row } from '$lib/data/ledger';

export type SortDirection = 'asc' | 'desc' | null;
export type SortSpec = { column: string; direction: SortDirection };
export type PrintedCell = { text: string; kind: 'null' | 'number' | 'text' | 'boolean' | 'json' | 'blob' };

function groupedInt(text: string): string {
	const sign = text.startsWith('-') ? '-' : '';
	const digits = sign ? text.slice(1) : text;
	if (digits.length < 5) return text;
	return `${sign}${digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
}

function numberText(value: number): string {
	if (!Number.isFinite(value)) return String(value);
	if (value !== 0 && Math.abs(value) < 0.001) return value.toExponential(2);
	if (Number.isInteger(value)) return groupedInt(String(value));
	return value.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

function typeName(column: Column): string {
	return column.type.toUpperCase();
}

function rawText(value: Row[string]): string {
	if (value === null) return 'null';
	if (typeof value === 'string') return value;
	if (typeof value === 'number') return String(value);
	if (typeof value === 'boolean') return value ? 'true' : 'false';
	return JSON.stringify(value);
}

export function printCell(column: Column, value: Row[string]): PrintedCell {
	if (value === null || rawText(value).toUpperCase() === 'NULL') return { text: 'null', kind: 'null' };
	const text = rawText(value);
	const type = typeName(column);
	if (/^U?BIGINT$|^INTEGER$|^U?INTEGER$|^SMALLINT$|^TINYINT$/.test(type)) {
		return /^-?\d+$/.test(text) && text.replace('-', '').length <= 15
			? { text: groupedInt(text), kind: 'number' }
			: { text, kind: 'text' };
	}
	if (type.includes('DOUBLE') || type.includes('FLOAT') || type.includes('DECIMAL') || type.includes('REAL')) {
		const n = Number(text);
		return Number.isFinite(n) ? { text: numberText(n), kind: 'number' } : { text, kind: 'text' };
	}
	if (type === 'DATE') return { text: text.slice(0, 10), kind: 'text' };
	if (type.includes('TIMESTAMP')) return { text: text.replace('T', ' ').replace(/Z$/, '').replace(/\.000$/, ''), kind: 'text' };
	if (type === 'BOOLEAN' || type === 'BOOL') return { text: text.toLowerCase() === 'true' ? 'true' : 'false', kind: 'boolean' };
	if (type.includes('BLOB')) return { text: `${text.length} bytes`, kind: 'blob' };
	if (type.includes('LIST') || type.includes('STRUCT') || type.includes('MAP')) return { text, kind: 'json' };
	return { text, kind: 'text' };
}

function comparable(column: Column, row: Row): string | number | null {
	const value = row[column.name];
	if (value === null || value === undefined) return null;
	const text = rawText(value);
	const type = typeName(column);
	if (type.includes('INT') || type.includes('DOUBLE') || type.includes('FLOAT') || type.includes('DECIMAL') || type.includes('REAL')) {
		const n = Number(text);
		return Number.isFinite(n) ? n : text;
	}
	if (type === 'DATE' || type.includes('TIMESTAMP')) return Date.parse(text.length === 10 ? `${text}T00:00:00Z` : text);
	return text.toLowerCase();
}

export function sortedRows(rows: readonly Row[], columns: readonly Column[], sort: SortSpec): Row[] {
	if (sort.direction === null) return [...rows];
	const column = columns.find((one) => one.name === sort.column);
	if (column === undefined) return [...rows];
	const factor = sort.direction === 'asc' ? 1 : -1;
	return rows.map((row, index) => ({ row, index })).sort((a, b) => {
		const left = comparable(column, a.row);
		const right = comparable(column, b.row);
		if (left === null && right === null) return a.index - b.index;
		if (left === null) return 1;
		if (right === null) return -1;
		if (left < right) return -1 * factor;
		if (left > right) return 1 * factor;
		return a.index - b.index;
	}).map((entry) => entry.row);
}

export function nextSort(current: SortSpec, column: Column): SortSpec {
	if (current.column !== column.name || current.direction === null) {
		const type = typeName(column);
		const direction = type.includes('INT') || type.includes('DOUBLE') || type.includes('FLOAT') || type.includes('DECIMAL') || type === 'DATE' || type.includes('TIMESTAMP') ? 'desc' : 'asc';
		return { column: column.name, direction };
	}
	if (current.direction === 'desc') return { column: column.name, direction: 'asc' };
	return { column: column.name, direction: null };
}

export function numericBarShare(column: Column, rows: readonly Row[], spreadShare: number): number | null {
	const values = rows.map((row) => Number(rawText(row[column.name]))).filter((n) => Number.isFinite(n) && n >= 0);
	if (values.length !== rows.length || values.length === 0) return null;
	const max = Math.max(...values);
	const min = Math.min(...values);
	if (max <= 0 || min > max * spreadShare) return null;
	return max;
}
