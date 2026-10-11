/** Deterministic model reasons rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { REASONS, neverSeenNote, reasonDays, reasonHeadline, reasonTotals, unexplainedNote } from '../src/lib/console/doubt-reasons';
interface RawItem {
    band?: string | null;
    band_reason?: string | null;
}
function some(n: number, band: string, reason: string | null): RawItem[] {
    return Array.from({ length: n }, () => ({ band, band_reason: reason }));
}
const FIXTURE: {
    date: string;
    items: RawItem[];
}[] = [
    {
        date: '2026-03-04',
        items: [
            ...some(3, 'low', 'unsupported_number'),
            ...some(5, 'low', 'faithfulness'),
            ...some(2, 'medium', 'faithfulness'),
            ...some(4, 'medium', 'lead_missing'),
            ...some(6, 'medium', 'hedge_dropped'),
            ...some(1, 'medium', 'not_scored'),
            ...some(9, 'high', null)
        ]
    },
    { date: '2026-03-01', items: [...some(4, 'medium', null), ...some(2, 'low', null), ...some(7, 'high', null)] },
    { date: '2026-03-02', items: some(11, 'high', null) },
    { date: '2026-03-03', items: [...some(2, 'low', 'a_sixth_reason'), ...some(3, 'high', null)] },
    { date: '2026-03-05', items: [] },
    { date: '2026-03-06', items: [{}, {}, {}] }
];
function fixtureDays() {
    return reasonDays(FIXTURE.map((day) => ({
        date: day.date,
        items: day.items.map((item) => ({
            band: item.band ?? null,
            reason: item.band_reason ?? null
        }))
    })));
}
test.describe('the arithmetic', () => {
    test('a day the checker had nothing to say about is not a day nothing ran', () => {
        const clean = fixtureDays().find((day) => day.date === '2026-03-02');
        expect(clean?.items, 'the clean day lost its item count').toBe(11);
        expect(clean?.explained, 'a top-band day drew a band').toBe(0);
        expect(clean?.unexplained, 'a top-band day was called unexplained').toBe(0);
    });
    test('a reason the panel has never heard of is never drawn as one of the five', () => {
        const odd = fixtureDays().find((day) => day.date === '2026-03-03');
        expect(REASONS.reduce((sum, r) => sum + (odd?.counts[r.id] ?? 0), 0)).toBe(0);
        expect(odd?.explained, 'an unknown reason was counted as a drawn one').toBe(0);
        expect(odd?.unexplained, 'the item was doubted and is not accounted for').toBe(2);
    });
    test('the days with no reason written down are counted and never folded in', () => {
        const totals = reasonTotals(fixtureDays());
        expect(totals.unexplained).toBe(8);
        expect(totals.unexplainedDays).toBe(2);
        expect(totals.explained).toBe(21);
        expect(totals.items).toBe(3 + 5 + 2 + 4 + 6 + 1 + 9 + 13 + 11 + 5 + 0 + 3);
    });
    test('the three sentences say what the numbers mean, and say nothing when there is nothing to say', () => {
        const days = fixtureDays();
        expect(reasonHeadline(days, 30)).toBe('The reason given most often is "Does not match the article": 7 summaries in these 30 days, or about one in every nine published.');
        expect(unexplainedNote(days, 30)).toBe('8 of the 29 doubted summaries in these 30 days have no reason written down, on 2 days. Those columns are short by that much: the reason is missing from our record, not from the summary.');
        expect(neverSeenNote(days, 30)).toBeNull();
        const clean = reasonDays([{ date: '2026-03-02', items: [{ band: 'high', reason: null }] }]);
        expect(reasonHeadline(clean, 7)).toBeNull();
        expect(unexplainedNote(clean, 7)).toBeNull();
        expect(neverSeenNote(clean, 7)).toContain('"Numbers not in the article"');
        expect(neverSeenNote(clean, 7)).toContain('"Maybe" told as fact');
        expect(neverSeenNote([], 7)).toBeNull();
    });
    test('a share is spelled out, so the number carries what it means', () => {
        const oneInFive = reasonDays([
            {
                date: '2026-03-04',
                items: [
                    ...some(2, 'medium', 'faithfulness'),
                    ...some(8, 'high', null)
                ].map((item) => ({ band: item.band ?? null, reason: item.band_reason ?? null }))
            }
        ]);
        expect(reasonHeadline(oneInFive, 30)).toBe('The reason given most often is "Does not match the article": 2 summaries in these 30 days, or about one in every five published.');
    });
    test('no reason label is the name of the column behind it', () => {
        for (const reason of REASONS) {
            expect(reason.label, `${reason.id} is labelled with its own identifier`).not.toContain('_');
            expect(reason.label.length, `${reason.id} has no label`).toBeGreaterThan(3);
        }
    });
});
