import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	compressionView,
	grouped,
	placeRow,
	type TelemetryRow
} from '../src/lib/charts/series';
import { axisLabels, centreOffset, spanLabel } from '../src/lib/charts/run-history';
import { dayKey, monthsInWindow, panWindow, toDay, windowOfDays } from '../src/lib/charts/viewport';
import { CUT_FLAG_MEANS_A_CUT_FROM, modelWork } from '../src/lib/server/model-work';
import { readCsv, telemetryMonths, telemetryRows } from '../src/lib/server/payload';
import { failing, preserves, reliability, type FeedRecord } from '../src/lib/feed-health';

/**
 * The console says whether the runs worked and which feeds are broken.
 *
 * It runs against the canary build, whose fixtures carry one run of each colour
 * and one feed of each kind the page has to tell apart. The canary build writes
 * the item-health ledger because the console reads timing medians from it, and
 * the score ledger because the model table counts its rows. The failed-item
 * list is the section with nothing to show, which proves the page keeps
 * rendering when one of its sources holds nothing.
 *
 * The band section has its own file, `console-compression.spec.ts`.
 *
 * See `backend/utilities/build_canary_day.py` for the fixture.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

/** A run strip at the pitch `cellFor` settles on for a page-wide frame: a 16px
 * cell and a 4px gap. The axis is thinned against that room, so a test about it
 * has to state it. `density` is `chart.tick_density`. */
const STRIP = { density: 6, pitch: 20 };

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

/** Every span the control offers, from the same knob the control reads. */
const WINDOW_PRESETS = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console?: { window_presets?: number[] } }
).console?.window_presets ?? [7, 14, 30, 90];

/** Which end of the window today sits on, from the knob the page reads. */
const TODAY_ANCHOR = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console?: { today_anchor?: 'right' | 'centre' } }
).console?.today_anchor ?? 'right';

/** The span every windowed surface opens on, hung off the build clock the way
 * the page hangs it. Both daily tables follow the control since 2026-08-31, so
 * a test that expected every committed day would fail on the two the fixture
 * puts before the default window reaches back to. */
function openWindow(dates: string[]) {
	return windowOfDays(
		dates,
		new Date().toISOString().slice(0, 10),
		DEFAULT_WINDOW_DAYS,
		TODAY_ANCHOR
	);
}

/** Every window control is disabled in the prerendered document and enabled on
 * mount, so a click before this just times out. */
async function hydrated(page: Page) {
	await expect(
		page.locator(`[data-window-preset="${DEFAULT_WINDOW_DAYS}"] input`)
	).toBeEnabled();
}

