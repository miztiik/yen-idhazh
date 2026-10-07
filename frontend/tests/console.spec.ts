import { expect, test, type Page } from './support/browser';
import type { TestInfo } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { grouped, telemetryCsv, type StageTimingDay, type ThroughputDay } from '../src/lib/charts/series';
import { monthsInWindow, panWindow } from '../src/lib/charts/viewport';
import { shortDate } from '../src/lib/format';
import { throughputWithin } from '../src/lib/server/model-work';
import { publishedCharts, telemetryMonths, telemetryRows } from '../src/lib/server/payload';
import { reliability, resultLabel, type FeedRecord } from '../src/lib/feed-health';
import { days } from './support/consecutive-days';
import { publishedSite } from './support/published-site';
import { serverCompiler } from './support/server-render';
import { telemetryRow } from './support/telemetry-row';

/**
 * The console says whether the runs worked and which feeds are broken.
 *
 * It runs against the canary build, and no case reads a figure the canary
 * holds. A case on the built page checks what the page draws against what the
 * page itself publishes - its window, its counts and its sentences - or serves
 * the rows it counts. The figures behind those drawings are pinned where they
 * are computed, over rows a test writes: the feed record and the day's token
 * rates here, the stage medians in `console-stage-timing-days.spec.ts`, the run
 * square in `console-run-health.spec.ts` and the model table in
 * `console-model-work.spec.ts`. The stage-timing and token-rate charts are
 * drawn here from days a test writes, so their axes, gaps, zeros and sentences
 * are written out, and the telemetry a pan reaches is served by the test. The
 * failed-item list is the section with nothing to show, which proves the page
 * keeps rendering when one of its sources holds nothing.
 *
 * The band section has its own file, `console-compression.spec.ts`.
 *
 * See `backend/utilities/build_canary_day.py` for the fixture.
 */

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
).console?.default_window_days ?? 14;

/** Every span the control offers, from the same knob the control reads. */
const WINDOW_PRESETS = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console?: { window_presets?: number[] } }
).console?.window_presets ?? [1, 7, 14, 30, 90];

/** The widest span the control offers. Every column of the run strip is a day of it. */
const WIDEST = Math.max(...WINDOW_PRESETS);

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

/** A telemetry corpus deliberately longer than the window, for the read tests.
 *
 * The canary day carries two days, which is shorter than any window this knob
 * can hold. A window asserted against a corpus it cannot cut passes without
 * cutting anything, so the telemetry read tests read this instead.
 */
const TELEMETRY_FIXTURE = resolve(process.cwd(), 'tests', 'fixtures', 'telemetry');

/** The day the page says its window ends on: the viewport publishes the span it draws. */
async function windowEnd(page: Page): Promise<string> {
	const end = (await page.locator('[data-viewport-control]').getAttribute('data-window-end')) ?? '';
	expect(end, 'the viewport publishes no window end').toMatch(/^\d{4}-\d{2}-\d{2}$/);
	return end;
}

/** The run strip's newest column: the day the window ends on. */
function newestColumn(page: Page) {
	return page.locator('[data-day]').last();
}

/** Open `/console/` on a stored span, the way a reader's last choice reopens it. */
async function openOnWindow(page: Page, days: number) {
	await page.addInitScript(
		(stored) => localStorage.setItem('idhazh:console-window', String(stored)),
		days
	);
	await page.goto('/console/');
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
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

/** A phone, where the run squares draw their own strip. The strip keeps its
 * floor there and cannot shrink, so a week of days leaves it room to spare -
 * which is what lets an alignment test assert on spare room without depending on
 * today's ledger. Wider than a phone the squares stand under the chart's own
 * days instead. */
const UNDERFULL_VIEWPORT = { width: 390, height: 844 };

/** A phone, for the rules only the scrolling strip has. */
const PHONE = { width: 360, height: 720 };

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

test('the strip reads oldest to newest, left to right', async ({ page }) => {
	await page.goto('/console/');

	const columns = page.locator('[data-day]');
	const dates = await columns.evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-day') ?? '')
	);
	// The window's own calendar, one column a day, consecutive and oldest first,
	// ending on the day the page says its window ends.
	expect(dates.length).toBe(DEFAULT_WINDOW_DAYS);
	expect(dates).toEqual(days(dates[0], dates.length));
	expect(dates.at(-1)).toBe(await windowEnd(page));

	// Chronology a reader can see, not only one the DOM asserts.
	const boxes = await columns.evaluateAll(TO_BOX);
	for (let index = 1; index < boxes.length; index += 1) {
		expect(boxes[index].x).toBeGreaterThan(boxes[index - 1].x);
	}
});

test('every recorded run gets a square, and nothing else does', async ({ page }) => {
	// The widest span, so the window holds empty days as well as recorded ones and
	// the rule below has both to check.
	await openOnWindow(page, WIDEST);

	// One column a day of the WINDOW, not one a manifest. An empty column is the
	// fact the strip exists to show, and the days with runs are a subset of it.
	await expect(page.locator('[data-day]')).toHaveCount(WIDEST);
	const drawn = await page.locator('[data-day]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			date: node.getAttribute('data-day') ?? '',
			labels: [...node.querySelectorAll('[data-health]')].map((square) => square.getAttribute('aria-label') ?? '')
		}))
	);
	// No square stands outside a day's column.
	await expect(page.locator('[data-health]')).toHaveCount(
		drawn.reduce((total, day) => total + day.labels.length, 0)
	);

	// A column's squares are its own day's runs, in the order they landed. A
	// scheduled run that never wrote a manifest has left no evidence, so the strip
	// cannot draw a slot for it; two runs can finish in parallel, so a number may
	// be skipped but never repeated.
	for (const day of drawn) {
		const numbers = day.labels.map((label) => {
			const named = new RegExp(`^Run (\\d+) on ${shortDate(day.date)}: `).exec(label);
			expect(named, `a square in the ${day.date} column names another day: ${label}`).not.toBeNull();
			return Number(named?.[1]);
		});
		expect(numbers, `${day.date} draws its runs out of order`).toEqual([...numbers].sort((a, b) => a - b));
		expect(new Set(numbers).size, `${day.date} draws one run twice`).toBe(numbers.length);
	}
	expect(drawn.some((day) => day.labels.length > 0), 'the window holds no run, so the rule is untested').toBe(true);
	expect(
		drawn.some((day) => day.labels.length === 0),
		'the window carries no empty day, so the rule is untested'
	).toBe(true);
});

test('runs rise from a shared baseline, on a square day track', async ({ page }) => {
	// The phone strip, where a day is a track of its own. Under the chart a day
	// takes the chart's slot instead, and `console-run-health.spec.ts` holds it to
	// the bars.
	await page.setViewportSize(PHONE);
	await page.goto('/console/');
	await expect(page.locator('[data-run-history="strip"]')).toHaveCount(1);

	const stack = await newestColumn(page).locator('[data-health]').evaluateAll(TO_BOX);
	expect(stack.length, 'the newest day ran once, so its stack has no gap to measure').toBeGreaterThan(1);

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
	// The phone strip's own date row. Under the chart the squares have none - the
	// chart's date row is directly above them.
	await page.setViewportSize(PHONE);
	await page.goto('/console/');
	await expect(page.locator('[data-run-history="strip"]')).toHaveCount(1);

	const labels = await page.locator('[data-axis-label]').evaluateAll(TO_BOX);
	expect(labels.length).toBeGreaterThan(1);

	const ordered = [...labels].sort((a, b) => a.x - b.x);
	for (let index = 1; index < ordered.length; index += 1) {
		expect(ordered[index].x).toBeGreaterThan(ordered[index - 1].right);
	}
});

