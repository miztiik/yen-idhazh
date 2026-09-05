/** How a day's items are laid out, as arithmetic.
 *
 * Separate from the component for the same reason the run strip's axis is:
 * the rules here are decisions - which topic pills stay on the row, which of
 * the day's leads the page can actually reach, and what order the stream runs
 * in - and a decision is worth testing without a browser.
 *
 * Nothing here removes or hides an item. `orderByTime` re-orders and the set it
 * returns is the set it was given, which `frontend/tests/time-rail.spec.ts`
 * asserts over every committed day.
 */

import { railTime, type RailTime } from './format';
import type { DigestItem, DigestLead, DigestVerticalRef, SeededVisual } from './payload/types';

/** The arrived stories, with the seeded ones keeping the drawing they came with.
 *
 * The build reads a seeded story's SVG off disk and puts it in the document, so
 * the drawing can read the page's colours. The served day carries no such thing
 * and never will - it is fetched by every reader past the seed, and a drawing
 * averages 12.7 KB. So swapping the arrived list in wholesale takes the seed's
 * drawings straight back out, and the first screen falls to the carrier this
 * exists to replace. Measured 2026-09-05 on `/2026-09-04/` before the fix: one
 * figure, an inline drawing in the document and an `img` again a second later.
 *
 * Only a story the document seeded can gain anything here, so every other story
 * is returned untouched.
 */
export function keepDrawings(seeded: DigestItem[], arrived: DigestItem[]): DigestItem[] {
	const drawings = new Map<string, SeededVisual>();
	for (const item of seeded) {
		const visual = item.visual as SeededVisual | null;
		if (visual?.markup) drawings.set(item.item_id, visual);
	}
	if (drawings.size === 0) return arrived;
	return arrived.map((item) => {
		const visual = drawings.get(item.item_id);
		return visual ? { ...item, visual } : item;
	});
}

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

/** A thin desk's shortfall, in the two numbers its sentence needs. */
export interface DeskShortfall {
	/** Distinct stories the sources offered this desk today. */
	offered: number;
	/** How many of those were too old to run. */
	tooOld: number;
}

/** Why this desk is thin, or null where there is nothing worth saying.
 *
 * Three clauses, and all three have to hold. A sentence under every desk is a
 * column of absences pretending to be information, so the rule has to refuse
 * more often than it fires.
 *
 * 1. **The desk is thin** - at or under `thinMax` stories, which is one page of
 *    the stream. Above it the reader is scrolling, not wondering.
 * 2. **Something was rejected for age.** With nothing dropped there is no
 *    reason to name, and "the sources had three stories" is a fact with no
 *    explanation attached.
 * 3. **The sources offered more than the desk ran.** `considered` is counted
 *    per run and the day's stories accumulate across runs, so it is not an
 *    upper bound on `count` - and a sentence saying the sources offered fewer
 *    stories than the page is showing reads as a broken number.
 *
 * A day published before the counts existed carries none of them, and absent is
 * unknown rather than zero: it fires nothing.
 */
export function deskShortfall(
	desk: DigestVerticalRef | undefined,
	thinMax: number
): DeskShortfall | null {
	if (!desk) return null;
	const offered = desk.considered;
	const tooOld = desk.too_old;
	if (offered === undefined || offered === null) return null;
	if (tooOld === undefined || tooOld === null) return null;
	if (desk.count > thinMax) return null;
	if (tooOld < 1) return null;
	if (offered <= desk.count) return null;
	return { offered, tooOld };
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

/** The day's stories, newest first by the time the item carries.
 *
 * **This is a re-order and never a filter.** The array it returns holds exactly
 * the items it was handed; a story with no time keeps its place at the end
 * rather than dropping out, because "we could not date this" is not a reason to
 * stop publishing it.
 *
 * The order it replaces is the published one, which is desk-blocked rather than
 * ranked - the whole of one desk, then the whole of the next - so a reader
 * scrolling it met the same desk ninety times before the next one started.
 * Nothing editorial is lost by re-ordering it: what the day thinks is important
 * is in the leading block, chosen across the whole day.
 *
 * `item_id` breaks a tie, and it is derived from the story's own address, so
 * two builds of one day agree and nothing about the order can be gamed.
 */
export function orderByTime(items: DigestItem[]): DigestItem[] {
	return [...items].sort((left, right) => {
		const a = left.published_at;
		const b = right.published_at;
		if (a !== b) {
			if (!a) return 1;
			if (!b) return -1;
			return a < b ? 1 : -1;
		}
		return left.item_id < right.item_id ? -1 : left.item_id > right.item_id ? 1 : 0;
	});
}

/** One row of the day's stream: the story, and the marker above it if it opens
 * a group. */
export interface RailRow {
	item: DigestItem;
	/** Null on every story but the first of its group. */
	mark: RailTime | null;
}

/** The stream with its rail markers, one per time group rather than one per
 * story.
 *
 * A day of 359 stories over four groups is 355 duplicate labels, and a label
 * repeated ninety times is texture rather than information. So the marker is
 * drawn on the first story of each run of stories sharing a group, and the
 * stories under it carry none. Measured 2026-09-02 over the 12 committed days
 * and 4,713 stories at the 60-minute default: 907 markers rather than 4,713.
 *
 * The marker is the first story's own time to the minute, not a rounded one.
 * The stream runs newest first, so a marker is an upper bound on everything
 * below it until the next one - which is how a reader already reads a rail.
 *
 * `items` must already be in the order the page draws them (`orderByTime`), or
 * a group that the order split reopens further down. That is the honest
 * behaviour rather than a bug: a rail over an order it did not sort would print
 * numbers that jump up and down as the reader scrolls.
 */
export function railRows(items: DigestItem[], onDate: string, groupMinutes: number): RailRow[] {
	let previous: string | null = null;
	return items.map((item) => {
		const time = railTime(item.published_at, item.time_source, onDate, groupMinutes);
		const opens = time.group !== previous;
		previous = time.group;
		return { item, mark: opens ? time : null };
	});
}
