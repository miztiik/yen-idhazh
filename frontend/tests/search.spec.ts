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
 * One labelled query is checked here, to prove the browser ranks rather than
 * merely returns. Recall over the labelled set is an evaluation, and its
 * instrument is `backend/idhazh/evals/retrieval.py`, which runs the same ranking
 * over sixty labelled queries with no browser and no download.
 *
 * Keep one real encoder-backed query and one failed-download recovery case.
 * Do not expand either into model-state, query-corpus or presentation matrices.
 */
const FIXTURES = resolve(process.cwd(), '..', 'tests', 'fixtures');
const WEIGHTS = /\/assist\/models\/.*\.onnx$/;
/** The other file the encoder needs, which the library asks for at the same time. */
const TOKENIZER = /\/assist\/models\/.*\/tokenizer\.json$/;
interface Gold {
    queries: {
        query: string;
        expect_canary: string;
    }[];
}
const gold: Gold = JSON.parse(readFileSync(resolve(FIXTURES, 'routing/search-gold.json'), 'utf8'));
/** The title the canary was published under, which is how a name finds its item. */
function titleOf(canary: string): string {
    for (const dir of ['canaries', 'canaries/browser']) {
        try {
            const raw = readFileSync(resolve(FIXTURES, dir, `${canary}.json`), 'utf8');
            return JSON.parse(raw).raw_title as string;
        }
        catch {
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
        timeout: 180000
    });
}
test('one click downloads the encoder and answers the question already typed', async ({ page }) => {
    // The gesture this row exists to fix. There used to be a link that enabled a
    // search box, and then a box to type into. A reader wants an answer, not a
    // feature turned on, so the field is there before anything is downloaded and
    // one click pays for the encoder and runs what is already in it.
    await page.goto('/archive/');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#archive-query')).toBeVisible();
    await expect(page.locator('[data-search-state]')).toContainText('The first search downloads');
    await expect(page.locator('h2').first()).toHaveText('Stories');
    const { query, expect_canary } = gold.queries[0]!;
    await ask(page, query);
    await answered(page);
    await expect(page.locator('h2').first()).toHaveText('Search results');
    // One labelled query proves the browser ranks, not merely returns. Recall
    // over the whole labelled set is an evaluation, and `evals/retrieval.py`
    // measures it with no browser and no download.
    const top = (await titles(page)).slice(0, 3).join(' | ');
    // The title is truncated in the fixture only by our own layout, so match on
    // its opening words rather than the whole string.
    const wanted = titleOf(expect_canary).replace(/<[^>]*>/g, '').split(' ').slice(0, 4).join(' ');
    expect(top, `${query} -> wanted "${wanted}" in the top three`).toContain(wanted);
    // Paid for, and the sentence says so rather than asking again.
    await expect(page.locator('[data-search-state]')).toContainText('The download is done');
});
test('a failed download offers a way to try again', async ({ page }) => {
    // One flaky connection must not turn the feature off for the rest of the
    // page's life. This is the dead end that used to be permanent.
    //
    // The library asks for the tokenizer and the weights at the same time, so
    // failing only the weights leaves a file still on its way. Holding that file
    // back puts it on the far side of the failure, which is the order a loaded
    // runner reaches on its own: its progress report used to revive the download
    // the reader had just been told did not finish, and take the retry away with
    // it for good. Left to chance that order turned this test red in three of the
    // four CI runs observed on 2026-08-27, `main`'s own commit among them.
    await page.route(WEIGHTS, (route) => route.fulfill({ status: 500, body: 'no' }));
    await page.route(TOKENIZER, async (route) => {
        await new Promise((wake) => setTimeout(wake, 5000));
        await route.continue();
    });
    await page.goto('/archive/');
    const state = page.locator('[data-search-state]');
    await ask(page, gold.queries[0]!.query);
    await expect(state).toContainText('the download did not finish', { timeout: 120000 });
    // The held file lands in here, and the failure has to still be what a reader
    // is looking at once it has.
    await page.waitForLoadState('networkidle');
    await expect(state, 'a file arriving late revived the failed download').toContainText('the download did not finish');
    await expect(page.locator('[data-search-retry]'), 'the way back went away on its own').toHaveCount(1);
    await page.unroute(WEIGHTS);
    await page.unroute(TOKENIZER);
    await page.locator('[data-search-retry]').click();
    await expect(page.locator('[data-search-stop]'), 'the retry did not restart it').toBeVisible();
});
