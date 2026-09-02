import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { archiveCalendar, dayDate, type ArchiveDay } from '../src/lib/archive-calendar';

/**
 * The archive's day list stops growing one link a published day.
 *
 * The Oracle this row is held to: a fixture archive of 700 published days
 * renders at most `archive_recent_days` rows plus one row per month plus one
 * row per prior year, and every one of those 700 days is still reachable with
 * no script at all.
 *
 * The 700-day arm is driven in Node rather than in a page, for the reason
 * `archive-scope.spec.ts` is: the canary build publishes twenty days in one
 * month, and a rule about two years of months cannot show up in it. The
 * browser arms below hold the parts only a real document can answer - that the
 * rows are there, that a month is shut at rest, and that a `<details>` opens
 * and its links navigate with scripting switched off.
 *
 * What this file does NOT hold is the page's weight. That was measured by hand
 * on two fixture archives and is recorded in `docs/reference/measurements.md`;
 * there is no ratchet file to keep it, and a build-to-build byte comparison on
 * a developer machine is noise (`docs/reference/agent-notes.md`).
 */

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

/** How many days the archive lists as rows of their own, off the committed config. */
function recentDays(): number {
	const parsed = JSON.parse(
		readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
	) as { digest?: { archive_recent_days?: number } };
	const days = parsed.digest?.archive_recent_days;
	expect(days, 'config/appearance.json no longer sets digest.archive_recent_days').toBeDefined();
	return days as number;
}

/** `count` consecutive published days ending on `last`, newest first. */
function consecutive(count: number, last: string): ArchiveDay[] {
	const end = Date.parse(`${last}T00:00:00Z`);
	return Array.from({ length: count }, (_, back) => ({
		date: new Date(end - back * 86_400_000).toISOString().slice(0, 10),
		items: 10,
		partial: false
	}));
}

test.describe('the calendar at seven hundred days', () => {
	// 700 days ending 1 September 2026 starts on 2 October 2024: 244 days of
	// 2026 up to and including 1 September, all 365 of 2025, and 91 of 2024.
	const days = consecutive(700, '2026-09-01');
	const calendar = archiveCalendar(days);

	test('the reader meets rows in the tens, not links in the hundreds', () => {
		expect(days[0]!.date).toBe('2026-09-01');
		expect(days[699]!.date).toBe('2024-10-02');

		// January to September of the newest published year.
		expect(calendar.months.map((month) => month.month)).toEqual([
			'2026-09',
			'2026-08',
			'2026-07',
			'2026-06',
			'2026-05',
			'2026-04',
			'2026-03',
			'2026-02',
			'2026-01'
		]);
		expect(calendar.years.map((year) => year.year)).toEqual(['2025', '2024']);

		const atRest = recentDays() + calendar.months.length + calendar.years.length;
		expect(atRest, 'the day list is meant to be scannable at 700 days').toBe(18);

		// And even with every year opened, the ceiling is a row a month.
		const everyMonth =
			calendar.months.length +
			calendar.years.reduce((count, year) => count + year.months.length, 0);
		expect(recentDays() + everyMonth + calendar.years.length).toBeLessThanOrEqual(33);
	});

	test('no day is dropped, and no day is reachable twice from the calendar', () => {
		const reached: string[] = [];
		for (const month of [
			...calendar.months,
			...calendar.years.flatMap((year) => year.months)
		]) {
			for (const day of month.days) reached.push(dayDate(month.month, day));
		}
		expect(new Set(reached).size, 'a date is behind two different months').toBe(reached.length);
		expect([...reached].sort()).toEqual(days.map((day) => day.date).sort());
	});

	test('a month row states its own span, and the spans add up', () => {
		const august = calendar.months.find((month) => month.month === '2026-08');
		expect(august).toBeDefined();
		expect(august!.label).toBe('August 2026');
		expect(august!.length, 'August has 31 days').toBe(31);
		expect(august!.days.length).toBe(31);
		expect(august!.stories).toBe(310);

		// The oldest month in the window published 30 of its 31 days, which is the
		// row that proves the denominator is the calendar rather than what we hold.
		const october = calendar.years
			.find((year) => year.year === '2024')!
			.months.find((month) => month.month === '2024-10')!;
		expect(october.days.length).toBe(30);
		expect(october.length).toBe(31);

		const leap = calendar.years.find((year) => year.year === '2024')!;
		expect(leap.length, '2024 is a leap year').toBe(366);
		expect(leap.days).toBe(91);
		expect(calendar.years.find((year) => year.year === '2025')!.length).toBe(365);
	});

	test('a month with a gap in it still says how many days it holds', () => {
		// Every other day of one month, which is the shape a run that failed leaves.
		const sparse = archiveCalendar(
			[2, 4, 6, 8].map((day) => ({ date: `2026-04-0${day}`, items: 3, partial: false }))
		);
		const april = sparse.months[0]!;
		expect(april.days).toEqual([8, 6, 4, 2]);
		expect(april.length).toBe(30);
		expect(april.stories).toBe(12);
		expect(sparse.years).toEqual([]);
	});

	test('an archive that has published nothing is a calendar with no rows', () => {
		expect(archiveCalendar([])).toEqual({ months: [], years: [] });
	});
});

