/** The stage-timing chart's axis, its marks and the strip that reads them.
 *
 * The chart used to print one string for the whole span and no mark at any
 * point. So a spike could not be attributed to a date without counting columns
 * with a finger, and there was nothing to aim a pointer at. It also drew its
 * own span, so the control above it could read 30 days over a plot drawing 6.
 *
 * Measured on the built canary console page 2026-08-30, at the default 30-day
 * preset over 4 stages: 6 date labels where there was 1 span string, and 9
 * marks across 3 lines where there were 0. The strip under them was then a
 * third of the plot wide and stacked its entries; it now takes the plot's
 * width and lays them side by side. Every
 * count here is read off a fact the chart publishes about itself rather than
 * written down, so growing the fixture or moving the window cannot turn an
 * assertion into a tautology or a false failure.
 */
import { expect, test } from '@playwright/test';
import { coverage, coverageSentence, dayColumns, dayColumnX, dayTicks, frame } from '../src/lib/charts/frame';
import { readoutCapStyle } from '../src/lib/charts/readout';
function days(start: string, count: number): string[] {
    const first = new Date(`${start}T00:00:00Z`);
    return Array.from({ length: count }, (_, step) => {
        const day = new Date(first);
        day.setUTCDate(day.getUTCDate() + step);
        return day.toISOString().slice(0, 10);
    });
}
/** A plot wide enough that the fit never bites, so a test about the ceiling is
 * about the ceiling. 4,000px is over twice the widest window this ships in. */
