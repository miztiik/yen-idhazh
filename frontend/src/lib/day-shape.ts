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
