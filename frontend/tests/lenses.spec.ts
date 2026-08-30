import { expect, test } from '@playwright/test';
import { LENS_NAMES, MAX_LENS_CHIPS, shownLenses } from '../src/lib/payload/lenses';

/**
 * A topic chip is the one thing on an item that a desk heading cannot say: that
 * this story and one three screens down under another desk are the same story.
 *
 * It is inert on purpose, so the assertions that matter are about what it is
 * NOT - not a control, not present when we know nothing, not a tombstone.
 */

test.describe('the chips, without a browser', () => {
	test('unknown and retired ids resolve to nothing', () => {
		expect(shownLenses(['ai-roi'])).toEqual([]);
		expect(shownLenses(['not-a-lens'])).toEqual([]);
		expect(shownLenses(undefined)).toEqual([]);
		expect(shownLenses([])).toEqual([]);
	});

	test('more than the cap is cut, in configured order and not payload order', () => {
		const shown = shownLenses(['war', 'chips', 'china']);
		expect(shown).toHaveLength(MAX_LENS_CHIPS);
		expect(shown).toEqual(['chips', 'china']);
	});

	test('every name is a phrase a reader would use', () => {
		for (const [id, name] of Object.entries(LENS_NAMES)) {
			expect(name, id).not.toMatch(/[-_]/);
			expect(name[0], id).toBe(name[0].toUpperCase());
		}
	});
});

test.describe('the chips on the page', () => {
	test('a topic renders its display name beside the desk', async ({ page }) => {
		await page.goto('/');
		const war = page.locator('[data-lens="war"]');
		await expect(war).toHaveCount(1);
		await expect(war).toHaveText('War');
		await expect(page.locator('article[data-lenses~="war"]')).toHaveCount(1);
	});

	test('an item shows no more topics than the page allows', async ({ page }) => {
		await page.goto('/');
		// The canary plants china, trade and chips on one item. Two is the cap and
		// the order is the vocabulary's, not the payload's, so chips and china
		// survive and trade is dropped with no overflow marker - a "+1 more" on a
		// two-word label is more chrome than the word it hides.
		const many = page.locator('article[data-lenses~="china"]');
		await expect(many).toHaveCount(1);
		await expect(many.locator('[data-lens]')).toHaveCount(MAX_LENS_CHIPS);
		await expect(many.locator('[data-lens="chips"]')).toHaveCount(1);
		await expect(many.locator('[data-lens="trade"]')).toHaveCount(0);
	});

	test('an item we could not place carries no attribute and no chip', async ({ page }) => {
		await page.goto('/');
		// Most items have no lens. The absence is a gap in our keyword list and
		// not a fact about the story, so the page says nothing rather than
		// printing a dash. `:not([data-lenses])` only works if the attribute is
		// absent rather than empty.
		const bare = page.locator('article.item:not([data-lenses])');
		expect(await bare.count()).toBeGreaterThan(0);
		await expect(bare.locator('[data-lens]')).toHaveCount(0);
	});

	test('a topic is not a control', async ({ page }) => {
		await page.goto('/');
		await expect(page.locator('a[data-lens], button[data-lens], [data-lens][tabindex]')).toHaveCount(
			0
		);
	});

	test('a retired topic never reaches the page', async ({ page }) => {
		await page.goto('/');
		await expect(page.locator('[data-lens="ai-roi"]')).toHaveCount(0);
		await expect(page.getByText('Return on AI investment')).toHaveCount(0);
	});

	test('events and entities stay off the reading page', async ({ page }) => {
		await page.goto('/');
		await expect(page.locator('[data-event], [data-entity]')).toHaveCount(0);
	});
});
