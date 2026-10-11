/** THE ORACLE for Row #12: a chart never draws a span nothing measured.
 *
 * Three console charts draw the window the control set rather than the days
 * their own data covers, which is right - narrowing the window would make a
 * seven-day record look like a thirty-day one. What was wrong is what they did
 * with the difference. Measured 2026-09-01 at 1440 on the built console:
 * `Time per item, by stage` drew a 1,292px plot with every mark between
 * x=1,030 and x=1,342 - 312px, 24 percent of the plot, all against the right
 * edge - because the window was 30 days and 8 carried a timing. `Failure rate
 * against volume` and `Summary length against the length asked for` drew
 * columns on the same 8 of 30. Nothing on any of the three said so, and a
 * pointer on one of the other 22 columns printed a row of blanks or a row of
 * zeros, which reads as a broken hover rather than as an empty day.
 *
 * The oracle is over the page, not over the rule: it counts the columns that
 * carry a mark itself, off the drawn geometry, and holds the chart's own
 * sentence to that count.
 *
 * It runs against the canary build. See `frontend/scripts/build-canary.mjs`.
 */
import { expect, test } from '@playwright/test';
import { coverage, SPARSE_COVERAGE } from '../src/lib/charts/frame';
test.describe('the coverage rule itself', () => {
    test('it counts the columns and finds every gap', () => {
        const all = coverage([true, true, true]);
        expect(all).toEqual({ days: 3, measured: 3, sparse: false, gaps: [] });
        const some = coverage([false, false, true, false, true, false]);
        expect(some.days).toBe(6);
        expect(some.measured).toBe(2);
        expect(some.gaps).toEqual([
            [0, 1],
            [3, 3],
            [5, 5]
        ]);
    });
    test('an empty chart is not a sparse one', () => {
        // Nothing at all is the panel's own empty state, in words, and a tinted
        // span across a plot with no axis on it explains nothing.
        expect(coverage([]).sparse).toBe(false);
        expect(coverage([false, false, false]).sparse).toBe(false);
    });
    test('the threshold is the line, and it is declared', () => {
        expect(SPARSE_COVERAGE).toBeGreaterThan(0);
        expect(SPARSE_COVERAGE).toBeLessThan(1);
        const under = Array.from({ length: 10 }, (_, index) => index < 4);
        const over = Array.from({ length: 10 }, (_, index) => index < 6);
        expect(under.filter(Boolean).length / 10).toBeLessThan(SPARSE_COVERAGE);
        expect(coverage(under).sparse).toBe(true);
        expect(over.filter(Boolean).length / 10).toBeGreaterThanOrEqual(SPARSE_COVERAGE);
        expect(coverage(over).sparse).toBe(false);
    });
});
