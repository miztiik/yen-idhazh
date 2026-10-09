import { expect, test } from './support/browser';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { failureLoad } from '../src/lib/charts/glance';
import { failureSeries, type TelemetryRow } from '../src/lib/charts/series';
import { dayBefore, items, openServed } from './support/served-telemetry';
import { telemetryRow } from './support/telemetry-row';

/**
 * A failure rate, and the volume it was measured on, in one picture.
 *
 * The row this file holds: three stage panels became one chart, because a rate
 * on its own cannot be acted on. A stage that failed both of the two items it
 * was given drew the same full bar as an outage, and the number that tells them
 * apart - the denominator - was the one number the panel did not print.
 *
 * The oracle is that every printed rate carries its denominator in the same
 * sentence, and that a stage under `console.min_attempts_for_rate` prints an
 * explicit low-sample state instead of a rate. A bare percentage fails the row.
 *
 * The rules are driven as pure functions over rows written here, and the page is
 * driven in the browser over telemetry the test serves it: rows built for the
 * window the page opened on, so every count below is written out rather than
 * worked out from what the canary happens to hold.
 */

/** The knob, read from the file the page reads it from. */
const MIN_ATTEMPTS_FOR_RATE = (
	JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')) as {
		console?: { min_attempts_for_rate?: number };
	}
).console?.min_attempts_for_rate ?? 5;

const STAGES = ['fetch', 'extract', 'summarize'] as const;

function row(date: string, id: string, stage: string, outcome: string, code = ''): TelemetryRow {
	return telemetryRow({
		date,
		run_id: `${date}-1`,
		item_id: id,
		source_id: 'fixture',
		stage,
		outcome,
		code,
		source_words: 400,
		summary_words: 60
	});
}

/** Playwright's `toContainText` with a regex reads raw text, so a sentence that
 * wrapped across two lines never matches. Every assertion below reads
 * `innerText` and collapses the whitespace itself. */
function flat(text: string): string {
	return text.replace(/\s+/g, ' ').trim();
}

test('a stage is measured against what reached it, never against the day', () => {
	// One day, ten items. Four die at fetch, so only six ever reach extract and
	// only four ever reach summarize. Dividing by the day instead understates
	// every stage after the first, which is what the page did until this row:
	// measured 2026-08-30 over the 4,273 rows of the committed projection,
	// extract read 10.2 percent against the day and 12.1 percent against the
	// 3,601 items that got as far as extract.
	const rows = [
		...Array.from({ length: 4 }, (_, i) => row('2026-08-20', `f${i}`, 'fetch', 'failed', 'no_text')),
		...Array.from({ length: 2 }, (_, i) =>
			row('2026-08-20', `e${i}`, 'extract', 'failed', 'too_short')
		),
		row('2026-08-20', 's0', 'summarize', 'failed', 'bad_shape'),
		...Array.from({ length: 3 }, (_, i) => row('2026-08-20', `p${i}`, 'publish', 'ok'))
	];
	const series = failureSeries(rows, { start: '2026-08-20', end: '2026-08-20' });
	const day = (stage: string) => series.find((s) => s.stage === stage)?.days[0];

	expect(day('fetch')).toMatchObject({ planned: 10, reached: 10, failures: 4, rate: 0.4 });
	expect(day('extract')).toMatchObject({ planned: 10, reached: 6, failures: 2 });
	expect(day('extract')?.rate).toBeCloseTo(2 / 6, 10);
	expect(day('summarize')).toMatchObject({ planned: 10, reached: 4, failures: 1, rate: 0.25 });

	// An item the planner listed and never fetched is in the day and in no
	// stage's denominator. It cannot fail a stage it never entered.
	const withSkipped = failureSeries([...rows, row('2026-08-20', 'x0', 'plan', 'failed')], {
		start: '2026-08-20',
		end: '2026-08-20'
	});
	expect(withSkipped[0].days[0]).toMatchObject({ planned: 11, reached: 10, failures: 4 });
});

