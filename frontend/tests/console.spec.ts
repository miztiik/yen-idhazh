import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { axisLabels, spanLabel } from '../src/lib/charts/run-history';
import { dayKey, monthsInWindow, panWindow, toDay } from '../src/lib/charts/viewport';
import { modelWork } from '../src/lib/server/model-work';
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
	await expect(page.locator('[data-viewport-control]')).toContainText('11 rows in view');
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

test('the compression view draws every scored item, and marks the truncated ones', async ({
	page
}) => {
	await page.goto('/console/');

	// The state that had no coverage at all while the canary day carried no
	// scored item: marks instead of a sentence, a zone behind them, and more
	// than one decade under them.
	const chart = page.locator('[data-compression]');
	await expect(chart).not.toContainText('No scored items in this window');

	const dots = await chart.locator('svg circle').count();
	const diamonds = await chart.locator('svg rect').count();
	expect(dots).toBeGreaterThan(0);
	expect(diamonds, 'no truncated item, so the diamond is undrawn').toBeGreaterThan(0);
	// Every scored row reaches the plot. A filter that dropped one would still
	// leave a chart that looks right.
	expect(dots + diamonds).toBe(scoredItems());

	await expect(chart.locator('[data-band-zone]')).toHaveCount(1);

	// A log axis labelled at one decade is a linear axis with an odd label on
	// it. The y ticks and the two axis titles carry their own attributes, so
	// what is left is the decades.
	const decades = await chart
		.locator('svg text:not([data-tick="y"]):not([data-axis])')
		.evaluateAll((nodes) =>
			nodes
				.map((node) => (node.textContent ?? '').trim())
				.filter((text) => /^10*$/.test(text))
		);
	expect(new Set(decades).size).toBeGreaterThan(1);
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

	// "summary words" used to be printed on the bottom row beside the x axis
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

	return {
		summaries: scores.length === 0 ? '-' : String(scores.length),
		'not-sure': tally((row) => row.band === 'low'),
		unsupported: tally((row) => Number(row.unsupported_numbers) > 0),
		hedge: tally((row) => truthy(row.hedge_dropped)),
		part: tally((row) => truthy(row.truncation_flagged)),
		copied: scores.length === 0 ? '-' : `${Math.round(middle(copied) * 100)}%`,
		'per-item': times.length === 0 ? '-' : units(middle(times), 1000),
		minutes:
			times.length === 0 ? '-' : units(times.reduce((total, ms) => total + ms, 0), 60_000),
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
	for (const cell of ['summaries', 'not-sure', 'unsupported', 'hedge', 'part', 'copied']) {
		await expect(row.locator(`[data-model-cell="${cell}"]`)).toHaveText('-');
	}
	// Speed is measured by the runtime, not by the scorer, so it still prints.
	await expect(row.locator('[data-model-cell="per-item"]')).not.toHaveText('-');
	await expect(row.locator('[data-model-cell="minutes"]')).not.toHaveText('-');

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
