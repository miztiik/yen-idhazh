import { expect, test } from './support/browser';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { bandShares } from '../src/lib/charts/frame';
import { readoutCapStyle } from '../src/lib/charts/readout';
import { stacked } from '../src/lib/charts/stacked';
import {
	countersWithoutScores,
	measurementOff,
	recordDestroyed,
	recordingNotes,
	recordingStarted,
	sampledAt,
	scoresWithoutCounters,
	type OfferedWindow,
	type RecordRead
} from '../src/lib/console/recording';
import type { HeldPeriod } from '../src/lib/data/slice';

/** `chart.readout_max_share`, read off the committed config inside the test
 * that uses it, so a malformed file fails one test rather than the module. */
function readoutMaxShare(): number {
	const config = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'config', 'appearance.json');
	return (JSON.parse(readFileSync(config, 'utf8')) as { chart: { readout_max_share: number } }).chart
		.readout_max_share;
}

/** Chart chrome, and the states a panel is in when the ledger has no answer.
 *
 * Two rules are under test and they are the whole of both rows.
 *
 * **Every chart resolves to non-empty accessible text.** Prose the page cut
 * still lives in the description, so a reader who cannot see the shape loses
 * nothing - and that is an oracle rather than a promise, because it is checked
 * on every chart of every route that draws one with a readout strip.
 *
 * **A chart that plots more than one series prints them together.** A fixed
 * strip below the plot, as wide as the plot at most, its entries side by side,
 * reachable by an arrow key. A tooltip is never the only place a value
 * appears: a tooltip needs a hover, and a hover is not a thing a thumb can do.
 */

// `/console/voices/` is NOT here, and that is a decision rather than an
// oversight. Every block below needs a strip to read, and the two day matrices
// on that route declare they have none: each square already names its own day
// and what that day did, so a strip would reprint the list the pointer is
// already on. An `if` inside this loop to walk past them is how a route list
// stops meaning one thing.
const ROUTES = ['/console/', '/console/model/', '/console/machine/', '/console/judgement/'];

test.describe('the shape switch draws one array two ways', () => {
	const COLUMNS = ['Mon', 'Tue', 'Wed'];
	const SERIES = [
		{ label: 'fetch', token: '--chart-1' as const, values: [3, 1, 4] },
		{ label: 'extract', token: '--chart-2' as const, values: [1, 5, 9] }
	];

	/** Every series' `data`, in drawing order. */
	function drawn(option: Record<string, unknown>): unknown[][] {
		const series = option.series as { data: unknown[] }[];
		return series.map((one) => one.data);
	}

	test('both shapes hand the engine byte-for-byte the same values', () => {
		const bars = stacked(COLUMNS, SERIES, 'bars');
		const lines = stacked(COLUMNS, SERIES, 'lines');

		// The row's own test for whether a chart may carry the switch at all: the
		// presence of a transform is the definition of "not cheap". If these two
		// ever disagree, the switch is re-shaping data and has to be withdrawn.
		expect(drawn(lines.option as Record<string, unknown>)).toEqual(
			drawn(bars.option as Record<string, unknown>)
		);
		expect(drawn(bars.option as Record<string, unknown>)).toEqual([
			[3, 1, 4],
			[1, 5, 9]
		]);
	});

	test('only the type and the stack differ between them', () => {
		const bars = (stacked(COLUMNS, SERIES, 'bars').option as { series: Record<string, unknown>[] })
			.series;
		const lines = (stacked(COLUMNS, SERIES, 'lines').option as { series: Record<string, unknown>[] })
			.series;

		expect(bars.map((one) => one.type)).toEqual(['bar', 'bar']);
		expect(lines.map((one) => one.type)).toEqual(['line', 'line']);
		// Stacked is the only one that stacks. A line drawn from a stack baseline
		// would be a cumulative reading wearing a line's clothes.
		expect(bars.every((one) => one.stack === 'total')).toBe(true);
		expect(lines.every((one) => one.stack === undefined)).toBe(true);
	});

	test('bars is the default, so the server and the first paint agree', () => {
		const drawnBars = (stacked(COLUMNS, SERIES).option as { series: { type: string }[] }).series;
		expect(drawnBars.map((one) => one.type)).toEqual(['bar', 'bar']);
	});
});

