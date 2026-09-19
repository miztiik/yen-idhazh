/** Is every rate this panel prints made from one machine's shards alone?
 *
 * That is the question the panel was rebuilt to answer. Until 2026-09-17 it
 * summed four counters over every shard of a run and printed one rate in bold,
 * and measured over the committed counters ledger - 380 rows, 95 runs, 19 dates
 * - 86 of the 90 runs that name a processor drew more than one kind of
 * processor. So the bold number averaged two different machines on 95.6 percent
 * of runs.
 *
 * Every oracle here computes its expectation from the fixture rows in this file
 * with a pencil, never from the module's own output. Nothing reads a committed
 * ledger: the case that matters most - a run whose shards drew four different
 * machines, one of them unrecorded - is one the archive has never produced.
 *
 * Pure functions only. No browser, no SvelteKit alias, no `$app` import.
 */

import { expect, test } from '@playwright/test';
import { machineName } from '../src/lib/charts/machine-name';
import {
	machineRamp,
	FOLDED_KEY,
	UNRECORDED_KEY,
	UNRECORDED_NAME,
	UNRECORDED_STOP
} from '../src/lib/charts/machine-colour';
import { splitByMachine } from '../src/lib/charts/machine-split';
import {
	machineCounters,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';

const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 21_600 };

/** Seven stops for a machine, which is `console.machine_colour_stops`. */
const STOPS = 7;

/** A shard that reported all four figures, so it lands in a group. */
function shard(
	index: number,
	cpu: string,
	figures: { readTokens: number; readSeconds: number; writeTokens: number; writeSeconds: number }
): ShardReading {
	return {
		date: '2026-09-12',
		runId: '2026-09-12-1',
		shard: index,
		cpuModel: cpu,
		serverPromptTokens: figures.readTokens,
		serverPromptSeconds: figures.readSeconds,
		writtenTokens: figures.writeTokens,
		writeSeconds: figures.writeSeconds,
		cachedTokens: 0,
		longestSequence: figures.readTokens + figures.writeTokens
	};
}

/** Four shards on three machines and one that recorded none.
 *
 * Read rates by hand: EPYC 12,000/200 = 60, Xeon 2,000/200 = 10 and again
 * 1,000/100 = 10 over its two shards pooled (3,000/300), and the unrecorded
 * shard 600/30 = 20.
 */
const FOUR_SHARDS = [
	shard(0, 'AMD EPYC 7763 64-Core Processor', {
		readTokens: 12_000,
		readSeconds: 200,
		writeTokens: 1000,
		writeSeconds: 100
	}),
	shard(1, 'INTEL(R) XEON(R) PLATINUM 8573C', {
		readTokens: 2000,
		readSeconds: 200,
		writeTokens: 500,
		writeSeconds: 100
	}),
	shard(2, 'Intel(R) Xeon(R) Platinum 8573C', {
		readTokens: 1000,
		readSeconds: 100,
		writeTokens: 500,
		writeSeconds: 100
	}),
	shard(3, '', { readTokens: 600, readSeconds: 30, writeTokens: 300, writeSeconds: 30 })
];

function onlyRun(readings: ShardReading[]): MachineRun {
	const { hosts, health } = ledgers(
		readings.map((reading) => ({ date: '2026-09-12', runId: '2026-09-12-1', ...reading }))
	);
	const { runs, refused } = machineCounters(hosts, health, plan(['2026-09-12-1', 4]), LIMITS);
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs).toHaveLength(1);
	return runs[0];
}

test.describe('what a processor is called', () => {
	test('the six strings the committed ledger holds normalise to six names', () => {
		// Measured 2026-09-17 over the committed machine records: six distinct
		// `cpu_model` values across 359 named rows.
		expect(machineName('AMD EPYC 7763 64-Core Processor')).toBe('AMD EPYC 7763');
		expect(machineName('AMD EPYC 9V74 80-Core Processor')).toBe('AMD EPYC 9V74');
		expect(machineName('AMD EPYC 9V45 96-Core Processor')).toBe('AMD EPYC 9V45');
		expect(machineName('INTEL(R) XEON(R) PLATINUM 8573C')).toBe('Intel Xeon Platinum 8573C');
		expect(machineName('Intel(R) Xeon(R) 6973P-C')).toBe('Intel Xeon 6973P-C');
		expect(machineName('Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz')).toBe(
			'Intel Xeon Platinum 8370C'
		);
	});

	test('the two spellings of one machine become one name, so they group as one', () => {
		expect(machineName('INTEL(R) XEON(R) PLATINUM 8573C')).toBe(
			machineName('Intel(R) Xeon(R) Platinum 8573C')
		);
	});

	test('a part number keeps the case the host spelled it in', () => {
		// `9V74` is an identifier and case is part of it. Title-casing it would
		// invent a machine nobody can look up.
		expect(machineName('AMD EPYC 9V74 80-Core Processor')).toContain('9V74');
	});

	test('nothing recorded stays nothing, and is never a placeholder name', () => {
		expect(machineName(null)).toBe('');
		expect(machineName('')).toBe('');
		expect(machineName('   ')).toBe('');
	});
});

