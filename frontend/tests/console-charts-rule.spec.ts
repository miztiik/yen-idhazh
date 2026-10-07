import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chartRule, coverageOf, type ChartThresholds, type GlanceDay } from '../src/lib/charts/glance';
import { targetGeometry } from '../src/lib/charts/targetbar';

/**
 * Chart drawing is the only console section carrying a written decision rule in
 * its own prose, and until this row the page showed none of the three numbers
 * that rule is made of. Seven columns of daily counts asked the operator to
 * compute a fourteen-day median of a ratio in his head, twice, against two
 * constants that were not on the screen.
 *
 * So the oracle here is arithmetic, not appearance. The rule's medians and the
 * marker on each bar are worked out over days written below, with no browser.
 * On the page, the two printed figures are the medians of the rows the daily
 * table prints over the rule's span, and each marker sits where its own bar
 * places it; nothing there is worked out from what the site was built from. A
 * bar that draws a plausible fill against the wrong divisor looks perfectly
 * healthy, which is why it is the failure worth a test.
 */

const REPO = resolve(process.cwd(), '..');

const CONFIG = JSON.parse(
	readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
) as {
	console?: {
		window_presets?: number[];
		default_window_days?: number;
		chart_rule_days?: number;
		chart_minutes_target?: number;
		chart_coverage_pct?: number;
	};
};

const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;
const THRESHOLDS: ChartThresholds = {
	ruleDays: CONFIG.console?.chart_rule_days ?? 14,
	minutesTarget: CONFIG.console?.chart_minutes_target ?? 6,
	coveragePct: CONFIG.console?.chart_coverage_pct ?? 5
};

/** A window narrower than the rule, and one at least as wide, from the presets
 * the config actually offers. Typed constants here would go stale the day the
 * preset list moves, and go stale silently. */
const NARROW = PRESETS.filter((days) => days < THRESHOLDS.ruleDays).at(-1) as number;
const WIDE = PRESETS.filter((days) => days >= THRESHOLDS.ruleDays)[0];

function day(date: string, over: Partial<GlanceDay> = {}): GlanceDay {
	return { date, published: 0, items: 0, minutesPerChart: null, ...over };
}

