/** Deterministic voices sources rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { rangeMarks } from '../src/lib/charts/series';
import { sourceCuts, SOURCE_CUT_ROWS } from '../src/lib/server/model-work';
const CUT_WINDOW = { start: '2026-08-01', end: '2026-08-07', days: 7 };
function cutRow(cells: Record<string, string>): Record<string, string> {
    return {
        date: '2026-08-07',
        source_id: 'alpha',
        url_key: 'alpha-1',
        source_words: '',
        source_words_before_cap: '',
        ...cells
    };
}
const CUT_ROWS = [
    cutRow({
        date: '2026-08-03',
        source_id: 'alpha',
        url_key: 'alpha-1',
        source_words: '3000',
        source_words_before_cap: '5000'
    }),
    cutRow({
        date: '2026-08-04',
        source_id: 'alpha',
        url_key: 'alpha-2',
        source_words: '3000',
        source_words_before_cap: '7000'
    }),
    cutRow({
        date: '2026-08-05',
        source_id: 'alpha',
        url_key: 'alpha-repeat',
        source_words: '1800',
        source_words_before_cap: '2500'
    }),
    cutRow({
        date: '2026-08-05',
        source_id: 'alpha',
        url_key: 'alpha-repeat',
        source_words: '3000',
        source_words_before_cap: '6500'
    }),
    cutRow({
        date: '2026-08-06',
        source_id: 'alpha',
        url_key: 'alpha-4',
        source_words: '9000',
        source_words_before_cap: '9000'
    }),
    cutRow({
        date: '2026-08-06',
        source_id: 'beta',
        url_key: 'beta-1',
        source_words: '3000',
        source_words_before_cap: '4200'
    }),
    cutRow({
        date: '2026-08-06',
        source_id: 'beta',
        url_key: 'beta-2',
        source_words: '2000',
        source_words_before_cap: '2000'
    }),
    cutRow({
        date: '2026-08-06',
        source_id: 'beta',
        url_key: 'beta-3',
        source_words: '30000',
        source_words_before_cap: ''
    }),
    cutRow({
        date: '2026-08-07',
        source_id: 'gamma',
        url_key: 'gamma-1',
        source_words: '3846',
        source_words_before_cap: '6200'
    }),
    cutRow({
        date: '2026-08-07',
        source_id: 'gamma',
        url_key: 'gamma-2',
        source_words: '1800',
        source_words_before_cap: '1800'
    }),
    cutRow({
        date: '2026-08-02',
        source_id: 'delta',
        url_key: 'delta-1',
        source_words: '1923',
        source_words_before_cap: '4100'
    })
];
test('cut points come from the rows that were cut, not from the setting', () => {
    const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 2 });
    expect(cuts.caps).toEqual([
        { words: 1923, first: '2026-08-02', last: '2026-08-02' },
        { words: 3000, first: '2026-08-03', last: '2026-08-06' },
        { words: 3846, first: '2026-08-07', last: '2026-08-07' }
    ]);
    expect(cuts.measured).toBe(true);
});
test('sources cut by the cap are ranked worst first, with the tail counted', () => {
    const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 2 });
    expect(cuts.rows).toEqual([
        {
            sourceId: 'alpha',
            cut: 3,
            articles: 4,
            lengths: { min: 5000, median: 6750, max: 9000 }
        },
        {
            sourceId: 'beta',
            cut: 1,
            articles: 3,
            lengths: { min: 2000, median: 3100, max: 4200 }
        }
    ]);
    expect(cuts.moreSources).toBe(2);
    expect(cuts.moreCuts).toBe(2);
    expect(cuts.articles).toBe(10);
});
test('article counts collapse reruns, and ranges use measured article length', () => {
    const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 4 });
    const alpha = cuts.rows.find((row) => row.sourceId === 'alpha');
    const beta = cuts.rows.find((row) => row.sourceId === 'beta');
    expect(alpha?.articles, 'five rows of alpha collapse to four articles').toBe(4);
    expect(alpha?.cut).toBe(3);
    expect(alpha?.lengths).toEqual({ min: 5000, median: 6750, max: 9000 });
    expect(beta?.articles, 'a row without a before length is still an article').toBe(3);
    expect(beta?.lengths.max, 'the surviving 30,000-word cell is not a pre-cut length').toBe(4200);
});
test('cut cost is counted as article losses with n, median and max', () => {
    const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 2 });
    expect(cuts.cost).toEqual({ n: 6, median: 2354, max: 4000 });
});
const WEEK = { start: '2026-08-22', end: '2026-08-28', days: 7 };
test('a window with no cut renders its own empty state, and absence is not zero', () => {
    const migrated = (source: string, index: number) => ({
        date: '2026-08-28',
        source_id: source,
        url_key: `${source}-${index}`,
        source_words: '5000',
        source_words_before_cap: ''
    });
    const nothing = sourceCuts([migrated('a', 0), migrated('a', 1)], WEEK, { limit: SOURCE_CUT_ROWS });
    expect(nothing.rows).toEqual([]);
    expect(nothing.measured).toBe(false);
    expect(nothing.cost).toBeNull();
    expect(nothing.caps).toEqual([]);
    const some = sourceCuts([
        migrated('a', 0),
        {
            date: '2026-08-28',
            source_id: 'a',
            url_key: 'a-1',
            source_words: '1923',
            source_words_before_cap: '2612'
        }
    ], WEEK, { limit: SOURCE_CUT_ROWS });
    expect(some.measured).toBe(true);
    expect(some.rows).toHaveLength(1);
    expect(some.rows[0].cut).toBe(1);
    expect(some.rows[0].articles).toBe(2);
    expect(some.rows[0].lengths).toEqual({ min: 2612, median: 2612, max: 2612 });
    expect(some.caps).toEqual([{ words: 1923, first: '2026-08-28', last: '2026-08-28' }]);
    expect(some.cost).toEqual({ n: 1, median: 689, max: 689 });
    expect(sourceCuts([
        {
            date: '2026-08-28',
            source_id: 'a',
            url_key: 'a-0',
            source_words: '',
            source_words_before_cap: '2612'
        }
    ], WEEK, { limit: SOURCE_CUT_ROWS }).rows).toEqual([]);
});
test('a cut point per length the cap left, oldest first, read off the rows', () => {
    const row = (index: number, date: string, before: string, after: string) => ({
        date,
        source_id: 'a',
        url_key: `a-${index}`,
        source_words: after,
        source_words_before_cap: before
    });
    const capsOf = (rows: Record<string, string>[]) => sourceCuts(rows, { start: '2026-08-01', end: '2026-08-30', days: 30 }, { limit: SOURCE_CUT_ROWS }).caps;
    expect(capsOf([row(0, '2026-08-20', '4000', '1923'), row(1, '2026-08-22', '9000', '1923')])).toEqual([{ words: 1923, first: '2026-08-20', last: '2026-08-22' }]);
    expect(capsOf([row(0, '2026-08-20', '4000', '1923'), row(1, '2026-08-29', '9000', '3846')])).toEqual([
        { words: 1923, first: '2026-08-20', last: '2026-08-20' },
        { words: 3846, first: '2026-08-29', last: '2026-08-29' }
    ]);
    expect(capsOf([row(0, '2026-08-20', '4000', '1877')])[0].words).toBe(1877);
    const many = sourceCuts([
        ...Array.from({ length: 12 }, (_, index) => ({
            date: '2026-08-28',
            source_id: `s${index}`,
            url_key: `s${index}-0`,
            source_words: '1900',
            source_words_before_cap: '4000'
        })),
        {
            date: '2026-08-28',
            source_id: 'tail',
            url_key: 'tail-0',
            source_words: '1923',
            source_words_before_cap: '5000'
        }
    ], WEEK, { limit: SOURCE_CUT_ROWS });
    expect(many.rows).toHaveLength(SOURCE_CUT_ROWS);
    expect(many.moreSources).toBe(3);
    expect(many.caps.map((cap) => cap.words)).toEqual([1900, 1923]);
});
test('a row is placed on the axis, and the lost span is held inside it', () => {
    const identity = (words: number) => words;
    expect(rangeMarks({ min: 400, median: 2600, max: 9000 }, 1923, identity)).toEqual({
        x0: 400,
        xMid: 2600,
        x1: 9000,
        xCut: 1923,
        past: true
    });
    expect(rangeMarks({ min: 2623, median: 4723, max: 9000 }, 1923, identity).xCut).toBe(2623);
    const untouched = rangeMarks({ min: 100, median: 200, max: 900 }, 1923, identity);
    expect(untouched.past).toBe(false);
    expect(untouched.xCut).toBe(untouched.x1);
    expect(rangeMarks({ min: 100, median: 200, max: 900 }, null, identity).past).toBe(false);
});
