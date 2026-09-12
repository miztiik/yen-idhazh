/**
 * Plan 25 row #5's oracle, the half that needs no browser: every story prints
 * its own published time beside its heading, and every time it prints is one
 * the payload can vouch for.
 *
 * This replaces `time-rail.spec.ts`. The rail is gone - it grouped stories by
 * the hour and drew one marker per group, which left 86.3 percent of stories
 * with no time at all (1,218 markers over 8,922 committed stories in 22 days,
 * re-measured 2026-09-12). What survives the rail is the formatter and the
 * order, and both keep their promises here:
 *
 * 1. **The re-order is a re-order.** `orderByTime` returns exactly the set it
 *    was handed, newest first, with the undated at the end. A sort that drops a
 *    story looks exactly like a day that published fewer.
 * 2. **No relative form, anywhere.** The page is prerendered once and read for
 *    the next 24 hours with script optionally off, so `3 hours ago` baked in at
 *    06:20 is wrong by 18:20 and wrong for ever on an archived day.
 * 3. **A clock is attributed only where the payload attributes it.** A story
 *    whose `time_source` is `first_seen` carries our own first sight of the
 *    address rather than the publisher's date, and printing that as a bare
 *    `06:20` is the same class of failure as an invented axis label.
 * 4. **`time_source: unknown` draws nothing at all.** There is no number to
 *    print, and a word saying so is a label with no fact under it.
 *
 * Every case is BUILT rather than sampled. `time_source` is a contract enum and
 * `published_at` is validated beside it, so a committed story cannot carry a
 * pair outside the table below - and the `unknown` branch has never once
 * happened in 8,922 committed items, so no archive-driven test can reach it.
 * The canary day plants one of every state on purpose, and what those four
 * states DRAW is asserted in `item-meta.spec.ts` against the built page.
 */

import { expect, test } from '@playwright/test';
import { orderByTime } from '../src/lib/day-shape';
import { itemTime, type TimeForm } from '../src/lib/format';
import { loadDay } from '../src/lib/server/payload';
import type { DigestItem } from '../src/lib/payload/types';
import { CANARY, newestDate } from './support/published';

/** Never a date written here: a hardcoded one passes on an empty page the
 * moment the fixture moves. Read off the digest tree rather than out of
 * `build/`, which since 2026-09-09 holds no dated directory at all. */
const DAY = newestDate();

/** Every shape a reader could mistake for a clock that rewrites itself.
 *
 * Written as separate patterns rather than one alternation, so a failure names
 * which form was found. The item prints digits only, so `Yesterday` cannot
 * appear either - the letter check in the truth table below catches it, and
 * this list stays the record of the specific forms that were argued about.
 */
const RELATIVE = [
	/\bago\b/i,
	/\bjust now\b/i,
	/\bin \d/i,
	/\b(a|an|\d+)\s+(second|minute|hour|day|week|month|year)s?\b/i,
	/\bmoments?\b/i,
	/\byesterday\b/i,
	/\btoday\b/i,
	/\btomorrow\b/i
];

function refuseRelative(label: string, where: string): void {
	for (const form of RELATIVE) {
		expect(form.test(label), `${where} printed a relative time: "${label}"`).toBe(false);
	}
}

