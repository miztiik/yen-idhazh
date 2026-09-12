import { expect, test } from '@playwright/test';
import { LENS_NAMES, MAX_LENS_CHIPS, lensLabel, shownLenses } from '../src/lib/payload/lenses';

/**
 * A topic chip is the one thing on an item that a desk heading cannot say: that
 * this story and one three screens down under another desk are the same story.
 *
 * It is inert on purpose, so the assertions that matter are about what it is
 * NOT - not a control, not present when we know nothing, not a silent edit of a
 * day that has already been published.
 */

test.describe('the chips, without a browser', () => {
	test('an id the payload carries is kept, named or not', () => {
		// Until 2026-09-12 both of these resolved to nothing. That was not the
		// page being tidy - it was the page dropping a word a frozen day had
		// published, which it did on 18 committed items carrying `ai-roi`.
		expect(shownLenses(['ai-roi'])).toEqual(['ai-roi']);
		expect(shownLenses(['not-a-lens'])).toEqual(['not-a-lens']);
		expect(shownLenses(undefined)).toEqual([]);
		expect(shownLenses([])).toEqual([]);
	});

	test('a chip reads its committed name, and falls back to the raw id', () => {
		expect(lensLabel('china')).toBe('China');
		// Retired, not deleted: config still carries the words, so the page still
		// says them.
		expect(lensLabel('ai-roi')).toBe('Return on AI investment');
		// Deleted: nothing left to say but what the day recorded.
		expect(lensLabel('supply-chain')).toBe('supply-chain');
	});

	test('a named id takes a slot before an unnamed one', () => {
		// The cap is two and a reader can read 'China'. `supply-chain` is what a
		// day looks like once its word has been deleted from the vocabulary.
		expect(shownLenses(['supply-chain', 'china'])).toEqual(['china', 'supply-chain']);
		expect(shownLenses(['supply-chain', 'war', 'china'])).toEqual(['china', 'war']);
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

	test('a retired topic keeps its tombstone on a day that published it', async ({ page }) => {
		await page.goto('/');
		// The canary plants `ai-roi` beside `supply-chain` on one item, which is
		// what a real day looks like after the vocabulary moved under it: one word
		// retired and still named in config, one deleted from it entirely.
		const tombstone = page.locator('[data-lens="ai-roi"]');
		await expect(tombstone).toHaveCount(1);
		await expect(tombstone).toHaveText('Return on AI investment');
	});

	test('a topic config cannot name renders the raw id, not a blank', async ({ page }) => {
		await page.goto('/');
		const unnamed = page.locator('[data-lens="supply-chain"]');
		await expect(unnamed).toHaveCount(1);
		await expect(unnamed).toHaveText('supply-chain');
		// Both of the item's words survive: the cap is what drops a chip, never
		// the page's ability to name it.
		await expect(page.locator('article[data-lenses~="ai-roi"] [data-lens]')).toHaveCount(2);
	});

	test('events and entities stay off the reading page', async ({ page }) => {
		await page.goto('/');
		await expect(page.locator('[data-event], [data-entity]')).toHaveCount(0);
	});
});
