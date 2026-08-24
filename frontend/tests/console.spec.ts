import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { axisLabels, spanLabel } from '../src/lib/charts/run-history';

/**
 * The console says whether the runs worked and which feeds are broken.
 *
 * It runs against the canary build, whose fixtures carry one run of each colour
 * and one feed of each kind the page has to tell apart. The canary build writes
 * the item-health ledger because the console reads timing medians from it. The
 * fixture still has no score ledger, which proves the page keeps rendering when
 * one data source is missing.
 *
 * See `backend/utilities/build_canary_day.py` for the fixture.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** The day the canary build publishes, discovered rather than hardcoded.
 *
 * A hardcoded date passes on an empty 404 page the moment the fixture moves.
 */
function publishedDay(): string {
	const root = join(CANARY, 'digest');
	const year = dirs(root).at(-1) as string;
	const month = dirs(join(root, year)).at(-1) as string;
	const day = dirs(join(root, year, month)).at(-1) as string;
	return `${year}-${month}-${day}`;
}

const DAY = publishedDay();

/** The cap read from the knob, so the test cannot drift from the config. */
const FAILURE_LIST_MAX = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
	) as { console?: { failure_list_max?: number } }
).console?.failure_list_max ?? 25;

/** Every day the fixture wrote a manifest for, oldest first, with its run count.
 *
 * The strip is asserted against this rather than a number: a fixture that grows
 * a day must not need the test renumbered, and a test that is renumbered by
 * hand gets renumbered wrong.
 */
function manifestDays(): { date: string; runs: number }[] {
	const root = join(CANARY, 'digest');
	const found: { date: string; runs: number }[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(join(root, year))) {
			for (const day of dirs(join(root, year, month))) {
				const raw = readFileSync(join(root, year, month, day, 'run.json'), 'utf8');
				found.push({
					date: `${year}-${month}-${day}`,
					runs: (JSON.parse(raw) as { runs: unknown[] }).runs.length
				});
			}
		}
	}
	return found.sort((a, b) => a.date.localeCompare(b.date));
}

/** A run of consecutive ISO days, read in UTC so the suite cannot drift west. */
function days(start: string, count: number): string[] {
	const first = new Date(`${start}T00:00:00Z`).getTime();
	return Array.from({ length: count }, (_, index) =>
		new Date(first + index * 86_400_000).toISOString().slice(0, 10)
	);
}

interface Box {
	x: number;
	y: number;
	width: number;
	height: number;
	right: number;
	bottom: number;
}

/** `DOMRect` does not survive the wire, so only the numbers cross it. */
const TO_BOX = (nodes: Element[]): Box[] =>
	nodes.map((node) => {
		const rect = node.getBoundingClientRect();
		return {
			x: rect.x,
			y: rect.y,
			width: rect.width,
			height: rect.height,
			right: rect.right,
			bottom: rect.bottom
		};
	});

function stripMetrics(page: Page) {
	return page
		.locator('[data-run-history]')
		.evaluate((node) => ({
			scrollLeft: node.scrollLeft,
			scrollWidth: node.scrollWidth,
			clientWidth: node.clientWidth
		}));
}

/** How many runs the fixture manifest records for that day. */
function runCount(): number {
	const [year, month, day] = DAY.split('-');
	const raw = readFileSync(join(CANARY, 'digest', year, month, day, 'run.json'), 'utf8');
	return (JSON.parse(raw) as { runs: unknown[] }).runs.length;
}

/** How many days a telemetry viewport window covers, ends included. */
function span(start: string | null, end: string | null): number {
	if (!start || !end) return 0;
	return (
		(new Date(`${end}T00:00:00Z`).getTime() - new Date(`${start}T00:00:00Z`).getTime()) /
			86_400_000 +
		1
	);
}

/** Every request the page made that came back missing. */
function watchFor404s(page: Page): string[] {
	const missing: string[] = [];
	page.on('response', (response) => {
		if (response.status() === 404) missing.push(response.url());
	});
	return missing;
}

