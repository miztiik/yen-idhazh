/**
 * Row #17's oracle: the day runs newest first down a time rail, and every time
 * it prints is one the payload can vouch for.
 *
 * Four promises, and every one of them fails silently:
 *
 * 1. **The re-order is a re-order.** The stream orders by the time on the item
 *    rather than by the desk-blocked order the payload publishes, and a sort
 *    that drops a story looks exactly like a day that published fewer. So the
 *    item set is compared before and after, over every committed day.
 * 2. **No relative form, anywhere.** The page is prerendered once and read for
 *    the next 24 hours with script optionally off, so `3 hours ago` baked in at
 *    06:20 is wrong by 18:20 and wrong for ever on an archived day. Every label
 *    the rail can print is driven and matched against the relative forms.
 * 3. **A clock is attributed only where the payload attributes it.** A story
 *    whose `time_source` is `first_seen` carries our own first sight of the
 *    address rather than the publisher's date, and printing that as a bare
 *    `06:20` is the same class of failure as an invented axis label.
 * 4. **One marker per group, not one per story.** A label repeated ninety times
 *    is texture rather than information.
 *
 * The counts per `time_source` are asserted rather than assumed, and printed on
 * a failure, because a branch nothing exercised passes for free. Over the
 * committed days the `unknown` category is empty - no run has ever failed to
 * date a story at all - so that branch is carried by the canary day instead,
 * which plants one of every state on purpose.
 */

import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { orderByTime, railRows } from '../src/lib/day-shape';
import { railTime, type RailForm } from '../src/lib/format';
import { loadDay, publishedDates } from '../src/lib/server/payload';
import type { DigestItem } from '../src/lib/payload/types';

const HERE = dirname(fileURLToPath(import.meta.url));
/** The tree the preview server serves, so a route here is a route that exists. */
const BUILD = join(HERE, '..', 'build');
/** The tree that built it. */
const CANARY = resolve(HERE, '..', '..', 'backend', 'var', 'canary', 'digest');
/** Every day this project has published, which is where the real spread is. */
const COMMITTED = resolve(HERE, '..', 'public', 'digest');

/** Never a date written here: a hardcoded one passes on an empty page the
 * moment the fixture moves. */
const DAY = readdirSync(BUILD, { withFileTypes: true })
	.filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
	.map((entry) => entry.name)
	.sort()
	.at(-1) as string;

/** The grouping the page draws at, read off the config so a knob moved there
 * moves the expectation with it. */
const GROUP_MINUTES = ((): number => {
	const raw = JSON.parse(
		readFileSync(resolve(HERE, '..', '..', 'config', 'appearance.json'), 'utf8')
	) as { digest?: { rail_group_minutes?: number } };
	return raw.digest?.rail_group_minutes ?? 60;
})();

/** Every shape a reader could mistake for a clock that rewrites itself.
 *
 * Written as separate patterns rather than one alternation, so a failure names
 * which form was found. `Yesterday` is deliberately absent: it is relative to
 * the day the page IS, which is printed at the top of that page and never
 * moves, so it stays true on an archived day for ever.
 */
const RELATIVE = [
	/\bago\b/i,
	/\bjust now\b/i,
	/\bin \d/i,
	/\b(a|an|\d+)\s+(second|minute|hour|day|week|month|year)s?\b/i,
	/\bmoments?\b/i,
	/\btoday\b/i,
	/\btomorrow\b/i
];

function refuseRelative(label: string, where: string): void {
	for (const form of RELATIVE) {
		expect(form.test(label), `${where} printed a relative time: "${label}"`).toBe(false);
	}
}