test('a phone strip that cannot fill its frame is centred in it', async ({ page }) => {
	// Where an OVERFLOWING strip opens and where an UNDERFULL one sits are two
	// questions, and `today_anchor` only answers the first. Anchored left, the
	// spare room piled up on the right - and the right of a time axis whose last
	// column is today is where a reader looks for the days that just happened,
	// so it read as a run that had stopped. Centred, the spare room is on both
	// sides and belongs to neither end.
	//
	// The narrowest strip the presets offer, on purpose. At the default window
	// thirty columns fill a page-wide frame, so left and right and centred are the
	// same thing there and the premise below could not hold. A one-day window is
	// excluded for the opposite reason: one square has no inside to be centred in,
	// and every assertion here would pass on it.
	await page.setViewportSize(UNDERFULL_VIEWPORT);
	await page.goto('/console/');
	await hydrated(page);
	await setWindow(page, Math.min(...WINDOW_PRESETS.filter((days) => days > 1)));

	const [strip] = await page.locator('[data-run-history]').evaluateAll(TO_BOX);
	const columns = await page.locator('[data-day]').evaluateAll(TO_BOX);

	// The premise: fewer days than the strip has room for. Without it the test
	// passes on a full strip, where every alignment is the same thing.
	expect(columns.length, 'the strip drew one column, so alignment asserts nothing').toBeGreaterThan(
		1
	);
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
	// says the span and nothing about where in it a run sits. The squares read
	// the chart's date row, directly above them, rather than carrying their own.
	const labels = await page
		.locator('[data-console-panel="Run health"] svg[data-run-yield-chart] [data-day-axis]')
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
	// run after the day's own counts, and every such line is a run rather than a
	// stage.
	const runs = await page.locator('[data-day]').last().locator('[data-health]').count();
	expect(runs, 'the newest column carries no run, so the per-run rule is untested').toBeGreaterThan(
		0
	);
	expect(newest.rows.filter((row) => row.startsWith('Run '))).toEqual(
		Array.from({ length: runs }, (_, index) => `Run ${index + 1}`)
	);

	// And the standing key is gone. The readout prints the swatch and the counts
	// for the run it is on, so a key beside it would draw the same pair twice.
	// The one list left is the chart's days in words, for a screen reader.
	await expect(
		page.locator('[data-windowed="run-health"] ul:not([data-run-yield-values])')
	).toHaveCount(0);
});

test('on a phone the strip scrolls, and opens on the newest run', async ({ page }) => {
	await page.setViewportSize({ width: 360, height: 720 });
	// More history than a phone is wide: the default fourteen days fit one.
	await openOnWindow(page, WIDEST);

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
	const [newest] = await newestColumn(page).evaluateAll(TO_BOX);
	expect(newest.x).toBeGreaterThanOrEqual(strip.x - 1);
	expect(newest.right).toBeLessThanOrEqual(strip.right + 1);

	const opened = (await stripMetrics(page)).scrollLeft;
	await page.locator('[data-run-history]').focus();
	await page.keyboard.press('ArrowLeft');
	await expect.poll(async () => (await stripMetrics(page)).scrollLeft).toBeLessThan(opened);
});

test('the grid draws one square per run, coloured by what the run did', async ({ page }) => {
	await page.goto('/console/');

	// The colour and the sentence on a square are made from the same facts of one
	// run (`$lib/console/run-square.ts`), so each sentence names the colour its
	// square wears: a run that failed, or fell under the floor, is red; one that
	// tried nothing, failed an article, reused yesterday's sources or waited on
	// another run is amber; and the rest are green.
	const squares = await page.locator('[data-day] [data-health]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			health: node.getAttribute('data-health') ?? '',
			label: node.getAttribute('aria-label') ?? ''
		}))
	);
	expect(
		new Set(squares.map((square) => square.health)).size,
		'every run in the window wears one colour, so the rule is untested'
	).toBeGreaterThan(1);
	for (const square of squares) {
		const said = square.label.replace(/^Run \d+ on [^:]+: /, '');
		const colour = /the run failed|under \d+%/.test(said)
			? 'red'
			: /nothing new to try|\d+ failed|reused yesterday's list of sources|another run's failed article was still missing/.test(said)
				? 'amber'
				: 'green';
		expect(square.health, square.label).toBe(colour);
	}
});

test('a square says what happened without a mouse', async ({ page }) => {
	await page.goto('/console/');

	// The colour alone is not the answer. Anyone who cannot see the difference
	// between amber and red still has to be able to read the run - and a native
	// tooltip is not how, because it needs a mouse held still over a 7px square.
	// The words are the square's name and are printed in the strip under it.
	const column = newestColumn(page);
	const date = (await column.getAttribute('data-day')) ?? '';
	const first = column.locator('[data-health]').first();
	await expect(first).toHaveAttribute(
		'aria-label',
		new RegExp(`^Run \\d+ on ${shortDate(date)}: (\\d+ of \\d+ succeeded|nothing new to try)`)
	);
	expect(await first.getAttribute('title')).toBeNull();
});

test('the run that read only the start of an article says so on its own square', async ({
	page
}) => {
	await page.goto('/console/');

	// Per run, and only here. Measured 2026-08-29 over 19 committed runs the
	// count is 1 to 12 articles of 160 to 200 - which is the article mix on that
	// run, so a published figure would read as the cap moving when nothing did.
	const labels = await page
		.locator('[data-day] [data-health]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label') ?? ''));
	const carried = labels.filter((label) => label.includes('read only in part'));
	expect(carried.length, 'no run in the window cut anything, so the clause is untested').toBeGreaterThan(0);
	for (const label of carried) {
		// One clause, after the run's counts, naming how many of its articles were cut.
		expect(label).toMatch(/^Run \d+ on [^:]+: .+, [1-9]\d* read only in part(, |$)/);
	}

	// And a run that cut nothing does not carry the clause at all. A `0 read
	// only in part` on every other square is a sentence about nothing.
	expect(labels.filter((label) => /(^|\D)0 read only in part/.test(label))).toEqual([]);
	expect(labels.length).toBeGreaterThan(carried.length);
});

test('a listed feed failed at least once, and a feed the pipeline never read is not listed', async ({
	page
}) => {
	// Which reads count as failures is the quarantine rule's, pinned over rows written in
	// `console-voices-feeds.spec.ts`: an answer that carried nothing is one, and a polite
	// refusal is not. What the page owes is to list only feeds that failed, and never one it
	// names as unread.
	await page.goto('/console/voices/');

	const listed = await page.locator('[data-feed]').evaluateAll((rows) =>
		rows.map((row) => ({
			id: row.getAttribute('data-feed') ?? '',
			failures: Number(row.getAttribute('data-feed-failures'))
		}))
	);
	expect(listed.length, 'the page lists no failing feed, so this asserts nothing').toBeGreaterThan(0);
	for (const feed of listed) expect(feed.failures, `${feed.id} is listed and never failed`).toBeGreaterThan(0);
	const unread = await page
		.locator('[data-feed-ineligible-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-ineligible-name') ?? ''));
	expect(
		listed.map((feed) => feed.id).filter((id) => unread.includes(id)),
		'a feed the pipeline never read is listed as failing'
	).toEqual([]);
});

