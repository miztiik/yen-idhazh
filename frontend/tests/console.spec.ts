import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	capLabel,
	capsInView,
	compressionView,
	grouped,
	parseTelemetryCsv,
	placeRow,
	type CompressionPoint,
	type TelemetryRow
} from '../src/lib/charts/series';
import { axisLabels, spanLabel } from '../src/lib/charts/run-history';
import { dayKey, monthsInWindow, panWindow, toDay } from '../src/lib/charts/viewport';
import {
	CUT_FLAG_MEANS_A_CUT_FROM,
	modelWork,
	sourceCuts,
	SOURCE_CUT_ROWS
} from '../src/lib/server/model-work';
import { readCsv, telemetryMonths, telemetryRows } from '../src/lib/server/payload';

/**
 * The console says whether the runs worked and which feeds are broken.
 *
 * It runs against the canary build, whose fixtures carry one run of each colour
 * and one feed of each kind the page has to tell apart. The canary build writes
 * the item-health ledger because the console reads timing medians from it, and
 * the score ledger because the compression plot reads its marks from that. The
 * failed-item list is the section with nothing to show, which proves the page
 * keeps rendering when one of its sources holds nothing.
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

/** The window the viewport opens on, read from the same knob the page reads. */
const DEFAULT_WINDOW_DAYS = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
	) as { console?: { default_window_days?: number } }
).console?.default_window_days ?? 30;

/** The fewest articles a source needs before a share of them means anything. */
const MIN_ATTEMPTS_FOR_RATE = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
	) as { console?: { min_attempts_for_rate?: number } }
).console?.min_attempts_for_rate ?? 5;

/** A telemetry corpus deliberately longer than the window, for the seed tests.
 *
 * The canary day carries two days, which is shorter than any window this knob
 * can hold. A window asserted against a corpus it cannot cut passes without
 * cutting anything, so the seed tests read this instead.
 */
const TELEMETRY_FIXTURE = resolve(process.cwd(), 'tests', 'fixtures', 'telemetry');

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

/** Wide enough that the run strip cannot fill its frame at any day count the
 * window admits, because `cellFor` caps a day column. That is what lets an
 * alignment test assert on spare room without depending on today's ledger. */
const UNDERFULL_VIEWPORT = { width: 1680, height: 900 };

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

/** How many items the fixture ledger scored.
 *
 * Read from the file rather than typed here: a count in a test is a count that
 * goes stale the day the fixture grows a row, and it goes stale silently.
 */
function scoredItems(): number {
	const raw = readFileSync(join(CANARY, 'state', 'scores.csv'), 'utf8');
	return raw.trim().split('\n').length - 1;
}

/** The canary's own telemetry projection - the file the page fetches.
 *
 * The compression plot draws from these rows, so its oracle reads them. It used
 * to read `state/scores.csv`, which the plot no longer touches: an oracle over
 * a file the page has stopped reading passes while the page draws something
 * else entirely.
 */
function telemetryProjection(): TelemetryRow[] {
	const dir = join(CANARY, 'state', 'telemetry');
	return readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => parseTelemetryCsv(readFileSync(join(dir, name), 'utf8')));
}

/** The rows the plot is about: an item that reached a reader.
 *
 * One entry per article per day, not per row. A re-run writes a second row for
 * an article an earlier run already published, and the run that read the most
 * of it is the one the plot draws. Recomputed here rather than imported, so an
 * implementation that counted rows would fail against this instead of moving
 * the oracle with it.
 */
function publishedRows(): TelemetryRow[] {
	const perArticle = new Map<string, TelemetryRow>();
	for (const row of telemetryProjection()) {
		if (row.stage !== 'publish' || row.outcome !== 'ok') continue;
		const key = `${row.date}-${row.item_id}`;
		const held = perArticle.get(key);
		if (held === undefined || articleWords(row) > articleWords(held)) perArticle.set(key, row);
	}
	return [...perArticle.values()];
}

/** The article's own length: before the cap where a run wrote one down, and
 * what survived where it did not. Recomputed here rather than imported, so a
 * reading that changed in the page would not change under the test with it. */
function articleWords(row: TelemetryRow): number {
	return row.source_words_before_cap ?? row.source_words ?? 0;
}

/** The rows the compression plot can place: both lengths written down. */
function plottedRows(): TelemetryRow[] {
	return publishedRows().filter(
		(row) => articleWords(row) > 0 && (row.summary_words ?? 0) > 0
	);
}

/** The rows that recorded no article length at all, so they have no x. */
function noLengthRows(): TelemetryRow[] {
	return publishedRows().filter((row) => articleWords(row) <= 0);
}

/** The articles the cap cut: the body before it was longer than what survived.
 *
 * Two cells of one row and nothing else. It used to be a flag read through the
 * ledger stamp that changed the flag's meaning; the projection needs no stamp,
 * because a comparison of two lengths has only ever meant one thing.
 */
function cutRows(): TelemetryRow[] {
	return plottedRows().filter(
		(row) =>
			row.source_words_before_cap !== null &&
			row.source_words !== null &&
			row.source_words_before_cap > row.source_words
	);
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

/** The oracle rows the page's own open window holds.
 *
 * The window is read off the page rather than recomputed, so a fixture that
 * grows a day past the window moves the count with it. Comparing a chart drawn
 * over a window against a corpus is how a test starts passing on the wrong
 * number.
 */
async function inOpenWindow(page: Page, rows: TelemetryRow[]): Promise<TelemetryRow[]> {
	const control = page.locator('[data-viewport-control]');
	const start = (await control.getAttribute('data-window-start')) ?? '';
	const end = (await control.getAttribute('data-window-end')) ?? '';
	expect(start, 'the page published no window, so the filter below drops everything').not.toBe('');
	return rows.filter((row) => row.date >= start && row.date <= end);
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

test('runs rise from a shared baseline, on a square day track', async ({ page }) => {
	await page.goto('/console/');

	const stack = await page.locator(`[data-day="${DAY}"] [data-health]`).evaluateAll(TO_BOX);
	expect(stack.length).toBe(runCount());

	// Run 1 is first in the DOM so it is read first, and lowest on screen so the
	// day reads upward from the ground like every other time series.
	const lowest = Math.max(...stack.map((box) => box.y));
	expect(stack[0].y).toBe(lowest);

	// The track grows into the room the frame gives it and never shrinks below
	// the 16 it has always used, so the size is a floor rather than a constant.
	// What must hold at every size: a square is square, and every square on the
	// strip is the same size, or the strip stops being a time axis.
	for (const box of stack) {
		expect(box.width).toBeGreaterThanOrEqual(16);
		expect(box.height).toBe(box.width);
		expect(box.width).toBe(stack[0].width);
	}
	// The gap holds its share of the column at every size, so two days apart
	// still measures twice one day apart. Rounded to a whole pixel by the layout,
	// so the check is the share within a pixel rather than an exact value.
	for (let index = 1; index < stack.length; index += 1) {
		const measured = stack[index - 1].y - stack[index].bottom;
		expect(Math.abs(measured - stack[0].width / 4)).toBeLessThanOrEqual(1);
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
		// The same share, between columns as within one. Two days apart measures
		// twice one day apart at whatever size the strip was given.
		const measured = columns[index].x - columns[index - 1].right;
		expect(Math.abs(measured - columns[0].width / 4)).toBeLessThanOrEqual(1);
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

test('a short history starts at the left edge and grows right', async ({ page }) => {
	// Where an OVERFLOWING strip opens and where an UNDERFULL one sits are two
	// questions, and `today_anchor` only answers the first. Anchored right, the
	// whole strip slid left by a column every time a day was published, so a run
	// an operator had looked at yesterday was somewhere else today. Anchored
	// left, a day keeps its place and the empty room is on the side where the
	// days that have not happened yet belong.
	//
	// Wide on purpose. `cellFor` caps a day column, so past a frame width the
	// strip CANNOT fill its room whatever the ledger holds - which is what makes
	// the premise below a property of the layout rather than of today's data.
	await page.setViewportSize(UNDERFULL_VIEWPORT);
	await page.goto('/console/');

	const [strip] = await page.locator('[data-run-history]').evaluateAll(TO_BOX);
	const columns = await page.locator('[data-day]').evaluateAll(TO_BOX);

	// The premise: fewer days than the strip has room for. Without it the test
	// passes on a full strip, where left and right alignment are the same thing.
	const drawn = columns[columns.length - 1].right - columns[0].x;
	expect(drawn, 'the strip is full, so alignment cannot be told apart').toBeLessThan(
		strip.width - 2
	);

	expect(Math.abs(columns[0].x - strip.x)).toBeLessThan(2);
	expect(strip.right - columns[columns.length - 1].right).toBeGreaterThan(1);
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

test('the run that read only the start of an article says so on its own square', async ({
	page
}) => {
	await page.goto('/console/');

	// Per run, and only here. Measured 2026-08-29 over 19 committed runs the
	// count is 1 to 12 articles of 160 to 200 - which is the article mix on that
	// run, so a published figure would read as the cap moving when nothing did.
	const dir = join(CANARY, 'state', 'item-health');
	const rows = readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(dir, name)).rows)
		.filter((row) => row.date === DAY);
	const cutByRun = new Map<string, Set<string>>();
	for (const row of rows) {
		if (row.source_words_before_cap === '' || row.source_words === '') continue;
		if (Number(row.source_words_before_cap) <= Number(row.source_words)) continue;
		cutByRun.set(row.run_id, (cutByRun.get(row.run_id) ?? new Set()).add(row.url_key));
	}
	expect(cutByRun.size, 'no run on this day cut anything, so the clause is untested').toBe(1);

	const labels = await page
		.locator(`[data-day="${DAY}"] [data-health]`)
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label') ?? ''));
	const carried = labels.filter((label) => label.includes('read only in part'));
	expect(carried).toHaveLength(cutByRun.size);
	for (const [runId, keys] of cutByRun) {
		const n = Number(runId.split('-').at(-1));
		expect(carried[0]).toContain(`run ${n},`);
		expect(carried[0]).toContain(`${keys.size} read only in part`);
	}

	// And a run that cut nothing does not carry the clause at all. A `0 read
	// only in part` on every other square is a sentence about nothing.
	expect(labels.filter((label) => label.includes('0 read only in part'))).toEqual([]);
	expect(labels.length).toBeGreaterThan(carried.length);
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

test('a feed that answered with nothing does not report its last result as ok', async ({ page }) => {
	await page.goto('/console/');

	// The ledger's own word for this read is `ok` - the fetch returned 200. Printed
	// raw it sits on the same row as the failure count and contradicts it, which is
	// how a dead feed reads as a healthy one.
	const result = page.locator('[data-feed="canary-empty"] [data-feed-result]');
	await expect(result).toHaveCount(1);
	await expect(result).toContainText('answered with nothing');

	// A feed that really did fail still reports the reason the ledger recorded.
	await expect(page.locator('[data-feed="canary-gone"] [data-feed-result]')).not.toContainText(
		'answered with nothing'
	);
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

	await expect(page.getByText('Time per item, by stage')).toBeVisible();
	// The legend, not the axis: the largest median is printed in both places, so
	// an unscoped match is ambiguous the moment one stage is the slowest.
	await expect(page.locator('[data-stage="fetch"]')).toContainText('200 ms');
	await expect(page.locator('[data-stage="extract"]')).toContainText('30 ms');
	await expect(page.locator('[data-stage="summarize"]')).toContainText('700 ms');
});

test('the timing y axis is decades, and it crosses milliseconds to seconds', async ({ page }) => {
	await page.goto('/console/');

	const labels = await page
		.locator('[data-timing="plot"] [data-decade]')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));

	// Four stages spanning three decades cannot share a linear axis: the slowest
	// sets the domain and the other three draw on the baseline.
	expect(labels.length).toBeGreaterThanOrEqual(3);
	expect(labels).toContain('10 ms');
	expect(labels).toContain('100 ms');
	expect(labels).toContain('1 s');
	// One label in each unit, so the reader is told where the crossing is.
	expect(labels.some((text) => text.endsWith(' ms'))).toBe(true);
	expect(labels.some((text) => /\d s$/.test(text))).toBe(true);

	// Zero has no position on a log axis, so the old baseline label is gone.
	const printed = await page
		.locator('[data-timing="plot"] text')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));
	expect(printed).not.toContain('0');

	// The eight steps inside each decade, unlabelled. Without them the axis
	// reads as linear with odd numbers on it.
	const stubs = await page.locator('[data-timing="plot"] [data-minor-tick]').count();
	expect(stubs).toBeGreaterThanOrEqual(8 * (labels.length - 1));
	for (const text of printed) expect(text).not.toBe('20');
});

test('the timing legend is sorted by the newest day, tallest first', async ({ page }) => {
	await page.goto('/console/');

	// Colour is one signal and never the only one. Matching the legend order to
	// the plot's vertical order makes position the second signal, for free.
	const entries = await page
		.locator('[data-timing="chart"] [data-stage]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				stage: node.getAttribute('data-stage') ?? '',
				text: node.textContent?.trim() ?? ''
			}))
		);
	expect(entries.length).toBeGreaterThan(1);

	const asMs = (text: string): number => {
		const match = text.match(/([\d.]+)\s(ms|s)$/);
		if (!match) return -1;
		return Number(match[1]) * (match[2] === 's' ? 1000 : 1);
	};
	const values = entries.map((entry) => asMs(entry.text));
	for (let index = 1; index < values.length; index += 1) {
		expect(values[index]).toBeLessThanOrEqual(values[index - 1]);
	}
	expect(entries[0].stage).toBe('summarize');
});