/** Click the label, never the input: a span inside it takes the pointer. */
async function setWindow(page: Page, days: number) {
	await page.locator(`label[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

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
	return shardRows(join(CANARY, 'state', 'scores')).length;
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
	expect(axisLabels([], STRIP)).toEqual([]);
	expect(axisLabels(['2026-08-20'], STRIP)).toEqual([
		{ column: 1, text: '20 Aug 2026', align: 'end' }
	]);

	// Two to six days cannot carry a cadence, so the whole span is said once.
	expect(spanLabel('2026-08-18', '2026-08-20')).toBe('18-20 Aug 2026');
	expect(spanLabel('2026-07-30', '2026-08-02')).toBe('30 Jul - 2 Aug 2026');
	expect(spanLabel('2025-12-30', '2026-01-02')).toBe('30 Dec 2025 - 2 Jan 2026');
	expect(axisLabels(days('2026-08-15', 4), STRIP)).toEqual([
		{ column: 4, text: '15-18 Aug 2026', align: 'end' }
	]);
});

test('a longer run carries both ends and as many between them as fit', () => {
	const twenty = axisLabels(days('2026-08-01', 20), STRIP);

	// The ceiling offers six columns over twenty days. At a 20px pitch the strip
	// is 380px wide, and a date is about 64px, so six of them cannot be drawn.
	// The rule drops to three rather than letting two of them touch.
	expect(twenty.map((label) => label.column)).toEqual([1, 12, 20]);
	expect(twenty.map((label) => label.text)).toEqual(['1 Aug 2026', '12 Aug', '20 Aug']);
	expect(twenty.map((label) => label.align)).toEqual(['start', 'centre', 'end']);

	// A strip with three times the room carries every column the ceiling allows.
	const wide = axisLabels(days('2026-08-01', 20), { density: STRIP.density, pitch: 60 });
	expect(wide.map((label) => label.column)).toEqual([1, 5, 9, 12, 16, 20]);
});

test('the year is stated on the first label that changes it, and not again', () => {
	const across = axisLabels(days('2025-12-20', 30), { density: STRIP.density, pitch: 60 });

	expect(across.map((label) => label.text)).toEqual([
		'20 Dec 2025',
		'26 Dec',
		'1 Jan 2026',
		'6 Jan',
		'12 Jan',
		'18 Jan'
	]);
});

test('a strip shares its spare room, and a strip with none keeps its first column', () => {
	// Half the difference, rounded, so the two margins differ by at most a pixel.
	expect(centreOffset(1326, 300)).toBe(513);
	expect(centreOffset(1326, 1290)).toBe(18);

	// An overflowing strip has no spare room to divide, and an offset there
	// would push its first column out of reach of the scroll.
	expect(centreOffset(360, 1290)).toBe(0);
	expect(centreOffset(300, 300)).toBe(0);

	// Nothing has measured the frame yet - the server, or the first frame - so
	// there is no room to share and the strip starts where it always did.
	expect(centreOffset(null, 300)).toBe(0);
	expect(centreOffset(0, 300)).toBe(0);
	expect(centreOffset(1326, 0)).toBe(0);
});

test('the strip reads oldest to newest, left to right', async ({ page }) => {
	await page.goto('/console/');

	const columns = page.locator('[data-day]');
	const dates = await columns.evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-day') ?? '')
	);
	// The window's own calendar, one column a day, consecutive and oldest first.
	// The days that carried a run are a subset of it in the same order.
	expect(dates.length).toBe(DEFAULT_WINDOW_DAYS);
	expect(dates).toEqual(days(dates[0], dates.length));
	const ran = manifestDays().map((day) => day.date);
	expect(dates.filter((date) => ran.includes(date))).toEqual(ran);

	// Chronology a reader can see, not only one the DOM asserts.
	const boxes = await columns.evaluateAll(TO_BOX);
	for (let index = 1; index < boxes.length; index += 1) {
		expect(boxes[index].x).toBeGreaterThan(boxes[index - 1].x);
	}
});

test('every recorded run gets a square, and nothing else does', async ({ page }) => {
	await page.goto('/console/');

	const expected = manifestDays();
	// One column a day of the WINDOW, not one a manifest. An empty column is the
	// fact the strip exists to show, and the days with runs are a subset of it.
	await expect(page.locator('[data-day]')).toHaveCount(DEFAULT_WINDOW_DAYS);
	await expect(page.locator('[data-health]')).toHaveCount(
		expected.reduce((total, day) => total + day.runs, 0)
	);

	// A scheduled run that never wrote a manifest has left no evidence, so the
	// strip cannot draw a slot for it without inventing one.
	for (const day of expected) {
		await expect(page.locator(`[data-day="${day.date}"] [data-health]`)).toHaveCount(day.runs);
	}

	// And every other column of the window is drawn and empty.
	const withRuns = new Set(expected.map((day) => day.date));
	const drawn = await page
		.locator('[data-day]')
		.evaluateAll((nodes) =>
			nodes.map((node) => [
				node.getAttribute('data-day') ?? '',
				node.querySelectorAll('[data-health]').length
			])
		);
	const empties = drawn.filter(([date]) => !withRuns.has(date as string));
	expect(empties.length, 'the window carries no empty day, so the rule is untested').toBeGreaterThan(
		0
	);
	expect(empties.every(([, runs]) => runs === 0)).toBe(true);
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

	// Every day's run 1 sits on the same line, or the strip is a scatter. Only
	// the days that carry a run have one; an empty column has no baseline to be
	// on and is not evidence of a scatter.
	const baselines = await page
		.locator('[data-day]')
		.evaluateAll((nodes) =>
			nodes
				.map((node) => node.querySelector('[data-health]'))
				.filter((square): square is Element => square !== null)
				.map((square) => square.getBoundingClientRect().bottom)
		);
	expect(baselines.length).toBeGreaterThan(1);
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

test('a strip that cannot fill its frame is centred in it', async ({ page }) => {
	// Where an OVERFLOWING strip opens and where an UNDERFULL one sits are two
	// questions, and `today_anchor` only answers the first. Anchored left, the
	// spare room piled up on the right - and the right of a time axis whose last
	// column is today is where a reader looks for the days that just happened,
	// so it read as a run that had stopped. Centred, the spare room is on both
	// sides and belongs to neither end.
	//
	// The narrowest preset on purpose. At the default window thirty columns fill
	// a page-wide frame, so left and right and centred are the same thing there
	// and the premise below could not hold.
	await page.setViewportSize(UNDERFULL_VIEWPORT);
	await page.goto('/console/');
	await hydrated(page);
	await setWindow(page, Math.min(...WINDOW_PRESETS));

	const [strip] = await page.locator('[data-run-history]').evaluateAll(TO_BOX);
	const columns = await page.locator('[data-day]').evaluateAll(TO_BOX);

	// The premise: fewer days than the strip has room for. Without it the test
	// passes on a full strip, where every alignment is the same thing.
	const drawn = columns[columns.length - 1].right - columns[0].x;
	expect(drawn, 'the strip is full, so alignment cannot be told apart').toBeLessThan(
		strip.width - 2
	);

	const before = columns[0].x - strip.x;
	const after = strip.right - columns[columns.length - 1].right;
	expect(before, 'the strip is not centred: the room before it').toBeGreaterThan(1);
	expect(Math.abs(before - after), 'the spare room is not shared evenly').toBeLessThanOrEqual(2);
});

test('THE ORACLE: the run strip fills its frame, keeps a cadence and reads a day', async ({
	page
}) => {
	// Three defects, one panel. The strip drew only the days that carried a run,
	// so a thirty-day window drew a third of a page-wide frame and the rest read
	// as a chart that failed to load; the axis carried two labels because eleven
	// narrow columns have room for two; and the only way to read a square was a
	// native tooltip, which no thumb and no keyboard can reach.
	await page.setViewportSize({ width: 1440, height: 1000 });
	await page.goto('/console/');
	await hydrated(page);

	const [strip] = await page.locator('[data-run-history]').evaluateAll(TO_BOX);
	const columns = await page.locator('[data-day]').evaluateAll(TO_BOX);
	expect(columns.length).toBe(DEFAULT_WINDOW_DAYS);

	const drawn = columns[columns.length - 1].right - columns[0].x;
	expect(
		drawn / strip.width,
		`the strip drew ${Math.round(drawn)} of ${Math.round(strip.width)} px`
	).toBeGreaterThanOrEqual(0.7);

	// A cadence needs at least three marks. Two is a pair of endpoints, which
	// says the span and nothing about where in it a run sits.
	const labels = await page
		.locator('[data-axis-label]')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));
	expect(labels.length, `the axis drew ${labels.join(', ')}`).toBeGreaterThanOrEqual(3);

	// The oldest and the newest column print two different days, each with a
	// line per run recorded on it. One column that printed both would be a strip
	// that never moved.
	const readout = page.locator('[data-readout="run-health"]');
	const head = readout.locator('[data-readout-day]');
	await expect(head).toHaveCount(1);

	const read = async (at: number) => {
		const column = page.locator('[data-day]').nth(at);
		await column.hover();
		await expect(page.locator(`[data-day][data-day-selected]`)).toHaveCount(1);
		return {
			day: (await head.innerText()).trim(),
			rows: await readout
				.locator('[data-readout-row]')
				.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''))
		};
	};

	const oldest = await read(0);
	const newest = await read(columns.length - 1);
	expect(oldest.day, 'the oldest and the newest column print the same day').not.toBe(newest.day);

	// The newest column of the canary is a day that ran, so it prints a line per
	// run and every line is a run rather than a stage.
	const runs = await page.locator('[data-day]').last().locator('[data-health]').count();
	expect(runs, 'the newest column carries no run, so the per-run rule is untested').toBeGreaterThan(
		0
	);
	expect(newest.rows).toEqual(
		Array.from({ length: runs }, (_, index) => `Run ${index + 1}`)
	);

	// And the standing key is gone. The readout prints the swatch and the word
	// for the run it is on, so a key beside it would draw the same pair twice.
	await expect(page.locator('[data-windowed="run-health"] ul')).toHaveCount(0);
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

	// Nearest to a rest first. `canary-flaky` has failed every run it was asked,
	// `canary-empty` answered once before its two blank runs, and `canary-gone`
	// has one failure. The full ordering rule is held in console-feeds.spec.ts,
	// against the page's own published streaks rather than against this list.
	const named = await page
		.locator('[data-feed]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-feed')));
	expect(named).toEqual(['canary-flaky', 'canary-empty', 'canary-gone']);
});

/** The cap the feed list draws with, from the file the page reads it from. */
const FEED_ROWS =
	(
		JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
		) as { console?: { feed_rows?: number } }
	).console?.feed_rows ?? 10;

/** The threshold under which this page prints counts and no rate. */
const MIN_ATTEMPTS =
	(
		JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
		) as { console?: { min_attempts_for_rate?: number } }
	).console?.min_attempts_for_rate ?? 5;

/** A feed-health ledger, read again independently of the page.
 *
 * The CANARY tree, because that is what `build:canary` built the site from.
 * Reading `state/` here would compare the page to a ledger it never saw.
 */
function feedLedger(root: string): FeedRecord[] {
	const dir = join(root, 'state', 'feed-health');
	const rows: FeedRecord[] = [];
	for (const shard of readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.sort()) {
		const lines = readFileSync(join(dir, shard), 'utf8').trim().split(/\r?\n/);
		const head = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cell = line.split(',');
			const row = new Map(head.map((name, index) => [name, cell[index] ?? '']));
			rows.push({
				date: row.get('date') ?? '',
				runId: row.get('run_id') ?? '',
				outcome: row.get('outcome') ?? '',
				items: Number(row.get('items') ?? 0) || 0,
				feedId: row.get('feed_id') ?? ''
			});
		}
	}
	return rows;
}

/** The clean count, the denominator and the span, computed here from scratch.
 *
 * A read is a row that asked the feed. A rest and a robots answer are neither -
 * neither one asked whether the feed still works - so a source the pipeline has
 * only ever been refused by is in neither count. Until 2026-09-03 a refusal was
 * counted as an ask, which reported a source we have never read as one that had
 * never failed.
 */
function recordByHand(rows: FeedRecord[]) {
	const read = new Map<string, FeedRecord[]>();
	const seen = new Set<string>();
	for (const row of rows) {
		seen.add(row.feedId);
		if (preserves(row)) continue;
		read.set(row.feedId, [...(read.get(row.feedId) ?? []), row]);
	}
	const clean: string[] = [];
	const broken: string[] = [];
	for (const [feedId, reads] of read) {
		if (reads.some(failing)) broken.push(feedId);
		else clean.push(feedId);
	}
	const byName = (a: string, b: string) => a.localeCompare(b);
	return {
		clean: clean.sort(byName),
		broken: broken.sort(byName),
		checked: read.size,
		ineligible: [...seen].filter((feedId) => !read.has(feedId)).sort(byName),
		runs: new Set(rows.map((row) => row.runId)).size
	};
}

test('THE ORACLE: the feed headline carries its own denominator and span', async ({ page }) => {
	await page.goto('/console/');

	const byHand = recordByHand(feedLedger(CANARY));
	// Read against a fact the fixture owns, never against a locator count: a
	// renamed attribute would make every number zero and switch this off.
	expect(byHand.checked, 'the canary ledger asked no feed at all').toBeGreaterThan(0);
	expect(byHand.clean.length, 'the canary has no clean feed to name').toBeGreaterThan(0);
	expect(byHand.broken.length, 'the canary has no failing feed, so the list is empty').toBeGreaterThan(
		0
	);

	const headline = page.locator('[data-feed-reliability]');
	await expect(headline, 'the feed section prints no denominator').toHaveCount(1);
	await expect(headline).toHaveAttribute('data-feed-clean', String(byHand.clean.length));
	await expect(headline).toHaveAttribute('data-feed-checked', String(byHand.checked));
	await expect(headline).toHaveAttribute('data-feed-runs', String(byHand.runs));
	// The numbers in the attributes are also the numbers in the type. An
	// attribute nobody reads and a sentence that says something else is exactly
	// the shape this section had before.
	await expect(headline).toContainText(`${byHand.clean.length} of ${byHand.checked} feeds`);
	await expect(headline).toContainText(String(byHand.runs));
	// The record's depth decides which of the two sentences prints, and the
	// canary is deep enough for the measured one.
	await expect(headline).toHaveAttribute(
		'data-feed-reliability',
		byHand.runs >= MIN_ATTEMPTS ? 'measured' : 'shallow'
	);
});

test('THE ORACLE: the disclosed names are exactly the feeds that never failed', async ({
	page
}) => {
	await page.goto('/console/');

	const byHand = recordByHand(feedLedger(CANARY));
	const named = await page
		.locator('[data-feed-clean-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-clean-name') ?? ''));

	expect(named).toEqual(byHand.clean);
	// And the two lists are disjoint: no feed is both clean and listed as broken.
	const listed = await page
		.locator('[data-feed]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-feed') ?? ''));
	expect(named.filter((feedId) => listed.includes(feedId))).toEqual([]);
});

test('THE ORACLE: the failure list is capped and its tail counts the remainder', async ({
	page
}) => {
	await page.goto('/console/');

	const byHand = recordByHand(feedLedger(CANARY));
	const table = page.locator('[data-feeds="table"]');
	const drawn = Number(await table.getAttribute('data-feeds-drawn'));
	const hidden = Number(await table.getAttribute('data-feeds-hidden'));

	// The identity that catches a cap dropping rows without counting them. It
	// holds at zero hidden, which is what makes it worth asserting on a fixture
	// the cap does not bite.
	expect(drawn + hidden, 'the cap lost a feed on the way past it').toBe(byHand.broken.length);
	expect(drawn).toBeLessThanOrEqual(FEED_ROWS);
	expect(drawn).toBe(Math.min(byHand.broken.length, FEED_ROWS));
	await expect(page.locator('[data-feed]')).toHaveCount(drawn);

	const tail = page.locator('[data-feeds-more]');
	if (hidden === 0) {
		// A sentence saying nothing is hidden is a line an operator reads and
		// learns nothing from.
		await expect(tail).toHaveCount(0);
	} else {
		await expect(tail).toContainText(`${hidden} more feed`);
	}
});

test('a record too shallow for a rate says so instead of printing one', () => {
	// The canary is deep enough, so the third state is driven here rather than
	// left to a sentence that never prints. Two runs deep, "has never failed"
	// means "did not fail twice", and the page has to say which it means.
	const shallow: FeedRecord[] = [
		{ feedId: 'a-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'ok', items: 9 },
		{ feedId: 'a-wire', date: '2026-08-02', runId: '2026-08-02-1', outcome: 'ok', items: 9 },
		{ feedId: 'b-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'transient', items: 0 }
	];
	const shallowRecord = reliability(shallow);
	expect(shallowRecord.runs).toBe(2);
	expect(shallowRecord.runs).toBeLessThan(MIN_ATTEMPTS);
	expect(shallowRecord.clean).toEqual(['a-wire']);
	expect(shallowRecord.checked).toBe(2);
	expect(shallowRecord.failed).toBe(1);

	// A feed nobody has asked is neither clean nor broken, so it is in neither
	// number. Counting a rest as a clean read is how a dead feed joins the
	// reliable list.
	const rested: FeedRecord[] = [
		...shallow,
		{ feedId: 'c-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'skipped', items: 0 }
	];
	const withRest = reliability(rested);
	expect(withRest.checked).toBe(2);
	expect(withRest.clean).toEqual(['a-wire']);
	// The run count is every run on record, rest or no rest.
	expect(withRest.runs).toBe(2);
	// And the partition holds, always.
	expect(withRest.clean.length + withRest.failed).toBe(withRest.checked);
});

test('the committed ledger is deeper than the cap, so the tail sentence has work to do', () => {
	// The canary cannot show a capped list, so the numbers the production build
	// prints are pinned here off the ledger the production build reads. The
	// click-through is the section-12 smoke.
	const real = recordByHand(feedLedger(resolve(process.cwd(), '..')));
	expect(real.checked, 'no committed feed-health ledger - the read is broken').toBeGreaterThan(0);
	expect(
		real.broken.length,
		'the committed ledger holds fewer failing feeds than the cap, so nothing is hidden'
	).toBeGreaterThan(FEED_ROWS);
	expect(real.runs).toBeGreaterThanOrEqual(MIN_ATTEMPTS);
	expect(real.clean.length + real.broken.length).toBe(real.checked);

	const measured = reliability(feedLedger(resolve(process.cwd(), '..')));
	expect(measured.clean).toEqual(real.clean);
	expect(measured.checked).toBe(real.checked);
	expect(measured.runs).toBe(real.runs);
	expect(measured.failed).toBe(real.broken.length);
});

test('stage medians come from item health, not the score ledger', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.getByText('Time per item, by stage')).toBeVisible();
	// The legend, not the axis: the largest median is printed in both places, so
	// an unscoped match is ambiguous the moment one stage is the slowest.
	await expect(page.locator('[data-readout="timings"] [data-readout-row="fetch"]')).toContainText(
		'200 ms'
	);
	await expect(page.locator('[data-readout="timings"] [data-readout-row="extract"]')).toContainText(
		'30 ms'
	);
	await expect(
		page.locator('[data-readout="timings"] [data-readout-row="summarize"]')
	).toContainText('700 ms');
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
		.locator('[data-timing="chart"] [data-readout-row]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				stage: node.getAttribute('data-readout-row') ?? '',
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

/** What the timing chart drew for one stage, read off the chart itself.
 *
 * The chart draws the window the page is set to rather than the days that
 * happen to carry a row. So a count typed into a test here would have to be
 * re-typed every time a preset moved or the fixture grew, and it would go stale
 * silently. The plot publishes the span it drew, and it draws one mark for every
 * day it has a number for - a filled dot for a measured time, an open dot for a
 * measured zero - so the days it timed nothing on are the difference between
 * the two.
 */
async function drewFor(
	page: Page,
	stage: string
): Promise<{ days: number; filled: number; zeros: number; blank: number }> {
	const plot = page.locator('[data-timing="plot"]');
	const days = Number(await plot.getAttribute('data-timing-days'));
	expect(days, 'the chart must publish the span it drew').toBeGreaterThan(0);
	const { filled, zeros } = await plot.evaluate(
		(svg, key) => ({
			filled: svg.querySelectorAll(`circle[data-stage-mark="${key}"]`).length,
			zeros: svg.querySelectorAll(`circle[data-stage-zero="${key}"]`).length
		}),
		stage
	);
	return { days, filled, zeros, blank: days - filled - zeros };
}

test('a stage with no number draws a gap, never a plunge to the axis floor', async ({ page }) => {
	await page.goto('/console/');

	// This read `score` until 2026-08-31, when that stage left this chart for the
	// Model route - it runs after the summary is written, so nothing waits on it.
	// `fetch` carries the same shape: the canary times it on some days of the
	// window and not on others. A zero clamped onto a log axis would draw the
	// line falling to the bottom of the plot, which says the stage got a thousand
	// times faster. The chart breaks the line and names the loss.
	await expect(page.locator('[data-stage-mark="fetch"]')).not.toHaveCount(0);
	const fetched = await drewFor(page, 'fetch');
	expect(fetched.blank, 'the fixture leaves fetch no gap to name').toBeGreaterThan(0);
	// One sentence for the whole chart, not one per stage. It was three notes
	// saying one window-level fact three times until 2026-09-01.
	const note = page.locator('[data-timing-coverage]');
	await expect(note, 'the window is part-timed, so it owes one sentence').toHaveCount(1);
	await expect(note).toContainText(`of these ${fetched.days} days`);

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

	// The measured zero is named in type, once for the chart rather than once for
	// the stage that happened to have one.
	const drewExtract = await drewFor(page, 'extract');
	expect(drewExtract.zeros, 'the fixture has no measured zero to name').toBeGreaterThan(0);
	await expect(page.locator('[data-timing-zero-key]')).toHaveText(
		'An open dot on the baseline is a day a stage took under 1 ms an item, which is faster than we can time.'
	);

	// The partly timed day is in the one coverage sentence, as the items it
	// reached against the items the days held. The denominator is the day's own
	// item count and never the sum of the stages' totals.
	const note = page.locator('[data-timing-coverage]');
	const low = Number(await note.getAttribute('data-coverage-timed-low'));
	const high = Number(await note.getAttribute('data-coverage-timed-high'));
	const items = Number(await note.getAttribute('data-coverage-items'));
	expect(items, 'the chart publishes no item denominator').toBeGreaterThan(0);
	expect(low, 'the fixture times every item, so the numerator says nothing').toBeLessThan(items);
	// The stages reached different amounts of the same days here, so the
	// numerator is a range rather than one stage's count passed off as the whole.
	expect(high, 'the fixture leaves the stages agreeing, so the range is untested').toBeGreaterThan(
		low
	);
	await expect(note).toContainText(`${low} to ${high} of the ${items} items on them`);

	// One note for the chart, and the count no longer scales with the series.
	await expect(page.locator('[data-timing-note]')).toHaveCount(0);

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
	// Lending them to the stages says the slowest one is the failing one.
	expect(source).not.toContain('--band-');
	// Three stages since 2026-08-31: `score` left this chart for the Model route,
	// and `--series-4` went with it. One series per stage and no spare.
	for (const series of ['--series-1', '--series-2', '--series-3']) {
		expect(source).toContain(series);
	}
	expect(source, 'a fourth series here means a fourth stage nobody declared').not.toContain(
		'--series-4'
	);
});

test('reading and writing are drawn as separate candles per day', async ({ page }) => {
	await page.goto('/console/model/');

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
	await page.goto('/console/model/');

	const newest = page.locator('[data-candle="write"][data-date="2026-08-20"]');
	const caption = await newest.locator('title').textContent();

	expect(caption).toContain('median');
	expect(caption).toContain('middle half');
	// Per run, because a day hides which of its four runs moved.
	expect(caption).toContain('Run medians: 2026-08-20-1');
	expect(caption).toContain('2026-08-20-2');
});

test('writing draws slower than reading, on one shared scale', async ({ page }) => {
	await page.goto('/console/model/');

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
	await page.goto('/console/model/');

	const link = page.getByRole('link', { name: 'why the range is wide' });
	await expect(link).toHaveAttribute(
		'href',
		'https://github.com/miztiik/yen-idhazh/blob/main/docs/architecture/summarize/throughput.md'
	);
});

test('the throughput chart draws in the pixels it occupies', async ({ page }) => {
	await page.goto('/console/model/');

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
	await page.goto('/console/model/');

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
	await expect(page.locator('[data-band-distance]')).toBeVisible();

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

test('the failed-item list is capped, states its scope, and offers the rest', async ({ page }) => {
	await page.goto('/console/');

	// The rows sit behind a disclosure, so the control that reaches them is what
	// has to work before anything about them can be read.
	const toggle = page.locator('[data-failure-toggle]');
	await expect(toggle).toBeVisible();
	await toggle.click();

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

test('the candle reads out its day and every series at that column', async ({ page }) => {
	await page.goto('/console/model/');

	const readout = page.locator('[data-readout="throughput"]');
	// The strip rests on the newest day rather than opening blank, so it never
	// appears under the pointer and pushes the marks it explains out from under
	// it. That is the stage-timing chart's rule, applied here unchanged.
	await expect(readout).toHaveCount(1);
	await expect(readout.locator('[data-readout-day]')).toContainText('the newest day');

	const plot = page.locator('[data-throughput="chart"] svg');
	await plot.evaluate((node: SVGSVGElement) => node.focus());

	// The readout carried `caption()` verbatim until 2026-08-30, on the rule that
	// one day gets one sentence. The strip is now capped at a share of the plot,
	// and the per-run list in `caption()` is the one clause that grows with the
	// day's run count - four wrapped lines of it is not a readout. The `<title>`
	// keeps every word; the strip keeps the median and the extent per series.
	await expect(readout.locator('[data-readout-day]')).toHaveText(/^\d+ \w+ \d{4}$/);

	// One row per series drawn, read against write off one hover rather than two.
	const rows = await readout
		.locator('[data-readout-row]')
		.evaluateAll((nodes) =>
			nodes.map((node) => (node.getAttribute('data-readout-row') ?? '').trim())
		);
	expect(rows).toEqual(['read', 'write']);
	for (const series of rows) {
		await expect(readout.locator(`[data-readout-row="${series}"] dd`).last()).toHaveText(
			/^[\d.]+ \([\d.]+-[\d.]+\)$/
		);
	}

	await expect(page.locator('[data-readout-hint="throughput"]')).toHaveText(
		'Point at a day to read it. Left and Right step through the days, Escape returns to the newest.'
	);
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

	// The failure surface says the window holds nothing rather than drawing a
	// column of zeroes, which would read as a run that went badly.
	await expect(page.locator('[data-failure-empty]')).toBeVisible();
	await expect(viewport).toContainText('0 rows in view');
});

test('an empty section costs the page that section, never the page', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const missing = watchFor404s(page);

	await page.goto('/console/');

	// The canary telemetry records no failed item, so the failed-item list has
	// nothing to list. It says so and the page carries on: the timing chart, the
	// run grid, the feed table and the score table all still draw. The rows are
	// behind a disclosure now, so what has to survive is the control that reaches
	// them and the sentence it carries - not the table itself.
	await expect(page.locator('[data-failure-toggle]')).toBeVisible();
	await expect(page.locator('[data-failure-list="empty"]')).toHaveText(
		'No failed item is in this window.'
	);
	await expect(page.getByText('Time per item, by stage')).toBeVisible();
	await expect(page.locator('[data-grid="days"]')).toBeVisible();
	await expect(page.locator('[data-feeds="table"]')).toBeVisible();
	// The daily rows are behind a disclosure now, so what has to survive is the
	// control that reaches them - not the table itself.
	await expect(page.locator('[data-charts="daily"]')).toBeVisible();
	await expect(page.locator('[data-charts-verdict]')).toBeVisible();

	// And the same on the route the model section moved to, which has its own
	// empty states and its own band above them.
	await page.goto('/console/model/');
	await expect(page.getByRole('heading', { name: 'What the model did' })).toBeVisible();
	await expect(page.locator('[data-console-band]')).toBeVisible();

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

/** Open the daily figures.
 *
 * The rows are on demand: the section leads with the two figures its own
 * retirement rule names and keeps the seven daily columns behind a native
 * disclosure. `page.evaluate` rather than a click, because the integrated
 * browser is a hidden page and a click waits for an element to be stable.
 */
async function openDailyCharts(page: Page) {
	await page.locator('[data-charts="daily"]').evaluate((node) => {
		(node as HTMLDetailsElement).open = true;
	});
	await expect(page.locator('[data-charts="table"]')).toBeVisible();
}

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
		// The denominator of the arm's coverage rule, and the reason a share of no
		// articles is printed as an absence rather than as zero percent.
		items: String(items.length),
		minutes: printed(minutes),
		'per-chart': printed(minutes === null || published === 0 ? null : minutes / published)
	};
}

test('every chart cell equals what the day committed', async ({ page }) => {
	await page.goto('/console/');
	await openDailyCharts(page);

	const dates = await page
		.locator('[data-chart-day]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-chart-day') ?? ''));
	// Newest first, and every day inside the open window that the manifest covers
	// - so a day the visuals planner never reached still counts towards the arm's
	// fourteen-day rule. Days older than the window are the section's own answer
	// to a preset the reader picked, not rows that went missing.
	const committed = manifestDays().map((day) => day.date);
	const span = openWindow(committed);
	const expected = committed.filter((date) => date >= span.start && date <= span.end).reverse();
	expect(expected.length, 'the window reaches no committed day, so this asserts nothing').toBeGreaterThan(
		0
	);
	expect(dates).toEqual(expected);

	for (const date of dates) {
		const row = page.locator(`[data-chart-day="${date}"]`);
		for (const [cell, expected] of Object.entries(chartCells(date))) {
			await expect(row.locator(`[data-charts-cell="${cell}"]`)).toHaveText(expected);
		}
	}
});

test('the measured day prints rates, and the day with no minutes prints dashes', async ({
	page
}) => {
	await page.goto('/console/');
	await openDailyCharts(page);

	// The attack day is the one the fixture gives planner counts to. Asserting it
	// is not all zeros is what stops the oracle above passing on an empty table.
	const measured = page.locator(`[data-chart-day="${DAY}"]`);
	const cells = chartCells(DAY);
	expect(Number(cells.reached)).toBeGreaterThan(Number(cells.asked));
	expect(Number(cells.drafted)).toBeGreaterThan(Number(cells.published));
	expect(Number(cells.published)).toBeGreaterThan(0);
	await expect(measured.locator('[data-charts-cell="minutes"]')).not.toHaveText('-');
	await expect(measured.locator('[data-charts-cell="per-chart"]')).not.toHaveText('-');

	// A quiet day ran and published nothing, so its visuals planner never
	// started. Zero items reached is a measurement; zero minutes would be an
	// invention, and a per-visual cost over no visuals is not a number at all.
	const quiet = page.locator(`[data-chart-day="${manifestDays()[0].date}"]`);
	await expect(quiet.locator('[data-charts-cell="reached"]')).toHaveText('0');
	await expect(quiet.locator('[data-charts-cell="published"]')).toHaveText('0');
	await expect(quiet.locator('[data-charts-cell="minutes"]')).toHaveText('-');
	await expect(quiet.locator('[data-charts-cell="per-chart"]')).toHaveText('-');
});

test('a visual that never drew is a visual and is not a published chart', async ({ page }) => {
	await page.goto('/console/');
	await openDailyCharts(page);

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

	// The fixture publishes two charts and plans a third the renderer refused. The
	// column is headed `Visuals published` since 2026-08-31 but still counts only
	// rendered charts, because counting every visual would put a picture nobody
	// can see on the arm's bill and the arm would look more productive than it is.
	// Every visual on the committed days is a rendered chart, so the two numbers
	// agree there; the fixture is the only place they can be told apart.
	expect(visuals).toBeGreaterThan(charts);
	await expect(
		page.locator(`[data-chart-day="${DAY}"] [data-charts-cell="published"]`)
	).toHaveText(String(charts));
});

test('no console route reads the word router to an operator', async ({ page }) => {
	// `router` names a pipeline stage, and CLAUDE.md section 0b bars a subsystem
	// word from a string a person reads. Script text is exempt because nobody
	// reads it: the serialized payload still carries `routerMinutes`, which is a
	// key and not a sentence.
	for (const route of ['/console/', '/console/model/', '/console/machine/']) {
		await page.goto(route);
		const leaks = await page.evaluate(() => {
			const found: string[] = [];
			const skip = new Set(['SCRIPT', 'STYLE', 'TEMPLATE']);
			const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
			for (let node = walk.nextNode(); node; node = walk.nextNode()) {
				const text = (node.textContent ?? '').trim();
				if (skip.has(node.parentElement?.tagName ?? '')) continue;
				if (/router/i.test(text)) found.push(text);
			}
			// An accessible name is read aloud, so it is a reader string too.
			for (const el of document.querySelectorAll('[aria-label], [title]')) {
				for (const name of ['aria-label', 'title']) {
					const value = el.getAttribute(name);
					if (value && /router/i.test(value)) found.push(value);
				}
			}
			return found;
		});
		expect(leaks, `${route} reads a subsystem word to an operator`).toEqual([]);
	}
});

test('the renamed section draws what it drew before, figure for figure', async ({ page }) => {
	// The other half of the oracle: a rename that quietly dropped a bar would
	// pass the grep above. The counts are `origin/main` at bb7fd4a, counted in
	// its own source: two figures, each a target bar over a sparkline, and one
	// flow diagram beside them.
	await page.goto('/console/');
	const section = page.locator('[data-windowed="chart-arm"]');
	await expect(section.locator('[data-arm-figure]')).toHaveCount(2);
	await expect(section.locator('[data-target-bar]')).toHaveCount(2);
	await expect(section.locator('[data-sparkline]')).toHaveCount(2);
	await expect(page.locator('[data-flow]')).toHaveCount(1);
	await expect(page.locator('[data-charts="table"] thead th')).toHaveCount(8);
});

/** The canary's own score rows and item-health rows for one date. */
/** Every month shard in a ledger directory, oldest first.
 *
 * `state/scores/` shards by month since 2026-08-31. A spec that opened one file
 * by name reads nothing, which makes every day look unscored - and a test whose
 * fixture silently empties passes for the wrong reason.
 */
function shardRows(dir: string): Record<string, string>[] {
	return readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.sort()
		.flatMap((name) => readCsv(join(dir, name)).rows);
}

function ledgers(date: string): {
	scores: Record<string, string>[];
	health: Record<string, string>[];
} {
	const health = join(CANARY, 'state', 'item-health');
	return {
		scores: shardRows(join(CANARY, 'state', 'scores')).filter((row) => row.date === date),
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
	const scored = shardRows(join(CANARY, 'state', 'scores')).map((row) => row.date);
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

/** The daily figures sit behind a disclosure now; the cards above them lead.
 *
 * Opening it is a reader's own action, so a test that reads a cell takes it
 * too. `console-model.spec.ts` owns the cards and the control itself.
 */
async function openDailyFigures(page: Page) {
	await page.locator('[data-model-table-control] > summary').click();
	await expect(page.locator('[data-model="table"]')).toBeVisible();
}

test('every model cell equals what the day committed', async ({ page }) => {
	await page.goto('/console/model/');
	await openDailyFigures(page);

	const dates = await page
		.locator('[data-model-day]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-model-day') ?? ''));
	// A day the pipeline found no article on gets no row at all. A row of zeroes
	// would read as a day that went badly rather than a day with nothing in it.
	// A day outside the open window gets none either, because the rows answer the
	// same control the cards above them do.
	const worked = modelDays();
	const span = openWindow(worked);
	const expected = worked.filter((date) => date >= span.start && date <= span.end);
	expect(expected.length, 'the window reaches no worked day, so this asserts nothing').toBeGreaterThan(
		0
	);
	expect(dates).toEqual(expected);

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
	await page.goto('/console/model/');
	await openDailyFigures(page);

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
	await page.goto('/console/model/');
	// Opened, so the scan below reads the cards AND the rows. A closed disclosure
	// keeps its rows out of `innerText`, and a scan that cannot see half the
	// section is a scan that passes for the wrong reason.
	await openDailyFigures(page);

	const section = await page.locator('[data-model-section]').innerText();

	// A value between zero and one is what the scorer emits, and none of them may
	// reach an operator: a number nobody can pull a lever on is not a report. A
	// token rate that low would itself be the failure, so this cannot misfire on
	// the candle above the table.
	expect(section).not.toMatch(/\b[01]\.\d/);

	// A ledger column name on screen makes a reader open the schema to read the
	// page. Every one of these is a real column of `state/scores/<YYYY-MM>.csv` or
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
	await page.goto('/console/model/');

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

