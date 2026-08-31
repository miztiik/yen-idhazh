/** The Machine route in a browser: what it draws, and what it does with a rate.
 *
 * The arithmetic is checked in `console-machine.spec.ts` against fixture rows.
 * What is checked here is everything that only a browser can answer - that the
 * marks reach the page at all, that the page is complete before any script runs,
 * and that a typed rate redraws every cost figure from one shared value rather
 * than from four copies that can drift.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
) as {
	run: { shard_timeout_minutes: number };
	observability: {
		cost_currency: string;
		cost_input_per_million: number;
		cost_output_per_million: number;
	};
};

/** Digits out of a money string. `money` groups thousands and names the
 * currency, so a parser has to strip both. */
function amount(text: string): number {
	return Number(text.replace(/[^0-9.]/g, ''));
}

async function costs(page: Page): Promise<Record<string, number>> {
	const cells = await page
		.locator('[data-cost-figures] [data-cost]')
		.evaluateAll((nodes) =>
			nodes.map((node) => [
				node.getAttribute('data-cost') ?? '',
				(node.querySelector('dd')?.textContent ?? '').trim()
			])
		);
	return Object.fromEntries(cells.map(([key, text]) => [key, amount(text)]));
}

async function typeRate(page: Page, which: 'input' | 'output', value: string): Promise<void> {
	const field = page.locator(`[data-rate-input="${which}"]`);
	await expect(field).toBeEnabled();
	await field.fill(value);
	await field.blur();
}

test.describe('the shard board', () => {
	test('draws a row per shard that reported, and each bar sums to that shard', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-shard-board]');
		await expect(board).toHaveCount(1);
		// The canary carries a counters ledger and so does the committed one, so an
		// empty board here is a broken read rather than a state to tolerate. An
		// assertion that returned early on it would pass having checked nothing.
		await expect(board).not.toHaveAttribute('data-shard-board', 'empty');

		const rows = await page.locator('[data-shard-row]').evaluateAll((nodes) =>
			nodes.map((node) => ({
				shard: Number(node.getAttribute('data-shard-row')),
				read: node.getAttribute('data-shard-read-seconds') ?? '',
				write: node.getAttribute('data-shard-write-seconds') ?? '',
				model: node.getAttribute('data-shard-model-seconds') ?? '',
				job: node.getAttribute('data-shard-job-seconds') ?? '',
				cpu: node.getAttribute('data-shard-cpu') ?? ''
			}))
		);
		expect(rows.length, 'the board drew no shard').toBeGreaterThan(0);
		expect(rows.length).toBeLessThanOrEqual(Number(await board.getAttribute('data-shard-board-shards')));

		for (const row of rows) {
			if (row.model === '') continue;
			// Reading and writing are never one figure, and the two of them are the
			// whole of the model's seconds for that shard.
			expect(Number(row.read) + Number(row.write)).toBeCloseTo(Number(row.model), 6);
		}

		// Ranked by the clock the platform kills a shard on, slowest first, with an
		// unclocked shard last rather than sorted as though its clock were zero.
		const clocked = rows.filter((row) => row.job !== '').map((row) => Number(row.job));
		expect(clocked).toEqual([...clocked].sort((a, b) => b - a));
		expect(rows.findIndex((row) => row.job === '')).toBe(
			clocked.length === rows.length ? -1 : clocked.length
		);
	});

	test('the job clock is read against the configured timeout', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator('[data-shard-board]');
		await expect(board).toHaveAttribute(
			'data-shard-board-timeout-seconds',
			String(CONFIG.run.shard_timeout_minutes * 60)
		);
	});
});

test.describe('the page as a whole', () => {
	test('renders every panel with no console error and no failed request', async ({ page }) => {
		const errors: string[] = [];
		const bad: string[] = [];
		page.on('console', (message) => {
			if (message.type() === 'error') errors.push(message.text());
		});
		page.on('pageerror', (error) => errors.push(String(error)));
		page.on('response', (response) => {
			if (response.status() >= 400) bad.push(`${response.status()} ${response.url()}`);
		});

		await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });
		await page.waitForTimeout(900);

		expect(await page.locator('[data-console-panel]').count()).toBeGreaterThan(5);
		expect(errors).toEqual([]);
		expect(bad).toEqual([]);
	});

	test('every chart on the route names itself for anybody who cannot see it', async ({ page }) => {
		await page.goto('/console/machine/', { waitUntil: 'domcontentloaded' });
		await page.waitForTimeout(900);
		const described = await page.evaluate(() =>
			[...document.querySelectorAll('[data-surface="operator"] svg')]
				.filter((svg) => svg.closest('[aria-hidden="true"]') === null)
				.filter((svg) => svg.getBoundingClientRect().width > 0)
				.map((svg) => (svg.closest('[aria-label]')?.getAttribute('aria-label') ?? '').trim())
		);
		expect(described.length, 'no chart found - the scan is broken').toBeGreaterThan(2);
		expect(described.filter((label) => label === '')).toEqual([]);
	});

	test('a share prints its denominator rather than standing alone', async ({ page }) => {
		await page.goto('/console/machine/');
		// Every panel that divides says what it divided by: a rate with no
		// denominator beside it is the defect the item-health census exists to
		// prevent, and it is the same defect one layer up.
		await expect(page.locator('[data-reading-writing-sentence]')).toContainText(
			/of the run's \d+ shards/
		);
		await expect(page.locator('[data-context-run]').first()).toContainText(
			/over \d+ of \d+ shards/
		);
	});

	test('a shard that reported nothing prints absence, never a zero', async ({ page }) => {
		await page.goto('/console/machine/');
		// The canary's newest run carries one shard written before `job_seconds`,
		// `cpu_model` and the three host cells existed - the state 24 of the 54
		// committed rows are in. A dash is the only honest reading of it, and a
		// `0 s` there would say that shard finished instantly.
		const blank = page.locator('[data-shard-row][data-shard-job-seconds=""]');
		if ((await blank.count()) === 0) return;
		await expect(blank.first().locator('[data-shard-cell="cpu"]')).toContainText('Not recorded');
		await expect(blank.first().locator('[data-target-cell="value"]')).toHaveText('-');
		await expect(blank.first().locator('[data-target-cell="empty"]')).toBeVisible();
	});
});

