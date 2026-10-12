import { expect, test } from './support/door-page';
import { completenessOf, completenessSentence, spelledInstant, untilNextUtcDay } from '../src/lib/console/completeness';
const DAY_MS = 86400000;
test.describe('how complete the record is, as arithmetic', () => {
    // 18:23:02 UTC on Sunday 27 September 2026.
    const FINISHED = '2026-09-27T18:23:02Z';
    const at = Date.parse(FINISHED);
    const midnight = Date.parse('2026-09-27T00:00:00Z');
    test('no record is a named absence, and no clock claims nothing about age', () => {
        expect(completenessOf(null, at, 1)).toEqual({ kind: 'unread' });
        expect(completenessOf('not a time', at, 1)).toEqual({ kind: 'unread' });
        expect(completenessOf(FINISHED, null, 1)).toEqual({ kind: 'complete', finished: at });
        expect(completenessSentence({ kind: 'unread' })).toBe('This page cannot say when the last run finished - its record did not load.');
    });
    test('the day boundary is 00:00 UTC, and the grace moves only when the count is said', () => {
        expect(completenessOf(FINISHED, midnight + DAY_MS - 1, 1).kind).toBe('complete');
        expect(completenessOf(FINISHED, midnight + 2 * DAY_MS - 1, 1).kind).toBe('complete');
        expect(completenessOf(FINISHED, midnight + 2 * DAY_MS, 1)).toEqual({
            kind: 'behind',
            finished: at,
            missingDays: 1
        });
        // A wider grace says it later, and counts the same days when it does.
        expect(completenessOf(FINISHED, midnight + 3 * DAY_MS, 2)).toEqual({
            kind: 'behind',
            finished: at,
            missingDays: 2
        });
        expect(completenessOf(FINISHED, midnight + 3 * DAY_MS, 1)).toEqual({
            kind: 'behind',
            finished: at,
            missingDays: 2
        });
        // A reader whose clock is behind the record is not told anything is late.
        expect(completenessOf(FINISHED, at - DAY_MS, 1).kind).toBe('complete');
    });
    test('the instant is spelled in UTC, with the weekday and never "today"', () => {
        expect(spelledInstant(at)).toBe('18:23 UTC on Sunday 27 September');
        expect(completenessSentence({ kind: 'complete', finished: at })).toBe('The latest run on this page finished at 18:23 UTC on Sunday 27 September. A run still going is not on this page yet.');
        expect(completenessSentence({ kind: 'behind', finished: at, missingDays: 1 })).toBe('Nothing has been recorded since 18:23 UTC on Sunday 27 September. 1 day is missing.');
        expect(completenessSentence({ kind: 'behind', finished: at, missingDays: 4 })).toBe('Nothing has been recorded since 18:23 UTC on Sunday 27 September. 4 days are missing.');
    });
    test('the page looks again at the next 00:00 UTC and not before', () => {
        expect(untilNextUtcDay(at)).toBe(midnight + DAY_MS - at);
        expect(untilNextUtcDay(midnight)).toBe(DAY_MS);
    });
});