function roomy(count: number): number[] {
    return Array.from({ length: count }, (_, index) => index * (4000 / Math.max(1, count - 1)));
}
/** Every date a tick carries a label for, in order. */
function labelled(ticks: {
    text: string;
}[]): string[] {
    return ticks.filter((tick) => tick.text !== '').map((tick) => tick.text);
}
test.describe('the day axis', () => {
    test('a window shorter than the density gets a label on every day', () => {
        expect(dayTicks([], { density: 6, columns: [] })).toEqual([]);
        expect(dayTicks(days('2026-08-18', 3), { density: 6, columns: roomy(3) }).map((tick) => tick.index)).toEqual([0, 1, 2]);
        expect(dayTicks(days('2026-08-18', 6), { density: 6, columns: roomy(6) }).map((tick) => tick.index)).toEqual([0, 1, 2, 3, 4, 5]);
    });
    test('a longer window is thinned to the density, endpoints included', () => {
        const month = dayTicks(days('2026-08-01', 30), { density: 6, columns: roomy(30) });
        expect(month).toHaveLength(6);
        expect(month.map((tick) => tick.index)).toEqual([0, 6, 12, 17, 23, 29]);
        expect(month[0].date).toBe('2026-08-01');
        expect(month[month.length - 1].date).toBe('2026-08-30');
        // The knob is the ceiling, so a lower one thins further and keeps both ends.
        const sparse = dayTicks(days('2026-08-01', 30), { density: 3, columns: roomy(30) });
        expect(sparse.map((tick) => tick.index)).toEqual([0, 15, 29]);
    });
    test('the ceiling is a ceiling, and the room decides the rest', () => {
        const dates = days('2026-08-01', 30);
        // 320px is about the plot a 390px phone gives this chart. Six dates at
        // `20 Aug 2026` need over 330px of text alone, so they cannot all be drawn.
        const phone = dayTicks(dates, {
            density: 6,
            columns: Array.from({ length: 30 }, (_, index) => (index * 320) / 29)
        });
        expect(phone, 'every column the ceiling allows still carries a mark').toHaveLength(6);
        expect(labelled(phone).length, 'and fewer of them carry a date').toBeLessThan(6);
        // The two ends survive as long as anything does, so the span of the chart
        // can still be read off the chart.
        expect(phone[0].text).not.toBe('');
        expect(phone[phone.length - 1].text).not.toBe('');
        // A wider plot of the same days carries more. That is the whole rule: one
        // count cannot hold at 1440 and at 390.
        const desktop = dayTicks(dates, { density: 6, columns: roomy(30) });
        expect(labelled(desktop).length).toBeGreaterThan(labelled(phone).length);
    });
    test('a dropped label keeps its tick mark, and prints nothing', () => {
        // A date is about 64px and the rule wants 8px between two of them, so 40px
        // of plot cannot carry even the two ends.
        const crowded = dayTicks(days('2026-08-01', 30), {
            density: 6,
            columns: Array.from({ length: 30 }, (_, index) => (index * 40) / 29)
        });
        expect(crowded, 'the grid does not change shape as the window does').toHaveLength(6);
        // The newest day is the one an operator reads first, so it is the survivor.
        expect(labelled(crowded)).toEqual(['30 Aug 2026']);
        expect(crowded[crowded.length - 1].anchor).toBe('end');
    });
    test('one day is labelled once, in the middle, with its year', () => {
        expect(dayTicks(['2026-08-20'], { density: 6, columns: [0] })).toEqual([
            { index: 0, date: '2026-08-20', text: '20 Aug 2026', anchor: 'middle' }
        ]);
    });
    test('the year is printed where it changes and nowhere else', () => {
        const across = dayTicks(days('2025-12-20', 30), { density: 6, columns: roomy(30) });
        const years = across.filter((tick) => /\d{4}$/.test(tick.text));
        // The first label always carries one, and the crossing carries the next.
        expect(years.length).toBeGreaterThanOrEqual(2);
        expect(across[0].text).toContain('2025');
        expect(across[across.length - 1].text).not.toContain('2025');
    });
    test('the ends anchor inwards so neither label hangs off the plot', () => {
        const week = dayTicks(days('2026-08-01', 10), { density: 6, columns: roomy(10) });
        expect(week[0].anchor).toBe('start');
        expect(week[week.length - 1].anchor).toBe('end');
        for (const tick of week.slice(1, -1))
            expect(tick.anchor).toBe('middle');
    });
    test('the columns come from the same function the marks do', () => {
        const box = frame(760, 220);
        const columns = dayColumns(6, box);
        expect(columns).toEqual([0, 1, 2, 3, 4, 5].map((index) => dayColumnX(index, 6, box)));
    });
});
test.describe('a day column', () => {
    const box = frame(760, 220);
    test('the first and last column sit on the plot edges', () => {
        expect(dayColumnX(0, 6, box)).toBe(box.left);
        expect(dayColumnX(5, 6, box)).toBe(box.right);
    });
    test('a pad pulls both ends inside, by the same amount', () => {
        expect(dayColumnX(0, 6, box, 8)).toBe(box.left + 8);
        expect(dayColumnX(5, 6, box, 8)).toBe(box.right - 8);
    });
    test('one column is drawn in the middle, not at the left edge', () => {
        expect(dayColumnX(0, 1, box)).toBe((box.left + box.right) / 2);
    });
});
test.describe('the readout strip', () => {
    // The strip used to carry a second test here, asserting that `readoutMarks`
    // preformatted one sentence per series onto every mark. Nothing printed those
    // sentences - `ChartReadout.svelte` is the live region and it prints the rows
    // - so the field went on 2026-09-06 and this test went with it. Which column
    // a mark stands for is now held in `frame.spec.ts`, against the walk it
    // replaced.
    test('the cap is a share of the plot, and it is clamped to one', () => {
        expect(readoutCapStyle(0.33)).toBe('max-width: 33.00%');
        expect(readoutCapStyle(1.5)).toBe('max-width: 100.00%');
        expect(readoutCapStyle(-1)).toBe('max-width: 0.00%');
    });
});
test.describe('the coverage sentence', () => {
    test('the sentence says nothing where the window was timed in full', () => {
        const full = coverage([true, true, true, true]);
        expect(coverageSentence(full, 'We timed', { low: 9, high: 9, total: 9 })).toBeNull();
    });
    test('where two stages disagree the numerator is a range', () => {
        const sparse = coverage([true, false, false, false]);
        expect(coverageSentence(sparse, 'We timed', { low: 3900, high: 3955, total: 5113 })).toBe('We timed 1 of 4 days, and 3,900 to 3,955 of the 5,113 items on them. The tinted span is days nothing recorded, not quiet days.');
        // And where they agree it is one number, not a range with two equal ends.
        expect(coverageSentence(sparse, 'We timed', { low: 3955, high: 3955, total: 5113 })).toBe('We timed 1 of 4 days, and 3,955 of the 5,113 items on them. The tinted span is days nothing recorded, not quiet days.');
    });
});
