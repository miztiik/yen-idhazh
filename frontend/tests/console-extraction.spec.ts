/** Private yield and native extraction/evaluator states remain independent. */
import { expect, test } from './support/door-page';
import { hydrated, setWindow } from './support/console-window/controls';
import { THROUGH, nativeRow, packedPipelines, servePipelines, settled } from './support/pipelines-ledgers';

let root: string;
test.beforeAll(async () => {
	root = await packedPipelines('extraction', [{ covers: THROUGH, rows: [
		nativeRow(THROUGH, { url_key: 'one', element_class: 'comparative', span_integrity: false, elements_found: 4 }),
		nativeRow(THROUGH, { url_key: 'two', element_class: 'processual', span_integrity: true, elements_found: 0 })
	] }], [{ covers: THROUGH, rows: [
		{ date: THROUGH, url_key: 'one', extraction_suspect: true },
		{ date: THROUGH, url_key: 'two', extraction_suspect: null }
	] }]);
});
test.beforeEach(async ({ page }) => servePipelines(page, root));
const panel = (page: import('@playwright/test').Page) => page.locator('[data-eval-panel="extraction"]');

test('the panel names its own absence rather than leaving a heading over nothing', async ({ page }) => {
	await page.route('**/state/compact/item-health/index/*.json', (route) => route.fulfill({ status: 404 }));
	await page.goto('/console/');
	await settled(page);
	await expect(panel(page)).toBeVisible();
	await expect(panel(page).locator('[data-extraction="none"]')).toContainText('unavailable');
	await expect(panel(page).locator('[data-reserved="extraction"]')).toHaveAttribute('data-panel-state', 'missing');
	await expect(panel(page).locator('[data-extraction-source="flags"]')).toHaveAttribute('data-panel-state', 'ready');
	await expect(panel(page)).toContainText('1 have no boolean flag');
});

test('a panel with no private record draws no trend and no empty axis', async ({ page }) => {
	await page.goto('/console/');
	await settled(page);
	await expect(panel(page).locator('[data-extraction="none"]')).toBeVisible();
	await expect(panel(page).locator('[data-chart-name="extraction-yield"] svg')).toHaveCount(0);
	await expect(panel(page).locator('[data-extraction-trend-day]')).toHaveCount(0);
	await expect(panel(page)).toContainText('No build-time day carries both yield counts.');
});

test('the panel names measured comparative and processual classes, not promised future measurements', async ({ page }) => {
	await page.goto('/console/');
	await settled(page);
	await expect(panel(page)).toContainText('comparative');
	await expect(panel(page)).toContainText('processual');
	await expect(panel(page)).toContainText('would not re-slice');
	await expect(panel(page)).not.toContainText('Two more classes are coming');
});

test('the section follows the window control the rest of the page follows', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);
	for (const days of [1, 7]) {
		await setWindow(page, days);
		await settled(page);
		await expect(page.locator('[data-windowed="extraction"]')).toHaveAttribute('data-window-days', String(days));
		await expect(panel(page).locator('[data-extraction-record]')).toHaveText(`Extraction record: ${THROUGH} through ${THROUGH}.`);
		await expect(panel(page).locator('[data-extraction-evaluator-record]')).toHaveText(`Flag record: ${THROUGH} through ${THROUGH}.`);
	}
});

test('the panel prints no jargon a term sheet would be needed for', async ({ page }) => {
	await page.goto('/console/');
	await settled(page);
	const text = ((await panel(page).textContent()) ?? '').toLowerCase();
	for (const term of ['extractable_but_unused', 'span_integrity', 'element_class', 'tier 1']) expect(text).not.toContain(term);
});

test('the page reports no error and no missing file while the panel renders', async ({ page }) => {
	const errors: string[] = [];
	const missing: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
	page.on('response', (response) => { if (response.status() === 404) missing.push(response.url()); });
	await page.goto('/console/');
	await settled(page);
	await expect(panel(page)).toBeVisible();
	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});

test('recorded flags keep their exact counts without certifying a checker', async ({ page }) => {
	await page.goto('/console/');
	await settled(page);
	await expect(panel(page).getByText('Recorded flags for page furniture', { exact: true })).toBeVisible();
	await expect(panel(page)).toContainText('of 2 distinct recorded articles; 1 have no boolean flag');
	await expect(panel(page).locator('[data-extraction-provenance]')).toHaveText(
		"The record does not identify which extraction checker ran or its version. A false flag is the record's default, not proof that an extraction check ran.");
	await expect(panel(page).locator('[data-nothing-fired]')).toHaveCount(0);
	await expect(panel(page)).not.toContainText("other evaluators' unmeasured cells");
});

for (const state of ['missing', 'unreachable', 'quiet'] as const) {
	test(`the ${state} evaluator does not collapse a loaded extractor into null`, async ({ page }) => {
		await page.route('**/state/compact/summary-quality-evals/index/*.json', async (route) => {
			if (state === 'missing') return route.fulfill({ status: 404 });
			if (state === 'unreachable') return route.abort('failed');
			const response = await route.fetch();
			const index = await response.json();
			return route.fulfill({ response, json: { ...index, entries: index.entries.map((entry: object) =>
				({ ...entry, rows: 0, bytes: 0, state: 'empty' })) } });
		});
		await page.goto('/console/');
		await settled(page);
		await expect(panel(page).locator('[data-extraction-source="native"]')).toHaveAttribute('data-panel-state', 'ready');
		await expect(panel(page).locator('[data-reserved="extraction-suspect"]')).toHaveAttribute('data-panel-state', state);
		await expect(panel(page)).toContainText('comparative');
		await expect(panel(page).locator('[data-nothing-fired]')).toHaveCount(0);
	});
}