test('an answer that carried nothing is labelled as such, and never as ok', () => {
	// The ledger's own word for this read is `ok` - the fetch returned 200. Printed raw it sits on
	// the same row as the failure count and contradicts it, which is how a dead feed reads as a
	// healthy one.
	const read = (outcome: string, items: number) => ({ date: '2030-06-15', runId: '2030-06-15-1', outcome, items });
	expect(resultLabel(read('ok', 0))).toBe('answered with nothing');
	expect(resultLabel(read('ok', 4))).toBe('ok');
	// A feed that really did fail still reports the reason the ledger recorded.
	expect(resultLabel(read('permanent', 0))).toBe('permanent');
});

test('a feed still failing never reports its last result as ok', async ({ page }) => {
	// A streak runs to the newest read, so a feed that has one has not answered since: its last
	// result is a failure or a read that did not ask, never the word ok.
	await page.goto('/console/voices/');

	const rows = await page.locator('[data-feed]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			id: node.getAttribute('data-feed') ?? '',
			streak: Number(node.getAttribute('data-feed-streak')),
			result: (node.querySelector('[data-feed-result]')?.textContent ?? '').replace(/\s+/g, ' ').trim()
		}))
	);
	expect(rows.length, 'the page lists no failing feed, so this asserts nothing').toBeGreaterThan(0);
	for (const row of rows) {
		const label = row.result.split(' - ')[0];
		expect(label, `${row.id} prints no last result`).not.toBe('');
		if (row.streak > 0) expect(label, `${row.id} is still failing and reports ok`).not.toBe('ok');
	}
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

/** The feed record the voices page prints in its headline, read off its own attributes.
 *
 * The record behind these numbers is pinned over rows written here (`a record too
 * shallow for a rate says so instead of printing one`, `a record with more failing
 * feeds than the list draws is counted whole`); what the page owes is to print the
 * numbers it publishes, and to list every feed they count.
 */
async function feedHeadline(page: Page) {
	const headline = page.locator('[data-feed-reliability]');
	await expect(headline, 'the feed section prints no denominator').toHaveCount(1);
	const count = async (name: string) => Number(await headline.getAttribute(name));
	return {
		headline,
		clean: await count('data-feed-clean'),
		checked: await count('data-feed-checked'),
		runs: await count('data-feed-runs')
	};
}

test('THE ORACLE: the feed headline carries its own denominator and span', async ({ page }) => {
	await page.goto('/console/voices/');

	const { headline, clean, checked, runs } = await feedHeadline(page);
	// Read against facts the page publishes, never against a locator count alone: a
	// renamed attribute would make every number zero and switch this off.
	expect(checked, 'the page checked no feed at all').toBeGreaterThan(0);
	expect(clean, 'the page has no clean feed to name').toBeGreaterThan(0);
	expect(clean, 'the page has no failing feed, so the list is empty').toBeLessThan(checked);
	await expect(page.locator('[data-feed-clean-name]')).toHaveCount(clean);
	// The numbers in the attributes are also the numbers in the type. An
	// attribute nobody reads and a sentence that says something else is exactly
	// the shape this section had before.
	await expect(headline).toContainText(`${clean} of ${checked} feeds`);
	await expect(headline).toContainText(String(runs));
	// The record's depth decides which of the two sentences prints.
	await expect(headline).toHaveAttribute(
		'data-feed-reliability',
		runs >= MIN_ATTEMPTS ? 'measured' : 'shallow'
	);
});

test('THE ORACLE: the disclosed names are exactly the feeds that did not fail', async ({
	page
}) => {
	await page.goto('/console/voices/');

	const { clean } = await feedHeadline(page);
	const named = await page
		.locator('[data-feed-clean-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-clean-name') ?? ''));

	// Every clean feed the headline counts, once each, in name order.
	expect(named).toHaveLength(clean);
	expect(new Set(named).size).toBe(named.length);
	expect(named).toEqual([...named].sort((a, b) => a.localeCompare(b)));
	// And the lists are disjoint: no feed is both clean and listed as broken, or
	// both clean and one the pipeline did not read.
	const listed = await page
		.locator('[data-feed]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-feed') ?? ''));
	expect(named.filter((feedId) => listed.includes(feedId))).toEqual([]);
	const unread = await page
		.locator('[data-feed-ineligible-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-ineligible-name') ?? ''));
	expect(named.filter((feedId) => unread.includes(feedId))).toEqual([]);
});

test('THE ORACLE: the failure list is capped and its tail counts the remainder', async ({
	page
}) => {
	await page.goto('/console/voices/');

	const { clean, checked } = await feedHeadline(page);
	// A feed the headline checked and did not count clean is a feed that failed.
	const broken = checked - clean;
	const table = page.locator('[data-feeds="table"]');
	const drawn = Number(await table.getAttribute('data-feeds-drawn'));
	const hidden = Number(await table.getAttribute('data-feeds-hidden'));

	// The identity that catches a cap dropping rows without counting them. It
	// holds at zero hidden, which is what makes it worth asserting on a fixture
	// the cap does not bite.
	expect(drawn + hidden, 'the cap lost a feed on the way past it').toBe(broken);
	expect(drawn).toBeLessThanOrEqual(FEED_ROWS);
	expect(drawn).toBe(Math.min(broken, FEED_ROWS));
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
	// left to a sentence that never prints. Two runs deep, "did not fail" means
	// "did not fail twice", and the page has to say which it means.
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
	// The run count is every run the rows hold, rest or no rest.
	expect(withRest.runs).toBe(2);
	// And the partition holds, always.
	expect(withRest.clean.length + withRest.failed).toBe(withRest.checked);
});

test('a record with more failing feeds than the list draws is counted whole', () => {
	// The canary cannot show a capped list, so a record deeper than the cap is
	// written here, over five runs: twelve feeds that each failed once, in each of
	// the four ways a read fails, two that never failed, one only ever rested and
	// one only ever refused by its robots file. The page draws `feed_rows` of the
	// twelve and counts the rest in its tail sentence; the count behind both is
	// never capped.
	const runs = ['2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14', '2030-06-15'];
	const record = (feedId: string, last: { outcome: string; items: number }): FeedRecord[] =>
		runs.map((date, at) => ({
			feedId,
			date,
			runId: `${date}-1`,
			...(at === runs.length - 1 ? last : { outcome: 'ok', items: 9 })
		}));
	const failures = [
		{ outcome: 'transient', items: 0 },
		{ outcome: 'permanent', items: 0 },
		{ outcome: 'blocked', items: 0 },
		{ outcome: 'ok', items: 0 }
	];
	const failed = Array.from({ length: 12 }, (_, at) =>
		record(`failing-${String(at + 1).padStart(2, '0')}`, failures[at % failures.length])
	);
	const rows: FeedRecord[] = [
		...failed.flat(),
		...record('clean-a', { outcome: 'ok', items: 9 }),
		...record('clean-b', { outcome: 'ok', items: 4 }),
		...runs.map((date) => ({ feedId: 'rested', date, runId: `${date}-1`, outcome: 'skipped', items: 0 })),
		...runs.map((date) => ({ feedId: 'refused', date, runId: `${date}-1`, outcome: 'robots_denied', items: 0 }))
	];
	expect(FEED_ROWS, 'the cap reaches past this record, so it hides nothing').toBeLessThan(12);

	const measured = reliability(rows);
	expect(measured.runs).toBe(5);
	expect(measured.checked).toBe(14);
	expect(measured.failed).toBe(12);
	expect(measured.clean).toEqual(['clean-a', 'clean-b']);
	expect(measured.ineligible).toEqual(['refused', 'rested']);
});

