import { test, expect } from '@playwright/test';
import type { SourceHealthRow, SourceHealthView } from '../src/lib/server/payload';
import { retiring } from '../src/lib/server/source-retiring';

/** The reliability strip: is a source counting down, and can an operator see it?
 *
 * One question a file. Whether the panel is on exactly one route is
 * `console-voices.spec.ts`'s; the yield figures themselves are
 * `console-voices-sources.spec.ts`'s. This file owns the countdown: the dwell
 * drawn as an area, the shared date axis, and the three sentences that carry
 * the state without colour.
 *
 * What a countdown row carries - its bar, where its dwell starts and the line
 * under it - is worked out by `retiring()` over a census written below, because
 * no source on the canary is under the mark and a row that is never drawn is a
 * row no test can read. Everything else is read off the built canary, which is
 * what `playwright.config.ts` serves, and checks only what holds for any census.
 * Nothing here opens a committed ledger: the archive grows on every run and a
 * test whose cost grows with it is the defect Guardrail #12 names (`CLAUDE.md`
 * section 13).
 */

const ROUTE = '/console/voices/';

/** A source the census names, with every count it was judged on. */
function source(over: Partial<SourceHealthRow> & Pick<SourceHealthRow, 'source_id'>): SourceHealthRow {
	return {
		title: `The ${over.source_id} desk`,
		vertical: 'world',
		permission: 'allowed',
		availability: 'answering',
		retired: false,
		retired_on: null,
		opportunities: 0,
		publications: 0,
		source_failures: 0,
		reliability: 1,
		reliability_reads: 0,
		recent_days: [],
		days_under_the_mark: 0,
		retires_on: null,
		...over
	};
}

/** One day of a source's share on the census's five-day axis. */
function day(date: string, publications: number, failures: number) {
	return { date, opportunities: publications + failures, publications, source_failures: failures };
}

/** A census of 20 complete days, judged at 7 of them and 30 decisions, with a mark of
 *  half the addresses a source decides and a dwell of 14 days.
 *
 *  - `gone` was retired on 10 Jun 2030: 3 of 40 decided, nothing running now.
 *  - `falling` published 12 of the 40 it decided, under the mark for its newest 3 days.
 *  - `sliding` published 15 of 35, under the mark for its newest day.
 *  - `steady` published 30 of 40 and is at or above the mark.
 *  - `thin` decided 5 of the 9 it was offered, under both evidence floors.
 */
function census(): SourceHealthView {
	const dates = ['2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14', '2030-06-15'];
	const days = (shares: [number, number][]) => shares.map(([kept, lost], at) => day(dates[at], kept, lost));
	return {
		generated_at: '2030-06-15T19:00:00Z',
		run_id: '2030-06-15-1',
		headline_sentence: 'Five sources were read.',
		reliability_floor: 0.5,
		reliability_window_days: 30,
		min_complete_days: 7,
		complete_dates: 20,
		yield_readable: true,
		first_date: '2030-05-27',
		last_date: '2030-06-15',
		yield_alarm_point: 0.5,
		yield_alarm_min_decisions: 30,
		dwell_days: 14,
		auto_retire: false,
		dwell_dates: dates,
		sources: [
			source({ source_id: 'gone', retired: true, retired_on: '2030-06-10', opportunities: 45, publications: 3, source_failures: 37 }),
			source({
				source_id: 'falling',
				opportunities: 45,
				publications: 12,
				source_failures: 28,
				recent_days: days([[6, 4], [5, 5], [1, 9], [2, 8], [0, 10]]),
				days_under_the_mark: 3,
				retires_on: '2030-06-26'
			}),
			source({
				source_id: 'sliding',
				opportunities: 40,
				publications: 15,
				source_failures: 20,
				recent_days: days([[7, 3], [6, 4], [8, 2], [5, 5], [3, 7]]),
				days_under_the_mark: 1,
				retires_on: '2030-06-28'
			}),
			source({ source_id: 'steady', opportunities: 44, publications: 30, source_failures: 10 }),
			source({ source_id: 'thin', opportunities: 9, publications: 2, source_failures: 3 })
		]
	};
}

