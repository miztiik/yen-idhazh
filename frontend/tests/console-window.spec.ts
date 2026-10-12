/** One shared control, declared surface coverage, and actual cross-route navigation. */
import { expect, test } from './support/door-page';
import { type RouteId } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-window';
import { monthsInWindow, monthsToFetch, stepPreset, windowOfDays } from '../src/lib/charts/viewport';
import { minus, presets } from './support/console-window/controls';
import { config, telemetry } from './support/console-window/controls';
function monthsKept(today: string, months: number): string[] {
    const [year, month] = today.split('-').map(Number);
    const newest = year * 12 + (month - 1);
    return Array.from({ length: months }, (_, index) => {
        const total = newest - (months - 1) + index;
        const stem = String(Math.floor(total / 12)).padStart(4, '0');
        return `${stem}-${String((total % 12) + 1).padStart(2, '0')}`;
    });
}
test('a window of N days is exactly N days, and ends on the day it is handed', () => {
    // It used to shrink to the rows it found. That was invisible while nothing
    // named the span and a lie the moment a control does: a page reading 90 while
    // the charts draw 2 cannot be trusted about anything else. It also used to end
    // on the newest date in the rows it was handed, so a record that stopped moved
    // its window into the past; every route now hands it the newest published day.
    expect(windowOfDays('2026-08-28', 30, 'right')).toEqual({
        start: '2026-07-30',
        end: '2026-08-28'
    });
    expect(windowOfDays('2026-08-28', 7, 'right')).toEqual({
        start: '2026-08-22',
        end: '2026-08-28'
    });
    expect(windowOfDays('2026-08-28', 1, 'right')).toEqual({
        start: '2026-08-28',
        end: '2026-08-28'
    });
    // Centred pushes the end past the day it is handed, which is the anchor's whole
    // purpose: room on the right for days that have not happened yet.
    expect(windowOfDays('2026-08-28', 7, 'centre')).toEqual({
        start: '2026-08-25',
        end: '2026-08-31'
    });
});
test('a step lands on a preset, and stops at the ends rather than wrapping', () => {
    // The ends are read off the list, never written down. Seven was the narrowest
    // preset until a one-day span was added on 2026-09-06, and a literal end
    // stops testing the end the moment the list moves under it.
    const narrowest = Math.min(...presets());
    const widest = Math.max(...presets());
    expect(stepPreset(30, presets(), 1)).toBe(90);
    expect(stepPreset(30, presets(), -1)).toBe(14);
    expect(stepPreset(widest, presets(), 1)).toBe(widest);
    expect(stepPreset(narrowest, presets(), -1)).toBe(narrowest);
    expect(stepPreset(7, presets(), -1)).toBe(1);
    // A span that is not a preset still steps to the neighbouring one, so a
    // window left by a pan cannot strand the keys.
    expect(stepPreset(21, presets(), 1)).toBe(30);
    expect(stepPreset(21, presets(), -1)).toBe(14);
});
test('the cost of widening is the months not already in hand, and never a 404', () => {
    const available = ['2026-06', '2026-07', '2026-08'];
    expect(monthsToFetch({ start: '2026-08-01', end: '2026-08-28' }, available, ['2026-08'])).toEqual([]);
    expect(monthsToFetch({ start: '2026-06-15', end: '2026-08-28' }, available, ['2026-08'])).toEqual(['2026-06', '2026-07']);
    // A month the pipeline never published is not a cost. Asking for it would
    // only produce a 404 and a gap the charts already draw.
    expect(monthsToFetch({ start: '2026-04-01', end: '2026-08-28' }, available, ['2026-08'])).toEqual(['2026-06', '2026-07']);
});
test('the widest window this control offers never names a shard the cleanup age took', () => {
    // The gardener's `telemetry-aggregate` task deletes the browser's copy of a
    // month past its `public-copy` series, and that series must equal the ledger's
    // own `full-grain` one. This is the reader's half of the same promise: over
    // every anchor a year can offer, the months the widest read selects are all
    // months the cleanup kept, so widening costs a fetch and never a 404.
    //
    // It reads both windows rather than 366 and 14, because the two configs are
    // where the pair is set and a test that repeated the numbers would agree with
    // itself after an edit moved them.
    const publicCopy = telemetry().series?.['public-copy'];
    expect(publicCopy?.unit, 'the public copy is kept in whole months').toBe('months');
    const keepMonths = publicCopy?.value ?? 0;
    const maxDays = config().console?.max_window_days ?? 366;
    expect(keepMonths).toBe(telemetry().series?.['full-grain']?.value);
    for (let offset = 0; offset < 366; offset += 1) {
        const today = minus('2026-12-31', offset);
        const kept = monthsKept(today, keepMonths);
        const widest = windowOfDays(today, maxDays, 'right');
        expect(monthsToFetch(widest, kept, []), `a ${maxDays}-day read on ${today} wants a month ${keepMonths} months of cleanup removed`).toEqual(monthsInWindow(widest));
    }
});
for (const [id, declared] of Object.entries(BY_ROUTE) as [
    RouteId,
    (typeof BY_ROUTE)[RouteId]
][]) {
    if (declared === null)
        continue; // The Data explorer has its own explicit window coverage.
}
