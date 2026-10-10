import { expect, test, type Page } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { daySlots } from '../src/lib/charts/day-slots';
import { slotCellFor } from '../src/lib/charts/run-history';
import { health, runOutcome, squareLabel, type RunFacts } from '../src/lib/console/run-square';
import { shortDate } from '../src/lib/format';
import { loadManifests } from '../src/lib/server/payload';
import { publishedSite } from './support/published-site';

/**
 * The oracle for `Run health`: its squares are painted at fill weight, they
 * stand on their own day's bars, and one day is picked for both figures.
 *
 * Two defects sat side by side on this section and neither is visible in a
 * diff. The squares were painted with `--band-high`, `--band-medium` and
 * `--band-low`, which are TEXT colours - measured against the surface the strip
 * sits on they run 5.0:1 to 6.1:1 in the light theme, and at 16px solid they
 * read as olive and brick rather than as a state. And the strip was jammed to
 * the right edge, so a run an operator looked at yesterday moved a column left
 * every time a day published.
 *
 * Where the squares sit was answered three times. Left, while the strip drew
 * only the days that carried a run. Centred, once it drew the window's own
 * calendar. And since the squares joined the chart of articles published
 * against planned, under that chart's own days: the chart hands them its slots,
 * so a day's runs stand under that day's bars. Centring survives on a phone,
 * where the squares keep a scrolling strip of their own.
 *
 * The contrast numbers below are computed here, from the WCAG 2.2 relative
 * luminance formula written out in this file. That is deliberate: `CLAUDE.md`
 * section 0a makes accessibility AUDIT TOOLING a project non-goal, so this row
 * adds no dependency and gates nothing but itself. It is one row's own oracle,
 * measuring the thing that row changed.
 */

/** The band a fill has to land in, and where each bound comes from.
 *
 * FLOOR, both themes - WCAG 2.2 SC 1.4.11 (non-text contrast). A graphical
 * object that carries meaning has to reach 3:1 against what it sits on, or the
 * shape itself is not distinguishable from the surface.
 *
 * CEILING, light theme - WCAG 2.2 SC 1.4.3 makes 4.5:1 the MINIMUM for normal
 * text, so a colour at or above it is a text-weight colour. That is exactly the
 * defect this row removes.
 *
 * CEILING, dark theme - a fill on a dark ground is lighter than its ground, so
 * it can never become ink and the light ceiling does not apply. What it can do
 * is get as loud as the page's own type, so the ceiling is a tripwire measured
 * rather than borrowed: the loudest dark fill read 7.943:1 on 2026-08-30, and
 * 9.0 leaves it 13 percent of headroom while failing `--color-text` (14.932:1)
 * and pure white (17.619:1) by a wide margin.
 */
const FILL_FLOOR = 3;
const LIGHT_FILL_CEILING = 4.5;
const DARK_FILL_CEILING = 9;

const DESKTOP = { width: 1440, height: 900 };

/** A phone, where the squares draw their own strip. A strip there keeps its
 * floor and cannot shrink, so a week of days leaves it room to spare whatever
 * the ledger holds - which is what makes the centring premise below a property
 * of the layout, not of today's data. */
const UNDERFULL = { width: 390, height: 844 };

/** Every span the control offers, from the same knob the control reads. */
const WINDOW_PRESETS = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console?: { window_presets?: number[] } }
).console?.window_presets ?? [1, 7, 14, 30, 90];

/** The widest span the control offers. Ninety days of squares are far more than a
 * phone is wide, whatever the record holds, so a rule about a strip wider than
 * the screen is a rule about the layout and not about today's data. */
const WIDEST = Math.max(...WINDOW_PRESETS);

/** Click the label, never the input: a span inside it takes the pointer. */
async function setWindow(page: Page, days: number) {
	await expect(page.locator(`label[data-window-preset="${days}"] input`)).toBeEnabled();
	await page.locator(`label[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}
const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

const CEILING: Record<Theme, number> = {
	light: LIGHT_FILL_CEILING,
	dark: DARK_FILL_CEILING
};

/** WCAG 2.2 relative luminance. Written out rather than imported. */
function luminance([r, g, b]: number[]): number {
	const channel = (value: number) => {
		const s = value / 255;
		return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: number[], b: number[]): number {
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (high + 0.05) / (low + 0.05);
}

/** A colour as the browser hands it back: `rgb(...)`, `#rrggbb` or `#rgb`. */
function rgb(value: string): number[] {
	const parts = /rgba?\(([^)]+)\)/.exec(value);
	if (parts) return parts[1].split(',').slice(0, 3).map((n) => Number(n.trim()));
	const text = value.trim().replace('#', '');
	if (/^[0-9a-f]{6}$/i.test(text)) {
		return [0, 2, 4].map((i) => parseInt(text.slice(i, i + 2), 16));
	}
	if (/^[0-9a-f]{3}$/i.test(text)) {
		return [0, 1, 2].map((i) => parseInt(text[i] + text[i], 16));
	}
	throw new Error(`not a colour: ${JSON.stringify(value)}`);
}

function round(value: number): number {
	return Math.round(value * 1000) / 1000;
}

async function openConsole(page: Page, theme: Theme, viewport = DESKTOP) {
	await page.setViewportSize(viewport);
	await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);
	await page.goto('/console/');
	await expect
		.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
		.toBe(theme);
}