test.describe('a readout column sits where the engine drew it', () => {
	test('the shares account for the grid insets', () => {
		// Four columns in a 600px element with 48 left and 12 right: the plot is
		// 540 wide, a column is 135, and the first centre sits at 48 + 67.5.
		const shares = bandShares(4, 600, { left: 48, right: 12 });
		expect(shares.map((share) => Math.round(share * 600))).toEqual([116, 251, 386, 521]);
	});

	test('an element with no width and a chart with no columns give nothing', () => {
		expect(bandShares(4, 0, { left: 48, right: 12 })).toEqual([]);
		expect(bandShares(0, 600, { left: 48, right: 12 })).toEqual([]);
	});

	test('the cap is a share of the plot and never more than all of it', () => {
		expect(readoutCapStyle(0.33)).toBe('max-width: 33.00%');
		expect(readoutCapStyle(2)).toBe('max-width: 100.00%');
	});
});

test.describe('what the recording was doing, in fixed words', () => {
	/** The windows the control offers, each ending on 15 Jun 2030, the newest published day. */
	const OFFERED: OfferedWindow[] = [
		{ days: 1, start: '2030-06-15', end: '2030-06-15' },
		{ days: 7, start: '2030-06-09', end: '2030-06-15' },
		{ days: 14, start: '2030-06-02', end: '2030-06-15' },
		{ days: 30, start: '2030-05-17', end: '2030-06-15' },
		{ days: 90, start: '2030-03-18', end: '2030-06-15' }
	];

	/** A record read whole, packed as far as `through`, whose newest rows are in `lastRows`. */
	const packed = (through: string, lastRows: HeldPeriod | null): RecordRead => ({
		state: 'read',
		through,
		lastRows,
		lostDays: [],
		setAside: {}
	});

	/** The line a switched-off instrument prints over the `days`-day window. */
	const offOver = (days: number, read: RecordRead, recorded: string[] = []) =>
		measurementOff({
			enabled: false,
			recorded,
			read,
			open: OFFERED.find((window) => window.days === days)!,
			offered: OFFERED
		});

	test('a measurement that is on prints no line', () => {
		expect(
			measurementOff({
				enabled: true,
				recorded: [],
				read: packed('2030-06-14', null),
				open: OFFERED[2]!,
				offered: OFFERED
			})
		).toBeNull();
	});

	test('measurement off names the newest day it recorded in the window, and never the knob', () => {
		const said = offOver(14, packed('2030-06-14', { period: 'daily', covers: '2030-06-12' }), [
			'2030-05-06',
			'2030-06-10',
			'2030-06-12'
		]);
		expect(said).toBe('Measurement is off. Nothing has been recorded since 12 Jun 2030. Turn it on in config/idhazh.json.');
		// A term from a subsystem is not a term for a user (CLAUDE.md section 0b).
		expect(said).not.toContain('host_fingerprint');
		expect(said).not.toContain('evaluation_enabled');
	});

	test('a window that holds no recorded day names none, and names the window that reaches back to the last one', () => {
		const stopped = packed('2030-06-14', { period: 'daily', covers: '2030-05-06' });
		// 6 May 2030 is the last day this record recorded, and it is in the 90-day window
		// alone, so every narrower window names that window and not the day.
		expect(offOver(7, stopped, ['2030-05-06'])).toBe(
			'Measurement is off. Nothing was recorded in these 7 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
		expect(offOver(30, stopped, ['2030-05-06'])).toBe(
			'Measurement is off. Nothing was recorded in these 30 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
		// Packed as far as the window's one day, which held no row: the window names its day.
		expect(offOver(1, packed('2030-06-15', { period: 'daily', covers: '2030-05-06' }))).toBe(
			'Measurement is off. Nothing was recorded on 15 Jun 2030. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
	});

	test('a window reaches back to a closed month only when it holds the whole month', () => {
		// The 90-day window starts on 18 Mar 2030: it holds the whole of April and part of March.
		expect(offOver(14, packed('2030-06-14', { period: 'monthly', covers: '2030-04' }))).toBe(
			'Measurement is off. Nothing was recorded in these 14 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'
		);
		expect(offOver(14, packed('2030-06-14', { period: 'monthly', covers: '2030-03' }))).toBe(
			'Measurement is off. Nothing was recorded in these 14 days. Turn it on in config/idhazh.json. No window here reaches back to the last recorded day.'
		);
		// The widest window can never point to a wider one.
		expect(offOver(90, packed('2030-06-14', { period: 'yearly', covers: '2029' }))).toBe(
			'Measurement is off. Nothing was recorded in these 90 days. Turn it on in config/idhazh.json. No window here reaches back to the last recorded day.'
		);
	});

	test('measurement off with nothing on record says so in every window, rather than dating it', () => {
		const never = packed('2030-06-14', null);
		for (const window of OFFERED) {
			// The 1-day window holds no packed day, and the record has still never held a row.
			expect(offOver(window.days, never), `the ${window.days}-day window`).toBe(
				'Measurement is off. Nothing has been recorded at all. Turn it on in config/idhazh.json.'
			);
		}
	});

	test('measurement off claims nothing about what was recorded where the page has not read it', () => {
		const said = 'Measurement is off. Turn it on in config/idhazh.json.';
		// Not packed yet, and a read that failed: the note above the line says which.
		expect(offOver(14, { state: 'not-packed' })).toBe(said);
		expect(offOver(14, { state: 'unreadable', at: '2030-06-10', fault: 'file-missing' })).toBe(said);
		// Packed as far as 14 Jun 2030, so the 1-day window of 15 Jun holds no packed day.
		expect(offOver(1, packed('2030-06-14', { period: 'daily', covers: '2030-05-06' }))).toBe(said);
		// The record holds rows on 12 Jun 2030 that the instrument's figures do not use.
		expect(offOver(14, packed('2030-06-14', { period: 'daily', covers: '2030-06-12' }))).toBe(said);
	});

	test('a clean fraction reads as one run in four', () => {
		expect(sampledAt(0.25)).toBe(
			'Measured on 1 run in 4. These figures count the runs we measured and are not scaled up to stand for the rest.'
		);
	});

	test('an unclean rate reads as a percentage, because 1 in 2.7 never happened', () => {
		expect(sampledAt(0.37)).toBe(
			'Measured on 37% of runs. These figures count the runs we measured and are not scaled up to stand for the rest.'
		);
	});

	test('a rate of one owes no caveat', () => {
		expect(sampledAt(1)).toBeNull();
	});

	test('the two one-sided days each name which instrument answered', () => {
		expect(countersWithoutScores()).toBe(
			'The machine ran and we timed it. Nothing scored the summaries, so this day has no quality figure.'
		);
		expect(scoresWithoutCounters()).toBe(
			"The summaries were scored, but the server's own counters were not written down for this day. The speed figures here come from the summariser, not the server."
		);
	});

	test('a gap before the first recorded day is named as a gap in the recording', () => {
		expect(recordingStarted('2026-08-27', 5)).toBe(
			'Recording started on 27 Aug 2026. The 5 days before it have no server figures, and the gap in the chart is a gap in the recording, not a quiet day.'
		);
	});

	test('one day reads as one day, and no gap reads as nothing at all', () => {
		expect(recordingStarted('2026-08-27', 1)).toContain('The 1 day before it has');
		expect(recordingStarted('2026-08-27', 0)).toBeNull();
		expect(recordingStarted(null, 4)).toBeNull();
	});

	test('a live instrument that started mid-window says only that', () => {
		const notes = recordingNotes({
			enabled: true,
			rate: 1,
			recorded: ['2026-08-27', '2026-08-28'],
			window: ['2026-08-25', '2026-08-26', '2026-08-27', '2026-08-28']
		});
		expect(notes.sampled).toBeNull();
		expect(notes.startedMidWindow).toContain('Recording started on 27 Aug 2026');
		expect(notes.startedMidWindow).toContain('The 2 days before it have');
	});

	test('a switched-off instrument owes no sampling caveat as well', () => {
		const notes = recordingNotes({
			enabled: false,
			rate: 0.25,
			recorded: ['2030-06-12'],
			window: ['2030-06-12']
		});
		expect(offOver(14, packed('2030-06-14', { period: 'daily', covers: '2030-06-12' }), ['2030-06-12'])).toBe(
			'Measurement is off. Nothing has been recorded since 12 Jun 2030. Turn it on in config/idhazh.json.'
		);
		// Two sentences about the same absence is one too many: a measurement that
		// is off was not sampled, it was not taken.
		expect(notes.sampled).toBeNull();
	});

	test('a day another instrument covered is named, not drawn as a quiet day', () => {
		const notes = recordingNotes({
			enabled: true,
			rate: 1,
			recorded: ['2026-08-29'],
			window: ['2026-08-28', '2026-08-29'],
			coveredElsewhere: ['2026-08-28', '2026-08-29']
		});
		expect(notes.scoresOnly).toBe(scoresWithoutCounters());
	});

	test('a day that published and kept no row is a loss, not a quiet day', () => {
		// The fixture is the state that destroyed 303 rows on 2026-09-16: the day
		// file exists and holds only its header, and the digest for that date
		// carries articles. Built, never read off the archive - a case the archive
		// holds today ages out of every window, and a test timed to go red on a
		// date nobody set is a fuse (`CLAUDE.md` section 13).
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-17'],
			window: ['2026-09-16', '2026-09-17'],
			lost: [{ date: '2026-09-16', articles: 431 }],
			figures: 'machine record'
		});
		// The whole point. Counted as a gap, the lost day would date the record's
		// own start to the day AFTER the loss and hand that back as the reason.
		expect(notes.startedMidWindow).toBeNull();
		expect(notes.recordDestroyed).toBe(
			'This day published 431 articles and its machine record is missing. The run worked; what it measured about the machine did not survive.'
		);
	});

	test('a gap and a loss are told apart inside one window', () => {
		// A window wide enough to reach days before the record shipped AND to hold
		// the day it lost. Both sentences are owed, and neither may absorb the
		// other: one says go and look at the instrument, one says open an incident.
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-17'],
			window: ['2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17'],
			lost: [{ date: '2026-09-16', articles: 431 }],
			figures: 'machine record'
		});
		// The record ran on the day it lost, so that day dates its start; the day
		// after the loss would be the lie the loss sentence exists to stop.
		expect(notes.startedMidWindow).toContain('Recording started on 16 Sep 2026.');
		expect(notes.startedMidWindow).toContain('The 2 days before it have no machine record');
		expect(notes.recordDestroyed).not.toBeNull();
	});

	test('a day the record has no record for is a day it ran, never a day before it started', () => {
		// The record's own index says the day was lost: an empty day, then a lost one,
		// then the first day with rows. Counted the old way, the note said recording
		// started on the day after the loss.
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-08-20'],
			window: ['2026-08-17', '2026-08-19', '2026-08-20'],
			daysWithNoRecord: ['2026-08-19'],
			figures: 'machine record'
		});
		expect(notes.startedMidWindow).toBe(
			'Recording started on 19 Aug 2026. The 1 day before it has no machine record, and the gap in the chart is a gap in the recording, not a quiet day.'
		);
		const lostFirst = recordingNotes({
			enabled: true,
			recorded: ['2026-08-20'],
			window: ['2026-08-19', '2026-08-20'],
			daysWithNoRecord: ['2026-08-19']
		});
		expect(lostFirst.startedMidWindow).toBeNull();
	});

	test('a day the record kept a row of is never counted as lost', () => {
		// The caller does the join over two ledgers, so the one thing this can be
		// handed is a date the record answered for after all.
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-16', '2026-09-17'],
			window: ['2026-09-16', '2026-09-17'],
			lost: [{ date: '2026-09-16', articles: 431 }]
		});
		expect(notes.recordDestroyed).toBeNull();
	});

	test('several lost days are one sentence that counts them', () => {
		expect(recordDestroyed([])).toBeNull();
		expect(
			recordDestroyed([
				{ date: '2026-09-15', articles: 400 },
				{ date: '2026-09-16', articles: 31 }
			])
		).toBe(
			'2 days published 431 articles between them and their machine record is missing. The runs worked; what they measured about the machine did not survive.'
		);
		// One article reads as one article, because "1 articles" is the tell that a
		// sentence was assembled rather than written.
		expect(recordDestroyed([{ date: '2026-09-16', articles: 1 }])).toContain('published 1 article and');
	});

	test('an instrument with no sampling knob owes no sampling caveat', () => {
		const notes = recordingNotes({
			enabled: true,
			recorded: ['2026-09-17'],
			window: ['2026-09-17']
		});
		expect(notes.sampled).toBeNull();
	});
});

