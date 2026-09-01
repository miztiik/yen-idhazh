import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { dayShell, loadDay, publishedDates, wholeDay } from '../src/lib/server/payload';

/**
 * Row #23's oracle, as a function rather than as a build.
 *
 * The reading routes now load a day in two halves - the facts that do not grow
 * with the number of stories, and the stories themselves split at
 * `ui.shell_seed_items` - and then put it straight back together. Rows 24 to 27
 * stop putting it back and fetch the remainder instead. So the one thing this
 * seam owes today is that it changes nothing: the day a route renders must be
 * the day the loader read, key order and all.
 *
 * Key order is asserted rather than deep equality alone because it is what the
 * bytes are. A prerendered document serialises an object in its own key order,
 * and the committed payload writes its keys sorted, so a day rebuilt with the
 * stories appended is a different document holding the same day.
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
				const shell = dayShell(date, seed, CANARY);
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
		const shell = dayShell(date!, 3, CANARY)!;
		expect(shell.seed.map((item) => item.item_id)).toEqual(
			items.slice(0, 3).map((item) => item.item_id)
		);
		expect(shell.rest.map((item) => item.item_id)).toEqual(
			items.slice(3).map((item) => item.item_id)
		);
	});

	test('the facts carry no stories, so they do not grow with the day', () => {
		const date = publishedDates(CANARY)[0];
		const shell = dayShell(date, 3, CANARY)!;
		expect(shell.facts.items).toEqual([]);
		expect(shell.facts.date).toBe(date);
		expect(shell.facts.verticals.length).toBeGreaterThan(0);
	});

	test('a date that was never published has no shell', () => {
		expect(dayShell('1999-01-01', 3, CANARY)).toBeNull();
	});
});