/** Every colour the assertions below need, read off the live document. */
function paints(page: Page) {
	return page.evaluate(() => {
		const style = getComputedStyle(document.documentElement);
		const token = (name: string) => style.getPropertyValue(name).trim();
		const square = document.querySelector('[data-health]');
		const panel = document.querySelector('[data-console-panel="Run health"]');
		return {
			surface: token('--color-surface'),
			fill: {
				high: token('--fill-high'),
				medium: token('--fill-medium'),
				low: token('--fill-low')
			},
			band: {
				high: token('--band-high'),
				medium: token('--band-medium'),
				low: token('--band-low')
			},
			squarePaint: square ? getComputedStyle(square).backgroundColor : null,
			squareHealth: square ? square.getAttribute('data-health') : null,
			panelPaint: panel ? getComputedStyle(panel).backgroundColor : null
		};
	});
}

for (const theme of THEMES) {
	test(`THE ORACLE: every fill is fill weight on the ${theme} panel`, async ({ page }) => {
		await openConsole(page, theme);
		const seen = await paints(page);

		// The surface the squares are drawn on is the panel's, and the panel takes
		// `--color-surface`. Asserting that first is what makes the ratios below
		// answer the question the row asked: before this row the strip sat on the
		// page background with no panel at all.
		expect(seen.panelPaint, 'the run strip is not inside a panel').not.toBeNull();
		expect(
			rgb(seen.panelPaint as string),
			'the panel is not painted --color-surface, so the ratios below measure the wrong ground'
		).toEqual(rgb(seen.surface));

		const measured: Record<string, number> = {};
		for (const [name, value] of Object.entries(seen.fill)) {
			expect(value, `--fill-${name} is not declared in the ${theme} theme`).not.toBe('');
			measured[name] = round(contrast(rgb(value), rgb(seen.surface)));
		}

		for (const [name, ratio] of Object.entries(measured)) {
			expect(
				ratio,
				`--fill-${name} is ${ratio}:1 on ${theme}; under ${FILL_FLOOR}:1 the square is not distinguishable from the surface`
			).toBeGreaterThanOrEqual(FILL_FLOOR);
			expect(
				ratio,
				`--fill-${name} is ${ratio}:1 on ${theme}; at or over ${CEILING[theme]}:1 it is a text-weight colour, not a fill`
			).toBeLessThan(CEILING[theme]);
		}
	});

	test(`the square on the page is painted with the fill ramp, ${theme}`, async ({ page }) => {
		// A token in the band is worth nothing if the markup still reads the other
		// ramp. This is the half that catches that.
		await openConsole(page, theme);
		const seen = await paints(page);

		expect(seen.squareHealth, 'no run square on the page').not.toBeNull();
		const wanted = { green: seen.fill.high, amber: seen.fill.medium, red: seen.fill.low }[
			seen.squareHealth as 'green' | 'amber' | 'red'
		];
		expect(
			rgb(seen.squarePaint as string),
			`a ${seen.squareHealth} square is painted ${seen.squarePaint}, not the fill token ${wanted}`
		).toEqual(rgb(wanted));
	});
}

test('the band ramp is text weight, which is the whole reason the fill ramp exists', async ({
	page
}) => {
	// The negative control. Point --fill-* back at --band-* and the light-theme
	// oracle above fails; this test is what says why, and it fails too if someone
	// "fixes" that by lightening the band tokens, which are read as type on four
	// other surfaces.
	await openConsole(page, 'light');
	const seen = await paints(page);

	for (const [name, value] of Object.entries(seen.band)) {
		const ratio = round(contrast(rgb(value), rgb(seen.surface)));
		expect(
			ratio,
			`--band-${name} is ${ratio}:1, under the ${LIGHT_FILL_CEILING}:1 that makes a colour text weight - it is a text colour and has to stay one`
		).toBeGreaterThanOrEqual(LIGHT_FILL_CEILING);
	}
});

