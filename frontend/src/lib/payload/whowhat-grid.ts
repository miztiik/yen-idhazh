/** Read the separate, versioned actor/claim payload without chart assumptions. */

import { publishedVisualData } from './drawing';
import type { WhowhatGridData, WhowhatGridRow } from './types';

/** Mirrors `WhowhatGridData.schema_version()` in Python. */
export const WHOWHAT_GRID_VERSION = '2026-10-28';
export const WHOWHAT_GRID_MAX_ROWS = 8;
export const WHOWHAT_SOURCE_SPAN_MAX = 500;

type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(value: Json, allowed: readonly string[]): boolean {
	return Object.keys(value).every((key) => allowed.includes(key));
}

function boundedText(value: unknown): value is string {
	return (
		typeof value === 'string' &&
		Array.from(value).length > 0 &&
		Array.from(value).length <= WHOWHAT_SOURCE_SPAN_MAX
	);
}

function fittedText(value: unknown, source: string): value is string {
	return (
		boundedText(value) &&
		(value === source ||
			(Array.from(value).length > 3 &&
				Array.from(value).length < Array.from(source).length &&
				value.endsWith('...') &&
				source.startsWith(value.slice(0, -3)))
		)
	);
}

function sourceSpan(value: unknown, kind: 'entity' | 'claim'): boolean {
	if (!isObject(value)) return false;
	const allowed = [
		'element_id',
		'sentence_index',
		'span_start',
		'span_end',
		'span_excerpt',
		'display_text',
		'kind'
	];
	if (!hasOnlyKeys(value, allowed)) return false;
	if (
		value.kind !== kind ||
		typeof value.element_id !== 'string' ||
		!Number.isInteger(value.sentence_index) ||
		(value.sentence_index as number) < 0 ||
		!Number.isInteger(value.span_start) ||
		(value.span_start as number) < 0 ||
		!Number.isInteger(value.span_end) ||
		(value.span_end as number) <= (value.span_start as number) ||
		!boundedText(value.span_excerpt)
	) return false;
	if (
		(value.span_end as number) - (value.span_start as number) !==
		Array.from(value.span_excerpt).length
	) return false;
	if (value.element_id !== `${kind}-${value.span_start}-${value.span_end}`) return false;
	return fittedText(value.display_text, value.span_excerpt);
}

function row(value: unknown): value is WhowhatGridRow {
	if (!isObject(value) || !hasOnlyKeys(value, ['actor', 'claim'])) return false;
	if (!Object.hasOwn(value, 'actor') || !Object.hasOwn(value, 'claim')) return false;
	const actor = value.actor;
	const claim = value.claim;
	if (actor === null || claim === null) return actor === null && claim === null;
	if (!sourceSpan(actor, 'entity') || !sourceSpan(claim, 'claim')) return false;
	if (!isObject(actor) || !isObject(claim)) return false;
	return actor.sentence_index === claim.sentence_index;
}

/** Return a reason, never a repaired document or an approximate grid. */
export function refusedWhowhatGridData(data: unknown, itemId: string): string | null {
	if (!isObject(data) || !hasOnlyKeys(data, ['version', 'item_id', 'rows'])) {
		return 'is not a whowhat-grid document';
	}
	if (data.version !== WHOWHAT_GRID_VERSION) return 'was written for an unknown grid contract';
	if (data.item_id !== itemId) return 'names another item';
	const rows = data.rows;
	if (
		!Array.isArray(rows) ||
		rows.length === 0 ||
		rows.length > WHOWHAT_GRID_MAX_ROWS ||
		!rows.every(row)
	) return 'carries invalid rectangular rows';
	if (!(rows as WhowhatGridRow[]).some((one) => one.actor !== null && one.claim !== null)) {
		return 'carries no source-backed actor and claim pair';
	}
	return null;
}

/** The same check narrows a fetched value without a caller-side cast. */
export function isWhowhatGridData(data: unknown, itemId: string): data is WhowhatGridData {
	return refusedWhowhatGridData(data, itemId) === null;
}

/** One path rule for either visual family, plus the identity this item expects. */
export function publishedWhowhatGrid(path: string, itemId: string): boolean {
	return (
		publishedVisualData(path) &&
		path.slice(path.lastIndexOf('/') + 1) === `${itemId}.json`
	);
}
