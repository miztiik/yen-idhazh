import { expect, test } from '@playwright/test';
import {
	COVERAGE_NAMES_MAX,
	DAY_FIELDS,
	ITEM_FIELDS,
	VIEW_VERSION,
	projectDay
} from '../src/lib/payload/project';

/**
 * The served day, read the way a browser reads it.
 *
 * `frontend/public/digest/` is the committed day. `projectDay` narrows it into
 * the file the site serves at `<base>/digest/<Y>/<M>/<D>/digest.json`, and from
 * 2026-08-31 that file is a contract - `schemas/digest-view.schema.json`, from
 * `backend/idhazh/contracts/digest_view.py`. This is the reader's half of it.
 *
 * **The one claim under test: an absent field reads as unknown, and never as a
 * value.** Every plausible default is a false claim - `0` for `carried_by` says
 * no feed carried the story, `false` for `on_front_page` denies a vote nobody
 * counted.
 *
 * **It is driven from two fixture days rather than from the committed tree**
 * (`CLAUDE.md` section 13). Walking the archive cost 93 s and grew with every
 * publish, and what it bought was one shape repeated: the older days are all
 * the same older shape. Worse, it was self-expiring - its own non-vacuity guard
 * demanded a committed item still missing the five, and that set only shrinks
 * as days age out, so the test was going to fail one day for a reason that has
 * nothing to do with the code. The two shapes below are both of them, and
 * `COMMITTED_FIELDS` holds the fixture to what a day really carries on disk.
 *
 * **`read` below is two lines, and they are `assist/day.ts`'s two lines.** That
 * module cannot be imported here: it takes `base` from `$app/paths` as a value,
 * and a Playwright spec runs in plain node, which fails the whole file at load
 * with `Cannot find package '$app'`. What it does to a response body is
 * `response.json()` and one array guard, restated here with nothing else added
 * - in particular no defaulting, which is the thing being proved. The browser
 * half of the same promise is the section-12 smoke: the site is rebuilt over
 * days carrying an unknown field and every reading route renders.
 */

const COMMITTED_FIELDS: readonly string[] = [
	'item_id',
	'vertical',
	'title',
	'summary',
	'key_points',
	'reader_note',
	'band',
	'band_reason',
	'truncated',
	'visual',
	'source_name',
	'source_id',
	'source_kind',
	'source_url',
	'published_at',
	'also_covered_by',
	'introduced_by_run',
	'lenses'
];

/** The five a run records to say why a story is here and whose clock it used.
 * Absent on every day published before 2026-08-31. */
const UNKNOWN_WHEN_ABSENT = [
	'carried_by',
	'watchlist_hit',
	'on_front_page',
	'rank_score',
	'time_source'
];

interface Served {
	version?: unknown;
	items: Record<string, unknown>[];
}

/** What `assist/day.ts` does to a response body, and nothing more. */
function read(text: string): Served | null {
	const payload = JSON.parse(text) as Served;
	return Array.isArray(payload?.items) ? payload : null;
}

/** One committed story, carrying everything the projector reads off one. */
function committedItem(id: string, extra: Record<string, unknown>): Record<string, unknown> {
	const base: Record<string, unknown> = {
		item_id: id,
		vertical: 'ai',
		title: `Story ${id}`,
		summary: `A summary of ${id}.`,
		key_points: ['One point.'],
		reader_note: null,
		band: 'high',
		band_reason: null,
		truncated: false,
		visual: null,
		source_name: 'Test',
		source_id: 'test',
		source_kind: 'reporting',
		source_url: `https://example.test/${id}`,
		published_at: '2026-08-23T14:05:00Z',
		also_covered_by: [],
		introduced_by_run: 1,
		lenses: []
	};
	return { ...base, ...extra };
}

/** A day published before the five fields existed, which is what every day
 * committed before 2026-08-31 looks like on disk. */
