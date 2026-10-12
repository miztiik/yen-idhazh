/** Deterministic model rule rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { pipelineChanges } from '../src/lib/server/model-work';
function boundariesFrom(rows: Record<string, string>[]): string[] {
    const seen = new Map<string, string[]>();
    for (const row of rows) {
        if (!row.date || !row.pipeline_fingerprint)
            continue;
        seen.set(row.date, [...(seen.get(row.date) ?? []), row.pipeline_fingerprint]);
    }
    const dates = [...seen.keys()].sort();
    const found: string[] = [];
    for (let at = 1; at < dates.length; at += 1) {
        const before = seen.get(dates[at - 1]) ?? [];
        const now = seen.get(dates[at]) ?? [];
        if (now.some((stamp) => !before.includes(stamp)))
            found.push(dates[at]);
    }
    return found;
}
test.describe('the boundary, as arithmetic', () => {
    const row = (date: string, stamp: string) => ({ date, pipeline_fingerprint: stamp });
    test('a day running a stamp yesterday did not run is a boundary', () => {
        expect(pipelineChanges([row('2026-08-01', 'aaa'), row('2026-08-02', 'aaa'), row('2026-08-03', 'bbb')])).toEqual(['2026-08-03']);
    });
    test('the first scored day is never a boundary - there is nothing before it', () => {
        expect(pipelineChanges([row('2026-08-01', 'aaa'), row('2026-08-02', 'aaa')])).toEqual([]);
    });
    test('a day that only stopped using one of yesterday stamps changed nothing', () => {
        expect(pipelineChanges([
            row('2026-08-29', 'old'),
            row('2026-08-29', 'new'),
            row('2026-08-30', 'new')
        ])).toEqual([]);
    });
    test('a day carrying several stamps is one boundary, because a day is one column', () => {
        expect(pipelineChanges([
            row('2026-08-25', 'aaa'),
            row('2026-08-26', 'aaa'),
            row('2026-08-26', 'bbb'),
            row('2026-08-26', 'ccc')
        ])).toEqual(['2026-08-26']);
    });
    test('a row with no stamp is not a change', () => {
        expect(pipelineChanges([
            row('2026-08-01', 'aaa'),
            { date: '2026-08-02', pipeline_fingerprint: '' },
            row('2026-08-02', 'aaa')
        ])).toEqual([]);
    });
    test('the written ledger, read by both implementations, agrees', () => {
        const rows = [
            row('2026-08-01', 'aaa'),
            row('2026-08-02', 'aaa'),
            row('2026-08-03', 'bbb'),
            row('2026-08-04', 'bbb'),
            row('2026-08-05', 'ccc'),
            { date: '2026-08-06', pipeline_fingerprint: '' }
        ];
        expect(pipelineChanges(rows)).toEqual(['2026-08-03', '2026-08-05']);
        expect(pipelineChanges(rows)).toEqual(boundariesFrom(rows));
    });
});
test.describe('the boundary, after the inputs became a record', () => {
    const [first, second, third] = ['2026-03-01', '2026-03-02', '2026-03-03'];
    const runDay = (date: string, ...inputs: (Record<string, unknown> | null)[]) => ({
        date,
        records: inputs.map((one) => ({ inputs: one }))
    });
    test('a day whose recorded inputs differ from yesterday is a boundary', () => {
        expect(pipelineChanges([], [
            runDay(first, { prompt_sha256: 'aaa' }),
            runDay(second, { prompt_sha256: 'aaa' }),
            runDay(third, { prompt_sha256: 'bbb' })
        ])).toEqual([third]);
    });
    test('a run that recorded nothing contributes no identity', () => {
        expect(pipelineChanges([], [runDay(first, { prompt_sha256: 'aaa' }), runDay(second, null)])).toEqual([]);
    });
    test('a stamped day against a recorded day is never a boundary, whatever the dates are', () => {
        expect(pipelineChanges([{ date: first, pipeline_fingerprint: 'aaa' }], [runDay(second, { prompt_sha256: 'aaa' })])).toEqual([]);
    });
    test('a day carrying both records reads the manifest and ignores the digest', () => {
        expect(pipelineChanges([
            { date: first, pipeline_fingerprint: 'aaa' },
            { date: second, pipeline_fingerprint: 'bbb' }
        ], [runDay(first, { prompt_sha256: 'x' }), runDay(second, { prompt_sha256: 'x' })])).toEqual([]);
    });
    test('a digest that moves under a manifest that does not is still no boundary', () => {
        expect(pipelineChanges([
            { date: first, pipeline_fingerprint: 'aaa' },
            { date: second, pipeline_fingerprint: 'zzz' }
        ], [runDay(first, { prompt_sha256: 'x' }), runDay(second, { prompt_sha256: 'x' })])).toEqual([]);
    });
});
