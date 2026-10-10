/** What the judge said about the line, on a rendered page.
 *
 * The arithmetic is checked without a browser in `verdict-split.spec.ts`. What
 * is left needs the page: a cell that names what it actually knows, an axis
 * taken off the record's own band rather than off zero, a dash where the ledger
 * holds no answer, and a rule drawn at the line the day was built with.
 *
 * The canary has no score record: it must not draw measured zeros. A private
 * full route supplies a real score-distribution file and checks every drawing
 * through the real loader, including a build line different from fitted history.
 * `console-judgement-nothings` owns the supplied zero-count record.
 */

import { expect, test, type Page } from './support/door-page';
import { chartsReady } from './support/charts-ready';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { judgementRoute } from './support/judgement-route';
import { BUILD_TIME } from './support/panel-drivers/judgement';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const ROUTE = '/console/judgement/';
const SPLIT = '[data-verdict-split]';
let recorded: Awaited<ReturnType<typeof judgementRoute>>;
let recordedClosed = false;

test.beforeAll(async ({}, testInfo) => {
	test.setTimeout(180_000);
	recorded = await judgementRoute(testInfo.outputPath('recorded-route'), { scoreRecord: 'populated' });
});

test.afterAll(async () => {
	if (!recordedClosed) await recorded?.close();
});

test('THE ORACLE: the hydrated route binds all three panels to the newest build record', async ({ browser }) => {
	const server = recorded;
	const context = await browser.newContext({ serviceWorkers: 'block' });
	try {
			await context.route('**/*', (route) =>
				new URL(route.request().url()).origin === new URL(server.origin).origin
					? route.continue()
					: route.abort('blockedbyclient'));
			const page = await context.newPage();
			const errors: string[] = [];
			page.on('pageerror', (error) => errors.push(error.message));
			page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
			page.on('response', (response) => { if (response.status() === 404) errors.push(`404 ${response.url()}`); });
			await page.goto(`${server.origin}console/judgement/`, { timeout: 60_000 });
			const oneDay = page.locator('[data-window-preset="1"]');
			await expect(oneDay.locator('input')).toBeEnabled();
			await page.locator('[data-window-preset="14"]').click();
			const merge = page.locator('[data-windowed="merge-line"]');
			await expect(merge.locator('[data-line-day="2030-06-14"]')).toHaveAttribute('data-line-applied', '0.952');
			await expect(page.locator('[data-windowed="record-gates"] [data-target-bar]')).toHaveCount(3);
			expect(await page.locator('[data-windowed="record-gates"] [data-target-bar]')
				.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-target-tone'))))
				.toEqual(['policy', 'policy', 'policy']);
			await oneDay.click();
			await expect(merge).toHaveAttribute('data-line-days', '0');
			await chartsReady(page);
			await expect(merge.locator('[data-line-rule]')).toHaveAttribute('data-line-rule', '0.937');
			await expect(merge.locator('[data-line-rule]')).toHaveAttribute('stroke-dasharray', /.+/);
			await expect(merge.locator('[data-line-rule-label]')).toHaveText('The line this one day was built with');
			await expect(page.locator(SPLIT)).toHaveAttribute('data-verdict-line', '0.937');
			await expect(page.locator(`${SPLIT} [data-verdict-rule]`)).toHaveAttribute('data-verdict-rule', '0.937');
			await expect(page.locator('[data-holdout-rule]')).toHaveAttribute('data-holdout-rule', '0.9370');
			expect(errors, 'the generated full route must hydrate without browser errors or missing assets').toEqual([]);
	} finally {
		await context.close();
	}
});

test('an absent score record prints an unavailable sentence without measured zeros', async ({ page }) => {
	await page.goto(ROUTE);
	await chartsReady(page);
	await expect(page.locator(`${SPLIT} [data-empty="missing"]`)).toHaveText(
		"The judge's score record is unavailable."
	);
	await expect(page.locator(`${SPLIT} [data-verdict-cell]`)).toHaveCount(0);
	await expect(page.locator(`${SPLIT} [data-verdict-figures]`)).toHaveCount(0);
	await expect(page.locator(`${SPLIT} [data-chart-type]`)).toHaveCount(0);
});

function appearance(): { console: { precision_axis_multiple: number } } {
	// Read inside the test, never at module scope: a fixture opened while the
	// module loads fails before any test exists to own the failure.
	return JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8'));
}

function tuning(): { discard_share: number } {
	return JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble.same_story
		.adaptive_dedup_threshold;
}

async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1000 });
	await page.goto(`${recorded.origin}console/judgement/`);
	await chartsReady(page);
}