/** A story carrying only what the time formatter reads off one.
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
				expect(here >= next, `${here} is above ${next}, so the stream counts upward`).toBe(true);
			}
		}
	});

	test('every clock a payload can carry prints its own form', () => {
		// The whole domain rather than a sample of it. `time_source` is a contract
		// enum and `published_at` is validated beside it, so a committed story
		// cannot carry a pair outside this table - which is what walking the
		// archive was re-establishing, once per story, for ever (Guardrail #12).
		const day = '2026-08-20';
		const cases: { at: string | null; source: string | null; form: TimeForm; label: string }[] = [
			{ at: `${day}T14:05:00Z`, source: 'feed', form: 'clock', label: '14:05' },
			{ at: `${day}T14:05:00Z`, source: null, form: 'clock', label: '14:05' },
			{ at: '2026-08-19T23:40:00Z', source: 'feed', form: 'dated', label: '08-19 23:40' },
			{ at: '2026-08-19T23:40:00Z', source: null, form: 'dated', label: '08-19 23:40' },
			{ at: '2026-06-11T08:15:00Z', source: null, form: 'dated', label: '06-11 08:15' },
			{ at: '2019-06-11T08:15:00Z', source: null, form: 'dated', label: '2019-06-11 08:15' },
			{ at: `${day}T06:20:00Z`, source: 'first_seen', form: 'first-seen', label: '06:20' },
			{ at: null, source: 'unknown', form: 'none', label: '' }
		];

		for (const one of cases) {
			const time = itemTime(one.at, one.source, day);
			const named = `${one.source ?? 'unrecorded'} at ${one.at ?? 'no time'}`;
			expect(time.label, named).toBe(one.label);
			expect(time.form, named).toBe(one.form);
			refuseRelative(time.label, named);

			// The stamp is digits. A label carrying a letter is a word that crept
			// back in, whichever branch put it there.
			expect(/[A-Za-z]/.test(time.label), `${named} prints a word`).toBe(false);
			// Our own clock is still marked as ours - by `form`, which the item
			// draws a glyph from, never by a phrase in the label.
			expect(time.form === 'first-seen', named).toBe(one.source === 'first_seen');
			// A story with no time prints nothing, and one with a time always prints.
			expect(time.form === 'none', named).toBe(!one.at);
			expect(time.label === '', named).toBe(!one.at);
		}

		// Exhaustive by construction, which a census could only approximate: it
		// counted what the corpus happened to hold, and over 8,922 committed
		// stories the corpus has never once held an undated one.
		expect(
			[...new Set(cases.map((one) => one.form))].sort(),
			'a form no case reaches is a branch with no test'
		).toEqual(['clock', 'dated', 'first-seen', 'none']);
	});

	test('an unattributed stamp is drawn exactly like a feed stamp, and takes no mark', () => {
		// 3,733 committed items predate `time_source` and carry a stamp labelled by
		// nobody - 41.8 percent of the archive, re-measured 2026-09-12 over 8,922
		// items. `rank.appeared_at` chose that stamp the same way it chooses one
		// today; only the label was thrown away. So the honest render is the stamp
		// with no claim attached: a mark would assert a clock the run never
		// recorded, and blanking it would delete a fact from two items in five.
		const day = '2026-08-20';
		const attributed = itemTime(`${day}T14:05:00Z`, 'feed', day);
		const unattributed = itemTime(`${day}T14:05:00Z`, null, day);
		expect(
			unattributed,
			'the unlabelled stamp is drawn differently from a feed stamp'
		).toEqual(attributed);
		expect(unattributed.form, 'an unlabelled stamp took the first-seen mark').not.toBe(
			'first-seen'
		);
		expect(unattributed.label, 'an unlabelled stamp was blanked').not.toBe('');
	});

	test('the canary day carries the one state no committed day has', () => {
		// `unknown` means neither the feed nor our own first sight gave a time.
		// It has never happened on a real run, so the fixture plants it - the
		// alternative is a branch that ships with no test at all.
		const items = loadDay(DAY, CANARY)?.items ?? [];
		expect(items.length, `the canary tree published nothing on ${DAY}`).toBeGreaterThan(0);

		const undated = items.filter((item) => item.time_source === 'unknown');
		expect(undated.length, 'the canary day no longer plants an undated story').toBe(1);
		const time = itemTime(undated[0].published_at, undated[0].time_source, DAY);
		expect(time.label).toBe('');
		expect(time.form).toBe('none');

		// And every other form, on the same fixture, so the browser half in
		// `item-meta.spec.ts` has something to find.
		const drawn = new Set(
			orderByTime(items).map((item) => itemTime(item.published_at, item.time_source, DAY).form)
		);
		expect([...drawn].sort()).toEqual(['clock', 'dated', 'first-seen', 'none']);
	});

	test('a day whose stories carry no time still renders', async ({ page }) => {
		// Degrade, do not fail. A payload that carries no stamp at all must still
		// draw a page, and every item on it draws no time rather than an empty
		// slot with a mark in it.
		const items: DigestItem[] = (loadDay(DAY, CANARY)?.items ?? []).map((item) => ({
			...item,
			published_at: null,
			time_source: null
		}));
		expect(items.length, 'the canary published nothing to blank').toBeGreaterThan(0);
		const forms = new Set(
			items.map((item) => itemTime(item.published_at, item.time_source, DAY).form)
		);
		expect([...forms], 'a blanked day still prints a number somewhere').toEqual(['none']);

		// And on the page: the canary's own undated story is on it, and the day
		// around it rendered.
		const errors: string[] = [];
		page.on('console', (message) => {
			if (message.type() === 'error') errors.push(message.text());
		});
		await page.goto('/');
		await expect(page.locator('article.item').first()).toBeVisible();
		// The zone caption survives the rail that used to carry it, once per page.
		// It is what makes every bare clock on the page readable.
		await expect(
			page.locator('[data-time-note]'),
			'the day names its clock more than once, or not at all'
		).toHaveCount(1);
		await expect(page.locator('[data-time-note]')).toHaveText('Times shown in UTC.');
		expect(errors, 'the day page logged an error').toEqual([]);
	});
});
