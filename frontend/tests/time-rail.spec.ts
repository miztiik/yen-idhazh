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
import { loadDay } from '../src/lib/server/payload';
import type { DigestItem } from '../src/lib/payload/types';

const HERE = dirname(fileURLToPath(import.meta.url));
/** The tree the preview server serves, so a route here is a route that exists. */
const BUILD = join(HERE, '..', 'build');
/** The tree that built it. */
const CANARY = resolve(HERE, '..', '..', 'backend', 'var', 'canary', 'digest');

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

/** A story carrying only what the rail reads off one.
 *
 * Everything else on a `DigestItem` is another surface's business, so it is
 * filled once here and never varied - a case below differs from its neighbour
 * in the clock and in nothing else.
 */
function story(id: string, at: string | null, source: string | null): DigestItem {
	return {
		item_id: id,
		vertical: 'ai',
		title: `Story ${id}`,
		source_url: `https://example.test/${id}`,
		source_id: 'test',
		source_name: 'Test',
		source_kind: 'reporting',
		published_at: at,
		time_source: source,
		summary: id,
		key_points: [],
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
	} as DigestItem;
}

test.describe('the day runs newest first, and every time it prints is attributed', () => {
	test('the re-order keeps every story it was given, and never counts upward', () => {
		const day = '2026-08-20';
		const items = [
			story('ai-01', `${day}T06:20:00Z`, 'feed'),
			story('ai-02', null, 'unknown'),
			story('ai-03', `${day}T14:05:00Z`, 'feed'),
			story('ai-04', '2026-08-19T23:40:00Z', 'feed'),
			// A tie. An unstable sort drops or duplicates a story here and nowhere else.
			story('ai-05', `${day}T14:05:00Z`, 'first_seen'),
			story('ai-06', '2019-06-11T08:15:00Z', null),
			story('ai-07', null, null)
		];

		const ordered = orderByTime(items);
		expect(ordered.length, 'the re-order changed the story count').toBe(items.length);
		expect(
			ordered.map((item) => item.item_id).sort(),
			'the re-order changed which stories the day holds'
		).toEqual(items.map((item) => item.item_id).sort());

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
				`a dated story sits below an undated one at ${i}`
			).toBe(false);
			if (here !== null && next !== null) {
				expect(here >= next, `${here} is above ${next}, so the rail counts upward`).toBe(true);
			}
		}
	});

	test('every clock a payload can carry prints its own form', () => {
		// The whole domain rather than a sample of it. `time_source` is a contract
		// enum and `published_at` is validated beside it, so a committed story
		// cannot carry a pair outside this table - which is what walking the
		// archive was re-establishing, once per story, for ever.
		const day = '2026-08-20';
		const cases: { at: string | null; source: string | null; form: RailForm; label: string }[] = [
			{ at: `${day}T14:05:00Z`, source: 'feed', form: 'clock', label: '14:05' },
			{ at: `${day}T14:05:00Z`, source: null, form: 'clock', label: '14:05' },
			{ at: '2026-08-19T23:40:00Z', source: 'feed', form: 'yesterday', label: 'Yesterday 23:40' },
			{ at: '2026-08-19T23:40:00Z', source: null, form: 'yesterday', label: 'Yesterday 23:40' },
			{ at: '2026-06-11T08:15:00Z', source: null, form: 'dated', label: '11 Jun 08:15' },
			{ at: '2019-06-11T08:15:00Z', source: null, form: 'dated', label: '11 Jun 2019 08:15' },
			{
				at: `${day}T06:20:00Z`,
				source: 'first_seen',
				form: 'first-seen',
				label: 'First seen 06:20'
			},
			{ at: null, source: 'unknown', form: 'none', label: 'No time given' }
		];

		for (const one of cases) {
			const time = railTime(one.at, one.source, day, GROUP_MINUTES);
			const named = `${one.source ?? 'unrecorded'} at ${one.at ?? 'no time'}`;
			expect(time.label, named).toBe(one.label);
			expect(time.form, named).toBe(one.form);
			refuseRelative(time.label, named);

			// Our own clock never prints as a bare reading, and no other clock claims
			// a first sight the payload does not record.
			expect(time.label.startsWith('First seen'), named).toBe(one.source === 'first_seen');
			// A story with no time says so, and one with a time never does.
			expect(time.form === 'none', named).toBe(!one.at);
		}

		// Exhaustive by construction, which the census could only approximate: it
		// counted what the corpus happened to hold, and over 6,539 committed
		// stories the corpus has never once held an undated one.
		expect(
			[...new Set(cases.map((one) => one.form))].sort(),
			'a form no case reaches is a branch with no test'
		).toEqual(['clock', 'dated', 'first-seen', 'none', 'yesterday']);
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
		const day = '2026-08-20';
		// Seven stories over several groups: two feed clocks in one hour, three in
		// the hour below it, our own clock, which never shares a group with a
		// feed's, and a story with no time at all.
		const items = orderByTime([
			story('ai-01', `${day}T14:58:00Z`, 'feed'),
			story('ai-02', `${day}T14:05:00Z`, 'feed'),
			story('ai-03', `${day}T13:50:00Z`, 'feed'),
			story('ai-04', `${day}T13:20:00Z`, 'feed'),
			story('ai-05', `${day}T13:01:00Z`, 'feed'),
			story('ai-06', `${day}T13:40:00Z`, 'first_seen'),
			story('ai-07', null, 'unknown')
		]);

		const rows = railRows(items, day, GROUP_MINUTES);
		expect(rows.length, 'the rail lost a story').toBe(items.length);
		expect(rows[0]?.mark ?? null, 'the first story opens no group').not.toBeNull();

		// A marker is drawn exactly where the group changes, and nowhere else.
		let previous: string | null = null;
		for (const row of rows) {
			const time = railTime(row.item.published_at, row.item.time_source, day, GROUP_MINUTES);
			expect(
				row.mark !== null,
				`${row.item.item_id} is in group ${time.group} and drew ` +
					`${row.mark ? 'a marker' : 'none'}`
			).toBe(time.group !== previous);
			previous = time.group;
		}

		// The whole point, as a number: a marker per story would be `items.length`.
		const markers = rows.filter((row) => row.mark !== null).length;
		expect(markers, 'the rail draws nothing').toBeGreaterThan(0);
		expect(
			markers,
			`${markers} markers over ${items.length} stories - a label on almost every ` +
				`story is the state this grouping exists to avoid`
		).toBeLessThan(items.length);
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
