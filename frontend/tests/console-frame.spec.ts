import { expect, test } from './support/door-page';
import { cellFor, CELL_PX, GAP_PX } from '../src/lib/charts/run-history';
import { BAND_UNREAD } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-frame';
import { frame, labelsFromStyle, labelWidth, DEFAULT_CHART_LABELS } from '../src/lib/charts/frame';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { valueAxis } from '../src/lib/charts/d3/axis';
import { resolveConsoleStyle } from '../src/lib/console/console-style';
import { numberFormat } from './support/number-format';
import { distribution } from '../src/lib/charts/d3/distribution';

test('nondefault console type changes actual frame, date thinning and value-axis clearance', () => {
	const type = resolveConsoleStyle({ typography: { small: { size_rem: 1.125, leading_rem: 1.5 } } }).typography.small;
	const labels = labelsFromStyle(type, 20);
	expect(labels.fontSize).toBe(22.5);
	expect(labels.leading).toBe(30);
	const plain = frame(380, 240);
	const changed = frame(380, 240, undefined, labels);
	expect(plain.labels).toBe(DEFAULT_CHART_LABELS);
	expect(changed.left).toBeGreaterThan(plain.left);
	expect(changed.margin.bottom).toBeGreaterThan(plain.margin.bottom);
	const series = [{
		label: 'Measured', token: '--chart-1' as const,
		points: Array.from({ length: 14 }, (_, index) => ({ date: `2026-09-${String(index + 1).padStart(2, '0')}`, value: index }))
	}];
	const options = { density: 6, valueTicks: 8, padding: 0.2, number_format: numberFormat, rule: { changes: [], note: null } };
	const small = dateSeries(series, { ...options, frame: plain })!;
	const large = dateSeries(series, { ...options, frame: changed })!;
	expect(large.ticks.filter((tick) => tick.text)).toHaveLength(1);
	expect(small.ticks.filter((tick) => tick.text).length).toBeGreaterThan(1);
	expect(large.lines[0].points.map((point) => point.value)).toEqual(small.lines[0].points.map((point) => point.value));
	expect(labelWidth('20 Sep 2026', labels)).toBeGreaterThan(labelWidth('20 Sep 2026'));
	const upright = valueAxis([0, 100], changed, { along: 'y', ticks: 12, number_format: numberFormat });
	const kept = upright.ticks.filter((tick) => tick.text);
	for (let index = 1; index < kept.length; index += 1) {
		expect(Math.abs(kept[index].at - kept[index - 1].at)).toBeGreaterThanOrEqual(labels.leading + 8);
	}
});

test('a configured log axis keeps its bin edges but thins labels against measured type', () => {
	const labels = labelsFromStyle({ size_rem: 1.125, leading_rem: 1.5, tracking_em: 0 }, 20);
	const box = frame(380, 240, undefined, labels);
	const geometry = distribution([1, 10, 100, 1000, 10000, 100000, 1000000], {
		frame: box, minValues: 1, valueTicks: 6, scale: 'log', number_format: numberFormat
	})!;
	expect(geometry.x.ticks.map((tick) => tick.value)).toEqual([1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]);
	expect(geometry.x.ticks.filter((tick) => tick.text).length).toBeLessThan(geometry.x.ticks.length);
	expect(geometry.bins.reduce((count, bin) => count + bin.count, 0)).toBe(7);
	const kept = geometry.x.ticks.flatMap((tick, index, ticks) => {
		if (!tick.text) return [];
		const width = labelWidth(tick.text, labels);
		const left = index === 0 ? tick.at : index === ticks.length - 1 ? tick.at - width : tick.at - width / 2;
		return [{ left, right: left + width }];
	});
	for (let index = 1; index < kept.length; index += 1) {
		expect(kept[index].left - kept[index - 1].right).toBeGreaterThanOrEqual(8);
	}
});
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
