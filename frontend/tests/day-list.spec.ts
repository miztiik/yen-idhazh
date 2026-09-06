/** Row #5's oracle: the same day list, however it is computed.
 *
 * `DigestList` used to lowercase every title, every summary and every key point
 * on each keystroke, and then walk the whole day three more times to find where
 * one story had landed. This row prepares the text once per day and walks the
 * day once per filter. **Nothing a reader sees may move.**
 *
 * So the arithmetic being replaced is restated here in its plainest form -
 * filter, `findIndex`, filter - and held up as the reference. Over a generated
 * day, every needle that day's own text can produce, both hide-read states, and
 * every kind of address a reader can follow, the two have to agree on the same
 * six answers: what matched, what is visible, what is drawn, how far the pager
 * reached, how many stories are left, and whether the address names a story the
 * day never held.
 *
 * The second half counts visits, because parity on its own cannot see a cost. A
 * field read is counted through a getter and a row read through a proxy, so
 * "the text is lowercased once per day" and "the pager reads the prefix it
 * draws" are numbers here rather than claims about the shape of the code.
 *
 * Nothing here reads a committed day. A test that walks the archive costs more
 * every published day (Rule #12), and every shape this row is about - a lead
 * sitting past the first page, an address deep in the stream, a story hidden by
 * a read mark - is reachable from a day built in this file.
 */

import { expect, test } from '@playwright/test';

import { indexDay, leadingStories, orderByTime, revealed, shortlist } from '../src/lib/day-shape';
import type { DigestItem, DigestLead } from '../src/lib/payload/types';

/** What `DigestList` reveals before a reader asks for more. Mirrors `PAGE`
 * there; a page size is not what this oracle is about, so it is fixed. */
const PAGE = 12;

const NOBODY: ReadonlySet<string> = new Set<string>();

