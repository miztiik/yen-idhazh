/** Pipelines draws only the windowed telemetry and refuses a too-narrow rule. */
import { expect, test } from './support/browser';
import { windowOfDays } from '../src/lib/charts/viewport';
import type { TelemetryRow } from '../src/lib/charts/series';
import { daysInWindow } from '../src/lib/charts/viewport';
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { nativeTimeSplit, timeSplitReadout } from '../src/lib/console/pipelines/item-time-split';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { frame } from '../src/lib/charts/frame';
import { telemetryRow } from './support/telemetry-row';
import { JUDGED_THROUGH } from './support/console-window/judgement-fixtures';
/** An item that published, timed from start to finish: 800 ms in all. */
function timedItem(date: string, item: string): TelemetryRow {
    return telemetryRow({
        date,
        run_id: `${date}-1`,
        item_id: item,
        fetch_ms: 100,
        extract_ms: 20,
        summarize_ms: 600,
        label_ms: 150,
        summary_ms: 430,
        visual_plan_ms: 60,
        faithfulness_ms: 30,
        item_total_ms: 800,
        stage_gap_ms: 50
    });
}
/** An item that stopped at a stage, with no clock of its own. */
function failedItem(date: string, item: string, stage: 'fetch' | 'extract'): TelemetryRow {
    return telemetryRow({
        date,
        run_id: `${date}-1`,
        item_id: item,
        stage,
        outcome: 'failed',
        code: 'timeout'
    });
}
test.describe("Pipelines' failure mix and time split draw the window's days, on telemetry the test builds", () => {
    test("a day with no row draws no column, and its strip says so, while a day that ran clean is a real zero", () => {
        // Three days ending on the pinned day: an item failed at fetch on the first,
        // nothing ran on the second, and the third timed one item and failed none.
        const window = windowOfDays(JUDGED_THROUGH, 3, 'right');
        const rows = [failedItem('2030-06-13', 'a', 'fetch'), timedItem('2030-06-15', 'b')];
        const calendar = daysInWindow(window);
        const mix = nativeFailureMix(rows.map((row) => ({ ...row })), calendar);
        expect(mix.series.map((stage) => [stage.label, stage.points.map((point) => point.value)])).toEqual([
            ['Fetch', [1, null, 0]], ['Extract', [0, null, 0]], ['Summarize', [0, null, 0]]
        ]);
        const options = { frame: frame(760, 220), density: 6, valueTicks: 5, padding: 0.2, rule: { changes: [], note: null } };
        const bars = dateSeries(mix.series, { ...options, stacked: true })!;
        const lines = dateSeries(mix.series, options)!;
        expect(bars.dates).toEqual(['2030-06-13', '2030-06-14', '2030-06-15']);
        expect(bars.bars.map((bar) => [bar.date, bar.label, bar.value])).toEqual([['2030-06-13', 'Fetch', 1]]);
        expect(lines.lines[0].points.map((point) => [point.date, point.value, point.alone])).toEqual([
            ['2030-06-13', 1, true], ['2030-06-15', 0, true]
        ]);
        const split = nativeTimeSplit(rows.map((row) => ({ ...row })), calendar);
        const strip = timeSplitReadout(split);
        expect(split.series.map((band) => band.points.map((point) => point.value))).toEqual(
            [100, 20, 600, 30, 50].map((value) => [null, null, value]));
        expect(strip.series.slice(0, 7).map((band) => band.values)).toEqual(
            ['0.10 s', '0.02 s', '0.60 s', '0.03 s', '0.05 s', '0.80 s', '0.00 s'].map((value) => [null, null, value]));
        expect(strip.notMeasured).toBe('Not measured for the complete cohort');
    });
});
