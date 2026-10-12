import { test, expect } from '@playwright/test';
import type { SourceHealthRow, SourceHealthView } from '../src/lib/server/payload';
import { retiring } from '../src/lib/server/source-retiring';
/** A source the census names, with every count it was judged on. */
function source(over: Partial<SourceHealthRow> & Pick<SourceHealthRow, 'source_id'>): SourceHealthRow {
    return {
        title: `The ${over.source_id} desk`,
        vertical: 'world',
        permission: 'allowed',
        availability: 'answering',
        retired: false,
        retired_on: null,
        opportunities: 0,
        publications: 0,
        source_failures: 0,
        reliability: 1,
        reliability_reads: 0,
        recent_days: [],
        days_under_the_mark: 0,
        retires_on: null,
        ...over
    };
}
/** The census's five-day axis, oldest first. */
const DATES = ['2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14', '2030-06-15'];
/** One day of a source's share on the census's five-day axis. */
function day(date: string, publications: number, failures: number) {
    return { date, opportunities: publications + failures, publications, source_failures: failures };
}
/** A source's five days on that axis, oldest first, each as published and lost. */
function days(shares: [
    number,
    number
][]) {
    return shares.map(([kept, lost], at) => day(DATES[at], kept, lost));
}
/** A census of 20 complete days, judged at 7 of them and 30 decisions, with a mark of
 *  half the addresses a source decides and a dwell of 14 days.
 *
 *  - `gone` was retired on 10 Jun 2030: 3 of 40 decided, nothing running now.
 *  - `falling` published 12 of the 40 it decided, under the mark for its newest 3 days.
 *  - `sliding` published 15 of 35, under the mark for its newest day.
 *  - `steady` published 30 of 40 and is at or above the mark.
 *  - `thin` decided 5 of the 9 it was offered, under both evidence floors.
 */
function census(): SourceHealthView {
    return {
        generated_at: '2030-06-15T19:00:00Z',
        run_id: '2030-06-15-1',
        headline_sentence: 'Five sources were read.',
        reliability_floor: 0.5,
        reliability_window_days: 30,
        min_complete_days: 7,
        complete_dates: 20,
        yield_readable: true,
        first_date: '2030-05-27',
        last_date: '2030-06-15',
        yield_alarm_point: 0.5,
        yield_alarm_min_decisions: 30,
        dwell_days: 14,
        auto_retire: false,
        dwell_dates: DATES,
        sources: [
            source({ source_id: 'gone', retired: true, retired_on: '2030-06-10', opportunities: 45, publications: 3, source_failures: 37 }),
            source({
                source_id: 'falling',
                opportunities: 45,
                publications: 12,
                source_failures: 28,
                recent_days: days([[6, 4], [5, 5], [1, 9], [2, 8], [0, 10]]),
                days_under_the_mark: 3,
                retires_on: '2030-06-26'
            }),
            source({
                source_id: 'sliding',
                opportunities: 40,
                publications: 15,
                source_failures: 20,
                recent_days: days([[7, 3], [6, 4], [8, 2], [5, 5], [3, 7]]),
                days_under_the_mark: 1,
                retires_on: '2030-06-28'
            }),
            source({ source_id: 'steady', opportunities: 44, publications: 30, source_failures: 10 }),
            source({ source_id: 'thin', opportunities: 9, publications: 2, source_failures: 3 })
        ]
    };
}
test('every row draws its bar on the same track with its marker at the same share', () => {
    // The whole reason to stack these is that a column means the same thing all the
    // way down. A per-row maximum, or a marker at a different x on different rows,
    // makes the stack unreadable while looking perfectly fine. Three ranked rows at
    // three shares: each bar's fill is its own share, and each track and marker are
    // the same.
    const strip = retiring(census(), 10);
    expect(strip?.rows.map((row) => row.sourceId)).toEqual(['gone', 'falling', 'sliding']);
    for (const row of strip?.rows ?? []) {
        expect(row.marks.track, `${row.sourceId} is drawn on its own track`).toBe(1);
        expect(row.marks.markerFraction, `${row.sourceId} puts the mark elsewhere`).toBe(0.5);
    }
    expect(strip?.rows.map((row) => row.marks.valueFraction)).toEqual([3 / 40, 12 / 40, 15 / 35]);
});
test('the dwell is an area under the newest squares, not a number in a chip', () => {
    // On a five-day axis, a run of 3 days under the mark is underlined from the third
    // square to the newest, and a run of 1 day under the newest square alone. A day
    // that decided nothing breaks no run, so `pausing` - under the mark, then a day it
    // decided nothing, then under the mark again - counts 2 days and is underlined
    // from the third square too: the older of its two days under the mark. A row with
    // no run under way draws no rule at all, and neither does `overcounted`, whose
    // count of 3 its squares cannot hold because a day at or above the mark sits two
    // squares back. The producer never writes such a row; any rule drawn for it would
    // underline a day at or above the mark. Which days are under the mark is the
    // run's own count, and `backend/tests/test_source_dwell.py` holds it.
    const view = census();
    const pausing = source({
        source_id: 'pausing',
        opportunities: 45,
        publications: 16,
        source_failures: 24,
        recent_days: days([[7, 3], [6, 4], [1, 9], [0, 0], [2, 8]]),
        days_under_the_mark: 2,
        retires_on: '2030-06-27'
    });
    const overcounted = source({
        source_id: 'overcounted',
        opportunities: 55,
        publications: 10,
        source_failures: 40,
        recent_days: days([[1, 9], [2, 8], [6, 4], [0, 10], [1, 9]]),
        days_under_the_mark: 3,
        retires_on: '2030-06-26'
    });
    const strip = retiring({ ...view, sources: [...view.sources, pausing, overcounted] }, 10);
    expect(strip?.dates).toHaveLength(5);
    expect(strip?.rows.map((row) => [row.sourceId, row.daysUnder, row.dwellFrom])).toEqual([
        ['gone', 0, null],
        ['overcounted', 3, null],
        ['falling', 3, 3],
        ['pausing', 2, 3],
        ['sliding', 1, 5]
    ]);
});
test('a live countdown reads its days and its date without colour', () => {
    // The line under each row says what it published of what it was offered, and
    // while it is under the mark, for how long and the day it retires on; the chip
    // counts the days left. A row under its evidence floors says how much it decided.
    const strip = retiring(census(), 10);
    expect(strip?.rows.map((row) => [row.sourceId, row.daysLeft, row.readout])).toEqual([
        ['gone', null, '3 published of 45 offered, over 20 complete days.'],
        [
            'falling',
            11,
            '12 published of 45 offered, over 20 complete days. Under the mark for 3 days running - 3 of 14. Retires on 2030-06-26 if it stays there.'
        ],
        [
            'sliding',
            13,
            '15 published of 40 offered, over 20 complete days. Under the mark for 1 day running - 1 of 14. Retires on 2030-06-28 if it stays there.'
        ]
    ]);
    expect(strip?.unjudged.map((row) => [row.sourceId, row.readout])).toEqual([
        ['thin', 'Decided 5 of the 9 addresses it was offered.']
    ]);
    expect(strip?.clear, 'steady is the one judged source at or above the mark').toBe(1);
});
