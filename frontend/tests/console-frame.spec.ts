import { expect, test } from './support/door-page';
import { cellFor, CELL_PX, GAP_PX } from '../src/lib/charts/run-history';
import { BAND_UNREAD } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-frame';
test.describe('the run strip uses the room it has', () => {
    test('an unmeasured strip still draws at the fixed pair', () => {
        // The server has no width. Deriving a cell from null must not yield zero,
        // or the prerendered strip is invisible until JavaScript runs.
        const metrics = cellFor(null, 30);
        expect(metrics.cell).toBe(CELL_PX);
        expect(metrics.gap).toBe(GAP_PX);
    });
    test('a wide frame grows the day column, up to a limit', () => {
        const narrow = cellFor(400, 30);
        const wide = cellFor(1400, 30);
        expect(wide.cell).toBeGreaterThan(narrow.cell);
        // Past a point a sequence stops reading as a sequence and starts reading
        // as a row of tiles, so the growth is bounded.
        expect(cellFor(9000, 4).cell).toBeLessThanOrEqual(34);
    });
    test('a crowded strip holds the pair it has always used, and scrolls instead', () => {
        // It grows into room and never shrinks out of it. Shrinking would let a
        // wide window quietly change what a phone does: there the strip scrolls
        // and opens on the newest run, which is a behaviour rather than a side
        // effect of the cell happening to be 16.
        const metrics = cellFor(300, 90);
        expect(metrics.cell).toBe(CELL_PX);
        expect(metrics.gap).toBe(GAP_PX);
    });
    test('the gap keeps its share, so the rhythm survives the resize', () => {
        // Two days apart must measure twice one day apart at every size, which is
        // only true if the gap scales with the cell rather than staying put.
        for (const width of [400, 800, 1400]) {
            const m = cellFor(width, 30);
            expect(m.gap / m.cell).toBeCloseTo(GAP_PX / CELL_PX, 1);
        }
    });
});
for (const { id, href: route, label } of BAND_UNREAD.routes) {
    const expected = BY_ROUTE[id];
    if (expected === null)
        continue;
    /**
     * The console as a browser lays it out before any of its JavaScript has run.
     *
     * `chartWidth` returns the `console.chart_width` fallback until `observeWidth`
     * reports, so every prerendered chart is 760px wide in the HTML that arrives
     * first. A chart that does not cap that at its container IS the document's
     * width until the page hydrates - 800px inside a 360px phone. Ten chart SVGs
     * carry `max-w-full` or `w-full` by hand and one shipped without it, which is
     * a convention no gate could see.
     *
     * Scripts off rather than a timed sample. The overflow lasts until hydration,
     * so a sample races it and reports a layout fact as a flake - which is exactly
     * how this arrived, as one red `layout-overflow.spec.ts` in a job whose other
     * theme passed.
     */
    if (expected.prerender) {
    }
}