for (const route of ROUTES) {
	test(`every chart on ${route} resolves to non-empty accessible text`, async ({ page }) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		// Prose cut from the visible page lives here, so this is the oracle that
		// says a screen-reader reader lost nothing. It may not regress.
		const named = await page.locator('svg[role="img"], figure.chart').evaluateAll((nodes) =>
			nodes.map((node) => {
				const own = (node.getAttribute('aria-label') ?? '').trim();
				const by = node.getAttribute('aria-describedby');
				const referenced = by
					? (by
							.split(/\s+/)
							.map((id) => document.getElementById(id)?.textContent ?? '')
							.join(' ')
							.trim() ?? '')
					: '';
				return { text: own || referenced, tag: node.tagName.toLowerCase() };
			})
		);

		expect(named.length, 'the route drew at least one chart').toBeGreaterThan(0);
		expect(named.filter((one) => one.text.length === 0)).toEqual([]);
	});

	test(`every readout strip on ${route} stays inside its cap and lays its entries side by side`, async ({
		page
	}) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		const strips = page.locator('[data-readout]');
		const count = await strips.count();
		expect(count, 'the route prints at least one readout').toBeGreaterThan(0);
		const cap = readoutMaxShare();

		for (let at = 0; at < count; at += 1) {
			const strip = strips.nth(at);
			// Either spelling of the same share. The server writes `100.00%` and
			// Svelte's client-side setter normalises it to `100%`, so since
			// 2026-09-09 - when the console started drawing charts from rows it
			// fetches, and their strips are created in the browser - one page
			// carries both. The number is what this checks.
			const style = await strip.getAttribute('style');
			expect(style, 'the strip carries its own cap').toMatch(/max-width: \d+(\.\d+)?%/);
			const share = Number((style ?? '').replace(/[^\d.]/g, ''));
			expect(share).toBeLessThanOrEqual(cap * 100 + 0.005);

			// Below the plot, never over it. A strip that floats can cover the mark
			// it is explaining, and a floating box that dodges moves it instead.
			await expect(strip).toHaveCSS('position', 'static');

			// The defect this layout replaced: a cap of a third of the plot left a
			// phone's strip 119 px wide and stacked every entry on a line of its
			// own. An entry may start a new line only where it would not have
			// fitted on the line before it. A new line is read from where the entry
			// starts, not from its top: the strip aligns entries on their baseline,
			// so two on one line can sit a few pixels apart vertically. There is no
			// slack in the fit: the browser wraps an entry that misses by a fifth of
			// a pixel, and a box is measured exactly, to a sixty-fourth of one.
			const early = await strip.evaluate((node) => {
				const room = node.getBoundingClientRect().right;
				const gap = parseFloat(getComputedStyle(node).columnGap) || 0;
				const boxes = [...node.querySelectorAll(':scope > [data-readout-row]')].map((entry) =>
					entry.getBoundingClientRect()
				);
				return boxes.filter(
					(box, index) =>
						index > 0 &&
						box.left <= boxes[index - 1].left + 1 &&
						boxes[index - 1].right + gap + box.width <= room + 0.02
				).length;
			});
			expect(early, 'an entry went to a new line while it fitted on the last one').toBe(0);
		}
	});

	test(`every readout strip on ${route} opens on a column rather than blank`, async ({ page }) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		const heads = page.locator('[data-readout] [data-readout-day]');
		const count = await heads.count();
		expect(count).toBeGreaterThan(0);
		for (let at = 0; at < count; at += 1) {
			await expect(heads.nth(at)).not.toHaveText('');
		}
	});
}

