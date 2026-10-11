import { expect, test } from './support/door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { BAND_UNREAD, readBand, stripRoutes, type RouteId } from '../src/lib/console/band';
import { uiConfig } from '../src/lib/server/config';
import { BY_ROUTE } from './support/console-expect/console-nav';
/**
 * The console is six routes, and this file is why it is routes and not tabs.
 * Data explorer is live and is answered by the fallback document because it fetches
 * all data after JavaScript starts.
 *
 * A tab strip that switches with script fails every assertion here: with
 * JavaScript off it shows one panel set and no way to reach the others, and
 * every panel it hides still ships inside the one document. Five prerendered
 * routes with real anchors pass.
 *
 * Five things this file protects that a screenshot cannot. The labels are the
 * words the owner chose, so a paraphrase fails. The ids and the paths under
 * them did NOT move when two of the labels changed on 2026-08-31, which is what
 * makes that a rename and not a route change. The strip may never take the
 * health ramp: green, amber and red on a label would say a route is failing,
 * and a route is a noun. Since 2026-09-12 the strip has to FIT - six tabs
 * on one row at 1440 and no more than three at 360 and 320, with no box
 * overlapping another. And each route's title in the browser names that route,
 * after a tab click as well as on a page load.
 */
/** The owner's words, and the paths they sit on. Typed out on purpose: this is
 * the copy the file exists to protect, so reading it from the source it guards
 * would only prove the page agrees with itself.
 *
 * `Model` became `Summaries` and `Machine` became `Hardware` on 2026-08-31.
 * Every panel on the middle route is about a published summary and none is
 * about the model as an artefact; `Hardware` is the plainest word for a
 * processor, a memory and a clock, and unlike `Runner` it is not a term the
 * build system uses on itself (CLAUDE.md section 0b).
 *
 * `Judgement` and `Voices` joined on 2026-09-12, opened empty by the row that
 * added them; `Voices` filled on 2026-09-14 when four feed and source panels
 * moved onto it off Pipelines. `Judgement` is singular because the other three
 * name a place and this one names an act; `Voices` is the owner's word over
 * Susan's `Sources`.
 */
const ROUTES = BAND_UNREAD.routes.flatMap((route) => {
    const expected = BY_ROUTE[route.id];
    return expected === null ? [] : [{ ...expected, href: route.href }];
});
const FALLBACK_ROUTES = ROUTES.filter((route) => route.fallbackDescription !== null);
/** Each route's page title, in Reader's words: the label on its tab, then
 * `Console`. The site's own title follows, read from the config the build reads,
 * because it is not this file's copy to protect.
 *
 * Typed out on purpose, like the labels above: read from the pages it guards, it
 * would only prove a page agrees with itself. Every route sets its own, because a
 * tab click moves inside the page, and a route that sets no title keeps the one
 * the route before it set.
 */
/** The whole title a route owes: its own words, then the site's title. */
function titleOf(id: RouteId): string {
    return `${BY_ROUTE[id]!.title} \u2014 ${uiConfig().site_title}`;
}
test.describe('the title names the route on screen', () => {
    test('no two routes share a title', () => {
        // Each route's test above holds its page to its own entry here, so entries
        // that differ are titles that differ on screen.
        const titles = ROUTES.map((route) => titleOf(route.id));
        expect(new Set(titles).size, `two routes share a title: ${titles.join(' | ')}`).toBe(ROUTES.length);
    });
});
/** A band written before Data explorer existed still reads, and the fallback fills the route. */
const OLD_BAND = resolve(process.cwd(), '..', 'tests', 'fixtures', 'contracts', 'console-band', 'newest-day.json');
test.describe('old bands still draw every route', () => {
    for (const DATA_EXPLORER of FALLBACK_ROUTES) {
        test('the strip draws Data explorer from the fallback words', () => {
            const payload = JSON.parse(readFileSync(OLD_BAND, 'utf8')) as {
                routes: {
                    id: string;
                }[];
            };
            expect(payload.routes.map((route) => route.id)).not.toContain('data-explorer');
            const band = readBand(payload);
            expect(band.read, 'an old band no longer reads').toBe(true);
            const drawn = stripRoutes(band.routes);
            expect(drawn.map((route) => route.id)).toEqual(ROUTES.map((entry) => entry.id));
            expect(drawn.at(-1)).toMatchObject({
                id: DATA_EXPLORER.id,
                label: DATA_EXPLORER.label,
                href: DATA_EXPLORER.path,
                description: DATA_EXPLORER.fallbackDescription,
                worst: null
            });
        });
    }
});
