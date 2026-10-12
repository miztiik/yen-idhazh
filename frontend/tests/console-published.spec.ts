/** Deterministic published rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { publishedSkyline, publishingHorizon, siteCost } from '../src/lib/charts/glance';
import type { GlanceDay } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';
const FRONTEND = resolve(process.cwd());
const CONFIG = JSON.parse(readFileSync(resolve(FRONTEND, '..', 'config', 'appearance.json'), 'utf8')) as {
    console?: {
        window_presets?: number[];
        default_window_days?: number;
    };
};
const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
function day(date: string, published: number, items = published): GlanceDay {
    return { date, published, items, minutesPerChart: null };
}
function summary(date: string, siteBytes: number): RunSummary {
    return { date, runs: 1, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}
test('the window decides the columns, not the days that carry a run', () => {
    const sparse = publishedSkyline([day('2026-08-27', 4), day('2026-08-28', 8)], { start: '2026-08-22', end: '2026-08-28' });
    expect(sparse.bars.map((bar) => bar.date)).toEqual([
        '2026-08-22',
        '2026-08-23',
        '2026-08-24',
        '2026-08-25',
        '2026-08-26',
        '2026-08-27',
        '2026-08-28'
    ]);
    expect(sparse.bars.map((bar) => bar.published)).toEqual([0, 0, 0, 0, 0, 4, 8]);
    expect(sparse.busiest).toBe(8);
    expect(sparse.bars.map((bar) => bar.height)).toEqual([0, 0, 0, 0, 0, 0.5, 1]);
    expect(sparse.total).toBe(12);
    expect(sparse.empty).toBe(false);
});
test('a day outside the window is outside the count as well as the picture', () => {
    const window = { start: '2026-08-26', end: '2026-08-28' };
    const skyline = publishedSkyline([day('2026-08-20', 100), day('2026-08-27', 3), day('2026-08-28', 5)], window);
    expect(skyline.bars.length).toBe(3);
    expect(skyline.total).toBe(8);
    expect(skyline.total).toBe(skyline.bars.reduce((sum, bar) => sum + bar.published, 0));
});
test('a window that published nothing says so rather than drawing thirty zeros', () => {
    const quiet = publishedSkyline([day('2026-08-27', 0)], {
        start: '2026-08-26',
        end: '2026-08-28'
    });
    expect(quiet.empty).toBe(true);
    expect(quiet.busiest).toBe(0);
    expect(quiet.bars.every((bar) => bar.height === 0)).toBe(true);
    expect(publishedSkyline([], { start: '2026-08-26', end: '2026-08-28' }).empty).toBe(true);
});
test('the bars sit inside the box and never touch each other', () => {
    for (const days of PRESETS) {
        const end = '2026-08-28';
        const start = new Date(Date.parse(`${end}T00:00:00Z`) - (days - 1) * 86_400_000)
            .toISOString()
            .slice(0, 10);
        const skyline = publishedSkyline([day(end, 1)], { start, end });
        expect(skyline.bars.length, `${days} days drew ${skyline.bars.length} bars`).toBe(days);
        for (const [index, bar] of skyline.bars.entries()) {
            expect(bar.x, `${days} days: bar ${index} starts left of the box`).toBeGreaterThanOrEqual(0);
            expect(bar.x + bar.width, `${days} days: bar ${index} runs past the box`).toBeLessThanOrEqual(1.000001);
            const next = skyline.bars[index + 1];
            if (next)
                expect(bar.x + bar.width).toBeLessThanOrEqual(next.x + 0.000001);
        }
    }
});
test('one function draws both strips, so their geometry cannot drift', () => {
    const span = { start: '2026-08-26', end: '2026-08-28' };
    const days = [day('2026-08-27', 1, 40), day('2026-08-28', 3, 60)];
    const visuals = publishedSkyline(days, span, 'published');
    const articles = publishedSkyline(days, span, 'items');
    expect(articles.bars.map((bar) => bar.published)).toEqual([0, 40, 60]);
    expect(visuals.bars.map((bar) => bar.published)).toEqual([0, 1, 3]);
    expect(articles.total).toBe(100);
    expect(visuals.total).toBe(4);
    expect(articles.bars.map((bar) => bar.date)).toEqual(visuals.bars.map((bar) => bar.date));
    expect(articles.bars.map((bar) => bar.x)).toEqual(visuals.bars.map((bar) => bar.x));
    expect(articles.bars.map((bar) => bar.width)).toEqual(visuals.bars.map((bar) => bar.width));
    expect(articles.busiest).toBe(60);
    expect(visuals.busiest).toBe(3);
});
test('the horizon needs both rates, and prints nothing without either', () => {
    const runs = [
        summary('2026-08-01', 1000000),
        summary('2026-08-02', 1300000),
        summary('2026-08-03', 1600000)
    ];
    const items = new Map([
        ['2026-08-01', 100],
        ['2026-08-02', 100],
        ['2026-08-03', 100]
    ]);
    const cost = siteCost(runs, items);
    expect(cost.median).toBe(3000);
    const horizon = publishingHorizon(1600000, cost, items, 10000000);
    expect(horizon).not.toBeNull();
    expect(horizon?.articles).toBe((10000000 - 1600000) / 3000);
    expect(horizon?.articlesPerDay).toBe(100);
    expect(horizon?.years).toBeCloseTo((10000000 - 1600000) / 3000 / 100 / 365.25, 6);
    expect(publishingHorizon(null, cost, items, 10000000)).toBeNull();
    expect(publishingHorizon(1600000, { ...cost, median: null }, items, 10000000)).toBeNull();
    expect(publishingHorizon(1600000, cost, new Map(), 10000000)).toBeNull();
});