/** Four timed days in a window of fifteen, written here and handed to the stage-timing chart.
 *
 * Newest first, as the route hands them over. Nothing timed 1 to 10 June or
 * 13 June, so those days have no entry, and with fewer than half the days
 * timed the chart tints them and says so in one sentence. On 14 June fetch
 * timed nothing and extract was measured at zero; on 15 June summarize timed 2
 * of the day's 3 items. The smallest reading is 20 ms and the largest 900 ms,
 * so the axis runs from the 10 ms decade to the 1 s one, and no reading sits on
 * a decade line.
 */
const TIMING_SPAN = { start: '2030-06-01', end: '2030-06-15' };

function timedStage(ms: number | null, count: number, total: number) {
	return { ms, timed: count, total };
}

const TIMING_DAYS: StageTimingDay[] = [
	{ date: '2030-06-15', items: 3, fetch: timedStage(200, 3, 3), extract: timedStage(30, 3, 3), summarize: timedStage(700, 2, 3) },
	{ date: '2030-06-14', items: 2, fetch: timedStage(null, 0, 2), extract: timedStage(0, 2, 2), summarize: timedStage(900, 2, 2) },
	{ date: '2030-06-12', items: 2, fetch: timedStage(150, 2, 2), extract: timedStage(20, 2, 2), summarize: timedStage(800, 2, 2) },
	{ date: '2030-06-11', items: 2, fetch: timedStage(120, 2, 2), extract: timedStage(25, 2, 2), summarize: timedStage(850, 2, 2) }
];

/** A console chart drawn in a real browser page from the days a test hands it.
 *
 * The chart's geometry and its words are worked out inside the component, so
 * the component is what a test has to draw. It is compiled with its real
 * readout child, never a stub (`tests/support/server-render.ts`), at the size
 * and tick density the console draws it with.
 */
async function drawnChart(page: Page, testInfo: TestInfo, name: string, props: Record<string, unknown>) {
	const appearance = JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as {
		chart: { tick_density: number; readout_max_share: number };
		console: { chart_height: number; chart_width: number };
	};
	const compiled = serverCompiler(testInfo.outputPath(name));
	const readout = await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
	const module = await compiled(`src/lib/components/${name}.svelte`, name, [
		['./ChartReadout.svelte', pathToFileURL(readout).href]
	]);
	const component = (await import(pathToFileURL(module).href)).default;
	const markup = render(component, {
		props: {
			...props,
			height: appearance.console.chart_height,
			width: appearance.console.chart_width,
			tickDensity: appearance.chart.tick_density,
			readoutMaxShare: appearance.chart.readout_max_share
		}
	}).body;
	await page.setContent(
		`<style>${[...compiled.css.values()].join('\n')}</style>` +
			`<main style="width: ${appearance.console.chart_width}px">${markup}</main>`
	);
}

/** The stage-timing chart, drawn from `TIMING_DAYS`, and its plot. */
async function drawnTimings(page: Page, testInfo: TestInfo) {
	await drawnChart(page, testInfo, 'StageTimings', { days: TIMING_DAYS, span: TIMING_SPAN });
	return page.locator('[data-timing="plot"]');
}

test('the timing y axis is decades, and it crosses milliseconds to seconds', async ({ page }, testInfo) => {
	const plot = await drawnTimings(page, testInfo);

	// Readings from 20 ms to 900 ms span the 10 ms decade to the 1 s one. Stages
	// that far apart cannot share a linear axis: the slowest would set the domain
	// and the others would draw on the baseline.
	const labels = await plot
		.locator('[data-decade]')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));
	expect(labels).toEqual(['10 ms', '100 ms', '1 s']);

	// Zero has no position on a log axis, so no label prints it.
	const printed = await plot
		.locator('text')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));
	expect(printed).not.toContain('0');

	// The eight steps inside each of the two decades, unlabelled. Without them
	// the axis reads as linear with odd numbers on it.
	await expect(plot.locator('[data-minor-tick]')).toHaveCount(16);
	expect(printed).not.toContain('20');
});

test('the timing legend is sorted by the newest day, tallest first', async ({ page }, testInfo) => {
	await drawnTimings(page, testInfo);

	// Colour is one signal and never the only one. Matching the legend order to
	// the plot's vertical order makes position the second signal, for free. On the
	// newest day summarize took 700 ms, fetch 200 ms and extract 30 ms.
	const entries = await page.locator('[data-timing="chart"] [data-readout-row]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			stage: node.getAttribute('data-readout-row') ?? '',
			text: (node.textContent ?? '').replace(/\s+/g, ' ').trim()
		}))
	);
	expect(entries.map((entry) => entry.stage)).toEqual(['summarize', 'fetch', 'extract']);
	expect(entries[0].text).toContain('700 ms');
	expect(entries[1].text).toContain('200 ms');
	expect(entries[2].text).toContain('30 ms');
});

test('a stage with no number draws a gap, never a plunge to the axis floor', async ({ page }, testInfo) => {
	const plot = await drawnTimings(page, testInfo);

	// Fetch timed 11, 12 and 15 June and nothing on 13 or 14 June. A missing
	// reading clamped onto a log axis would draw the line falling to the bottom of
	// the plot, which says the stage got a thousand times faster; the chart breaks
	// the line instead. So fetch draws one line, over 11 and 12 June, and three
	// points, and none on 14 June, where extract's measured zero sits.
	await expect(plot.locator('polyline[data-stage-mark="fetch"]')).toHaveCount(1);
	const fetchX = await plot
		.locator('circle[data-stage-mark="fetch"]')
		.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('cx'))));
	expect(fetchX).toHaveLength(3);
	const zeroX = Number(await plot.locator('[data-stage-zero="extract"]').getAttribute('cx'));
	expect(fetchX, 'fetch drew a point on a day it timed nothing').not.toContain(zeroX);

	// No reading here sits on a decade line, so every filled point is above the floor rule.
	const geometry = await plot.evaluate((svg) => ({
		floor: Math.max(
			...[...svg.querySelectorAll('[data-decade-line]')].map((line) => Number(line.getAttribute('y1')))
		),
		lowest: Math.max(
			...[...svg.querySelectorAll('circle[data-stage-mark]')].map((mark) => Number(mark.getAttribute('cy')))
		)
	}));
	expect(geometry.floor - geometry.lowest, 'a filled point sits on the axis floor').toBeGreaterThan(4);

	// The days nothing timed are tinted, each unbroken run once, and the one
	// sentence for the chart names the days timed.
	await expect(plot.locator('[data-coverage-empty="2030-06-01"]')).toHaveAttribute(
		'data-coverage-empty-to',
		'2030-06-10'
	);
	await expect(plot.locator('[data-coverage-empty="2030-06-13"]')).toHaveAttribute(
		'data-coverage-empty-to',
		'2030-06-13'
	);
	await expect(plot.locator('[data-coverage-empty]')).toHaveCount(2);
	await expect(page.locator('[data-timing-coverage]')).toContainText('We timed 4 of these 15 days');
});

