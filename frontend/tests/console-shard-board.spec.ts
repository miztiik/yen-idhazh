/** Does the shard board put every work-or-host fact on the row?
 *
 * The board is worked out here on shard rows this file writes, folded the way the
 * Hardware page folds a run, with every figure a row carries written out. That
 * covers the three clocks as well - the time no named step claimed, the time an
 * item waited, and the time the shard paid opening the weights. The first is the
 * one to watch: it is the stored column added up and nothing else, so an
 * implementation that worked it out from the step clocks would give a different
 * number here.
 *
 * The built page is then held to the board's own scale rules, against the marks
 * it drew, whatever run it drew them for.
 */
import { expect, test } from './support/door-page';
import { shardBoard } from '../src/lib/charts/machine';
import { machineCounters, type MachineLimits, type MachineRun } from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';
const DATE = '2026-09-18';
const RUN = '2026-09-18-1';
const MIB = 1024 * 1024;
const TEST_LIMITS: MachineLimits = {
    contextWindow: 8192,
    jobTimeoutSeconds: 3600
};
function foldedRun(readings: ShardReading[], shards = readings.length): MachineRun {
    const stamped = readings.map((reading) => ({ date: DATE, runId: RUN, ...reading }));
    const { hosts, health } = ledgers(stamped);
    const { runs, refused } = machineCounters(hosts, health, plan([RUN, shards]), TEST_LIMITS);
    expect(refused, 'the fixture was refused').toEqual([]);
    expect(runs, 'the fixture folded into no run').toHaveLength(1);
    return runs[0];
}
function shard(over: ShardReading): ShardReading {
    return {
        cachedTokens: 0,
        serverPromptTokens: 100,
        serverPromptSeconds: 10,
        jobSeconds: 100,
        longestSequence: 1000,
        cpuModel: 'AMD EPYC 7763 64-Core Processor',
        cores: 4,
        ...over
    };
}
test.describe('the shard board carries the work-or-host answer on the row', () => {
    test('every host figure on a row comes from written shard rows', () => {
        const run = foldedRun([
            shard({
                shard: 0,
                writtenTokens: 90,
                writeSeconds: 9,
                peakRssBytes: 2000 * MIB,
                cpuBusyPct: 40,
                cpuBusyMax: 70,
                load: 3.5,
                swapFree: 512 * MIB,
                swapTotal: 1024 * MIB,
                modelLoadMs: 500,
                unclaimedMs: 2500,
                queueWaitMs: 1200
            }),
            shard({
                shard: 1,
                writtenTokens: 80,
                writeSeconds: 10,
                peakRssBytes: 3000 * MIB,
                cpuBusyPct: 60,
                cpuBusyMax: 90,
                load: 5.25,
                swapFree: 0,
                swapTotal: 0,
                modelLoadMs: 750,
                unclaimedMs: -250,
                queueWaitMs: 3400
            })
        ]);
        const board = shardBoard(run, TEST_LIMITS.jobTimeoutSeconds, 640);
        const byShard = new Map(board.rows.map((row) => [row.shard, row]));
        expect(board.runId).toBe(RUN);
        expect(board.rows).toHaveLength(2);
        expect(byShard.get(0)).toMatchObject({
            items: 1,
            writeTokensPerSecond: 10,
            cpuBusyPct: 40,
            loadMax: 3.5,
            cores: 4,
            swapFreeBytes: 512 * MIB,
            swapTotalBytes: 1024 * MIB,
            swapState: 'measured',
            modelLoadMs: 500,
            unclaimedSeconds: 2.5,
            clocksDisagreed: 0,
            clockedItems: 1,
            queueMedianSeconds: 1.2,
            queueMaxSeconds: 1.2
        });
        expect(byShard.get(0)?.memory).toMatchObject({
            median: 2000 * MIB,
            max: 2000 * MIB,
            empty: false
        });
        expect(byShard.get(0)?.cpu).toMatchObject({
            median: 40,
            max: 70,
            empty: false
        });
        expect(byShard.get(1)).toMatchObject({
            items: 1,
            writeTokensPerSecond: 8,
            cpuBusyPct: 60,
            loadMax: 5.25,
            cores: 4,
            swapFreeBytes: 0,
            swapTotalBytes: 0,
            swapState: 'none',
            modelLoadMs: 750,
            unclaimedSeconds: -0.25,
            clocksDisagreed: 1,
            clockedItems: 1,
            queueMedianSeconds: 3.4,
            queueMaxSeconds: 3.4
        });
        expect(board.memoryScaleBytes).toBe(16 * 1024 * MIB);
    });
    test('THE ORACLE: a shard whose clocks disagree says so, and never draws a zero', () => {
        const run = foldedRun([
            shard({
                shard: 0,
                writtenTokens: 50,
                writeSeconds: 5,
                unclaimedMs: -125,
                queueWaitMs: 900
            }),
            shard({
                shard: 1,
                writtenTokens: 50,
                writeSeconds: 5,
                unclaimedMs: 625,
                queueWaitMs: 400
            })
        ]);
        const board = shardBoard(run, TEST_LIMITS.jobTimeoutSeconds, 640);
        const byShard = new Map(board.rows.map((row) => [row.shard, row]));
        expect(byShard.get(0)?.unclaimedSeconds).toBe(-0.125);
        expect(byShard.get(0)?.unclaimedSeconds).not.toBe(0);
        expect(byShard.get(0)?.clocksDisagreed).toBe(1);
        expect(byShard.get(0)?.clockedItems).toBe(1);
        expect(byShard.get(1)?.unclaimedSeconds).toBe(0.625);
        expect(byShard.get(1)?.clocksDisagreed).toBe(0);
    });
});
