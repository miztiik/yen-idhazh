import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chartArm, coverageOf, type ArmThresholds, type GlanceDay } from '../src/lib/charts/glance';
import { targetGeometry } from '../src/lib/charts/targetbar';

/**
 * The chart arm is the only console section carrying a written decision rule in
 * its own prose, and until this row the page showed none of the three numbers
 * that rule is made of. Seven columns of daily counts asked the operator to
 * compute a fourteen-day median of a ratio in his head, twice, against two
 * constants that were not on the screen.
 *
 * So the oracle here is arithmetic, not appearance: the median the page prints
 * is recomputed from the fixture's own committed files over exactly the rule's
 * span, and the marker on each bar is recomputed from the geometry module. A
 * bar that draws a plausible fill against the wrong divisor looks perfectly
 * healthy, which is why it is the failure worth a test.
 */

const REPO = resolve(process.cwd(), '..');
const CANARY = join(REPO, 'backend', 'var', 'canary');

const CONFIG = JSON.parse(
	readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
) as {
	console?: {
		window_presets?: number[];
		default_window_days?: number;
		chart_arm_rule_days?: number;
		chart_arm_minutes_target?: number;
		chart_arm_coverage_pct?: number;
	};
};

const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;
const THRESHOLDS: ArmThresholds = {
	ruleDays: CONFIG.console?.chart_arm_rule_days ?? 14,
	minutesTarget: CONFIG.console?.chart_arm_minutes_target ?? 6,
	coveragePct: CONFIG.console?.chart_arm_coverage_pct ?? 5
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
		// would read as an arm that ran and reached nobody, and it would drag the
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
		const arm = chartArm(days, THRESHOLDS, WIDE);

		expect(arm.minutes).toBe(3);
		expect(arm.coverage).toBe(10);
		const mean = (2 + 3 + 40) / 3;
		expect(arm.minutes).toBeLessThan(mean);
	});

	test('an even count of days averages the middle pair', () => {
		const days = [4, 2, 8, 6].map((m, i) =>
			day(`2026-08-0${i + 1}`, { items: 10, published: 1, minutesPerChart: m })
		);
		expect(chartArm(days, THRESHOLDS, WIDE).minutes).toBe(5);
	});

	test('below the rule span nothing is measured, and the bars are empty', () => {
		const days = [
			day('2026-08-01', { items: 10, published: 5, minutesPerChart: 1 }),
			day('2026-08-02', { items: 10, published: 5, minutesPerChart: 1 })
		];
		const arm = chartArm(days, THRESHOLDS, NARROW);

		// A median of the wrong span is the same figure with a different meaning
		// and nothing on the page to say which one is being read.
		expect(arm.narrow).toBe(true);
		expect(arm.minutes).toBeNull();
		expect(arm.coverage).toBeNull();
		expect(arm.minutesMarks.empty).toBe(true);
		expect(arm.coverageMarks.empty).toBe(true);
		expect(arm.minutesTrend.empty).toBe(true);

		// And the same rows at the rule's own span do produce both figures, so the
		// assertions above are about the window and not about the fixture.
		const wide = chartArm(days, THRESHOLDS, WIDE);
		expect(wide.narrow).toBe(false);
		expect(wide.minutes).toBe(1);
		expect(wide.coverage).toBe(50);
	});

	test('the verdict names both figures and which side of each threshold they fell', () => {
		const inside = chartArm(
			[day('2026-08-01', { items: 10, published: 5, minutesPerChart: 1 })],
			THRESHOLDS,
			WIDE
		);
		expect(inside.verdict).toContain('1.0 minutes per visual');
		expect(inside.verdict).toContain('inside');
		expect(inside.verdict).toContain('50% of what it published');
		expect(inside.verdict).toContain('above');

		const outside = chartArm(
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
		const arm = chartArm([day('2026-08-01')], THRESHOLDS, WIDE);
		expect(arm.minutes).toBeNull();
		expect(arm.coverage).toBeNull();
		expect(arm.verdict).toContain('has no minutes on record');
		expect(arm.verdict).toContain('no day published anything to put a visual on');
		// The second clause has no subject of its own, so the first has to hand it
		// one whichever branch it took.
		expect(arm.verdict.startsWith('The median day')).toBe(true);
	});

	test('each trend carries one point per measured day, oldest first', () => {
		// Handed over newest-first, which is the order the daily table reads in.
		const days = [
			day('2026-08-03', { items: 10, published: 3, minutesPerChart: 9 }),
			day('2026-08-02', { items: 10, published: 2, minutesPerChart: 5 }),
			day('2026-08-01', { items: 10, published: 1, minutesPerChart: 1 })
		];
		const arm = chartArm(days, THRESHOLDS, WIDE);

		expect(arm.minutesDays).toBe(3);
		expect(arm.coverageDays).toBe(3);
		expect(arm.minutesTrend.values).toEqual([1, 5, 9]);
		expect(arm.coverageTrend.values).toEqual([10, 20, 30]);
		// Rising, because the oldest day is the smallest. A line drawn from the
		// table's own order would be falling, and it would look like a fix.
		expect(arm.minutesTrend.rising).toBe(true);

		// One measured day is a dot, and a dot with a direction beside it is a lie.
		const single = chartArm([days[0]], THRESHOLDS, WIDE);
		expect(single.minutesDays).toBe(1);
		expect(single.minutesTrend.empty).toBe(true);
	});

	test('the marker sits at the threshold on both bars, and the senses are opposite', () => {
		const days = [day('2026-08-01', { items: 100, published: 20, minutesPerChart: 9 })];
		const arm = chartArm(days, THRESHOLDS, WIDE);

		// Recomputed rather than read back: a bar whose fill and marker come from
		// one wrong divisor is self-consistent and still wrong.
		expect(arm.minutesMarks.markerFraction).toBeCloseTo(
			targetGeometry(9, THRESHOLDS.minutesTarget, 'lower-is-better').markerFraction,
			9
		);
		expect(arm.coverageMarks.markerFraction).toBeCloseTo(
			targetGeometry(20, THRESHOLDS.coveragePct, 'higher-is-better').markerFraction,
			9
		);
		// Nine minutes against a six-minute limit is past it. Twenty percent
		// against a five percent floor is not. Same numbers, opposite senses.
		expect(arm.minutesMarks.band).toBe('past');
		expect(arm.coverageMarks.band).toBe('good');
	});
});