test('the panel is present in every state, and says which one it is in', async ({ page }) => {
	await page.goto(ROUTE);

	const heading = page.getByRole('heading', { name: 'Sources close to retiring themselves' });
	await expect(heading).toBeVisible();

	// The heading survives even when the run published no census. A panel that
	// disappears teaches an operator to stop looking for it.
	const table = page.locator('[data-retiring="table"]');
	const absent = page.locator('[data-retiring="absent"]');
	expect((await table.count()) + (await absent.count())).toBe(1);
});

test('a countdown that retires nothing says so in words', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const auto = await table.getAttribute('data-retiring-auto');
	const watching = page.locator('[data-retiring-watching]');

	if (auto === 'no') {
		// A red countdown while nothing retires is a lie told in colour. The
		// sentence is what makes the panel honest in its first release.
		await expect(watching).toHaveText(/watching only/);
	} else {
		expect(await watching.count()).toBe(0);
	}
});

test('the lead names the rule in full: a share, a run of days, and a denominator', async ({
	page
}) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const lead = await page.locator('[data-retiring-lead]').innerText();
	const dwell = await table.getAttribute('data-retiring-dwell');

	// A share with no period is not a measurement, and a period with no share is
	// not a rule. Both are in one sentence or the panel has not said the rule.
	expect(lead).toMatch(/\d+%/);
	expect(lead).toContain(`${dwell} days running`);
	await expect(page.locator('[data-retiring-clear]')).toHaveText(/at or above the mark/);
});

test('every row draws its bar on the same track with its marker at the same share', () => {
	// The whole reason to stack these is that a column means the same thing all the
	// way down. A per-row maximum, or a marker at a different x on different rows,
	// makes the stack unreadable while looking perfectly fine. Three ranked rows at
	// three shares: each bar's fill is its own share, and each track and marker are
	// the same.
	const strip = retiring(census(), 10);
	expect(strip?.rows.map((row) => row.sourceId)).toEqual(['gone', 'falling', 'sliding']);
	for (const row of strip?.rows ?? []) {
		expect(row.marks.track, `${row.sourceId} is drawn on its own track`).toBe(1);
		expect(row.marks.markerFraction, `${row.sourceId} puts the mark elsewhere`).toBe(0.5);
	}
	expect(strip?.rows.map((row) => row.marks.valueFraction)).toEqual([3 / 40, 12 / 40, 15 / 35]);
});

test('the dwell is an area under the newest squares, not a number in a chip', () => {
	// On a five-day axis, a run of 3 days under the mark is underlined from the third
	// square to the newest, and a run of 1 day under the newest square alone. A row
	// with no run under way draws no rule at all. Which days are under the mark is
	// the run's own count, and `backend/tests/test_source_dwell.py` holds it.
	const strip = retiring(census(), 10);
	expect(strip?.dates).toHaveLength(5);
	expect(strip?.rows.map((row) => [row.sourceId, row.daysUnder, row.dwellFrom])).toEqual([
		['gone', 0, null],
		['falling', 3, 3],
		['sliding', 1, 5]
	]);
});

test('a live countdown reads its days and its date without colour', () => {
	// The line under each row says what it published of what it was offered, and
	// while it is under the mark, for how long and the day it retires on; the chip
	// counts the days left. A row under its evidence floors says how much it decided.
	const strip = retiring(census(), 10);
	expect(strip?.rows.map((row) => [row.sourceId, row.daysLeft, row.readout])).toEqual([
		['gone', null, '3 published of 45 offered, over 20 complete days.'],
		[
			'falling',
			11,
			'12 published of 45 offered, over 20 complete days. Under the mark for 3 days running - 3 of 14. Retires on 2030-06-26 if it stays there.'
		],
		[
			'sliding',
			13,
			'15 published of 40 offered, over 20 complete days. Under the mark for 1 day running - 1 of 14. Retires on 2030-06-28 if it stays there.'
		]
	]);
	expect(strip?.unjudged.map((row) => [row.sourceId, row.readout])).toEqual([
		['thin', 'Decided 5 of the 9 addresses it was offered.']
	]);
	expect(strip?.clear, 'steady is the one judged source at or above the mark').toBe(1);
});