test('a hand-written multi-series chart prints every series at one column', async ({ page }) => {
	await page.goto('/console/', { waitUntil: 'domcontentloaded' });

	// The failure chart is the hardest shape on the page to read one band off:
	// columns on the left axis, a rate line per stage on the right. Comparing them
	// by eye is what the strip replaces, and four hovers is what it replaces.
	const strip = page.locator('[data-readout="failure-rate"]');
	await expect(strip).toHaveCount(1);

	const rows = await strip
		.locator('[data-readout-row]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
	expect(rows.length, 'more than one series is printed').toBeGreaterThan(1);
	expect(new Set(rows).size, 'no series is printed twice').toBe(rows.length);
	// Where the items stopped AND what share that was, at one column. A stack
	// without its own rate beside it is the reading this chart exists to refuse.
	expect(rows.some((row) => row.endsWith(' rate'))).toBe(true);
});

test('an engine-drawn chart prints both its series at one column', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// The two-clocks chart is the one this rule exists for: two readings of one
	// quantity on a shared axis, which is exactly the comparison a reader would
	// otherwise make by eye, one hover at a time.
	const strip = page.locator('[data-readout="clocks"]');
	await expect(strip, 'the two-instrument chart carries a strip').toHaveCount(1);

	const rows = await strip
		.locator('[data-readout-row]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
	// Both instruments, and the gap between them, at the column the reader is on.
	expect(rows).toEqual(['Item ledger', 'Model server', 'Apart']);
});

test('an arrow key moves an engine chart readout and draws a guide', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// One column a run, and a run id is unique, so the column Home lands on can
	// never print what the resting column prints.
	const frame = page.locator('[data-chart-readout="read-against-written"]');
	await expect(frame).toHaveCount(1);
	const head = page.locator('[data-readout="read-against-written"] [data-readout-day]');
	const resting = await head.textContent();

	// The keyboard is the point. A tooltip that only a pointer can raise leaves
	// a value with nowhere to appear on a phone or under a screen reader.
	await frame.focus();
	await page.keyboard.press('Home');
	await expect(page.locator('[data-chart-guide="read-against-written"]')).toHaveCount(1);
	expect(await head.textContent()).not.toBe(resting);

	// Escape returns it to rest, and the guide goes with it.
	await page.keyboard.press('Escape');
	await expect(page.locator('[data-chart-guide="read-against-written"]')).toHaveCount(0);
	expect(await head.textContent()).toBe(resting);
});