test('THE ORACLE: a phone strip with room to spare is centred in its grid', async ({ page }) => {
	// It started at the left edge until 2026-09-01, and that was right while the
	// strip drew only the days that carried a run: the room on the right really
	// was the days that had not happened yet. The strip draws the window's own
	// calendar now, so its last column IS today and there is nothing to the
	// right of it - spare room there reads as a run that stopped. Wider than a
	// phone the squares stand under the chart's own days instead, which the
	// alignment oracle below holds.
	await openConsole(page, 'light', UNDERFULL);
	// The narrowest preset that draws more than one column. A one-day window is a
	// single square: it has no inside to be centred in, so every assertion below
	// would pass on it while proving nothing about a strip. The count guard is
	// what catches that, and this is what keeps the guard from firing.
	await setWindow(page, Math.min(...WINDOW_PRESETS.filter((days) => days > 1)));
	await expect(page.locator('[data-run-history="strip"]')).toHaveCount(1);

	const geometry = await page.evaluate(() => {
		const box = (node: Element | null) => {
			if (!node) return null;
			const rect = node.getBoundingClientRect();
			return { x: rect.x, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width };
		};
		const days = [...document.querySelectorAll('[data-day]')];
		return {
			strip: box(document.querySelector('[data-run-history]')),
			grid: box(document.querySelector('[data-grid="days"]')),
			first: box(days[0]),
			last: box(days[days.length - 1]),
			count: days.length
		};
	});

	expect(geometry.count, 'the strip drew no day, so alignment asserts nothing').toBeGreaterThan(1);
	const drawn = (geometry.last as { right: number }).right - (geometry.first as { x: number }).x;
	const room = (geometry.strip as { width: number }).width;
	// The premise. On a full strip every alignment is the same picture, so
	// without this the test passes on a strip that proves nothing. The narrowest
	// strip the presets offer, because the default window fills a page-wide frame.
	expect(drawn, `the strip is full at ${UNDERFULL.width}px, so alignment cannot be told apart`).toBeLessThan(room - 2);

	// The grid still starts where the columns do; what moved is the grid.
	expect(
		Math.abs((geometry.first as { x: number }).x - (geometry.grid as { x: number }).x),
		'the oldest day does not start at the left edge of the grid'
	).toBeLessThan(2);

	const before = (geometry.first as { x: number }).x - (geometry.strip as { x: number }).x;
	const after = (geometry.strip as { right: number }).right - (geometry.last as { right: number }).right;
	expect(before, 'there is no room on the oldest side, so nothing was centred').toBeGreaterThan(1);
	expect(after, 'there is no room on the newest side, so nothing was centred').toBeGreaterThan(1);
	expect(
		Math.abs(before - after),
		`the spare room is ${Math.round(before)}px before and ${Math.round(after)}px after`
	).toBeLessThanOrEqual(2);
});

test('on a phone the dates label the strip from below its squares', async ({ page }) => {
	// Only the phone strip has a date row of its own. Wider than that the squares
	// stand under the chart, whose own date row is directly above them.
	await openConsole(page, 'light', UNDERFULL);
	await expect(page.locator('[data-run-history="strip"]')).toHaveCount(1);

	const placed = await page.evaluate(() => {
		const bottom = (selector: string) =>
			Math.max(
				...[...document.querySelectorAll(selector)].map((n) => n.getBoundingClientRect().bottom)
			);
		const labels = [...document.querySelectorAll('[data-axis-label]')];
		return {
			labels: labels.length,
			labelTop: Math.min(...labels.map((n) => n.getBoundingClientRect().top)),
			squareBottom: bottom('[data-health]')
		};
	});

	expect(placed.labels, 'the axis carries no date at all').toBeGreaterThan(0);
	expect(
		placed.labelTop,
		'a date label overlaps the squares, so it reads as a row heading rather than an axis'
	).toBeGreaterThanOrEqual(placed.squareBottom - 1);
});

test("the squares stand 8px under the chart's date row, with nothing between", async ({
	page
}) => {
	await openConsole(page, 'light');
	const panel = page.locator('[data-console-panel="Run health"]');
	await expect(panel.locator('svg[data-run-yield-chart]')).toHaveCount(1);
	await expect(panel.locator('[data-run-history="under-chart"]')).toHaveCount(1);

	const placed = await panel.evaluate((node) => {
		const chart = node.querySelector('svg[data-run-yield-chart]') as Element;
		const squares = node.querySelector('[data-run-history="under-chart"]') as Element;
		const top = chart.getBoundingClientRect().bottom;
		const bottom = squares.getBoundingClientRect().top;
		// Anything drawn in the gap, other than the two figures themselves. A
		// visually hidden list is one pixel square and takes no room.
		const between = [...node.querySelectorAll('*')]
			.filter((el) => !chart.contains(el) && !squares.contains(el) && !el.contains(chart))
			.filter((el) => {
				const box = el.getBoundingClientRect();
				return box.width > 1 && box.height > 1 && box.top >= top - 0.5 && box.bottom <= bottom + 0.5;
			})
			.map((el) => el.outerHTML.slice(0, 80));
		const gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--space-2'));
		const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
		return { space: bottom - top, token: gap * rem, between };
	});

	expect(Math.abs(placed.space - placed.token), `the squares sit ${placed.space}px under the chart`).toBeLessThanOrEqual(1);
	expect(placed.between, 'something is drawn between the chart and its squares').toEqual([]);
});

test('the panel says which window it is drawing, in its own label', async ({ page }) => {
	await openConsole(page, 'light');

	// The section joined the shared window, so it owes the same contract: the
	// attribute AND words a reader is given. It has no note under its title, so
	// the words are its own accessible label, the way `Failure rate against
	// volume` carries its own.
	const section = page.locator('section[data-windowed="run-health"]');
	await expect(section).toHaveCount(1);
	const days = await section.getAttribute('data-window-days');
	expect(Number(days)).toBeGreaterThan(0);
	await expect(section).toHaveAttribute('aria-label', `Run health, over ${days} days`);
});

