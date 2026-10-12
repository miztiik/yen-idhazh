/** Deterministic site size rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { PAGES_CAP_BYTES, siteCost, publishingHorizon, type SiteCost } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';
function manifest(date: string, siteBytes: number): RunSummary {
    return { date, runs: 1, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}
const DAYS: {
    date: string;
    bytes: number;
    items: number;
    expected: number | null;
}[] = [
    { date: '2026-08-01', bytes: 1000000, items: 100, expected: null },
    { date: '2026-08-02', bytes: 1300000, items: 100, expected: 3000 },
    { date: '2026-08-03', bytes: 1600000, items: 100, expected: 3000 },
    { date: '2026-08-04', bytes: 1900000, items: 100, expected: 3000 },
    { date: '2026-08-05', bytes: 2400000, items: 100, expected: 5000 },
    { date: '2026-08-06', bytes: 2500000, items: 100, expected: 1000 },
    { date: '2026-08-07', bytes: 2800000, items: 100, expected: 3000 },
    { date: '2026-08-08', bytes: 2800000, items: 0, expected: null },
    { date: '2026-08-09', bytes: 3100000, items: 100, expected: 3000 }
];
const MANIFESTS = DAYS.map((day) => manifest(day.date, day.bytes));
const ITEMS = new Map(DAYS.map((day) => [day.date, day.items]));
function band(values: number[]): {
    median: number;
    spread: number;
} {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    const spread = Math.sqrt(values.reduce((sum, value) => sum + (value - median) ** 2, 0) / values.length);
    return { median, spread };
}
function outside(dates: string[], values: number[]): string[] {
    const { median, spread } = band(values);
    return dates.filter((_, i) => Math.abs(values[i] - median) > spread);
}
test('a day costs its own bytes over its own articles, and a day with none has no cost', () => {
    const cost = siteCost(MANIFESTS, ITEMS);
    expect(cost.empty).toBe(false);
    expect(cost.days.map((day) => [day.date, Math.round(day.bytesPerItem)]), 'a day the tree grew on but nothing was published cannot report a rate').toEqual(DAYS.filter((day) => day.expected !== null).map((day) => [day.date, day.expected]));
});
test('THE ORACLE: the flagged days are the days outside one standard deviation of the median', () => {
    const cost = siteCost(MANIFESTS, ITEMS);
    const values = cost.days.map((day) => day.bytesPerItem);
    const expected = outside(cost.days.map((day) => day.date), values);
    expect(expected, 'the fixture stopped producing an outlier in each direction').toEqual([
        '2026-08-05',
        '2026-08-06'
    ]);
    expect(cost.days.filter((day) => day.flagged).map((day) => day.date), 'the chart flags a different set of days than the rule does').toEqual(expected);
    expect(Math.round(cost.median ?? 0)).toBe(3000);
    expect(Math.round(cost.spread ?? 0)).toBe(Math.round(band(values).spread));
});
test('the window bounds what is drawn and never what is differenced', () => {
    const cost = siteCost(MANIFESTS, ITEMS, { start: '2026-08-04', end: '2026-08-09' });
    expect(cost.days.map((day) => day.date)).toEqual([
        '2026-08-04',
        '2026-08-05',
        '2026-08-06',
        '2026-08-07',
        '2026-08-09'
    ]);
    expect(Math.round(cost.days[0].bytesPerItem)).toBe(3000);
    expect(cost.days.filter((day) => day.flagged).map((day) => day.date)).toEqual(outside(cost.days.map((day) => day.date), cost.days.map((day) => day.bytesPerItem)));
});
test('one day is not a spread, and a window with no published day has no cost', () => {
    const single = siteCost(MANIFESTS, ITEMS, { start: '2026-08-02', end: '2026-08-02' });
    expect(single.days).toHaveLength(1);
    expect(single.spread, 'a spread taken over one number is not a spread').toBeNull();
    expect(single.days[0].flagged, 'one day cannot be unusual relative to itself').toBe(false);
    const none = siteCost(MANIFESTS, ITEMS, { start: '2026-08-08', end: '2026-08-08' });
    expect(none.empty).toBe(true);
    expect(none.median).toBeNull();
});
test('the runway is headroom over one article, and absent where there is no rate', () => {
    const used = 100000000;
    const alarm = 800 * 1024 * 1024;
    const cost = siteCost(MANIFESTS, ITEMS);
    const runway = publishingHorizon(used, cost, ITEMS, PAGES_CAP_BYTES);
    expect(runway).not.toBeNull();
    expect(Math.round(runway?.articles ?? 0)).toBe(Math.round((PAGES_CAP_BYTES - used) / 3000));
    expect(Math.round(publishingHorizon(used, cost, ITEMS, alarm)?.articles ?? 0)).toBe(Math.round((alarm - used) / 3000));
    for (const median of [null, 0, -2000]) {
        const absent: SiteCost = { ...cost, median };
        expect(publishingHorizon(used, absent, ITEMS)).toBeNull();
    }
});