const LEGACY = JSON.stringify({
	version: '2026-08-23T18:48',
	date: '2026-08-23',
	items: [committedItem('ai-0001', {}), committedItem('ai-0002', {})]
});

/** A day published since, carrying all five - including the one pairing that
 * says a story has no time at all. */
const CURRENT = JSON.stringify({
	version: '2026-09-01T09:00',
	date: '2026-09-04',
	items: [
		committedItem('ai-0001', {
			carried_by: 3,
			watchlist_hit: true,
			on_front_page: false,
			rank_score: 0.72,
			time_source: 'feed'
		}),
		committedItem('ai-0002', {
			carried_by: 0,
			watchlist_hit: false,
			on_front_page: true,
			rank_score: 0.0,
			time_source: 'unknown',
			published_at: null
		})
	]
});

interface Day {
	name: string;
	committed: { items: Record<string, unknown>[] };
	served: Served;
}

function day(name: string, text: string): Day {
	const served = read(projectDay(text));
	expect(served, `${name} did not survive the projection`).not.toBeNull();
	return { name, committed: JSON.parse(text), served: served as Served };
}

const DAYS = [day('a day older than the five fields', LEGACY), day('a day since', CURRENT)];

test('every day serves the shape the contract names', () => {
	// The committed shapes are not guesses: `COMMITTED_FIELDS` is what a day
	// carries on disk, and a backend contract test holds the served list against
	// `schemas/digest-view.schema.json`.
	const [legacy, current] = DAYS as [Day, Day];
	for (const item of legacy.committed.items) {
		expect(Object.keys(item).sort(), 'the older fixture is not the older shape').toEqual(
			[...COMMITTED_FIELDS].sort()
		);
	}
	for (const item of current.committed.items) {
		expect(Object.keys(item).sort(), 'the newer fixture is not the newer shape').toEqual(
			[...COMMITTED_FIELDS, ...UNKNOWN_WHEN_ABSENT].sort()
		);
	}

	for (const one of DAYS) {
		expect(Object.keys(one.served).sort(), `${one.name} is not the served day`).toEqual(
			[...DAY_FIELDS, 'version'].sort()
		);
		expect(one.served.version, `${one.name} carries the wrong stamp`).toBe(VIEW_VERSION);
		for (const item of one.served.items) {
			expect(Object.keys(item).sort(), `${one.name} ${String(item.item_id)}`).toEqual(
				[...ITEM_FIELDS].sort()
			);
		}
	}
});

/** The day's own facts reach the wire, and an absent one is null rather than a
 * value.
 *
 * They joined the served day on 2026-09-09, because deleting the dated document
 * left the browser with no other source for the date, the desks, the leading
 * block, the run list or the day notice. A fixture that carries none of them is
 * what says the projector writes an explicit null rather than leaving the key
 * out - which is what makes every served day the same shape whichever day it was
 * published on.
 */
test('the day facts are projected, and an absent one is null', () => {
	const facts = DAY_FIELDS.filter((name) => name !== 'items');
	expect(facts.length, 'the served day carries no day-level fact at all').toBeGreaterThan(0);

	for (const one of DAYS) {
		const committed = one.committed as unknown as Record<string, unknown>;
		const served = one.served as unknown as Record<string, unknown>;
		for (const name of facts) {
			expect(name in served, `${one.name} left ${name} out instead of nulling it`).toBe(true);
			expect(served[name], `${one.name} invented ${name}`).toEqual(committed[name] ?? null);
		}
	}
});

