import { expect, test } from '@playwright/test';

import { bandShares, readoutCapStyle } from '../src/lib/charts/frame';
import { stacked } from '../src/lib/charts/stacked';
import {
	countersWithoutScores,
	measurementOff,
	recordingNotes,
	recordingStarted,
	sampledAt,
	scoresWithoutCounters
} from '../src/lib/console/recording';

/** Chart chrome, and the states a panel is in when the ledger has no answer.
 *
 * Two rules are under test and they are the whole of both rows.
 *
 * **Every chart resolves to non-empty accessible text.** Prose the page cut
 * still lives in the description, so a reader who cannot see the shape loses
 * nothing - and that is an oracle rather than a promise, because it is checked
 * on every chart of all three routes.
 *
 * **A chart that plots more than one series prints them together.** A fixed
 * strip below the plot, capped at a share of it, reachable by an arrow key. A
 * tooltip is never the only place a value appears: a tooltip needs a hover, and
 * a hover is not a thing a thumb can do.
 */

const ROUTES = ['/console/', '/console/model/', '/console/machine/'];

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

test.describe('what the recording was doing, in the owner words', () => {
	test('measurement off names the day it stopped and never the knob', () => {
		const said = measurementOff('2026-08-29');
		expect(said).toBe(
			'Measurement is off. Nothing has been recorded since 29 Aug 2026, so the figures below stop on that day. Turn it back on in config/idhazh.json.'
		);
		// A term from a subsystem is not a term for a user (CLAUDE.md section 0b).
		expect(said).not.toContain('runtime_counters_scrape');
		expect(said).not.toContain('evaluation_enabled');
	});

	test('measurement off with nothing on record says so rather than dating it', () => {
		expect(measurementOff(null)).toBe(
			'Measurement is off. Nothing has been recorded at all. Turn it back on in config/idhazh.json.'
		);
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
		expect(notes.off).toBeNull();
		expect(notes.sampled).toBeNull();
		expect(notes.startedMidWindow).toContain('Recording started on 27 Aug 2026');
		expect(notes.startedMidWindow).toContain('The 2 days before it have');
	});

	test('a switched-off instrument owes no sampling caveat as well', () => {
		const notes = recordingNotes({
			enabled: false,
			rate: 0.25,
			recorded: ['2026-08-29'],
			window: ['2026-08-29']
		});
		expect(notes.off).toContain('Measurement is off.');
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

	test(`every readout strip on ${route} stays inside its cap`, async ({ page }) => {
		await page.goto(route, { waitUntil: 'domcontentloaded' });

		const strips = page.locator('[data-readout]');
		const count = await strips.count();
		expect(count, 'the route prints at least one readout').toBeGreaterThan(0);

		for (let at = 0; at < count; at += 1) {
			const strip = strips.nth(at);
			// The measured defect was a readout box taking 40 to 55 percent of the
			// chart it explained. The cap is a share, so it holds at every width.
			const style = await strip.getAttribute('style');
			expect(style, 'the strip carries its own cap').toMatch(/max-width: \d+\.\d\d%/);
			const share = Number((style ?? '').replace(/[^\d.]/g, ''));
			expect(share).toBeLessThanOrEqual(33);

			// Below the plot, never over it. A strip that floats can cover the mark
			// it is explaining, and a floating box that dodges moves it instead.
			await expect(strip).toHaveCSS('position', 'static');
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

	const strip = page.locator('[data-readout="cache"]');
	await expect(strip, 'the stacked cache chart carries a strip').toHaveCount(1);

	const rows = await strip
		.locator('[data-readout-row]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
	expect(rows).toEqual(['Read', 'Served from cache']);
});

test('an arrow key moves an engine chart readout and draws a guide', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	const frame = page.locator('[data-chart-readout="cache"]');
	await expect(frame).toHaveCount(1);
	const head = page.locator('[data-readout="cache"] [data-readout-day]');
	const resting = await head.textContent();

	// The keyboard is the point. A tooltip that only a pointer can raise leaves
	// a value with nowhere to appear on a phone or under a screen reader.
	await frame.focus();
	await page.keyboard.press('Home');
	await expect(page.locator('[data-chart-guide="cache"]')).toHaveCount(1);
	expect(await head.textContent()).not.toBe(resting);

	// Escape returns it to rest, and the guide goes with it.
	await page.keyboard.press('Escape');
	await expect(page.locator('[data-chart-guide="cache"]')).toHaveCount(0);
	expect(await head.textContent()).toBe(resting);
});

test('the shape switch is one control per panel and reaches the chart', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	const control = page.locator('[data-shape-switch="cache"]');
	await expect(control, 'one control, not one per series').toHaveCount(1);
	await expect(control).toHaveAttribute('data-shape', 'bars');

	// The label, not the input: the segment box sits over it, which is exactly the
	// trap `console-window.spec.ts` already records for the window presets.
	await control.locator('[data-shape-option="lines"]').click();
	await expect(control).toHaveAttribute('data-shape', 'lines');
	await control.locator('[data-shape-option="bars"]').click();
	await expect(control).toHaveAttribute('data-shape', 'bars');
});

test('a route in a state says which state, in the owner words', async ({ page }) => {
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
		expect(note.text).not.toContain('runtime_counters_scrape');
		expect(note.text).not.toContain('evaluation_enabled');
		expect(note.text).not.toContain('sample_rate');
	}
});

test('the machine route never prints a zero where the ledger holds no answer', async ({ page }) => {
	await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });

	// `data-host-value` carries the cell's own reading. Empty is absent, and an
	// absent cell has to say so in words - a zero there would report a processor
	// that never idled and a server that used no memory.
	const cells = await page
		.locator('[data-host-value]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				value: node.getAttribute('data-host-value') ?? '',
				text: (node.textContent ?? '').trim()
			}))
		);
	expect(cells.length).toBeGreaterThan(0);
	for (const cell of cells) {
		if (cell.value !== '') continue;
		expect(cell.text).toContain('Not recorded on this run.');
		expect(cell.text).not.toMatch(/(^|[^\d])0([^\d.%]|$)/);
	}
});
