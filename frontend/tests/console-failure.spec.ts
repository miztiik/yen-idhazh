import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { failureLoad } from '../src/lib/charts/glance';
import { failureSeries, type TelemetryRow } from '../src/lib/charts/series';
import { readCsv } from '../src/lib/server/payload';

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
 * The canary fixture records no failure at all, which is deliberate elsewhere -
 * the failed-item list is the section that proves the page renders with nothing
 * to show. So the two states that need failures in them are driven as pure
 * functions here, and the two states the fixture DOES reach - a window too thin
 * to divide, and a window holding nothing - are driven in the browser through
 * the controls an operator has.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

/** The knob, read from the file the page reads it from. */
const MIN_ATTEMPTS_FOR_RATE = (
	JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')) as {
		console?: { min_attempts_for_rate?: number };
	}
).console?.min_attempts_for_rate ?? 5;

const STAGES = ['fetch', 'extract', 'summarize'] as const;

function row(date: string, id: string, stage: string, outcome: string, code = ''): TelemetryRow {
	return {
		date,
		run_id: `${date}-1`,
		item_id: id,
		vertical: 'ai',
		source_id: 'fixture',
		stage,
		outcome,
		code,
		source_words: 400,
		summary_words: 60,
		source_words_before_cap: null,
		fetch_ms: null,
		extract_ms: null,
		summarize_ms: null,
		prefill_ms: null,
		decode_ms: null,
		input_tokens: null,
		output_tokens: null,
		cached_tokens: null
	};
}

/** Every telemetry row the canary published, as the page reads them. */
function canaryRows(): Record<string, string>[] {
	const shard = join(CANARY, 'state', 'telemetry');
	return readdirSync(shard)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(shard, name)).rows);
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
	await page.goto('/console/');

	const control = page.locator('[data-viewport-control]');
	const start = (await control.getAttribute('data-window-start')) ?? '';
	const end = (await control.getAttribute('data-window-end')) ?? '';
	expect(start, 'the viewport publishes no window, so there is nothing to count over').not.toBe('');

	// Recomputed from the fixture, down the pipeline order, exactly as the page
	// claims to: each stage's denominator is what the stage before it let through.
	const inWindow = canaryRows().filter((r) => r.date >= start && r.date <= end);
	let reached = inWindow.filter((r) => r.stage !== 'plan').length;
	expect(reached, 'the window holds nothing, so the counts below are trivial').toBeGreaterThan(0);

	for (const stage of STAGES) {
		const failures = inWindow.filter((r) => r.outcome === 'failed' && r.stage === stage).length;
		const cell = page.locator(`[data-failure-stage="${stage}"]`);
		await expect(cell).toHaveAttribute('data-stage-reached', String(reached));
		await expect(cell).toHaveAttribute('data-stage-failed', String(failures));
		await expect(cell).toHaveAttribute(
			'data-stage-low-sample',
			reached < MIN_ATTEMPTS_FOR_RATE ? 'true' : 'false'
		);
		// The number in the attribute is the number in the sentence.
		expect(flat(await page.locator(`[data-panel-rate="${stage}"]`).innerText())).toContain(
			`${reached.toLocaleString('en-US')} that reached it`
		);
		reached -= failures;
	}
});

test('a day under the threshold gets no mark, and a day over it gets one', async ({ page }) => {
	await page.goto('/console/');

	const control = page.locator('[data-viewport-control]');
	const start = (await control.getAttribute('data-window-start')) ?? '';
	const end = (await control.getAttribute('data-window-end')) ?? '';
	const perDay = new Map<string, number>();
	for (const r of canaryRows()) {
		if (r.date < start || r.date > end || r.stage === 'plan') continue;
		perDay.set(r.date, (perDay.get(r.date) ?? 0) + 1);
	}
	const fat = [...perDay.values()].filter((n) => n >= MIN_ATTEMPTS_FOR_RATE).length;
	const thin = [...perDay.values()].filter((n) => n > 0 && n < MIN_ATTEMPTS_FOR_RATE).length;

	// Positive evidence and negative evidence together. A count of zero marks
	// would pass an absence test on a chart that draws nothing at all.
	expect(fat, 'no day in the window is thick enough to draw a mark').toBeGreaterThan(0);
	expect(thin, 'no day in the window is thin enough to withhold one').toBeGreaterThan(0);
	await expect(page.locator('[data-rate-mark="fetch"]')).toHaveCount(fat);
	await expect(page.locator('[data-rate-mark="summarize"]')).toHaveCount(fat);
});

test('a window too thin to divide states that, and never a rate', async ({ page }) => {
	await page.goto('/console/');
	await expect(page.locator('[data-window-preset="7"] input')).toBeEnabled();

	// Driven through the controls an operator has: narrow to the shortest
	// preset, then step back until the window holds fewer items than the knob
	// asks for. The canary's older days carry one and three items, so this state
	// is reachable without inventing a fixture for it.
	await page.locator('[data-window-preset="7"]').click();
	const control = page.locator('[data-viewport-control]');
	const back = page.getByRole('button', { name: 'Back' });

	let reached = 0;
	for (let step = 0; step < 6; step += 1) {
		await back.click();
		const start = (await control.getAttribute('data-window-start')) ?? '';
		const end = (await control.getAttribute('data-window-end')) ?? '';
		reached = canaryRows().filter(
			(r) => r.date >= start && r.date <= end && r.stage !== 'plan'
		).length;
		if (reached > 0 && reached < MIN_ATTEMPTS_FOR_RATE) break;
	}
	expect(reached, 'no window this walk reached is thin enough to test the state').toBeGreaterThan(0);
	expect(reached).toBeLessThan(MIN_ATTEMPTS_FOR_RATE);

	for (const stage of STAGES) {
		await expect(page.locator(`[data-failure-stage="${stage}"]`)).toHaveAttribute(
			'data-stage-low-sample',
			'true'
		);
		const says = flat(await page.locator(`[data-panel-rate="${stage}"]`).innerText());
		expect(says, `${stage} gave a rate on ${reached} items`).not.toContain('%');
		expect(says).toContain('that reached it');
	}
	await expect(page.locator('[data-failure-low-sample]')).toBeVisible();
});

test('a window holding nothing renders, and says so rather than drawing zero', async ({ page }) => {
	await page.goto('/console/');
	await expect(page.locator('[data-window-preset="7"] input')).toBeEnabled();
	await page.locator('[data-window-preset="7"]').click();

	const control = page.locator('[data-viewport-control]');
	const back = page.getByRole('button', { name: 'Back' });
	for (let step = 0; step < 10; step += 1) {
		await back.click();
		const start = (await control.getAttribute('data-window-start')) ?? '';
		const end = (await control.getAttribute('data-window-end')) ?? '';
		const held = canaryRows().filter((r) => r.date >= start && r.date <= end).length;
		if (held === 0) break;
	}

	// A column of zeroes reads as a run that went badly. An empty window went
	// nowhere at all, and the page has to say which.
	await expect(page.locator('[data-failure-empty]')).toBeVisible();
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