test('a field the run never recorded reads as unknown, never as a value', () => {
	const [legacy, current] = DAYS as [Day, Day];

	// The case that would make every assertion below vacuous: the older shape has
	// to be missing the five in the first place.
	for (const [index, item] of legacy.served.items.entries()) {
		const source = legacy.committed.items[index] as Record<string, unknown>;
		for (const name of UNKNOWN_WHEN_ABSENT) {
			expect(name in source, `the older shape carries ${name}, so it is not the older shape`).toBe(
				false
			);
			// `null` is the only honest answer. `0` for `carried_by` says no feed
			// carried the story and `false` for `on_front_page` denies a vote nobody
			// counted, so anything but null here is a manufactured claim.
			expect(item[name], `${String(item.item_id)} invented ${name}`).toBeNull();
		}
	}

	// And the other direction, which is what stops the projector passing this by
	// nulling everything it touches.
	for (const [index, item] of current.served.items.entries()) {
		const source = current.committed.items[index] as Record<string, unknown>;
		for (const name of UNKNOWN_WHEN_ABSENT) {
			expect(item[name], `${String(item.item_id)} lost the ${name} the day recorded`).toEqual(
				source[name]
			);
		}
	}
	// A falsy value the day really recorded survives as itself rather than as an
	// absence - the pair the read-side rule exists to tell apart.
	expect(current.served.items[1]?.carried_by).toBe(0);
	expect(current.served.items[1]?.on_front_page).toBe(true);
});

test('the served item says whose clock its time came from, or says nothing', () => {
	const current = DAYS[1] as Day;
	const clocks = current.served.items.map((item) => String(item.time_source));
	// Both sides of the pairing are driven, which the count guard here used to
	// only hope for: `unknown` is the one member that goes with no time at all.
	expect(clocks.sort(), 'the fixture no longer drives both sides of the pairing').toEqual([
		'feed',
		'unknown'
	]);

	for (const item of current.served.items) {
		expect(item.published_at === null, String(item.item_id)).toBe(item.time_source === 'unknown');
	}
});

test('a field the shell does not know does not throw and disturbs nothing beside it', () => {
	// A newer build adds a field; a reader still holding an older shell fetches
	// it. Nothing in the read path may object, and the fields the old shell does
	// know must come back unchanged.
	const one = DAYS[1] as Day;
	const grown = JSON.parse(projectDay(CURRENT)) as Served & {
		a_field_from_a_later_build?: string;
	};
	grown.a_field_from_a_later_build = 'a value no shell has ever seen';
	for (const item of grown.items) {
		item.a_field_from_a_later_build = 'and one on the item too';
	}

	const after = read(JSON.stringify(grown));
	expect(after, 'an unknown field made the day unreadable').not.toBeNull();
	expect(after?.items.length).toBe(one.served.items.length);
	for (const [index, item] of (after as Served).items.entries()) {
		const known = one.served.items[index] as Record<string, unknown>;
		for (const name of ITEM_FIELDS) {
			expect(item[name], `${name} moved when an unknown field arrived beside it`).toEqual(
				known[name]
			);
		}
	}
});

/**
 * The publisher names, which are the one name on a served item the committed day
 * does not carry.
 *
 * `coverageOf` derives them from the grouping the day already recorded, and the
 * page folds a group into one card and prints them. The same cases are asserted
 * in `backend/tests/contracts/test_served_day.py` against the other projector, so
 * a rule that moved in one language and not the other turns one of the two red.
 *
 * Nothing here reads a committed day. Every case is a shape the archive has never
 * produced - four outlets on one story, one outlet running it twice, a story
 * naming an anchor the day does not hold - and building it is the only way to
 * reach it (`CLAUDE.md` section 13).
 */

/** A day of stories, some of them one story. Each member is
 * `[item_id, source_name, rank_score]`; the first is the anchor unless `anchor`
 * names another, and every other member points at it. */
function grouped(
	members: [string, string, number | null][],
	anchor?: string
): Record<string, unknown>[] {
	const keeper = anchor ?? members[0][0];
	return members.map(([item_id, source_name, rank_score]) =>
		committedItem(item_id, {
			vertical: item_id.split('-')[0],
			source_name,
			source_id: source_name.toLowerCase(),
			rank_score,
			same_story_as: item_id === keeper ? null : keeper
		})
	);
}

