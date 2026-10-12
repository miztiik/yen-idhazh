import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { archiveCalendar, dayDate, type ArchiveDay } from '../src/lib/archive-calendar';
/**
 * The archive's day list stops growing one link a published day.
 *
 * The Oracle this row is held to: a fixture archive of 700 published days
 * renders at most `archive_recent_days` rows plus one row per month plus one
 * row per prior year, and every one of those 700 days is still reachable with
 * no script at all.
 *
 * The 700-day case is driven in Node rather than in a page, for the reason
 * `archive-scope.spec.ts` is: the canary build publishes twenty days in one
 * month, and a rule about two years of months cannot show up in it. The
 * browser cases below hold the parts only a real document can answer - that the
 * rows are there, that a month is shut at rest, and that a `<details>` opens
 * and its links navigate with scripting switched off.
 *
 * What this file does NOT hold is the page's weight. That was measured by hand
 * on two fixture archives and is recorded in `docs/reference/pipeline-cost.md`;
 * there is no ratchet file to keep it, and a build-to-build byte comparison on
 * a developer machine is noise (`docs/reference/agent-notes.md`).
 */
const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
/** How many days the archive lists as rows of their own, off the committed config. */
function recentDays(): number {
    const parsed = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
        digest?: {
            archive_recent_days?: number;
        };
    };
    const days = parsed.digest?.archive_recent_days;
    expect(days, 'config/appearance.json no longer sets digest.archive_recent_days').toBeDefined();
    return days as number;
}
/** `count` consecutive published days ending on `last`, newest first. */
function consecutive(count: number, last: string): ArchiveDay[] {
    const end = Date.parse(`${last}T00:00:00Z`);
    return Array.from({ length: count }, (_, back) => ({
        date: new Date(end - back * 86400000).toISOString().slice(0, 10),
        items: 10,
        partial: false
    }));
}
test.describe('the calendar at seven hundred days', () => {
    // 700 days ending 1 September 2026 starts on 2 October 2024: 244 days of
    // 2026 up to and including 1 September, all 365 of 2025, and 91 of 2024.
    const days = consecutive(700, '2026-09-01');
    const calendar = archiveCalendar(days);
    test('the reader meets rows in the tens, not links in the hundreds', () => {
        expect(days[0]!.date).toBe('2026-09-01');
        expect(days[699]!.date).toBe('2024-10-02');
        // January to September of the newest published year.
        expect(calendar.months.map((month) => month.month)).toEqual([
            '2026-09',
            '2026-08',
            '2026-07',
            '2026-06',
            '2026-05',
            '2026-04',
            '2026-03',
            '2026-02',
            '2026-01'
        ]);
        expect(calendar.years.map((year) => year.year)).toEqual(['2025', '2024']);
        // The day rows the config asks for, a row for each month of this year, and
        // a row for each year before it: 14 + 9 + 2. The first term is
        // `digest.archive_recent_days`, which moved from seven to fourteen on
        // 2026-09-06 and took this total from 18 to 25 with it.
        const atRest = recentDays() + calendar.months.length + calendar.years.length;
        expect(atRest, 'the day list is meant to be scannable at 700 days').toBe(25);
        // And even with every year opened, the ceiling is a row a month: 14 + 24 + 2.
        const everyMonth = calendar.months.length +
            calendar.years.reduce((count, year) => count + year.months.length, 0);
        expect(recentDays() + everyMonth + calendar.years.length).toBeLessThanOrEqual(40);
    });
    test('no day is dropped, and no day is reachable twice from the calendar', () => {
        const reached: string[] = [];
        for (const month of [
            ...calendar.months,
            ...calendar.years.flatMap((year) => year.months)
        ]) {
            for (const day of month.days)
                reached.push(dayDate(month.month, day));
        }
        expect(new Set(reached).size, 'a date is behind two different months').toBe(reached.length);
        expect([...reached].sort()).toEqual(days.map((day) => day.date).sort());
    });
    test('a month row states its own span, and the spans add up', () => {
        const august = calendar.months.find((month) => month.month === '2026-08');
        expect(august).toBeDefined();
        expect(august!.label).toBe('August 2026');
        expect(august!.length, 'August has 31 days').toBe(31);
        expect(august!.days.length).toBe(31);
        expect(august!.stories).toBe(310);
        // The oldest month in the window published 30 of its 31 days, which is the
        // row that proves the denominator is the calendar rather than what we hold.
        const october = calendar.years
            .find((year) => year.year === '2024')!
            .months.find((month) => month.month === '2024-10')!;
        expect(october.days.length).toBe(30);
        expect(october.length).toBe(31);
        const leap = calendar.years.find((year) => year.year === '2024')!;
        expect(leap.length, '2024 is a leap year').toBe(366);
        expect(leap.days).toBe(91);
        expect(calendar.years.find((year) => year.year === '2025')!.length).toBe(365);
    });
    test('a month with a gap in it still says how many days it holds', () => {
        // Every other day of one month, which is the shape a run that failed leaves.
        const sparse = archiveCalendar([2, 4, 6, 8].map((day) => ({ date: `2026-04-0${day}`, items: 3, partial: false })));
        const april = sparse.months[0]!;
        expect(april.days).toEqual([8, 6, 4, 2]);
        expect(april.length).toBe(30);
        expect(april.stories).toBe(12);
        expect(sparse.years).toEqual([]);
    });
    test('an archive that has published nothing is a calendar with no rows', () => {
        expect(archiveCalendar([])).toEqual({ months: [], years: [] });
    });
});
