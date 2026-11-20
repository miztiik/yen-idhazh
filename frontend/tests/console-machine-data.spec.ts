/** Deterministic machine data rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { contextReadings } from '../src/lib/console/machine/records';
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
test.describe('native context requests against recorded slot limits', () => {
    test('label and summary inputs keep their own populations, even without a limit', () => {
        const rows: Row[] = [
            { n_ctx_configured: 8192, n_parallel: 2, label_input_tokens: 900, summary_input_tokens: 4000 },
            { n_ctx_configured: 8192, n_parallel: 2, summary_input_tokens: 1000 },
            { n_ctx_configured: 8192, n_parallel: 2, summary_input_tokens: 2000 },
            { n_ctx_configured: 8192, n_parallel: 2, summary_input_tokens: 3000 },
            { summary_input_tokens: 500 },
            {}
        ];
        const reading = contextReadings(rows);
        expect(reading.label).toEqual([900]);
        expect(reading.summary).toEqual([4000, 1000, 2000, 3000, 500]);
        expect(reading.limits).toEqual([4096]);
        expect(reading.rules).toEqual([{ at: 4096, label: 'Reading limit: 4096 tokens per slot' }]);
        expect(reading.cut).toBe(0);
    });
    test('the reading limit divides context by parallel slots and retains changing limits', () => {
        const reading = contextReadings([
            { n_ctx_configured: 65536, n_parallel: 8, summary_input_tokens: 2000 },
            { n_ctx_configured: 8192, n_parallel: 4, summary_input_tokens: 1000 },
            { n_ctx_configured: 8192, n_parallel: 2, label_input_tokens: 900 },
            { n_ctx_configured: 16384, n_parallel: 8 }
        ]);
        expect(reading.limits).toEqual([2048, 4096, 8192]);
        expect(reading.rules).toEqual([{ at: 2048, label: 'Reading limit: 2048 tokens per slot' }]);
        expect(reading.summary).toEqual([2000, 1000]);
        expect(reading.label).toEqual([900]);
    });
    test('a missing half of the slot limit cannot suppress a recorded request or invent a limit', () => {
        const reading = contextReadings([
            { n_ctx_configured: 8192, summary_input_tokens: 1900 },
            { n_parallel: 2, label_input_tokens: 900 },
            { n_ctx_configured: 8192, n_parallel: 0, summary_input_tokens: 1000 },
            { n_ctx_configured: null, n_parallel: 2 }
        ]);
        expect(reading.label).toEqual([900]);
        expect(reading.summary).toEqual([1900, 1000]);
        expect(reading.limits).toEqual([]);
        expect(reading.rules).toEqual([]);
    });
    test('the cut rule is the upper-middle label request of cut articles, not the cap or every request', () => {
        const reading = contextReadings([
            { truncation_cap_tokens: 1, label_input_tokens: 200 },
            { truncation_cap_tokens: 8192, label_input_tokens: 1000 },
            { truncation_cap_tokens: 0, label_input_tokens: 400 },
            { truncation_cap_tokens: 64, label_input_tokens: 900 },
            { truncation_cap_tokens: 64, label_input_tokens: null },
            { truncation_cap_tokens: null, label_input_tokens: 90000 }
        ]);
        expect(reading.cut).toBe(5);
        expect(reading.label).toEqual([200, 1000, 400, 900, 90000]);
        expect(reading.rules).toEqual([{ at: 900, label: "Cut articles' median (p50) label request: 900 tokens" }]);
    });
    test('the logarithmic request population excludes zero and invalid cells without losing a recorded zero cap', () => {
        const reading = contextReadings([
            { label_input_tokens: 0, summary_input_tokens: 'Infinity', n_ctx_configured: 0, n_parallel: 2, truncation_cap_tokens: 0 },
            { label_input_tokens: -1, summary_input_tokens: NaN, n_ctx_configured: 8192, n_parallel: -1 },
            { label_input_tokens: '', summary_input_tokens: null, n_ctx_configured: 'Infinity', n_parallel: 2 },
            { label_input_tokens: true, summary_input_tokens: '12', n_ctx_configured: 8192, n_parallel: NaN }
        ]);
        expect(reading).toEqual({ label: [], summary: [12], rules: [], limits: [], cut: 1 });
    });
    test('no query rows produce no request population or inferred reading limit', () => {
        expect(contextReadings([])).toEqual({ label: [], summary: [], rules: [], limits: [], cut: 0 });
    });
});