test.describe('which colour a machine takes', () => {
	const keys = [
		{ key: 'c81d9e0a', name: 'Intel Xeon Platinum 8573C' },
		{ key: '3a7f0b1c', name: 'AMD EPYC 7763' },
		{ key: UNRECORDED_KEY, name: '' }
	];

	test('the stop comes off the key, so a different arrival order gives the same stops', () => {
		const forward = machineRamp(keys, STOPS);
		const backward = machineRamp([...keys].reverse(), STOPS);
		const stops = (ramp: ReturnType<typeof machineRamp>) =>
			ramp.rows.map((row) => `${row.key}:${row.colourStop}`);
		expect(stops(forward)).toEqual(stops(backward));
		// Ascending by key: `3a7f0b1c` before `c81d9e0a`.
		expect(forward.rows[0].key).toBe('3a7f0b1c');
		expect(forward.rows[0].colourStop).toBe(1);
		expect(forward.rows[1].colourStop).toBe(2);
	});

	test('no two named machines share a stop, and the grey is reserved', () => {
		const ramp = machineRamp(keys, STOPS);
		const named = ramp.rows.filter((row) => row.key !== UNRECORDED_KEY);
		expect(new Set(named.map((row) => row.colourStop)).size).toBe(named.length);
		expect(named.every((row) => row.colourStop < UNRECORDED_STOP)).toBe(true);
		const absent = ramp.rows.find((row) => row.key === UNRECORDED_KEY);
		expect(absent?.colourStop).toBe(UNRECORDED_STOP);
		expect(absent?.name).toBe(UNRECORDED_NAME);
	});

	test('every machine keeps its own colour right up to the stop count', () => {
		const seven = Array.from({ length: STOPS }, (_, index) => ({
			key: `k${index}`,
			name: `Machine ${index}`
		}));
		const ramp = machineRamp(seven, STOPS);
		expect(ramp.rows).toHaveLength(STOPS);
		expect(ramp.rows.map((row) => row.folded.length)).toEqual(Array(STOPS).fill(0));
	});

	test('past the stop count the rest fold into one row that names them', () => {
		const nine = Array.from({ length: 9 }, (_, index) => ({
			key: `k${index}`,
			name: `Machine ${index}`
		}));
		const ramp = machineRamp(nine, STOPS);
		expect(ramp.rows).toHaveLength(STOPS);
		const fold = ramp.rows.at(-1);
		expect(fold?.key).toBe(FOLDED_KEY);
		// Six keep a colour; the last three share the seventh and are listed.
		expect(fold?.folded).toEqual(['Machine 6', 'Machine 7', 'Machine 8']);
		// A folded key still resolves, so nothing has to ask whether it folded.
		expect(ramp.at.get('k8')).toBe(fold);
		expect(new Set(ramp.rows.map((row) => row.colourStop)).size).toBe(STOPS);
	});
});

