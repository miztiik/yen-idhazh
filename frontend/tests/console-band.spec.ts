import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { PAGES_CAP_BYTES, siteCost, siteRunway } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';

/**
 * The band's remaining-room figure, and the unit it is allowed to be in.
 *
 * It used to be published days, and the number of articles it divided a day by
 * was `run.safety_ceiling_per_run` - which bounds one RUN, not one day. The
 * schedule fires up to five runs a day, so a day was priced at 160 articles
 * while the ten committed published days ran 4 to 731, median 334 (measured
 * 2026-08-31). The band printed 1,950 published days where the measured median
 * rate gives 934: too long by 2.09 times.
 *
 * The fix removes the assumption instead of correcting it. Headroom over the
 * per-article cost is a count of articles and needs no daily rate at all, so
 * there is nothing left in it for a run rate to be wrong about. That is the
 * claim this file holds: the printed figure equals `(cap - bytes) / cost`, and
 * no number of runs a day can move it.
 *
 * `console-site-size.spec.ts` owns the per-article cost the runway divides by.
 */

/** The tree the site was built from. The suite builds from the canaries. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

/** What the alarm is set to matters to `site-weight`, never to this figure. */
const ALARM = 800 * 1024 * 1024;

interface Day {
	date: string;
	siteBytes: number;
	items: number;
}

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every published day the build read, oldest first.
 *
 * Read straight off the manifests rather than through `payload.ts`, so the
 * expected answer below is arrived at by a second path and not by running the
 * page's own arithmetic twice.
 */
function publishedDays(root: string): Day[] {
	const days: Day[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(join(root, year))) {
			for (const day of dirs(join(root, year, month))) {
				const at = join(root, year, month, day);
				if (!existsSync(join(at, 'run.json')) || !existsSync(join(at, 'digest.json'))) continue;
				const runs = (JSON.parse(readFileSync(join(at, 'run.json'), 'utf8')).runs ?? []) as {
					site_bytes?: number;
				}[];
				const items = (JSON.parse(readFileSync(join(at, 'digest.json'), 'utf8')).items ??
					[]) as unknown[];
				days.push({
					date: `${year}-${month}-${day}`,
					// The console reads the last run of the day, because the site is one
					// thing measured once per run.
					siteBytes: Number(runs.at(-1)?.site_bytes ?? 0) || 0,
					items: items.length
				});
			}
		}
	}
	return days.sort((a, b) => a.date.localeCompare(b.date));
}

function medianOf(values: number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** `(cap - bytes) / bytesPerItem`, stated here rather than imported. */
function remainingArticles(days: Day[]): number | null {
	const rates: number[] = [];
	for (let i = 1; i < days.length; i += 1) {
		if (days[i].items <= 0) continue;
		rates.push((days[i].siteBytes - days[i - 1].siteBytes) / days[i].items);
	}
	const cost = medianOf(rates);
	if (cost === null || cost <= 0) return null;
	return (PAGES_CAP_BYTES - days[days.length - 1].siteBytes) / cost;
}

/** Three significant figures, which is the precision the band prints at.
 *
 * The rate under the answer is a median whose spread is near a fifth of itself,
 * so the trailing digits of a six-figure count are noise (Rule #10).
 */
function threeFigures(value: number): number {
	if (value <= 0) return 0;
	const scale = 10 ** Math.max(0, Math.floor(Math.log10(value)) - 2);
	return Math.round(value / scale) * scale;
}

function summary(date: string, siteBytes: number, runs: number): RunSummary {
	return { date, runs, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}

async function hydrated(page: Page) {
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', /\d+/);
}

test('THE ORACLE: the band prints the articles the headroom buys', async ({ page }) => {
	const days = publishedDays(CANARY);
	expect(days.length, 'the build read fewer than two days, so nothing has a rate').toBeGreaterThan(
		1
	);
	const expected = remainingArticles(days);
	expect(expected, 'no day in the build grew the tree over an article it published').not.toBeNull();

	await page.goto('/console/');
	await hydrated(page);

	const sentence = page.locator('[data-band-size]');
	await expect(sentence).toHaveCount(1);
	const text = (await sentence.innerText()).trim();

	const printed = Number(
		/room for about ([\d,]+) more articles/.exec(text)?.[1]?.replace(/,/g, '')
	);
	expect(Number.isFinite(printed), `the band printed no article headroom: ${text}`).toBe(true);
	expect(printed, 'the band and the manifests disagree about the room left').toBe(
		threeFigures(expected as number)
	);

	// The defect, stated as the thing that may not come back. A daily article
	// rate is a quantity nothing here measures, and the one number that was
	// standing in for it - `run.safety_ceiling_per_run` - bounds a run.
	expect(text, 'the band is claiming a daily article rate again').not.toMatch(/articles a day/);
	expect(text, 'the band is printing a date it cannot derive').not.toMatch(/fills it in/);
});

test('no rate of runs a day can move the answer', () => {
	// One site, described twice: four days at one run a day, and the same four
	// days at three. `run.safety_ceiling_per_run` is 160 and bounds a RUN, so a
	// formula built on it prices the second day at 480 articles and the first at
	// 160 - and its answer moves by three. This one may not move at all, because
	// the site did not change.
	const dates = ['2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04'];
	const bytes = [1_000_000, 1_300_000, 1_600_000, 1_900_000];
	const used = bytes[bytes.length - 1];
	const items = new Map(dates.map((date) => [date, 100]));

	const once = dates.map((date, i) => summary(date, bytes[i], 1));
	const thrice = dates.map((date, i) => summary(date, bytes[i], 3));

	const a = siteRunway(used, siteCost(once, items).median, ALARM);
	const b = siteRunway(used, siteCost(thrice, items).median, ALARM);
	expect(a).not.toBeNull();
	expect(a?.toCap, 'the runway moved when only the run count did').toBe(b?.toCap);

	// 3,000 bytes an article, by construction, so the expected answer is a
	// division a reader can check.
	expect(Math.round(a?.toCap ?? 0)).toBe(Math.round((PAGES_CAP_BYTES - used) / 3000));

	// And what a per-day answer would have done with the same two fixtures,
	// written out so the difference is on the page rather than asserted in the
	// abstract.
	const CEILING = 160;
	const daysAtCeiling = (runsADay: number) =>
		(PAGES_CAP_BYTES - used) / (3000 * CEILING * runsADay);
	expect(daysAtCeiling(3)).toBeCloseTo(daysAtCeiling(1) / 3, 6);
});