test('a stage with no number draws a gap, never a plunge to the axis floor', async ({ page }) => {
	await page.goto('/console/');

	// The canary scores one day of the three, so `score` has a number on that
	// day and none on the other two. A zero clamped onto a log axis would draw
	// the line falling to the bottom of the plot, which says the stage got a
	// thousand times faster. The chart breaks the line and names the loss.
	await expect(page.locator('[data-stage-mark="score"]')).not.toHaveCount(0);
	const note = page.locator('[data-timing-note="score"]');
	await expect(note, 'score is timed on one day of three, so it owes a note').toHaveCount(1);
	await expect(note).toHaveText('We timed no score work on 2 of the 3 days. The line breaks there.');

	const geometry = await page.locator('[data-timing="plot"]').evaluate((svg) => {
		const floor = Math.max(
			...[...svg.querySelectorAll('[data-decade-line]')].map((line) =>
				Number(line.getAttribute('y1'))
			)
		);
		const drawn = [...svg.querySelectorAll('[data-stage-mark]')].flatMap((mark) =>
			mark.tagName === 'circle'
				? [Number(mark.getAttribute('cy'))]
				: (mark.getAttribute('points') ?? '')
						.split(' ')
						.filter(Boolean)
						.map((pair) => Number(pair.split(',')[1]))
		);
		return { floor, lowest: Math.max(...drawn), marks: drawn.length };
	});

	expect(geometry.marks).toBeGreaterThan(0);
	// Every stage is legible: no line sits flat on the floor of the plot.
	expect(geometry.floor - geometry.lowest).toBeGreaterThan(4);
});

test('a timing nobody took, a timing of zero and a partly timed day read apart', async ({
	page
}) => {
	await page.goto('/console/');

	// The three facts that used to arrive at this chart as the number 0. The
	// fixture carries one of each: 2026-08-18 timed no summarize work, timed
	// extract at 0 ms on all three items, and 2026-08-20 timed four of its five
	// items for summarize. Counts are asserted before text, so renaming an
	// attribute fails here instead of quietly matching nothing.
	const zero = page.locator('[data-stage-zero="extract"]');
	await expect(zero, 'the day extract measured 0 ms draws one open dot').toHaveCount(1);
	await expect(zero, 'an open dot, so it is not read as a point on the scale').toHaveAttribute(
		'fill',
		'none'
	);

	// Centred on the baseline rule. Clamped into the bottom decade instead, it
	// would draw a plunge that says the stage got a thousand times faster.
	const offBaseline = await page.locator('[data-timing="plot"]').evaluate((svg) => {
		const dot = svg.querySelector('[data-stage-zero]');
		const floor = Math.max(
			...[...svg.querySelectorAll('[data-decade-line]')].map((line) =>
				Number(line.getAttribute('y1'))
			)
		);
		return Math.abs(Number(dot?.getAttribute('cy')) - floor);
	});
	expect(offBaseline).toBeLessThanOrEqual(1);

	const extract = page.locator('[data-timing-note="extract"]');
	await expect(extract, 'the measured zero is named in type').toHaveCount(1);
	await expect(extract).toHaveText(
		'extract took under 1 ms per item on 1 day, which is faster than we can time. ' +
			'The open dot on the baseline marks it.'
	);

	// Both facts about summarize, one paragraph, absence first.
	const summarize = page.locator('[data-timing-note="summarize"]');
	await expect(summarize, 'summarize has a blank day and a part-timed day').toHaveCount(1);
	await expect(summarize).toHaveText(
		'We timed no summarize work on 1 of the 3 days. The line breaks there. ' +
			'We timed 4 of the 5 items for summarize on 1 day. The line is the items we timed.'
	);

	// A stage timed in full every day of the window has nothing to explain.
	await expect(page.locator('[data-timing-note="fetch"]')).toHaveCount(0);

	// One place, not two. The legend used to print `no data` for the same
	// absence a paragraph under it also named.
	const chart = await page.locator('[data-timing="chart"]').innerText();
	expect(chart).not.toContain('no data');
	expect(chart).not.toContain('No time recorded');
});

test('the timing chart draws one unit per CSS pixel at every width', async ({ page }) => {
	// A viewBox is a scale factor, not a unit. When it disagrees with the width
	// the chart occupies, every declared font-size and stroke-width comes out at
	// some other number - 0.87x at 380px before this was fixed.
	const measured: { viewport: number; declared: number; rendered: number }[] = [];
	for (const viewport of [380, 768, 1400]) {
		await page.setViewportSize({ width: viewport, height: 1000 });
		await page.goto('/console/');
		const plot = page.locator('[data-timing="plot"]');
		await expect(plot).toBeVisible();
		await expect
			.poll(async () => {
				const box = await plot.boundingBox();
				const viewBox = (await plot.getAttribute('viewBox')) ?? '';
				return Math.abs(Number(viewBox.split(' ')[2]) - (box?.width ?? 0)) <= 1;
			})
			.toBe(true);
		const box = await plot.boundingBox();
		const viewBox = (await plot.getAttribute('viewBox')) ?? '';
		measured.push({
			viewport,
			declared: Number(viewBox.split(' ')[2]),
			rendered: Math.round(box?.width ?? 0)
		});
	}

	// Reported rather than only asserted, so a failure names the three pairs.
	for (const pair of measured) {
		expect(Math.abs(pair.declared - pair.rendered)).toBeLessThanOrEqual(1);
	}
});

test('a stage colour is categorical, never a health band', () => {
	const source = readFileSync(
		resolve(process.cwd(), 'src', 'lib', 'components', 'StageTimings.svelte'),
		'utf8'
	);

	// Green, amber and red mean good, watch and bad everywhere else on this page.
	// Lending them to four stages says the slowest one is the failing one.
	expect(source).not.toContain('--band-');
	for (const series of ['--series-1', '--series-2', '--series-3', '--series-4']) {
		expect(source).toContain(series);
	}
});

test('reading and writing are drawn as separate candles per day', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.getByText('Model tokens per second')).toBeVisible();

	// Two days on record, two series each. A day with no census draws nothing
	// rather than a candle sitting on zero.
	await expect(page.locator('[data-candle="read"]')).toHaveCount(2);
	await expect(page.locator('[data-candle="write"]')).toHaveCount(2);

	// The whole day over the whole day: 4253 prompt tokens less the 2183 the
	// cache carried is 2070 read in 177.249 s, and 655 written in 113.008 s.
	const verdict = page.locator('[data-throughput="verdict"]');
	await expect(verdict).toContainText('read 11.68 tok/s');
	await expect(verdict).toContainText('write 5.80 tok/s');
	await expect(verdict).toContainText('4 items across 2 runs');
	await expect(verdict).toContainText('Read is up 5% and write is up 9%');

	// Milliseconds per token is 1000 / tokens per second, so drawing it too
	// would be the same fact mirrored. It must not come back.
	await expect(verdict).not.toContainText('ms per token');
});