test('a rate is given where the denominator holds and withheld where it does not', () => {
	// Both directions off one fixture, so this cannot pass on an implementation
	// that always returns null. Fetch is measured on ten items and summarize on
	// four, which is under the knob.
	const rows = [
		...Array.from({ length: 6 }, (_, i) => row('2026-08-20', `f${i}`, 'fetch', 'failed', 'no_text')),
		row('2026-08-20', 's0', 'summarize', 'failed', 'bad_shape'),
		...Array.from({ length: 3 }, (_, i) => row('2026-08-20', `p${i}`, 'publish', 'ok'))
	];
	const load = failureLoad(
		failureSeries(rows, { start: '2026-08-20', end: '2026-08-20' }),
		MIN_ATTEMPTS_FOR_RATE
	);
	const stage = (name: string) => load.stages.find((s) => s.stage === name);

	expect(MIN_ATTEMPTS_FOR_RATE, 'the fixture is built around a knob of 5').toBe(5);
	expect(stage('fetch')).toMatchObject({ reached: 10, failures: 6, rate: 0.6, lowSample: false });
	// Four items reached summarize. One failed. 25 percent is arithmetic, not a
	// measurement, so no rate is given and the state says why.
	expect(stage('summarize')).toMatchObject({ reached: 4, failures: 1, rate: null, lowSample: true });
	// And a stage nothing reached is a third state again: unknown, not thin.
	const nothing = failureLoad(
		failureSeries([], { start: '2026-08-20', end: '2026-08-20' }),
		MIN_ATTEMPTS_FOR_RATE
	);
	expect(nothing.stages[0]).toMatchObject({ reached: 0, rate: null, lowSample: false });
	expect(nothing.empty).toBe(true);
});

test('the column is the day, and no band in it is a residue', () => {
	const rows = [
		row('2026-08-20', 'x0', 'plan', 'failed', 'not_attempted'),
		...Array.from({ length: 4 }, (_, i) => row('2026-08-20', `f${i}`, 'fetch', 'failed', 'no_text')),
		row('2026-08-20', 'e0', 'extract', 'failed', 'too_short'),
		row('2026-08-20', 's0', 'summarize', 'failed', 'bad_shape'),
		...Array.from({ length: 3 }, (_, i) => row('2026-08-20', `p${i}`, 'publish', 'ok'))
	];
	const load = failureLoad(
		failureSeries(rows, { start: '2026-08-20', end: '2026-08-20' }),
		MIN_ATTEMPTS_FOR_RATE
	);
	const column = load.columns[0];

	expect(column.planned).toBe(10);
	// A stack whose bands do not add up to the number above it is a chart whose
	// height means nothing.
	expect(column.bands.reduce((sum, band) => sum + band.value, 0)).toBe(column.planned);
	expect(column.bands.map((band) => `${band.key}:${band.value}`)).toEqual([
		'finished:3',
		'fetch:4',
		'extract:1',
		'summarize:1',
		'skipped:1'
	]);
	expect(load.peak).toBe(10);
});

test('a day too thin to divide breaks the line rather than drawing a share', () => {
	const rows = [
		// A day of one item. A rate over one item is 0 or 100 and neither is news.
		row('2026-08-19', 'a0', 'publish', 'ok'),
		...Array.from({ length: 8 }, (_, i) => row('2026-08-20', `b${i}`, 'publish', 'ok')),
		row('2026-08-20', 'b8', 'fetch', 'failed', 'no_text')
	];
	const load = failureLoad(
		failureSeries(rows, { start: '2026-08-19', end: '2026-08-20' }),
		MIN_ATTEMPTS_FOR_RATE
	);
	const fetch = load.stages[0];

	expect(fetch.points.map((point) => point.date)).toEqual(['2026-08-19', '2026-08-20']);
	expect(fetch.points[0]).toMatchObject({ rate: null, reached: 1 });
	expect(fetch.points[1]).toMatchObject({ rate: 1 / 9, reached: 9 });
});

test('drawn rate lines stop at gaps, keep measured zero and leave singleton dots unjoined', async ({ page }) => {
	await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '7'));
	await openServed(page, (window) => [6, 5, 3, 2, 0].flatMap((ago) =>
		items(dayBefore(window.end, ago), `day-${ago}`, 'publish', 'ok', 8)
	));
	for (const stage of STAGES) {
		const marks = await page.locator(`[data-rate-mark="${stage}"]`).evaluateAll((nodes) =>
			nodes.map((node) => `${node.getAttribute('cx')},${node.getAttribute('cy')}`)
		);
		expect(marks).toHaveLength(5);
		const lines = await page.locator(`[data-rate-line="${stage}"]`).evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('points'))
		);
		expect(lines).toEqual([marks.slice(0, 2).join(' '), marks.slice(2, 4).join(' ')]);
		expect(new Set(marks.map((point) => point.split(',')[1])).size).toBe(1);
	}
});

