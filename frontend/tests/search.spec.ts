import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { longDate } from '../src/lib/format';

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
 * What this file adds now that the box is a field rather than an offer: the one
 * gesture, the stop, the retry, and each model-state sentence a reader can
 * actually reach. The two files a month can still fail independently, so both
 * failures are driven here too. A missing index leaves the page browsing. A
 * missing vector file leaves the page browsing and search says so.
 */

const FIXTURES = resolve(process.cwd(), '..', 'tests', 'fixtures');
const VECTORS = /\/index\/\d{4}-\d{2}\.bin$/;
const MONTH = /\/index\/\d{4}-\d{2}\.json$/;
const WEIGHTS = /\/assist\/models\/.*\.onnx$/;

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

/** Every story in the one list, in the order it is rendered. */
async function titles(page: Page): Promise<string[]> {
	return page.locator('[data-story-list="rows"] li').allInnerTexts();
}

/** The one gesture: type the question, press the one button. */
async function ask(page: Page, query: string): Promise<void> {
	await page.fill('#archive-query', query);
	await page.getByRole('button', { name: 'Search', exact: true }).click();
}

/** Wait for the search to finish.
 *
 * The state sentence is the signal, because it is the same sentence a reader
 * watches. It says the download is done once, and only once, the encoder has
 * answered - so a test that waits on it is waiting on what the reader waits on.
 */
async function answered(page: Page): Promise<void> {
	await expect(page.locator('[data-search-state]')).toContainText('The download is done', {
		timeout: 180_000
	});
}

/** The newest day the canary build published, read off the day row. */
async function newestDay(page: Page): Promise<string> {
	const hrefs = await page
		.locator('[data-day-row] a')
		.evaluateAll((links) => links.map((link) => link.getAttribute('href') ?? ''));
	const dates = hrefs
		.map((href) => /(\d{4}-\d{2}-\d{2})/.exec(href)?.[1])
		.filter((date): date is string => date !== undefined)
		.sort();
	if (dates.length === 0) throw new Error(`no dates in the day row: ${hrefs.join(', ')}`);
	return dates[dates.length - 1]!;
}

/** The newest month the canary build published, read off the day row. */
async function newestMonth(page: Page): Promise<string> {
	const hrefs = await page.locator('[data-day-row] a').evaluateAll((links) =>
		links.map((link) => link.getAttribute('href') ?? '')
	);
	const months = hrefs
		.map((href) => /(\d{4}-\d{2})-\d{2}/.exec(href)?.[1])
		.filter((month): month is string => month !== undefined)
		.sort();
	if (months.length === 0) throw new Error(`no dates in the day row: ${hrefs.join(', ')}`);
	return months[months.length - 1]!;
}

test('one click downloads the encoder and answers the question already typed', async ({ page }) => {
	// The gesture this row exists to fix. There used to be a link that enabled a
	// search box, and then a box to type into. A reader wants an answer, not a
	// feature turned on, so the field is there before anything is downloaded and
	// one click pays for the encoder and runs what is already in it.
	await page.goto('/archive/');

	await expect(page.locator('#archive-query')).toBeVisible();
	await expect(page.locator('[data-search-state]')).toContainText('The first search downloads');
	await expect(page.locator('h2').first()).toHaveText('Stories');

	await ask(page, gold.queries[0]!.query);
	await answered(page);

	await expect(page.locator('h2').first()).toHaveText('Search results');
	expect((await titles(page)).length, 'the one click returned nothing').toBeGreaterThan(0);
	// Paid for, and the sentence says so rather than asking again.
	await expect(page.locator('[data-search-state]')).toContainText('The download is done');
});