/** A fixed stream, so a failure here is the same failure on the next machine. */
function rolls(seed: number): () => number {
	let state = seed >>> 0;
	return () => {
		state = (state + 0x6d2b79f5) >>> 0;
		let t = state;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** A small alphabet, in mixed case on purpose. A needle is lowercase by the
 * time it arrives, so a day written in mixed case is the only kind that can
 * tell a filter that lowercases from one that does not. */
const WORDS = [
	'Chip', 'FAB', 'Wafer', 'node', 'YIELD', 'tool', 'Etch', 'laser', 'PHOTO', 'mask',
	'die', 'Pack', 'test', 'RAMP', 'fault', 'probe', 'ion', 'Dose', 'Line', 'stack'
];

interface BuiltDay {
	items: DigestItem[];
	leads: DigestLead[];
}

/** A day of `stories` stories and five leads, in the order the page draws it.
 *
 * Three things are deliberate. Times repeat and some are absent, so the tie
 * rule and the undated tail are inside the sweep rather than beside it. The
 * leads sit at fractions of the day rather than at its head, because a lead
 * past the first page is the case the pager exists for. And every field is
 * drawn from the same twenty words, so a two-letter needle keeps a realistic
 * share of the day instead of one story or none.
 */
function buildDay(stories: number, seed: number): BuiltDay {
	const roll = rolls(seed);
	const pick = () => WORDS[Math.floor(roll() * WORDS.length)];
	const phrase = (length: number) => Array.from({ length }, pick).join(' ');
	const items: DigestItem[] = [];
	for (let n = 0; n < stories; n += 1) {
		const minute = Math.floor(roll() * 40) * 15;
		items.push({
			item_id: `story-${String(n).padStart(4, '0')}`,
			vertical: 'ai',
			title: phrase(3),
			source_url: `https://example.invalid/${n}`,
			source_id: 'example',
			source_name: 'Example',
			source_kind: 'reporting',
			published_at:
				roll() < 0.08
					? null
					: `2026-08-31T${String(Math.floor(minute / 60) % 24).padStart(2, '0')}:${String(
							minute % 60
						).padStart(2, '0')}:00Z`,
			summary: phrase(8),
			key_points: Array.from({ length: 2 + Math.floor(roll() * 3) }, () => phrase(4)),
			lenses: [],
			events: [],
			entities: [],
			band: 'high',
			band_reason: null,
			source_form: 'article',
			reader_note: null,
			truncated: false,
			visual: null,
			introduced_by_run: 1,
			updated_at: null
		});
	}
	const ordered = orderByTime(items);
	const leads: DigestLead[] = [0.02, 0.2, 0.45, 0.72, 0.95].map((at) => ({
		item_id: ordered[Math.floor(at * (ordered.length - 1))].item_id,
		reason: 'a reason'
	}));
	return { items: ordered, leads };
}

/** The six answers the page draws from. */
interface Answer {
	matched: number;
	visible: string[];
	paged: string[];
	reach: number;
	remaining: number;
	missing: boolean;
}

function ids(items: readonly DigestItem[]): string[] {
	return items.map((item) => item.item_id);
}

/** The arithmetic this row replaces, restated. Deliberately the plainest form -
 * a filter, a second filter, a `findIndex` and a third filter - because a
 * reference that shares an idea with the thing it checks cannot catch it. */
function reference(
	day: BuiltDay,
	needle: string | null,
	hideRead: boolean,
	read: ReadonlySet<string>,
	wanted: string,
	shownCount: number
): Answer {
	const matched =
		needle === null
			? day.items
			: day.items.filter(
					(item) =>
						item.title.toLowerCase().includes(needle) ||
						item.summary.toLowerCase().includes(needle) ||
						item.key_points.some((point) => point.toLowerCase().includes(needle))
				);
	const visible = hideRead ? matched.filter((item) => !read.has(item.item_id)) : matched;
	const drawn = needle !== null ? [] : leadingStories(day.leads, visible);
	const leading = new Set(drawn.map((story) => story.item_id));
	const reach =
		wanted === '' || leading.has(wanted)
			? 0
			: visible.findIndex((item) => item.item_id === wanted) + 1;
	const shown = Math.max(shownCount || PAGE, reach);
	const paged = visible.filter((item, index) => index < shown || leading.has(item.item_id));
	return {
		matched: matched.length,
		visible: ids(visible),
		paged: ids(paged),
		reach,
		remaining: Math.max(visible.length - paged.length, 0),
		missing: wanted !== '' && !day.items.some((item) => item.item_id === wanted)
	};
}

/** The arithmetic this row ships, in the same order `DigestList` runs it.
 *
 * The day index is handed in rather than built here, because building it once
 * per day and reading it once per keystroke IS the change. Every other line is
 * a copy of the component's derived block; the browser specs hold the component
 * itself, and this holds the rule the component runs.
 */
function shipped(
	day: BuiltDay,
	index: ReturnType<typeof indexDay>,
	pinned: ReadonlySet<string>,
	needle: string | null,
	hideRead: boolean,
	read: ReadonlySet<string>,
	wanted: string,
	shownCount: number
): Answer {
	const list = shortlist(index, needle, hideRead ? read : null, pinned, wanted);
	const drawn = needle !== null ? [] : leadingStories(day.leads, list.visible);
	const leading = new Set(drawn.map((story) => story.item_id));
	const reach =
		wanted === '' || leading.has(wanted) || list.wantedRow < 0 ? 0 : list.wantedRow + 1;
	const shown = Math.max(shownCount || PAGE, reach);
	const paged = revealed(list.visible, list.pinnedRows, leading, shown);
	return {
		matched: list.matched,
		visible: ids(list.visible),
		paged: ids(paged),
		reach,
		remaining: Math.max(list.visible.length - paged.length, 0),
		missing: wanted !== '' && !index.at.has(wanted)
	};
}

/** Every needle this day's own text can produce, at one, two and three letters,
 * plus whole words and a handful that match nothing.
 *
 * Drawn from the day rather than invented, so the sweep cannot quietly become a
 * list of strings that all miss. The three-letter run is thinned because it is
 * the largest by far and adds the least - two letters already crosses a word
 * boundary, which is the case a naive concatenation of fields gets wrong.
 */
function needlesOf(day: BuiltDay): string[] {
	const text = day.items
		.flatMap((item) => [item.title, item.summary, ...item.key_points])
		.join(' ')
		.toLowerCase();
	const one = new Set<string>();
	const two = new Set<string>();
	const three = new Set<string>();
	for (let at = 0; at < text.length; at += 1) {
		one.add(text.slice(at, at + 1));
		if (at + 2 <= text.length) two.add(text.slice(at, at + 2));
		if (at + 3 <= text.length) three.add(text.slice(at, at + 3));
	}
	return [
		...one,
		...two,
		...[...three].filter((_, at) => at % 5 === 0),
		...WORDS.map((word) => word.toLowerCase()),
		'zzz',
		'qq',
		'chipwafer',
		'not in this day'
	];
}

const DAY = buildDay(120, 20260906);
const INDEX = indexDay(DAY.items);
const PINNED: ReadonlySet<string> = new Set(DAY.leads.map((lead) => lead.item_id));
const NEEDLES = needlesOf(DAY);

/** A read mark on every third story, which is enough that hiding them changes
 * where every later story sits. */
const READ: ReadonlySet<string> = new Set(
	DAY.items.filter((_, at) => at % 3 === 0).map((item) => item.item_id)
);

/** The six addresses a reader can arrive on: none, a lead, a story on the first
 * page, one in the middle, the last one, one the day never held. */
const ADDRESSES = [
	'',
	DAY.leads[3].item_id,
	DAY.items[3].item_id,
	DAY.items[60].item_id,
	DAY.items[DAY.items.length - 1].item_id,
	'story-9999'
];

test.describe('the day list', () => {
	test('draws the same stories in the same order as the arithmetic it replaces', () => {
		const drift: string[] = [];
		let cases = 0;
		for (const needle of [null, ...NEEDLES]) {
			for (const hideRead of [false, true]) {
				for (const wanted of ADDRESSES) {
					for (const shownCount of [0, 40]) {
						cases += 1;
						const want = JSON.stringify(
							reference(DAY, needle, hideRead, READ, wanted, shownCount)
						);
						const got = JSON.stringify(
							shipped(DAY, INDEX, PINNED, needle, hideRead, READ, wanted, shownCount)
						);
						if (got !== want) {
							drift.push(
								`needle=${JSON.stringify(needle)} hideRead=${hideRead} ` +
									`wanted=${wanted || '(none)'} shown=${shownCount}\n  want ${want}\n  got  ${got}`
							);
						}
					}
				}
			}
		}
		expect(cases, 'the sweep generated no cases, so it can only pass').toBeGreaterThan(2000);
		expect(drift.slice(0, 3).join('\n'), `${drift.length} of ${cases} cases disagree`).toBe('');
	});

	test('a needle never straddles two fields', () => {
		// The one thing a day index gets wrong if it joins a story's fields into
		// one string: the last word of the title and the first of the summary
		// become a match for text no story holds.
		const day = buildDay(4, 7);
		day.items[0] = { ...day.items[0], title: 'alpha', summary: 'beta', key_points: ['gamma'] };
		const index = indexDay(day.items);
		for (const needle of ['alphabeta', 'alpha beta', 'betagamma', 'beta gamma']) {
			const list = shortlist(index, needle, null, NOBODY, '');
			expect(ids(list.visible), `"${needle}" matched across a field boundary`).not.toContain(
				day.items[0].item_id
			);
		}
		for (const needle of ['alpha', 'beta', 'gamma']) {
			expect(ids(shortlist(index, needle, null, NOBODY, '').visible)).toContain(
				day.items[0].item_id
			);
		}
	});

	test('an address resolves to the story it names, wherever that story sits', () => {
		for (let at = 0; at < DAY.items.length; at += 1) {
			const wanted = DAY.items[at].item_id;
			const list = shortlist(INDEX, null, null, PINNED, wanted);
			expect(list.wantedRow, `${wanted} sits at row ${at}`).toBe(at);
			expect(list.visible[list.wantedRow].item_id).toBe(wanted);
			const paged = revealed(list.visible, list.pinnedRows, NOBODY, Math.max(PAGE, at + 1));
			expect(ids(paged), `the pager did not reach ${wanted}`).toContain(wanted);
		}
		expect(shortlist(INDEX, null, null, PINNED, 'story-9999').wantedRow).toBe(-1);
	});
});

/** Counting a read of a story's searchable text. `orderByTime` and `shortlist`
 * read `item_id` and `published_at`, which are not counted - only the three
 * fields a filter has to lowercase. */
function watchFields(items: DigestItem[]): { items: DigestItem[]; reads: () => number } {
	let reads = 0;
	const watched = items.map((item) => {
		const { title, summary, key_points, ...rest } = item;
		return {
			...rest,
			get title() {
				reads += 1;
				return title;
			},
			get summary() {
				reads += 1;
				return summary;
			},
			get key_points() {
				reads += 1;
				return key_points;
			}
		} as DigestItem;
	});
	return { items: watched, reads: () => reads };
}

/** Counting a read of a row of the visible list. */
function watchRows(items: DigestItem[]): { rows: DigestItem[]; reads: () => number } {
	let reads = 0;
	const rows = new Proxy(items, {
		get(target, key, receiver) {
			if (typeof key === 'string' && /^\d+$/.test(key)) reads += 1;
			return Reflect.get(target, key, receiver);
		}
	});
	return { rows, reads: () => reads };
}

test.describe('what the day list costs', () => {
	test('the day is lowercased once, however many letters a reader types', () => {
		const typed = NEEDLES.slice(0, 40);
		const stories = DAY.items.length;

		const once = watchFields(DAY.items);
		const index = indexDay(once.items);
		for (const needle of typed) shortlist(index, needle, null, PINNED, '');
		expect(once.reads(), 'the index read a field more than once per story').toBe(stories * 3);

		// The same day, typed at twice as long. The number may not move.
		const again = watchFields(DAY.items);
		const second = indexDay(again.items);
		for (const needle of [...typed, ...typed]) shortlist(second, needle, null, PINNED, '');
		expect(again.reads(), 'a second pass over the same letters read the day again').toBe(
			stories * 3
		);

		// What it replaces: at least one title read per story per keystroke.
		const before = watchFields(DAY.items);
		for (const needle of typed) {
			before.items.filter(
				(item) =>
					item.title.toLowerCase().includes(needle) ||
					item.summary.toLowerCase().includes(needle) ||
					item.key_points.some((point) => point.toLowerCase().includes(needle))
			);
		}
		expect(before.reads()).toBeGreaterThanOrEqual(typed.length * stories);
	});

	test('the pager reads the prefix it draws, not the day behind it', () => {
		const small = buildDay(120, 11);
		const large = buildDay(480, 11);
		const counts: number[] = [];
		let scanned = 0;
		for (const day of [small, large]) {
			const pinned = new Set(day.leads.map((lead) => lead.item_id));
			const list = shortlist(indexDay(day.items), null, null, pinned, '');
			const leading = new Set(
				leadingStories(day.leads, list.visible).map((story) => story.item_id)
			);
			const watched = watchRows(list.visible);
			const drawn = revealed(watched.rows, list.pinnedRows, leading, PAGE);
			expect(ids(drawn).length, 'the prefix and its outlying leads').toBe(
				PAGE + list.pinnedRows.filter((row) => row >= PAGE).length
			);
			counts.push(watched.reads());

			// What it replaces, on the same list: one read per story in the day.
			const all = watchRows(list.visible);
			all.rows.filter((item, index) => index < PAGE || leading.has(item.item_id));
			expect(all.reads()).toBe(list.visible.length);
			scanned = all.reads();
		}
		expect(counts[0], 'the pager read past the prefix it draws').toBeLessThanOrEqual(PAGE + 5);
		expect(counts[1], 'a four-times longer day cost the pager more').toBe(counts[0]);
		expect(scanned, 'the day being paged did not actually grow').toBe(480);
	});
});
