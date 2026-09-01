/** How a day's items are laid out, as arithmetic.
 *
 * Separate from the component for the same reason the run strip's axis is:
 * the rules here are decisions - when a day has a shape worth showing, and
 * which items each topic gets - and a decision is worth testing without a
 * browser.
 *
 * Nothing here removes, hides or re-orders an item. A slice is the head of the
 * published order, and the whole topic stays one link away.
 */

import type { DigestItem, DigestVerticalRef } from './payload/types';

export interface TopicSlice {
	vertical: DigestVerticalRef;
	/** The head of the topic's published order, at most `limit` long. */
	items: DigestItem[];
	/** The day published more of this topic than the slice shows. */
	hasMore: boolean;
}

/** The topic row split into the pills that stay out and the pills that fold away. */
export interface PillSplit {
	/** On the row, in the payload's own topic order. */
	shown: DigestVerticalRef[];
	/** Inside the disclosure, in the payload's own topic order. */
	folded: DigestVerticalRef[];
}

/** Which topic pills stay on the row, and which go inside the `+N more` control.
 *
 * The cut is decided by each topic's story count, at build time. It cannot be
 * decided by measuring the row: every page here is prerendered, so a row that
 * measures itself is wrong until a script runs, which is the one moment a
 * static site is supposed to be already finished.
 *
 * The topic the reader is on is always on the row. Folding it away would hide
 * the only mark saying where they are, and it is the one pill they came for.
 *
 * Order is the payload's, in both halves, never the count order the cut used.
 * `day.items` is grouped by desk and the pills already read alphabetically, so
 * re-sorting by size would move a topic between two days for a reason a reader
 * cannot see.
 */
export function splitPills(
	verticals: DigestVerticalRef[],
	active: string | null,
	limit: number
): PillSplit {
	if (verticals.length <= limit) return { shown: verticals, folded: [] };
	const keep = new Set(
		[...verticals]
			.sort((a, b) => b.count - a.count || a.id.localeCompare(b.id))
			.slice(0, Math.max(limit, 1))
			.map((vertical) => vertical.id)
	);
	if (active !== null) keep.add(active);
	return {
		shown: verticals.filter((vertical) => keep.has(vertical.id)),
		folded: verticals.filter((vertical) => !keep.has(vertical.id))
	};
}

/** Whether the all-topics view should render sections instead of one queue.
 *
 * A topic route already has a subject and a filter already has one, so both
 * stay flat. So does a day that ran to a single topic: one heading over the
 * whole page states what the page already says, and it would put items behind
 * a link that leads back to the same list.
 */
export function shouldGroup(
	vertical: string | null,
	query: string,
	verticals: DigestVerticalRef[]
): boolean {
	return vertical === null && query === '' && verticals.length > 1;
}

/** One slice per topic, in the payload's own topic order, empty ones dropped.
 *
 * An empty section is a heading over nothing, which reads as broken software.
 * It happens for real when a reader hides what they have read.
 */
export function topicSlices(
	verticals: DigestVerticalRef[],
	items: DigestItem[],
	limit: number
): TopicSlice[] {
	const slices: TopicSlice[] = [];
	for (const vertical of verticals) {
		const own = items.filter((item) => item.vertical === vertical.id);
		if (own.length === 0) continue;
		slices.push({
			vertical,
			items: own.slice(0, limit),
			// Against the day's own count, not the slice's: a reader who hid what
			// they read has not made the rest of the topic stop existing.
			hasMore: vertical.count > limit
		});
	}
	return slices;
}