test.describe('the day runs newest first, and every time it prints is attributed', () => {
	test('the re-order keeps the day, over every committed day', () => {
		const dates = publishedDates(COMMITTED);
		expect(dates.length, 'nothing is committed, so this checks nothing').toBeGreaterThan(0);

		let stories = 0;
		for (const date of dates) {
			const items = loadDay(date, COMMITTED)?.items ?? [];
			const ordered = orderByTime(items);
			stories += items.length;

			expect(ordered.length, `${date}: the re-order changed the story count`).toBe(items.length);
			expect(
				[...ordered].map((item) => item.item_id).sort(),
				`${date}: the re-order changed which stories the day holds`
			).toEqual([...items].map((item) => item.item_id).sort());

			// Newest first, with the undated at the end. Written as an indexed loop
			// rather than as the pairwise helper the implementation would reach for,
			// so this is a second expression of the rule and not a copy of it.
			let seenUndated = false;
			for (let i = 0; i < ordered.length - 1; i += 1) {
				const here = ordered[i].published_at;
				const next = ordered[i + 1].published_at;
				if (here === null) seenUndated = true;
				expect(
					seenUndated && next !== null,
					`${date}: a dated story sits below an undated one at ${i}`
				).toBe(false);
				if (here !== null && next !== null) {
					expect(
						here >= next,
						`${date}: ${here} is above ${next}, so the rail counts upward`
					).toBe(true);
				}
			}
		}
		expect(stories, 'the committed tree holds no stories').toBeGreaterThan(0);
	});

	test('every time_source category is counted, and each one prints its own form', () => {
		const seen: Record<string, number> = { feed: 0, first_seen: 0, unknown: 0, unrecorded: 0 };
		const forms: Record<RailForm, number> = {
			clock: 0,
			yesterday: 0,
			dated: 0,
			'first-seen': 0,
			none: 0
		};

		for (const date of publishedDates(COMMITTED)) {
			const day = loadDay(date, COMMITTED);
			for (const item of day?.items ?? []) {
				seen[item.time_source ?? 'unrecorded'] += 1;
				const time = railTime(item.published_at, item.time_source, date, GROUP_MINUTES);
				forms[time.form] += 1;
				refuseRelative(time.label, `${date} ${item.item_id}`);

				// The negative arm, and the whole reason `time_source` is published.
				// Our own clock never prints as a bare clock reading.
				if (item.time_source === 'first_seen') {
					expect(
						time.form,
						`${date} ${item.item_id} came off our clock and printed "${time.label}"`
					).toBe('first-seen');
					expect(time.label).toMatch(/^First seen \d{2}:\d{2}$/);
				} else {
					expect(
						time.label.startsWith('First seen'),
						`${date} ${item.item_id} claims a first sight the payload does not record`
					).toBe(false);
				}

				// And the positive arm: a story with no time at all says so, and one
				// with a time never does.
				expect(
					time.form === 'none',
					`${date} ${item.item_id} has ${item.published_at ? 'a time' : 'no time'} ` +
						`and printed "${time.label}"`
				).toBe(!item.published_at);
			}
		}

		const total = Object.values(seen).reduce((sum, n) => sum + n, 0);
		const counted = JSON.stringify(seen);
		expect(total, 'no story was counted, so nothing above ran').toBeGreaterThan(0);
		// Two of the four are what the committed days actually hold. Asserting
		// them is what stops a branch passing because no story reached it.
		expect(seen.feed, `no story came off a feed clock: ${counted}`).toBeGreaterThan(0);
		expect(seen.first_seen, `no story came off our own clock: ${counted}`).toBeGreaterThan(0);
		expect(
			seen.unrecorded,
			`no story predates time_source, so the unattributed form is untested: ${counted}`
		).toBeGreaterThan(0);
		expect(forms.clock, `no story printed a same-day clock: ${counted}`).toBeGreaterThan(0);
		expect(forms.yesterday, `no story printed the day before: ${counted}`).toBeGreaterThan(0);
		expect(forms.dated, `no story printed an older date: ${counted}`).toBeGreaterThan(0);
		expect(forms['first-seen'], `no story printed our clock: ${counted}`).toBeGreaterThan(0);
	});

	test('the canary day carries the one state no committed day has', () => {
		// `unknown` means neither the feed nor our own first sight gave a time.
		// It has never happened on a real run, so the fixture plants it - the
		// alternative is a branch that ships with no test at all.
		const items = loadDay(DAY, CANARY)?.items ?? [];
		expect(items.length, `the canary tree published nothing on ${DAY}`).toBeGreaterThan(0);

		const undated = items.filter((item) => item.time_source === 'unknown');
		expect(undated.length, 'the canary day no longer plants an undated story').toBe(1);
		const time = railTime(undated[0].published_at, undated[0].time_source, DAY, GROUP_MINUTES);
		expect(time.label).toBe('No time given');
		expect(time.form).toBe('none');

		// And every other form, on the same fixture, so the browser check below
		// has something to find.
		const drawn = new Set(
			orderByTime(items).map(
				(item) => railTime(item.published_at, item.time_source, DAY, GROUP_MINUTES).form
			)
		);
		expect([...drawn].sort()).toEqual(['clock', 'dated', 'first-seen', 'none', 'yesterday']);
	});

	test('the rail draws one marker per group, not one per story', () => {
		let stories = 0;
		let markers = 0;
		for (const date of publishedDates(COMMITTED)) {
			const items = orderByTime(loadDay(date, COMMITTED)?.items ?? []);
			const rows = railRows(items, date, GROUP_MINUTES);
			expect(rows.length, `${date}: the rail lost a story`).toBe(items.length);
			expect(rows[0]?.mark ?? null, `${date}: the first story opens no group`).not.toBeNull();

			// A marker is drawn exactly where the group changes, and nowhere else.
			let previous: string | null = null;
			for (const row of rows) {
				const time = railTime(row.item.published_at, row.item.time_source, date, GROUP_MINUTES);
				expect(
					row.mark !== null,
					`${date}: ${row.item.item_id} is in group ${time.group} and drew ` +
						`${row.mark ? 'a marker' : 'none'}`
				).toBe(time.group !== previous);
				previous = time.group;
			}
			stories += items.length;
			markers += rows.filter((row) => row.mark !== null).length;
		}

		// The whole point, as a number: a marker per story would be `stories`.
		expect(markers, 'the rail draws nothing').toBeGreaterThan(0);
		expect(
			markers,
			`${markers} markers over ${stories} stories - the rail is a label on almost ` +
				`every story, which is the state this grouping exists to avoid`
		).toBeLessThan(stories / 2);
	});

	test('a group is the configured span, and a day boundary always breaks it', () => {
		const at = (stamp: string | null, source: string | null): string =>
			railTime(stamp, source, '2026-08-20', 60).group;

		// Inside one hour, one group.
		expect(at('2026-08-20T14:05:00Z', 'feed')).toBe(at('2026-08-20T14:58:00Z', 'feed'));
		// Across the hour, two.
		expect(at('2026-08-20T14:58:00Z', 'feed')).not.toBe(at('2026-08-20T15:02:00Z', 'feed'));
		// Same clock reading, different days: never one group, whatever the span.
		expect(railTime('2026-08-20T14:05:00Z', 'feed', '2026-08-20', 1440).group).not.toBe(
			railTime('2026-08-19T14:05:00Z', 'feed', '2026-08-20', 1440).group
		);
		// And our clock never shares a group with a feed's, even at the same hour.
		expect(at('2026-08-20T14:05:00Z', 'first_seen')).not.toBe(at('2026-08-20T14:05:00Z', 'feed'));
	});

	test('the four strings, in the words the reader gets', () => {
		const day = '2026-08-20';
		expect(railTime(`${day}T14:05:00Z`, 'feed', day, 60).label).toBe('14:05');
		expect(railTime('2026-08-19T23:40:00Z', 'feed', day, 60).label).toBe('Yesterday 23:40');
		expect(railTime('2026-06-11T08:15:00Z', null, day, 60).label).toBe('11 Jun 08:15');
		expect(railTime('2019-06-11T08:15:00Z', null, day, 60).label).toBe('11 Jun 2019 08:15');
		expect(railTime(`${day}T06:20:00Z`, 'first_seen', day, 60).label).toBe('First seen 06:20');
		expect(railTime(null, 'unknown', day, 60).label).toBe('No time given');
		for (const label of [
			railTime(`${day}T14:05:00Z`, 'feed', day, 60).label,
			railTime('2026-08-19T23:40:00Z', 'feed', day, 60).label,
			railTime('2026-06-11T08:15:00Z', null, day, 60).label,
			railTime(`${day}T06:20:00Z`, 'first_seen', day, 60).label,
			railTime(null, 'unknown', day, 60).label
		]) {
			refuseRelative(label, 'the rail vocabulary');
		}
	});
});

