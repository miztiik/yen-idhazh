import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { orderByTime } from '../src/lib/day-shape';
import { dayShell, homeShell, loadDay, publishedDates, wholeDay } from '../src/lib/server/payload';
import type { DigestDay, DigestItem, SeededVisual } from '../src/lib/payload/types';

/**
 * Row #23's oracle, as a function rather than as a build, and row #25's seed
 * rules beside it.
 *
 * The reading routes load a day in two halves - the facts that do not grow with
 * the number of stories, and the stories themselves split at
 * `ui.shell_seed_items`. Every one of them keeps a seed and fetches the rest,
 * including the home page since 2026-09-10. So the seam owes two things.
 *
 * Put back together it must change nothing: the day a route renders is the day
 * the loader read, key order and all. Key order is asserted rather than deep
 * equality alone because it is what the bytes are - a prerendered document
 * serialises an object in its own key order, and the committed payload writes
 * its keys sorted, so a day rebuilt with the stories appended is a different
 * document holding the same day. `wholeDay` has no caller in `frontend/src` now
 * that `/` has stopped inlining, and the round trip is asserted here because it
 * is what says the split loses nothing.
 *
 * And split, it must lose nothing. A topic's seed comes from the topic's own
 * list, and a story named in `keep` is in the seed whatever its position - the
 * head is a prefix and a leading story is not inside one.
 *
 * **The list the seam splits is the reading order, not the published one.** The
 * stream runs newest first by the time on the story, so a seed taken off the
 * desk-blocked payload would put one desk in the document and then shuffle it
 * the moment the rest of the day arrived. The expectations below therefore go
 * through `orderByTime` - the same function the shell and the page call - so
 * this file cannot disagree with either about what the head of the day is.
 */

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

/** Every split worth trying: nothing seeded, a partial seed, the exact length,
 * and a seed longer than the day. */
const SEEDS = [0, 1, 3, 8, 500];

/** The day as a route renders it: the loader's day, in the order the page draws. */
function reading(day: DigestDay): DigestDay {
	return { ...day, items: orderByTime(day.items) };
}

/** The day with the drawings taken back out.
 *
 * `dayShell` reads a seeded story's SVG off disk and hands it over with the
 * story, so from 2026-09-05 the halves put back together hold one thing the
 * loader's day does not. That is the point of the seed and not a leak: `markup`
 * is a build-time field, it never reaches a served day, and every other byte of
 * every story still has to survive the round trip. Removing it is what lets the
 * test below go on asking the question it was written to ask.
 */
function withoutDrawings(day: DigestDay): DigestDay {
	return {
		...day,
		items: day.items.map((item) => {
			if (!item.visual) return item;
			const { markup: _markup, ...visual } = item.visual as SeededVisual;
			return { ...item, visual };
		})
	};
}