test('THE ORACLE: a run row says how many of the articles it tried succeeded', async ({
	page
}) => {
	await openConsole(page, 'light');

	// The readout rests on the window's newest day and prints one line for each run
	// the squares draw on that day: the line is the square's own sentence after the
	// run and the day. Both are built from what the run wrote down, read through
	// `loadManifests`, which the next test holds to a manifest it writes.
	const end = (await page.locator('[data-viewport-control]').getAttribute('data-window-end')) ?? '';
	expect(end, 'the viewport prints no window').toMatch(/^\d{4}-\d{2}-\d{2}$/);
	const readout = page.locator('[data-readout="run-health"]');
	await expect(readout.locator('[data-readout-day]')).toHaveText(`${shortDate(end)}, the newest day`);
	const rows = await readout
		.locator('[data-readout-row^="Run "]')
		.evaluateAll((nodes) =>
			nodes.map((node) => [
				node.getAttribute('data-readout-row') ?? '',
				(node.querySelectorAll('dd')[1]?.textContent ?? '').trim()
			])
		);
	const squares = await page
		.locator(`[data-run-history] [data-day="${end}"] [data-health]`)
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label') ?? ''));
	expect(rows.length, 'the newest day drew no run, so no line is checked').toBeGreaterThan(0);
	expect(
		rows.map(([label, value]) => `${label} on ${shortDate(end)}: ${value}`),
		'a run line is not its square sentence'
	).toEqual(squares);

	// Every clause in the order the rule writes them: what it tried, then what went
	// wrong, then what the run itself recorded.
	const clauses = new RegExp(
		[
			'^(nothing new to try|\\d+ of \\d+ succeeded)',
			'(, under \\d+%)?',
			'(, \\d+ failed)?',
			'(, \\d+ skipped)?',
			'(, \\d+ read only in part)?',
			"(, reused yesterday's list of sources)?",
			"(, another run's failed article was still missing)?",
			'(, the run failed)?$'
		].join('')
	);
	for (const [label, value] of rows) {
		expect(value, `${label} does not read as the clauses of its run`).toMatch(clauses);
	}

	// And the words that named a colour rather than a fact are gone from the
	// panel, from what it prints and from what a square says to a pointer or a
	// screen reader. `block` was a run's old name here; elsewhere on the route it
	// is ordinary English - a run that worked in parallel draws a solid block on
	// the run's own clock. The standing band above every route writes its own run
	// words from its own producer, and this panel does not print them.
	const said = await page.evaluate(() =>
		[...document.querySelectorAll('section[data-windowed="run-health"]')]
			.flatMap((root) => [
				(root as HTMLElement).innerText,
				...[root, ...root.querySelectorAll('[aria-label], [title]')].flatMap((node) => [
					node.getAttribute('aria-label') ?? '',
					node.getAttribute('title') ?? ''
				])
			])
			.join('\n')
	);
	expect(said, 'the panel printed nothing to check').not.toBe('');
	for (const word of [
		/ran clean/i,
		/worth a look/i,
		/\bblock\b/i,
		/\bmanifest\b/i,
		/recorded run/i,
		/\bItems\b/
	]) {
		expect(said, `${word} is still in Run health`).not.toMatch(word);
	}
});