test('a candle carries its spread and its runs without a mouse', async ({ page }) => {
	await page.goto('/console/');

	const newest = page.locator('[data-candle="write"][data-date="2026-08-20"]');
	const caption = await newest.locator('title').textContent();

	expect(caption).toContain('median');
	expect(caption).toContain('middle half');
	// Per run, because a day hides which of its four runs moved.
	expect(caption).toContain('Run medians: 2026-08-20-1');
	expect(caption).toContain('2026-08-20-2');
});

test('writing draws slower than reading, on one shared scale', async ({ page }) => {
	await page.goto('/console/');

	const medians = async (series: string) =>
		page
			.locator(`[data-candle="${series}"][data-date="2026-08-20"] rect`)
			.evaluateAll((boxes) => boxes.map((box) => box.getBoundingClientRect().top));

	const [read] = await medians('read');
	const [write] = await medians('write');

	// Y grows downward, so the slower series sits lower on the page. Drawn
	// against their own maxima both would top out and say nothing.
	expect(read).toBeGreaterThan(0);
	expect(write).toBeGreaterThan(read);
});

test('the chart points at the write-up rather than restating it', async ({ page }) => {
	await page.goto('/console/');

	const link = page.getByRole('link', { name: 'why the spread is wide' });
	await expect(link).toHaveAttribute(
		'href',
		'https://github.com/miztiik/yen-idhazh/blob/main/docs/architecture/summarize/throughput.md'
	);
});

test('the throughput chart draws in the pixels it occupies', async ({ page }) => {
	await page.goto('/console/');

	const svg = page.locator('[data-throughput="chart"] svg');
	// A viewBox is a scale factor, not a unit. Where the two disagree the chart
	// renders every declared font-size at some other number of pixels.
	for (const width of [380, 768, 1400]) {
		await page.setViewportSize({ width, height: 900 });
		await expect
			.poll(async () =>
				svg.evaluate(
					(node) =>
						Math.abs(
							Number((node.getAttribute('viewBox') ?? '').split(' ')[2]) -
								node.getBoundingClientRect().width
						) <= 1
				)
			)
			.toBe(true);
	}
});

test('the throughput axis covers the rates drawn, not zero to the fastest', async ({ page }) => {
	await page.goto('/console/');

	const ticks = await page
		.locator('[data-throughput-tick]')
		.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('data-throughput-tick'))));

	// The fixture's slowest item writes at 5.30 tok/s and its fastest reads at
	// 11.91. Both ends are printed, and the axis does not spend most of its
	// height on rates nothing ran at - a candle says where a rate is, and only a
	// mark whose length carries the number needs zero on the axis.
	expect(ticks.length).toBeGreaterThanOrEqual(2);
	expect(Math.min(...ticks)).toBeGreaterThan(0);
	expect(Math.min(...ticks)).toBeLessThanOrEqual(5.3);
	expect(Math.max(...ticks)).toBeGreaterThanOrEqual(11.91);

	// The prompt-reuse line and its right-hand 0-100% axis are gone. Reuse is a
	// cache statistic, so the number stays in the legend and nothing draws a
	// second y scale a reader could correlate against tokens per second.
	await expect(page.locator('[data-throughput="chart"] polyline')).toHaveCount(0);
	await expect(page.locator('[data-series="reused"]')).toContainText('51%');
});

test('the telemetry viewport renders the published projection', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.locator('[data-viewport-control]')).toBeVisible();
	await expect(page.locator('[data-failure-panels]')).toBeVisible();
	await expect(page.locator('[data-compression]')).toBeVisible();

	// Counted off the projection the page reads, over the window the page says it
	// is showing. It was `11 rows in view` until the fixture grew the rows the
	// source table needs - and a count against a window this test picked itself
	// would go stale the day the fixture moves out from under it.
	const control = page.locator('[data-viewport-control]');
	const first = (await control.getAttribute('data-window-start')) ?? '';
	const last = (await control.getAttribute('data-window-end')) ?? '';
	expect(first, 'the viewport publishes no window, so there is nothing to count over').not.toBe('');
	const shard = join(CANARY, 'state', 'telemetry');
	const inView = readdirSync(shard)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(shard, name)).rows)
		.filter((row) => row.date >= first && row.date <= last);
	expect(inView.length, 'the window holds no row, so the count below is trivial').toBeGreaterThan(0);
	await expect(control).toContainText(`${inView.length} rows in view`);
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

test('a failure panel draws in CSS pixels, so its type is the size it declares', async ({
	page
}) => {
	await page.goto('/console/');

	// The skip reads the window, which is the fixture's own fact, and never a
	// locator count. Counting `[data-panel]` here meant that renaming the
	// attribute drew zero panels, skipped this test, and left the suite green.
	// `span` answers 0 for a missing attribute, so the skip cannot fire on one.
	const viewport = page.locator('[data-viewport-control]');
	const start = await viewport.getAttribute('data-window-start');
	const end = await viewport.getAttribute('data-window-end');
	test.skip(span(start, end) === 1, 'the fixture window holds one day, so no panel draws');

	// One panel per stage - fetch, extract and summarize. A renamed attribute
	// fails here instead of switching the test off.
	const panels = page.locator('[data-panel]');
	await expect(panels, 'a window of more than one day draws one panel per stage').toHaveCount(3);

	// A `viewBox` is a scale factor, not a unit. Stretched from 360 units into a
	// 163px panel it put `font-size="10"` on screen at 4.5px.
	for (const width of [380, 768, 1400]) {
		await page.setViewportSize({ width, height: 900 });
		await expect
			.poll(async () =>
				panels.evaluateAll((nodes) =>
					nodes.every((node) => {
						const declared = Number((node.getAttribute('viewBox') ?? '').split(' ')[2]);
						return Math.abs(declared - node.getBoundingClientRect().width) <= 1;
					})
				)
			)
			.toBe(true);
	}

	// Two rules: the baseline and the y axis. The unlabelled 50% dash was a
	// reference at a value nobody acts on, and it is gone.
	await expect(page.locator('[data-panel="fetch"] line')).toHaveCount(2);
	// Both ends of the fixed domain are printed, so the scale can be read.
	await expect(page.locator('[data-panel="fetch"]')).toContainText('100%');
	await expect(page.locator('[data-panel="fetch"]')).toContainText('0%');
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

	// The band reference is one step outline across the whole axis, so it costs
	// the same handful of nodes at seven points and at eleven hundred. It used
	// to be one vertical line per point: 1166 of them on the committed ledger,
	// measured 2026-08-25.
	expect(await chart.locator('svg path').count()).toBeLessThanOrEqual(4);

	// Both arms stay asserted. The canary window now holds scored items, and
	// this test also runs against a window that holds none.
	const marks = await chart.locator('svg circle, svg rect').count();
	if (marks === 0) {
		await expect(chart).toContainText('No scored items in this window');
	} else {
		await expect(chart.locator('[data-band-zone]')).toHaveCount(1);
	}
});

test('the compression view draws every article it can place, and marks only the ones the cap cut', async ({
	page
}) => {
	await page.goto('/console/');

	// The state that had no coverage at all while the canary day carried no
	// scored item: marks instead of a sentence, a zone behind them, and more
	// than one decade under them.
	const chart = page.locator('[data-compression]');
	await expect(chart).not.toContainText('No scored items in this window');

	const placeable = await inOpenWindow(page, plottedRows());
	const cut = await inOpenWindow(page, cutRows());

	const dots = await chart.locator('svg circle').count();
	const diamonds = await chart.locator('svg rect').count();
	expect(dots).toBeGreaterThan(0);
	// Every row the plot can place reaches it, and no row it cannot does. A
	// filter that dropped one either way would still leave a chart that looks
	// right.
	expect(dots + diamonds).toBe(placeable.length);
	// And the plot is drawn from the published projection, not from every row of
	// it: the fixture holds rows this predicate throws away, and it holds one
	// article two runs both wrote a row for, so a plot that drew the whole file
	// would land on a different number here.
	expect(
		placeable.length,
		'the fixture holds only one row an article, so the filter cannot be seen to fire'
	).toBeLessThan((await inOpenWindow(page, telemetryProjection())).length);

	// A diamond says the cap cut this article, which the projection carries as
	// its pre-cap length standing above its post-cap one. The fixture holds
	// articles on both sides of that, so the count below is evidence rather than
	// an absence, and an unconditional diamond fails it in both directions.
	expect(cut.length, 'the fixture cut nothing, so the mark cannot be seen to fire').toBeGreaterThan(
		0
	);
	expect(cut.length, 'the fixture cut everything, so a diamond on every row would pass').toBeLessThan(
		placeable.length
	);
	expect(diamonds, 'a diamond is drawn for an article the cap cut, and for nothing else').toBe(
		cut.length
	);

	await expect(chart.locator('[data-band-zone]')).toHaveCount(1);

	// A log axis labelled at one decade is a linear axis with an odd label on
	// it. The y ticks, the cap labels and the two axis titles carry their own
	// attributes, so what is left is the decades.
	const decades = await chart
		.locator('svg text:not([data-tick="y"]):not([data-axis]):not([data-cap-label])')
		.evaluateAll((nodes) =>
			nodes
				.map((node) => (node.textContent ?? '').trim())
				.filter((text) => /^10*$/.test(text))
		);
	expect(new Set(decades).size).toBeGreaterThan(1);
});