test.describe('the arithmetic behind the two bars', () => {
	test('a share of nothing is an absence, never zero percent', () => {
		// A day that published no article did not fail to put a visual on one. Zero
		// would read as chart drawing that ran and reached nobody, and it would drag the
		// median of every quiet week to the floor.
		expect(coverageOf(day('2026-08-01'))).toBeNull();
		expect(coverageOf(day('2026-08-02', { items: 8, published: 1 }))).toBeCloseTo(12.5, 6);
		expect(coverageOf(day('2026-08-03', { items: 4, published: 4 }))).toBe(100);
	});

	test('the median is the middle day, so one ruinous day cannot decide the rule', () => {
		const days = [
			day('2026-08-01', { items: 10, published: 1, minutesPerChart: 2 }),
			day('2026-08-02', { items: 10, published: 1, minutesPerChart: 3 }),
			// The pathological day. A mean would put the figure past the target.
			day('2026-08-03', { items: 10, published: 1, minutesPerChart: 40 })
		];
		const rule = chartRule(days, THRESHOLDS, WIDE);

		expect(rule.minutes).toBe(3);
		expect(rule.coverage).toBe(10);
		const mean = (2 + 3 + 40) / 3;
		expect(rule.minutes).toBeLessThan(mean);
	});

	test('an even count of days averages the middle pair', () => {
		const days = [4, 2, 8, 6].map((m, i) =>
			day(`2026-08-0${i + 1}`, { items: 10, published: 1, minutesPerChart: m })
		);
		expect(chartRule(days, THRESHOLDS, WIDE).minutes).toBe(5);
	});

	test('below the rule span nothing is measured, and the bars are empty', () => {
		const days = [
			day('2026-08-01', { items: 10, published: 5, minutesPerChart: 1 }),
			day('2026-08-02', { items: 10, published: 5, minutesPerChart: 1 })
		];
		const rule = chartRule(days, THRESHOLDS, NARROW);

		// A median of the wrong span is the same figure with a different meaning
		// and nothing on the page to say which one is being read.
		expect(rule.narrow).toBe(true);
		expect(rule.minutes).toBeNull();
		expect(rule.coverage).toBeNull();
		expect(rule.minutesMarks.empty).toBe(true);
		expect(rule.coverageMarks.empty).toBe(true);
		expect(rule.minutesTrend.empty).toBe(true);

		// And the same rows at the rule's own span do produce both figures, so the
		// assertions above are about the window and not about the fixture.
		const wide = chartRule(days, THRESHOLDS, WIDE);
		expect(wide.narrow).toBe(false);
		expect(wide.minutes).toBe(1);
		expect(wide.coverage).toBe(50);
	});

	test('the verdict names both figures and which side of each threshold they fell', () => {
		const inside = chartRule(
			[day('2026-08-01', { items: 10, published: 5, minutesPerChart: 1 })],
			THRESHOLDS,
			WIDE
		);
		expect(inside.verdict).toContain('1.0 minutes per visual');
		expect(inside.verdict).toContain('inside');
		expect(inside.verdict).toContain('50% of what it published');
		expect(inside.verdict).toContain('above');

		const outside = chartRule(
			[day('2026-08-01', { items: 100, published: 1, minutesPerChart: 40 })],
			THRESHOLDS,
			WIDE
		);
		expect(outside.verdict).toContain('past');
		expect(outside.verdict).toContain('below');
		// One sentence, both halves. A verdict that stopped at the first figure
		// would answer half the rule. Counted on sentence-ending stops, because
		// `40.0` carries a full stop that ends nothing.
		expect((outside.verdict.match(/\.(\s|$)/g) ?? []).length).toBe(1);
	});

	test('a window with nothing in it says so rather than printing a zero', () => {
		const rule = chartRule([day('2026-08-01')], THRESHOLDS, WIDE);
		expect(rule.minutes).toBeNull();
		expect(rule.coverage).toBeNull();
		expect(rule.verdict).toContain('has no minutes on record');
		expect(rule.verdict).toContain('no day published anything to put a visual on');
		// The second clause has no subject of its own, so the first has to hand it
		// one whichever branch it took.
		expect(rule.verdict.startsWith('The median day')).toBe(true);
	});

	test('each trend carries one point per measured day, oldest first', () => {
		// Handed over newest-first, which is the order the daily table reads in.
		const days = [
			day('2026-08-03', { items: 10, published: 3, minutesPerChart: 9 }),
			day('2026-08-02', { items: 10, published: 2, minutesPerChart: 5 }),
			day('2026-08-01', { items: 10, published: 1, minutesPerChart: 1 })
		];
		const rule = chartRule(days, THRESHOLDS, WIDE);

		expect(rule.minutesDays).toBe(3);
		expect(rule.coverageDays).toBe(3);
		expect(rule.minutesTrend.values).toEqual([1, 5, 9]);
		expect(rule.coverageTrend.values).toEqual([10, 20, 30]);
		// Rising, because the oldest day is the smallest. A line drawn from the
		// table's own order would be falling, and it would look like a fix.
		expect(rule.minutesTrend.rising).toBe(true);

		// One measured day is a dot, and a dot with a direction beside it is a lie.
		const single = chartRule([days[0]], THRESHOLDS, WIDE);
		expect(single.minutesDays).toBe(1);
		expect(single.minutesTrend.empty).toBe(true);
	});

	test('the marker sits at the threshold on both bars, and the senses are opposite', () => {
		const days = [day('2026-08-01', { items: 100, published: 20, minutesPerChart: 9 })];
		const rule = chartRule(days, THRESHOLDS, WIDE);

		// Recomputed rather than read back: a bar whose fill and marker come from
		// one wrong divisor is self-consistent and still wrong.
		expect(rule.minutesMarks.markerFraction).toBeCloseTo(
			targetGeometry(9, THRESHOLDS.minutesTarget, 'lower-is-better').markerFraction,
			9
		);
		expect(rule.coverageMarks.markerFraction).toBeCloseTo(
			targetGeometry(20, THRESHOLDS.coveragePct, 'higher-is-better').markerFraction,
			9
		);
		// Nine minutes against a six-minute limit is past it. Twenty percent
		// against a five percent floor is not. Same numbers, opposite senses.
		expect(rule.minutesMarks.band).toBe('past');
		expect(rule.coverageMarks.band).toBe('good');
	});
});

