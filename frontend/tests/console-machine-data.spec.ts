/** Deterministic machine data rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { clockAgreement } from '../src/lib/charts/machine';
import { contextReadings } from '../src/lib/console/machine/records';
import { CLOCKS_AGREE_WITHIN_PCT, machineCounters, type MachineLimits, type MachineRun } from '../src/lib/console/machine/counters';
import type { Row } from '../src/lib/data/ledger';
import { itemHealthRows } from '../src/lib/server/ledger-rows';
import { buildLedger } from './support/ledger-lifecycle';
import { hostRow, itemRow, ledgers, plan, type ShardReading } from './support/machine-rows';
const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 9000 };
function row(reading: ShardReading): ShardReading {
    return { date: '2026-09-02', runId: '2026-09-02-1', shard: 0, ...reading };
}
const FULL: ShardReading[] = [
    row({
        shard: 0,
        serverPromptTokens: 1000,
        serverPromptSeconds: 100,
        cachedTokens: 250,
        writtenTokens: 400,
        writeSeconds: 50,
        longestSequence: 4096,
        jobSeconds: 600,
        cpuModel: 'AMD EPYC 7763 64-Core Processor',
        cpuBusyPct: 99.5,
        peakRssBytes: 6000000000,
        modelLoadMs: 12000
    }),
    row({
        shard: 1,
        serverPromptTokens: 3000,
        serverPromptSeconds: 100,
        cachedTokens: 1000,
        writtenTokens: 600,
        writeSeconds: 150,
        longestSequence: 2048,
        jobSeconds: 900,
        cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C',
        cpuBusyPct: 88,
        peakRssBytes: 7000000000,
        modelLoadMs: 9000
    })
];
function healthRows(runId: string, items: number, tokens: number, prefillMs: number) {
    return Array.from({ length: items }, (_, index) => ({
        date: runId.slice(0, 10),
        run_id: runId,
        item_id: `item-${index}`,
        input_tokens: String(tokens + 100),
        cached_tokens: '100',
        prefill_ms: String(prefillMs),
        decode_ms: '1000'
    }));
}
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
    health?: Record<string, string>[];
    limits?: MachineLimits;
} = {}) {
    const input = readerInput(readings, options.planned);
    return machineCounters(input.hosts, [...input.health, ...(options.health ?? [])], input.planned, options.limits ?? LIMITS);
}
function only(runs: MachineRun[], runId: string): MachineRun {
    const found = runs.find((run) => run.runId === runId);
    expect(found, `no run ${runId}`).toBeTruthy();
    return found as MachineRun;
}
test.describe('every figure, recomputed by hand', () => {
    const { runs, refused } = read(FULL);
    const run = only(runs, '2026-09-02-1');
    test('nothing was refused and both shards were read', () => {
        expect(refused).toEqual([]);
        expect(run.shards).toBe(2);
        expect(run.reported.map((shard) => shard.shard)).toEqual([0, 1]);
    });
    test('reading and writing are two clocks and never one', () => {
        expect(run.readSeconds).toEqual({ value: 200, from: 2, outOf: 2 });
        expect(run.writeSeconds).toEqual({ value: 200, from: 2, outOf: 2 });
        expect(run.readPct).toEqual({ value: 50, from: 2, outOf: 2 });
        expect(run.readTokensPerSecond).toEqual({ value: 20, from: 2, outOf: 2 });
        expect(run.writeTokensPerSecond).toEqual({ value: 5, from: 2, outOf: 2 });
    });
    test('the spread between shards is carried, not averaged away', () => {
        expect(run.reported[0].readTokensPerSecond).toBe(10);
        expect(run.reported[1].readTokensPerSecond).toBe(30);
        expect(run.readSpread).toEqual({ value: 3, from: 2, outOf: 2 });
    });
    test('the cache share is of every token the prompt needed', () => {
        expect(run.promptTokens).toEqual({ value: 4000, from: 2, outOf: 2 });
        expect(run.cachedTokens).toEqual({ value: 1250, from: 2, outOf: 2 });
        expect(run.cachedPct).toEqual({ value: Math.round((1250 / 5250) * 100), from: 2, outOf: 2 });
        expect(run.cachedPct.value).toBe(24);
    });
    test('the longest sequence is read against the window, and is a maximum', () => {
        expect(run.longestSequence).toEqual({ value: 4096, from: 2, outOf: 2 });
        expect(run.contextUsedPct).toEqual({ value: 50, from: 2, outOf: 2 });
        expect(run.reported[1].contextUsedPct).toBe(25);
    });
    test('the job clock is the slowest shard, read against the timeout', () => {
        expect(run.slowestJobSeconds).toEqual({ value: 900, from: 2, outOf: 2 });
        expect(run.jobUsedPct).toEqual({ value: 10, from: 2, outOf: 2 });
        expect(run.reported[0].jobUsedPct).toBe(7);
    });
});
test.describe('the two clocks, checked against each other', () => {
    test('an agreeing run reports the gap it agreed by', () => {
        const health = healthRows('2026-09-02-1', 4, 1000, 50_000);
        const run = only(read(FULL, { health }).runs, '2026-09-02-1');
        expect(run.clocks.ledger).toEqual({ tokens: 4000, seconds: 200, parts: 4, rate: 20 });
        expect(run.clocks.server).toEqual({ tokens: 4000, seconds: 200, parts: 2, rate: 20 });
        expect(run.clocks.gapPct).toBe(0);
        expect(run.clocks.agrees).toBe(true);
    });
    test('a disagreeing run says so rather than rounding it away', () => {
        const health = healthRows('2026-09-02-1', 4, 1000, 75_000);
        const run = only(read(FULL, { health }).runs, '2026-09-02-1');
        const expected = ((20 - 4000 / 300) / 20) * 100;
        expect(run.clocks.gapPct).toBeCloseTo(expected, 6);
        expect(run.clocks.gapPct as number).toBeGreaterThan(CLOCKS_AGREE_WITHIN_PCT);
        expect(run.clocks.agrees).toBe(false);
    });
    test('nothing to compare is null, never a disagreement', () => {
        const run = only(read(FULL).runs, '2026-09-02-1');
        expect(run.clocks.ledger.parts).toBe(0);
        expect(run.clocks.gapPct).toBeNull();
        expect(run.clocks.agrees).toBeNull();
    });
    test('an item missing either timing cell is left out of both sums', () => {
        const health = [
            ...healthRows('2026-09-02-1', 4, 1000, 50_000),
            { runId: '2026-09-02-1', item_id: 'older', input_tokens: '', cached_tokens: '', prefill_ms: '' }
        ];
        const run = only(read(FULL, { health }).runs, '2026-09-02-1');
        expect(run.clocks.ledger.parts).toBe(4);
        expect(run.clocks.gapPct).toBe(0);
    });
});
test.describe('THE ORACLE: one item cost, taken away', () => {
    const REFUSED = 'ai-09';
    const COST = ['prefill_ms', 'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens'];
    const RUN = '2030-06-15-1';
    const shard = { date: '2030-06-15', runId: RUN, shard: 0 };
    const hosts = [hostRow({ ...shard, serverPromptTokens: 1000, serverPromptSeconds: 100 })];
    const item = (itemId: string, prompt: number, seconds: number) => itemRow({ ...shard, itemId, longestSequence: prompt + 50, writtenTokens: 50, cachedTokens: 0, ledgerReadSeconds: seconds, writeSeconds: 5 });
    const whole = [item('ai-01', 300, 44), item('ai-02', 300, 45), item(REFUSED, 400, 10)];
    const blanked = whole.map((row) => row.item_id === REFUSED ? { ...row, ...Object.fromEntries(COST.map((cell) => [cell, ''])) } : row);
    function verdict(machines: Record<string, string>[], health: Record<string, string>[]) {
        const counters = machineCounters(machines, health, plan([RUN, 1]), LIMITS);
        expect(counters.refused, 'the reader refused the run').toEqual([]);
        const run = only(counters.runs, RUN);
        return { run, view: clockAgreement(run, health, CLOCKS_AGREE_WITHIN_PCT) };
    }
    test('the two ledgers agree, and disagree once one row cost goes missing', () => {
        const before = verdict(hosts, whole);
        expect(before.run.clocks.agrees).toBe(true);
        expect(before.run.clocks.gapPct, '1,000 tokens in 99 seconds against 1,000 in 100').toBeCloseTo(1.0101, 3);
        expect(before.view.grain).toBe('shard');
        expect(before.view.disagreeing).toBe(0);
        expect(before.view.pairs.every((pair) => pair.agrees === true)).toBe(true);
        const after = verdict(hosts, blanked);
        expect(after.run.clocks.agrees).toBe(false);
        expect(after.run.clocks.gapPct, '600 tokens in 89 seconds against 1,000 in 100').toBeCloseTo(32.584, 2);
        expect(after.view.disagreeing).toBeGreaterThan(0);
        expect(after.view.pairs.some((pair) => pair.agrees === false)).toBe(true);
        expect(verdict(hosts, whole).run.clocks.agrees).toBe(true);
    });
    test('the server counters are what turn it, and not the item rows alone', () => {
        const blind = hosts.map((row) => ({ ...row, server_prompt_tokens: '', server_prompt_seconds: '' }));
        const { run } = verdict(blind, blanked);
        expect(run.clocks.server.rate).toBeNull();
        expect(run.clocks.agrees).toBeNull();
        expect(run.clocks.agrees).not.toBe(false);
    });
});
test.describe('an empty cell is unknown and never zero', () => {
    const partial = [
        row({
            runId: '2026-09-02-2',
            shard: 0,
            serverPromptTokens: 1000,
            cachedTokens: 250,
            serverPromptSeconds: 100,
            writtenTokens: 400,
            writeSeconds: 50,
            longestSequence: 4096
        })
    ];
    const PLANNED: [
        string,
        number
    ][] = [['2026-09-02-2', 4]];
    test('a cell no shard reported reads as absent, with a denominator of zero', () => {
        const run = only(read(partial, { planned: PLANNED }).runs, '2026-09-02-2');
        for (const [name, reading] of [
            ['slowestJobSeconds', run.slowestJobSeconds],
            ['jobUsedPct', run.jobUsedPct],
            ['lowestCpuBusyPct', run.lowestCpuBusyPct],
            ['peakRssBytes', run.peakRssBytes],
            ['slowestModelLoadMs', run.slowestModelLoadMs]
        ] as const) {
            expect(reading.value, `${name} invented a value`).toBeNull();
            expect(reading.value, `${name} read a blank cell as zero`).not.toBe(0);
            expect(reading.from, `${name} counted a shard that said nothing`).toBe(0);
            expect(reading.outOf, `${name} lost the run's shard count`).toBe(4);
        }
        expect(run.cpuModels.value).toBeNull();
        expect(run.cpuModels.from).toBe(0);
    });
    test('the same run with the cell filled proves the absence was the cell', () => {
        const filled = [{ ...partial[0], jobSeconds: 600, cpuBusyPct: 99.5 }];
        const run = only(read(filled, { planned: PLANNED }).runs, '2026-09-02-2');
        expect(run.slowestJobSeconds).toEqual({ value: 600, from: 1, outOf: 4 });
        expect(run.lowestCpuBusyPct).toEqual({ value: 99.5, from: 1, outOf: 4 });
    });
    test('a figure from one shard of four carries the four out of the module', () => {
        const run = only(read(partial, { planned: PLANNED }).runs, '2026-09-02-2');
        expect(run.reported).toHaveLength(1);
        expect(run.readSeconds).toEqual({ value: 100, from: 1, outOf: 4 });
        expect(run.readTokensPerSecond).toEqual({ value: 10, from: 1, outOf: 4 });
        expect(run.readSpread.value).toBeNull();
    });
    test('a measurement of zero is a measurement and survives as one', () => {
        const zeroed = [{ ...partial[0], cpuBusyPct: 0 }];
        const run = only(read(zeroed, { planned: PLANNED }).runs, '2026-09-02-2');
        expect(run.lowestCpuBusyPct).toEqual({ value: 0, from: 1, outOf: 4 });
    });
    test('no ceiling means no share, and the counter still prints', () => {
        const run = only(read(partial, { limits: { contextWindow: null, jobTimeoutSeconds: null } }).runs, '2026-09-02-2');
        expect(run.longestSequence.value).toBe(4096);
        expect(run.contextUsedPct.value).toBeNull();
    });
});
test.describe('a shard is a set and never a count', () => {
    const twice = [
        row({ runId: '2026-09-02-3', shard: 0, serverPromptSeconds: 100, serverPromptTokens: 1000 }),
        row({ runId: '2026-09-02-3', shard: 0, serverPromptSeconds: 100, serverPromptTokens: 1000 }),
        row({ runId: '2026-09-02-3', shard: 1, serverPromptSeconds: 300, serverPromptTokens: 3000 })
    ];
    test('one record written twice is counted once', () => {
        const run = only(read(twice, { planned: [['2026-09-02-3', 2]] }).runs, '2026-09-02-3');
        expect(run.reported.map((shard) => shard.shard)).toEqual([0, 1]);
        expect(run.readSeconds).toEqual({ value: 400, from: 2, outOf: 2 });
        expect(run.promptTokens).toEqual({ value: 4000, from: 2, outOf: 2 });
        expect(run.readTokensPerSecond).toEqual({ value: 10, from: 2, outOf: 2 });
    });
    test('two servers answering for one shard refuse the run rather than sum it', () => {
        const disagree = [twice[0], { ...twice[1], serverPromptSeconds: 250 }, twice[2]];
        const { runs, refused } = read(disagree, { planned: [['2026-09-02-3', 2]] });
        expect(runs.map((run) => run.runId)).not.toContain('2026-09-02-3');
        expect(refused).toHaveLength(1);
        expect(refused[0].runId).toBe('2026-09-02-3');
        expect(refused[0].rows).toBe(6);
        expect(refused[0].why).toContain('shard 0');
    });
    test('a run is refused rather than reported half', () => {
        const { runs } = read([twice[0], { ...twice[1], serverPromptSeconds: 250 }, twice[2]], {
            planned: [['2026-09-02-3', 2]]
        });
        expect(runs).toEqual([]);
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
        const { runs, refused } = machineCounters(hosts.map((host) => ({ ...host, shard: '' })), health, plan(['2026-09-02-7', 1]), LIMITS);
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
        const { runs, refused } = machineCounters([...hosts, second], health, plan([RUN_ID, 1]), LIMITS);
        expect(runs).toEqual([]);
        expect(refused.map((run) => run.runId)).toEqual([RUN_ID]);
        expect(refused[0].why).toContain('two machine records that disagree');
    });
});
test.describe('the ledgers this reads, over a record written here', () => {
    const limits = LIMITS;
    const counted = () => {
        const { hosts, health } = ledgers([
            ...FULL,
            row({ runId: '2026-09-02-5', shard: 0 }),
            row({ runId: '2026-09-02-5', shard: 1 })
        ]);
        return machineCounters(hosts, health, plan(['2026-09-02-1', 2], ['2026-09-02-5', 1]), limits);
    };
    test('the record reads as one run and one refused run', () => {
        const { runs, refused } = counted();
        expect(runs.map((run) => run.runId)).toEqual(['2026-09-02-1']);
        expect(refused.map((run) => run.runId)).toEqual(['2026-09-02-5']);
    });
    test('nothing derived off them is impossible', () => {
        for (const run of counted().runs) {
            if (run.shards !== null) {
                expect(run.reported.length, `${run.runId} reported more shards than it had`).toBeLessThanOrEqual(run.shards);
            }
            expect(new Set(run.reported.map((shard) => shard.shard)).size).toBe(run.reported.length);
            for (const reading of [run.readSeconds, run.writeSeconds, run.promptTokens, run.cachedTokens]) {
                if (reading.value !== null)
                    expect(reading.value).toBeGreaterThanOrEqual(0);
            }
            if (run.readSpread.value !== null)
                expect(run.readSpread.value).toBeGreaterThanOrEqual(1);
            if (run.contextUsedPct.value !== null)
                expect(run.contextUsedPct.value).toBeLessThanOrEqual(100);
        }
    });
    test('a run the reader refuses says which run and why', () => {
        for (const run of counted().refused) {
            expect(run.runId).not.toBe('');
            expect(run.why.length).toBeGreaterThan(10);
            expect(run.why).toContain('shards');
        }
    });
    test('an absent ledger is an empty read, never a throw', () => {
        expect(machineCounters([], [], new Map(), limits)).toEqual({ runs: [], refused: [] });
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
        expect(reading.rules).toEqual([{ at: 900, label: "Cut articles' middle label request: 900 tokens" }]);
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
