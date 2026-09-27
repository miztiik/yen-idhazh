/** Where each day sits on a chart that gives every day one equal slot of its plot.
 *
 * A second figure drawn under a day chart has to land on the same days, and two
 * calculations that agree today drift apart the day one margin moves. The run
 * squares under `Articles published against planned` were laid out by one
 * calculation from the strip's own centred start while the bars were laid out by
 * another from the chart's plot edge - about 41 and 43 px a day apart on the
 * real ledger - so reading down from a bar landed on the previous day's squares.
 * One function, and its one answer handed to both figures, is what stops that.
 */

/** The room either side of the plot, in CSS pixels. */
export interface SlotInset {
	left: number;
	right: number;
}

/** Every day's slot on one drawing, oldest first. */
export interface DaySlots {
	/** The whole drawing, margins included. */
	width: number;
	/** The plot's two edges. */
	left: number;
	right: number;
	/** One day's share of the plot. */
	slot: number;
	/** The middle of each day's slot. */
	centres: number[];
}

export function daySlots(width: number, days: number, inset: SlotInset): DaySlots {
	const left = inset.left;
	// A frame narrower than its own margins would flip the plot inside out.
	const right = Math.max(left, width - inset.right);
	const count = Math.max(0, Math.floor(days));
	const slot = (right - left) / Math.max(1, count);
	return {
		width,
		left,
		right,
		slot,
		centres: Array.from({ length: count }, (_, index) => left + index * slot + slot / 2)
	};
}
