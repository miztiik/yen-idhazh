/** Which named thing is worst: rows ranked by one magnitude, each a bar of the same scale.
 *
 * The ranking is `rank.ts`'s, by magnitude and descending with a total order on
 * ties, because that module is the one place this console decides an order.
 * What this adds is a row's segments: the parts of its one bar, each measured
 * against the same divisor as the bar, so a part and the bar it sits in can
 * never be read against two different scales.
 *
 * Drawn by `RankedList.svelte`, as markup rather than a chart: seventy rows
 * would be seventy chart instances, and markup still draws with no script.
 */
import { percentOf, rank } from '../rank';

/** A middle reading and its highest reading on one caller-owned track. */
export interface RangeMark {
	median: number | null;
	max: number | null;
	medianWidth: string;
	notchWidth: string;
	empty: boolean;
}

export function rangeMark(middle: number | null, highest: number | null, scale: number): RangeMark {
	if (middle === null && highest === null) {
		return { median: null, max: null, medianWidth: '0%', notchWidth: '0%', empty: true };
	}
	const fraction = (value: number | null) =>
		value === null || scale <= 0 ? 0 : Math.min(value / scale, 1);
	return {
		median: middle,
		max: highest,
		medianWidth: percentOf(fraction(middle)),
		notchWidth: percentOf(fraction(highest)),
		empty: false
	};
}

export interface RankedInput {
	label: string;
	value: number;
	segments?: readonly { label: string; value: number }[];
}

export interface RankedOptions {
	/** The most rows drawn. Every row, where it is absent. */
	max?: number;
}

export interface RankedSegment {
	label: string;
	value: number;
	/** Where the part starts along the track, as a CSS length. */
	start: string;
	/** How long it is along the same track, as a CSS length. */
	size: string;
}

export interface RankedEntry {
	label: string;
	value: number;
	/** `value / max`, 0 to 1. */
	fraction: number;
	/** The same fraction as a CSS length, for the bar's inline size. */
	percent: string;
	segments: RankedSegment[];
}

export interface RankedGeometry {
	rows: RankedEntry[];
	/** The divisor every length was taken against. The list prints it, because
	 * a bar scaled to a hidden maximum can be read for order and not for size. */
	max: number;
	/** Rows the cap left off, and their magnitudes summed, for the tail line. */
	hidden: number;
	hiddenValue: number;
}

function segmentsOf(row: RankedInput, max: number): RankedSegment[] {
	const parts = row.segments ?? [];
	let sum = 0;
	const placed = parts.map((part) => {
		if (!Number.isFinite(part.value) || part.value < 0) {
			throw new RangeError(`"${row.label}" has a part "${part.label}" of ${part.value}; a part is a magnitude.`);
		}
		const start = sum;
		sum += part.value;
		return { label: part.label, value: part.value, start: percentOf(start / max), size: percentOf(part.value / max) };
	});
	// Adding fractions can land a hair over the row; the bound is the rounding
	// error of the sum itself. Past it, the parts claim more than the row does.
	if (sum - row.value > Number.EPSILON * parts.length * Math.max(1, sum)) {
		throw new RangeError(`The parts of "${row.label}" add to ${sum}, more than its ${row.value}.`);
	}
	return placed;
}

/** The ranked rows, or null where nothing has a magnitude to rank. */
export function rankedList(rows: readonly RankedInput[], opts: RankedOptions): RankedGeometry | null {
	if (opts.max !== undefined && (!Number.isInteger(opts.max) || opts.max < 1)) {
		throw new RangeError(`A ranked list draws one row or more; asked for ${opts.max}.`);
	}
	const named = new Set<string>();
	for (const row of rows) {
		if (named.has(row.label)) throw new Error(`A ranked list names each thing once; "${row.label}" came twice.`);
		named.add(row.label);
		if (row.value < 0) {
			throw new RangeError(`"${row.label}" is ${row.value}; a ranked list takes a magnitude, never a signed value.`);
		}
	}
	const ranked = rank(
		rows.map((row) => ({
			key: row.label,
			value: row.value,
			row: { label: row.label, value: String(row.value), input: row }
		})),
		opts.max ?? 0
	);
	if (ranked.empty || ranked.max <= 0) return null;
	return {
		rows: ranked.rows.map((entry) => ({
			label: entry.key,
			value: entry.value,
			fraction: entry.fraction,
			percent: entry.percent,
			segments: segmentsOf(entry.row.input, ranked.max)
		})),
		max: ranked.max,
		hidden: ranked.hidden,
		hiddenValue: ranked.hiddenValue
	};
}