test.describe('the reading routes load a day in two halves', () => {
	test('the halves put back together are the day the loader read', () => {
		const dates = publishedDates(CANARY);
		expect(dates.length, 'the canary tree published no day').toBeGreaterThan(0);
		let drawings = 0;
		for (const date of dates) {
			const whole = loadDay(date, CANARY);
			expect(whole, `${date} did not load`).not.toBeNull();
			for (const seed of SEEDS) {
				const shell = dayShell(date, seed, { root: CANARY });
				expect(shell, `${date} at a seed of ${seed} did not load`).not.toBeNull();
				drawings += shell!.seed.filter((item) => (item.visual as SeededVisual)?.markup).length;
				expect(
					JSON.stringify(withoutDrawings(wholeDay(shell!))),
					`${date} at a seed of ${seed} rebuilt a different day`
				).toBe(JSON.stringify(reading(whole!)));
				// And the set is the set, whatever the order: a sort that dropped a
				// story would otherwise only fail the line above, which reads as a key
				// order problem.
				expect(
					wholeDay(shell!)
						.items.map((item) => item.item_id)
						.sort(),
					`${date} at a seed of ${seed} lost or doubled a story`
				).toEqual(whole!.items.map((item) => item.item_id).sort());
			}
		}
		// Without this the strip above could be removing nothing, and the test
		// would read as green while checking a shape it no longer meets.
		expect(drawings, 'no seeded story carried a drawing, so the strip proved nothing').toBeGreaterThan(0);
	});

	test('the seed is the head of the reading order and the rest is the tail', () => {
		const date = publishedDates(CANARY).find((d) => (loadDay(d, CANARY)?.items.length ?? 0) > 1);
		expect(date, 'no canary day carries more than one story').toBeDefined();
		const items = orderByTime(loadDay(date!, CANARY)!.items);
		const shell = dayShell(date!, 3, { root: CANARY })!;
		expect(shell.seed.map((item) => item.item_id)).toEqual(
			items.slice(0, 3).map((item) => item.item_id)
		);
		expect(shell.rest.map((item) => item.item_id)).toEqual(
			items.slice(3).map((item) => item.item_id)
		);
	});

	test('the facts carry no stories, so they do not grow with the day', () => {
		const date = publishedDates(CANARY)[0];
		const shell = dayShell(date, 3, { root: CANARY })!;
		expect(shell.facts.items).toEqual([]);
		expect(shell.facts.date).toBe(date);
		expect(shell.facts.verticals.length).toBeGreaterThan(0);
	});

	test('a date that was never published has no shell', () => {
		expect(dayShell('1999-01-01', 3, { root: CANARY })).toBeNull();
	});
});

/** The newest canary day carrying more than one story, and a topic it holds.
 *
 * `items` is in the order the page draws, so every expectation built from it is
 * about the list the seam actually splits. */
function busiest(): { date: string; vertical: string; items: DigestItem[] } {
	for (const date of publishedDates(CANARY)) {
		const day = loadDay(date, CANARY);
		if (!day || day.items.length < 2) continue;
		const items = orderByTime(day.items);
		return { date, vertical: items[0].vertical, items };
	}
	throw new Error('no canary day carries more than one story');
}

test.describe('a topic route splits its own list', () => {
	test('the seed and the rest together are exactly the topic, in reading order', () => {
		const { date, vertical, items } = busiest();
		const own = items.filter((item) => item.vertical === vertical).map((item) => item.item_id);
		expect(own.length, `${date} published nothing under ${vertical}`).toBeGreaterThan(0);
		for (const seed of SEEDS) {
			const shell = dayShell(date, seed, { vertical, root: CANARY })!;
			expect(
				[...shell.seed, ...shell.rest].map((item) => item.item_id),
				`${date}/${vertical} at a seed of ${seed} did not hold its topic`
			).toEqual(own);
			expect(shell.seed.length, `${date}/${vertical} seeded more than ${seed}`).toBeLessThanOrEqual(
				seed
			);
		}
	});

	test('the facts are the whole day, so the pill row still counts every topic', () => {
		const { date, vertical, items } = busiest();
		const shell = dayShell(date, 1, { vertical, root: CANARY })!;
		expect(shell.facts.verticals.map((ref) => ref.id).sort()).toEqual(
			[...new Set(items.map((item) => item.vertical))].sort()
		);
	});

	test('a topic nobody published splits to nothing rather than to the day', () => {
		const { date } = busiest();
		const shell = dayShell(date, 5, { vertical: 'no-such-desk', root: CANARY })!;
		expect(shell.seed).toEqual([]);
		expect(shell.rest).toEqual([]);
	});
});