test('a run manifest reads into the facts its square and its line are built from', () => {
	// Two published days. 14 Jun 2030 has no manifest, and reads as no row rather
	// than a day of zeros. 15 Jun 2030 ran twice: run 1 completed, tried 8 articles
	// of the 9 it planned, published 6, failed 2 and skipped 1, on two shards, with
	// the planner timed; run 2 reused yesterday's list of sources and failed on all
	// 3 it planned. The day's site size is the last run's, never a sum.
	const { digest } = publishedSite(test.info().outputPath('site'), {
		published: ['2030-06-14', '2030-06-15']
	});
	const model = { model_ref: { id: 'model-a' } };
	writeFileSync(
		join(digest, '2030', '06', '15', 'run.json'),
		JSON.stringify({
			date: '2030-06-15',
			runs: [
				{
					run_id: '2030-06-15-1',
					n: 1,
					status: 'completed',
					started_at: '2030-06-15T06:00:00Z',
					items_planned: 9,
					items_succeeded: 6,
					items_failed: 2,
					items_skipped: 1,
					source_list_stale: false,
					shards: 2,
					items_routed: 5,
					items_prefiltered: 3,
					charts_drafted: 2,
					chart_evidence: {
						displayed_values: 7,
						derived_values: 1,
						trusted_values: 7,
						derived_value_rate: 1 / 7,
						trusted_data_ratio: 1
					},
					route_ms: 90_000,
					inputs: { summarizer: 'model-a' },
					models: [model],
					site_bytes: 2_400_000,
					site_files: 39
				},
				{
					run_id: '2030-06-15-2',
					n: 2,
					status: 'failed',
					started_at: '2030-06-15T12:00:00Z',
					items_planned: 3,
					items_succeeded: 0,
					items_failed: 3,
					items_skipped: 0,
					source_list_stale: true,
					route_ms: null,
					models: [model],
					site_bytes: 2_500_000,
					site_files: 40
				}
			]
		})
	);

	const days = loadManifests(digest, 2);
	expect(days.map((day) => day.date)).toEqual(['2030-06-15']);
	const [day] = days;
	expect(day).toMatchObject({
		runs: 2,
		planned: 12,
		failed: 5,
		siteBytes: 2_500_000,
		siteFiles: 40,
		models: ['model-a']
	});
	expect(day.records).toEqual([
		{
			runId: '2030-06-15-1',
			n: 1,
			status: 'completed',
			planned: 9,
			succeeded: 6,
			failed: 2,
			skipped: 1,
			startedAt: '2030-06-15T06:00:00Z',
			sourceListStale: false,
			shards: 2,
			decided: 5,
			prefiltered: 3,
			chartsDrafted: 2,
			chartEvidence: {
				displayed_values: 7,
				derived_values: 1,
				trusted_values: 7,
				derived_value_rate: 1 / 7,
				trusted_data_ratio: 1
			},
			decisionMs: 90_000,
			inputs: { summarizer: 'model-a' }
		},
		{
			runId: '2030-06-15-2',
			n: 2,
			status: 'failed',
			planned: 3,
			succeeded: 0,
			failed: 3,
			skipped: 0,
			startedAt: '2030-06-15T12:00:00Z',
			sourceListStale: true,
			shards: null,
			decided: 0,
			prefiltered: 0,
			chartsDrafted: 0,
			chartEvidence: null,
			// Nothing timed the planner, and the manifest says so with a null: a zero
			// here would be a measurement nobody took.
			decisionMs: null,
			inputs: null
		}
	]);

	// What each square says, and the line beside it, at a floor of 70 percent.
	expect(day.records.map((run) => squareLabel(day.date, run, 70, 0))).toEqual([
		'Run 1 on 15 Jun 2030: 6 of 8 succeeded, 2 failed, 1 skipped',
		"Run 2 on 15 Jun 2030: 0 of 3 succeeded, under 70%, 3 failed, reused yesterday's list of sources, the run failed"
	]);
});

test('a square carries the whole run in one sentence', () => {
	// The square's accessible name and the readout line are built from one set
	// of facts, and the line carries every clause the name does - the strip is
	// where a keyboard and a thumb read a run, so it may not be the shorter of
	// the two. They are checked together here, and against the colour the same
	// facts give.
	const floor = 70;
	const run = (facts: Partial<RunFacts>): RunFacts => ({
		n: 1,
		status: 'completed',
		succeeded: 0,
		failed: 0,
		skipped: 0,
		sourceListStale: false,
		...facts
	});

	const clean = run({ succeeded: 8 });
	expect(squareLabel('2026-08-20', clean, floor, 0)).toBe('Run 1 on 20 Aug 2026: 8 of 8 succeeded');
	expect(runOutcome(clean, floor, 0)).toBe('8 of 8 succeeded');
	expect(health(clean, floor)).toBe('green');

	// Nothing tried: a run that skipped everything it planned.
	const idle = run({ n: 2, skipped: 4 });
	expect(squareLabel('2026-08-20', idle, floor, 0)).toBe(
		'Run 2 on 20 Aug 2026: nothing new to try, 4 skipped'
	);
	expect(runOutcome(idle, floor, 0)).toBe('nothing new to try, 4 skipped');
	expect(health(idle, floor)).toBe('amber');

	// A crash that took every article with it, in the order the clauses are read.
	const broke = run({ n: 3, failed: 5, status: 'failed' });
	expect(squareLabel('2026-08-20', broke, floor, 0)).toBe(
		'Run 3 on 20 Aug 2026: 0 of 5 succeeded, under 70%, 5 failed, the run failed'
	);
	expect(runOutcome(broke, floor, 0)).toBe('0 of 5 succeeded, under 70%, 5 failed, the run failed');
	expect(health(broke, floor)).toBe('red');

	// Under the floor without crashing, and cut short, and on yesterday's sources.
	const thin = run({ n: 4, succeeded: 6, failed: 4, sourceListStale: true });
	expect(squareLabel('2026-08-20', thin, floor, 2)).toBe(
		"Run 4 on 20 Aug 2026: 6 of 10 succeeded, under 70%, 4 failed, 2 read only in part, reused yesterday's list of sources"
	);
	expect(runOutcome(thin, floor, 2)).toBe(
		"6 of 10 succeeded, under 70%, 4 failed, 2 read only in part, reused yesterday's list of sources"
	);
	expect(health(thin, floor)).toBe('red');

	// Held open by another run's failure: partial while failing nothing itself.
	const held = run({ n: 5, succeeded: 3, status: 'partial' });
	expect(squareLabel('2026-08-20', held, floor, 0)).toBe(
		"Run 5 on 20 Aug 2026: 3 of 3 succeeded, another run's failed article was still missing"
	);
	expect(runOutcome(held, floor, 0)).toBe(
		"3 of 3 succeeded, another run's failed article was still missing"
	);
	expect(health(held, floor)).toBe('amber');

	// A partial run that failed something itself says so by its count, not twice.
	const partial = run({ n: 6, succeeded: 9, failed: 1, status: 'partial' });
	expect(runOutcome(partial, floor, 0)).toBe('9 of 10 succeeded, 1 failed');
	expect(squareLabel('2026-08-20', partial, floor, 0)).toBe(
		'Run 6 on 20 Aug 2026: 9 of 10 succeeded, 1 failed'
	);
});