test('one day gets a full date, and a short run gets one span', () => {
	expect(axisLabels([])).toEqual([]);
	expect(axisLabels(['2026-08-20'])).toEqual([{ column: 1, text: '20 Aug 2026', align: 'end' }]);

	// Two to six days cannot carry a cadence, so the whole span is said once.
	expect(spanLabel('2026-08-18', '2026-08-20')).toBe('18-20 Aug 2026');
	expect(spanLabel('2026-07-30', '2026-08-02')).toBe('30 Jul - 2 Aug 2026');
	expect(spanLabel('2025-12-30', '2026-01-02')).toBe('30 Dec 2025 - 2 Jan 2026');
	expect(axisLabels(days('2026-08-15', 4))).toEqual([
		{ column: 4, text: '15-18 Aug 2026', align: 'end' }
	]);
});

test('a longer run carries both ends and a weekly cadence between them', () => {
	const twenty = axisLabels(days('2026-08-01', 20));

	// Column 15 would land five columns from the newest end, where the two texts
	// would share pixels. It is dropped rather than crowded.
	expect(twenty.map((label) => label.column)).toEqual([1, 8, 20]);
	expect(twenty.map((label) => label.text)).toEqual(['1 Aug 2026', '8 Aug', '20 Aug 2026']);
	expect(twenty.map((label) => label.align)).toEqual(['start', 'centre', 'end']);

	expect(axisLabels(days('2026-08-01', 30)).map((label) => label.column)).toEqual([1, 8, 15, 22, 30]);
});

test('the year is stated on the first label that changes it, and not again', () => {
	const across = axisLabels(days('2025-12-20', 30));

	expect(across.map((label) => label.text)).toEqual([
		'20 Dec 2025',
		'27 Dec',
		'3 Jan 2026',
		'10 Jan',
		'18 Jan 2026'
	]);
});

test('the strip reads oldest to newest, left to right', async ({ page }) => {
	await page.goto('/console/');

	const columns = page.locator('[data-day]');
	const dates = await columns.evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-day') ?? '')
	);
	expect(dates).toEqual(manifestDays().map((day) => day.date));

	// Chronology a reader can see, not only one the DOM asserts.
	const boxes = await columns.evaluateAll(TO_BOX);
	for (let index = 1; index < boxes.length; index += 1) {
		expect(boxes[index].x).toBeGreaterThan(boxes[index - 1].x);
	}
});

test('every recorded run gets a square, and nothing else does', async ({ page }) => {
	await page.goto('/console/');

	const expected = manifestDays();
	await expect(page.locator('[data-day]')).toHaveCount(expected.length);
	await expect(page.locator('[data-health]')).toHaveCount(
		expected.reduce((total, day) => total + day.runs, 0)
	);

	// A scheduled run that never wrote a manifest has left no evidence, so the
	// strip cannot draw a slot for it without inventing one.
	for (const day of expected) {
		await expect(page.locator(`[data-day="${day.date}"] [data-health]`)).toHaveCount(day.runs);
	}
});

test('runs rise from a shared baseline, on a 16px day track', async ({ page }) => {
	await page.goto('/console/');

	const stack = await page.locator(`[data-day="${DAY}"] [data-health]`).evaluateAll(TO_BOX);
	expect(stack.length).toBe(runCount());

	// Run 1 is first in the DOM so it is read first, and lowest on screen so the
	// day reads upward from the ground like every other time series.
	const lowest = Math.max(...stack.map((box) => box.y));
	expect(stack[0].y).toBe(lowest);

	for (const box of stack) {
		expect(box.width).toBe(16);
		expect(box.height).toBe(16);
	}
	for (let index = 1; index < stack.length; index += 1) {
		expect(stack[index - 1].y - stack[index].bottom).toBeCloseTo(4, 1);
	}

	// Every day's run 1 sits on the same line, or the strip is a scatter.
	const baselines = await page
		.locator('[data-day]')
		.evaluateAll((nodes) =>
			nodes.map((node) => node.querySelector('[data-health]')!.getBoundingClientRect().bottom)
		);
	for (const bottom of baselines) expect(bottom).toBeCloseTo(baselines[0], 1);

	const columns = await page.locator('[data-day]').evaluateAll(TO_BOX);
	for (let index = 1; index < columns.length; index += 1) {
		expect(columns[index].x - columns[index - 1].right).toBeCloseTo(4, 1);
	}
});

