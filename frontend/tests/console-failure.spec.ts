/** Deterministic failure rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { failureLoad } from '../src/lib/charts/glance';
import { failureSeries, type TelemetryRow } from '../src/lib/charts/series';
import { telemetryRow } from './support/telemetry-row';
const MIN_ATTEMPTS_FOR_RATE = (JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')) as {
    console?: {
        min_attempts_for_rate?: number;
    };
}).console?.min_attempts_for_rate ?? 5;
function row(date: string, id: string, stage: string, outcome: string, code = ''): TelemetryRow {
    return telemetryRow({
        date,
        run_id: `${date}-1`,
        item_id: id,
        source_id: 'fixture',
        stage,
        outcome,
        code,
        source_words: 400,
        summary_words: 60
    });
}
test('a stage is measured against what reached it, never against the day', () => {
    const rows = [
        ...Array.from({ length: 4 }, (_, i) => row('2026-08-20', `f${i}`, 'fetch', 'failed', 'no_text')),
        ...Array.from({ length: 2 }, (_, i) => row('2026-08-20', `e${i}`, 'extract', 'failed', 'too_short')),
        row('2026-08-20', 's0', 'summarize', 'failed', 'bad_shape'),
        ...Array.from({ length: 3 }, (_, i) => row('2026-08-20', `p${i}`, 'publish', 'ok'))
    ];
    const series = failureSeries(rows, { start: '2026-08-20', end: '2026-08-20' });
    const day = (stage: string) => series.find((s) => s.stage === stage)?.days[0];
    expect(day('fetch')).toMatchObject({ planned: 10, reached: 10, failures: 4, rate: 0.4 });
    expect(day('extract')).toMatchObject({ planned: 10, reached: 6, failures: 2 });
    expect(day('extract')?.rate).toBeCloseTo(2 / 6, 10);
    expect(day('summarize')).toMatchObject({ planned: 10, reached: 4, failures: 1, rate: 0.25 });
    const withSkipped = failureSeries([...rows, row('2026-08-20', 'x0', 'plan', 'failed')], {
        start: '2026-08-20',
        end: '2026-08-20'
    });
    expect(withSkipped[0].days[0]).toMatchObject({ planned: 11, reached: 10, failures: 4 });
});
test('a rate is given where the denominator holds and withheld where it does not', () => {
    const rows = [
        ...Array.from({ length: 6 }, (_, i) => row('2026-08-20', `f${i}`, 'fetch', 'failed', 'no_text')),
        row('2026-08-20', 's0', 'summarize', 'failed', 'bad_shape'),
        ...Array.from({ length: 3 }, (_, i) => row('2026-08-20', `p${i}`, 'publish', 'ok'))
    ];
    const load = failureLoad(failureSeries(rows, { start: '2026-08-20', end: '2026-08-20' }), MIN_ATTEMPTS_FOR_RATE);
    const stage = (name: string) => load.stages.find((s) => s.stage === name);
    expect(MIN_ATTEMPTS_FOR_RATE, 'the fixture is built around a knob of 5').toBe(5);
    expect(stage('fetch')).toMatchObject({ reached: 10, failures: 6, rate: 0.6, lowSample: false });
    expect(stage('summarize')).toMatchObject({ reached: 4, failures: 1, rate: null, lowSample: true });
    const nothing = failureLoad(failureSeries([], { start: '2026-08-20', end: '2026-08-20' }), MIN_ATTEMPTS_FOR_RATE);
    expect(nothing.stages[0]).toMatchObject({ reached: 0, rate: null, lowSample: false });
    expect(nothing.empty).toBe(true);
});
test('the column is the day, and no band in it is a residue', () => {
    const rows = [
        row('2026-08-20', 'x0', 'plan', 'failed', 'not_attempted'),
        ...Array.from({ length: 4 }, (_, i) => row('2026-08-20', `f${i}`, 'fetch', 'failed', 'no_text')),
        row('2026-08-20', 'e0', 'extract', 'failed', 'too_short'),
        row('2026-08-20', 's0', 'summarize', 'failed', 'bad_shape'),
        ...Array.from({ length: 3 }, (_, i) => row('2026-08-20', `p${i}`, 'publish', 'ok'))
    ];
    const load = failureLoad(failureSeries(rows, { start: '2026-08-20', end: '2026-08-20' }), MIN_ATTEMPTS_FOR_RATE);
    const column = load.columns[0];
    expect(column.planned).toBe(10);
    expect(column.bands.reduce((sum, band) => sum + band.value, 0)).toBe(column.planned);
    expect(column.bands.map((band) => `${band.key}:${band.value}`)).toEqual([
        'finished:3',
        'fetch:4',
        'extract:1',
        'summarize:1',
        'skipped:1'
    ]);
    expect(load.peak).toBe(10);
});
test('a day too thin to divide breaks the line rather than drawing a share', () => {
    const rows = [
        row('2026-08-19', 'a0', 'publish', 'ok'),
        ...Array.from({ length: 8 }, (_, i) => row('2026-08-20', `b${i}`, 'publish', 'ok')),
        row('2026-08-20', 'b8', 'fetch', 'failed', 'no_text')
    ];
    const load = failureLoad(failureSeries(rows, { start: '2026-08-19', end: '2026-08-20' }), MIN_ATTEMPTS_FOR_RATE);
    const fetch = load.stages[0];
    expect(fetch.points.map((point) => point.date)).toEqual(['2026-08-19', '2026-08-20']);
    expect(fetch.points[0]).toMatchObject({ rate: null, reached: 1 });
    expect(fetch.points[1]).toMatchObject({ rate: 1 / 9, reached: 9 });
});
