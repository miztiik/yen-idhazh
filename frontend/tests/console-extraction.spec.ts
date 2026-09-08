import { expect, test } from '@playwright/test';

/** The extraction panel on the operator's page.
 *
 * The canary carries a day-metrics record with no extraction block, and that is
 * by construction rather than by accident: `build_canary_day.py` writes the
 * record before `build-canary.mjs` writes the item-health ledger it would be
 * reduced from, which is the same reason the record carries no throughput and no
 * stage timing. So this suite proves the panel's absent state - the state
 * `CLAUDE.md` section 12 requires of every surface - and the seven built cases in
 * `extraction-window.spec.ts` prove the loaded one.
 */

test.beforeEach(async ({ page }) => {
	await page.goto('/console/');
});

test('the panel names its own absence rather than leaving a heading over nothing', async ({
	page
}) => {
	const panel = page.locator('[data-console-panel="Extraction"]');
	await expect(panel).toBeVisible();

	const absent = panel.locator('[data-extraction="none"]');
	await expect(absent).toBeVisible();
	await expect(absent).toContainText('carries a record of what the extractor found');
	// Not a blank, and not the loaded state either.
	await expect(panel.locator('[data-extraction="classes"]')).toHaveCount(0);
});

test('the panel says two more classes are coming, whether or not it has data', async ({ page }) => {
	const taxonomy = page.locator('[data-extraction="taxonomy"]');

	await expect(taxonomy).toBeVisible();
	await expect(taxonomy).toContainText('Two more classes are coming');
	await expect(taxonomy).toContainText('Comparative and processual');
});

test('the section follows the window control the rest of the page follows', async ({ page }) => {
	const section = page.locator('[data-windowed="extraction"]');

	await expect(section).toBeVisible();
	const opened = await section.getAttribute('data-window-days');
	expect(Number(opened)).toBeGreaterThan(0);
});

test('the panel prints no jargon a term sheet would be needed for', async ({ page }) => {
	const panel = page.locator('[data-console-panel="Extraction"]');
	const text = ((await panel.textContent()) ?? '').toLowerCase();

	// Correct field names, and wrong labels on an operator surface
	// (`CLAUDE.md` section 0b).
	for (const term of ['extractable_but_unused', 'span_integrity', 'element_class', 'tier 1']) {
		expect(text).not.toContain(term);
	}
});

test('the page reports no error and no missing file while the panel renders', async ({ page }) => {
	const errors: string[] = [];
	const missing: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('response', (response) => {
		if (response.status() === 404) missing.push(response.url());
	});

	await page.goto('/console/');
	await expect(page.locator('[data-console-panel="Extraction"]')).toBeVisible();

	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});