test('every rate the chart prints carries its denominator in the same sentence', async ({
	page
}) => {
	await page.goto('/console/');

	const section = page.locator('[data-failure-panels]');
	await expect(section, 'the failure surface is gone, so nothing below is tested').toBeVisible();
	await expect(
		page.locator('[data-failure-readout] [data-failure-stage]'),
		'one readout per stage - fetch, extract and summarize'
	).toHaveCount(STAGES.length);

	for (const stage of STAGES) {
		const line = page.locator(`[data-panel-rate="${stage}"]`);
		await expect(line, `${stage} prints nothing at all`).toBeVisible();
		const says = flat(await line.innerText());

		// Three permitted sentences, and a bare percentage is none of them.
		const rate = /^(\d+%|<1%) failed, [\d,]+ of the [\d,]+ that reached it\.$/;
		const thin = /^[\d,]+ failed of the [\d,]+ that reached it\. Too few to give a rate - \d+ needed\.$/;
		const none = /^Nothing reached this stage in these \d+ days\.$/;
		expect(rate.test(says) || thin.test(says) || none.test(says), `${stage} says "${says}"`).toBe(
			true
		);
		// The whole row in one line: a percent may never appear without a
		// denominator behind it.
		if (says.includes('%')) {
			expect(rate.test(says), `${stage} printed a percent with no denominator`).toBe(true);
		}
	}
});

test('the printed denominators are the ones the ledger holds', async ({ page }) => {
	// The window's newest day: one item listed and never fetched, four that failed at
	// fetch, two at extract, one at summarize and six published. Three days earlier:
	// five published and one that failed at fetch. Down the pipeline, each stage is
	// reached by what the stage before it let through: fetch by 19 items, 5 failing,
	// extract by 14, 2 failing, summarize by 12, 1 failing. The item never fetched is
	// in no stage's count.
	await openServed(page, (window) => [
		...items(window.end, 'listed', 'plan', 'failed', 1),
		...items(window.end, 'fetch', 'fetch', 'failed', 4),
		...items(window.end, 'extract', 'extract', 'failed', 2),
		...items(window.end, 'summarize', 'summarize', 'failed', 1),
		...items(window.end, 'done', 'publish', 'ok', 6),
		...items(dayBefore(window.end, 3), 'older', 'publish', 'ok', 5),
		...items(dayBefore(window.end, 3), 'older-fetch', 'fetch', 'failed', 1)
	]);

	const expected = [
		{ stage: 'fetch', reached: 19, failed: 5 },
		{ stage: 'extract', reached: 14, failed: 2 },
		{ stage: 'summarize', reached: 12, failed: 1 }
	];
	for (const { stage, reached, failed } of expected) {
		const cell = page.locator(`[data-failure-readout] [data-failure-stage="${stage}"]`);
		await expect(cell).toHaveAttribute('data-stage-reached', String(reached));
		await expect(cell).toHaveAttribute('data-stage-failed', String(failed));
		await expect(cell).toHaveAttribute('data-stage-low-sample', 'false');
		// The number in the attribute is the number in the sentence.
		expect(flat(await page.locator(`[data-panel-rate="${stage}"]`).innerText())).toContain(
			`${failed} of the ${reached} that reached it`
		);
	}
});

test('a day under the threshold gets no mark, and a day over it gets one', async ({ page }) => {
	// Four days, each with only published items, so every stage is reached by the
	// same number: the knob itself and two over it draw a mark, one under it and a
	// single item do not. Positive evidence and negative evidence together - a count
	// of zero marks would pass an absence test on a chart that draws nothing at all.
	await openServed(page, (window) => [
		...items(window.end, 'at-the-knob', 'publish', 'ok', MIN_ATTEMPTS_FOR_RATE),
		...items(dayBefore(window.end, 1), 'one-under', 'publish', 'ok', MIN_ATTEMPTS_FOR_RATE - 1),
		...items(dayBefore(window.end, 2), 'two-over', 'publish', 'ok', MIN_ATTEMPTS_FOR_RATE + 2),
		...items(dayBefore(window.end, 3), 'alone', 'publish', 'ok', 1)
	]);

	await expect(page.locator('[data-rate-mark="fetch"]')).toHaveCount(2);
	await expect(page.locator('[data-rate-mark="summarize"]')).toHaveCount(2);
});

test('a window too thin to divide states that, and never a rate', async ({ page }) => {
	// Two items fewer than the knob asks for, both on the window's newest day, so
	// every stage is reached by too few items to give a rate.
	const thin = MIN_ATTEMPTS_FOR_RATE - 2;
	await openServed(page, (window) => items(window.end, 'thin', 'publish', 'ok', thin));

	for (const stage of STAGES) {
		const cell = page.locator(`[data-failure-readout] [data-failure-stage="${stage}"]`);
		await expect(cell).toHaveAttribute('data-stage-reached', String(thin));
		await expect(cell).toHaveAttribute('data-stage-low-sample', 'true');
		const says = flat(await page.locator(`[data-panel-rate="${stage}"]`).innerText());
		expect(says, `${stage} gave a rate on ${thin} items`).not.toContain('%');
		expect(says).toContain(`the ${thin} that reached it`);
	}
	await expect(page.locator('[data-failure-low-sample]')).toBeVisible();
});

