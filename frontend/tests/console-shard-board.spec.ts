/** Native shard counters retain independent host, signed-gap and queue readings. */
import { expect, test } from '@playwright/test';
import { machineCounters, type MachineLimits, type MachineRun } from '../src/lib/console/machine/counters';
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
		longestSequence: 1_000,
		cpuModel: 'AMD EPYC 7763 64-Core Processor',
		logicalProcessors: 4,
		...over
	};
}
test.describe('native shard readings', () => {
	test('every host figure on a row comes from written shard rows', () => {
		const run = foldedRun([
			shard({
				shard: 0,
				writtenTokens: 90,
				writeSeconds: 9,
				peakRssBytes: 2_000 * MIB,
				cpuBusyPct: 40,
				cpuBusyMax: 70,
				load: 3.5,
				swapFree: 512 * MIB,
				swapTotal: 1_024 * MIB,
				modelLoadMs: 500,
				unclaimedMs: 2_500,
				queueWaitMs: 1_200
			}),
			shard({
				shard: 1,
				writtenTokens: 80,
				writeSeconds: 10,
				peakRssBytes: 3_000 * MIB,
				cpuBusyPct: 60,
				cpuBusyMax: 90,
				load: 5.25,
				swapFree: 0,
				swapTotal: 0,
				modelLoadMs: 750,
				unclaimedMs: -250,
				queueWaitMs: 3_400
			})
		]);
		const byShard = new Map(run.reported.map((row) => [row.shard, row]));

		expect(run.runId).toBe(RUN);
		expect(run.reported).toHaveLength(2);
		expect(byShard.get(0)).toMatchObject({
			items: 1,
			writeTokensPerSecond: 10,
			cpuBusyPct: 40,
			loadMax: 3.5,
			logicalProcessors: 4,
			swapFreeMinBytes: 512 * MIB,
			swapTotalBytes: 1_024 * MIB,
			modelLoadMs: 500,
			unclaimedSeconds: 2.5,
			clocksDisagreed: 0,
			clockedItems: 1,
			queueMedianSeconds: 1.2,
			queueMaxSeconds: 1.2
		});
		expect(byShard.get(0)).toMatchObject({
			rssMedianBytes: 2_000 * MIB,
			peakRssBytes: 2_000 * MIB,
			cpuBusyMedianPct: 40,
			cpuBusyMaxPct: 70
		});
		expect(byShard.get(1)).toMatchObject({
			items: 1,
			writeTokensPerSecond: 8,
			cpuBusyPct: 60,
			loadMax: 5.25,
			logicalProcessors: 4,
			swapFreeMinBytes: 0,
			swapTotalBytes: 0,
			modelLoadMs: 750,
			unclaimedSeconds: -0.25,
			clocksDisagreed: 1,
			clockedItems: 1,
			queueMedianSeconds: 3.4,
			queueMaxSeconds: 3.4
		});
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
		const byShard = new Map(run.reported.map((row) => [row.shard, row]));

		expect(byShard.get(0)?.unclaimedSeconds).toBe(-0.125);
		expect(byShard.get(0)?.unclaimedSeconds).not.toBe(0);
		expect(byShard.get(0)?.clocksDisagreed).toBe(1);
		expect(byShard.get(0)?.clockedItems).toBe(1);
		expect(byShard.get(1)?.unclaimedSeconds).toBe(0.625);
		expect(byShard.get(1)?.clocksDisagreed).toBe(0);
	});

	test('a cancelled signed sum still counts the disagreeing item and queue waits never add', () => {
		const run = foldedRun([
			shard({ shard: 0, itemId: 'a', writtenTokens: 50, writeSeconds: 5, unclaimedMs: -2000, queueWaitMs: 1000 }),
			{ shard: 0, itemId: 'b', writtenTokens: 50, writeSeconds: 5, unclaimedMs: 2000, queueWaitMs: 5000 }
		], 1);
		expect(run.reported[0]).toMatchObject({
			unclaimedSeconds: 0, clocksDisagreed: 1, clockedItems: 2,
			queueMedianSeconds: 3, queueMaxSeconds: 5
		});
	});

	test('absent host instruments stay unknown, not measured zeroes', () => {
		const run = foldedRun([shard({ shard: 0, writtenTokens: 50, writeSeconds: 5 })], 4);
		expect(run.shards).toBe(4);
		expect(run.reported).toHaveLength(1);
		expect(run.reported[0]).toMatchObject({
			swapFreeMinBytes: null, swapTotalBytes: null, unclaimedSeconds: null,
			queueMedianSeconds: null, queueMaxSeconds: null, modelLoadMs: null,
			clocksDisagreed: 0, clockedItems: 0
		});
	});
});
