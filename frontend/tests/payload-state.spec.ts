import { expect, test, type Page } from '@playwright/test';
import { Intercepted, loaderSource, servedDayUrl, type Loader } from './support/day-loader';
const DATE = '2026-08-30';
/** What the loader must ask for, spelled out rather than rebuilt from `dayUrl`. */
const WANTED = servedDayUrl(DATE);
const PATTERN = `**${WANTED}`;
/** The content revision a served day carries. Its own `generated_at`, which is
 * what a republish moves and nothing else does. */
const REVISION = '2026-08-30T06:00';
/** A day payload holding stories the page can actually render.
 *
 * Four names, because the loader keeps a story only when it carries everything
 * the page reads off it without a guard - a story short of one of them is
 * dropped and counted, which `malformed-day.spec.ts` is the case for.
 */
function dayBody(revision: string, ids: string[]): string {
    return JSON.stringify({
        version: '2026-09-01T09:00',
        generated_at: revision,
        items: ids.map((id) => ({
            item_id: id,
            title: 'A story',
            summary: 'A summary long enough to be a summary.'
        }))
    });
}
const LOADER = loaderSource('payload-state');
const primed = new WeakSet<Page>();
/** The loader, live in a page of the real built site.
 *
 * Every navigation re-runs the injected script, so the module's held days start
 * empty on each `goto` - which is what lets one test drive a fresh fetch twice.
 *
 * **`/archive/` rather than `/`, and the page has to be one that fetches no day
 * and stays put.** `/` carried its whole day inline until 2026-09-10 and fetches
 * the rest now, so opening it puts one interception and one held day into every
 * case here - which reads as the loader asking for a date it should have refused,
 * and as a session holding a day it never visited. `/archive/` is prerendered,
 * asks for no digest until a reader opens a search result, and does not move.
 */
async function armed(page: Page): Promise<void> {
    if (!primed.has(page)) {
        await page.addInitScript({ content: await LOADER });
        primed.add(page);
    }
    await page.goto('/archive/');
}
interface Watched {
    states: string[];
    items: number | null;
}
/** One `watchDay` call, with every state it reported, in order. */
async function watch(page: Page, slowMs: number, again = false): Promise<Watched> {
    return page.evaluate(async ([date, ms, retry]: [
        string,
        number,
        boolean
    ]) => {
        const loader = (window as unknown as {
            dayLoader: Loader;
        }).dayLoader;
        const states: string[] = [];
        const day = await loader.watchDay(date, {
            slowMs: ms,
            again: retry,
            onStatus: (status: string) => states.push(status)
        });
        return { states, items: day === null ? null : day.items.length };
    }, [DATE, slowMs, again] as [
        string,
        number,
        boolean
    ]);
}
/** One `loadDay` call - the archive's own, with no wait states and no retry
 * control. It returns the story count, or null for a day it could not read. */
async function load(page: Page, date: string = DATE): Promise<number | null> {
    return page.evaluate(async (asked: string) => {
        const loader = (window as unknown as {
            dayLoader: Loader;
        }).dayLoader;
        const day = await loader.loadDay(asked);
        return day === null ? null : day.items.length;
    }, date);
}
test.describe('what one session keeps in hand', () => {
    test('a day that failed once is asked for again, and it recovers', async ({ page }) => {
        // The oracle. A search answer names a day, that day's fetch fails, and the
        // next answer naming it has no retry control to press - so if the failure
        // is held, that day is finished for the life of the session.
        const asked = new Intercepted();
        let refuse = true;
        await page.route(PATTERN, async (route) => {
            asked.take(route.request().url());
            if (refuse) {
                await route.abort('connectionfailed');
                return;
            }
            await route.fulfill({ contentType: 'application/json', body: dayBody(REVISION, ['ai-1']) });
        });
        await armed(page);
        expect(await load(page), 'the first ask did not fail').toBeNull();
        // The network recovers, and nothing tells the loader.
        refuse = false;
        const recovered = await load(page);
        console.log(`[payload-state] recovery interceptions: ${asked.count}`);
        expect(recovered, 'a day that failed once stayed failed for the session').toBe(1);
        expect(asked.count, 'the second ask never reached the network').toBe(2);
        // The reader's own route reaches the same rule through `watchDay`.
        refuse = true;
        const readerFailed = await watch(page, 30000, true);
        expect(readerFailed.states).toEqual(['loading', 'unreachable']);
        refuse = false;
        const readerRecovered = await watch(page, 30000);
        expect(readerRecovered.states, 'the reading page could not recover either').toEqual([
            'loading',
            'ready'
        ]);
    });
});