test('a held month file says the chart is waiting, not empty', async ({ page }) => {
	let release!: () => void;
	const held = new Promise<void>((resolve) => (release = resolve));
	let requested = 0;
	await page.route('**/telemetry/*.csv', async (route) => {
		requested += 1;
		await held;
		await route.fulfill({ status: 404, contentType: 'text/plain', body: '' });
	});

	try {
		await page.goto('/console/');
		await expect.poll(() => requested, 'the page did not request a month file').toBeGreaterThan(0);
		await expect(page.locator('[data-failure-loading]')).toHaveText(
			'Reading the monthly files. This chart is not ready yet.'
		);
		await expect(page.locator('[data-failure-empty]')).toHaveCount(0);
		await expect(page.locator('[data-failure-chart]')).toHaveCount(0);
	} finally {
		release();
	}
});

test('a month file that returns 404 says the chart is unavailable, not empty', async ({ page }) => {
	let requested = 0;
	await page.route('**/telemetry/*.csv', async (route) => {
		requested += 1;
		await route.fulfill({ status: 404, contentType: 'text/plain', body: '' });
	});

	await page.goto('/console/');
	await expect.poll(() => requested, 'the page did not request a month file').toBeGreaterThan(0);
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute(
		'data-telemetry-fetching',
		'no'
	);
	await expect(page.locator('[data-failure-unavailable]')).toHaveText('This chart is unavailable.');
	await expect(page.locator('[data-failure-empty]')).toHaveCount(0);
	await expect(page.locator('[data-failure-chart]')).toHaveCount(0);
});

test('a window holding nothing renders, and says so rather than drawing zero', async ({ page }) => {
	// Six items on the window's newest day and none before it. Narrowed to seven days
	// the window draws them; one step back it holds nothing, which is the state.
	await openServed(page, (window) => items(window.end, 'newest', 'publish', 'ok', 6));
	await page.locator('[data-window-preset="7"]').click();
	await expect(page.locator('[data-failure-chart]'), 'the newest seven days drew no chart').toHaveCount(1);

	await page.getByRole('button', { name: 'Back' }).click();
	await expect(page.locator('[data-viewport-control]')).toContainText('0 rows in view');

	// A column of zeroes reads as a run that went badly. An empty window went
	// nowhere at all, and the page has to say which.
	await expect(page.locator('[data-failure-empty]')).toHaveText(
		'No item was planned in these 7 days, so there is no rate to give and no volume to give it against.'
	);
	await expect(page.locator('[data-failure-chart]')).toHaveCount(0);
	await expect(page.locator('[data-failure-panels]')).toBeVisible();
});

test('the chart draws in CSS pixels, so its type is the size it declares', async ({ page }) => {
	await page.goto('/console/');

	// A `viewBox` is a scale factor, not a unit. Three panels declaring 360
	// units into a 163px column put `font-size="10"` on screen at 4.5px.
	const chart = page.locator('[data-failure-chart]');
	await expect(chart, 'one chart, not three panels').toHaveCount(1);

	for (const width of [380, 768, 1400]) {
		await page.setViewportSize({ width, height: 900 });
		await expect
			.poll(async () =>
				chart.evaluate((node) => {
					const declared = Number((node.getAttribute('viewBox') ?? '').split(' ')[2]);
					return Math.abs(declared - node.getBoundingClientRect().width) <= 1;
				})
			)
			.toBe(true);
	}

	// Both ends of the fixed rate axis are printed, so the scale can be read
	// without hovering anything.
	await expect(chart).toContainText('100%');
	await expect(chart).toContainText('0%');
	// And both axes are named, because a chart with two y scales that names
	// neither is a chart nobody can read a value off.
	await expect(chart).toContainText('Items');
	await expect(chart).toContainText('Failure rate');
	// The bands that are not a stage colour are named too. The column height is
	// the volume, and a reader who cannot tell what the tall grey band means
	// cannot read the volume off it.
	await expect(page.locator('[data-failure-key]')).toContainText('the work that finished');
});

test('the surface follows the shared window and says so', async ({ page }) => {
	await page.goto('/console/');
	await expect(page.locator('[data-window-preset="7"] input')).toBeEnabled();

	for (const days of [7, 14]) {
		await page.locator(`[data-window-preset="${days}"]`).click();
		const surface = page.locator('[data-windowed="failure-rate"]');
		await expect(surface).toHaveAttribute('data-window-days', String(days));
		// The number is in the words as well as the attribute. An attribute
		// nobody reads is not a disclosure.
		expect(flat((await surface.getAttribute('aria-label')) ?? '')).toContain(`over ${days} days`);
	}
});
