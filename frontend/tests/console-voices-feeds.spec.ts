/** Deterministic voices feeds rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chronological, failing, feedDays, resting, settled, streak, type FeedEvent, type FeedRead } from '../src/lib/feed-health';
import { sourceHealth } from '../src/lib/console/voices/source-health';
import { feedInput, feedsFailed } from '../src/lib/console/voices/feeds-failed';
import { feedFailurePreview } from '../src/lib/console/voices/feed-failure-preview';
import type { RecordRead } from '../src/lib/console/recording';
import type { SourceHealthView } from '../src/lib/server/payload';
const repo = resolve(process.cwd(), '..');
const QUARANTINE_AFTER = (JSON.parse(readFileSync(join(repo, 'config', 'idhazh.json'), 'utf8')) as {
    collect: {
        availability_strikes_before_rest: number;
    };
}).collect.availability_strikes_before_rest;
test.describe('the quarantine rule, without a browser', () => {
    test('a failure count is a run of failures, not a lifetime total', () => {
        const cameBack: FeedRead[] = [
            ...Array.from({ length: 12 }, (_, n) => ({
                date: '2026-07-01',
                runId: `2026-07-01-${n + 1}`,
                outcome: 'transient',
                items: 0
            })),
            { date: '2026-08-01', runId: '2026-08-01-1', outcome: 'ok', items: 9 }
        ];
        expect(streak(cameBack)).toBe(0);
        expect(cameBack.filter(failing)).toHaveLength(12);
        expect(resting(cameBack, QUARANTINE_AFTER)).toBe(false);
        const dying: FeedRead[] = Array.from({ length: 4 }, (_, n) => ({
            date: '2026-08-01',
            runId: `2026-08-01-${n + 1}`,
            outcome: 'permanent',
            items: 0
        }));
        expect(streak(dying)).toBe(4);
        expect(resting(dying, QUARANTINE_AFTER)).toBe(false);
    });
    test('a rest is transparent to the count, and lifts itself', () => {
        const struck: FeedRead[] = Array.from({ length: QUARANTINE_AFTER }, (_, n) => ({
            date: '2026-08-01',
            runId: `2026-08-01-${n + 1}`,
            outcome: 'transient',
            items: 0
        }));
        expect(resting(struck, QUARANTINE_AFTER)).toBe(true);
        const oneSkip = [...struck, { date: '2026-08-02', runId: '2026-08-02-1', outcome: 'skipped', items: 0 }];
        expect(streak(oneSkip)).toBe(QUARANTINE_AFTER);
        expect(resting(oneSkip, QUARANTINE_AFTER)).toBe(true);
        const served = [
            ...struck,
            ...Array.from({ length: QUARANTINE_AFTER }, (_, n) => ({
                date: '2026-08-02',
                runId: `2026-08-02-${n + 1}`,
                outcome: 'skipped',
                items: 0
            }))
        ];
        expect(resting(served, QUARANTINE_AFTER)).toBe(false);
        const failure = { ...at(9), checkedAt: '2026-08-30T12:00:00.100Z', outcome: 'transient', items: 0 };
        const skip = { ...at(1), checkedAt: '2026-08-30T12:00:00.100Z', outcome: 'skipped', items: 0 };
        expect(resting([failure, skip], 1)).toBeNull();
        expect(resting([skip, failure], 1)).toBeNull();
        expect(resting([failure, { ...skip, checkedAt: '2026-08-30T12:00:00.101Z' }], 1)).toBe(false);
        expect(resting([{ ...failure, checkedAt: '2026-08-30T12:00:00Z' }, skip], 1)).toBeNull();
        expect(streak([failure, skip])).toBe(1);
        const view: SourceHealthView = {
            generated_at: failure.checkedAt.slice(0, 19) + 'Z', run_id: failure.runId,
            headline_sentence: 'Observation order is not known.', reliability_floor: 0,
            reliability_window_days: 1, min_complete_days: 1, complete_dates: 0,
            yield_readable: false, first_date: null, last_date: null,
            sources: [{
                source_id: 'recorded-feed', title: 'Recorded feed', vertical: 'ai',
                permission: 'allowed', availability: 'unavailable', retired: false,
                retired_on: null, opportunities: 0, publications: 0, source_failures: 0,
                reliability: 0, reliability_reads: 1,
            }],
        };
        expect(sourceHealth(view, 1)?.withheld).toBe(0);
        view.sources[0]!.permission = 'unavailable';
        expect(sourceHealth(view, 1)?.withheld).toBe(1);
    });
    test('an answer that carried nothing is a failure, and a polite refusal is not', () => {
        const empty: FeedRead = { date: '2026-08-01', runId: 'r1', outcome: 'ok', items: 0 };
        const polite: FeedRead = { date: '2026-08-01', runId: 'r2', outcome: 'robots_denied', items: 0 };
        expect(failing(empty)).toBe(true);
        expect(failing(polite)).toBe(false);
        expect(streak([polite, polite])).toBe(0);
    });
    test('a day is drawn by its worst outcome and labelled by all of them', () => {
        const mixed: FeedRead[] = [
            { date: '2026-08-01', runId: 'a', outcome: 'ok', items: 5 },
            { date: '2026-08-01', runId: 'b', outcome: 'ok', items: 5 },
            { date: '2026-08-01', runId: 'c', outcome: 'transient', items: 0 }
        ];
        const [day] = feedDays(mixed);
        expect(day.outcome).toBe('failed');
        expect(day.label).toBe('1 Aug 2026, 3 runs: 2 answered, 1 failed.');
        const clean = feedDays([{ date: '2026-08-02', runId: 'a', outcome: 'ok', items: 5 }]);
        expect(clean[0].outcome).toBe('answered');
        expect(clean[0].label).toBe('2 Aug 2026, 1 run: 1 answered.');
    });
});
const EVIDENCE: {
    name: string;
    row: FeedRead;
    after: number;
}[] = [
    { name: 'a success carrying entries', row: { ...at(9), outcome: 'ok', items: 3 }, after: 0 },
    { name: 'a success carrying nothing', row: { ...at(9), outcome: 'ok', items: 0 }, after: 3 },
    { name: 'blocked', row: { ...at(9), outcome: 'blocked', items: 0 }, after: 3 },
    { name: 'permanent', row: { ...at(9), outcome: 'permanent', items: 0 }, after: 3 },
    { name: 'transient', row: { ...at(9), outcome: 'transient', items: 0 }, after: 3 },
    { name: 'robots denied', row: { ...at(9), outcome: 'robots_denied', items: 0 }, after: 2 },
    { name: 'robots unknown', row: { ...at(9), outcome: 'robots_denied', items: 0 }, after: 2 },
    { name: 'a rest', row: { ...at(9), outcome: 'skipped', items: 0 }, after: 2 }
];
function at(run: number): {
    date: string;
    runId: string;
    checkedAt: string;
} {
    return { date: '2026-08-30', runId: `2026-08-30-${run}`, checkedAt: `2026-08-30T12:00:${String(run).padStart(2, '0')}Z` };
}
test.describe('the evidence table, without a browser', () => {
    const twoStrikes: FeedRead[] = [
        { ...at(1), outcome: 'transient', items: 0 },
        { ...at(2), outcome: 'transient', items: 0 }
    ];
    for (const { name, row, after } of EVIDENCE) {
        test(`${name} leaves the streak at ${after}`, () => {
            expect(streak(twoStrikes)).toBe(2);
            expect(streak([...twoStrikes, row])).toBe(after);
        });
    }
    test('a refusal never launders a record', () => {
        const struck: FeedRead[] = Array.from({ length: QUARANTINE_AFTER }, (_, n) => ({
            ...at(n + 1),
            outcome: 'transient',
            items: 0
        }));
        const refused = [...struck, { ...at(9), outcome: 'robots_denied', items: 0 }];
        expect(streak(refused)).toBe(QUARANTINE_AFTER);
        expect(resting(refused, QUARANTINE_AFTER)).toBe(true);
    });
});
test.describe('THE ORACLE: one result per feed per run, in both languages', () => {
    const FIXTURE = join(repo, 'tests', 'fixtures', 'feed-health', 'one-result-per-run.csv');
    function fixtureRows(): FeedEvent[] {
        const lines = readFileSync(FIXTURE, 'utf8').trim().split(/\r?\n/);
        const head = lines[0].split(',');
        return lines.slice(1).map((line) => {
            const cell = line.split(',');
            const row = new Map(head.map((name, index) => [name, cell[index] ?? '']));
            return {
                date: row.get('date') ?? '',
                runId: row.get('run_id') ?? '',
                checkedAt: row.get('checked_at') ?? '',
                outcome: row.get('outcome') ?? '',
                items: Number(row.get('items') ?? 0) || 0,
                feedId: row.get('feed_id') ?? ''
            };
        });

        test.describe('the feed-only preview', () => {
            const first = '2026-08-29';
            const through = '2026-08-30';
            const read: Extract<RecordRead, { state: 'read' }> = {
                state: 'read', first, through, lastRows: null, lostDays: [], setAside: {}
            };
            function feed(id: string, date: string, run: number, outcome: string, items = '0') {
                return {
                    run_id: `${date}-${run}`, date, feed_id: id,
                    checked_at: `${date}T12:00:${String(run).padStart(2, '0')}Z`, outcome, items
                };
            }

            test('ranks failed days before raw reads and keeps tied failures beyond the preview', () => {
                const rows = [
                    feed('anchor', first, 1, 'transient'),
                    feed('anchor', through, 1, 'ok'), // Answered with no entries.
                    feed('anchor', through, 2, 'ok', '5'),
                    feed('beta', first, 1, 'ok', '1'),
                    feed('beta', through, 1, 'blocked'),
                    feed('delta', through, 1, 'permanent'),
                    ...[1, 2, 3].map(run => feed('gamma', through, run, 'transient')),
                    feed('polite', first, 1, 'robots_denied'),
                    feed('clean', through, 1, 'transient'),
                    feed('clean', through, 1, 'ok', '1') // The successful read settles this run.
                ];
                const view = feedFailurePreview(feedInput({ rows, columns: [], read }), through, 2, 3);
                expect(view.state).toBe('read');
                if (view.state !== 'read') throw new Error('Expected the packed feed record to be usable');
                expect(view).toMatchObject({ checked: 5, failed: 4, runs: 4, tied: 1, cutoff: 1, moreFailedReads: 3, partial: false });
                expect(view.preview.map(({ id }) => id)).toEqual(['anchor', 'beta', 'delta']);
                expect(view.preview[0]).toMatchObject({
                    failedDays: 2, observedDays: 2, failedReads: 2, reads: 3, last: through, reasons: ['answered with no entries']
                });
                expect(view.preview[1]).toMatchObject({ failedDays: 1, observedDays: 2, failedReads: 1, reads: 2 });
                expect(view.more).toEqual([expect.objectContaining({ id: 'gamma', failedDays: 1, observedDays: 1, failedReads: 3 })]);
            });

            test('keeps absent and unreadable records separate from a read with no asks or no failures', () => {
                const preview = (state: RecordRead, rows: ReturnType<typeof feed>[] = []) =>
                    feedFailurePreview(feedInput({ rows, columns: [], read: state }), through, 2, 3);
                expect(preview({ state: 'not-packed' }).state).toBe('not-packed');
                expect(preview({ state: 'unreadable', at: through, fault: null }).state).toBe('unreadable');
                expect(preview(read)).toMatchObject({ state: 'read', checked: 0, recordedDays: 0, failed: 0 });
                expect(preview(read, [feed('resting', through, 1, 'skipped'), feed('refused', through, 2, 'robots_denied')]))
                    .toMatchObject({ state: 'read', checked: 0, recordedDays: 1, failed: 0 });
                expect(preview(read, [feed('clean', through, 1, 'ok', '1')]))
                    .toMatchObject({ state: 'read', checked: 1, recordedDays: 1, failed: 0, preview: [], more: [] });
            });

            test('does not backfill a lost day with older rows or count newer published days', () => {
                const rows = [feed('older', '2026-08-28', 1, 'permanent'), feed('today', first, 1, 'transient')];
                const input = feedInput({ rows, columns: [], read: { ...read, lostDays: [through], setAside: { [through]: 1 } } });
                expect(feedFailurePreview(input, '2026-08-31', 2, 3)).toMatchObject({
                    start: first, end: through, recordedDays: 1, checked: 1, failed: 1,
                    partial: true, lost: [through], setAside: 1, preview: [expect.objectContaining({ id: 'today' })]
                });
                expect(feedFailurePreview(input, '2026-08-31', 1, 3)).toMatchObject({
                    start: through, end: through, partial: true, checked: 0, preview: []
                });
            });

            test('the combined chart still includes an article failure for a feed that answered', () => {
                const rows = [feed('clean-feed', first, 1, 'ok', '1'), feed('later-feed', through, 1, 'permanent')];
                const input = feedInput({ rows, columns: [], read });
                const combined = feedsFailed(input, [{
                    date: first, source_id: 'clean-feed', stage: 'fetch', outcome: 'failed', code: 'http_server_error'
                }], { from: first, to: through, asked: 2, days: 2 }, 10, 1, 3);
                expect(combined.sources.map(({ sourceId }) => sourceId)).toEqual(['clean-feed']);
                expect(combined.sources[0]).toMatchObject({ fired: 1, feed: { counts: { quiet: 1 } }, article: { counts: { fired: 1 } } });
                expect(combined.feedWaiting).toContain(`Feed results after ${first} wait for their article fetches`);
            });
        });
    }
    test('nine rows are seven events, and each distinct run is counted once', () => {
        const rows = fixtureRows();
        expect(rows).toHaveLength(9);
        const effective = chronological(settled(rows));
        expect(effective).toHaveLength(7);
        expect(new Set(effective.map((row) => row.runId)).size).toBe(7);
        const third = effective.find((row) => row.runId === '2026-08-30-3') as FeedEvent;
        expect(third.items).toBe(6);
    });
    test('the strike count is one, and it is two if nothing settles the rows', () => {
        const rows = fixtureRows();
        expect(streak(chronological(rows))).toBe(2);
        expect(streak(chronological(settled(rows)))).toBe(1);
        expect(resting(chronological(settled(rows)), QUARANTINE_AFTER)).toBe(false);
    });
});