test('no two date labels print on top of each other', async ({ page }) => {
	await page.goto('/console/');

	const labels = await page.locator('[data-axis-label]').evaluateAll(TO_BOX);
	expect(labels.length).toBeGreaterThan(1);

	const ordered = [...labels].sort((a, b) => a.x - b.x);
	for (let index = 1; index < ordered.length; index += 1) {
		expect(ordered[index].x).toBeGreaterThan(ordered[index - 1].right);
	}
});

test('a short history sits at the newest edge, never adrift on the left', async ({ page }) => {
	await page.goto('/console/');

	const [strip] = await page.locator('[data-run-history]').evaluateAll(TO_BOX);
	const columns = await page.locator('[data-day]').evaluateAll(TO_BOX);

	expect(Math.abs(strip.right - columns[columns.length - 1].right)).toBeLessThan(2);
	expect(columns[0].x - strip.x).toBeGreaterThan(1);
});

test('on a phone the strip scrolls, and opens on the newest run', async ({ page }) => {
	await page.setViewportSize({ width: 360, height: 720 });
	await page.goto('/console/');

	// More history than a phone is wide. The operator reaches the rest by
	// scrolling, and starts where the newest run is.
	await expect
		.poll(async () => {
			const metrics = await stripMetrics(page);
			return metrics.scrollWidth > metrics.clientWidth;
		})
		.toBe(true);
	await expect
		.poll(async () => {
			const metrics = await stripMetrics(page);
			return Math.abs(metrics.scrollWidth - metrics.clientWidth - metrics.scrollLeft) < 1;
		})
		.toBe(true);

	const [strip] = await page.locator('[data-run-history]').evaluateAll(TO_BOX);
	const [newest] = await page.locator(`[data-day="${DAY}"]`).evaluateAll(TO_BOX);
	expect(newest.x).toBeGreaterThanOrEqual(strip.x - 1);
	expect(newest.right).toBeLessThanOrEqual(strip.right + 1);

	const opened = (await stripMetrics(page)).scrollLeft;
	await page.locator('[data-run-history]').focus();
	await page.keyboard.press('ArrowLeft');
	await expect.poll(async () => (await stripMetrics(page)).scrollLeft).toBeLessThan(opened);
});

test('the grid draws one square per run, coloured by what the run did', async ({ page }) => {
	await page.goto('/console/');

	const column = page.locator(`[data-day="${DAY}"]`);
	await expect(column).toHaveCount(1);
	await expect(column.locator('[data-health]')).toHaveCount(runCount());

	// The fixture is authored as one run of each colour: it published
	// everything, then found nothing new, then broke.
	await expect(column.locator('[data-health="green"]')).toHaveCount(1);
	await expect(column.locator('[data-health="amber"]')).toHaveCount(1);
	await expect(column.locator('[data-health="red"]')).toHaveCount(1);
});

test('a square says what happened without a mouse', async ({ page }) => {
	await page.goto('/console/');

	// The colour alone is not the answer. Anyone who cannot see the difference
	// between amber and red still has to be able to read the run.
	const first = page.locator(`[data-day="${DAY}"] [data-health]`).first();
	await expect(first).toHaveAttribute('aria-label', new RegExp(`^${DAY} run 1,`));
	await expect(first).toHaveAttribute('title', /succeeded/);
});

test('a feed that answered with nothing is named, and a polite refusal is not', async ({ page }) => {
	await page.goto('/console/');

	// Answered with zero items. It cost the digest the same articles a refusal would.
	await expect(page.locator('[data-feed="canary-empty"]')).toHaveCount(1);
	// Permanently gone.
	await expect(page.locator('[data-feed="canary-gone"]')).toHaveCount(1);

	// Said no in robots.txt, every single run. Honouring it is the pipeline
	// working, so it is not a failure and the operator is not asked to look.
	await expect(page.locator('[data-feed="canary-polite"]')).toHaveCount(0);
	// Answered every run. A healthy feed is never listed.
	await expect(page.locator('[data-feed="canary-steady"]')).toHaveCount(0);
	// Never asked, so it can neither pass nor fail.
	await expect(page.locator('[data-feed="canary-quiet"]')).toHaveCount(0);
});

