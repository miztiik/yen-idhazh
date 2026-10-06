
import type { Column, Row } from '$lib/data/ledger';
import { classifyType, isDay, isNumber } from './type-family';
import { readUtcNanoseconds } from './utc-instant';

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
	switch (classifyType(column.type)) {
		case 'whole':
			return /^-?\d+$/.test(text) && text.replace('-', '').length <= 15
				? { text: groupedInt(text), kind: 'number' }
				: { text, kind: 'text' };
		case 'decimal': {
			const n = Number(text);
			return Number.isFinite(n) ? { text: numberText(n), kind: 'number' } : { text, kind: 'text' };
		}
		case 'timestamp':
			return { text: text.replace('T', ' ').replace(/Z$/, '').replace(/\.000$/, ''), kind: 'text' };
		case 'truth':
			return { text: text.toLowerCase() === 'true' ? 'true' : 'false', kind: 'boolean' };
		case 'bytes':
			return { text: `${text.length} bytes`, kind: 'blob' };
		case 'nested':
			return { text, kind: 'json' };
		default:
			return { text, kind: 'text' };
	}
}

function comparable(column: Column, row: Row): string | number | bigint | null {
	const value = row[column.name];
	if (value === null || value === undefined) return null;
	const text = rawText(value);
	const family = classifyType(column.type);
	if (isNumber(family)) {
		const n = Number(text);
		return Number.isFinite(n) ? n : text;
	}
	if (isDay(family)) return readUtcNanoseconds(text);
	return text.toLowerCase();
}

export function sortedRows(rows: readonly Row[], columns: readonly Column[], sort: SortSpec): Row[] {
	if (sort.direction === null) return [...rows];
	const column = columns.find((one) => one.name === sort.column);
	if (column === undefined) return [...rows];
	const factor = sort.direction === 'asc' ? 1 : -1;
	return rows.map((row, index) => ({ row, index, key: comparable(column, row) })).sort((a, b) => {
		if (a.key === null && b.key === null) return a.index - b.index;
		if (a.key === null) return 1;
		if (b.key === null) return -1;
		if (a.key < b.key) return -1 * factor;
		if (a.key > b.key) return 1 * factor;
		return a.index - b.index;
	}).map((entry) => entry.row);
}

export function nextSort(current: SortSpec, column: Column): SortSpec {
	if (current.column !== column.name || current.direction === null) {
		const family = classifyType(column.type);
		const direction = isNumber(family) || isDay(family) ? 'desc' : 'asc';
		return { column: column.name, direction };
	}
	if (current.direction === 'desc') return { column: column.name, direction: 'asc' };
	return { column: column.name, direction: null };
}

export function numericBarShare(column: Column, rows: readonly Row[], spreadShare: number): number | null {
	if (!isNumber(classifyType(column.type))) return null;
	const values = rows.map((row) => Number(rawText(row[column.name]))).filter((n) => Number.isFinite(n) && n >= 0);
	if (values.length !== rows.length || values.length === 0) return null;
	const max = Math.max(...values);
	const min = Math.min(...values);
	if (max <= 0 || min > max * spreadShare) return null;
	return max;
}
