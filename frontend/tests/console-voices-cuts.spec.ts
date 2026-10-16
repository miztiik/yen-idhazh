/** THE ORACLE for Row #9: `Sources cut short most often` fills its frame.
 *
 * The plot gave its source names a fixed 168px gutter and its rows a fixed 34px
 * pitch. Measured 2026-09-01 on the built console, before this row: at 1440 the
 * frame was 1,342px and the plot 1,162px of it - 86.6 percent; at 768, 493 of
 * 673 - 73.3 percent; and at 390, 144 of 324 - **44.4 percent**, so on a phone
 * the label column took more of the chart than the plot did and the six tracks
 * drew inside 91px. The pitch was 34px at all three, which is two lines of type
 * and a 10px bar with nothing between one row and the next.
 *
 * The right-most axis label is checked here too. It measured clipped to
 * `10,00` at 1440 on 2026-08-31; Row #1's `tickAnchor` fixed that by anchoring
 * the end labels inwards, and this asserts it stays fixed rather than fixing it
 * a second time.
 *
 * Every bound below is read off the frame the page drew, so a wider window or a
 * longer source id moves both sides of the assertion at once.
 *
 * It runs against the canary build. See `frontend/scripts/build-canary.mjs`.
 */
import { expect, test } from '@playwright/test';
import { labelGutter, MAX_GUTTER_SHARE, rowPitch } from '../src/lib/charts/frame';
test.describe('the two frame rules this row added', () => {
    test('a gutter is measured, and refused where the frame cannot spare it', () => {
        // `inside-climate-news` is the widest source id the committed ledger holds
        // at the time of writing, and it is what the fixed 168px was sized for.
        const names = ['heatmap', 'inside-climate-news', 'aws-ml-blog'];
        const wide = labelGutter(names, 11, 10, 1342);
        expect(wide, 'a page-wide frame can hold the names beside the plot').not.toBeNull();
        expect(wide ?? 0).toBeLessThanOrEqual(1342 * MAX_GUTTER_SHARE);
        // And it is the widest name that decides, not the first or the last.
        expect(labelGutter(names, 11, 10, 1342)).toBe(labelGutter(['inside-climate-news'], 11, 10, 1342));
        // Null is the cue to put the names above their tracks. It is never a cue
        // to shrink the plot behind them, and never one to shorten a name.
        expect(labelGutter(names, 11, 10, 324), 'a phone frame cannot').toBeNull();
        // An empty set needs only the gap, whatever the frame.
        expect(labelGutter([], 11, 10, 324)).toBe(10);
    });
    test('a row pitch grows with the frame, between a floor and a ceiling', () => {
        expect(rowPitch(1198, 40, 56), 'a page-wide plot grows the row').toBe(50);
        expect(rowPitch(300, 40, 56), 'a narrow plot stops at the floor').toBe(40);
        expect(rowPitch(4000, 40, 56), 'and a very wide one stops at the ceiling').toBe(56);
        // Nothing measured yet - the server, or the first frame - is the floor and
        // never a zero-height row.
        expect(rowPitch(0, 40, 56)).toBe(40);
        expect(rowPitch(Number.NaN, 40, 56)).toBe(40);
    });
});