test.describe('the rail on the page', () => {
	test('the markers run downward, the zone is named once, and only our clock is marked', async ({
		page
	}) => {
		const published = loadDay(DAY, CANARY)?.items ?? [];
		expect(published.length, `the canary tree published nothing on ${DAY}`).toBeGreaterThan(0);

		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/');
		// The home page inlines the whole day, and it pages at twelve.
		for (let guard = 0; guard <= published.length; guard += 1) {
			const more = page.getByRole('button', { name: /^Show \d+ more$/ });
			if ((await more.count()) === 0) break;
			await more.first().click();
		}
		await expect(page.locator('article.item')).toHaveCount(published.length);

		const seen = await page.evaluate(() => {
			const rail = document.querySelector('[data-time-rail]');
			return {
				notes: document.querySelectorAll('[data-rail-note]').length,
				noteText: (document.querySelector('[data-rail-note]')?.textContent ?? '').trim(),
				stories: rail ? rail.querySelectorAll('article.item').length : 0,
				marks: [...document.querySelectorAll('[data-rail-mark]')].map((mark) => ({
					label: (mark.textContent ?? '').replace(/\s+/g, ' ').trim(),
					form: mark.getAttribute('data-rail-form') ?? '',
					glyph: mark.querySelector('svg') !== null,
					top: Math.round(mark.getBoundingClientRect().top + window.scrollY)
				}))
			};
		});

		expect(seen.stories, 'the stream is not inside the rail').toBe(published.length);
		expect(seen.notes, 'the zone is named once at the top of the day, or not at all').toBe(1);
		expect(seen.noteText).toBe('Times shown in UTC.');

		expect(seen.marks.length, 'the rail drew nothing').toBeGreaterThan(0);
		expect(
			seen.marks.length,
			`${seen.marks.length} markers over ${published.length} stories - a marker on ` +
				`every story is what the grouping exists to avoid`
		).toBeLessThan(published.length);

		// The markers are in the order they are painted, so this is the promise a
		// reader scrolling actually gets: the page never counts upward.
		const tops = seen.marks.map((mark) => mark.top);
		expect([...tops].sort((a, b) => a - b)).toEqual(tops);
		const rank: Record<string, number> = {
			clock: 0,
			'first-seen': 0,
			yesterday: 1,
			dated: 2,
			none: 3
		};
		let previous = -1;
		for (const mark of seen.marks) {
			refuseRelative(mark.label, 'the rendered rail');
			expect(rank[mark.form], `an unknown marker form: ${mark.form}`).not.toBeUndefined();
			expect(
				rank[mark.form] >= previous,
				`"${mark.label}" (${mark.form}) came after a form older than it`
			).toBe(true);
			previous = rank[mark.form];
			// The one glyph the rail draws, and it draws it on one case.
			expect(
				mark.glyph,
				`"${mark.label}" ${mark.glyph ? 'carries' : 'is missing'} the stale-clock mark`
			).toBe(mark.form === 'first-seen');
		}

		// Every form the fixture plants reaches the page.
		expect([...new Set(seen.marks.map((mark) => mark.form))].sort()).toEqual([
			'clock',
			'dated',
			'first-seen',
			'none',
			'yesterday'
		]);
	});

	test('the time is printed once: the item eyebrow gave it to the rail', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/');
		const eyebrows = await page.evaluate(() =>
			[...document.querySelectorAll('[data-item-eyebrow]')].map((line) =>
				(line.textContent ?? '').replace(/\s+/g, ' ').trim()
			)
		);
		expect(eyebrows.length, 'no item rendered').toBeGreaterThan(0);
		for (const text of eyebrows) {
			expect(text, `the eyebrow still prints a clock: "${text}"`).not.toMatch(/\b\d{2}:\d{2}\b/);
			expect(text, `the eyebrow still prints a date: "${text}"`).not.toMatch(
				/\b\d{1,2} [A-Z][a-z]{2}\b/
			);
		}
	});

	test('a day whose stories carry no time still renders', async ({ page }) => {
		// Degrade, do not fail. `railTime` is the only reader of `published_at` on
		// the stream now, so a payload that carries none must still draw a page.
		const items: DigestItem[] = (loadDay(DAY, CANARY)?.items ?? []).map((item) => ({
			...item,
			published_at: null,
			time_source: null
		}));
		const rows = railRows(orderByTime(items), DAY, GROUP_MINUTES);
		expect(rows.length).toBe(items.length);
		expect(rows.filter((row) => row.mark !== null).length, 'one group, one marker').toBe(1);
		expect(rows[0].mark?.label).toBe('No time given');

		// And on the page: the canary's own undated story is on it, and the day
		// around it rendered.
		const errors: string[] = [];
		page.on('console', (message) => {
			if (message.type() === 'error') errors.push(message.text());
		});
		await page.goto('/');
		await expect(page.locator('article.item').first()).toBeVisible();
		await expect(page.locator('[data-rail-form="none"]')).toHaveCount(1);
		expect(errors, 'the day page logged an error').toEqual([]);
	});
});
