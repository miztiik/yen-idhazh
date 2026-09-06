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

/** A day's stories with the two things the page asks about them over and over.
 *
 * **Built once per day, read once per keystroke.** A needle arrives lowercase
 * and a story's text does not, so a filter has to lower one side of every
 * comparison - and the day's side is the same answer on every letter. On the
 * 601-story day of 2026-08-31 that was a little over 3,600 strings rebuilt per
 * keystroke for an answer that had not changed since the day loaded.
 *
 * Measured 2026-09-06 on a 12th Gen Intel Core i7-1265U, Windows 11, node
 * 24.12.0, over a built 601-story day and 40 keystrokes, 10 timed repetitions
 * after 2 discarded: a keystroke's selection work went from a median 0.254 ms
 * to 0.112 ms - 56 percent less, and 0.14 ms of it back per letter. Whole-run
 * medians were 10.2 ms (6.4 to 12.9) and 4.5 ms (4.3 to 6.3). Building the
 * index costs a median 0.4 ms (0.3 to 0.5) and is paid once. These are small
 * numbers on a fast machine; what matters is that the part that grew with the
 * day is now paid when the day changes rather than when a reader types.
 *
 * **It takes the list rather than holding one.** A reading route seeds its
 * document with the head of the day and fetches the rest, so an index captured
 * once at mount would narrow the seed for ever and hide everything that landed
 * afterwards, with nothing on screen saying so. `DigestList` derives it from
 * the list the page is holding, so it is rebuilt when that list changes.
 */
export interface DayIndex {
	/** The stories, in the order the page draws them. */
	items: DigestItem[];
	/** Each story's searchable text, lowercased: its title, then its summary,
	 * then its key points, in that order.
	 *
	 * **Kept as separate strings and never joined.** A join turns the end of one
	 * field and the start of the next into a substring, so a needle would match
	 * text no story holds - `frontend/tests/day-list.spec.ts` asserts it cannot.
	 */
	fields: string[][];
	/** Where each story sits in `items`, by id. */
	at: Map<string, number>;
}

/** The day, prepared for the two questions a filter and a link keep asking. */
export function indexDay(items: DigestItem[]): DayIndex {
	const fields: string[][] = [];
	const at = new Map<string, number>();
	for (let row = 0; row < items.length; row += 1) {
		const item = items[row];
		const lowered = [item.title.toLowerCase(), item.summary.toLowerCase()];
		for (const point of item.key_points) lowered.push(point.toLowerCase());
		fields.push(lowered);
		// First wins, which is what a scan down the day would have found. A
		// payload cannot hold one id twice, so this only decides what happens if
		// one ever does - and quietly pointing at the second copy is worse than
		// pointing at the one a reader scrolling would reach first.
		if (!at.has(item.item_id)) at.set(item.item_id, row);
	}
	return { items, fields, at };
}

/** What the page shows, and where the two stories it has to point at landed. */
export interface Shortlist {
	/** How many stories the needle kept, before read state hid any. This is the
	 * number beside the filter box, and it is counted rather than collected -
	 * the list it would have built is never drawn. */
	matched: number;
	/** The stories the page would show, in draw order. */
	visible: DigestItem[];
	/** Where each of the day's published leads landed in `visible`, ascending.
	 * A lead is chosen across the whole day, so it is routinely past the page a
	 * reader has revealed, and the pager has to draw it anyway. */
	pinnedRows: number[];
	/** Where the story a reader's own address named landed in `visible`, or -1
	 * where this page is not showing it. */
	wantedRow: number;
}

/** One pass down the day: what the needle keeps, what read state hides, and
 * where the leads and the addressed story ended up.
 *
 * The four answers used to cost four walks - a filter, a second filter, a
 * `findIndex` and a membership scan - over a list that had just been walked to
 * build it. They are four answers about the same row, so they are collected on
 * the way past it.
 *
 * `hidden` is null rather than an empty set when the reader is not hiding what
 * they have read, so the ordinary case does no lookups at all.
 */
export function shortlist(
	day: DayIndex,
	needle: string | null,
	hidden: ReadonlySet<string> | null,
	pinned: ReadonlySet<string>,
	wanted: string
): Shortlist {
	const visible: DigestItem[] = [];
	const pinnedRows: number[] = [];
	let matched = 0;
	let wantedRow = -1;
	for (let row = 0; row < day.items.length; row += 1) {
		if (needle !== null && !day.fields[row].some((field) => field.includes(needle))) continue;
		matched += 1;
		const item = day.items[row];
		if (hidden !== null && hidden.has(item.item_id)) continue;
		const seat = visible.length;
		visible.push(item);
		if (pinned.has(item.item_id)) pinnedRows.push(seat);
		if (wantedRow < 0 && item.item_id === wanted) wantedRow = seat;
	}
	return { matched, visible, pinnedRows, wantedRow };
}

/** The stories the page draws: the prefix it has revealed, plus any lead
 * sitting past it.
 *
 * The prefix is taken rather than filtered for. A filter reads every story in
 * the day to decide the first twelve, so a reader on a long day paid for the
 * whole stream to see one screen of it. `frontend/tests/day-list.spec.ts`
 * counts both: over a built 480-story day the filter reads 480 rows and this
 * reads 12 plus its outlying leads, and quadrupling the day does not move the
 * second number.
 *
 * `leading` is the block the page actually drew, which is a subset of the day's
 * published leads: a topic route and a filter both draw no block, and a lead
 * the reader has hidden drops out of it. `pinnedRows` says where every
 * published lead sits; `leading` says which of them the page is pointing at.
 */
export function revealed(
	visible: readonly DigestItem[],
	pinnedRows: readonly number[],
	leading: ReadonlySet<string>,
	shown: number
): DigestItem[] {
	const drawn = visible.slice(0, shown);
	if (leading.size === 0) return drawn;
	for (const row of pinnedRows) {
		if (row < shown) continue;
		const item = visible[row];
		if (leading.has(item.item_id)) drawn.push(item);
	}
	return drawn;
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
