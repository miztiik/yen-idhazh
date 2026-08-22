import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Does on-device search actually work, or does it merely run?
 *
 * Without a labelled query set this row could only claim the latter, so the
 * labels are hand-written and committed. They name a canary rather than an item
 * id: ids shift the moment a canary is added, and a test that has to be
 * renumbered gets renumbered wrong.
 *
 * The bar is deliberately loose. A missed result costs a reader a convenience.
 * The tight bars belong on the canary suite, where a failure costs trust.
 */

const FIXTURES = resolve(process.cwd(), '..', 'tests', 'fixtures');

interface Gold {
	pass_bar: { minimum: number };
	queries: { query: string; expect_canary: string }[];
}

const gold: Gold = JSON.parse(readFileSync(resolve(FIXTURES, 'routing/search-gold.json'), 'utf8'));

/** The title the canary was published under, which is how a name finds its item. */
function titleOf(canary: string): string {
	for (const dir of ['canaries', 'canaries/browser']) {
		try {
			const raw = readFileSync(resolve(FIXTURES, dir, `${canary}.json`), 'utf8');
			return JSON.parse(raw).raw_title as string;
		} catch {
			continue;
		}
	}
	throw new Error(`no canary fixture named ${canary}`);
}

test('the retrieval bar, on hand-labelled queries', async ({ page }) => {
	await page.goto('/archive/');

	const offer = page.getByRole('button', { name: /Search this archive/ });
	await expect(offer, 'no day carries vectors - the payload lost its embeddings').toHaveCount(1);
	await offer.click();
	await page.waitForSelector('#assist-query', { timeout: 150_000 });

	const misses: string[] = [];
	for (const { query, expect_canary } of gold.queries) {
		await page.fill('#assist-query', query);
		await page.getByRole('button', { name: 'Search', exact: true }).click();
		await expect(page.locator('main ol li, main p:has-text("Nothing in the archive")')).not.toHaveCount(
			0
		);

		const top = (await page.locator('main ol li').allInnerTexts()).slice(0, 3).join(' | ');
		// The title is truncated in the fixture only by our own layout, so match
		// on its opening words rather than the whole string.
		const wanted = titleOf(expect_canary).replace(/<[^>]*>/g, '').split(' ').slice(0, 4).join(' ');
		if (!top.includes(wanted)) misses.push(`${query} -> wanted "${wanted}", got: ${top || '(none)'}`);
	}

	const recall = (gold.queries.length - misses.length) / gold.queries.length;
	console.log(`top-3 recall: ${recall.toFixed(2)} over ${gold.queries.length} labelled queries`);
	expect(recall, `misses:\n${misses.join('\n')}`).toBeGreaterThanOrEqual(gold.pass_bar.minimum);
});

test('a query with no answer says so rather than inventing one', async ({ page }) => {
	await page.goto('/archive/');
	await page.getByRole('button', { name: /Search this archive/ }).click();
	await page.waitForSelector('#assist-query', { timeout: 150_000 });

	await page.fill('#assist-query', 'medieval basket weaving techniques of rural Anatolia');
	await page.getByRole('button', { name: 'Search', exact: true }).click();
	await expect(page.getByText('Nothing in the archive is close to that.')).toBeVisible();
});

test('the digest is complete before search is ever offered', async ({ page }) => {
	// The rule the whole assist scope rests on: nothing on the reading path
	// waits for a model. If this fails, the feature is not secondary.
	const requests: string[] = [];
	page.on('request', (request) => requests.push(request.url()));
	await page.goto('/2026-08-20/', { waitUntil: 'networkidle' });

	await expect(page.locator('article').first()).toBeVisible();
	expect(requests.filter((url) => url.includes('/assist/'))).toEqual([]);
});