test('the chart and the squares share one slot a day, and a square fits inside it', () => {
	// The same arithmetic the bars are placed by: one equal slot a day between the
	// two margins, each day at its slot's middle.
	const slots = daySlots(1000, 4, { left: 40, right: 60 });
	expect(slots.slot).toBe(225);
	expect(slots.centres).toEqual([152.5, 377.5, 602.5, 827.5]);
	// A frame narrower than its own margins does not flip inside out.
	expect(daySlots(50, 3, { left: 40, right: 60 }).slot).toBe(0);

	// Eighty percent of the slot, held between the two limits a dense strip uses.
	expect(slotCellFor(10)).toEqual({ cell: 8, gap: 2 });
	expect(slotCellFor(40)).toEqual({ cell: 14, gap: 4 });
	expect(slotCellFor(4)).toEqual({ cell: 3, gap: 1 });
	// Under three pixels there is no square to draw here, and the caller draws the
	// scrolling strip instead.
	expect(slotCellFor(3.7)).toBeNull();
	expect(slotCellFor(0)).toBeNull();
});

/** The widths and windows the squares are held to their bars at, in one pass.
 *
 * Three page widths because the day's share of the plot is what sizes a square,
 * and two windows because ninety days is where that share is smallest. */
const ALIGNED_WIDTHS = [1440, 1024, 768] as const;
const ALIGNED_WINDOWS = [30, 90] as const;

/** The largest a run square may be drawn under the bars. It is the dense
 * strip's own ceiling: a square larger than the bar beside it reads as the more
 * important of the two, and it is not. */
const SQUARE_MAX_PX = 14;

/** The chart and the squares have settled at this width and this window.
 *
 * Two readings a frame apart, with the viewport part of the reading, so a pair
 * taken before the resize reached the renderer cannot settle it. The chart
 * draws at the width it measured, so its drawn width meeting its frame's width
 * is the sign the measurement has landed. */
async function settled(page: Page, width: number, days: number) {
	await expect(page.locator(`[data-run-yield-days="${days}"]`)).toHaveCount(1);
	await expect
		.poll(() =>
			page.evaluate(
				(asked) =>
					new Promise<boolean>((wake) => {
						const read = () => {
							const svg = document.querySelector('svg[data-run-yield-chart]');
							const host = svg?.parentElement;
							if (!svg || !host) return '';
							return `${svg.getAttribute('width')}:${host.getBoundingClientRect().width}`;
						};
						const before = read();
						requestAnimationFrame(() =>
							requestAnimationFrame(() => {
								const [drawn, room] = read().split(':').map(Number);
								wake(
									window.innerWidth === asked &&
										read() === before &&
										Math.abs(drawn - room) < 1
								);
							})
						);
					}),
				width
			)
		)
		.toBe(true);
}

/** Every square, and the centre of its own day on the chart, read off the drawing.
 *
 * A day that draws bars has its centre in the middle of its group of three: the
 * planned bar is the first of three equal bars, so the middle is one and a half
 * bar widths in from its left edge. A day that draws no bar still carries a tick
 * mark where it would stand, when the axis marks it. A day with neither has no
 * centre on the chart to hold its square to, and is not counted. */
function readAlignment() {
	const svg = document.querySelector('svg[data-run-yield-chart]') as SVGSVGElement | null;
	if (!svg) return null;
	const frame = svg.getBoundingClientRect();
	const scale = frame.width / svg.viewBox.baseVal.width;
	const centre = new Map<string, number>();
	const barArea = new Map<string, number>();
	for (const bar of svg.querySelectorAll('rect[data-run-bar]')) {
		const date = bar.getAttribute('data-run-bar-day') ?? '';
		const box = bar.getBoundingClientRect();
		barArea.set(date, (barArea.get(date) ?? 0) + box.width * box.height);
		if (bar.getAttribute('data-run-bar') === 'planned') centre.set(date, box.left + 1.5 * box.width);
	}
	for (const tick of svg.querySelectorAll('line[data-day-tick]')) {
		const date = tick.getAttribute('data-day-tick') ?? '';
		if (!centre.has(date)) {
			centre.set(date, frame.left + (tick as SVGLineElement).x1.baseVal.value * scale);
		}
	}
	const squares = [...document.querySelectorAll('[data-run-history] [data-day] [data-health]')].map(
		(square) => {
			const box = square.getBoundingClientRect();
			return {
				date: square.closest('[data-day]')?.getAttribute('data-day') ?? '',
				at: box.left + box.width / 2,
				width: box.width,
				area: box.width * box.height
			};
		}
	);
	return { squares, centre: [...centre], barArea: [...barArea] };
}

