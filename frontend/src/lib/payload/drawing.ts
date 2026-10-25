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
export const RENDERER_VERSION = '2026-10-25';
export const DRAWABLE = ['bar', 'dot', 'slope'] as const;
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
	if (!Array.isArray(marks) || marks.length === 0 || marks.length > 72) return 'carries an invalid number of marks';
	const held = new Map<string, Record<string, unknown>>();
	for (const mark of marks) {
		if (!isObject(mark) || typeof mark.mark_id !== 'string' || !/^m[0-9]{1,3}$/.test(mark.mark_id)) {
			return 'carries a mark with no valid id';
		}
		if (held.has(mark.mark_id)) return 'carries duplicate mark ids';
		if (!nullableText(mark.source_text) || !nullableText(mark.unit) || !nullableText(mark.text)) {
			return 'carries invalid mark text or unit';
		}
		held.set(mark.mark_id, mark);
	}
	const encoding = data.encoding;
	if (!isObject(encoding)) return 'carries no encoding';
	const drawn = new Set<string>();
	const channels: Record<string, string[]> = {};
	for (const role of ENCODING_ROLES) {
		const ids = encoding[role];
		if (!Array.isArray(ids) || !ids.every((id): id is string => typeof id === 'string')) {
			return 'carries a channel that is not a list of marks';
		}
		if (ids.length > 8) return 'carries too many marks in one channel';
		channels[role] = ids;
		for (const id of ids) {
			if (!held.has(id)) return 'draws a mark it does not carry';
			if (drawn.has(id)) return 'draws a mark twice';
			drawn.add(id);
		}
	}
	if (drawn.size !== held.size) return 'carries marks it does not draw';
	const figures = channels.quantity;
	for (const id of figures) {
		const value = held.get(id)?.value;
		if (typeof value !== 'string' || !value.trim() || !Number.isFinite(Number(value)) || held.get(id)?.text !== null) {
			return 'draws a bar with no finite figure';
		}
	}
	const textChannels: string[] = [];
	if (data.type === 'bar' || data.type === 'dot') {
		const names = channels.category;
		const series = channels.series;
		if (names.length === 0 || names.length !== figures.length) return 'names and figures do not pair';
		if (series.length !== 0 && series.length !== figures.length) return 'series labels do not pair with figures';
		if (
			channels.quantity_x.length !== 0 || channels.time.length !== 0 ||
			channels.entity.length !== 0 || channels.size.length !== 0 ||
			channels.bins.length !== 0 || channels.event_label.length !== 0
		) return 'carries a channel this chart does not draw';
		textChannels.push(...names, ...series);
	} else if (data.type === 'slope') {
		const times = channels.time;
		const entities = channels.entity;
		const series = channels.series;
		const lines = figures.length / 2;
		if (times.length !== 2 || figures.length < 4 || figures.length % 2 !== 0) {
			return 'does not pair quantities across two time labels';
		}
		if (entities.length === 0 && series.length === 0) return 'has no label for each slope line';
		if (entities.length !== 0 && entities.length !== lines) return 'entity labels do not pair with slope lines';
		if (series.length !== 0 && series.length !== lines) return 'series labels do not pair with slope lines';
		if (
			channels.category.length !== 0 || channels.quantity_x.length !== 0 ||
			channels.size.length !== 0 || channels.bins.length !== 0 ||
			channels.event_label.length !== 0
		) return 'carries a channel this chart does not draw';
		const timeLabels = times.map((id) => held.get(id)?.text);
		if (
			timeLabels.some((text) => typeof text !== 'string' || !text.trim()) ||
			timeLabels[0] === timeLabels[1]
		) {
			return 'has invalid or repeated slope time labels';
		}
		if (entities.length === 0 && new Set(series.map((id) => held.get(id)?.text)).size !== lines) {
			return 'slope lines need distinct series labels';
		}
		textChannels.push(...times, ...entities, ...series);
	} else {
		return 'names a type this page cannot draw';
	}
	for (const id of textChannels) {
		const mark = held.get(id);
		if (typeof mark?.text !== 'string' || !mark.text.trim() || mark.value !== null) {
			return 'draws a text channel without source text';
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