test('a timing nobody took, a timing of zero and a partly timed day read apart', async ({
	page
}, testInfo) => {
	const plot = await drawnTimings(page, testInfo);

	// The three facts that used to arrive at this chart as the number 0: 13 June
	// timed nothing, extract was measured at 0 ms on 14 June, and 15 June timed
	// summarize on 2 of its 3 items.
	const zero = plot.locator('[data-stage-zero]');
	await expect(zero, 'the one measured zero draws one open dot').toHaveCount(1);
	await expect(zero).toHaveAttribute('data-stage-zero', 'extract');
	await expect(zero, 'an open dot, so it is not read as a point on the scale').toHaveAttribute('fill', 'none');
	// Centred on the baseline rule. Clamped into the bottom decade instead, it
	// would draw a plunge that says the stage got a thousand times faster.
	const offFloor = await plot.evaluate((svg) => {
		const dot = svg.querySelector('[data-stage-zero]');
		const floor = Math.max(
			...[...svg.querySelectorAll('[data-decade-line]')].map((line) => Number(line.getAttribute('y1')))
		);
		return Math.abs(Number(dot?.getAttribute('cy')) - floor);
	});
	expect(offFloor, 'the open dot is not on the baseline').toBeLessThanOrEqual(1);
	await expect(page.locator('[data-timing-zero-key]')).toHaveText(
		'An open dot on the baseline is a day a stage took under 1 ms an item, which is faster than we can time.'
	);

	// The partly timed days are in the one coverage sentence, as the items the
	// stages reached against the items the timed days held: fetch reached 7 of the
	// 9, summarize 8 and extract all 9. The denominator is the days' own item
	// count, never the sum of the stages' totals.
	const note = page.locator('[data-timing-coverage]');
	await expect(note).toHaveAttribute('data-coverage-days', '15');
	await expect(note).toHaveAttribute('data-coverage-measured', '4');
	await expect(note).toHaveAttribute('data-coverage-items', '9');
	await expect(note).toHaveAttribute('data-coverage-timed-low', '7');
	await expect(note).toHaveAttribute('data-coverage-timed-high', '9');
	await expect(note).toHaveText(
		'We timed 4 of these 15 days, and 7 to 9 of the 9 items on them. The tinted span is days nothing recorded, not quiet days.'
	);

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
	// Loaded once: the first width drives the mount-time measure, the other two
	// the resize path, which is the one a reader turning a tablet takes.
	await page.setViewportSize({ width: 380, height: 1000 });
	await page.goto('/console/');
	for (const viewport of [380, 768, 1400]) {
		await page.setViewportSize({ width: viewport, height: 1000 });
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

test("a day's two rates are its whole tokens over its whole seconds, and each run keeps its own", () => {
	// Three items over two runs, written here. Pooled, the day read 3,000 tokens in
	// 5 s and wrote 250 in 4 s. A mean of the items' own rates would say 666.67 and
	// 66.67, which weighs a short article like a long one.
	const item = (runId: string, prefillMs: number, input: number, decodeMs: number, output: number) => ({
		date: '2030-06-15',
		run_id: runId,
		prefill_ms: String(prefillMs),
		decode_ms: String(decodeMs),
		input_tokens: String(input),
		cached_tokens: '100',
		output_tokens: String(output)
	});
	const [day] = throughputWithin(
		new Map([
			[
				'2030-06-15',
				[
					item('2030-06-15-1', 1000, 1100, 2000, 100),
					item('2030-06-15-1', 3000, 1600, 1000, 100),
					item('2030-06-15-2', 1000, 600, 1000, 50)
				]
			]
		]),
		new Map(),
		{ start: '2030-06-15', end: '2030-06-15' }
	);
	// Cached tokens are out of the read count: 3,300 asked less the 300 held.
	expect(day.readTps).toBe(600);
	expect(day.writeTps).toBe(62.5);
	expect(day.items).toBe(3);
	// The candle is the spread of the items' own rates, and each run keeps its median.
	expect(day.read).toEqual({ min: 500, p25: 500, median: 500, p75: 750, max: 1000 });
	expect(day.write).toEqual({ min: 50, p25: 50, median: 50, p75: 75, max: 100 });
	expect(day.runs).toEqual([
		{ runId: '2030-06-15-1', items: 2, read: 750, write: 75 },
		{ runId: '2030-06-15-2', items: 1, read: 500, write: 50 }
	]);
});

/** Three days of the token-rate chart, written here and handed to the chart itself.
 *
 * Reading ran at 40 to 60 tokens a second and writing at 10 to 14, so an axis
 * drawn from zero would spend a sixth of its height on rates nothing ran at.
 * 2030-06-13 ran nothing, and all three days ran on one model, so the line
 * under the chart sets the newest day against the one before it.
 */
function rateSpread(min: number, p25: number, median: number, p75: number, max: number) {
	return { min, p25, median, p75, max };
}

const THROUGHPUT_DAYS: ThroughputDay[] = [
	{
		date: '2030-06-12',
		items: 1,
		read: rateSpread(42, 42, 42, 42, 42),
		write: rateSpread(12, 12, 12, 12, 12),
		readTps: 42,
		writeTps: 12,
		cacheHitPct: 20,
		runs: [{ runId: '2030-06-12-1', items: 1, read: 42, write: 12 }],
		model: 'model-a'
	},
	{
		date: '2030-06-14',
		items: 2,
		read: rateSpread(40, 45, 50, 55, 58),
		write: rateSpread(11, 11.5, 12, 12.5, 13),
		readTps: 50,
		writeTps: 12,
		cacheHitPct: 30,
		runs: [{ runId: '2030-06-14-1', items: 2, read: 50, write: 12 }],
		model: 'model-a'
	},
	{
		date: '2030-06-15',
		items: 3,
		read: rateSpread(45, 50, 55, 58, 60),
		write: rateSpread(10, 10.5, 11, 12, 14),
		readTps: 55,
		writeTps: 11.4,
		cacheHitPct: 38.4,
		runs: [
			{ runId: '2030-06-15-1', items: 2, read: 56, write: 11.5 },
			{ runId: '2030-06-15-2', items: 1, read: 52, write: 11 }
		],
		model: 'model-a'
	}
];

/** The token-rate chart, drawn from `THROUGHPUT_DAYS`. */
async function drawnThroughput(page: Page, testInfo: TestInfo) {
	await drawnChart(page, testInfo, 'ThroughputTrend', { days: THROUGHPUT_DAYS, reference: '#throughput' });
}

test('reading and writing are drawn as separate candles per day', async ({ page }, testInfo) => {
	await drawnThroughput(page, testInfo);

	await expect(page.getByText('Model tokens per second')).toBeVisible();

	// Two series, one candle each on every day that ran. 13 June ran nothing: it
	// keeps its column and draws no candle, rather than a candle sitting on zero.
	const datesOf = (series: string) =>
		page
			.locator(`[data-candle="${series}"]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-date')));
	expect(await datesOf('read')).toEqual(['2030-06-12', '2030-06-14', '2030-06-15']);
	expect(await datesOf('write')).toEqual(['2030-06-12', '2030-06-14', '2030-06-15']);
	await expect(page.locator('[data-day-tick="2030-06-13"]')).toHaveCount(1);

	// The line under the chart is the newest day's whole day, set against the day
	// before it that ran: 55 against 50 tokens a second is up 10%, and 11.4
	// against 12 is down 5%.
	await expect(page.locator('[data-throughput="verdict"]')).toHaveText(
		'2030-06-15, over the whole day: read 55.00 tok/s, write 11.40 tok/s, from 3 items across 2 runs. ' +
			'Read is up 10% and write is down 5% on 2030-06-14.'
	);

	// Milliseconds per token is 1000 / tokens per second, so drawing it too
	// would be the same fact mirrored. It must not come back.
	expect(await page.locator('main').innerText()).not.toContain('ms per token');
});

/** The newest day the throughput chart draws a candle for. The readout under it rests on that day. */
async function newestCandleDay(page: Page): Promise<string> {
	const dates = await page
		.locator('[data-candle="write"]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-date') ?? ''));
	expect(dates.length, 'the chart draws no write candle').toBeGreaterThan(0);
	return [...dates].sort().at(-1) ?? '';
}

test('a candle carries its spread and its runs without a mouse', async ({ page }) => {
	await page.goto('/console/model/');

	const newest = page.locator(`[data-candle="write"][data-date="${await newestCandleDay(page)}"]`);
	// Its name, never a native tooltip: a `<title>` needs a hover, and the strip
	// under the chart prints every word of this sentence for a key and a thumb.
	const caption = (await newest.getAttribute('aria-label')) ?? '';
	await expect(newest.locator('title')).toHaveCount(0);

	expect(caption).toContain('median');
	expect(caption).toContain('middle half');
	// Per run, because a day hides which of its runs moved. The strip rests on this
	// day and lists its runs after the read, write and item rows; the name keeps
	// each run's write rate, which is what tells the runs apart.
	const runs = (
		await page
			.locator('[data-readout="throughput"] [data-readout-row]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''))
	).slice(3);
	expect(runs.length, 'the newest day ran once, so a rate a run is untested').toBeGreaterThan(1);
	expect(caption).toContain(`by run, ${runs[0]} write`);
	for (const run of runs) expect(caption).toContain(`${run} write`);
});

test('the slower of reading and writing sits lower, on one shared scale', async ({ page }) => {
	await page.goto('/console/model/');

	// Each candle's last mark is its median. The strip under the chart rests on the
	// newest day and prints both medians, so the drawing is held to the rates the
	// page itself prints.
	const day = await newestCandleDay(page);
	const medianAt = async (series: string) =>
		Number(await page.locator(`[data-candle="${series}"][data-date="${day}"] line`).last().getAttribute('y1'));
	const rate = async (series: string) =>
		Number(
			/^median ([\d.]+) tok\/s/.exec(
				await page.locator(`[data-readout="throughput"] [data-readout-row="${series}"] dd`).last().innerText()
			)?.[1]
		);
	const read = { y: await medianAt('read'), rate: await rate('read') };
	const write = { y: await medianAt('write'), rate: await rate('write') };
	expect(read.rate, 'reading and writing ran at one median rate, so the scale is untested').not.toBe(write.rate);

	// Y grows downward, so the slower series sits lower on the page. Drawn
	// against their own maxima both would top out and say nothing.
	expect(read.y > write.y, `read ${read.rate} tok/s at y ${read.y}, write ${write.rate} tok/s at y ${write.y}`).toBe(
		read.rate < write.rate
	);
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

test('the throughput axis covers the rates drawn, not zero to the fastest', async ({ page }, testInfo) => {
	await drawnThroughput(page, testInfo);

	// The slowest item wrote at 10 tokens a second and the fastest read at 60.
	// The axis runs from the one to the other and prints both ends. It does not
	// spend a sixth of its height on rates nothing ran at - a candle says where a
	// rate is, and only a mark whose length carries the number needs zero on the axis.
	const ticks = await page
		.locator('[data-throughput-tick]')
		.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('data-throughput-tick'))));
	expect(ticks).toEqual([10, 20, 30, 40, 50, 60]);

	// The prompt-reuse line and its right-hand 0-100% axis are gone. Reuse is a
	// cache statistic, so the newest day's 38.4 stays in the legend as a whole
	// percent, and nothing draws a second y scale a reader could correlate against
	// tokens per second.
	await expect(page.locator('[data-throughput="chart"] polyline')).toHaveCount(0);
	await expect(page.locator('[data-series="reused"]')).toContainText('38%');
});

/** A month's telemetry shard as a test writes it: one row on every day of the month. */
function everyDayOf(month: string): string {
	const [year, number] = month.split('-').map(Number);
	const length = new Date(Date.UTC(year, number, 0)).getUTCDate();
	return telemetryCsv(
		Array.from({ length }, (_, at) => {
			const date = `${month}-${String(at + 1).padStart(2, '0')}`;
			return telemetryRow({ date, run_id: `${date}-1`, item_id: 'served' });
		})
	);
}

test('the telemetry viewport renders the published projection', async ({ page }) => {
	// Every month the page asks for is answered with a shard the test writes, one
	// row on every day of it, so the window the page opens on holds one row a day.
	const asked: string[] = [];
	await page.route('**/telemetry/*.csv', (route) => {
		const month = /\/telemetry\/(\d{4}-\d{2})\.csv$/.exec(new URL(route.request().url()).pathname)?.[1];
		if (month === undefined) return route.fulfill({ status: 404 });
		asked.push(month);
		return route.fulfill({ status: 200, contentType: 'text/csv', body: everyDayOf(month) });
	});
	await page.goto('/console/');

	await expect(page.locator('[data-viewport-control]')).toBeVisible();
	await expect(page.locator('[data-failure-panels]')).toBeVisible();
	await expect(page.locator('[data-band-distance]')).toBeVisible();

	await expect(page.locator('[data-viewport-control]')).toContainText(`${DEFAULT_WINDOW_DAYS} rows in view`);
	expect(asked.length, 'the page asked for no month, so it drew no served row').toBeGreaterThan(0);
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

	// The strip carries every word the candle's sentence does: an SVG `<title>` is
	// a tooltip only a mouse reaches, so the spread, the item count and each run's
	// two rates moved into the strip. The run entries grow with the day's run
	// count, and the strip keeps room for the busiest day's entries.
	await expect(readout.locator('[data-readout-day]')).toHaveText(/^\d+ \w+ \d{4}$/);

	// One row per series drawn, read against write off one hover rather than two,
	// then the day's item count, then one entry a run with both of its rates.
	const rows = await readout
		.locator('[data-readout-row]')
		.evaluateAll((nodes) =>
			nodes.map((node) => (node.getAttribute('data-readout-row') ?? '').trim())
		);
	expect(rows.slice(0, 3)).toEqual(['read', 'write', 'items']);
	expect(rows.length, 'the day printed no run').toBeGreaterThan(3);
	for (const run of rows.slice(3)) expect(run).toMatch(/^run \S+$/);
	for (const series of ['read', 'write']) {
		await expect(readout.locator(`[data-readout-row="${series}"] dd`).last()).toHaveText(
			/^median [\d.]+ tok\/s, middle half [\d.]+ to [\d.]+, slowest [\d.]+, fastest [\d.]+$/
		);
	}

	await expect(page.locator('[data-readout-hint="throughput"]')).toHaveText(
		'Point at a day to read it. Left and Right step through the days, Escape returns to the newest.'
	);
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
	).console?.window_presets ?? [1, 7, 14, 30, 90];
	expect(presets).toContain(span(steppedStart, steppedEnd));
	expect(presets).toContain(span(widerStart, widerEnd));
});

test('panning to a month with no rows leaves a visible gap', async ({ page }) => {
	// The months the page opens on are answered with one row on every day. A month
	// asked for after that is answered with its header and no row.
	const opened: string[] = [];
	let panning = false;
	await page.route('**/telemetry/*.csv', (route) => {
		const month = /\/telemetry\/(\d{4}-\d{2})\.csv$/.exec(new URL(route.request().url()).pathname)?.[1];
		if (month === undefined) return route.fulfill({ status: 404 });
		if (!panning) opened.push(month);
		return route.fulfill({
			status: 200,
			contentType: 'text/csv',
			body: panning ? telemetryCsv([]) : everyDayOf(month)
		});
	});
	await page.goto('/console/');

	const viewport = page.locator('[data-viewport-control]');
	await expect(viewport).toContainText(new RegExp(`(^|\\D)${DEFAULT_WINDOW_DAYS}\\s+rows in view`));
	await expect(page.locator('[data-failure-empty]')).toHaveCount(0);
	panning = true;
	const firstServed = `${[...opened].sort()[0]}-01`;

	// Back, one pan at a time, until the window ends before the first day served.
	await viewport.focus();
	for (let press = 0; press < 60; press += 1) {
		const end = (await viewport.getAttribute('data-window-end')) ?? '';
		if (end < firstServed) break;
		await page.keyboard.press('ArrowLeft');
		await expect(viewport).not.toHaveAttribute('data-window-end', end);
	}
	const end = (await viewport.getAttribute('data-window-end')) ?? '';
	expect(end < firstServed, `the window still ends on ${end}, on or after ${firstServed}`).toBe(true);

	// The failure surface says the window holds nothing rather than drawing a
	// column of zeroes, which would read as a run that went badly.
	await expect(page.locator('[data-failure-empty]')).toBeVisible();
	await expect(viewport).toContainText(/(^|\D)0\s+rows in view/);
});

test('an empty section costs the page that section, never the page', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const missing = watchFor404s(page);

	await page.goto('/console/');

	// The canary records one failed item, so the list has a row to draw and the
	// page carries on around it: the timing chart, the run grid and the score
	// table all still draw. The rows are behind a disclosure now, so what has to
	// survive is the control that reaches them and the scope sentence it carries -
	// not the table itself.
	await expect(page.locator('[data-failure-toggle]')).toBeVisible();
	await expect(page.locator('[data-failure-scope]')).toContainText('in this window.');
	await expect(page.getByText('Time per item, by stage')).toBeVisible();
	await expect(page.locator('[data-grid="days"]')).toBeVisible();
	// The daily rows are behind a disclosure now, so what has to survive is the
	// control that reaches them - not the table itself.
	await expect(page.locator('[data-charts="daily"]')).toBeVisible();
	await expect(page.locator('[data-charts-verdict]')).toBeVisible();

	// And the same on the route the model section moved to, which has its own
	// empty states and its own band above them.
	await page.goto('/console/model/');
	await expect(page.getByRole('heading', { name: 'What the model did' })).toBeVisible();
	await expect(page.locator('[data-console-band]')).toBeVisible();

	// And on the route the feed and source panels moved to on 2026-09-14. The
	// feed table is the surface this test used to check on Pipelines; it is the
	// same check, on the route that now owns it.
	await page.goto('/console/voices/');
	await expect(page.locator('[data-feeds="table"]')).toBeVisible();
	await expect(page.locator('[data-console-band]')).toBeVisible();

	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});

test('a telemetry read holds exactly the window it is handed, however many months are committed', () => {
	// The fixture holds one row a day from 1 May to 10 Jul 2026, in three month
	// shards. The window ends a week before the newest row, as a console window
	// does when the projection has run on past the newest published day.
	const all = telemetryRows(TELEMETRY_FIXTURE);
	const read = telemetryRows(TELEMETRY_FIXTURE, { start: '2026-06-20', end: '2026-07-03' });
	expect(all.rows.length).toBe(71);
	expect(read.rows.map((row) => row.date)).toEqual(days('2026-06-20', 14));
	// Still the same table. The window touches June and July, the two shards a
	// read opens, however many months the pipeline has committed.
	expect(read.columns).toEqual(all.columns);
	expect(telemetryMonths(TELEMETRY_FIXTURE)).toEqual(['2026-05', '2026-06', '2026-07']);
	expect(monthsInWindow({ start: '2026-06-20', end: '2026-07-03' })).toEqual(['2026-06', '2026-07']);
});

test('the days a window read leaves out stay on disk for a pan to reach', () => {
	// Bounding the read must not put a day out of reach. The fortnight before the
	// window is in a shard the browser can still fetch by name.
	const opened = { start: '2026-06-20', end: '2026-07-03' };
	const back = panWindow(opened, -14);
	expect(back).toEqual({ start: '2026-06-06', end: '2026-06-19' });
	expect(telemetryMonths(TELEMETRY_FIXTURE)).toContain('2026-06');

	const older = telemetryRows(TELEMETRY_FIXTURE, back).rows;
	expect(older.map((row) => row.date)).toEqual(days('2026-06-06', 14));
	const readIds = new Set(telemetryRows(TELEMETRY_FIXTURE, opened).rows.map((row) => row.item_id));
	expect(older.filter((row) => readIds.has(row.item_id))).toEqual([]);
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

/** Every row of the daily chart table, as the page prints it. */
async function chartRows(page: Page) {
	return page.locator('[data-chart-day]').evaluateAll((rows) =>
		rows.map((row) => {
			const cell = (name: string) =>
				(row.querySelector(`[data-charts-cell="${name}"]`)?.textContent ?? '').trim();
			return {
				date: row.getAttribute('data-chart-day') ?? '',
				reached: cell('reached'),
				asked: cell('asked'),
				drafted: cell('drafted'),
				published: cell('published'),
				items: cell('items'),
				minutes: cell('minutes'),
				perChart: cell('per-chart')
			};
		})
	);
}

test('every chart row is a day of the window, newest first, and its rates follow its own counts', async ({ page }) => {
	await page.goto('/console/');
	await openDailyCharts(page);

	const rows = await chartRows(page);
	expect(rows.length, 'the window reaches no published day, so this asserts nothing').toBeGreaterThan(0);
	// Newest first, once each, and every day inside the open window. Days older
	// than the window are the section's own answer to a preset the reader picked,
	// not rows that went missing.
	const viewport = page.locator('[data-viewport-control]');
	const start = (await viewport.getAttribute('data-window-start')) ?? '';
	const end = await windowEnd(page);
	const dates = rows.map((row) => row.date);
	expect(dates).toEqual([...dates].sort().reverse());
	expect(new Set(dates).size).toBe(dates.length);
	for (const date of dates) expect(date >= start && date <= end, `${date} is outside ${start} to ${end}`).toBe(true);

	for (const row of rows) {
		for (const count of [row.reached, row.asked, row.drafted, row.published, row.items]) {
			expect(count, row.date).toMatch(/^\d+$/);
		}
		// Every item the planner was asked about reached it first.
		expect(Number(row.reached), row.date).toBeGreaterThanOrEqual(Number(row.asked));
		// Minutes print to one decimal, or as a dash where the planner timed nothing.
		// A cost per visual exists only where both the minutes and a published visual do,
		// and it is the minutes shared out over them.
		expect(row.minutes, row.date).toMatch(/^(-|\d+\.\d)$/);
		if (row.minutes === '-' || row.published === '0') expect(row.perChart, row.date).toBe('-');
		else {
			expect(row.perChart, row.date).toMatch(/^\d+\.\d$/);
			expect(Math.abs(Number(row.perChart) - Number(row.minutes) / Number(row.published)), row.date).toBeLessThanOrEqual(0.1);
		}
	}
});

test('the measured day prints rates, and the day with no minutes prints dashes', async ({
	page
}) => {
	await page.goto('/console/');
	await openDailyCharts(page);

	// Both states this table has to tell apart are in the window: a day the planner
	// timed and published a visual on, which prints its minutes and a cost per
	// visual; and a day the planner never started, whose minutes do not exist.
	// Zero minutes would be an invention, and a per-visual cost over no visuals is
	// not a number at all.
	const rows = await chartRows(page);
	const measured = rows.filter((row) => row.minutes !== '-' && row.published !== '0');
	const unmeasured = rows.filter((row) => row.minutes === '-');
	expect(measured.length, 'no day in the window was timed and published a visual').toBeGreaterThan(0);
	expect(unmeasured.length, 'every day in the window was timed, so the dash is untested').toBeGreaterThan(0);
	for (const row of measured) expect(row.perChart, row.date).not.toBe('-');
	for (const row of unmeasured) expect(row.perChart, row.date).toBe('-');
});

test('a visual that never drew is a visual and is not a published chart', () => {
	// A day that published four items: two charts that drew, one chart whose drawing
	// failed, and one with no visual. The column is headed `Visuals published` since
	// 2026-08-31 but still counts only rendered charts, because counting every visual
	// would put a picture nobody can see on chart drawing's bill and chart drawing
	// would look more productive than it is.
	const { digest } = publishedSite(test.info().outputPath('site'), { published: ['2030-06-15'] });
	const item = (n: number, visual: { kind: string; state: string } | null) => ({ item_id: `item-${n}`, visual });
	writeFileSync(
		join(digest, '2030', '06', '15', 'digest.json'),
		JSON.stringify({
			date: '2030-06-15',
			items: [
				item(1, { kind: 'chart', state: 'rendered' }),
				item(2, { kind: 'chart', state: 'rendered' }),
				item(3, { kind: 'chart', state: 'render_failed' }),
				item(4, null)
			]
		})
	);
	expect(publishedCharts(digest, 1)).toEqual(new Map([['2030-06-15', { items: 4, charts: 2 }]]));
});

test('no console route reads the word router to an operator', async ({ page }) => {
	// `router` named this pipeline stage until 2026-09-05, and CLAUDE.md section
	// 0b bars a subsystem word from a string a person reads. The word is gone from
	// the code as well now, so this is a ban list: it holds the old name out of
	// every reader string whatever a later row calls the stage.
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
	const section = page.locator('[data-windowed="chart-drawing"]');
	await expect(section.locator('[data-rule-figure]')).toHaveCount(2);
	await expect(section.locator('[data-target-bar]')).toHaveCount(2);
	await expect(section.locator('[data-sparkline]')).toHaveCount(2);
	await expect(page.locator('[data-flow]')).toHaveCount(1);
	await expect(page.locator('[data-charts="table"] thead th')).toHaveCount(8);
});

/** The daily figures sit behind a disclosure now; the cards above them lead.
 *
 * Opening it is a reader's own action, so a test that reads a cell takes it
 * too. `console-model.spec.ts` owns the cards and the control itself.
 */
async function openDailyFigures(page: Page) {
	await page.locator('[data-model-table-control] > summary').click();
	await expect(page.locator('[data-model="table"]')).toBeVisible();
}

/** Every day row of the model table, as the page prints it: each cell by its column key. */
async function modelRows(page: Page): Promise<{ date: string; cells: Record<string, string> }[]> {
	return page.locator('[data-model-day]').evaluateAll((rows) =>
		rows.map((row) => ({
			date: row.getAttribute('data-model-day') ?? '',
			cells: Object.fromEntries(
				[...row.querySelectorAll('[data-model-cell]')].map((cell) => [
					cell.getAttribute('data-model-cell') ?? '',
					(cell.textContent ?? '').replace(/\s+/g, ' ').trim()
				])
			)
		}))
	);
}

/** How each column of the model table prints a value: a count, a whole percent, or
 * whole units of time with `<1` for work too short to round to one. A day the
 * ledger holds no answer for prints a dash. Which values are absent is the model
 * work's own rule, pinned over rows written in `console-model-work.spec.ts`. */
const MODEL_CELL: Record<string, RegExp> = {
	summaries: /^(-|\d+)$/,
	'not-sure': /^(-|\d+)$/,
	unsupported: /^(-|\d+)$/,
	hedge: /^(-|\d+)$/,
	part: /^(-|\d+)$/,
	'part-pct': /^(-|\d+%)$/,
	copied: /^(-|\d+%)$/,
	'per-item': /^(-|(<1|\d+)( (<1|\d+) when cut short)?)$/,
	minutes: /^(-|<1|\d+)$/,
	'too-long': /^(-|\d+)$/,
	failed: /^(-|\d+)$/
};

test('every model cell prints a count, a share, a time or a dash, on a day of the window', async ({ page }) => {
	await page.goto('/console/model/');
	await openDailyFigures(page);

	const rows = await modelRows(page);
	expect(rows.length, 'the window reaches no worked day, so this asserts nothing').toBeGreaterThan(0);
	// Newest first, once each, and inside the window the table says it follows. A
	// day the pipeline found no article on gets no row at all: a row of zeroes would
	// read as a day that went badly rather than a day with nothing in it.
	const windowDays = Number(await page.locator('[data-model-table-control]').getAttribute('data-window-days'));
	const dates = rows.map((row) => row.date);
	expect(dates).toEqual([...dates].sort().reverse());
	expect(new Set(dates).size).toBe(dates.length);
	const spanned = (Date.parse(`${dates[0]}T00:00:00Z`) - Date.parse(`${dates.at(-1)}T00:00:00Z`)) / 86_400_000 + 1;
	expect(spanned, `the rows run past the ${windowDays} days the table follows`).toBeLessThanOrEqual(windowDays);
	for (const row of rows) {
		expect(Object.keys(row.cells).sort()).toEqual(Object.keys(MODEL_CELL).sort());
		for (const [key, printed] of Object.entries(row.cells)) {
			expect(printed, `${row.date} ${key}`).toMatch(MODEL_CELL[key]);
		}
	}
});

test('a day the scorer never reached prints dashes, and still prints its speed', async ({
	page
}) => {
	await page.goto('/console/model/');
	await openDailyFigures(page);

	// A day the scorer never reached has summaries nobody counted, so every figure
	// the scorer makes prints a dash rather than a zero that would say the model
	// wrote nothing.
	const rows = await modelRows(page);
	const unscored = rows.filter((row) => row.cells.summaries === '-');
	expect(unscored.length, 'every day in the window was scored, so the dashes are untested').toBeGreaterThan(0);
	for (const row of unscored) {
		for (const cell of ['not-sure', 'unsupported', 'hedge', 'part', 'part-pct', 'copied']) {
			expect(row.cells[cell], `${row.date} ${cell}`).toBe('-');
		}
	}
	// Speed is measured by the runtime, not by the scorer, so it still prints.
	expect(
		unscored.some((row) => row.cells['per-item'] !== '-' && row.cells.minutes !== '-'),
		'no day the scorer never reached was timed, so the speed half is untested'
	).toBe(true);

	// And a scored day is not all dashes, which is what stops the check above
	// passing on a table that prints nothing.
	const scored = rows.filter((row) => row.cells.summaries !== '-');
	expect(scored.length, 'no day in the window was scored').toBeGreaterThan(0);
	for (const row of scored) expect(row.cells.copied, row.date).not.toBe('-');
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
	// page. Every one of these is a real column of the eval ledger or the
	// item-health ledger.
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