test('the cap line comes from the cut points in view, and a window with none draws none', () => {
	// A fixture window built here rather than read off the canary: the canary is
	// one day, and the fact under test is what happens when a window straddles
	// two cap settings. A thirty-day window can, which is the whole reason the
	// line is read off the rows instead of off `extract.truncation_cap_tokens`.
	const point = (
		date: string,
		id: string,
		full: number,
		seen: number,
		cut: boolean
	): CompressionPoint => ({
		date,
		item_id: id,
		source_words: full,
		source_seen_words: seen,
		summary_words: 120,
		truncation_flagged: cut
	});

	const two = capsInView([
		point('2026-08-26', 'a', 4120, 1923, true),
		point('2026-08-27', 'b', 5200, 1923, true),
		point('2026-08-28', 'c', 9000, 3846, true),
		point('2026-08-28', 'd', 812, 812, false)
	]);
	// One line per distinct post-cap length, oldest first, and never one per
	// cut article - four cut rows at two settings are two lines.
	expect(two.map((cap) => cap.words)).toEqual([1923, 3846]);
	// Each label names its own value and its own end of the handover.
	expect(capLabel(two, 0)).toBe('cut at 1,923 words (to 27 Aug)');
	expect(capLabel(two, 1)).toBe('cut at 3,846 words (from 28 Aug)');

	// One cap over the whole window needs no date. It is the cut, throughout.
	const one = capsInView([point('2026-08-28', 'c', 9000, 3846, true)]);
	expect(one.map((cap) => cap.words)).toEqual([3846]);
	expect(capLabel(one, 0)).toBe('cut at 3,846 words');

	// The half a config-derived line fails. Nothing in view was cut, so there is
	// no cut to draw - a line read off the knob draws one anyway and claims a cut
	// the day never made.
	expect(capsInView([point('2026-08-28', 'd', 812, 812, false)])).toEqual([]);
	// A cut row with no recorded post-cap length has no x to sit at either.
	expect(capsInView([point('2026-08-28', 'e', 4120, 0, true)])).toEqual([]);
});

test('a dashed line is drawn for every cut length the window holds, and for no other', async ({
	page
}) => {
	await page.goto('/console/');

	const chart = page.locator('[data-compression]');
	const caps = [...new Set((await inOpenWindow(page, cutRows())).map((row) => row.source_words))]
		.filter((value): value is number => value !== null && value > 0)
		.sort((a, b) => a - b);

	await expect(
		chart.locator('[data-cap-line]'),
		'one dashed line per distinct cut length in view, and never one more'
	).toHaveCount(caps.length);
	// A line drawn from the knob would stand here whatever the rows held.
	await expect(chart.locator('svg line[stroke-dasharray="3 3"]')).toHaveCount(caps.length);

	for (const value of caps) {
		await expect(chart.locator(`[data-cap-line="${value}"]`)).toHaveCount(1);
		await expect(chart.locator(`[data-cap-label="${value}"]`)).toContainText(grouped(value));
	}
});

test('the plot says how many articles it could not place, and the count is the rows', async ({
	page
}) => {
	await page.goto('/console/');

	// The count and the sentence out of one reading, either way round. Drawing
	// the plot from the telemetry projection closed the gap this sentence used to
	// declare: an article that published has a length, so nothing is dropped and
	// the sentence stays off the page. It reads the rows rather than a constant,
	// so a fixture that ever holds one again turns it back on and pins its number.
	const dropped = (await inOpenWindow(page, noLengthRows())).length;
	const sentence = page.locator('[data-compression-note="not-plotted"]');

	if (dropped === 0) {
		await expect(sentence).toHaveCount(0);
	} else {
		await expect(sentence).toHaveText(
			`${dropped} articles in this window recorded no length before the cut, so they are not plotted.`
		);
	}

	// And the rows really did all get placed, rather than the plot being empty.
	await expect(page.locator('[data-compression] svg circle, [data-compression] svg rect')).not.toHaveCount(
		0
	);
});

test('an unplaceable row is counted and never silently dropped', () => {
	// The browser arm above cannot reach this state on the committed fixture, so
	// the decision is driven here instead of left to a sentence that never
	// prints. Three rows, one of each outcome, and the two outputs come out of
	// one pass - a plot and a sentence that disagree about the same row is the
	// failure this shape exists to prevent.
	const row = (over: Partial<TelemetryRow>): TelemetryRow => ({
		date: '2026-08-28',
		run_id: '2026-08-28-1',
		item_id: 'ai-01',
		vertical: 'ai',
		source_id: 'canary',
		stage: 'publish',
		outcome: 'ok',
		code: '',
		source_words: 1923,
		summary_words: 205,
		source_words_before_cap: 4200,
		...over
	});

	const view = compressionView([
		row({ item_id: 'ai-cut' }),
		row({ item_id: 'ai-whole', source_words: 880, source_words_before_cap: null }),
		row({ item_id: 'ai-nolength', source_words: 0, source_words_before_cap: null }),
		row({ item_id: 'ai-nosummary', summary_words: null }),
		// A failure never had an article, so it is neither a point nor a row the
		// sentence should count. Without the predicate it lands in the sentence and
		// tells the operator articles went missing that never existed.
		row({ item_id: 'ai-failed', stage: 'fetch', outcome: 'failed', code: 'http_error' }),
		row({
			item_id: 'ai-dropped',
			stage: 'extract',
			source_words: 0,
			summary_words: null,
			source_words_before_cap: null
		}),
		// The same article, written again by a second run of the same day. One
		// article is one mark: drawing it twice draws one measurement twice, and
		// the run that read the most of it is the one that counts.
		row({ item_id: 'ai-whole', run_id: '2026-08-28-2', source_words: 300, source_words_before_cap: null })
	]);

	expect(view.points.map((point) => point.item_id)).toEqual(['ai-cut', 'ai-whole']);
	expect(view.points.find((point) => point.item_id === 'ai-whole')?.source_words).toBe(880);
	expect(view.unplotted).toEqual([{ date: '2026-08-28', n: 1 }]);

	// The cut is the two lengths and nothing else, and the second one is carried
	// only where it says something the first does not.
	const [cut, whole] = view.points;
	expect(cut.source_words).toBe(4200);
	expect(cut.source_seen_words).toBe(1923);
	expect(cut.truncation_flagged).toBe(true);
	expect(whole.source_words).toBe(880);
	expect('source_seen_words' in whole).toBe(false);
	expect(whole.truncation_flagged).toBe(false);

	// The three outcomes, asserted on the one decision the view folds.
	expect(placeRow(row({ source_words: 0, source_words_before_cap: null }))).toEqual({
		kind: 'no-length',
		date: '2026-08-28'
	});
	expect(placeRow(row({ summary_words: null })).kind).toBe('no-summary');
	expect(placeRow(row({})).kind).toBe('point');
});

test('a mark reads out on the keyboard, and the readout closes on Escape', async ({ page }) => {
	await page.goto('/console/');

	const readout = page.locator('[data-readout="compression"]');
	await expect(readout).toHaveCount(0);

	// Focus reaches the series, not the points. A tab stop per point would be a
	// two-and-a-half-thousand-stop tab order.
	const plot = page.locator('[data-compression] svg');
	await expect(plot).toHaveAttribute('tabindex', '0');
	await plot.focus();
	await expect(readout).toHaveCount(1);

	const first = (await readout.innerText()).trim();
	const viewport = page.locator('[data-viewport-control]');
	const before = await viewport.getAttribute('data-window-start');
	await page.keyboard.press('ArrowRight');
	await expect(readout).not.toHaveText(first);
	// The scatter sits inside the viewport control, which pans on the same two
	// arrows. One step through the marks must not also move the window under
	// them - it did, and the readout ended up pointing at a mark that had gone.
	await expect(viewport, 'stepping a mark also panned the window').toHaveAttribute(
		'data-window-start',
		before ?? ''
	);
	// The numbers are in type, in the reader's words, and never a column name.
	await expect(readout).toContainText(/\d+ \w+ - /);
	await expect(readout).toContainText(
		/Article [\d,]+ words(, cut to [\d,]+)?\. Summary [\d,]+ words\./
	);

	await page.keyboard.press('Escape');
	await expect(readout).toHaveCount(0);

	// And the hint that says so, under the chart it belongs to.
	await expect(page.locator('[data-readout-hint="compression"]')).toHaveText(
		'Keyboard: Left and Right step through the days. Escape closes.'
	);
});

test('the candle reads out the sentence its title already carried', async ({ page }) => {
	await page.goto('/console/');

	const readout = page.locator('[data-readout="throughput"]');
	await expect(readout).toHaveCount(0);

	const plot = page.locator('[data-throughput="chart"] svg');
	await plot.focus();
	await expect(readout).toHaveCount(1);

	// Decision: reuse `caption()` verbatim. The readout and the `<title>` are the
	// same words, so there is one sentence about a day and not two.
	const title = await page
		.locator('[data-candle="read"][data-date="2026-08-19"] title')
		.textContent();
	await expect(readout).toContainText((title ?? '').trim());

	await expect(page.locator('[data-readout-hint="throughput"]')).toHaveText(
		'Keyboard: Left and Right step through the days. Escape closes.'
	);
});

test.describe('under a thumb', () => {
	test.use({ hasTouch: true });

	test('a tap reads out, and lifting the thumb does not blank it', async ({ page }) => {
		await page.goto('/console/');

		const plot = page.locator('[data-compression] svg');
		// A tap lands in the viewport, not in the document, and this chart is a long
		// way down the console. Tapping an unscrolled box taps whatever is on screen
		// at that y, which is not this chart.
		await plot.scrollIntoViewIfNeeded();
		const box = await plot.boundingBox();
		expect(box, 'the plot has no box, so the tap below would land nowhere').not.toBeNull();
		const at = box as { x: number; y: number; width: number; height: number };

		// An SVG `<title>` needs a hover, so on a phone the numbers in it did not
		// exist. This is the whole reason the readout is not a `<title>`.
		await page.touchscreen.tap(at.x + at.width * 0.6, at.y + at.height * 0.5);

		const readout = page.locator('[data-readout="compression"]');
		await expect(readout, 'a tap must leave the numbers on screen after the lift').toHaveCount(1);
		await expect(readout).toContainText('Article');
	});
});

test('a window holding no scored item says so rather than drawing an empty plot', async ({
	page
}) => {
	await page.goto('/console/');

	const chart = page.locator('[data-compression]');
	await expect(chart.locator('svg circle, svg rect')).not.toHaveCount(0);

	// The empty state is reached the way a reader reaches it: by panning off the
	// days that have rows. The fixture always has rows, so this is where that
	// rendering is still proved.
	const viewport = page.locator('[data-viewport-control]');
	await viewport.focus();
	for (let index = 0; index < 8; index += 1) {
		await page.keyboard.press('ArrowLeft');
	}

	await expect(chart).toContainText('No scored items in this window');
	await expect(chart.locator('svg circle, svg rect')).toHaveCount(0);
	await expect(chart.locator('[data-band-zone]')).toHaveCount(0);
});

