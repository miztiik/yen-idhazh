/** Deterministic doubt rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { doubted, sourceDoubts, type DayWindow } from '../src/lib/server/model-work';
const WEEK: DayWindow = { start: '2026-08-15', end: '2026-08-21', days: 7 };
function score(date: string, urlKey: string, extra: Record<string, string> = {}): Record<string, string> {
    return { date, url_key: urlKey, band: 'high', ...extra };
}
function published(urlKey: string, sourceId: string): Record<string, string> {
    return { date: '2026-08-20', url_key: urlKey, source_id: sourceId };
}
test.describe('the doubt signal, as arithmetic', () => {
    test('a summary is doubted by any one of the three, and never by a blend', () => {
        expect(doubted({ band: 'high' })).toBe(false);
        expect(doubted({ band: 'low' })).toBe(true);
        expect(doubted({ band: 'high', unsupported_numbers: '1' })).toBe(true);
        expect(doubted({ band: 'high', unsupported_numbers: '0' })).toBe(false);
        expect(doubted({ band: 'high', hedge_dropped: 'True' })).toBe(true);
        expect(doubted({ band: 'high', hedge_dropped: 'False' })).toBe(false);
    });
    test('a summary carrying two signals is one doubt, counted in both columns', () => {
        const doubts = sourceDoubts([score('2026-08-20', 'a', { band: 'low', hedge_dropped: 'True' })], [published('a', 'one')], WEEK, { limit: 10, minForShare: 5 });
        expect(doubts.rows[0].doubted).toBe(1);
        expect(doubts.rows[0].notSure).toBe(1);
        expect(doubts.rows[0].hedgeDropped).toBe(1);
        expect(doubts.rows[0].notSure + doubts.rows[0].hedgeDropped).toBeGreaterThan(doubts.rows[0].doubted);
    });
    test('THE ORACLE: the order is the count, so a big denominator cannot be demoted', () => {
        const scores = [
            ...Array.from({ length: 2 }, (_, at) => score('2026-08-20', `small-${at}`, { band: 'low' })),
            score('2026-08-20', 'small-2'),
            ...Array.from({ length: 40 }, (_, at) => score('2026-08-20', `big-${at}`, { band: 'low' })),
            ...Array.from({ length: 360 }, (_, at) => score('2026-08-20', `big-${at + 40}`))
        ];
        const health = [
            ...Array.from({ length: 3 }, (_, at) => published(`small-${at}`, 'small')),
            ...Array.from({ length: 400 }, (_, at) => published(`big-${at}`, 'big'))
        ];
        const doubts = sourceDoubts(scores, health, WEEK, { limit: 10, minForShare: 5 });
        expect(doubts.rows.map((row) => row.sourceId)).toEqual(['big', 'small']);
        expect(doubts.rows[0].doubted).toBe(40);
        expect(doubts.rows[0].summaries).toBe(400);
        expect(doubts.rows[1].doubted).toBe(2);
        expect(doubts.rows[1].summaries).toBe(3);
        expect(doubts.rows[1].sharePct, 'a share over three summaries is the second one').toBeNull();
        expect(doubts.rows[0].sharePct).toBe(10);
    });
    test('a tie goes to the name, so the page does not move between builds', () => {
        const doubts = sourceDoubts([
            score('2026-08-20', 'z', { band: 'low' }),
            score('2026-08-20', 'a', { band: 'low' }),
            score('2026-08-20', 'm', { band: 'low' })
        ], [published('z', 'zulu'), published('a', 'alpha'), published('m', 'mike')], WEEK, { limit: 10, minForShare: 5 });
        expect(doubts.rows.map((row) => row.sourceId)).toEqual(['alpha', 'mike', 'zulu']);
    });
    test('a source with nothing doubted is left out, not ranked at zero', () => {
        const doubts = sourceDoubts([score('2026-08-20', 'a'), score('2026-08-20', 'b', { band: 'low' })], [published('a', 'clean'), published('b', 'doubted')], WEEK, { limit: 10, minForShare: 5 });
        expect(doubts.rows.map((row) => row.sourceId)).toEqual(['doubted']);
        expect(doubts.sources).toBe(2);
        expect(doubts.summaries).toBe(2);
    });
    test('the cap states its own tail, in sources and in doubts', () => {
        const scores = Array.from({ length: 6 }, (_, at) => score('2026-08-20', `s${at}`, { band: 'low' }));
        const health = scores.map((row, at) => published(`s${at}`, `source-${at}`));
        const doubts = sourceDoubts(scores, health, WEEK, { limit: 2, minForShare: 5 });
        expect(doubts.rows).toHaveLength(2);
        expect(doubts.moreSources).toBe(4);
        expect(doubts.moreDoubted).toBe(4);
        expect(doubts.doubted).toBe(6);
    });
    test('a summary no ledger can place is counted as that, never dropped quietly', () => {
        const doubts = sourceDoubts([score('2026-08-20', 'known', { band: 'low' }), score('2026-08-20', 'orphan')], [published('known', 'one')], WEEK, { limit: 10, minForShare: 5 });
        expect(doubts.unattributed).toBe(1);
        expect(doubts.summaries).toBe(2);
        expect(doubts.rows[0].summaries).toBe(1);
    });
    test('a window is a filter on the rows and a day outside it is not counted', () => {
        const scores = [
            score('2026-08-14', 'a', { band: 'low' }),
            score('2026-08-20', 'b', { band: 'low' })
        ];
        const health = [published('a', 'one'), published('b', 'one')];
        expect(sourceDoubts(scores, health, WEEK, { limit: 10, minForShare: 5 }).doubted).toBe(1);
        expect(sourceDoubts(scores, health, { start: '2026-08-08', end: '2026-08-21', days: 14 }, {
            limit: 10,
            minForShare: 5
        }).doubted).toBe(2);
    });
    test('THE ORACLE: the ranked rows are the values written in this spec', () => {
        const scores = [
            score('2026-08-20', 'beta-1', { band: 'low', unsupported_numbers: '2' }),
            score('2026-08-20', 'beta-2', { band: 'low' }),
            score('2026-08-20', 'beta-3', { hedge_dropped: 'True' }),
            score('2026-08-20', 'alpha-1', { unsupported_numbers: '1' }),
            score('2026-08-20', 'alpha-2', { hedge_dropped: 'true' }),
            score('2026-08-20', 'alpha-3'),
            score('2026-08-20', 'clean-1'),
            score('2026-08-13', 'outside', { band: 'low' })
        ];
        const health = [
            published('beta-1', 'beta'),
            published('beta-2', 'beta'),
            published('beta-3', 'beta'),
            published('alpha-1', 'alpha'),
            published('alpha-2', 'alpha'),
            published('alpha-3', 'alpha'),
            published('clean-1', 'clean'),
            published('outside', 'outside')
        ];
        const doubts = sourceDoubts(scores, health, WEEK, { limit: 10, minForShare: 3 });
        expect(doubts.rows.map((row) => row.sourceId)).toEqual(['beta', 'alpha']);
        expect(doubts.rows.map((row) => row.doubted)).toEqual([3, 2]);
        expect(doubts.rows.map((row) => row.summaries)).toEqual([3, 3]);
        expect(doubts.rows.map((row) => row.notSure)).toEqual([2, 0]);
        expect(doubts.rows.map((row) => row.unsupportedNumbers)).toEqual([1, 1]);
        expect(doubts.rows.map((row) => row.hedgeDropped)).toEqual([1, 1]);
        expect(doubts.rows.map((row) => row.sharePct)).toEqual([100, 67]);
        expect(doubts.sources).toBe(3);
        expect(doubts.summaries).toBe(7);
        expect(doubts.doubted).toBe(5);
        expect(doubts.unattributed).toBe(0);
    });
    test('THE ORACLE: an unattributed summary is counted in totals and no source row', () => {
        const doubts = sourceDoubts([
            score('2026-08-20', 'known', { band: 'low' }),
            score('2026-08-20', 'orphan', { band: 'low' })
        ], [published('known', 'known-source')], WEEK, { limit: 10, minForShare: 5 });
        expect(doubts.rows.map((row) => row.sourceId)).toEqual(['known-source']);
        expect(doubts.rows[0].doubted).toBe(1);
        expect(doubts.rows[0].summaries).toBe(1);
        expect(doubts.unattributed).toBe(1);
        expect(doubts.summaries).toBe(2);
        expect(doubts.doubted).toBe(1);
    });
});