test.describe('the seed is the head union what the page must anchor', () => {
	test('a story past the head is in the seed when it is kept, exactly once', () => {
		const { date, vertical, items } = busiest();
		const own = items.filter((item) => item.vertical === vertical);
		expect(own.length, 'the canary topic is too small to have a tail').toBeGreaterThan(1);
		const last = own[own.length - 1].item_id;

		const plain = dayShell(date, 1, { vertical, root: CANARY })!;
		expect(plain.seed.map((item) => item.item_id), 'the head already held the tail').not.toContain(
			last
		);

		const kept = dayShell(date, 1, { vertical, keep: [last], root: CANARY })!;
		expect(kept.seed.map((item) => item.item_id)).toEqual([own[0].item_id, last]);
		expect(kept.rest.map((item) => item.item_id)).not.toContain(last);
		// The set is what reachability rests on: a story pulled forward must not
		// be dropped from the tail and must not be published twice.
		expect([...kept.seed, ...kept.rest].map((item) => item.item_id).sort()).toEqual(
			own.map((item) => item.item_id).sort()
		);
	});

	test('keeping a story the head already holds changes nothing', () => {
		const { date, vertical, items } = busiest();
		const first = items.filter((item) => item.vertical === vertical)[0].item_id;
		const plain = dayShell(date, 3, { vertical, root: CANARY })!;
		const kept = dayShell(date, 3, { vertical, keep: [first], root: CANARY })!;
		expect(kept.seed.map((item) => item.item_id)).toEqual(
			plain.seed.map((item) => item.item_id)
		);
	});

	test('keeping a story no day holds adds nothing', () => {
		const { date, vertical } = busiest();
		const plain = dayShell(date, 2, { vertical, root: CANARY })!;
		const kept = dayShell(date, 2, { vertical, keep: ['no-such-story'], root: CANARY })!;
		expect(kept.seed.map((item) => item.item_id)).toEqual(plain.seed.map((item) => item.item_id));
	});
});

test.describe('the home page anchors its leads', () => {
	/** A day the canary cannot stand in for.
	 *
	 * The canary's biggest day holds 8 stories against a 15-story seed and
	 * publishes no leads, so a seed built from it is always the whole day and this
	 * rule is invisible in it. The shape is built rather than found: 40 stories,
	 * with the two leads at positions 25 and 39 so neither is inside any head a
	 * page would take. Fixed in size, so it costs the same whatever the archive
	 * grows to (Rule #12).
	 */
	function dayWithOutlyingLeads(root: string, date: string): { leads: string[]; total: number } {
		const total = 40;
		const at = [25, 39];
		const items = Array.from({ length: total }, (_, index) => ({
			item_id: `story-${String(index).padStart(2, '0')}`,
			title: `Story ${index}`,
			url: `https://example.invalid/${index}`,
			source: 'Example',
			vertical: 'ai',
			// Descending, so the reading order is the published order and the leads
			// keep the positions this test put them in.
			published_at: `2026-08-20T${String(23 - Math.floor(index / 2)).padStart(2, '0')}:00:00Z`,
			summary: `Summary ${index}`,
			key_points: [`Point ${index}`]
		}));
		const leads = at.map((index) => items[index].item_id);
		const dir = join(root, ...date.split('-'));
		mkdirSync(dir, { recursive: true });
		writeFileSync(
			join(dir, 'digest.json'),
			JSON.stringify({
				date,
				items,
				leads: leads.map((item_id) => ({ item_id, why: 'because' })),
				verticals: [{ id: 'ai', display_name: 'AI', count: total }]
			})
		);
		return { leads, total };
	}

	test('every lead is in the seed, however far down the day it sits', () => {
		const root = mkdtempSync(join(tmpdir(), 'home-shell-'));
		const date = '2026-08-20';
		const { leads, total } = dayWithOutlyingLeads(root, date);

		const shell = homeShell(date, 15, root)!;
		const seeded = shell.seed.map((item) => item.item_id);

		// The regression this exists for: a home page that called `dayShell` without
		// `keep` shipped a leading block whose links land on nothing until the fetch
		// arrives, and on nothing at all when it fails.
		for (const lead of leads) {
			expect(seeded, `${lead} leads the day and the document does not carry it`).toContain(lead);
		}
		// And it is still a seed, or the page has quietly gone back to inlining.
		expect(seeded.length).toBe(15 + leads.length);
		expect(shell.rest.length).toBe(total - seeded.length);
		expect([...seeded, ...shell.rest.map((item) => item.item_id)].sort()).toHaveLength(total);
	});

	test('a day nobody published gives the home page no shell', () => {
		const root = mkdtempSync(join(tmpdir(), 'home-shell-'));
		expect(homeShell('2026-08-20', 15, root)).toBeNull();
	});
});
