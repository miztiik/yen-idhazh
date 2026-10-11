/** Pipelines draws only the windowed telemetry and refuses a too-narrow rule. */
import { expect, test } from './support/browser';
import { windowOfDays } from '../src/lib/charts/viewport';
import { failureSeries, timeSplit, type TelemetryRow } from '../src/lib/charts/series';
import { failureMix, failureMixColumns, timeSplitChart, timeSplitColumns } from '../src/lib/charts/glance';
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
        const series = failureSeries(rows, window);
        const mixStrip = failureMixColumns(series);
        expect(mixStrip.columns).toEqual(['13 Jun 2030', '14 Jun 2030', '15 Jun 2030']);
        expect(mixStrip.series.map((stage) => [stage.label, stage.values])).toEqual([
            ['fetch', ['1', null, '0']],
            ['extract', ['0', null, '0']],
            ['summarize', ['0', null, '0']]
        ]);
        expect(mixStrip.notMeasured).toBe('No item was planned on this day');
        const mixBars = failureMix(series).option.series as {
            name: string;
            data: (number | null)[];
        }[];
        expect(mixBars.map((bar) => [bar.name, bar.data])).toEqual([['fetch', [1, null, 0]]]);
        // Drawn as lines, the same array: the day with no row breaks the line.
        const mixLines = failureMix(series, 'lines').option.series as {
            data: (number | null)[];
        }[];
        expect(mixLines.map((line) => line.data)).toEqual([[1, null, 0]]);
        const days = timeSplit(rows, window);
        const splitStrip = timeSplitColumns(days);
        expect(splitStrip.series.map((band) => band.values)).toEqual([
            [null, null, '100 ms, 13%'],
            [null, null, '20 ms, 3%'],
            [null, null, '150 ms, 19%'],
            [null, null, '370 ms, 46%'],
            [null, null, '60 ms, 8%'],
            [null, null, '20 ms, 3%'],
            [null, null, '30 ms, 4%'],
            [null, null, '50 ms, 6%']
        ]);
        expect(splitStrip.notMeasured).toBe('No item was timed from start to finish on this day');
        const splitBars = timeSplitChart(days).option.series as {
            data: (number | null)[];
        }[];
        expect(splitBars.map((bar) => bar.data)).toEqual([
            [null, null, 100],
            [null, null, 20],
            [null, null, 150],
            [null, null, 370],
            [null, null, 60],
            [null, null, 20],
            [null, null, 30],
            [null, null, 50]
        ]);
    });
});