test.describe('reading against writing, machine by machine', () => {
	const split = splitByMachine(onlyRun(FOUR_SHARDS), { colourStops: STOPS });

	test('one group per machine drawn, and the two spellings are one machine', () => {
		expect(split.groups).toHaveLength(3);
		expect(split.groups.map((group) => group.identity.name)).toEqual([
			'AMD EPYC 7763',
			'Intel Xeon Platinum 8573C',
			UNRECORDED_NAME
		]);
		const xeon = split.groups[1];
		expect(xeon.shards).toBe(2);
	});

	test('every rate is that machine shards summed, never a mean of their rates', () => {
		const [epyc, xeon] = split.groups;
		// EPYC: 12,000 tokens over 200 s. Xeon: 2,000 + 1,000 over 200 + 100.
		expect(epyc.readTokensPerSecond).toBeCloseTo(60, 6);
		expect(xeon.readTokensPerSecond).toBeCloseTo(3000 / 300, 6);
		// A mean of the Xeon shards' own rates is 10 as well only because both are
		// 10, so tilt one to prove the sum is what is taken.
		const tilted = splitByMachine(
			onlyRun([
				FOUR_SHARDS[1],
				shard(2, 'Intel(R) Xeon(R) Platinum 8573C', {
					readTokens: 9000,
					readSeconds: 100,
					writeTokens: 500,
					writeSeconds: 100
				})
			]),
			{ colourStops: STOPS }
		);
		// Summed: 11,000 over 300 = 36.67. A mean of 10 and 90 would be 50.
		expect(tilted.groups[0].readTokensPerSecond).toBeCloseTo(11_000 / 300, 6);
	});

	test('the write cost of a machine is that machine own two rates', () => {
		const [epyc] = split.groups;
		// 60 read a second against 1,000 written over 100 s, which is 10.
		expect(epyc.writeTokensPerSecond).toBeCloseTo(10, 6);
		expect(epyc.writeCostRatio).toBeCloseTo(6, 6);
	});

	test('the one headline is the machine that read the most tokens, and it is named', () => {
		expect(split.headline?.identity.name).toBe('AMD EPYC 7763');
		expect(split.headline?.readTokens).toBe(12_000);
	});

	test('the spread sentence reads off the slowest and the fastest machine', () => {
		expect(split.slowest?.identity.name).toBe('Intel Xeon Platinum 8573C');
		expect(split.fastest?.identity.name).toBe('AMD EPYC 7763');
		// 60 against 10.
		expect(split.spread).toBeCloseTo(6, 6);
		expect(split.oneMachine).toBe(false);
		expect(split.noMachineNamed).toBe(false);
	});

	test('shards with no machine are their own group and are never merged into one', () => {
		const absent = split.groups.find((group) => group.identity.key === UNRECORDED_KEY);
		expect(absent?.shards).toBe(1);
		expect(absent?.readTokensPerSecond).toBeCloseTo(20, 6);
		// Its tokens are not inside any named machine's total.
		const named = split.groups.filter((group) => group.identity.key !== UNRECORDED_KEY);
		expect(named.reduce((total, group) => total + group.readTokens, 0)).toBe(15_000);
	});

	test('a run whose shards all drew one machine says so and has no spread', () => {
		const one = splitByMachine(onlyRun([FOUR_SHARDS[1], FOUR_SHARDS[2]]), { colourStops: STOPS });
		expect(one.groups).toHaveLength(1);
		expect(one.oneMachine).toBe(true);
		expect(one.spread).toBeNull();
		expect(one.slowest).toBeNull();
	});

	test('a run that named no machine at all pools, and the page is told to say so', () => {
		const pooled = splitByMachine(onlyRun([FOUR_SHARDS[3]]), { colourStops: STOPS });
		expect(pooled.noMachineNamed).toBe(true);
		expect(pooled.groups).toHaveLength(1);
		expect(pooled.groups[0].identity.colourStop).toBe(UNRECORDED_STOP);
	});

	test('a run with no complete shard splits nothing rather than splitting zero', () => {
		const bare = onlyRun([{ shard: 0 }, { shard: 1 }]);
		const view = splitByMachine(bare, { colourStops: STOPS });
		expect(view.empty).toBe(true);
		expect(view.groups).toEqual([]);
		expect(view.headline).toBeNull();
	});

	test('a fingerprint splits two machines one model name cannot tell apart', () => {
		// Two shards reporting one string, on machines whose fingerprints differ.
		// The name alone would pool them, which is the coarser key the panel falls
		// back to and not the one it prefers.
		const rows = [
			shard(0, 'AMD EPYC 7763 64-Core Processor', {
				readTokens: 12_000,
				readSeconds: 200,
				writeTokens: 1000,
				writeSeconds: 100
			}),
			shard(1, 'AMD EPYC 7763 64-Core Processor', {
				readTokens: 2000,
				readSeconds: 200,
				writeTokens: 1000,
				writeSeconds: 100
			})
		];
		const pooledByName = splitByMachine(onlyRun(rows), { colourStops: STOPS });
		expect(pooledByName.groups).toHaveLength(1);

		const byFingerprint = splitByMachine(onlyRun(rows), {
			colourStops: STOPS,
			fingerprints: new Map([
				[0, '1111111111111111'],
				[1, '2222222222222222']
			])
		});
		expect(byFingerprint.groups).toHaveLength(2);
		expect(byFingerprint.groups.every((group) => group.identity.name === 'AMD EPYC 7763')).toBe(true);
		expect(byFingerprint.spread).toBeCloseTo(6, 6);
	});
});