test("THE ORACLE: every square stands on its own day's bars, and never outweighs them", async ({
	page
}) => {
	// The two figures were drawn from two geometries: the bars at one pitch from
	// the chart's plot edge, the squares at another from the strip's own centred
	// start. Measured on the real ledger they sat about 41 and 43 px a day apart,
	// so reading down from a bar landed on the previous day's squares.
	for (const days of ALIGNED_WINDOWS) {
		expect(WINDOW_PRESETS, `the control offers no ${days}-day window`).toContain(days);
	}
	const failures: string[] = [];
	for (const width of ALIGNED_WIDTHS) {
		await page.setViewportSize({ width, height: 1000 });
		if (width === ALIGNED_WIDTHS[0]) await page.goto('/console/');
		for (const days of ALIGNED_WINDOWS) {
			await setWindow(page, days);
			await settled(page, width, days);
			const seen = await page.evaluate(readAlignment);
			if (seen === null) {
				failures.push(`${width}px, ${days} days: no chart is drawn`);
				continue;
			}
			const centres = new Map(seen.centre);
			let held = 0;
			for (const square of seen.squares) {
				if (square.width > SQUARE_MAX_PX + 0.01) {
					failures.push(
						`${width}px, ${days} days: a square on ${square.date} is ${square.width.toFixed(1)}px wide`
					);
				}
				const at = centres.get(square.date);
				if (at === undefined) continue;
				held += 1;
				const off = Math.abs(square.at - at);
				if (off > 1) {
					failures.push(
						`${width}px, ${days} days: a square on ${square.date} sits ${off.toFixed(1)}px off its day's centre`
					);
				}
			}
			if (held < 2) {
				failures.push(
					`${width}px, ${days} days: ${held} squares stand on a day the chart marks, so alignment is untested`
				);
			}
			// Only a day that draws bars can be compared. A day that planned nothing
			// draws a square and no bar, and a square cannot paint less than nothing.
			for (const [date, area] of seen.barArea) {
				const painted = seen.squares
					.filter((square) => square.date === date)
					.reduce((sum, square) => sum + square.area, 0);
				if (painted >= area) {
					failures.push(
						`${width}px, ${days} days: the squares on ${date} paint ${Math.round(painted)} px2 against its bars' ${Math.round(area)} px2`
					);
				}
			}
		}
	}
	expect(failures, failures.join('\n')).toEqual([]);
});

/** Where each day the chart's axis marks sits, in page pixels, oldest first. */
function tickPositions(node: Element) {
	const svg = node as SVGSVGElement;
	const frame = svg.getBoundingClientRect();
	const scale = frame.width / svg.viewBox.baseVal.width;
	return [...svg.querySelectorAll('line[data-day-tick]')].map((line) => ({
		date: line.getAttribute('data-day-tick') ?? '',
		x: frame.left + (line as SVGLineElement).x1.baseVal.value * scale
	}));
}

test('THE ORACLE: one day is picked, and both figures show it', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto('/console/');
	await expect(page.locator('label[data-window-preset] input').first()).toBeEnabled();

	const plot = page.locator('svg[data-run-yield-chart]');
	const day = page.locator('[data-readout="run-health"] [data-readout-day]');
	const guide = plot.locator('line[data-run-yield-chart="guide"]');
	await plot.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));

	// Two days the axis marks, so where they sit is read off the drawing. Neither
	// is the newest, which is where the readout rests, so a pick is visible.
	const ticks = await plot.evaluate(tickPositions);
	expect(ticks.length, 'the chart marks fewer than three days').toBeGreaterThan(2);
	const onChart = ticks[ticks.length - 2];
	const onSquares = ticks[ticks.length - 3];

	// Pointing at the chart picks the day on the readout and on the squares.
	const box = await plot.boundingBox();
	expect(box, 'the chart has no box').not.toBeNull();
	await page.mouse.move(onChart.x, (box?.y ?? 0) + (box?.height ?? 0) / 2);
	await expect(day, 'the readout did not follow the chart').toHaveText(shortDate(onChart.date));
	await expect(page.locator(`[data-day="${onChart.date}"][data-day-selected]`)).toHaveCount(1);

	// Pointing at the squares picks the day on the chart: its guide moves there.
	const column = page.locator(`[data-run-history] [data-day="${onSquares.date}"]`);
	const target = await column.boundingBox();
	expect(target, `the squares draw no column for ${onSquares.date}`).not.toBeNull();
	await page.mouse.move(
		(target?.x ?? 0) + (target?.width ?? 0) / 2,
		(target?.y ?? 0) + (target?.height ?? 0) / 2
	);
	await expect(day, 'the readout did not follow the squares').toHaveText(shortDate(onSquares.date));
	await expect(guide, 'the chart drew no guide for a day picked on the squares').toHaveCount(1);
	const guideX = await guide.evaluate((line) => {
		const svg = (line as SVGLineElement).ownerSVGElement as SVGSVGElement;
		const frame = svg.getBoundingClientRect();
		return (
			frame.left + (line as SVGLineElement).x1.baseVal.value * (frame.width / svg.viewBox.baseVal.width)
		);
	});
	expect(Math.abs(guideX - onSquares.x), "the guide is not on the squares' day").toBeLessThanOrEqual(1);

	// Escape on either figure returns both to the newest day.
	await page.mouse.move(0, 0);
	for (const figure of [plot, page.locator('[data-console-panel="Run health"] [data-grid="days"]')]) {
		await figure.focus();
		await page.keyboard.press('ArrowRight');
		await expect(guide).toHaveCount(1);
		await expect(page.locator('[data-day][data-day-selected]')).toHaveCount(1);
		await page.keyboard.press('Escape');
		await expect(day).toContainText('the newest day');
		await expect(guide).toHaveCount(0);
		await expect(page.locator('[data-day][data-day-selected]')).toHaveCount(0);
	}
});

