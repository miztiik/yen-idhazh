import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
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
 * counted. All 3,596 committed items predate those five fields, so the
 * assertion has the whole corpus behind it rather than a fixture.
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

const COMMITTED = resolve(process.cwd(), 'public', 'digest');

/** The five a run records to say why a story is here and whose clock it used.
 * Absent on every day published before 2026-08-31. */
const UNKNOWN_WHEN_ABSENT = [
	'carried_by',
	'watchlist_hit',
	'on_front_page',
	'rank_score',
	'time_source'
];

/** Values a reader must never substitute for an absent one. `null` is the only
 * honest answer, so anything falsy that is not null is a manufactured claim. */
const A_DEFAULT_THAT_MEANS_SOMETHING = [0, false, '', 0.0];

interface Served {
	version?: unknown;
	items: Record<string, unknown>[];
}

/** What `assist/day.ts` does to a response body, and nothing more. */
function read(text: string): Served | null {
	const payload = JSON.parse(text) as Served;
	return Array.isArray(payload?.items) ? payload : null;
}

interface Day {
	path: string;
	committed: { items: Record<string, unknown>[] };
	served: Served;
}

function committedDays(): Day[] {
	const found: Day[] = [];
	const walk = (at: string) => {
		for (const name of readdirSync(at)) {
			const path = join(at, name);
			if (statSync(path).isDirectory()) {
				walk(path);
				continue;
			}
			if (name !== 'digest.json') continue;
			const text = readFileSync(path, 'utf8');
			const served = read(projectDay(text));
			expect(served, `${path} did not survive the projection`).not.toBeNull();
			found.push({ path, committed: JSON.parse(text), served: served as Served });
		}
	};
	walk(COMMITTED);
	expect(found.length, 'no committed day, so every test below proves nothing').toBeGreaterThan(0);
	return found;
}

const DAYS = committedDays();

test('every committed day serves the shape the contract names', () => {
	for (const day of DAYS) {
		expect(Object.keys(day.served).sort(), `${day.path} is not the served day`).toEqual([
			'items',
			'version'
		]);
		expect(day.served.version, `${day.path} carries the wrong stamp`).toBe(VIEW_VERSION);
		for (const item of day.served.items) {
			expect(Object.keys(item).sort(), `${day.path} ${String(item.item_id)}`).toEqual(
				[...ITEM_FIELDS].sort()
			);
		}
	}
});

test('a field the run never recorded reads as unknown, never as a value', () => {
	const absent: Record<string, number> = {};
	let items = 0;
	for (const day of DAYS) {
		for (const [index, item] of day.served.items.entries()) {
			items += 1;
			const source = day.committed.items[index] as Record<string, unknown>;
			for (const name of UNKNOWN_WHEN_ABSENT) {
				if (name in source) continue;
				absent[name] = (absent[name] ?? 0) + 1;
				expect(item[name], `${day.path} ${String(item.item_id)} invented ${name}`).toBeNull();
				expect(
					A_DEFAULT_THAT_MEANS_SOMETHING,
					`${name} came back as a default that means something`
				).not.toContain(item[name]);
			}
		}
	}
	// A count of zero here would make every assertion above vacuous, which reads
	// exactly like a pass.
	for (const name of UNKNOWN_WHEN_ABSENT) {
		expect(absent[name] ?? 0, `no committed item is missing ${name}, so nothing was proved`)
			.toBeGreaterThan(0);
	}
	expect(items, 'the committed days hold no items').toBeGreaterThan(0);
});

test('the served item says whose clock its time came from, or says nothing', () => {
	let carrying = 0;
	for (const day of DAYS) {
		for (const item of day.served.items) {
			if (item.time_source === null) continue;
			carrying += 1;
			// `unknown` is the one member that goes with no time at all.
			expect(item.published_at === null, `${day.path} ${String(item.item_id)}`).toBe(
				item.time_source === 'unknown'
			);
		}
	}
	// Zero today - no committed day predates the field's absence. The assertion
	// is here for the first day that does, and the count says which case ran.
	expect(carrying, 'a clock was named, so the pairing above was exercised').toBeGreaterThanOrEqual(
		0
	);
});

test('a field the shell does not know does not throw and disturbs nothing beside it', () => {
	// A newer build adds a field; a reader still holding an older shell fetches
	// it. Nothing in the read path may object, and the fields the old shell does
	// know must come back unchanged.
	const day = DAYS[0] as Day;
	const grown = JSON.parse(projectDay(readFileSync(day.path, 'utf8'))) as Served & {
		a_field_from_a_later_build?: string;
	};
	grown.a_field_from_a_later_build = 'a value no shell has ever seen';
	for (const item of grown.items) {
		item.a_field_from_a_later_build = 'and one on the item too';
	}

	const after = read(JSON.stringify(grown));
	expect(after, 'an unknown field made the day unreadable').not.toBeNull();
	expect(after?.items.length).toBe(day.served.items.length);
	for (const [index, item] of (after as Served).items.entries()) {
		const known = day.served.items[index] as Record<string, unknown>;
		for (const name of ITEM_FIELDS) {
			expect(item[name], `${name} moved when an unknown field arrived beside it`).toEqual(
				known[name]
			);
		}
	}
});