test('a feed past the quarantine count is marked rested', async ({ page }) => {
	await page.goto('/console/');

	const flaky = page.locator('[data-feed="canary-flaky"]');
	await expect(flaky.locator('[data-rested]')).toHaveCount(1);
	await expect(page.locator('[data-feed="canary-gone"] [data-rested]')).toHaveCount(0);

	// Worst first. An operator reading top-down reads the biggest problem first.
	const named = await page
		.locator('[data-feed]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-feed')));
	expect(named).toEqual(['canary-flaky', 'canary-empty', 'canary-gone']);
});

test('stage medians come from item health, not the score ledger', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.getByText('Median seconds per item, by stage')).toBeVisible();
	// The legend, not the axis: the largest median is printed in both places, so
	// an unscoped match is ambiguous the moment one stage is the slowest.
	await expect(page.locator('[data-stage="fetch"]')).toContainText('200 ms');
	await expect(page.locator('[data-stage="extract"]')).toContainText('30 ms');
	await expect(page.locator('[data-stage="summarize"]')).toContainText('700 ms');
});

test('reading and writing are reported as separate rates', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.getByText('Model tokens per second')).toBeVisible();
	const day = page.locator('[data-throughput-day]').first();

	// Summed, not averaged: 2916 prompt tokens less 1800 the cache carried is
	// 1116 read in 95.103 s, and 466 written in 79.805 s.
	await expect(day).toContainText('11.73 tok/s');
	await expect(day).toContainText('85 ms');
	await expect(day).toContainText('5.84 tok/s');
	await expect(day).toContainText('171 ms');
	await expect(day).toContainText('62% of prompt reused');

	// Both bars share one scale, so the slower rate has to draw shorter. Drawn
	// against their own maxima they would both be full width and say nothing.
	const widths = await day.locator('.h-3 > div').evaluateAll((bars) =>
		bars.map((bar) => bar.getBoundingClientRect().width)
	);
	expect(widths).toHaveLength(2);
	expect(widths[0]).toBeGreaterThan(0);
	expect(widths[1]).toBeGreaterThan(0);
	expect(widths[1]).toBeLessThan(widths[0]);
});

test('the telemetry viewport renders the published projection', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.locator('[data-viewport-control]')).toBeVisible();
	await expect(page.locator('[data-failure-panels]')).toBeVisible();
	await expect(page.locator('[data-compression]')).toBeVisible();
	await expect(page.locator('[data-viewport-control]')).toContainText('3 rows in view');
});

test('a failure panel prints its rate in type, not only in a tooltip', async ({ page }) => {
	await page.goto('/console/');

	// A `<title>` does not fire on touch and does not survive the screenshot an
	// operator pastes into an issue, so a chart whose only number is a tooltip
	// has no number.
	for (const stage of ['fetch', 'extract', 'summarize']) {
		await expect(page.locator(`[data-panel-rate="${stage}"]`)).toHaveText(
			/(\d+%|<1%) failed, \d+ of \d+\.|No rows in this window\./
		);
	}
});

test('a window holding one day draws no bar, because a bar would be the panel', async ({
	page
}) => {
	await page.goto('/console/');

	const viewport = page.locator('[data-viewport-control]');
	const start = await viewport.getAttribute('data-window-start');
	const end = await viewport.getAttribute('data-window-end');
	test.skip(start !== end, 'the fixture window spans more than one day');

	await expect(page.locator('[data-panel]')).toHaveCount(0);
	await expect(page.locator('[data-panel-rate="fetch"]')).toBeVisible();
});

test('the failed-item list is capped, states its scope, and offers the rest', async ({ page }) => {
	await page.goto('/console/');

	const rows = page.locator('[data-failure-list="rows"] tbody tr');
	const empty = page.locator('[data-failure-list="empty"]');
	if ((await empty.count()) === 1) {
		await expect(empty).toBeVisible();
		return;
	}

	// Whatever the fixture holds, the list never renders more than the cap.
	expect(await rows.count()).toBeLessThanOrEqual(FAILURE_LIST_MAX);
	await expect(page.locator('[data-failure-scope]')).toContainText('in this window.');
});