test('on a phone a tap or a step on the chart brings its day into view, and a hover never moves the squares', async ({
	page
}) => {
	await page.setViewportSize({ width: 390, height: 844 });
	// More days than a phone is wide - the default fourteen fit one - so the page
	// opens on the widest span, the way a reader's stored choice reopens it.
	const wide = WIDEST;
	await page.addInitScript(
		(stored) => localStorage.setItem('idhazh:console-window', String(stored)),
		wide
	);
	await page.goto('/console/');
	await expect(page.locator('label[data-window-preset] input').first()).toBeEnabled();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(wide)
	);

	const strip = page.locator('[data-run-history]');
	const scroll = () => strip.evaluate((node) => node.scrollLeft);
	// More days than a phone is wide, opened on the newest.
	await expect
		.poll(() =>
			strip.evaluate(
				(node) =>
					node.scrollWidth > node.clientWidth &&
					Math.abs(node.scrollWidth - node.clientWidth - node.scrollLeft) < 1
			)
		)
		.toBe(true);
	const dates = await strip
		.locator('[data-day]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-day') ?? ''));
	/** How far a day's column sits inside the strip's visible edges. */
	const inside = (date: string) =>
		page.evaluate((wanted) => {
			const room = document.querySelector('[data-run-history]')?.getBoundingClientRect();
			const column = document
				.querySelector(`[data-run-history] [data-day="${wanted}"]`)
				?.getBoundingClientRect();
			if (!room || !column) return null;
			return { left: column.left - room.left, right: room.right - column.right };
		}, date);

	const plot = page.locator('svg[data-run-yield-chart]');
	await plot.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
	const opened = await scroll();
	const box = await plot.boundingBox();
	expect(box, 'the chart has no box').not.toBeNull();
	const left = (box?.x ?? 0) + 4;
	const middle = (box?.y ?? 0) + (box?.height ?? 0) / 2;

	// A hover, and then the start of a touch, pick the oldest day and move nothing.
	// Without this a page scroll that starts on the chart drags the squares with it.
	await page.mouse.move(left, middle);
	await page.waitForTimeout(150);
	expect(await scroll(), 'a hover on the chart scrolled the squares').toBe(opened);
	await page.mouse.down();
	await page.waitForTimeout(150);
	expect(await scroll(), 'the start of a press scrolled the squares').toBe(opened);

	// Lifted in place it was a tap, and a tap brings that day in.
	await page.mouse.up();
	await expect
		.poll(async () => (await inside(dates[0]))?.left ?? -99, 'a tap did not bring its day into view')
		.toBeGreaterThanOrEqual(-1);

	// A step key brings its day in too, and only as far as it has to: back to the
	// newest, then one step past the days already in view.
	await plot.focus();
	await page.keyboard.press('End');
	await expect.poll(async () => (await inside(dates[dates.length - 1]))?.right ?? -99).toBeGreaterThanOrEqual(-1);
	const shown = await strip.locator('[data-day]').evaluateAll((nodes) => {
		const room = document.querySelector('[data-run-history]')?.getBoundingClientRect();
		return nodes.filter((node) => {
			const box = node.getBoundingClientRect();
			return room !== undefined && box.left >= room.left - 1 && box.right <= room.right + 1;
		}).length;
	});
	expect(shown, 'every day already fits, so a step cannot show anything').toBeLessThan(dates.length);
	for (let step = 0; step < shown; step += 1) await page.keyboard.press('ArrowLeft');
	const stepped = dates[dates.length - 1 - shown];
	await expect
		.poll(async () => Math.abs((await inside(stepped))?.left ?? 99), `the step did not bring ${stepped} to the edge`)
		.toBeLessThanOrEqual(1);
	expect(await scroll(), 'the step scrolled all the way back instead of one day').toBeGreaterThan(0);
});