/** Every day the canary committed, as the console reads it.
 *
 * Read from `run.json` and `digest.json` rather than typed, so the oracle is
 * "the page prints what the fixture says" and not "the page prints what it
 * printed last week".
 */
function fixtureDays(): GlanceDay[] {
	const digest = join(CANARY, 'digest');
	const days: GlanceDay[] = [];
	for (const year of dirs(digest)) {
		for (const month of dirs(join(digest, year))) {
			for (const dayName of dirs(join(digest, year, month))) {
				const at = join(digest, year, month, dayName);
				const runs = (
					JSON.parse(readFileSync(join(at, 'run.json'), 'utf8')) as {
						runs: { route_ms?: number | null }[];
					}
				).runs;
				const items = (
					JSON.parse(readFileSync(join(at, 'digest.json'), 'utf8')) as {
						items: { visual?: { kind: string; state: string } | null }[];
					}
				).items;
				const timed = runs
					.map((run) => run.route_ms)
					.filter((ms): ms is number => typeof ms === 'number');
				const minutes = timed.length === 0 ? null : timed.reduce((a, b) => a + b, 0) / 60_000;
				const published = items.filter(
					(item) => item.visual?.kind === 'chart' && item.visual.state === 'rendered'
				).length;
				days.push({
					date: `${year}-${month}-${dayName}`,
					published,
					items: items.length,
					minutesPerChart: minutes === null || published === 0 ? null : minutes / published
				});
			}
		}
	}
	return days.sort((a, b) => a.date.localeCompare(b.date));
}

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** The window the page holds, cut to the rule's own span, ending on the newest
 * day the fixture committed. The page anchors on the newest committed day and
 * never on the build clock, so this has to as well. */