/** Every day link on the page, open or folded away. */
async function dayLinks(page: Page): Promise<string[]> {
	return page
		.locator('[data-day-row] a')
		.evaluateAll((links) => links.map((link) => link.getAttribute('href') ?? ''));
}

test('the newest days are rows and every other day is inside its month', async ({ page }) => {
	await page.goto('/archive/');

	const rows = page.locator('[data-day-recent] li');
	const count = await rows.count();
	expect(count, 'the recent block is empty').toBeGreaterThan(0);
	expect(count, 'the recent block grew past the knob').toBeLessThanOrEqual(recentDays());
	// A row carries the long date and the story count, not a bare date.
	await expect(rows.first()).toContainText(/\d{1,2} [A-Z][a-z]+ \d{4}/);
	await expect(rows.first()).toContainText(/\d+ (story|stories)/);

	const months = page.locator('[data-archive-month]');
	expect(await months.count(), 'no month row was drawn').toBeGreaterThan(0);
	// Shut at rest. An open month is the wall of dates this row removed.
	expect(
		await months.evaluateAll(
			(folds) => folds.filter((fold) => (fold as HTMLDetailsElement).open).length
		),
		'a month disclosure is open before anybody asked'
	).toBe(0);

	// Every committed day is still linked, whichever block it landed in.
	const links = await dayLinks(page);
	const dates = new Set(
		links.map((href) => /(\d{4}-\d{2}-\d{2})/.exec(href)?.[1]).filter((date) => date !== undefined)
	);
	const scope = (await page.locator('[data-archive-scope]').innerText()).trim();
	const published = Number(/^(\d+) days?/.exec(scope)?.[1] ?? '0');
	expect(published, 'the page states no day count to check against').toBeGreaterThan(0);
	expect(dates.size, 'a published day has no link anywhere on the page').toBe(published);
});

test('a month opens and its days navigate with no script at all', async ({ browser }) => {
	// The reason the day links were kept rather than deleted: this list is the
	// only part of the archive that works before a script runs, and the page's
	// own `<noscript>` line says so. A `<details>` is stateful and
	// keyboard-reachable with no script, which is asserted here rather than
	// assumed.
	const context = await browser.newContext({ javaScriptEnabled: false });
	const page = await context.newPage();
	try {
		await page.goto('/archive/');

		const recent = page.locator('[data-day-recent] a').first();
		const first = await recent.getAttribute('href');
		expect(first).toMatch(/\/\d{4}-\d{2}-\d{2}\/$/);
		await recent.click();
		await expect(page).toHaveURL(new RegExp(`${first}$`));
		await expect(page.locator('h1').first()).toBeVisible();

		await page.goBack();
		const month = page.locator('[data-archive-month]').first();
		await expect(month.locator('a').first()).toBeHidden();
		await month.locator('summary').click();
		const folded = month.locator('a').first();
		await expect(folded, 'a month disclosure did not open without a script').toBeVisible();

		const href = await folded.getAttribute('href');
		expect(href).toMatch(/\/\d{4}-\d{2}-\d{2}\/$/);
		await folded.click();
		await expect(page).toHaveURL(new RegExp(`${href}$`));
		await expect(page.locator('h1').first()).toBeVisible();
	} finally {
		await context.close();
	}
});
