/** Deterministic machine data rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { clockAgreement } from '../src/lib/charts/machine';
import { contextCost, type ContextOptions } from '../src/lib/console/machine/context-cost';
import { CLOCKS_AGREE_WITHIN_PCT, machineCounters, machineLimits, type MachineLimits, type MachineRun } from '../src/lib/server/machine-counters';
import { machineRecord } from '../src/lib/server/host-fingerprint';
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
    const limits = machineLimits();
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
        for (const ledger of ['host-fingerprint', 'item-health'] as const) {
            await buildLedger(state, { ledger, pinned: '2030-06-15', days: [{ ago: 1, rows: 2 }, { ago: 0, rows: 2 }] });
        }
        const empty = test.info().outputPath('empty');
        mkdirSync(empty, { recursive: true });
        const window = { start: '2030-06-14', end: '2030-06-15' };
        for (const read of [machineRecord, itemHealthRows]) {
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
const CONSOLE = JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')).console as {
    window_presets: number[];
    min_attempts_for_rate: number;
    context_high_percentile: number;
    context_cut_off_reason: string;
};
test.describe('Row #21 - the context panel says what the limit already costs', () => {
    const OPTIONS: ContextOptions = {
        percentile: CONSOLE.context_high_percentile,
        cutOffReason: CONSOLE.context_cut_off_reason
    };
    const AT_90: ContextOptions = { percentile: 90, cutOffReason: CONSOLE.context_cut_off_reason };
    const RECORD: Record<string, string>[] = [
        { run_id: '2030-06-14-1', date: '2030-06-14', n_ctx_configured: '8192', summary_input_tokens: '1000', summary_output_tokens: '24' },
        { run_id: '2030-06-14-1', date: '2030-06-14', n_ctx_configured: '8192', summary_input_tokens: '2000', summary_output_tokens: '48' },
        {
            run_id: '2030-06-14-1',
            date: '2030-06-14',
            n_ctx_configured: '8192',
            label_input_tokens: '900',
            label_output_tokens: '100',
            summary_input_tokens: '4000',
            summary_output_tokens: '96'
        },
        { run_id: '2030-06-15-1', date: '2030-06-15', n_ctx_configured: '8192', summary_input_tokens: '3000', summary_output_tokens: '72' },
        { run_id: '2030-06-15-1', date: '2030-06-15', summary_input_tokens: '500', summary_output_tokens: '20' },
        { run_id: '2030-06-15-2', date: '2030-06-15' }
    ];
    test('THE ORACLE: the unused share is the largest article recomputed off the ledger', () => {
        const { span } = contextCost(RECORD, AT_90);
        expect(span.limits, 'the record ran under more than one limit').toEqual([8192]);
        expect(span.rowsRead).toBe(6);
        expect(span.items, 'the reader measured a different set of articles').toBe(4);
        expect(span.largest, 'the largest article is not the largest in the record').toBe(4096);
        expect(span.largestPct).toBe(50);
        expect(span.unusedPct, 'the unused share is not the largest article inverted').toBe(50);
        expect(span.median).toBe(2560);
        expect(span.timesMedian).toBe(3.2);
        expect(span.high).toBe(3789);
        expect(span.percentile).toBe(90);
    });
    test('THE ORACLE: every run mark carries both ends, not one', () => {
        const { runs } = contextCost(RECORD, AT_90);
        expect(runs).toEqual([
            { runId: '2030-06-14-1', date: '2030-06-14', items: 3, high: 3686, largest: 4096, highPct: 45, largestPct: 50 },
            { runId: '2030-06-15-1', date: '2030-06-15', items: 1, high: 3072, largest: 3072, highPct: 38, largestPct: 38 },
            { runId: '2030-06-15-2', date: '2030-06-15', items: 0, high: null, largest: null, highPct: null, largestPct: null }
        ]);
    });
    test('a row that recorded no limit is not measured, and a total across calls is not a peak', () => {
        const rows: Record<string, string>[] = [
            { run_id: '2026-09-02-1', date: '2026-09-02', label_input_tokens: '900', label_output_tokens: '100' },
            { run_id: '2026-09-02-1', date: '2026-09-02', n_ctx_configured: '8192', input_tokens: '4000', output_tokens: '500' },
            { run_id: '2026-09-02-1', date: '2026-09-02', n_ctx_configured: '8192', summary_input_tokens: '1900', summary_output_tokens: '148' }
        ];
        const { span, runs } = contextCost(rows, OPTIONS);
        expect(span.rowsRead).toBe(3);
        expect(span.items, 'a row with no limit or no call cells was measured').toBe(1);
        expect(span.largest).toBe(2048);
        expect(span.largestPct).toBe(25);
        expect(span.unusedPct).toBe(75);
        expect(runs[0].items).toBe(1);
    });
    test('the peak is the largest call and never the calls added', () => {
        const row: Record<string, string> = {
            run_id: '2026-09-02-1',
            date: '2026-09-02',
            n_ctx_configured: '8192',
            label_input_tokens: '900',
            label_output_tokens: '100',
            summary_input_tokens: '1950',
            summary_output_tokens: '100'
        };
        const { span } = contextCost([row], OPTIONS);
        expect(span.largest, 'the reader added the calls together').toBe(2050);
        expect(span.largest).not.toBe(3050);
    });
    test('a limit that moved inside the span leaves the token figures unshared', () => {
        const rows: Record<string, string>[] = [
            { run_id: '2026-09-02-1', date: '2026-09-02', n_ctx_configured: '8192', summary_input_tokens: '1000', summary_output_tokens: '48' },
            { run_id: '2026-09-03-1', date: '2026-09-03', n_ctx_configured: '65536', summary_input_tokens: '2000', summary_output_tokens: '48' }
        ];
        const { span } = contextCost(rows, OPTIONS);
        expect(span.limits).toEqual([8192, 65536]);
        expect(span.largest, 'the token figure survives a limit that moved').toBe(2048);
        expect(span.largestPct, 'a share was taken against one of two limits').toBeNull();
        expect(span.unusedPct).toBeNull();
        expect(span.timesMedian).toBeNull();
        expect(span.items).toBe(2);
    });
    test('a cut-off reply is counted and an unrecorded one is not called a clean stop', () => {
        const clean = { label_finish_reason: 'stop', summary_finish_reason: 'stop' };
        const cut = { label_finish_reason: 'stop', summary_finish_reason: CONSOLE.context_cut_off_reason };
        const { span } = contextCost([clean, cut, {}], OPTIONS);
        expect(span.calls, 'a row that named no reason was counted as a call').toBe(4);
        expect(span.cutOff).toBe(1);
        expect(span.reasons).toEqual([
            { reason: 'stop', calls: 3 },
            { reason: CONSOLE.context_cut_off_reason, calls: 1 }
        ]);
    });
    test('no rows at all is an absence the panel can name, never a zero', () => {
        const { runs, span } = contextCost([], OPTIONS);
        expect(runs).toEqual([]);
        expect(span.rowsRead).toBe(0);
        expect(span.items).toBe(0);
        expect(span.limits).toEqual([]);
        expect(span.largest).toBeNull();
        expect(span.unusedPct, 'an unread limit reported a share').toBeNull();
        expect(span.timesMedian).toBeNull();
        expect(span.calls).toBe(0);
        expect(span.cutOff).toBe(0);
        expect(span.reasons).toEqual([]);
    });
});
