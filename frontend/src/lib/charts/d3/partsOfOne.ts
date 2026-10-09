/** What one thing is made of: each row a single total, split into its parts in a fixed order.
 *
 * Every row is measured against the largest row, so rows compare by length and
 * the list prints the divisor. The parts sit in the caller's `order` on every
 * row, so a part is always in the same place and always the same hue, and a
 * reader finds it by position before they read its name.
 *
 * **Overlapping parts are brackets, not segments.** Where the parts are not
 * shares of the total - one item counted under two causes, say - they do not
 * add up to the row, and a stack would draw a total nobody measured. With
 * `overlapping`, every part starts at the origin and the row has no total.
 *
 * Drawn as markup, not paths: a part is a length along a track.
 */
import { UNRECORDED_STOP } from '../machine-colour';
import { percentOf } from '../rank';
import type { ChartToken } from '../theme';

export interface PartsInput {
	label: string;
	parts: readonly { label: string; value: number }[];
}

export interface PartsOptions {
	/** Every part's name, in the order they sit on a row. */
	order: readonly string[];
	overlapping?: boolean;
	/** Caller colours in part order; omitted callers keep the categorical ramp. */
	tokens?: readonly ChartToken[];
}

export interface PartSegment {
	label: string;
	value: number;
	token: ChartToken;
	/** Where the part starts along the track, as a CSS length. */
	start: string;
	/** How long it is along the same track. */
	size: string;
}

export interface PartsRow {
	label: string;
	/** The parts added up, or null where they overlap and do not add up. */
	total: number | null;
	segments: PartSegment[];
}

export interface PartsGeometry {
	rows: PartsRow[];
	/** The divisor every length was taken against: the longest row. */
	max: number;
	overlapping: boolean;
	/** Each part in order with its hue, for the key. */
	key: { label: string; token: ChartToken }[];
}

/** The hues a part may take, in order: the categorical ramp up to, and never
 * including, the grey the ramp keeps for an absence. */
function hueOf(index: number): ChartToken {
	return `--chart-${index + 1}` as ChartToken;
}

/** The rows split into their parts, or null where no row has anything in it. */
export function partsOfOne(rows: readonly PartsInput[], opts: PartsOptions): PartsGeometry | null {
	const overlapping = opts.overlapping ?? false;
	const hues = UNRECORDED_STOP - 1;
	if (opts.order.length > hues) {
		throw new RangeError(`A row splits into at most ${hues} parts, one hue each; the order names ${opts.order.length}.`);
	}
	const place = new Map(opts.order.map((label, index) => [label, index]));
	const tokenOf = (index: number): ChartToken => opts.tokens?.[index] ?? hueOf(index);
	if (place.size !== opts.order.length) throw new Error('The order names one part twice.');

	const measured = rows.map((row) => {
		const seen = new Set<string>();
		const parts = row.parts.map((part) => {
			const index = place.get(part.label);
			if (index === undefined) throw new Error(`"${row.label}" has a part "${part.label}" the order does not name.`);
			if (seen.has(part.label)) throw new Error(`"${row.label}" has the part "${part.label}" twice.`);
			seen.add(part.label);
			if (!Number.isFinite(part.value) || part.value < 0) {
				throw new RangeError(`"${row.label}" has "${part.label}" at ${part.value}; a part is a magnitude.`);
			}
			return { ...part, index };
		});
		parts.sort((left, right) => left.index - right.index);
		const extent = overlapping
			? parts.reduce((most, part) => Math.max(most, part.value), 0)
			: parts.reduce((sum, part) => sum + part.value, 0);
		return { row, parts, extent };
	});
	const max = measured.reduce((most, entry) => Math.max(most, entry.extent), 0);
	if (max <= 0) return null;

	return {
		rows: measured.map(({ row, parts, extent }) => {
			let start = 0;
			const segments = parts
				.filter((part) => part.value > 0)
				.map((part) => {
					const at = overlapping ? 0 : start;
					start += part.value;
					return {
						label: part.label,
						value: part.value,
						token: tokenOf(part.index),
						start: percentOf(at / max),
						size: percentOf(part.value / max)
					};
				});
			return { label: row.label, total: overlapping ? null : extent, segments };
		}),
		max,
		overlapping,
		key: opts.order.map((label, index) => ({ label, token: tokenOf(index) }))
	};
}