test('the shape switch is one control per panel and reaches the chart', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// The counterfactual panel carries the one switch on this route that names
	// shapes; the other two name units and grains.
	const control = page.locator('[data-shape-switch="cost-shape"]');
	await expect(control, 'one control, not one per series').toHaveCount(1);
	await expect(control).toHaveAttribute('data-shape', 'daily');
	const chart = page.locator('[data-chart-readout="counterfactual-cost"]');

	// The label, not the input: the segment box sits over it, which is exactly the
	// trap `console-window.spec.ts` already records for the window presets.
	await control.locator('[data-shape-option="running"]').click();
	await expect(control).toHaveAttribute('data-shape', 'running');
	// And it reaches the chart rather than only its own fieldset. The accessible
	// name is where a reader who cannot see the marks is told which shape it is,
	// so a switch that moved the radio and left the drawing named as before is a
	// defect this file owns.
	await expect(chart, 'the chart is still named as the shape the switch left').toHaveAttribute(
		'aria-label',
		/added up day by day/
	);
	await control.locator('[data-shape-option="daily"]').click();
	await expect(control).toHaveAttribute('data-shape', 'daily');
	await expect(chart).toHaveAttribute('aria-label', /one column a day/);
});

test('a route in a state says which state, in fixed words', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// The states are the panel rather than a replacement for it, so the heading
	// above them is still there. A route that hid itself until it had data would
	// be a route nobody knew to check.
	await expect(page.locator('[data-machine="intro"]')).toHaveCount(1);

	const notes = await page
		.locator('[data-recording]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				state: node.getAttribute('data-recording') ?? '',
				text: (node.textContent ?? '').trim()
			}))
		);
	expect(notes.length, 'the fixture reaches at least one recording state').toBeGreaterThan(0);
	for (const note of notes) {
		expect(note.text.length).toBeGreaterThan(0);
		// Never the knob's name, and never styled as an error.
		expect(note.text).not.toContain('host_fingerprint');
		expect(note.text).not.toContain('evaluation_enabled');
		expect(note.text).not.toContain('sample_rate');
	}
});

// The route-wide sweep for a nought standing in for an absent reading lived
// here, and its only instrument was the host panel's own `data-host-value`
// cells. With that panel gone the sweep had nothing to walk. What is left is
// the per-panel rule, which is where the fault would be written: the memory
// board's absent cells in `console-memory-board.spec.ts` and the shard cells in
// `console-machine-data.spec.ts`. What nobody checks now is a NEW panel landing
// on this route with the fault, which is a check the panel that lands owes.
