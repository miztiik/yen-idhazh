/** Deterministic charts rule rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chartRule, coverageOf, type ChartThresholds, type GlanceDay } from '../src/lib/charts/glance';
import { targetGeometry } from '../src/lib/charts/targetbar';
import { numberFormat } from './support/number-format';
const REPO = resolve(process.cwd(), '..');
const CONFIG = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
    console?: {
        window_presets?: number[];
        default_window_days?: number;
        chart_rule_days?: number;
        chart_minutes_target?: number;
        chart_coverage_pct?: number;
    };
};
const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const THRESHOLDS: ChartThresholds = {
    ruleDays: CONFIG.console?.chart_rule_days ?? 14,
    minutesTarget: CONFIG.console?.chart_minutes_target ?? 6,
    coveragePct: CONFIG.console?.chart_coverage_pct ?? 5
};
const NARROW = PRESETS.filter((days) => days < THRESHOLDS.ruleDays).at(-1) as number;
const WIDE = PRESETS.filter((days) => days >= THRESHOLDS.ruleDays)[0];
function day(date: string, over: Partial<GlanceDay> = {}): GlanceDay {
    return { date, published: 0, items: 0, minutesPerChart: null, ...over };
}
const chartRuleFor = (days: readonly GlanceDay[], thresholds: ChartThresholds, windowDays: number) =>
    chartRule(days, thresholds, windowDays, numberFormat);
test.describe('the arithmetic behind the two bars', () => {
    test('a share of nothing is an absence, never zero percent', () => {
        expect(coverageOf(day('2026-08-01'))).toBeNull();
        expect(coverageOf(day('2026-08-02', { items: 8, published: 1 }))).toBeCloseTo(12.5, 6);
        expect(coverageOf(day('2026-08-03', { items: 4, published: 4 }))).toBe(100);
    });
    test('the median is the middle day, so one ruinous day cannot decide the rule', () => {
        const days = [
            day('2026-08-01', { items: 10, published: 1, minutesPerChart: 2 }),
            day('2026-08-02', { items: 10, published: 1, minutesPerChart: 3 }),
            day('2026-08-03', { items: 10, published: 1, minutesPerChart: 40 })
        ];
        const rule = chartRuleFor(days, THRESHOLDS, WIDE);
        expect(rule.minutes).toBe(3);
        expect(rule.coverage).toBe(10);
        const mean = (2 + 3 + 40) / 3;
        expect(rule.minutes).toBeLessThan(mean);
    });
    test('an even count of days averages the middle pair', () => {
        const days = [4, 2, 8, 6].map((m, i) => day(`2026-08-0${i + 1}`, { items: 10, published: 1, minutesPerChart: m }));
        expect(chartRuleFor(days, THRESHOLDS, WIDE).minutes).toBe(5);
    });
    test('below the rule span nothing is measured, and the bars are empty', () => {
        const days = [
            day('2026-08-01', { items: 10, published: 5, minutesPerChart: 1 }),
            day('2026-08-02', { items: 10, published: 5, minutesPerChart: 1 })
        ];
        const rule = chartRuleFor(days, THRESHOLDS, NARROW);
        expect(rule.narrow).toBe(true);
        expect(rule.minutes).toBeNull();
        expect(rule.coverage).toBeNull();
        expect(rule.minutesMarks.empty).toBe(true);
        expect(rule.coverageMarks.empty).toBe(true);
        expect(rule.minutesTrend.empty).toBe(true);
        const wide = chartRuleFor(days, THRESHOLDS, WIDE);
        expect(wide.narrow).toBe(false);
        expect(wide.minutes).toBe(1);
        expect(wide.coverage).toBe(50);
    });
    test('the verdict names both figures and which side of each threshold they fell', () => {
        const inside = chartRuleFor([day('2026-08-01', { items: 10, published: 5, minutesPerChart: 1 })], THRESHOLDS, WIDE);
        expect(inside.verdict).toContain('1 minutes per visual');
        expect(inside.verdict).toContain('inside');
        expect(inside.verdict).toContain('50% of what it published');
        expect(inside.verdict).toContain('above');
        const outside = chartRuleFor([day('2026-08-01', { items: 100, published: 1, minutesPerChart: 40 })], THRESHOLDS, WIDE);
        expect(outside.verdict).toContain('past');
        expect(outside.verdict).toContain('below');
        expect((outside.verdict.match(/\.(\s|$)/g) ?? []).length).toBe(1);
    });
    test('a window with nothing in it says so rather than printing a zero', () => {
        const rule = chartRuleFor([day('2026-08-01')], THRESHOLDS, WIDE);
        expect(rule.minutes).toBeNull();
        expect(rule.coverage).toBeNull();
        expect(rule.verdict).toContain('has no minutes on record');
        expect(rule.verdict).toContain('no day published anything to put a visual on');
        expect(rule.verdict.startsWith('The median day')).toBe(true);
    });
    test('each trend carries one point per measured day, oldest first', () => {
        const days = [
            day('2026-08-03', { items: 10, published: 3, minutesPerChart: 9 }),
            day('2026-08-02', { items: 10, published: 2, minutesPerChart: 5 }),
            day('2026-08-01', { items: 10, published: 1, minutesPerChart: 1 })
        ];
        const rule = chartRuleFor(days, THRESHOLDS, WIDE);
        expect(rule.minutesDays).toBe(3);
        expect(rule.coverageDays).toBe(3);
        expect(rule.minutesTrend.values).toEqual([1, 5, 9]);
        expect(rule.coverageTrend.values).toEqual([10, 20, 30]);
        expect(rule.minutesTrend.rising).toBe(true);
        const single = chartRuleFor([days[0]], THRESHOLDS, WIDE);
        expect(single.minutesDays).toBe(1);
        expect(single.minutesTrend.empty).toBe(true);
    });
    test('the marker sits at the threshold on both bars, and the senses are opposite', () => {
        const days = [day('2026-08-01', { items: 100, published: 20, minutesPerChart: 9 })];
        const rule = chartRuleFor(days, THRESHOLDS, WIDE);
        expect(rule.minutesMarks.markerFraction).toBeCloseTo(targetGeometry(9, THRESHOLDS.minutesTarget, 'lower-is-better').markerFraction, 9);
        expect(rule.coverageMarks.markerFraction).toBeCloseTo(targetGeometry(20, THRESHOLDS.coveragePct, 'higher-is-better').markerFraction, 9);
        expect(rule.minutesMarks.band).toBe('past');
        expect(rule.coverageMarks.band).toBe('good');
    });
});
