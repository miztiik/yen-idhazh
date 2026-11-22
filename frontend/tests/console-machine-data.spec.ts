/** Deterministic machine data rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { summaryContext, summaryContextSeries } from '../src/lib/console/machine/summary-context';
import { machineCounters } from '../src/lib/console/machine/counters';
import type { Row } from '../src/lib/data/ledger';
import { itemHealthRows } from '../src/lib/server/ledger-rows';
import { buildLedger } from './support/ledger-lifecycle';
import { ledgers, plan, type ShardReading } from './support/machine-rows';
function row(reading: ShardReading): ShardReading {
    return { date: '2026-09-02', runId: '2026-09-02-1', shard: 0, ...reading };
}
const FULL: ShardReading[] = [
    row({
        shard: 0,
        serverPromptTokens: 1000,
        serverPromptSeconds: 100,
        jobSeconds: 600,
        cpuModel: 'AMD EPYC 7763 64-Core Processor',
        modelLoadMs: 12000
    }),
    row({
        shard: 1,
        serverPromptTokens: 3000,
        serverPromptSeconds: 100,
        jobSeconds: 900,
        cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C',
        modelLoadMs: 9000
    })
];
function readerInput(readings: ShardReading[], planned?: [
    string,
    number
][]) {
    const { hosts, health } = ledgers(readings.map(row));
    const byRun = new Map<string, number>();
    for (const reading of readings) {
        const runId = reading.runId ?? '2026-09-02-1';
        byRun.set(runId, (byRun.get(runId) ?? 0) + 1);
    }
    return { hosts, health, planned: planned === undefined ? byRun : plan(...planned) };
}
function read(readings: ShardReading[], options: {
    planned?: [
        string,
        number
    ][];
} = {}) {
    const input = readerInput(readings, options.planned);
    return machineCounters(input.hosts, input.health, input.planned);
}
test.describe('a shard is a set and never a count', () => {
    const twice = [
        row({ runId: '2026-09-02-3', shard: 0, serverPromptSeconds: 100, serverPromptTokens: 1000 }),
        row({ runId: '2026-09-02-3', shard: 0, serverPromptSeconds: 100, serverPromptTokens: 1000 }),
        row({ runId: '2026-09-02-3', shard: 1, serverPromptSeconds: 300, serverPromptTokens: 3000 })
    ];
    test('one record written twice is counted once', () => {
        const { runs, refused } = read(twice, { planned: [['2026-09-02-3', 2]] });
        expect(refused).toEqual([]);
        expect(runs).toHaveLength(1);
    });
    test('two servers answering for one shard refuse the run rather than sum it', () => {
        const disagree = [twice[0], { ...twice[1], serverPromptSeconds: 250 }, twice[2]];
        const { runs, refused } = read(disagree, { planned: [['2026-09-02-3', 2]] });
        expect(runs).toEqual([]);
        expect(refused).toHaveLength(1);
        expect(refused[0].runId).toBe('2026-09-02-3');
        expect(refused[0].rows).toBe(6);
        expect(refused[0].why).toContain('shard 0');
    });
    test('more shards than the run says it had is refused', () => {
        const impossible = [
            row({ runId: '2026-09-02-5', shard: 0 }),
            row({ runId: '2026-09-02-5', shard: 1 })
        ];
        const { runs, refused } = read(impossible, { planned: [['2026-09-02-5', 1]] });
        expect(runs).toEqual([]);
        expect(refused[0].why).toContain('shards');
    });
    test('rows that disagree about the day are not one run', () => {
        const split = [
            row({ runId: '2026-09-02-6', shard: 0, date: '2026-09-02' }),
            row({ runId: '2026-09-02-6', shard: 1, date: '2026-09-03' })
        ];
        const { runs, refused } = read(split);
        expect(runs).toEqual([]);
        expect(refused[0].why).toContain('which day');
    });
    test('a row that does not say which shard it is refuses the run', () => {
        const nameless = [{ ...row({ runId: '2026-09-02-7' }), shard: undefined }];
        const { hosts, health } = ledgers(nameless);
        const { runs, refused } = machineCounters(hosts.map((host) => ({ ...host, shard: '' })), health, plan(['2026-09-02-7', 1]));
        expect(runs).toEqual([]);
        expect(refused[0].why).toContain('which shard');
    });
});
test.describe('two machine records for one shard', () => {
    const SHARD: ShardReading = FULL[0];
    const RUN_ID = SHARD.runId ?? '';
    test('that disagree are refused by name, never read one over the other', () => {
        const { hosts, health } = ledgers([SHARD]);
        const second = {
            ...hosts[0],
            cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
            job_seconds: '720'
        };
        const { runs, refused } = machineCounters([...hosts, second], health, plan([RUN_ID, 1]));
        expect(runs).toEqual([]);
        expect(refused.map((run) => run.runId)).toEqual([RUN_ID]);
        expect(refused[0].why).toContain('two machine records that disagree');
    });
});
test.describe('the ledgers this reads, over a record written here', () => {
    const counted = () => {
        const { hosts, health } = ledgers([
            ...FULL,
            row({ runId: '2026-09-02-5', shard: 0 }),
            row({ runId: '2026-09-02-5', shard: 1 })
        ]);
        return machineCounters(hosts, health, plan(['2026-09-02-1', 2], ['2026-09-02-5', 1]));
    };
    test('the record reads as one run and one refused run', () => {
        const { runs, refused } = counted();
        expect(runs.map((run) => run.date)).toEqual(['2026-09-02']);
        expect(refused.map((run) => run.runId)).toEqual(['2026-09-02-5']);
    });
    test('an absent ledger is an empty read, never a throw', () => {
        expect(machineCounters([], [], new Map())).toEqual({ runs: [], refused: [] });
    });
});
test.describe('ledger readers respect the fixture root', () => {
    test('an empty root cannot fall back to the populated canary or the archive', async () => {
        const state = test.info().outputPath('state');
        for (const ledger of ['item-health'] as const) {
            await buildLedger(state, { ledger, pinned: '2030-06-15', days: [{ ago: 1, rows: 2 }, { ago: 0, rows: 2 }] });
        }
        const empty = test.info().outputPath('empty');
        mkdirSync(empty, { recursive: true });
        const window = { start: '2030-06-14', end: '2030-06-15' };
        for (const read of [itemHealthRows]) {
            const built = await read(window, state);
            expect(built.read.state).toBe('read');
            expect(built.rows).toHaveLength(4);
            const nothing = await read(window, empty);
            expect(nothing.rows).toEqual([]);
            expect(nothing.read.state).not.toBe('read');
            const again = await read(window, state);
            expect(again.rows).toEqual(built.rows);
        }
    });
});
test.describe('summary prompts against their own recorded slots', () => {
    const [first, next, mixed, gap] = ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04'];
    const summary = (date: string, tokens: number, context: number, slots = 1): Row =>
        ({ date, summary_input_tokens: tokens, n_ctx_configured: context, n_parallel: slots });

    test('daily p90 and the window peak use each prompt with its own recorded capacity', () => {
        const reading = summaryContext([
            ...Array.from({ length: 10 }, (_, index) => summary(first, (index + 1) * 100, 4096, 2)),
            summary(next, 512, 1024),
            { date: next, summary_input_tokens: 9_000, n_ctx_configured: 1024 },
            { date: next, label_input_tokens: 20_000, truncation_cap_tokens: 26_000 }
        ], [first, next]);
        expect(reading.days[0].slots).toEqual([{ capacity: 2048, used: 900, room: 1148, measured: 10 }]);
        expect(reading.days[1]).toMatchObject({ recorded: 2, measured: 1, slots: [{ capacity: 1024, used: 512, room: 512 }] });
        expect(reading.peak).toEqual({ capacity: 1024, used: 512, share: 0.5 });
        expect(reading.prompts).toHaveLength(12);
        expect(reading.prompts.at(-1)).toBe(9_000);
        expect(reading.cut).toBe(1);
        const [limit, used] = summaryContextSeries(reading.days);
        expect(limit.points.map((point) => point.value)).toEqual([2048, 1024]);
        expect(used.points[1].spread).toEqual({ low: 512, high: 1024 });
    });

    test('mixed slots stay separate; exact zero room, overage and a missing slot differ', () => {
        const reading = summaryContext([
            summary(first, 128, 256), summary(mixed, 256, 256), summary(mixed, 1025, 1024),
            summary(gap, 20, 256, 0), summary(gap, 0, 256)
        ], [first, next, mixed, gap]);
        expect(reading.days[2].slots).toEqual([
            { capacity: 256, used: 256, room: 0, measured: 1 },
            { capacity: 1024, used: 1025, room: -1, measured: 1 }
        ]);
        expect(reading.days[1]).toMatchObject({ recorded: 0, slots: [] });
        expect(reading.days[3]).toMatchObject({ recorded: 1, measured: 0, slots: [] });
        const [limit, used, ...variants] = summaryContextSeries(reading.days);
        expect(limit.points.map((point) => point.value)).toEqual([256, null, null, null]);
        expect(used.points.map((point) => point.value)).toEqual([128, null, null, null]);
        expect(variants.flatMap((trace) => trace.points)).toEqual([
            { date: mixed, value: 256 }, { date: mixed, value: 256 },
            { date: mixed, value: 1024 }, { date: mixed, value: 1025 }
        ]);
    });
});
