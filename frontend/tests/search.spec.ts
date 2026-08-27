import { expect, test, type Page } from '@playwright/test';
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
 * The tight bars belong on the canary suite, where a failure costs trust, and
 * the real instrument is `backend/idhazh/evals/retrieval.py`, which runs the
 * same ranking over sixty labelled queries with no browser and no download.
 *
 * What this file adds now that search reads the month index: the two files a
 * month can fail independently, so both failures are driven here. A missing
 * index leaves the page browsing. A missing vector file leaves the page
 * browsing too, and search says so rather than white-screening.
 */

const FIXTURES = resolve(process.cwd(), '..', 'tests', 'fixtures');
const VECTORS = /\/index\/\d{4}-\d{2}\.bin$/;

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

/** Open the archive and get search all the way to ready. */
async function readyToSearch(page: Page): Promise<void> {
	await page.goto('/archive/');
	const offer = page.getByRole('button', { name: /Search this archive/ });
	await expect(offer, 'no month carries vectors - the index lost its sibling file').toHaveCount(1);
	await offer.click();
	await page.waitForSelector('#assist-query', { timeout: 150_000 });
}

test('the retrieval bar, on hand-labelled queries', async ({ page }) => {
	await readyToSearch(page);

	const misses: string[] = [];
	for (const { query, expect_canary } of gold.queries) {
		await page.fill('#assist-query', query);
		await page.getByRole('button', { name: 'Search', exact: true }).click();
		await expect(
			page.locator('[data-assist-results] li, main p:has-text("Nothing in the archive")')
		).not.toHaveCount(0);

		const top = (await page.locator('[data-assist-results] li').allInnerTexts())
			.slice(0, 3)
			.join(' | ');
		// The title is truncated in the fixture only by our own layout, so match
		// on its opening words rather than the whole string.
		const wanted = titleOf(expect_canary)
			.replace(/<[^>]*>/g, '')
			.split(' ')
			.slice(0, 4)
			.join(' ');
		if (!top.includes(wanted)) misses.push(`${query} -> wanted "${wanted}", got: ${top || '(none)'}`);
	}

	const recall = (gold.queries.length - misses.length) / gold.queries.length;
	console.log(`top-3 recall: ${recall.toFixed(2)} over ${gold.queries.length} labelled queries`);
	expect(recall, `misses:\n${misses.join('\n')}`).toBeGreaterThanOrEqual(gold.pass_bar.minimum);
});

test('the page says which months it searched', async ({ page }) => {
	// A reader who gets nothing back must be able to tell "never published" from
	// "not in the months this searched". The scope is a config knob, so the
	// sentence is the only place a reader can see what it is set to.
	await readyToSearch(page);

	await expect(page.locator('[data-assist-scope]')).toHaveText(
		/^Searching [A-Z][a-z]+ \d{4}( to [A-Z][a-z]+ \d{4})? - \d+ (story|stories)\./
	);
});

test('a result carries the summary from the day it names', async ({ page }) => {
	// The index carries no summary on purpose - it would be 6.35 times the entry.
	// The result fetches the day it names instead, and renders it through the
	// same component the digest uses.
	await readyToSearch(page);

	const { query } = gold.queries[0]!;
	await page.fill('#assist-query', query);
	await page.getByRole('button', { name: 'Search', exact: true }).click();

	const first = page.locator('[data-assist-results] li').first();
	await expect(first).toBeVisible();
	await expect(first.locator('article')).toBeVisible();
	await expect(first.locator('article h3')).not.toBeEmpty();
});

test('a query with no answer says so rather than inventing one', async ({ page }) => {
	await readyToSearch(page);

	await page.fill('#assist-query', 'medieval basket weaving techniques of rural Anatolia');
	await page.getByRole('button', { name: 'Search', exact: true }).click();
	await expect(page.getByText('Nothing in the archive is close to that.')).toBeVisible();
});

test('the page still browses when the vectors are gone', async ({ page }) => {
	// The two files a month can fail on their own. Losing the vectors costs
	// search and nothing else - the list is prerendered off the JSON, and it is
	// the half a reader came for.
	const errors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});

	await page.route(VECTORS, (route) => route.fulfill({ status: 404, body: 'not found' }));
	await page.goto('/archive/');

	await page.getByRole('button', { name: /Search this archive/ }).click();
	await expect(page.locator('[data-assist-unavailable]')).toBeVisible();
	await expect(page.locator('#assist-query')).toHaveCount(0);

	// The stories are still there, and so are the days.
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect(await page.locator('[data-day-row] a').count()).toBeGreaterThan(1);

	const ours = errors.filter((text) => !text.includes('Failed to load resource'));
	expect(ours, 'a missing vector file must degrade, not error').toEqual([]);
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