test.describe('the rate the cost is counterfactual against', () => {
	test('the prerendered page prices at the configured rate and says so', async ({ page }) => {
		await page.goto('/console/machine/');
		const figures = page.locator('[data-cost-figures]');
		// Both the canary and the committed ledger carry token counts, so an absent
		// cost panel is a broken read rather than a state to skip past.
		await expect(figures).toHaveCount(1);
		await expect(figures).toHaveAttribute('data-cost-source', 'configured');
		await expect(page.locator('[data-rate-basis]')).toContainText('Using the configured rate');
		await expect(page.locator('[data-rate-basis]')).toContainText(
			CONFIG.observability.cost_currency
		);
		// Four figures, and the set is the whole point: a total with no per-article
		// figure beside it cannot be compared with anything.
		expect(Object.keys(await costs(page)).sort()).toEqual([
			'input',
			'output',
			'per-article',
			'total'
		]);
	});

	test('a typed rate redraws every cost figure from one value', async ({ page }) => {
		await page.goto('/console/machine/');

		// Two typed rates, one exactly twice the other, rather than a comparison
		// against the configured pair: the committed rate is small enough that the
		// window's cost rounds away at two decimals, and a ratio taken across that
		// floor would be decided by the rounding rather than by the arithmetic.
		await typeRate(page, 'input', '100');
		await typeRate(page, 'output', '300');
		await expect(page.locator('[data-cost-figures]')).toHaveAttribute('data-cost-source', 'yours');
		await expect(page.locator('[data-rate-basis]')).toContainText('Using your rate');
		const single = await costs(page);
		expect(single.total).toBeGreaterThan(0.1);

		await typeRate(page, 'input', '200');
		await typeRate(page, 'output', '600');
		const doubled = await costs(page);

		// Every figure has to move by the same factor, which is what says they come
		// off one shared value rather than four copies of it.
		for (const key of ['input', 'output', 'total'] as const) {
			expect(doubled[key], `${key} did not follow the typed rate`).toBeCloseTo(single[key] * 2, 1);
		}
		// The prompts cost more than the answers here, because the run read far more
		// than it wrote - so the two figures are not the same number twice.
		expect(doubled.input).not.toBeCloseTo(doubled.output, 2);
	});

	test('the typed rate survives a reload, and the configured one is one click away', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const configured = (await page.locator('[data-cost="total"] dd').innerText()).trim();

		await typeRate(page, 'input', '100');
		await typeRate(page, 'output', '300');
		const typed = await costs(page);
		expect(typed.total).toBeGreaterThan(0.1);

		await page.reload();
		await expect(page.locator('[data-cost-figures]')).toHaveAttribute('data-cost-source', 'yours');
		expect((await costs(page)).total).toBeCloseTo(typed.total, 2);

		await page.locator('[data-rate-reset]').click();
		await expect(page.locator('[data-cost-figures]')).toHaveAttribute(
			'data-cost-source',
			'configured'
		);
		expect((await page.locator('[data-cost="total"] dd').innerText()).trim()).toBe(configured);
	});
});

test.describe('with no script at all', () => {
	test('the route is complete, and the rate control is inert rather than broken', async ({
		browser
	}) => {
		// A prerendered operator page owes a reader every mark before a script
		// runs. What a script adds here is a pointer readout and a typed rate, and
		// neither is on the page's critical path.
		const context = await browser.newContext({ javaScriptEnabled: false });
		const page = await context.newPage();
		await page.goto('/console/machine/');

		expect(await page.locator('[data-console-panel]').count()).toBeGreaterThan(5);
		await expect(page.locator('[data-shard-board]')).toHaveCount(1);
		// The server drew every chart, so the marks are in the document itself.
		expect(await page.locator('[data-surface="operator"] svg').count()).toBeGreaterThan(2);

		if ((await page.locator('[data-cost-figures]').count()) === 1) {
			await expect(page.locator('[data-cost-figures]')).toHaveAttribute(
				'data-cost-source',
				'configured'
			);
			await expect(page.locator('[data-rate-input="input"]')).toBeDisabled();
			await expect(page.locator('[data-rate-static]')).toBeVisible();
			// A cost that rounds away prints `<0.01`, never `0.00`: a zero there
			// would say the work was free.
			const total = (await page.locator('[data-cost="total"] dd').innerText()).trim();
			expect(total).toMatch(/\d/);
			expect(total).not.toBe(`0.00 ${CONFIG.observability.cost_currency}`);
		}
		await context.close();
	});
});