/** Every story's publisher stack, as `outlet@item id` pairs, off the projection. */
function stacks(items: Record<string, unknown>[]): Record<string, string[]> {
	const served = read(projectDay(JSON.stringify({ date: '2026-09-16', items })));
	expect(served, 'the built day did not survive the projection').not.toBeNull();
	return Object.fromEntries(
		(served as Served).items.map((item) => [
			String(item.item_id),
			(item.covered_by as { source_name: string; item_id: string }[]).map(
				(one) => `${one.source_name}@${one.item_id}`
			)
		])
	);
}

test('a folded story is named by the card that folds it', () => {
	const found = stacks(
		grouped([
			['ai-01', 'Alpha', 0.9],
			['ai-02', 'Beta', 0.7],
			['ai-03', 'Gamma', 0.8]
		])
	);

	expect(found['ai-01']).toEqual(['Gamma@ai-03', 'Beta@ai-02']);
	// And from every member's point of view, because a card is drawn for a
	// member whenever the fold is off or the reader's own address named it.
	expect(found['ai-02']).toEqual(['Alpha@ai-01', 'Gamma@ai-03']);
	expect(found['ai-03']).toEqual(['Alpha@ai-01', 'Beta@ai-02']);
});

test('a story no group holds, and a story naming an anchor this day lost, are named by nobody', () => {
	expect(
		stacks([
			...grouped([
				['ai-01', 'Alpha', 0.9],
				['ai-02', 'Beta', 0.7]
			]),
			...grouped([['world-01', 'Alpha', 0.5]])
		])['world-01'],
		'a story on its own was given a publisher stack'
	).toEqual([]);

	// A run appends, so a day can carry a story whose anchor was published
	// under a retention window that has since dropped it. The page cannot draw
	// a card that is not here, so neither may the stack.
	expect(
		stacks(
			grouped(
				[
					['ai-02', 'Beta', 0.7],
					['ai-03', 'Gamma', 0.8]
				],
				'ai-99'
			)
		),
		'a name pointed at a card the day does not hold'
	).toEqual({ 'ai-02': [], 'ai-03': [] });
});

test('one outlet running a story twice is named once, by its stronger piece', () => {
	// `also_covered_by` counts mastheads. A stack naming pieces would print
	// three newsrooms under a sentence saying two.
	expect(
		stacks(
			grouped([
				['ai-01', 'Alpha', 0.9],
				['ai-02', 'Beta', 0.4],
				['ai-03', 'Beta', 0.8]
			])
		)['ai-01']
	).toEqual(['Beta@ai-03']);
});

test('the stack stops at the cap, and an unscored or tied story is ordered last', () => {
	const capped = stacks(
		grouped([
			['ai-01', 'Alpha', 0.9],
			['ai-02', 'Beta', 0.8],
			['ai-03', 'Gamma', 0.7],
			['ai-04', 'Delta', 0.6],
			['ai-05', 'Epsilon', 0.5]
		])
	);
	expect(capped['ai-01'].length).toBe(COVERAGE_NAMES_MAX);
	expect(capped['ai-01']).toEqual(['Beta@ai-02', 'Gamma@ai-03', 'Delta@ai-04']);

	// Null is unknown, never 0, and never the top of the stack either.
	expect(
		stacks(
			grouped([
				['ai-01', 'Alpha', 0.9],
				['ai-02', 'Beta', null],
				['ai-03', 'Gamma', 0.1]
			])
		)['ai-01']
	).toEqual(['Gamma@ai-03', 'Beta@ai-02']);

	// A total order, so two builds of one day agree and so do two languages.
	expect(
		stacks(
			grouped([
				['ai-01', 'Alpha', 0.5],
				['ai-03', 'Gamma', 0.5],
				['ai-02', 'Beta', 0.5]
			])
		)['ai-01']
	).toEqual(['Beta@ai-02', 'Gamma@ai-03']);
});