test('the compression chart draws in CSS pixels, and labels its own y axis', async ({ page }) => {
	for (const width of [380, 768, 1400]) {
		await page.setViewportSize({ width, height: 900 });
		await page.goto('/console/');

		// A viewBox is a scale factor, not a unit. One that disagrees with the
		// rendered width puts `font-size="10"` on screen at some other size.
		await expect
			.poll(async () =>
				page.locator('[data-compression] svg').evaluate((node) => {
					const declared = Number((node.getAttribute('viewBox') ?? '').split(/\s+/)[2]);
					return Math.abs(node.getBoundingClientRect().width - declared);
				})
			)
			.toBeLessThan(1);
	}

	// The y axis title used to be printed on the bottom row beside the x axis
	// title, which is what made the chart read as unfinished rather than ugly.
	const [title] = await page.locator('[data-compression] [data-axis="y"]').evaluateAll(TO_BOX);
	const [across] = await page.locator('[data-compression] [data-axis="x"]').evaluateAll(TO_BOX);
	expect(title.bottom).toBeLessThan(across.y);
	// Rotated, so it runs along the axis it names rather than across it.
	expect(title.height).toBeGreaterThan(title.width);

	// The left margin holds both the title and the tick numbers. It is narrow,
	// so the two overlapping is a real failure rather than a theoretical one.
	const ticks = await page.locator('[data-compression] [data-tick="y"]').evaluateAll(TO_BOX);
	expect(ticks.length).toBeGreaterThan(1);
	for (const tick of ticks) expect(tick.x).toBeGreaterThanOrEqual(title.right);
});

test('the compression axis titles say what the heading says', async ({ page }) => {
	await page.goto('/console/');

	const chart = page.locator('[data-compression]');
	await expect(chart.locator('[data-axis="x"]')).toHaveText('Article length, words');
	await expect(chart.locator('[data-axis="y"]')).toHaveText('Summary length, words');

	// The axis used to read "source words", which is how the ledger spells the
	// column, not how a reader says it. Nothing here may name a column again.
	for (const text of await chart.locator('[data-axis]').allTextContents()) {
		expect(text).not.toMatch(/source|_/i);
	}
});

test('the reading path and the console carry no chart library', () => {
	const manifest = JSON.parse(
		readFileSync(resolve(process.cwd(), 'package.json'), 'utf8')
	) as { dependencies?: Record<string, string> };

	// Rule #8: a dependency names a beneficiary feature. The pan this one was
	// bought for is implemented in `Viewport.svelte`, and the window it pans is
	// set by the control on the page above it.
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

test('keyboard alone pans the viewport and steps its window through the presets', async ({
	page
}) => {
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
	const steppedStart = await viewport.getAttribute('data-window-start');
	const steppedEnd = await viewport.getAttribute('data-window-end');
	expect(span(steppedStart, steppedEnd)).toBeLessThan(span(widerStart, widerEnd));
	expect(span(start, end)).toBeGreaterThan(0);

	// Every span a key can reach is one the control can name. A key that landed
	// between two presets would leave all four buttons unchecked, and the page
	// with no way back to the window it is drawing.
	const presets = (
		JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
		) as { console?: { window_presets?: number[] } }
	).console?.window_presets ?? [7, 14, 30, 90];
	expect(presets).toContain(span(steppedStart, steppedEnd));
	expect(presets).toContain(span(widerStart, widerEnd));
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

test('an empty section costs the page that section, never the page', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const missing = watchFor404s(page);

	await page.goto('/console/');

	// The canary telemetry records no failed item, so the failed-item list has
	// nothing to list. It says so and the page carries on: the timing chart, the
	// run grid, the feed table and the score table all still draw.
	await expect(page.locator('[data-failure-list="empty"]')).toBeVisible();
	await expect(page.getByText('Time per item, by stage')).toBeVisible();
	await expect(page.locator('[data-grid="days"]')).toBeVisible();
	await expect(page.locator('[data-feeds="table"]')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'What the model did' })).toBeVisible();
	await expect(page.locator('[data-charts="table"]')).toBeVisible();

	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});

test('the seed carries one window, however many months are committed', () => {
	const all = telemetryRows(TELEMETRY_FIXTURE);
	const seeded = telemetryRows(TELEMETRY_FIXTURE, DEFAULT_WINDOW_DAYS);
	const dates = all.rows.map((row) => row.date).sort();
	const newest = dates.at(-1) as string;

	// A corpus shorter than the window is windowed to itself, so everything
	// below would pass with no window in the code at all. The fixture has to
	// outlast the window or this test proves nothing.
	expect(span(dates[0], newest)).toBeGreaterThan(DEFAULT_WINDOW_DAYS);

	const cutoff = dayKey(new Date(toDay(newest).getTime() - (DEFAULT_WINDOW_DAYS - 1) * 86_400_000));
	expect(all.rows.some((row) => row.date < cutoff)).toBe(true);
	expect(seeded.rows.every((row) => row.date >= cutoff)).toBe(true);
	expect(seeded.rows.length).toBeLessThan(all.rows.length);

	// The seed still reaches the newest day, and still reads as the same table.
	expect(seeded.rows.some((row) => row.date === newest)).toBe(true);
	expect(seeded.columns).toEqual(all.columns);

	// A window is a count of days, so it straddles a month boundary and reads
	// two shards. Every older shard is skipped unread, which is the bound: two,
	// however many months the pipeline has committed.
	expect(monthsInWindow({ start: cutoff, end: newest }).length).toBeLessThanOrEqual(2);
	expect(telemetryMonths(TELEMETRY_FIXTURE).length).toBeGreaterThan(
		monthsInWindow({ start: cutoff, end: newest }).length
	);
});

test('the days the seed drops stay on disk for a pan to reach', () => {
	const seeded = telemetryRows(TELEMETRY_FIXTURE, DEFAULT_WINDOW_DAYS);
	const dates = seeded.rows.map((row) => row.date).sort();
	const back = panWindow(
		{ start: dates[0], end: dates.at(-1) as string },
		-DEFAULT_WINDOW_DAYS
	);

	// Bounding the seed must not put a day out of reach. Every month the pan
	// lands on is still a shard the browser can fetch by name.
	const shards = telemetryMonths(TELEMETRY_FIXTURE);
	expect(monthsInWindow(back).filter((month) => shards.includes(month)).length).toBeGreaterThan(0);

	const older = telemetryRows(TELEMETRY_FIXTURE).rows.filter(
		(row) => row.date >= back.start && row.date <= back.end
	);
	const seededIds = new Set(seeded.rows.map((row) => row.item_id));
	expect(older.length).toBeGreaterThan(0);
	expect(older.every((row) => !seededIds.has(row.item_id))).toBe(true);
});

/** What the fixture's own files say the Charts table has to print for a day.
 *
 * Derived here from `run.json` and `digest.json` rather than typed as constants,
 * because the oracle is that every printed cell equals the value computed
 * directly from the day's committed record. A constant would only prove the
 * page still says what it said last week.
 */
function chartCells(date: string): Record<string, string> {
	const [year, month, day] = date.split('-');
	const at = join(CANARY, 'digest', year, month, day);
	type Run = {
		items_routed?: number;
		items_prefiltered?: number;
		charts_drafted?: number;
		route_ms?: number | null;
	};
	const runs = (JSON.parse(readFileSync(join(at, 'run.json'), 'utf8')) as { runs: Run[] }).runs;
	const items = (
		JSON.parse(readFileSync(join(at, 'digest.json'), 'utf8')) as {
			items: { visual?: { kind: string; state: string } | null }[];
		}
	).items;

	const sum = (of: (run: Run) => number) => runs.reduce((total, run) => total + of(run), 0);
	const timed = runs.map((run) => run.route_ms).filter((ms): ms is number => typeof ms === 'number');
	const minutes = timed.length === 0 ? null : timed.reduce((a, b) => a + b, 0) / 60_000;
	// A diagram is a visual and is not a chart, and a chart that failed to render
	// is not one a reader ever saw.
	const published = items.filter(
		(item) => item.visual?.kind === 'chart' && item.visual.state === 'rendered'
	).length;
	const printed = (value: number | null) => (value === null ? '-' : value.toFixed(1));

	return {
		reached: String(sum((run) => (run.items_routed ?? 0) + (run.items_prefiltered ?? 0))),
		asked: String(sum((run) => run.items_routed ?? 0)),
		drafted: String(sum((run) => run.charts_drafted ?? 0)),
		published: String(published),
		minutes: printed(minutes),
		'per-chart': printed(minutes === null || published === 0 ? null : minutes / published)
	};
}

test('every chart cell equals what the day committed', async ({ page }) => {
	await page.goto('/console/');

	const dates = await page
		.locator('[data-chart-day]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-chart-day') ?? ''));
	// Newest first, and every day the manifest covers, so a day the router never
	// reached still counts towards the arm's fourteen-day window.
	expect(dates).toEqual(
		manifestDays()
			.map((day) => day.date)
			.reverse()
	);

	for (const date of dates) {
		const row = page.locator(`[data-chart-day="${date}"]`);
		for (const [cell, expected] of Object.entries(chartCells(date))) {
			await expect(row.locator(`[data-charts-cell="${cell}"]`)).toHaveText(expected);
		}
	}
});

test('the measured day prints rates, and the day with no router prints dashes', async ({
	page
}) => {
	await page.goto('/console/');

	// The attack day is the one the fixture gives router counts to. Asserting it
	// is not all zeros is what stops the oracle above passing on an empty table.
	const measured = page.locator(`[data-chart-day="${DAY}"]`);
	const cells = chartCells(DAY);
	expect(Number(cells.reached)).toBeGreaterThan(Number(cells.asked));
	expect(Number(cells.drafted)).toBeGreaterThan(Number(cells.published));
	expect(Number(cells.published)).toBeGreaterThan(0);
	await expect(measured.locator('[data-charts-cell="minutes"]')).not.toHaveText('-');
	await expect(measured.locator('[data-charts-cell="per-chart"]')).not.toHaveText('-');

	// A quiet day ran and published nothing, so its router never started. Zero
	// items reached is a measurement; zero minutes would be an invention, and a
	// per-chart cost over no charts is not a number at all.
	const quiet = page.locator(`[data-chart-day="${manifestDays()[0].date}"]`);
	await expect(quiet.locator('[data-charts-cell="reached"]')).toHaveText('0');
	await expect(quiet.locator('[data-charts-cell="published"]')).toHaveText('0');
	await expect(quiet.locator('[data-charts-cell="minutes"]')).toHaveText('-');
	await expect(quiet.locator('[data-charts-cell="per-chart"]')).toHaveText('-');
});

