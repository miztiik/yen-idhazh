/** Refuse chart data the current browser renderer cannot safely draw.
 *
 * Framing is untrusted text, never markup. Paths accept only published item
 * identities. Older renderers have no compatibility reader (maintainer, 2026-10-24).
 * This module has no runtime imports so plain Node and the browser share it.
 */
import type { VisualData } from './types';

const VISUAL_DATA_PATH =
	/^digest\/\d{4}\/\d{2}\/\d{2}\/[a-z0-9]+(?:-[a-z0-9]+)*-(?:[0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})\.json$/;

/** Protocol stamp, held to the Python authority by the visual binding test. */
export const RENDERER_VERSION = '2026-10-27T05:00';
export const DRAWABLE = ['bar', 'dot', 'line', 'scatter', 'bubble', 'slope', 'stacked_bar', 'pie', 'histogram'] as const;
export const MAX_PIE_PARTS = 5;
export const MAX_MARKS_PER_CHANNEL = 8;
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

function dateOrYear(value: unknown): value is string {
	if (typeof value !== 'string' || !/^\d{4}(?:-\d{2}-\d{2})?$/.test(value)) return false;
	if (value.length === 4) return true;
	const date = new Date(`${value}T00:00:00Z`);
	return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function schemaVersion(value: unknown): value is string {
	if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$/.test(value)) {
		return false;
	}
	const parsed = new Date(value.length === 10 ? `${value}T00:00:00Z` : `${value}Z`);
	return Number.isFinite(parsed.getTime()) && parsed.toISOString().startsWith(value.slice(0, 10));
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
	if (!nullableText(data.histogram_unit) || !nullableText(data.histogram_unit_table_version)) {
		return 'carries invalid histogram unit provenance';
	}
	if (
		data.histogram_unit_table_version !== null &&
		!schemaVersion(data.histogram_unit_table_version)
	) return 'carries an invalid histogram unit-table stamp';
	if (data.type !== 'histogram' &&
		(data.histogram_unit !== null || data.histogram_unit_table_version !== null)) {
		return 'carries histogram unit provenance for another chart type';
	}
	if (
		!nullableText(data.declared_whole_element_id) ||
		(data.declared_whole !== null && !isObject(data.declared_whole))
	) return 'carries invalid declared-whole evidence';

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
		if (mark.time !== undefined && mark.time !== null && !dateOrYear(mark.time)) {
			return 'carries an invalid canonical date or year';
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
		if (ids.length > MAX_MARKS_PER_CHANNEL) return 'carries too many marks in one channel';
		channels[role] = ids;
		for (const id of ids) {
			if (!held.has(id)) return 'draws a mark it does not carry';
			if (drawn.has(id)) return 'draws a mark twice';
			drawn.add(id);
		}
	}
	const timeIds = new Set(channels.time);
	for (const [markId, mark] of held) {
		if (timeIds.has(markId) !== dateOrYear(mark.time)) {
			return 'canonical dates appear only on time marks';
		}
	}
	if (drawn.size !== held.size) return 'carries marks it does not draw';
	if (
		data.type !== 'pie' && data.type !== 'stacked_bar' &&
		(data.declared_whole_element_id !== null || data.declared_whole !== null)
	) return 'carries a declared whole for a chart that has none';
	const figures = channels.quantity;
	for (const id of [...figures, ...channels.quantity_x, ...(data.type === 'bubble' ? channels.size : [])]) {
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
	} else if (data.type === 'stacked_bar') {
		const names = channels.category;
		const series = channels.series;
		if (names.length !== 1 || figures.length < 2 || series.length !== figures.length) {
			return 'does not pair one declared whole with every stacked part';
		}
		const whole = held.get(names[0])!;
		if (typeof whole.element_id !== 'string' || !/^quantity-/.test(whole.element_id)) {
			return 'does not cite a source quantity for its declared whole';
		}
		if (data.declared_whole_element_id !== whole.element_id || data.declared_whole !== null) {
			return 'does not identify its declared whole consistently';
		}
		if (figures.some((id) => {
			const part = held.get(id)!;
			if (part.element_id === whole.element_id) return true;
			return isObject(part.derived) &&
				Array.isArray(part.derived.inputs) &&
				part.derived.inputs.includes(whole.element_id);
		})) return 'uses its declared whole as one of its own parts';
		if (figures.some((id) => Number(held.get(id)?.value) < 0)) {
			return 'carries a negative stacked part';
		}
		if (
			channels.quantity_x.length !== 0 || channels.time.length !== 0 ||
			channels.entity.length !== 0 || channels.size.length !== 0 ||
			channels.bins.length !== 0 || channels.event_label.length !== 0
		) return 'carries a channel this stacked bar does not draw';
		if (new Set(series.map((id) => held.get(id)?.text)).size !== series.length) {
			return 'stacked-bar part labels are not distinct';
		}
		textChannels.push(...names, ...series);
	} else if (data.type === 'pie') {
		const names = channels.category;
		const wholeId = data.declared_whole_element_id;
		const whole = data.declared_whole;
		if (
			names.length < 2 || names.length > MAX_PIE_PARTS || names.length !== figures.length ||
			typeof wholeId !== 'string' || !/^quantity-/.test(wholeId) ||
			!isObject(whole) || whole.element_id !== wholeId ||
			typeof whole.text !== 'string' || !whole.text.trim()
		) return 'does not pair each pie part with a declared whole';
		if (
			channels.quantity_x.length !== 0 || channels.time.length !== 0 ||
			channels.series.length !== 0 || channels.entity.length !== 0 ||
			channels.size.length !== 0 || channels.bins.length !== 0 ||
			channels.event_label.length !== 0
		) return 'carries a channel this pie does not draw';
		const categories = names.map((id) => held.get(id)!);
		if (categories.some((mark) =>
			typeof mark.element_id !== 'string' || !/^(entity|place|date)-/.test(mark.element_id)
		)) return 'pie categories need source labels';
		if (new Set(categories.map((mark) => mark.text)).size !== names.length) {
			return 'pie category names are not distinct';
		}
		const partIds: string[] = [];
		for (const id of figures) {
			const part = held.get(id)!;
			const derived = part.derived;
			if (
				part.unit !== '%' || Number(part.value) < 0 || Number(part.value) > 100 ||
				!isObject(derived) || derived.function !== 'share_of_declared_whole' ||
				!Array.isArray(derived.inputs) || derived.inputs.length !== 2 ||
				derived.inputs[1] !== wholeId || typeof derived.inputs[0] !== 'string' ||
				!/^quantity-/.test(derived.inputs[0]) || derived.inputs[0] === wholeId
			) return 'pie parts must be shares of their separately stated whole';
			partIds.push(derived.inputs[0]);
		}
		if (new Set(partIds).size !== partIds.length) return 'pie part quantities are not distinct';
		textChannels.push(...names);
	} else if (data.type === 'histogram') {
		const bins = channels.bins;
		if (bins.length < 2 || bins.length > MAX_MARKS_PER_CHANNEL) {
			return 'carries an invalid number of histogram bins';
		}
		if (
			channels.category.length !== 0 || channels.quantity.length !== 0 ||
			channels.quantity_x.length !== 0 || channels.time.length !== 0 ||
			channels.series.length !== 0 || channels.size.length !== 0 ||
			channels.entity.length !== 0 || channels.event_label.length !== 0
		) return 'carries a channel this histogram does not draw';
		if (data.histogram_unit_table_version !== null && data.histogram_unit === null) {
			return 'carries a unit-table stamp without a histogram unit';
		}
		const cited = new Set<string>();
		let previousUpper: number | null = null;
		let firstWidth: number | null = null;
		for (const [index, id] of bins.entries()) {
			const bin = held.get(id)!;
			const derived = bin.derived;
			if (
				!isObject(derived) || derived.function !== 'count' ||
				!Array.isArray(derived.inputs) || derived.inputs.length === 0 ||
				!derived.inputs.every((input): input is string => typeof input === 'string') ||
				typeof derived.bin_lower !== 'string' || typeof derived.bin_upper !== 'string' ||
				bin.unit !== null || typeof bin.value !== 'string'
			) return 'carries a histogram bin without count provenance';
			const lower = Number(derived.bin_lower);
			const upper = Number(derived.bin_upper);
			const count = Number(bin.value);
			const width = upper - lower;
			if (
				!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper ||
				!Number.isInteger(count) || count !== derived.inputs.length
			) return 'carries an empty or invalid histogram bin';
			if (previousUpper !== null && previousUpper !== lower) {
				return 'carries histogram bins with gaps or overlaps';
			}
			if (firstWidth === null) firstWidth = width;
			const precision = Math.max(Math.abs(firstWidth), Math.abs(width), 1) * Number.EPSILON * 16;
			if (Math.abs(width - firstWidth) > precision) {
				return 'carries histogram bins with unequal widths';
			}
			for (const input of derived.inputs) {
				if (!/^quantity-/.test(input) || cited.has(input)) {
					return 'carries repeated or invalid histogram input provenance';
				}
				cited.add(input);
			}
			previousUpper = upper;
		}
		if (!bins.every((id) => held.get(id)?.text === null)) {
			return 'carries text on a measured histogram bin';
		}
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
		const canonicalTimes = times.map((id) => held.get(id)?.time);
		if (
			timeLabels.some((text) => typeof text !== 'string' || !text.trim()) ||
			timeLabels[0] === timeLabels[1] ||
			!dateOrYear(canonicalTimes[0]) ||
			!dateOrYear(canonicalTimes[1]) ||
			canonicalTimes[0] === canonicalTimes[1]
		) {
			return 'has invalid or repeated slope time labels';
		}
		if (entities.length === 0 && new Set(series.map((id) => held.get(id)?.text)).size !== lines) {
			return 'slope lines need distinct series labels';
		}
		textChannels.push(...times, ...entities, ...series);
	} else if (data.type === 'scatter') {
		if (
			figures.length === 0 || channels.quantity_x.length !== figures.length ||
			channels.entity.length !== figures.length
		) return 'a scatter pairs one entity with both measures';
		if (channels.series.length !== 0 && channels.series.length !== figures.length) {
			return 'a scatter pairs one series label with every point';
		}
		if (
			channels.category.length !== 0 || channels.time.length !== 0 ||
			channels.size.length !== 0 || channels.bins.length !== 0 ||
			channels.event_label.length !== 0
		) return 'carries a channel this scatter does not draw';
		const entities = channels.entity.map((id) => held.get(id)!);
		if (entities.some((mark) =>
			typeof mark.element_id !== 'string' || !/^(entity|place)-/.test(mark.element_id)
		)) {
			return 'scatter entities need source element references';
		}
		if (
			new Set(entities.map((mark) => mark.element_id)).size !== figures.length ||
			new Set(entities.map((mark) => mark.text)).size !== figures.length
		) return 'scatter entity labels must be distinct';
		textChannels.push(...channels.entity, ...channels.series);
	} else if (data.type === 'bubble') {
		if (
			figures.length === 0 || channels.quantity_x.length !== figures.length ||
			channels.size.length !== figures.length || channels.entity.length !== figures.length
		) return 'a bubble pairs one entity with both positions and size';
		if (channels.series.length !== 0 && channels.series.length !== figures.length) {
			return 'a bubble pairs one series label with every point';
		}
		if (
			channels.category.length !== 0 || channels.time.length !== 0 ||
			channels.bins.length !== 0 || channels.event_label.length !== 0
		) return 'carries a channel this bubble does not draw';
		if (channels.size.some((id) => Number(held.get(id)?.value) <= 0)) {
			return 'bubble size measures must be positive';
		}
		const entities = channels.entity.map((id) => held.get(id)!);
		if (entities.some((mark) =>
			typeof mark.element_id !== 'string' || !/^(entity|place)-/.test(mark.element_id)
		)) {
			return 'bubble entities need source element references';
		}
		if (
			new Set(entities.map((mark) => mark.element_id)).size !== figures.length ||
			new Set(entities.map((mark) => mark.text)).size !== figures.length
		) return 'bubble entity labels must be distinct';
		textChannels.push(...channels.entity, ...channels.series);
	} else if (data.type === 'line') {
		const times: string[] = [];
		for (const id of channels.time) {
			const value = held.get(id)?.time;
			if (!dateOrYear(value)) return 'a line time has no canonical date or year';
			times.push(value);
		}
		if (times.length < 2 || times.length !== figures.length) {
			return 'does not pair at least two quantities with dates';
		}
		if (channels.series.length !== 0 && channels.series.length !== figures.length) {
			return 'series labels do not pair with line quantities';
		}
		if (
			channels.category.length !== 0 || channels.quantity_x.length !== 0 ||
			channels.entity.length !== 0 || channels.size.length !== 0 ||
			channels.bins.length !== 0 || channels.event_label.length !== 0
		) return 'carries a channel this line does not draw';
		if (new Set(times.map((value) => value.length)).size !== 1) {
			return 'mixes year and day precision';
		}
		const names: string[] = [];
		for (const id of channels.series) {
			const name = held.get(id)?.text;
			if (typeof name !== 'string') return 'draws a text channel without source text';
			names.push(name);
		}
		const datesBySeries = new Map<string, Set<string>>();
		const countsBySeries = new Map<string, number>();
		for (const [index, date] of times.entries()) {
			const name = names[index] ?? '';
			const dates = datesBySeries.get(name) ?? new Set<string>();
			if (dates.has(date)) return 'has two readings for one series and date';
			dates.add(date);
			datesBySeries.set(name, dates);
			countsBySeries.set(name, (countsBySeries.get(name) ?? 0) + 1);
		}
		if ([...countsBySeries.values()].some((count) => count < 2)) {
			return 'each line series needs at least two dates';
		}
		textChannels.push(...channels.time, ...channels.series);
	} else {
		return 'names a type this page cannot draw';
	}
	for (const id of textChannels) {
		const mark = held.get(id);
		if (typeof mark?.text !== 'string' || !mark.text.trim() || mark.value !== null) {
			return 'draws a text channel without source text';
		}
	}
	const emphasizedChannel = data.type === 'histogram' ? channels.bins : figures;
	if (typeof data.emphasized_mark_id !== 'string' || !emphasizedChannel.includes(data.emphasized_mark_id)) {
		return 'emphasizes no displayed quantity';
	}
	return null;
}

/** The same check narrows the fetched value without a caller-side cast. */
export function isVisualData(data: unknown): data is VisualData {
	return refusedVisualData(data) === null;
}
