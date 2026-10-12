/** Deterministic ranked rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { rank, tailSentence, percentOf } from '../src/lib/charts/rank';
import type { RankedDisplay } from '../src/lib/charts/rank';
import { targetGeometry, targetMarks } from '../src/lib/charts/targetbar';
import { sparklineMarks } from '../src/lib/charts/sparkline';
function display(label: string, value: string, extra: Partial<RankedDisplay> = {}): RankedDisplay {
    return { label, value, ...extra };
}
test.describe('the ranking', () => {
    test('orders by magnitude, and never by the order it arrived in', () => {
        const r = rank([
            { key: 'wed', value: 3, row: display('wed', '3') },
            { key: 'tue', value: 17, row: display('tue', '17') },
            { key: 'mon', value: 9, row: display('mon', '9') }
        ], 10);
        expect(r.rows.map((x) => x.key)).toEqual(['tue', 'mon', 'wed']);
    });
    test('the cap hides the tail and counts what it hid', () => {
        const r = rank([9, 8, 7, 6, 5].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })), 3);
        expect(r.rows.map((x) => x.value)).toEqual([9, 8, 7]);
        expect(r.hidden).toBe(2);
        expect(r.hiddenValue).toBe(11);
        expect(r.max).toBe(9);
    });
    test('a tie lands the same way whichever order it arrived in', () => {
        const rows = (order: string[]) => rank(order.map((k) => ({ key: k, value: 5, row: display(k, '5') })), 10).rows.map((x) => x.key);
        expect(rows(['b', 'a', 'c'])).toEqual(['a', 'b', 'c']);
        expect(rows(['c', 'b', 'a'])).toEqual(['a', 'b', 'c']);
    });
    test('a tiebreak outranks the key, and the magnitude outranks both', () => {
        const r = rank([
            { key: 'a', value: 5, tiebreak: 1, row: display('a', '5') },
            { key: 'b', value: 5, tiebreak: 9, row: display('b', '5') },
            { key: 'c', value: 6, tiebreak: 0, row: display('c', '6') }
        ], 10);
        expect(r.rows.map((x) => x.key)).toEqual(['c', 'b', 'a']);
    });
    test('a value nobody measured is dropped, not ranked as zero', () => {
        const r = rank([
            { key: 'a', value: Number.NaN, row: display('a', '-') },
            { key: 'b', value: 4, row: display('b', '4') }
        ], 10);
        expect(r.rows.map((x) => x.key)).toEqual(['b']);
        expect(r.hidden).toBe(0);
    });
    test('a list of zeros draws no bar rather than a NaN one', () => {
        const r = rank([
            { key: 'a', value: 0, row: display('a', '0') },
            { key: 'b', value: 0, row: display('b', '0') }
        ], 10);
        expect(r.max).toBe(0);
        for (const row of r.rows) {
            expect(Number.isFinite(row.fraction)).toBe(true);
            expect(row.percent).toBe('0.0000%');
        }
    });
    test('nothing to rank is empty', () => {
        const r = rank([], 10);
        expect(r.empty).toBe(true);
        expect(r.max).toBe(0);
    });
    test('a percentage cannot run negative or past the end of its track', () => {
        expect(percentOf(-0.4)).toBe('0.0000%');
        expect(percentOf(1.7)).toBe('100.0000%');
        expect(percentOf(Number.NaN)).toBe('0%');
    });
});
test.describe('the tail sentence', () => {
    const nouns = { one: 'source', many: 'sources', unitOne: 'cut', unitMany: 'cuts' };
    test('a sum that means nothing is left out of the sentence', () => {
        const r = rank([9, 8, 7].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })), 1);
        expect(tailSentence(r, { one: 'item', many: 'items' })).toBe('2 more items are not shown.');
    });
    test('nothing hidden is no sentence at all', () => {
        const r = rank([{ key: 'a', value: 1, row: display('a', '1') }], 10);
        expect(tailSentence(r, nouns)).toBeNull();
    });
});
test.describe('the target geometry', () => {
    test('a value nobody measured draws nothing', () => {
        const g = targetGeometry(null, 5, 'lower-is-better');
        expect(g.empty).toBe(true);
        expect(targetMarks(null, 5, 'lower-is-better').valuePercent).toBe('0.0000%');
    });
});
function readings(values: readonly (number | null)[]) {
    return values.map((value, index) => ({
        date: `2026-09-${String(index + 1).padStart(2, '0')}`,
        value
    }));
}
test.describe('the sparkline shape', () => {
    test('the points fill the drawn extent, not a domain anchored at zero', () => {
        const s = sparklineMarks(readings([980, 1000, 990]));
        expect(s.empty).toBe(false);
        expect(s.min).toBe(980);
        expect(s.max).toBe(1000);
        expect(s.points.map((p) => p.x)).toEqual([0, 0.5, 1]);
        expect(s.points[0].y).toBeCloseTo(1, 10);
        expect(s.points[1].y).toBeCloseTo(0, 10);
        expect(s.points[2].y).toBeCloseTo(0.5, 10);
    });
    test('a reading nobody took is dropped with its date, never drawn as a zero', () => {
        const s = sparklineMarks(readings([4, null, 6]));
        expect(s.values).toEqual([4, 6]);
        expect(s.dates).toEqual(['2026-09-01', '2026-09-03']);
        expect(s.points).toHaveLength(2);
    });
});