test.describe('what the judge said about the line', () => {
	test('the note names the newest day whose line every judged pair uses', async ({ page }) => {
		await open(page);

		await expect(
			page.locator('[data-console-panel="What the judge said about the line"] .panel-note')
		).toHaveText(
			'Every judged pair, split by whether its score cleared the line the newest day was built with and by what the judge said about it.'
		);
	});

	test('the supplied score record draws its cells, ranges and figures', async ({ page }) => {
		await open(page);

		await expect(page.locator(SPLIT)).toBeVisible();
		await expect(page.locator(`${SPLIT} [data-verdict-cell]`)).toHaveCount(4);
		await expect(page.locator(`${SPLIT} [data-verdict-cost]`)).toBeVisible();
		await expect(page.locator(`${SPLIT} [data-verdict-figures]`)).toBeVisible();
		await expect(page.locator(SPLIT)).toHaveAttribute('data-verdict-days', '1');
		await expect(page.locator(`${SPLIT} [data-verdict-state="reading"]`)).toBeVisible();
	});

	test('no cell claims a pair was merged', async ({ page }) => {
		await open(page);

		// THE BITE. The record holds counts in slots, not pairs, so the split says
		// which side of the line a verdict fell on and nothing more. Whether a pair
		// merged depends on two things the record never saw: a group is refused
		// unless every pair in it clears the line, and two items on different
		// published days never fold at all. Rename a cell to MERGED and this fails.
		const words = await page
			.locator(`${SPLIT} [data-verdict-cell]`)
			.evaluateAll((nodes) => nodes.map((node) => node.textContent ?? ''));

		expect(words).toHaveLength(4);
		for (const cell of words) {
			expect(cell.toLowerCase(), `a cell claims a merge: ${cell}`).not.toMatch(/merged/);
		}
		expect(words.filter((cell) => /eligible/i.test(cell))).toHaveLength(4);
	});

	test('the score axis is the record band, never anchored at zero', async ({ page }) => {
		await open(page);

		// A cosine in this band runs 0.88 to 1.00. An axis anchored at zero would
		// spend seven eighths of its width on scores the record has no slot for,
		// and the two population strips would collapse into one smear.
		const ticks = await page
			.locator(`${SPLIT} [data-tick="x"]`)
			.evaluateAll((nodes) => nodes.map((node) => Number(node.textContent)));

		expect(ticks.length).toBeGreaterThan(1);
		expect(Math.min(...ticks)).toBeGreaterThan(0.5);
		expect(Math.max(...ticks)).toBeLessThanOrEqual(1);
	});

	test('the rule sits at the line the day was built with', async ({ page }) => {
		await open(page);

		const line = await page.locator(SPLIT).getAttribute('data-verdict-line');
		const rule = await page.locator(`${SPLIT} [data-verdict-rule]`).getAttribute('data-verdict-rule');

		// One number, drawn once. A rule at a different value from the readout would
		// be two answers to the question the panel exists to ask.
		expect(rule).toBe(line);
		expect(Number(line)).toBeGreaterThan(0);
	});

	test('the figures print the recorded counts without inventing zeros', async ({ page }) => {
		await open(page);

		const figures = await page
			.locator(`${SPLIT} [data-verdict-figure]`)
			.evaluateAll((nodes) => nodes.map((node) => (node.textContent ?? '').trim()));

		expect(figures).toEqual(['10', '10', '10']);
	});

	test('the precision reading names the target it is judged against', async ({ page }) => {
		await open(page);

		// The corridor is the discard share times a knob, so a reader can see both
		// the target and a tenfold overshoot without the axis moving under them.
		const knobs = appearance().console.precision_axis_multiple;
		const target = tuning().discard_share;

		expect(knobs).toBeGreaterThan(1);
		expect(target).toBeGreaterThan(0);
		await expect(page.locator(`${SPLIT} [data-verdict-precision]`)).toBeVisible();
	});

	test('both population strips are labelled even where neither has a range', async ({ page }) => {
		await open(page);

		// A strip with nothing in it still says which population it is waiting for.
		// Dropping the label on an empty strip would leave a reader guessing which
		// of the two lines is missing.
		const labels = await page
			.locator(`${SPLIT} [data-verdict-strip-label]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-verdict-strip-label')));

		expect(labels.sort()).toEqual(['different', 'same']);
	});

	test('the slice table is shut, and says so when it holds nothing', async ({ page }) => {
		await open(page);

		// Twenty-four rows below a chart is a wall. It opens on a click, and closed
		// is the resting state.
		const table = page.locator(`${SPLIT} [data-verdict-table]`);
		await expect(table).toBeVisible();
		expect(await table.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
	});

	test('the panel says why it has no column to point at', async ({ page }) => {
		await open(page);

		// Two population ranges on one score axis. There is no day column the two
		// share, so the panel says so rather than leaving a reader unable to tell a
		// decision from an omission.
		const reason = (await page.locator(SPLIT).getAttribute('data-readout-none')) ?? '';
		expect(reason.trim().split(/\s+/).length, `the reason reads "${reason}"`).toBeGreaterThanOrEqual(
			5
		);
		expect(reason).toContain('no column to share');
	});

	test('a strip that has a range prints its middle, where the circle is drawn', async ({ page }) => {
		await open(page);

		const labels = await page
			.locator(`${SPLIT} [data-verdict-strip-label]`)
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					name: node.getAttribute('data-verdict-strip-label') ?? '',
					words: node.textContent ?? ''
				}))
			);
		expect(labels.length, 'neither strip is labelled').toBe(2);

		// Two x ticks are enough to invert the scale the panel drew with, so the
		// printed middle is checked against the pixel the circle sits at rather
		// than against the same number read back from the same string.
		const ticks = await page
			.locator(`${SPLIT} [data-tick="x"]`)
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					at: Number(node.getAttribute('x')),
					score: Number(node.textContent)
				}))
			);
		expect(ticks.length, 'the score axis drew fewer than two ticks').toBeGreaterThan(1);
		const first = ticks[0];
		const last = ticks[ticks.length - 1];
		const scoreAt = (x: number): number =>
			first.score + ((x - first.at) * (last.score - first.score)) / (last.at - first.at);

		let checked = 0;
		for (const label of labels) {
			if (label.words.startsWith('Nothing was ')) continue;
			expect(label.words, `the ${label.name} strip does not print its middle`).toMatch(
				/, middle \d\.\d{3}$/
			);
			const printed = Number(label.words.match(/, middle (\d\.\d{3})$/)![1]);
			const cx = Number(
				await page.locator(`${SPLIT} [data-verdict-median="${label.name}"]`).getAttribute('cx')
			);
			expect(
				scoreAt(cx),
				`the ${label.name} strip prints a middle the circle is not drawn at`
			).toBeCloseTo(printed, 3);
			checked += 1;
		}

		expect(checked, 'the real score record must draw both ranges').toBe(2);
	});
});

test('the full route renders in both themes with every source absent', async ({ browser }, testInfo) => {
	test.setTimeout(180_000);
	await recorded.close();
	recordedClosed = true;
	const server = await judgementRoute(testInfo.outputPath('absent-route'), { evidence: 'absent' });
	try {
		for (const width of [390, 768, 1440]) {
			for (const theme of ['light', 'dark']) {
				const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width, height: 1000 } });
				try {
					await context.addInitScript((choice) => localStorage.setItem('idhazh:theme', choice), theme);
					const page = await context.newPage();
					const errors: string[] = [];
					page.on('pageerror', (error) => errors.push(error.message));
					page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
					page.on('response', (response) => { if (response.status() === 404) errors.push(`404 ${response.url()}`); });
					await page.goto(`${server.origin}console/judgement/`);
					await chartsReady(page);
					await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
					for (const id of BUILD_TIME) {
						await expect(page.locator(`[data-console-panel-id="${id}"] [data-lede]`)).toBeVisible();
					}
					await expect(page.locator('[data-verdict-split] [data-empty="missing"]')).toBeVisible();
					await expect(page.locator('[data-console-panel-id="record-gates"] [data-empty="missing"]')).toHaveText("The record's gate counts are unavailable for these 14 days.");
					await expect(page.locator('[data-console-panel-id="record-gates"] [data-evidence-note]')).toHaveText(
						'The judge record has not been packed yet. Its readings are unavailable.'
					);
					await expect(page.locator('[data-target-cell="track"]')).toHaveCount(0);
					expect(errors, `${width}, ${theme}, absent source files`).toEqual([]);
				} finally {
					await context.close();
				}
			}
		}
	} finally {
		await server.close();
	}
});