/** The rows of the daily table, as the page prints them: the same days the rule
 * reads, because both follow the open window. */
async function dailyRows(page: Page) {
	return page.locator('[data-chart-day]').evaluateAll((rows) =>
		rows.map((row) => {
			const cell = (name: string) =>
				(row.querySelector(`[data-charts-cell="${name}"]`)?.textContent ?? '').trim();
			return {
				date: row.getAttribute('data-chart-day') ?? '',
				published: Number(cell('published')),
				items: Number(cell('items')),
				perChart: cell('per-chart')
			};
		})
	);
}

/** The middle of a list of numbers, or null where there is none. */
function middle(values: number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	const at = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[at] : (sorted[at - 1] + sorted[at]) / 2;
}

async function hydrated(page: Page) {
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** The disclosure, driven from inside the page. The integrated browser is a
 * hidden page, so a click waits for an element to be stable and never returns. */
async function setDaily(page: Page, open: boolean) {
	await page.locator('[data-charts="daily"]').evaluate((node, wanted) => {
		(node as HTMLDetailsElement).open = wanted;
	}, open);
}

test.describe('the section on the page', () => {
	test('THE ORACLE: the printed median is the median of the days the table prints over the rule span', async ({
		page
	}) => {
		await page.goto('/console/');
		await hydrated(page);
		await setWindow(page, WIDE);

		// The rule and the table read the same days, so the two figures are the
		// medians of the table's own rows: minutes per visual over the days that
		// timed one, and the share with a visual over the days that published
		// anything. Each per-day minute is printed to one decimal, so a median of two
		// printed values can sit up to 0.1 from the median of the values themselves.
		const rows = await dailyRows(page);
		expect(rows.length, 'the rule span holds no day').toBeGreaterThan(0);
		const minutes = middle(rows.filter((row) => row.perChart !== '-').map((row) => Number(row.perChart)));
		const coverage = middle(
			rows.filter((row) => row.items > 0).map((row) => (row.published / row.items) * 100)
		);

		const printedMinutes = (
			await page.locator('[data-rule-figure="minutes"] [data-target-cell="value"]').innerText()
		).trim();
		const printedCoverage = (
			await page.locator('[data-rule-figure="coverage"] [data-target-cell="value"]').innerText()
		).trim();
		if (minutes === null) expect(printedMinutes).toBe('-');
		else {
			expect(printedMinutes).toMatch(/^\d+\.\d$/);
			expect(Math.abs(Number(printedMinutes) - minutes), 'the minutes are not the table median').toBeLessThanOrEqual(
				0.1 + 1e-9
			);
		}
		expect(printedCoverage, 'the share is not the table median').toBe(
			coverage === null ? '-' : `${Math.round(coverage)}%`
		);

		// And the verdict says the same two things the bars do, so the sentence and
		// the picture cannot drift apart.
		const verdict = (await page.locator('[data-charts-verdict]').innerText()).trim();
		if (minutes !== null) expect(verdict).toContain(`${printedMinutes} minutes per visual`);
		if (coverage !== null) expect(verdict).toContain(`${printedCoverage} of what it published`);
	});

	test('the marker on each bar sits where the bar says it does', async ({ page }) => {
		await page.goto('/console/');
		await hydrated(page);
		await setWindow(page, WIDE);

		// The marker is placed by its own `inset-inline-start`, which carries the
		// geometry's marker fraction as a percent. What is measured here is that the
		// drawing honours it: the marker is 2px wide and pulled back 1px, so its
		// centre is the threshold, and reading its left edge would report a bar 1px
		// early. Where the geometry puts the marker is tested above with no browser.
		const placed = await page
			.locator('[data-rule-figure] [data-target-cell="marker"]')
			.evaluateAll((nodes) =>
				nodes.map((node) => {
					const track = node.parentElement as HTMLElement;
					const box = track.getBoundingClientRect();
					return {
						declared: parseFloat((node as HTMLElement).style.insetInlineStart) / 100,
						measured: (node.getBoundingClientRect().left + 1 - box.left) / box.width
					};
				})
			);

		expect(placed.length, 'the section drew fewer than two target bars').toBe(2);
		for (const [index, marker] of placed.entries()) {
			expect(Number.isFinite(marker.declared), `marker ${index} declares no place`).toBe(true);
			expect(
				Math.abs(marker.measured - marker.declared),
				`marker ${index} is off the place its bar declares`
			).toBeLessThan(0.003);
		}
	});

	test('a window under the rule span prints the notice and no median at all', async ({ page }) => {
		await page.goto('/console/');
		await hydrated(page);

		const section = page.locator('[data-windowed="chart-drawing"]');
		await setWindow(page, WIDE);
		await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveCount(0);
		await expect(section.locator('[data-target-bar]')).toHaveCount(2);

		await setWindow(page, NARROW);
		// The exact sentence, because a median of the wrong span is the same figure
		// with a different meaning and nothing on the page to say which.
		await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveText(
			`The rule reads ${THRESHOLDS.ruleDays} days. Widen the window to see it.`
		);
		await expect(section.locator('[data-target-bar]')).toHaveCount(0);
		await expect(section.locator('[data-charts-verdict]')).toHaveCount(0);
	});

	test('the section states its own rule, in the numbers config holds', async ({ page }) => {
		await page.goto('/console/');

		const section = page.locator('[data-windowed="chart-drawing"]');
		await expect(section).toContainText(`${THRESHOLDS.ruleDays} days`);
		await expect(section).toContainText(`${THRESHOLDS.minutesTarget} minutes per published visual`);
		await expect(section).toContainText(`${THRESHOLDS.coveragePct}% of the items`);
	});

	test('each figure carries a trend under it', async ({ page }) => {
		await page.goto('/console/');
		await hydrated(page);
		await setWindow(page, WIDE);

		// Two figures, two trends. The canary times exactly one day, so both draw
		// the empty shape - a blank of the same size, never a dash, so a pair
		// where only one has history does not stagger. What the line does over
		// several days is proved above without a browser, which is where a rule
		// the one-day fixture cannot reach belongs.
		await expect(page.locator('[data-rule-figure] [data-sparkline]')).toHaveCount(2);
	});

	test('the daily rows are on demand, and they open and close', async ({ page }) => {
		await page.goto('/console/');

		const daily = page.locator('[data-charts="daily"]');
		const table = page.locator('[data-charts="table"]');

		// Shut on arrival. Seven columns of counts are the answer to a question
		// nobody has yet asked, and they used to be the first thing here.
		await expect(daily).toHaveJSProperty('open', false);
		await expect(table).toBeHidden();
		await expect(page.locator('[data-charts-toggle]')).toBeVisible();

		await setDaily(page, true);
		await expect(table).toBeVisible();
		await expect(page.locator('[data-chart-day]').first()).toBeVisible();

		await setDaily(page, false);
		await expect(table).toBeHidden();
	});

	test('the rows the section stopped leading with are still in the table', async ({ page }) => {
		await page.goto('/console/');
		await setDaily(page, true);

		// Reached, asked and drafted left the top level for the flow diagram, and
		// raw minutes left because a numerator is not a decision. All four
		// are one control away rather than gone.
		for (const cell of ['reached', 'asked', 'drafted', 'items', 'minutes']) {
			await expect(
				page.locator(`[data-charts-cell="${cell}"]`).first(),
				`${cell} left the page instead of moving behind the control`
			).toBeVisible();
		}
	});

	test('the page renders the section with no script at all', async ({ browser }) => {
		const context = await browser.newContext({ javaScriptEnabled: false });
		const page = await context.newPage();
		await page.goto('/console/');

		// Every bar and both trend shapes are markup, so the prerendered document
		// is already finished. A native disclosure is why the rows stay reachable.
		await expect(page.locator('[data-charts-verdict]')).toBeVisible();
		await expect(page.locator('[data-rule-figure] [data-target-cell="track"]')).toHaveCount(2);
		await expect(page.locator('[data-charts-toggle]')).toBeVisible();
		await context.close();
	});
});