function ruleWindow(days: GlanceDay[], span: number): GlanceDay[] {
	const newest = days.at(-1)?.date ?? '';
	const start = new Date(`${newest}T00:00:00Z`);
	start.setUTCDate(start.getUTCDate() - (span - 1));
	const from = start.toISOString().slice(0, 10);
	return days.filter((entry) => entry.date >= from && entry.date <= newest);
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
	test('THE ORACLE: the printed median is the median of the fixture over the rule span', async ({
		page
	}) => {
		await page.goto('/console/');
		await hydrated(page);
		await setWindow(page, WIDE);

		const days = fixtureDays();
		expect(days.length, 'the fixture committed no day, so this asserts nothing').toBeGreaterThan(0);
		const expected = chartArm(ruleWindow(days, WIDE), THRESHOLDS, WIDE);
		expect(expected.minutes, 'no day in the fixture was timed').not.toBeNull();
		expect(expected.coverage, 'no day in the fixture published anything').not.toBeNull();

		const minutes = page.locator('[data-arm-figure="minutes"] [data-target-cell="value"]');
		const coverage = page.locator('[data-arm-figure="coverage"] [data-target-cell="value"]');
		await expect(minutes).toHaveText((expected.minutes as number).toFixed(1));
		await expect(coverage).toHaveText(`${Math.round(expected.coverage as number)}%`);

		// And the verdict says the same two things the bars do, so the sentence and
		// the picture cannot drift apart.
		await expect(page.locator('[data-charts-verdict]')).toHaveText(expected.verdict);
	});

	test('the marker on each bar sits where the geometry puts it', async ({ page }) => {
		await page.goto('/console/');
		await hydrated(page);
		await setWindow(page, WIDE);

		const expected = chartArm(ruleWindow(fixtureDays(), WIDE), THRESHOLDS, WIDE);
		const measured = await page
			.locator('[data-arm-figure] [data-target-cell="marker"]')
			.evaluateAll((nodes) =>
				nodes.map((node) => {
					const track = node.parentElement as HTMLElement;
					const box = track.getBoundingClientRect();
					// The marker is 2px wide and pulled back 1px, so its centre is the
					// threshold. Reading its left edge would report a bar 1px early.
					return (node.getBoundingClientRect().left + 1 - box.left) / box.width;
				})
			);

		expect(measured.length, 'the section drew fewer than two target bars').toBe(2);
		expect(
			Math.abs(measured[0] - expected.minutesMarks.markerFraction),
			'the minutes marker is off its threshold'
		).toBeLessThan(0.003);
		expect(
			Math.abs(measured[1] - expected.coverageMarks.markerFraction),
			'the coverage marker is off its threshold'
		).toBeLessThan(0.003);
	});

	test('a window under the rule span prints the notice and no median at all', async ({ page }) => {
		await page.goto('/console/');
		await hydrated(page);

		const section = page.locator('[data-windowed="chart-arm"]');
		await setWindow(page, WIDE);
		await expect(section.locator('[data-window-too-narrow="chart-arm"]')).toHaveCount(0);
		await expect(section.locator('[data-target-bar]')).toHaveCount(2);

		await setWindow(page, NARROW);
		// The exact sentence, because a median of the wrong span is the same figure
		// with a different meaning and nothing on the page to say which.
		await expect(section.locator('[data-window-too-narrow="chart-arm"]')).toHaveText(
			`The rule reads ${THRESHOLDS.ruleDays} days. Widen the window to see it.`
		);
		await expect(section.locator('[data-target-bar]')).toHaveCount(0);
		await expect(section.locator('[data-charts-verdict]')).toHaveCount(0);
	});

	test('the section states its own rule, in the numbers config holds', async ({ page }) => {
		await page.goto('/console/');

		const section = page.locator('[data-windowed="chart-arm"]');
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
		await expect(page.locator('[data-arm-figure] [data-sparkline]')).toHaveCount(2);
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
		await expect(page.locator('[data-arm-figure] [data-target-cell="track"]')).toHaveCount(2);
		await expect(page.locator('[data-charts-toggle]')).toBeVisible();
		await context.close();
	});
});
