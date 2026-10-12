/** Deterministic model panels rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { modelSwap, runLengths, scoreCost, writeTimes, type DayWindow } from '../src/lib/server/model-work';
import { BANDS, pair } from './support/model-swap';
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
test.describe('how long the summaries came out', () => {
    function summary(runId: string, date: string, words: number, sourceWords: number): Record<string, string> {
        return {
            run_id: runId,
            date,
            model_id: 'a-model',
            summary_words: String(words),
            source_words_before_cap: String(sourceWords)
        };
    }
    test('a run is three marks and the ask is read off its own articles', () => {
        const runs = runLengths([
            summary('2026-08-20-1', '2026-08-20', 40, 100),
            summary('2026-08-20-1', '2026-08-20', 90, 100),
            summary('2026-08-20-1', '2026-08-20', 200, 1000),
            summary('2026-08-21-1', '2026-08-21', 60, 100)
        ], BANDS);
        expect(runs.map((run) => run.runId)).toEqual(['2026-08-20-1', '2026-08-21-1']);
        const first = runs[0];
        expect(first.items).toBe(3);
        expect([first.low, first.median, first.high]).toEqual([40, 90, 200]);
        expect([first.askLow, first.askHigh]).toEqual([50, 150]);
        expect([runs[1].askLow, runs[1].askHigh]).toEqual([50, 90]);
    });
    test('a run whose articles recorded no length has no ask, and says so', () => {
        const runs = runLengths([{ run_id: 'r', date: '2026-08-20', summary_words: '70' }], BANDS);
        expect(runs).toHaveLength(1);
        expect(runs[0].askLow).toBeNull();
        expect(runs[0].askHigh).toBeNull();
    });
});
test.describe('did the model change move anything', () => {
    test('each measure is the after over the before, and both values are kept', () => {
        const swap = modelSwap([
            ...pair(10, '2026-08-20', 'old', { band: 'low' }),
            ...pair(10, '2026-08-21', 'new', { summary_words: '50' })
        ], [
            ...Array.from({ length: 10 }, () => timed('2026-08-20', 100000)),
            ...Array.from({ length: 10 }, () => timed('2026-08-21', 50000))
        ], BANDS, 5) as NonNullable<ReturnType<typeof modelSwap>>;
        expect(swap.at).toBe('2026-08-21');
        expect(swap.before.model).toBe('old');
        expect(swap.after.model).toBe('new');
        expect(swap.before.articles).toBe(10);
        expect(swap.after.articles).toBe(10);
        expect(swap.enough).toBe(true);
        const by = new Map(swap.measures.map((measure) => [measure.label, measure]));
        expect(by.get('Time to write one')?.ratio).toBeCloseTo(0.5, 6);
        expect(by.get('Summary length')?.before).toBe(100);
        expect(by.get('Summary length')?.after).toBe(50);
        expect(by.get('Marked "not sure"')?.before).toBe(100);
        expect(by.get('Marked "not sure"')?.after).toBe(0);
        expect(by.get('Summaries the checker doubted')?.before).toBe(100);
        expect(by.get('Summaries the checker doubted')?.after).toBe(0);
        expect(swap.measures).toHaveLength(10);
    });
    test('a measure neither side recorded is named, never drawn as a change', () => {
        const swap = modelSwap([...pair(10, '2026-08-20', 'old'), ...pair(10, '2026-08-21', 'new')], [], BANDS, 5) as NonNullable<ReturnType<typeof modelSwap>>;
        for (const label of ['Reading the article', 'Writing the summary', 'Time to write one']) {
            const measure = swap.measures.find((entry) => entry.label === label);
            expect(measure?.before, `${label} invented a value for a side with no rows`).toBeNull();
            expect(measure?.after, `${label} invented a value for a side with no rows`).toBeNull();
            expect(measure?.ratio, `${label} drew a ratio out of two absences`).toBeNull();
        }
    });
    test('a rate both sides recorded is a comparison, and it is drawn', () => {
        const rate = (date: string, prefill: number, decode: number) => ({
            date,
            prefill_ms: String(prefill),
            decode_ms: String(decode),
            input_tokens: '1000',
            output_tokens: '100',
            cached_tokens: '0'
        });
        const swap = modelSwap([...pair(10, '2026-08-20', 'old'), ...pair(10, '2026-08-21', 'new')], [
            ...Array.from({ length: 10 }, () => rate('2026-08-20', 1000, 1000)),
            ...Array.from({ length: 10 }, () => rate('2026-08-21', 2000, 1000))
        ], BANDS, 5) as NonNullable<ReturnType<typeof modelSwap>>;
        const read = swap.measures.find((entry) => entry.label === 'Reading the article');
        expect(read?.before).toBe(1000);
        expect(read?.after).toBe(500);
        expect(read?.ratio).toBeCloseTo(0.5, 6);
        expect(read?.polarity).toBe('no-agreed-direction');
        expect(swap.measures.find((entry) => entry.label === 'Writing the summary')?.polarity).toBe('no-agreed-direction');
    });
    test('a thin side draws nothing, and the counts are the whole answer', () => {
        const swap = modelSwap([...pair(2, '2026-08-20', 'old'), ...pair(30, '2026-08-21', 'new')], [], BANDS, 5) as NonNullable<ReturnType<typeof modelSwap>>;
        expect(swap.before.articles).toBe(2);
        expect(swap.enough).toBe(false);
    });
    test('no change of model is no panel at all', () => {
        expect(modelSwap(pair(30, '2026-08-20', 'one'), [], BANDS, 5)).toBeNull();
        expect(modelSwap([], [], BANDS, 5)).toBeNull();
    });
    test('a measure that was nothing before has no ratio, because a move away from nothing has no size', () => {
        const swap = modelSwap([
            ...pair(10, '2026-08-20', 'old'),
            ...pair(10, '2026-08-21', 'new', { hedge_dropped: 'True' })
        ], [], BANDS, 5) as NonNullable<ReturnType<typeof modelSwap>>;
        const hedge = swap.measures.find((measure) => measure.label === '"Maybe" told as fact');
        expect(hedge?.before).toBe(0);
        expect(hedge?.after).toBe(100);
        expect(hedge?.ratio).toBeNull();
    });
});