test('the retrieval bar, on hand-labelled queries', async ({ page }) => {
	await page.goto('/archive/');

	const misses: string[] = [];
	for (const { query, expect_canary } of gold.queries) {
		await ask(page, query);
		await answered(page);

		const top = (await titles(page)).slice(0, 3).join(' | ');
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

test('the page says how far back it searched, before anything is downloaded', async ({ page }) => {
	// A reader who gets nothing back must be able to tell "never published" from
	// "outside what this read". The scope is a floor of days filled by whole month
	// shards, so it has to name days: a month name over a partial month promises
	// thirty days and holds one, which is the defect this replaced. And it has to
	// be there before they spend 43 MB finding out.
	await page.goto('/archive/');

	const scope = page.locator('[data-search-scope]');
	await expect(scope).toHaveText(/^Searching .+ - \d+ (story|stories)\.$/);
	// The newest day it can answer for is named in full, never rounded to a month.
	await expect(scope).toContainText(longDate(await newestDay(page)));
});

test('a result carries the summary from the day it names', async ({ page }) => {
	// The index carries no summary on purpose - it would be 6.35 times the entry.
	// The result fetches the day it names instead, and renders it through the
	// same component the digest uses, in the same list the browse rows used.
	await page.goto('/archive/');
	await ask(page, gold.queries[0]!.query);
	await answered(page);

	const first = page.locator('[data-story-list="rows"] li').first();
	await expect(first).toBeVisible();
	await expect(first.locator('article')).toBeVisible();
	await expect(first.locator('article h3')).not.toBeEmpty();
	// The day it was found on is on the item's own meta line, as the link back.
	await expect(first.locator('[data-item-day]')).toHaveAttribute(
		'href',
		/\/\d{4}-\d{2}-\d{2}\/#[a-z0-9-]+$/
	);
});

test('a result keeps the way out to the source', async ({ page }) => {
	// The day a result renders from is a projection now - `copy-visuals.mjs`
	// stages a named list of fields and drops the rest, which is how the second
	// copy of every day stopped costing what the day itself costs. A field taken
	// off that list disappears from every search result at once, renders as a
	// slightly shorter meta line, and fails nothing.
	//
	// `source_url` is the field where that would cost the most. It is the
	// reader's exit and their only means of checking what we wrote about a story
	// - the most important thing on a result after the summary. So it gets an
	// assertion of its own rather than sharing one with the summary above, and it
	// is checked against the staged file rather than against a shape: the bytes
	// on disk and the link on screen have to name the same address.
	await page.goto('/archive/');
	await ask(page, gold.queries[0]!.query);
	await answered(page);

	const first = page.locator('[data-story-list="rows"] li').first();
	const article = first.locator('article');
	await expect(article).toBeVisible();

	const itemId = await article.getAttribute('id');
	const back = await first.locator('[data-item-day]').getAttribute('href');
	const date = /(\d{4})-(\d{2})-(\d{2})/.exec(back ?? '');
	expect(date, `no date on the result's link back: ${back}`).not.toBeNull();

	const staged = JSON.parse(
		readFileSync(
			resolve(process.cwd(), 'static', 'digest', date![1]!, date![2]!, date![3]!, 'digest.json'),
			'utf8'
		)
	) as { items: { item_id: string; source_name: string; source_url: string }[] };
	const item = staged.items.find((one) => one.item_id === itemId);
	expect(item, `${itemId} is not in the staged day the result names`).toBeDefined();

	const out = first.getByRole('link', { name: 'Read the original' });
	await expect(out, 'a search result offers no link to its source').toHaveCount(1);
	// A dropped field leaves `href` unset rather than wrong, so the attribute is
	// what bites - the link text survives either way.
	await expect(out).toHaveAttribute('href', item!.source_url);
	// Who said it, on the same line. The summary is only worth as much as this.
	await expect(article, 'the result names no source').toContainText(item!.source_name);
});


test('a search replaces the one story list, and a link gives it back', async ({ page }) => {
	// One list, not two. Two lists side by side leave a reader working out which
	// one answered them.
	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	const browsed = await titles(page);

	await ask(page, gold.queries[0]!.query);
	await answered(page);

	const found = await titles(page);
	expect(found, 'the search did not replace the list').not.toEqual(browsed);
	await expect(page.locator('[data-story-more]'), 'paging is not a search control').toHaveCount(0);

	await page.locator('[data-search-clear]').click();
	await expect(page.locator('h2').first()).toHaveText('Stories');
	expect(await titles(page)).toEqual(browsed);
});

test('a query with no answer leaves the story list where it was', async ({ page }) => {
	// The zero case is the whole disclosure: nothing weak is shown, no score is
	// printed, and the browse list is the empty state.
	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	const browsed = await titles(page);

	await ask(page, 'medieval basket weaving techniques of rural Anatolia');
	await answered(page);

	const empty = page.locator('[data-search-empty]');
	await expect(empty).toHaveText(/^No story from .+ is close to that\.$/);
	// The same days the line under the box named, so a miss is answerable.
	await expect(empty).toContainText(longDate(await newestDay(page)));
	await expect(page.locator('h2').first()).toHaveText('Stories');
	expect(await titles(page)).toEqual(browsed);
});

test('the count is stated over the stories searched, and says when the cap bit', async ({
	page,
	request
}) => {
	// The canary month holds eight searchable stories and the limit is ten, so
	// the cap can never bite on the real index and a test against it would assert
	// a branch nobody reaches. Tile the real entries instead - the same byte
	// offsets into the same real vector file, under new ids - so there are more
	// close stories than the limit allows.
	await page.goto('/archive/');
	const month = await newestMonth(page);
	const real = await (await request.get(`/index/${month}.json`)).json();
	expect(real.entries.length, `the ${month} index carries no stories`).toBeGreaterThan(0);
	const entries = Array.from({ length: 80 }, (_, at) => ({
		...real.entries[at % real.entries.length],
		item_id: `tiled-${at}`
	}));
	await page.route(MONTH, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({ ...real, entries })
		})
	);

	await page.goto('/archive/');
	await ask(page, gold.queries[0]!.query);
	await answered(page);

	await expect(page.locator('[data-story-scope]')).toHaveText(
		/^\d+ results from the 80 stories searched\. Only the closest \d+ are shown\.$/
	);
});

test('a stop leaves the page exactly as it was', async ({ page }) => {
	// Cancelling costs a reader nothing. The list stays live, nothing greys out,
	// and the offer comes back exactly as it was.
	await page.route(WEIGHTS, async (route) => {
		await new Promise((wake) => setTimeout(wake, 5_000));
		await route.continue();
	});
	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	const browsed = await titles(page);

	await ask(page, gold.queries[0]!.query);
	await page.locator('[data-search-stop]').click();

	await expect(page.locator('[data-search-stop]')).toHaveCount(0);
	await expect(page.locator('[data-search-state]')).toContainText('The first search downloads');
	await expect(page.locator('h2').first()).toHaveText('Stories');
	await expect(page.locator('#archive-query')).toBeEnabled();
	expect(await titles(page)).toEqual(browsed);
});

test('a failed download offers a way to try again', async ({ page }) => {
	// One flaky connection must not turn the feature off for the rest of the
	// page's life. This is the dead end that used to be permanent.
	await page.route(WEIGHTS, (route) => route.fulfill({ status: 500, body: 'no' }));
	await page.goto('/archive/');

	await ask(page, gold.queries[0]!.query);
	await expect(page.locator('[data-search-state]')).toContainText(
		'the download did not finish',
		{ timeout: 120_000 }
	);

	await page.unroute(WEIGHTS);
	await page.locator('[data-search-retry]').click();
	await expect(page.locator('[data-search-stop]'), 'the retry did not restart it').toBeVisible();
});

test('the page still browses when the vectors are gone', async ({ page }) => {
	// The two files a month can fail on their own. Losing the vectors costs
	// search and nothing else - the list is built off the JSON, and it is the
	// half a reader came for. The check runs before the 43 MB, not after it.
	const errors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});

	await page.route(VECTORS, (route) => route.fulfill({ status: 404, body: 'not found' }));
	await page.goto('/archive/');

	await ask(page, gold.queries[0]!.query);
	await expect(page.locator('[data-search-state]')).toContainText(
		'these stories cannot be searched on this device'
	);
	await expect(page.locator('#archive-query')).toHaveCount(0);

	// The stories are still there, and so are the days.
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect(await page.locator('[data-day-row] a').count()).toBeGreaterThan(1);

	const ours = errors.filter((text) => !text.includes('Failed to load resource'));
	expect(ours, 'a missing vector file must degrade, not error').toEqual([]);
});

test('a browser that cannot run the encoder says so, and offers no box', async ({ page }) => {
	// A field that can never answer is worse than no field.
	await page.addInitScript(() => {
		Object.defineProperty(window, 'Worker', { value: undefined, configurable: true });
	});
	await page.goto('/archive/');

	await expect(page.locator('[data-search-state]')).toHaveText(
		'Search is unavailable here - this browser cannot run it. Everything above still works.'
	);
	await expect(page.locator('#archive-query')).toHaveCount(0);
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
});

test('an encoder left from an earlier visit is named as a second download', async ({ page }) => {
	// The weights carry the date they were fetched in their own path, so a reader
	// holding last month's copy pays the whole download again. That is a fact
	// they cannot guess, so it gets its own sentence.
	await page.goto('/archive/');
	await page.evaluate(async () => {
		const cache = await caches.open('transformers-cache');
		await cache.put(
			'/assist/models/all-minilm-l6-v2-quantized/1999-01-01/onnx/model_quantized.onnx',
			new Response('an encoder from a previous visit')
		);
	});
	await page.reload();

	await expect(page.locator('[data-search-state]')).toContainText(
		'The search files changed since your last visit.'
	);
	await expect(page.locator('#archive-query')).toBeVisible();
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