test('the compression view draws the data once', async ({ page }) => {
	await page.goto('/console/');

	// A second plot under the first drew strictly less - no band reference and
	// no truncation mark - which is two drawings of one dataset that disagree.
	const chart = page.locator('[data-compression]');
	await expect(chart.locator('svg')).toHaveCount(1);
	await expect(chart.locator('canvas')).toHaveCount(0);
});

test('the reading path and the console carry no chart library', () => {
	const manifest = JSON.parse(
		readFileSync(resolve(process.cwd(), 'package.json'), 'utf8')
	) as { dependencies?: Record<string, string> };

	// Rule #8: a dependency names a beneficiary feature. The pan and zoom this
	// one was bought for are implemented in `Viewport.svelte`.
	expect(Object.keys(manifest.dependencies ?? {})).toEqual([]);
});

test('the old evals route moves bookmarks to the console', async ({ page }) => {
	await page.goto('/evals/');

	await expect(page).toHaveURL(/\/console\/$/);
	await expect(page.getByRole('heading', { name: 'Console' })).toBeVisible();
});

test('the evals entry point keeps a no-JS link to the console', () => {
	const page = readFileSync(resolve(process.cwd(), 'src', 'routes', 'evals', '+page.svelte'), 'utf8');

	expect(page).toContain('http-equiv="refresh"');
	expect(page).toContain('<link rel="canonical" href={consoleHref} />');
	expect(page).toContain('<a href={consoleHref}');
	expect(page).not.toContain('evalRows');
	// The stub is a redirect, not a second dashboard. Two surfaces counting one
	// ledger disagree the moment one count changes.
	expect(page).not.toContain('$lib/bands');
});

test('keyboard alone pans and zooms the telemetry viewport', async ({ page }) => {
	await page.goto('/console/');

	const viewport = page.locator('[data-viewport-control]');
	await viewport.focus();
	await expect(viewport).toBeFocused();
	const start = await viewport.getAttribute('data-window-start');
	const end = await viewport.getAttribute('data-window-end');

	await page.keyboard.press('ArrowLeft');
	await expect(viewport).not.toHaveAttribute('data-window-start', start ?? '');

	const pannedStart = await viewport.getAttribute('data-window-start');
	const pannedEnd = await viewport.getAttribute('data-window-end');
	await page.keyboard.press('-');
	const widenedStart = await viewport.getAttribute('data-window-start');
	const widenedEnd = await viewport.getAttribute('data-window-end');
	expect(span(widenedStart, widenedEnd)).toBeGreaterThan(span(pannedStart, pannedEnd));
	await page.keyboard.press('-');
	const widerStart = await viewport.getAttribute('data-window-start');
	const widerEnd = await viewport.getAttribute('data-window-end');
	await page.keyboard.press('+');
	const zoomedStart = await viewport.getAttribute('data-window-start');
	const zoomedEnd = await viewport.getAttribute('data-window-end');
	expect(span(zoomedStart, zoomedEnd)).toBeLessThan(span(widerStart, widerEnd));
	expect(span(start, end)).toBeGreaterThan(0);
});

test('panning to a month with no rows leaves a visible gap', async ({ page }) => {
	await page.goto('/console/');

	const viewport = page.locator('[data-viewport-control]');
	await viewport.focus();
	for (let index = 0; index < 8; index += 1) {
		await page.keyboard.press('ArrowLeft');
	}

	await expect(page.getByText('No rows in this window').first()).toBeVisible();
	await expect(viewport).toContainText('0 rows in view');
});

test('a missing ledger costs the page a section, never the page', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const missing = watchFor404s(page);

	await page.goto('/console/');

	// The canary build has no score ledger. The page says so and carries on:
	// the timing chart, run grid and feed table still draw.
	await expect(page.getByText('Nothing has been scored yet.')).toBeVisible();
	await expect(page.getByText('Median seconds per item, by stage')).toBeVisible();
	await expect(page.locator('[data-grid="days"]')).toBeVisible();
	await expect(page.locator('[data-feeds="table"]')).toBeVisible();

	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});
