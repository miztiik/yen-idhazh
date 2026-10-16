import { expect, test } from './support/door-page';
import { PAGES_CAP_BYTES, siteCost, publishingHorizon } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';
import { BAND_UNREAD } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-band';
/**
 * The band's remaining-room figure, and the unit it is allowed to be in.
 *
 * It used to be published days, and the number of articles it divided a day by
 * was `run.safety_ceiling_per_run` - which bounds one RUN, not one day. The
 * schedule fires up to five runs a day, so a day was priced at 160 articles
 * while the ten committed published days ran 4 to 731, median 334 (measured
 * 2026-08-31). The band printed 1,950 published days where the measured median
 * rate gives 934: too long by 2.09 times.
 *
 * The fix removes the assumption instead of correcting it. Headroom over the
 * per-article cost is a count of articles and needs no daily rate at all, so
 * there is nothing left in it for a run rate to be wrong about. The band's
 * producer works the figure out and the page prints its sentence word for word,
 * so the printed figure is held where it is computed:
 * `test_the_band_prints_the_articles_the_headroom_buys` in
 * `backend/tests/test_console_payloads_producer.py`, over manifests that test
 * writes. This file holds that no number of runs a day can move the answer, and
 * where the band sits on the page.
 *
 * `console-site-size.spec.ts` owns the per-article cost the runway divides by.
 */
function summary(date: string, siteBytes: number, runs: number): RunSummary {
    return { date, runs, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}
test('no rate of runs a day can move the answer', () => {
    // One site, described twice: four days at one run a day, and the same four
    // days at three. `run.safety_ceiling_per_run` is 80 and bounds a RUN, so a
    // formula built on it prices the second day at 240 articles and the first at
    // 80 - and its answer moves by three. This one may not move at all, because
    // the site did not change.
    const dates = ['2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04'];
    const bytes = [1000000, 1300000, 1600000, 1900000];
    const used = bytes[bytes.length - 1];
    const items = new Map(dates.map((date) => [date, 100]));
    const once = dates.map((date, i) => summary(date, bytes[i], 1));
    const thrice = dates.map((date, i) => summary(date, bytes[i], 3));
    const a = publishingHorizon(used, siteCost(once, items), items);
    const b = publishingHorizon(used, siteCost(thrice, items), items);
    expect(a).not.toBeNull();
    expect(a?.articles, 'the horizon moved when only the run count did').toBe(b?.articles);
    // 3,000 bytes an article, by construction, so the expected answer is a
    // division a reader can check.
    expect(Math.round(a?.articles ?? 0)).toBe(Math.round((PAGES_CAP_BYTES - used) / 3000));
    // And what a per-day answer would have done with the same two fixtures,
    // written out so the difference is on the page rather than asserted in the
    // abstract.
    const CEILING = 80;
    const daysAtCeiling = (runsADay: number) => (PAGES_CAP_BYTES - used) / (3000 * CEILING * runsADay);
    expect(daysAtCeiling(3)).toBeCloseTo(daysAtCeiling(1) / 3, 6);
});
for (const { id, href, label } of BAND_UNREAD.routes) {
    const expected = BY_ROUTE[id];
    if (expected === null)
        continue;
}
/** SvelteKit's own file for the route, holding what the three `+page.server.ts`
 * loads return. The router fetches it and AWAITS it before it runs a single
 * universal load, so while the console keeps a server load this one file is
 * ahead of the band and there is nothing the band can do about it. */
for (const { id, href } of BAND_UNREAD.routes) {
    const payload = BY_ROUTE[id]?.firstPayload;
    if (payload === null || payload === undefined)
        continue;
}
