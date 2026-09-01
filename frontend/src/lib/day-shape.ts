/** How a day's items are laid out, as arithmetic.
 *
 * Separate from the component for the same reason the run strip's axis is:
 * the rules here are decisions - which topic pills stay on the row, and which
 * of the day's leads the page can actually reach - and a decision is worth
 * testing without a browser.
 *
 * Nothing here removes, hides or re-orders an item. The stream carries the
 * whole day in the published order, and the leading block is a set of anchors
 * into it.
 */

import type { DigestItem, DigestLead, DigestVerticalRef } from './payload/types';

/** One entry of the leading block, as the component draws it. */
export interface LeadingStory {
	item_id: string;
	title: string;
	reason: string;
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

/** The needle a field is really filtering by, or null while it is too short.
 *
 * One letter narrows nothing - measured 2026-09-01 over the 12 committed days
 * and 4,203 story titles, the median single letter is in 80.2 percent of them
 * and `e` is in 99.8 percent - so a list that redraws on the first keystroke is
 * work the reader watches for no answer. `ui.filter_min_chars` is where the
 * threshold lives, and this is the one place that reads it, so the day page and
 * the archive cannot come to disagree about when a field starts filtering.
 *
 * The floor of 1 is not defensive: a caller handing this a zero would turn an
 * empty box into a filter that matches everything and prints a count, which
 * reads as a filter that is on.
 */
export function filterNeedle(query: string, minChars: number): string | null {
	const needle = query.trim().toLowerCase();
	return needle.length >= Math.max(minChars, 1) ? needle : null;
}

/** The stories a needle keeps, out of whatever list it is handed.
 *
 * **It takes the list rather than holding one.** A reading route seeds its
 * document with the head of the day and fetches the rest, so a filter that
 * captured the items once would narrow the seed for ever and hide everything
 * that arrived afterwards, with nothing on screen saying so.
 */
export function matchItems(items: DigestItem[], needle: string | null): DigestItem[] {
	if (needle === null) return items;
	return items.filter(
		(item) =>
			item.title.toLowerCase().includes(needle) ||
			item.summary.toLowerCase().includes(needle) ||
			item.key_points.some((point) => point.toLowerCase().includes(needle))
	);
}

/** The day's leads, resolved against the stories this page actually holds.
 *
 * Every entry is an anchor into the stream, so a lead the page cannot reach is
 * a link to nothing. Where that happens the lead is dropped and the rest of the
 * block still draws - degrade, do not fail.
 *
 * It cannot happen today: the reading routes render the whole day, and
 * `DigestDay` refuses a lead naming a story the payload does not hold. It
 * becomes reachable the moment a route draws part of a day, because the leads
 * are chosen across the whole day and are NOT a prefix of the published order.
 */
export function leadingStories(leads: DigestLead[], items: DigestItem[]): LeadingStory[] {
	const titles = new Map(items.map((item) => [item.item_id, item.title]));
	return leads
		.filter((lead) => titles.has(lead.item_id))
		.map((lead) => ({
			item_id: lead.item_id,
			title: titles.get(lead.item_id) as string,
			reason: lead.reason
		}));
}
