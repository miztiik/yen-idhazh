/** Deterministic model instruments rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { DRAWN_BY, EVAL_PANELS, RECORDED, FLAGS, evalDays, flagReadings, recordedReadings, recordedText, type EvalInput } from '../src/lib/console/eval-instruments';
import { numberFormat } from './support/number-format';
const FIXTURE: EvalInput[] = [
    { date: '2026-04-02', hhem: '0.90', hhem_delta: '0', compression: '0.20', coherence: '0.10' },
    { date: '2026-04-02', hhem: '0.80', hhem_delta: '0', compression: '0.40', coherence: '-0.30' },
    { date: '2026-04-01', hhem: '0.50', hhem_delta: '0.10', compression: '0.10' },
    { date: '2026-04-01', hhem: '0.60', hhem_delta: '-0.20', compression: '0.30' },
    { date: '2026-04-01', hhem: '0.70', hhem_delta: '0', compression: '0.50' },
    { date: '2026-04-01', hhem: '0.90', hhem_delta: '0', compression: '0.70' },
    { date: '2026-04-03', hhem: '', compression: '' },
    { date: '', hhem: '0.99' },
    { date: '2026-04-04', hhem: 'n/a', extraction_suspect: 'true' },
    { date: '2026-04-04', hhem: '0.85', determinism_violation: 'True' }
];
test('every measurement receiver is declared once and every declared receiver answers for a measurement', () => {
    const panels = EVAL_PANELS.map((panel) => panel.id);
    expect(new Set(panels).size).toBe(panels.length);
    for (const receiver of Object.values(DRAWN_BY)) expect(panels).toContain(receiver);
    for (const panel of panels) expect(Object.values(DRAWN_BY)).toContain(panel);
});
test('recorded instruments retain their approved receivers without inventing a checker result', () => {
    const receivers: Readonly<Record<string, string>> = {
        compression: 'summary-length', self_repetition: 'daily-figures', coherence: 'daily-figures',
        semantic_coverage: 'daily-figures', evidential_density: 'source-doubts',
        speculative_density: 'source-doubts', extraction_suspect: 'extraction',
        determinism_violation: 'daily-figures'
    };
    expect([...RECORDED, ...FLAGS].map((instrument) => instrument.id).sort()).toEqual(Object.keys(receivers).sort());
    for (const instrument of [...RECORDED, ...FLAGS]) expect(DRAWN_BY[instrument.id]).toBe(receivers[instrument.id]);
    expect(EVAL_PANELS.find((panel) => panel.id === 'extraction')?.route).toBe('/console/');
});
test.describe('the arithmetic', () => {
    test('a day is reduced by position, and a missing reading never enters as a zero', () => {
        const days = evalDays(FIXTURE);
        expect(days.map((day) => day.date)).toEqual([
            '2026-04-01',
            '2026-04-02',
            '2026-04-03',
            '2026-04-04'
        ]);
        const first = days[0];
        expect(first.matchLow).toBe(60);
        expect(first.matchMid).toBe(70);
        expect(first.matchHigh).toBe(90);
        expect(first.matched).toBe(4);
        expect(first.widerDiffers).toBe(2);
        expect(first.widestGap).toBe(20);
        const blank = days[2];
        expect(blank.scored).toBe(1);
        expect(blank.matched).toBe(0);
        expect(blank.matchMid).toBeNull();
        expect(blank.recorded.compression).toBeNull();
        const bad = days[3];
        expect(bad.scored).toBe(2);
        expect(bad.matched).toBe(1);
        expect(bad.matchMid).toBe(85);
        expect(bad.fired.extraction_suspect).toBe(1);
        expect(bad.fired.determinism_violation).toBe(1);
    });
    test('a cosine keeps its own scale and its sign, and is never read as a percent', () => {
        const days = evalDays(FIXTURE);
        expect(days[1].recorded.coherence).toBe(0.1);
        const reading = recordedReadings(days).find((entry) => entry.id === 'coherence');
        expect(reading?.days).toBe(1);
        expect(reading?.low).toBe(0.1);
        expect(recordedText(reading!, -0.3, numberFormat)).toBe('-0.3');
        expect(recordedText(reading!, null, numberFormat)).toBe('-');
    });
    test('a row with no day is dropped rather than pooled into an empty one', () => {
        const days = evalDays(FIXTURE);
        expect(days.some((day) => day.date === '')).toBe(false);
        expect(days.reduce((sum, day) => sum + day.scored, 0)).toBe(FIXTURE.length - 1);
    });
    test('a flag that never fired is counted, not omitted', () => {
        const readings = flagReadings(evalDays(FIXTURE));
        expect(readings.map((reading) => reading.id)).toEqual(FLAGS.map((flag) => flag.id));
        for (const reading of readings) {
            expect(reading.fired).toBe(1);
            expect(reading.of).toBe(FIXTURE.length - 1);
        }
    });
    test('THE ORACLE: what the faithfulness panel draws is reduced from rows written here', () => {
        const days = evalDays([
            { date: '2026-05-02', hhem: '0.80', hhem_delta: '0.05' },
            { date: '2026-05-01', hhem: '0.40', hhem_delta: '0' },
            { date: '2026-05-01', hhem: '0.90', hhem_delta: '-0.10' },
            { date: '2026-05-01', hhem: '0.70', hhem_delta: '0.20' },
            { date: '2026-05-03', hhem: '', hhem_delta: '', compression: '0.333' }
        ]);
        expect(days.map((day) => day.date)).toEqual(['2026-05-01', '2026-05-02', '2026-05-03']);
        expect(days.map((day) => ({
            date: day.date,
            scored: day.scored,
            matched: day.matched,
            low: day.matchLow,
            mid: day.matchMid,
            high: day.matchHigh,
            widerDiffers: day.widerDiffers,
            widestGap: day.widestGap,
            compression: day.recorded.compression
        }))).toEqual([
            {
                date: '2026-05-01',
                scored: 3,
                matched: 3,
                low: 40,
                mid: 70,
                high: 90,
                widerDiffers: 2,
                widestGap: 20,
                compression: null
            },
            {
                date: '2026-05-02',
                scored: 1,
                matched: 1,
                low: 80,
                mid: 80,
                high: 80,
                widerDiffers: 1,
                widestGap: 5,
                compression: null
            },
            {
                date: '2026-05-03',
                scored: 1,
                matched: 0,
                low: null,
                mid: null,
                high: null,
                widerDiffers: 0,
                widestGap: 0,
                compression: 33
            }
        ]);
    });
});