test('a diagram is a visual and is not a published chart', async ({ page }) => {
	await page.goto('/console/');

	const [year, month, day] = DAY.split('-');
	const items = (
		JSON.parse(
			readFileSync(join(CANARY, 'digest', year, month, day, 'digest.json'), 'utf8')
		) as { items: { visual?: { kind: string; state: string } | null }[] }
	).items;
	const visuals = items.filter((item) => item.visual != null).length;
	const charts = items.filter(
		(item) => item.visual?.kind === 'chart' && item.visual.state === 'rendered'
	).length;

	// The fixture publishes a chart and a diagram. A count that read "visuals"
	// would put the diagram in the chart arm's bill, and the arm would look twice
	// as productive as it is.
	expect(visuals).toBeGreaterThan(charts);
	await expect(
		page.locator(`[data-chart-day="${DAY}"] [data-charts-cell="published"]`)
	).toHaveText(String(charts));
});

/** The canary's own score rows and item-health rows for one date. */
function ledgers(date: string): {
	scores: Record<string, string>[];
	health: Record<string, string>[];
} {
	const health = join(CANARY, 'state', 'item-health');
	return {
		scores: readCsv(join(CANARY, 'state', 'scores.csv')).rows.filter((row) => row.date === date),
		health: readdirSync(health)
			.filter((name) => name.endsWith('.csv'))
			.flatMap((name) => readCsv(join(health, name)).rows)
			.filter((row) => row.date === date)
	};
}

function middle(values: number[]): number {
	const sorted = [...values].sort((a, b) => a - b);
	const at = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[at] : (sorted[at - 1] + sorted[at]) / 2;
}

/** Every day the fixture gave the model work on, newest first. */
function modelDays(): string[] {
	const health = join(CANARY, 'state', 'item-health');
	const scored = readCsv(join(CANARY, 'state', 'scores.csv')).rows.map((row) => row.date);
	const ran = readdirSync(health)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(health, name)).rows)
		.filter((row) => Number(row.summarize_ms) > 0)
		.map((row) => row.date);
	return [...new Set([...scored, ...ran])].sort().reverse();
}

/** What the fixture's own ledgers say the model table has to print for a day.
 *
 * Computed here from the committed CSVs rather than typed as constants, and
 * deliberately not through the page's own module: the oracle is that a printed
 * cell equals the value a second reading of the ledger produces.
 */
function modelCells(date: string): Record<string, string> {
	const { scores, health } = ledgers(date);
	const times = health.map((row) => Number(row.summarize_ms)).filter((ms) => ms > 0);
	const truthy = (value: string) => value === 'True' || value === 'true';
	const tally = (of: (row: Record<string, string>) => boolean) =>
		scores.length === 0 ? '-' : String(scores.filter(of).length);
	// Whole units, and a measurement that rounds away prints `<1` rather than the
	// `0` that would say the model ran for nothing.
	const units = (ms: number, per: number) => {
		const value = Math.round(ms / per);
		return value === 0 && ms > 0 ? '<1' : String(value);
	};
	const copied = scores.map((row) =>
		Math.max(Number(row.extractiveness), Number(row.verbatim_run))
	);
	// The cut flag is read only over the rows that carry its current meaning. An
	// older row's cell held a faithfulness gap, so adding the two would print one
	// number over two questions.
	const cutKnown = scores.filter((row) => (row.version ?? '') >= CUT_FLAG_MEANS_A_CUT_FROM);
	const readInPart = cutKnown.filter((row) => truthy(row.truncation_flagged)).length;
	// The cut is the two lengths on one row, compared. Never the post-cap count
	// against the cap, which moves the day the cap moves.
	const cutTimes = health
		.filter(
			(row) =>
				row.source_words_before_cap !== '' &&
				row.source_words !== '' &&
				Number(row.source_words_before_cap) > Number(row.source_words)
		)
		.map((row) => Number(row.summarize_ms))
		.filter((ms) => ms > 0);

	return {
		summaries: scores.length === 0 ? '-' : String(scores.length),
		'not-sure': tally((row) => row.band === 'low'),
		unsupported: tally((row) => Number(row.unsupported_numbers) > 0),
		hedge: tally((row) => truthy(row.hedge_dropped)),
		part: cutKnown.length === 0 ? '-' : String(readInPart),
		// The share is over the rows the flag still answers for, so its top and its
		// bottom are the same question.
		'part-pct':
			cutKnown.length === 0
				? '-'
				: `${Math.round((readInPart / cutKnown.length) * 100)}%`,
		copied: scores.length === 0 ? '-' : `${Math.round(middle(copied) * 100)}%`,
		'per-item':
			times.length === 0
				? '-'
				: units(middle(times), 1000) +
					(cutTimes.length === 0 ? '' : ` ${units(middle(cutTimes), 1000)} when cut short`),
		minutes:
			times.length === 0 ? '-' : units(times.reduce((total, ms) => total + ms, 0), 60_000),
		'too-long':
			health.length === 0
				? '-'
				: String(health.filter((row) => row.code === 'context_exceeded').length),
		failed:
			health.length === 0
				? '-'
				: String(health.filter((row) => row.outcome === 'failed').length)
	};
}

test('every model cell equals what the day committed', async ({ page }) => {
	await page.goto('/console/');

	const dates = await page
		.locator('[data-model-day]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-model-day') ?? ''));
	// A day the pipeline found no article on gets no row at all. A row of zeroes
	// would read as a day that went badly rather than a day with nothing in it.
	expect(dates).toEqual(modelDays());

	for (const date of dates) {
		const row = page.locator(`[data-model-day="${date}"]`);
		for (const [cell, expected] of Object.entries(modelCells(date))) {
			await expect(row.locator(`[data-model-cell="${cell}"]`)).toHaveText(expected);
		}
	}
});

test('a day the scorer never reached prints dashes, and still prints its speed', async ({
	page
}) => {
	await page.goto('/console/');

	// The attack day is the only day the fixture scored, so the day before it is
	// the scorer-off state: the model wrote summaries and nothing measured them.
	const unscored = modelDays().find((date) => ledgers(date).scores.length === 0);
	expect(unscored, 'the fixture has no day with model work and no score row').toBeDefined();

	const row = page.locator(`[data-model-day="${unscored}"]`);
	for (const cell of ['summaries', 'not-sure', 'unsupported', 'hedge', 'part', 'part-pct', 'copied']) {
		await expect(row.locator(`[data-model-cell="${cell}"]`)).toHaveText('-');
	}
	// Speed is measured by the runtime, not by the scorer, so it still prints.
	await expect(row.locator('[data-model-cell="per-item"]')).not.toHaveText('-');
	await expect(row.locator('[data-model-cell="minutes"]')).not.toHaveText('-');
	// So is a refusal. Nothing was refused for length, and zero is the answer -
	// at the committed cap no prompt can reach the window the machine reads with.
	await expect(row.locator('[data-model-cell="too-long"]')).toHaveText('0');
	// And that day cut nothing, so there is no second figure to split out.
	await expect(row.locator('[data-model-aside="per-item"]')).toHaveCount(0);

	// And the scored day is not all dashes, which is what stops the oracle above
	// passing on a table that prints nothing.
	const scored = page.locator(`[data-model-day="${DAY}"]`);
	await expect(scored.locator('[data-model-cell="summaries"]')).toHaveText(String(scoredItems()));
	await expect(scored.locator('[data-model-cell="copied"]')).not.toHaveText('-');
});

test('nothing under the heading is a score or an internal column name', async ({ page }) => {
	await page.goto('/console/');

	const section = await page.locator('[data-model-section]').innerText();

	// A value between zero and one is what the scorer emits, and none of them may
	// reach an operator: a number nobody can pull a lever on is not a report. A
	// token rate that low would itself be the failure, so this cannot misfire on
	// the candle above the table.
	expect(section).not.toMatch(/\b[01]\.\d/);

	// A ledger column name on screen makes a reader open the schema to read the
	// page. Every one of these is a real column of `state/scores.csv` or
	// `state/item-health/`.
	for (const name of [
		'hhem',
		'coverage',
		'compression',
		'extractiveness',
		'verbatim_run',
		'unsupported_numbers',
		'hedge_dropped',
		'truncation_flagged',
		'extraction_suspect',
		'determinism_violation',
		'evidential_density',
		'speculative_density',
		'scorer_version',
		'score_ms',
		'summarize_ms',
		'prefill_ms',
		'decode_ms',
		'input_tokens',
		'output_tokens',
		'cached_tokens'
	]) {
		expect(section.toLowerCase(), `${name} is printed under the heading`).not.toContain(name);
	}

	// No cell prints a decimal at all. Every figure is a count of the day's items.
	const printed = await page
		.locator('[data-model-cell]')
		.evaluateAll((cells) => cells.map((cell) => cell.textContent ?? ''));
	expect(printed.length).toBeGreaterThan(0);
	expect(printed.filter((text) => /\d\.\d/.test(text))).toEqual([]);
});

test('the candle stays first inside the section, above the table', async ({ page }) => {
	await page.goto('/console/');

	const order = await page
		.locator('[data-model-section] [data-throughput="chart"], [data-model-section] [data-model="table"]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-throughput') ?? 'table'));
	expect(order).toEqual(['chart', 'table']);

	// One heading for the whole section. The candle keeps its own name, one level
	// down, so a fourth console section is not what this became.
	await expect(page.getByRole('heading', { level: 2, name: 'What the model did' })).toBeVisible();
	await expect(
		page.getByRole('heading', { level: 3, name: 'Model tokens per second' })
	).toBeVisible();
});

