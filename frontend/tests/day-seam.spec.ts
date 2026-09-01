import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { dayShell, loadDay, publishedDates, wholeDay } from '../src/lib/server/payload';
import type { DigestItem } from '../src/lib/payload/types';

/**
 * Row #23's oracle, as a function rather than as a build, and row #25's seed
 * rules beside it.
 *
 * The reading routes load a day in two halves - the facts that do not grow with
 * the number of stories, and the stories themselves split at
 * `ui.shell_seed_items`. The day route still puts them back together; the topic
 * routes keep the head and fetch the rest. So the seam owes two things.
 *
 * Put back together it must change nothing: the day a route renders is the day
 * the loader read, key order and all. Key order is asserted rather than deep
 * equality alone because it is what the bytes are - a prerendered document
 * serialises an object in its own key order, and the committed payload writes
 * its keys sorted, so a day rebuilt with the stories appended is a different
 * document holding the same day.
 *
 * And split, it must lose nothing. A topic's seed comes from the topic's own
 * list, and a story named in `keep` is in the seed whatever its position - the
 * head is a prefix and a leading story is not inside one.
 */

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

/** Every split worth trying: nothing seeded, a partial seed, the exact length,
 * and a seed longer than the day. */
const SEEDS = [0, 1, 3, 8, 500];

test.describe('the reading routes load a day in two halves', () => {
	test('the halves put back together are the day the loader read', () => {
		const dates = publishedDates(CANARY);
		expect(dates.length, 'the canary tree published no day').toBeGreaterThan(0);
		for (const date of dates) {
			const whole = loadDay(date, CANARY);
			expect(whole, `${date} did not load`).not.toBeNull();
			for (const seed of SEEDS) {
				const shell = dayShell(date, seed, { root: CANARY });
				expect(shell, `${date} at a seed of ${seed} did not load`).not.toBeNull();
				expect(
					JSON.stringify(wholeDay(shell!)),
					`${date} at a seed of ${seed} rebuilt a different day`
				).toBe(JSON.stringify(whole));
			}
		}
	});

	test('the seed is the head of the published order and the rest is the tail', () => {
		const date = publishedDates(CANARY).find((d) => (loadDay(d, CANARY)?.items.length ?? 0) > 1);
		expect(date, 'no canary day carries more than one story').toBeDefined();
		const items = loadDay(date!, CANARY)!.items;
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

/** The newest canary day carrying more than one story, and a topic it holds. */
function busiest(): { date: string; vertical: string; items: DigestItem[] } {
	for (const date of publishedDates(CANARY)) {
		const day = loadDay(date, CANARY);
		if (!day || day.items.length < 2) continue;
		return { date, vertical: day.items[0].vertical, items: day.items };
	}
	throw new Error('no canary day carries more than one story');
}

test.describe('a topic route splits its own list', () => {
	test('the seed and the rest together are exactly the topic, in published order', () => {
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
