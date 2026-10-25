/** Refuse chart data the current browser renderer cannot safely draw.
 *
 * Framing is untrusted text, never markup. Paths accept only published item
 * identities. Older renderers have no compatibility reader (owner, 2026-10-24).
 * This module has no runtime imports so plain Node and the browser share it.
 */
import type { VisualData } from './types';

const VISUAL_DATA_PATH =
	/^digest\/\d{4}\/\d{2}\/\d{2}\/[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})\.json$/;

/** Protocol stamp, held to the Python authority by the visual binding test. */
export const RENDERER_VERSION = '2026-10-24';
export const DRAWABLE = ['bar'] as const;
export const ENCODING_ROLES = [
	'category', 'quantity', 'quantity_x', 'time', 'series', 'size', 'bins', 'entity', 'event_label'
] as const;

export function publishedVisualData(path: string): boolean {
	return VISUAL_DATA_PATH.test(path);
}

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function nullableText(value: unknown): boolean {
	return value === null || typeof value === 'string';
}

/** Return a reason, never a repaired document or an approximate drawing. */
export function refusedVisualData(data: unknown): string | null {
	if (!isObject(data)) return 'is not a visual-data document';
	if (data.renderer_version !== RENDERER_VERSION) return 'was compiled for an unknown renderer';
	if (!DRAWABLE.some((type) => type === data.type)) return 'names a type this page cannot draw';
	if (typeof data.version !== 'string' || typeof data.item_id !== 'string') {
		return 'carries no document identity';
	}
	if (!nullableText(data.title) || !nullableText(data.caption)) return 'carries invalid framing';

	const marks = data.marks;
	if (!Array.isArray(marks) || marks.length === 0) return 'carries no marks';
	const held = new Map<string, Record<string, unknown>>();
	for (const mark of marks) {
		if (!isObject(mark) || typeof mark.mark_id !== 'string') return 'carries a mark with no id';
		if (held.has(mark.mark_id)) return 'carries duplicate mark ids';
		if (!nullableText(mark.source_text) || !nullableText(mark.unit)) return 'carries invalid source text or unit';
		held.set(mark.mark_id, mark);
	}
	const encoding = data.encoding;
	if (!isObject(encoding)) return 'carries no encoding';
	const drawn = new Set<string>();
	for (const role of ENCODING_ROLES) {
		const ids = encoding[role];
		if (!Array.isArray(ids)) return 'carries a channel that is not a list of marks';
		if (role !== 'category' && role !== 'quantity' && ids.length !== 0) {
			return 'carries a channel this bar renderer does not draw';
		}
		for (const id of ids) {
			if (typeof id !== 'string' || !held.has(id)) return 'draws a mark it does not carry';
			if (drawn.has(id)) return 'draws a mark twice';
			drawn.add(id);
		}
	}
	if (drawn.size !== held.size) return 'carries marks it does not draw';
	const names = encoding.category as string[];
	const figures = encoding.quantity as string[];
	if (names.length === 0 || names.length !== figures.length) return 'names and figures do not pair into bars';
	for (const id of names) {
		const text = held.get(id)?.text;
		if (typeof text !== 'string' || !text.trim()) return 'draws a bar with no name';
	}
	for (const id of figures) {
		const value = held.get(id)?.value;
		if (typeof value !== 'string' || !value.trim() || !Number.isFinite(Number(value))) {
			return 'draws a bar with no finite figure';
		}
	}
	if (typeof data.emphasized_mark_id !== 'string' || !figures.includes(data.emphasized_mark_id)) {
		return 'emphasizes no displayed quantity';
	}
	return null;
}

/** The same check narrows the fetched value without a caller-side cast. */
export function isVisualData(data: unknown): data is VisualData {
	return refusedVisualData(data) === null;
}