test('a model change is one divider row, under the days that ran on it', () => {
	// The fixture ran one model, so the swap is asserted over the function that
	// places it. A divider drawn from a fixture that cannot change models would
	// only prove the fixture.
	const scored = (date: string, model: string) => ({
		date,
		model_id: model,
		band: 'high',
		extractiveness: '0.2',
		verbatim_run: '0.1',
		unsupported_numbers: '0',
		hedge_dropped: 'False',
		truncation_flagged: 'False'
	});

	const rows = modelWork(
		[scored('2026-08-26', 'new'), scored('2026-08-25', 'new'), scored('2026-08-24', 'old')],
		[]
	);

	expect(
		rows.map((row) => (row.kind === 'swap' ? `swap ${row.date} ${row.model}` : row.day.date))
	).toEqual(['2026-08-26', '2026-08-25', 'swap 2026-08-25 new', '2026-08-24']);

	// One model over every day is no divider at all.
	expect(
		modelWork([scored('2026-08-26', 'one'), scored('2026-08-25', 'one')], []).filter(
			(row) => row.kind === 'swap'
		)
	).toEqual([]);
});

test('a day with no summaries gets no row, and a day with no health row gets no failure count', () => {
	const health = (date: string, ms: string, outcome: string) => ({
		date,
		summarize_ms: ms,
		outcome
	});

	const rows = modelWork(
		[{ date: '2026-08-26', model_id: 'one', band: 'low' }],
		[
			health('2026-08-26', '2000', 'failed'),
			health('2026-08-25', '1500', 'ok'),
			// Fetched and thrown away before the model saw it. No summary, no row.
			health('2026-08-24', '', 'failed')
		]
	);

	const days = rows.filter((row) => row.kind === 'day').map((row) => row.day);
	expect(days.map((day) => day.date)).toEqual(['2026-08-26', '2026-08-25']);
	expect(days[0].failed).toBe(1);
	expect(days[0].notSure).toBe(1);
	// Model work, no score row: every quality figure is unknown, not zero.
	expect(days[1].summaries).toBeNull();
	expect(days[1].notSure).toBeNull();
	expect(days[1].copiedPct).toBeNull();
	expect(days[1].totalMs).toBe(1500);

	// A day with score rows and no health row cannot count failures.
	const scoredOnly = modelWork([{ date: '2026-08-26', model_id: 'one', band: 'high' }], []);
	expect(scoredOnly).toHaveLength(1);
	expect(scoredOnly[0].kind === 'day' && scoredOnly[0].day.failed).toBeNull();
	expect(scoredOnly[0].kind === 'day' && scoredOnly[0].day.perItemMs).toBeNull();
});

test('the cut flag is counted only over rows that carry the meaning it has now', () => {
	// `truncation_flagged` changed meaning at `CUT_FLAG_MEANS_A_CUT_FROM`. Before
	// that stamp the cell held the gap between two faithfulness scores; from it,
	// the cell says extract cut the article body. Two rows on one day, one either
	// side of the stamp, are what tell a reader of the new meaning apart from a
	// reader that just counts the column.
	const row = (version: string, flagged: string) => ({
		date: '2026-08-28',
		version,
		model_id: 'one',
		band: 'high',
		truncation_flagged: flagged
	});

	// `2026-08-27T20:30` is the newest stamp the committed ledger actually
	// carries. The date-stamp format is ASCII-sortable on purpose, so a stamp
	// carrying a time orders before the bare date that follows it - which is the
	// whole reason a plain string compare is enough here.
	const before = '2026-08-27T20:30';
	const after = CUT_FLAG_MEANS_A_CUT_FROM;
	expect(before < after, 'a stamp carrying a time must order before the bare date').toBe(true);

	const readInPart = (rows: Record<string, string>[]): number | null => {
		const days = modelWork(rows, []).filter((entry) => entry.kind === 'day');
		expect(days).toHaveLength(1);
		// Throws rather than falling back to a number: a silent 0 here would be
		// indistinguishable from the answer one of the assertions below expects.
		if (days[0].kind !== 'day') throw new Error('the filter above kept a divider row');
		return days[0].day.readInPart;
	};

	// One direction: the older row is flagged, the newer one is not. A reader that
	// counted the whole column would print 1. Only the newer row carries the
	// meaning, so the answer is 0 - a real number, and not the flagged row's.
	expect(readInPart([row(before, 'True'), row(after, 'False')])).toBe(0);

	// The other direction, the same pair with the flags swapped. The answer is 1,
	// which is what stops this passing on a reader that always returns null.
	expect(readInPart([row(before, 'False'), row(after, 'True')])).toBe(1);

	// A day made only of older rows holds no answer at all. Zero would say the
	// pipeline cut nothing, which those rows never measured.
	expect(readInPart([row(before, 'True'), row(before, 'True')])).toBeNull();

	// A stamp carrying a time on the boundary day is on the new side of it.
	expect(readInPart([row('2026-08-28T09:00', 'True')])).toBe(1);

	// An unstamped row reads as older. Unknown is the safe direction.
	expect(
		readInPart([{ date: '2026-08-28', model_id: 'one', truncation_flagged: 'True' }])
	).toBeNull();

	// The gate is on the one column whose meaning moved. Every other figure still
	// counts every row the day holds.
	const mixed = modelWork([row(before, 'True'), row(after, 'False')], [])[0];
	expect(mixed.kind === 'day' && mixed.day.summaries).toBe(2);
});

test('the cut share divides by the rows its own flag answers for', () => {
	const score = (version: string, flagged: string) => ({
		date: '2026-08-28',
		version,
		model_id: 'one',
		band: 'high',
		truncation_flagged: flagged
	});

	const only = (rows: Record<string, string>[]) => {
		const day = modelWork(rows, [])[0];
		if (day.kind !== 'day') throw new Error('the fixture is one day');
		return day.day;
	};

	// Four rows, one cut, and all four carry the flag's current meaning: 25
	// percent. A share over the day's whole ledger would print the same here,
	// which is why the row below is the one that separates them.
	const clean = only([
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'True'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False')
	]);
	expect(clean.readInPart).toBe(1);
	expect(clean.readInPartPct).toBe(25);

	// The same four, plus four older rows the flag no longer answers for. The
	// count is still 1 and the share is still 25 percent: dividing by eight
	// would print 13, and that 13 is a fact about the migration rather than
	// about the articles.
	const mixed = only([
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'True'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score('2026-08-27T20:30', 'True'),
		score('2026-08-27T20:30', 'True'),
		score('2026-08-27T20:30', 'False'),
		score('2026-08-27T20:30', 'False')
	]);
	expect(mixed.summaries).toBe(8);
	expect(mixed.readInPart).toBe(1);
	expect(mixed.readInPartPct).toBe(25);

	// A day with nothing the flag answers for holds no share either. Zero
	// percent would say the cap took nothing, which those rows never measured.
	expect(only([score('2026-08-27T20:30', 'True')]).readInPartPct).toBeNull();
});

test('the day splits its writing time by the articles it read only the start of', () => {
	const health = (ms: string, before: string, after: string, code = '') => ({
		date: '2026-08-28',
		summarize_ms: ms,
		outcome: 'ok',
		code,
		source_words: after,
		source_words_before_cap: before
	});

	const only = (rows: Record<string, string>[]) => {
		const day = modelWork([], rows)[0];
		if (day.kind !== 'day') throw new Error('the fixture is one day');
		return day.day;
	};

	// Two whole articles and two the cap cut. The day's median is over all four
	// and the split is over the two, so a split that quietly reported the day
	// again would print 1500 twice.
	const split = only([
		health('1000', '400', '400'),
		health('1200', '', '380'),
		health('4000', '2612', '1923'),
		health('6000', '9000', '1923')
	]);
	expect(split.perItemMs).toBe(2600);
	expect(split.perItemCutMs).toBe(5000);

	// A day that cut nothing has no second figure. Zero would say the machine
	// wrote those summaries for free.
	expect(only([health('1000', '400', '400'), health('1200', '', '380')]).perItemCutMs).toBeNull();

	// An empty cell is not a zero: a row that recorded no length before the cut
	// is not an article cut from nothing to 380 words.
	expect(only([health('1200', '', '380')]).perItemCutMs).toBeNull();

	// Refused for length is a count of the day's own rows, and zero is a real
	// answer. Null is kept for a day with no health row at all.
	expect(
		only([health('1000', '400', '400'), health('', '', '', 'context_exceeded')]).refusedForLength
	).toBe(1);
	expect(only([health('1000', '400', '400')]).refusedForLength).toBe(0);
	const scoredOnly = modelWork([{ date: '2026-08-28', model_id: 'one', band: 'high' }], [])[0];
	expect(scoredOnly.kind === 'day' && scoredOnly.day.refusedForLength).toBeNull();
});

test('the plot reads the cut off two lengths, so no ledger stamp can change what it means', () => {
	// This used to assert a gate on the score ledger's `truncation_flagged`,
	// which changed meaning at `CUT_FLAG_MEANS_A_CUT_FROM`: the plot read the
	// column raw while the day's count in the table read it only over the rows
	// stamped with its current meaning, so one page made two claims about one
	// column. The projection ends the argument. A pre-cap length standing above
	// a post-cap one has meant exactly one thing on every row ever written, so
	// there is no stamp to read and no second meaning to gate.
	const row = (before: number | null, after: number | null): TelemetryRow => ({
		date: '2026-08-28',
		run_id: '2026-08-28-1',
		item_id: 'ai-01',
		vertical: 'ai',
		source_id: 'canary',
		stage: 'publish',
		outcome: 'ok',
		code: '',
		source_words: after,
		summary_words: 205,
		source_words_before_cap: before
	});

	const marked = (before: number | null, after: number | null): boolean => {
		const placed = placeRow(row(before, after));
		if (placed.kind !== 'point') throw new Error('the fixture row is placeable');
		return placed.point.truncation_flagged;
	};

	// Cut, and drawn at the length the article actually was.
	expect(marked(4200, 1923)).toBe(true);
	// Nothing was cut, on the two shapes a run can write: the cap did not fire,
	// and the run predates the column that records what it did.
	expect(marked(2000, 2000)).toBe(false);
	expect(marked(null, 880)).toBe(false);

	// A row written before 2026-08-28 records no pre-cap length, so it is drawn
	// at the length that survived. That is the honest reading: the ledger holds
	// no answer to what the article was, and inventing a diamond on it would
	// claim a cut nobody measured.
	const older = placeRow(row(null, 880));
	expect(older.kind === 'point' && older.point.source_words).toBe(880);
	expect(older.kind === 'point' && 'source_seen_words' in older.point).toBe(false);
});

