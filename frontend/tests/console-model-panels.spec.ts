/** Deterministic model panels rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { scoreCost, writeTimes, type DayWindow } from '../src/lib/server/model-work';
const WEEK: DayWindow = { start: '2026-08-15', end: '2026-08-21', days: 7 };
function timed(date: string, ms: number): Record<string, string> {
    return { date, summarize_ms: String(ms) };
}
test.describe('what one summary cost, as a distribution', () => {
    test('the bars double, the first one holds everything under a second', () => {
        const times = writeTimes([
            timed('2026-08-20', 300),
            timed('2026-08-20', 20000),
            timed('2026-08-21', 40000),
            timed('2026-08-21', 40000),
            timed('2026-08-21', 100000)
        ], WEEK);
        expect(times, 'a window with five timed articles drew nothing').not.toBeNull();
        const bins = (times as NonNullable<typeof times>).bins;
        expect(bins[0].from).toBe(0);
        expect(bins[0].to).toBe(1);
        for (let index = 1; index < bins.length; index += 1) {
            expect(bins[index].from).toBe(bins[index - 1].to);
            expect(bins[index].to).toBe(bins[index].from * 2);
        }
        expect(bins.reduce((total, bin) => total + bin.n, 0)).toBe(5);
        expect((times as NonNullable<typeof times>).n).toBe(5);
        expect(bins[0].n).toBeGreaterThan(0);
        expect(bins[bins.length - 1].n).toBeGreaterThan(0);
        expect(bins.some((bin) => bin.n === 0), 'the empty span between the two ends was dropped').toBe(true);
        const through = bins.map((bin) => bin.throughPct);
        expect(through).toEqual([...through].sort((a, b) => a - b));
        expect(through[through.length - 1]).toBe(100);
    });
    test('the two rules are taken over the values, never off a bar', () => {
        const times = writeTimes([10000, 20000, 30000, 40000, 200000].map((ms) => timed('2026-08-20', ms)), WEEK) as NonNullable<ReturnType<typeof writeTimes>>;
        expect(times.median).toBe(30000);
        expect(times.p95).toBeCloseTo(168000, 6);
        expect(times.fastest).toBe(10000);
        expect(times.slowest).toBe(200000);
    });
    test('a window is a filter on the rows and a day outside it is not counted', () => {
        const rows = [timed('2026-08-14', 5000), timed('2026-08-20', 5000)];
        expect((writeTimes(rows, WEEK) as NonNullable<ReturnType<typeof writeTimes>>).n).toBe(1);
        expect((writeTimes(rows, { start: '2026-08-08', end: '2026-08-21', days: 14 }) as NonNullable<ReturnType<typeof writeTimes>>).n).toBe(2);
    });
    test('a window nothing was timed in draws nothing, and that is not a zero', () => {
        expect(writeTimes([], WEEK)).toBeNull();
        expect(writeTimes([{ date: '2026-08-20' }], WEEK)).toBeNull();
        expect(writeTimes([timed('2026-08-20', 0)], WEEK)).toBeNull();
    });
});
test.describe('what checking a summary cost, off the critical path', () => {
    function scored(date: string, ms: string): Record<string, string> {
        return { date, score_ms: ms };
    }
    test('a zero is a row nothing timed, and it is counted as that', () => {
        const cost = scoreCost([scored('2026-08-20', '1000'), scored('2026-08-20', '3000'), scored('2026-08-20', '0')], WEEK) as NonNullable<ReturnType<typeof scoreCost>>;
        expect(cost.n).toBe(2);
        expect(cost.untimed).toBe(1);
        expect(cost.median).toBe(2000);
    });
    test('nothing timed at all draws nothing', () => {
        expect(scoreCost([scored('2026-08-20', '0')], WEEK)).toBeNull();
        expect(scoreCost([], WEEK)).toBeNull();
    });
    test('the checker gets the same binning the model does, over its own clock', () => {
        const cost = scoreCost([300, 1500, 3000, 3000, 9000].map((ms) => scored('2026-08-20', String(ms))), WEEK) as NonNullable<ReturnType<typeof scoreCost>>;
        expect(cost.bins[0].from).toBe(0);
        expect(cost.bins[0].to).toBe(1);
        for (let index = 1; index < cost.bins.length; index += 1) {
            expect(cost.bins[index].from).toBe(cost.bins[index - 1].to);
            expect(cost.bins[index].to).toBe(cost.bins[index].from * 2);
        }
        expect(cost.bins.reduce((total, bin) => total + bin.n, 0)).toBe(5);
        expect(cost.bins[cost.bins.length - 1].throughPct).toBe(100);
        expect(cost.median).toBe(3000);
        expect(cost.p95).toBeCloseTo(7800, 6);
        expect(cost.fastest).toBe(300);
        expect(cost.slowest).toBe(9000);
    });
});
