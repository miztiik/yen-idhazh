import { expect, test } from '@playwright/test';
import { ITEM_FIELDS, VIEW_VERSION, projectDay } from '../src/lib/payload/project';

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
		expect(Object.keys(one.served).sort(), `${one.name} is not the served day`).toEqual([
			'items',
			'version'
		]);
		expect(one.served.version, `${one.name} carries the wrong stamp`).toBe(VIEW_VERSION);
		for (const item of one.served.items) {
			expect(Object.keys(item).sort(), `${one.name} ${String(item.item_id)}`).toEqual(
				[...ITEM_FIELDS].sort()
			);
		}
	}
});

test('a field the run never recorded reads as unknown, never as a value', () => {
	const [legacy, current] = DAYS as [Day, Day];

	// The arm that would make every assertion below vacuous: the older shape has
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
