/** Deterministic published rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { publishedSkyline, publishingHorizon, siteCost } from '../src/lib/charts/glance';
import type { GlanceDay } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';
import { chartConfig, consoleConfig } from '../src/lib/server/config';
import { serverCompiler, renderConfigured } from './support/server-render';
import { pathToFileURL } from 'node:url';
import type { Component } from 'svelte';
import { atAGlance } from '../src/lib/console/pipelines/at-a-glance';
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
    expect(sparse.bars.map((bar) => bar.measured)).toEqual([false, false, false, false, false, true, true]);
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
            expect((bar.x + bar.width / 2) * days, `${bar.date} must sit in its own calendar slot`).toBeCloseTo(index + 0.5);
            const next = skyline.bars[index + 1];
            if (next)
                expect(bar.x + bar.width).toBeLessThanOrEqual(next.x + 0.000001);
        }
    }
});
test.describe('the published cards draw their calendar, not just the selected date', () => {
    let component: Component<Record<string, unknown>>;
    test.beforeAll(async ({}, info) => {
        const compile = serverCompiler(info.outputPath('published-cards'));
        const rewrites = [
            ['$lib/components/KpiCard.svelte', './KpiCard.server.mjs'],
            ['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs']
        ] as const;
        await compile('src/lib/components/KpiCard.svelte', 'KpiCard', rewrites);
        await compile('src/lib/components/ChartReadout.svelte', 'ChartReadout', rewrites);
        const module = await compile('src/lib/console/pipelines/AtAGlance.svelte', 'AtAGlance', rewrites);
        component = (await import(pathToFileURL(module).href)).default;
    });
    const recorded = (date: string, articles: number, visuals: number) => ({
        ...day(date, visuals, articles), reached: articles, asked: articles, drafted: visuals, plannerMinutes: null
    });
    function cards(width: number, days: ReturnType<typeof recorded>[], start: string, end: string,
        publishedItems = Object.fromEntries(days.map((day) => [day.date, day.items]))) {
        return renderConfigured(component, { props: {
            days, publishedItems, window: { start, end }, knobs: { ...consoleConfig(), chart_width: width }, chart: chartConfig()
        } }).body;
    }
    test('both card axes span leap day, thin to real dates on a narrow card, and keep their original counts', () => {
        const days = [recorded('2028-02-27', 40, 1), recorded('2028-03-01', 60, 3)];
        const axes = (body: string) => [...body.matchAll(/data-day-axis="([^"]+)"/g)].map((match) => match[1]);
        const wide = cards(640, days, '2028-02-27', '2028-03-01');
        const narrow = cards(180, days, '2028-02-27', '2028-03-01');
        for (const body of [wide, narrow]) {
            expect(body).toContain('data-published-total="100"');
            expect(body).toContain('data-published-total="4"');
            expect(body).toContain('data-published-bar="2028-02-29"');
            expect(axes(body).filter((date) => date === '2028-02-27')).toHaveLength(2);
            expect(axes(body).filter((date) => date === '2028-03-01')).toHaveLength(2);
            expect(body).not.toContain('data-kpi-note');
            expect(body).not.toContain('in these');
        }
        expect(axes(wide).length).toBeGreaterThan(axes(narrow).length);
    });
    test('one real day has one centered date per card; a measured zero is not an absent record', () => {
        const date = '2028-02-29';
        const body = cards(180, [recorded(date, 0, 0)], date, date);
        expect([...body.matchAll(/data-day-axis="([^"]+)"/g)].map((match) => match[1])).toEqual([date, date]);
        expect(body).toMatch(/<text x="90"[^>]+data-day-axis="2028-02-29"/);
        expect(body).not.toContain('in this one day');
        expect(body).not.toContain('data-kpi-note');
        expect(publishedSkyline([day(date, 0)], { start: date, end: date }).bars[0].measured).toBe(true);
        expect(publishedSkyline([], { start: date, end: date }).bars[0].measured).toBe(false);
        const absent = cards(180, [recorded(date, 0, 0)], date, date, {});
        expect(absent).toContain('The private published-day record is unavailable in this window.');
        expect(absent).not.toContain('data-published-total');
        const partial = atAGlance([recorded('2028-02-28', 0, 0), recorded(date, 6, 2)],
            { start: '2028-02-28', end: date }, { [date]: 6 });
        expect(partial.articles.total).toBe(6);
        expect(partial.visuals.total).toBe(2);
        expect(partial.articles.bars.map((bar) => bar.measured)).toEqual([false, true]);
        expect(partial.visuals.bars.map((bar) => bar.measured)).toEqual([false, true]);
    });
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
