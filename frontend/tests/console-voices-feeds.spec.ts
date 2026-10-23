/** Deterministic voices feeds rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chronological, failing, feedDays, resting, settled, streak, type FeedEvent, type FeedRead } from '../src/lib/feed-health';
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