test('one date axis serves the whole list, so a column is one day on every row', async ({
	page
}) => {
	await page.goto(ROUTE);
	const strips = page.locator('[data-retiring-strip]');
	const count = await strips.count();
	test.skip(count === 0, 'the canary drew no strip');

	const widths = await strips.evaluateAll((list) =>
		list.map((strip) => strip.querySelectorAll('[data-retiring-day]').length)
	);
	expect(new Set(widths).size).toBe(1);

	const dates = await strips
		.first()
		.locator('[data-retiring-day]')
		.evaluateAll((list) => list.map((square) => square.getAttribute('data-retiring-day')));
	for (let index = 1; index < count; index += 1) {
		const other = await strips
			.nth(index)
			.locator('[data-retiring-day]')
			.evaluateAll((list) => list.map((square) => square.getAttribute('data-retiring-day')));
		expect(other).toEqual(dates);
	}
});

test('every square carries a sentence, so colour is never the only signal', async ({ page }) => {
	await page.goto(ROUTE);
	const squares = page.locator('[data-retiring-day]');
	const count = await squares.count();
	test.skip(count === 0, 'the canary drew no strip');

	const labels = await squares.evaluateAll((list) =>
		list.map((square) => square.getAttribute('aria-label') ?? '')
	);
	expect(labels.every((label) => label.length > 0)).toBe(true);
	expect(labels.some((label) => /mark|decided nothing/.test(label))).toBe(true);
});

test('a source under its evidence floors is drawn, not hidden, and says what is missing', async ({
	page
}) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const unjudged = page.locator('[data-retiring-unjudged-row]');
	const count = await unjudged.count();
	test.skip(count === 0, 'every source on the canary has cleared both floors');

	// Hiding these would hide the shape, and the shape is what an operator is
	// here for. What they have not got is a number anybody may act on.
	await expect(page.locator('[data-retiring-unjudged-lead]')).toHaveText(/Not judged yet/);
	await expect(page.locator('[data-retiring-unjudged-lead]')).toHaveText(
		/judged at \d+ of them plus \d+/
	);
	const readout = await unjudged.first().locator('[data-retiring-readout]').innerText();
	expect(readout).toMatch(/Decided \d+ of the \d+ address/);
	expect(await unjudged.first().locator('[data-retiring-chip]').count()).toBe(0);
});

test('the unjudged block is capped too, and its tail is a number', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const drawn = await page.locator('[data-retiring-unjudged-row]').count();
	test.skip(drawn === 0, 'every source on the canary has cleared both floors');

	// On a shallow record every source is unjudged, which on this repository is
	// 156 rows. A wall is not a panel, so it caps like every other console list.
	expect(drawn).toBeLessThanOrEqual(Number(await table.getAttribute('data-retiring-cap')));
	const more = page.locator('[data-retiring-unjudged-more]');
	if ((await more.count()) > 0) await expect(more).toHaveText(/^\d+ more/);
});

test('the tail of the ranking is a number, never another page of rows', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const hidden = Number(await table.getAttribute('data-retiring-hidden'));
	const more = page.locator('[data-retiring-more]');
	expect(await more.count()).toBe(hidden > 0 ? 1 : 0);
	if (hidden > 0) await expect(more).toHaveText(new RegExp(`^${hidden} more`));
});

test('the matrix declares one strip for all its squares', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	// Every square is one source on one day, read in the one strip under the
	// table. The declaration belongs to the table, not to each source's row:
	// one strip per source is the same strip once per source.
	const records = Number(await table.getAttribute('data-readout-records'));
	expect(records).toBeGreaterThan(0);
	expect(
		await page
			.locator('[data-retiring-strip][data-readout-records], [data-retiring-strip][data-readout-none]')
			.count()
	).toBe(0);
});