/** What the canary's own item-health rows say the source table has to print.
 *
 * Recomputed here from the CSV rather than typed as constants, and deliberately
 * not through the page's own module: the oracle is that a printed cell equals
 * the value a second, independent reading of the ledger produces.
 *
 * The window ends on the newest day the ledger holds, so a fixture that grows a
 * day moves this with it instead of going stale. Its length is the page's own -
 * the section follows the window control, so a length chosen here would be
 * asserting against a table nobody is looking at.
 */
function sourceTable(days: number): {
	rows: { sourceId: string; cut: number; articles: number; share: string; longest: string }[];
	moreSources: number;
	moreCuts: number;
	losses: number[];
} {
	const dir = join(CANARY, 'state', 'item-health');
	const all = readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(dir, name)).rows);
	const newest = all.map((row) => row.date).sort().at(-1) as string;
	const first = new Date(
		new Date(`${newest}T00:00:00Z`).getTime() - (days - 1) * 86_400_000
	)
		.toISOString()
		.slice(0, 10);

	// One entry per article, not per row: a run writes a row for every item it
	// plans, so counting rows counts a re-run twice.
	const articles = new Map<string, { source: string; before: number | null; after: number | null }>();
	for (const row of all) {
		if (row.date < first || row.date > newest) continue;
		const cell = (name: string) => (row[name] === '' ? null : Number(row[name]));
		const key = `${row.source_id}/${row.url_key}`;
		const held = articles.get(key);
		const before = cell('source_words_before_cap');
		if (held === undefined) {
			articles.set(key, { source: row.source_id, before, after: cell('source_words') });
		} else if (before !== null && (held.before === null || before > held.before)) {
			held.before = before;
			held.after = cell('source_words');
		}
	}

	const bySource = new Map<string, { before: number | null; after: number | null }[]>();
	for (const entry of articles.values()) {
		bySource.set(entry.source, [...(bySource.get(entry.source) ?? []), entry]);
	}

	const losses: number[] = [];
	const found = [];
	for (const [sourceId, group] of bySource) {
		const cut = group
			.map((a) => (a.before !== null && a.after !== null && a.before > a.after ? a.before - a.after : null))
			.filter((n): n is number => n !== null);
		if (cut.length === 0) continue;
		losses.push(...cut);
		const lengths = group.map((a) => a.before).filter((n): n is number => n !== null);
		found.push({
			sourceId,
			cut: cut.length,
			articles: group.length,
			share:
				group.length < MIN_ATTEMPTS_FOR_RATE
					? '-'
					: `${Math.round((cut.length / group.length) * 100)}%`,
			longest: lengths.length === 0 ? '-' : grouped(Math.max(...lengths))
		});
	}
	found.sort((a, b) => b.cut - a.cut || a.sourceId.localeCompare(b.sourceId));
	const rest = found.slice(SOURCE_CUT_ROWS);
	return {
		rows: found.slice(0, SOURCE_CUT_ROWS),
		moreSources: rest.length,
		moreCuts: rest.reduce((total, source) => total + source.cut, 0),
		losses: losses.sort((a, b) => a - b)
	};
}

test('the source table names every source the cap cut, and no other', async ({ page }) => {
	await page.goto('/console/');

	// The window is the page's own. The section follows the shared control, so a
	// number picked here would be an oracle over a table nobody is shown.
	// `console-window.spec.ts` drives the control and proves the contents move.
	const days = Number(
		await page.locator('[data-windowed="source-cuts"]').getAttribute('data-window-days')
	);
	expect(days, 'the section publishes no window, so the oracle below spans nothing').toBeGreaterThan(
		0
	);
	const expected = sourceTable(days);
	// The fixture has to hold more than the table prints, or the sort, the cap
	// and the sentence under it are all asserted against nothing.
	expect(expected.rows.length, 'the fixture cuts fewer sources than the table prints').toBe(
		SOURCE_CUT_ROWS
	);
	expect(expected.moreSources, 'the fixture never overflows, so the sentence is untested').toBeGreaterThan(0);

	const named = await page
		.locator('[data-source-cut]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-source-cut') ?? ''));
	// One row per source with at least one cut article, worst first. A source
	// that lost nothing is not here, and neither is one whose only cut fell
	// outside the window.
	expect(named).toEqual(expected.rows.map((source) => source.sourceId));
	expect(named).not.toContain('no-length');

	for (const source of expected.rows) {
		const row = page.locator(`[data-source-cut="${source.sourceId}"]`);
		await expect(row.locator('[data-source-cell="cut"]')).toHaveText(String(source.cut));
		await expect(row.locator('[data-source-cell="articles"]')).toHaveText(String(source.articles));
		await expect(row.locator('[data-source-cell="share"]')).toHaveText(source.share);
		await expect(row.locator('[data-source-cell="longest"]')).toHaveText(source.longest);
	}

	await expect(page.locator('[data-source-cuts-more]')).toHaveText(
		`${expected.moreSources} more sources had ${expected.moreCuts} cuts between them.`
	);
});

test('the source table counts articles, not rows, and reads its lengths off the right cell', async ({
	page
}) => {
	await page.goto('/console/');

	// One of this source's articles was written by two runs. A row count says
	// eight; the table's own sentence says articles, and it published seven.
	const dir = join(CANARY, 'state', 'item-health');
	const rows = readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(dir, name)).rows)
		.filter((row) => row.source_id === 'cut-a');
	expect(rows.length, 'no article is written twice, so the count below proves nothing').toBe(8);
	await expect(page.locator('[data-source-cut="cut-a"] [data-source-cell="articles"]')).toHaveText(
		'7'
	);

	// Its longest article was never cut. A column that read the longest cut
	// article would print 6,123 here.
	await expect(page.locator('[data-source-cut="cut-a"] [data-source-cell="longest"]')).toHaveText(
		'9,000'
	);

	// And this one's longest surviving body sits on a row that recorded no
	// length before the cut. Reading `source_words` would print 30,000; the
	// question is how long the article was, and that row never answered it.
	await expect(page.locator('[data-source-cut="cut-b"] [data-source-cell="longest"]')).toHaveText(
		'5,423'
	);
});

test('a share nothing supports prints a dash, never a percentage', async ({ page }) => {
	await page.goto('/console/');

	// Four articles is under `console.min_attempts_for_rate`, so there is no
	// share to print. The count and the denominator are still measurements and
	// still print.
	const thin = page.locator('[data-source-cut="cut-c"]');
	await expect(thin, 'the fixture lost its thin source, so the dash is untested').toHaveCount(1);
	await expect(thin.locator('[data-source-cell="articles"]')).toHaveText('4');
	expect(4).toBeLessThan(MIN_ATTEMPTS_FOR_RATE);
	await expect(thin.locator('[data-source-cell="share"]')).toHaveText('-');
	await expect(thin.locator('[data-source-cell="cut"]')).toHaveText('4');

	// And a source over the floor does print one, which is what stops this
	// passing on a column of dashes.
	await expect(
		page.locator('[data-source-cut="cut-a"] [data-source-cell="share"]')
	).toHaveText('86%');
});

test('what the cut cost is printed with the number of articles behind it', async ({ page }) => {
	await page.goto('/console/');

	const days = Number(
		await page.locator('[data-windowed="source-cuts"]').getAttribute('data-window-days')
	);
	const { losses } = sourceTable(days);
	const median = losses[Math.floor(losses.length / 2)];
	const max = losses[losses.length - 1];
	// A median equal to its own maximum is one number printed twice. The fixture
	// loses a different amount from every article so the two are two facts.
	expect(median).toBeLessThan(max);

	await expect(page.locator('[data-source-cuts-cost]')).toHaveText(
		`${losses.length} articles were cut short. Half of them lost more than ${grouped(median)} words each, and the longest lost ${grouped(max)}.`
	);
});

test('a source whose lengths were never recorded is absent, and reads as unknown', () => {
	// The state the whole `-` rule exists for, driven straight at the reader
	// because the table cannot reach it: a source is listed only because a row
	// recorded a length before the cut, so a source with only empty cells and a
	// source on the table are two different sets by construction.
	const migrated = (source: string, index: number) => ({
		date: '2026-08-28',
		source_id: source,
		url_key: `${source}-${index}`,
		source_words: '5000',
		source_words_before_cap: ''
	});

	// Seven days here is this test's own window, not the page's. The function
	// takes the span it is given, and these rows all sit on one day.
	const nothing = sourceCuts([migrated('a', 0), migrated('a', 1)], {
		days: 7,
		minAttempts: MIN_ATTEMPTS_FOR_RATE,
		limit: SOURCE_CUT_ROWS
	});
	// Not listed with a zero. Zero cuts and no measurement are different facts,
	// and the zero is the one nobody checks.
	expect(nothing.rows).toEqual([]);
	// And the page says which of the two it is: nothing recorded a length here,
	// so the table is not empty - it cannot answer yet.
	expect(nothing.measured).toBe(false);
	expect(nothing.cost).toBeNull();

	// One row of that source now records a length, and it was cut. The source
	// arrives, and the longest article is the one length on record - never the
	// 5,000-word body beside it that nobody measured before the cut.
	const some = sourceCuts(
		[
			migrated('a', 0),
			{
				date: '2026-08-28',
				source_id: 'a',
				url_key: 'a-1',
				source_words: '1923',
				source_words_before_cap: '2612'
			}
		],
		{ days: 7, minAttempts: MIN_ATTEMPTS_FOR_RATE, limit: SOURCE_CUT_ROWS }
	);
	expect(some.measured).toBe(true);
	expect(some.rows).toHaveLength(1);
	expect(some.rows[0].cut).toBe(1);
	expect(some.rows[0].articles).toBe(2);
	// Two articles is under the floor, so there is no share to print.
	expect(some.rows[0].sharePct).toBeNull();
	expect(some.rows[0].longestWords).toBe(2612);
	expect(some.cost).toEqual({ n: 1, median: 689, max: 689 });

	// Empty is not zero on the other cell either: a row with no surviving length
	// is not an article cut to nothing.
	expect(
		sourceCuts(
			[{ date: '2026-08-28', source_id: 'a', url_key: 'a-0', source_words: '', source_words_before_cap: '2612' }],
			{ days: 7, minAttempts: MIN_ATTEMPTS_FOR_RATE, limit: SOURCE_CUT_ROWS }
		).rows
	).toEqual([]);
});

