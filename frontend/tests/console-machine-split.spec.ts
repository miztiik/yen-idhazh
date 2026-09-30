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
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { machineName } from '../src/lib/charts/machine-name';
import {
	machineRamp,
	MACHINE_HUE,
	UNRECORDED_KEY,
	UNRECORDED_NAME,
	UNRECORDED_STOP,
	type Placement
} from '../src/lib/charts/machine-colour';
import { splitByMachine } from '../src/lib/charts/machine-split';
import {
	machineCounters,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';

const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 21_600 };

/** `config/appearance.json` read off disk, so the steps are the page's own. */
const CONSOLE = (
	JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')) as {
		console: { machine_colour_stops: number; machine_colour_floor_share: number };
	}
).console;

/** The speed ramp's steps and floor, as the page reads them. */
const COLOUR = { stops: CONSOLE.machine_colour_stops, floor: CONSOLE.machine_colour_floor_share };

/** The reserved grey, as every machine that has no speed is drawn. */
const GREY = `var(--chart-${UNRECORDED_STOP})`;

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
	/** A kind's jobs, each reading at the rate given. */
	const jobs = (key: string, name: string, rates: (number | null)[]): Placement[] =>
		rates.map((rate) => ({ machine: { key, name }, rate }));

	test('five steps for a machine, which is console.machine_colour_stops', () => {
		// Five, because a reader cannot rank many steps of one hue on a thin bar.
		// The route, the config reader's fallback and this spec move together.
		expect(COLOUR.stops).toBe(5);
		expect(COLOUR.floor).toBe(0.4);
	});

	test('a kind takes the step its median speed falls in, slowest first', () => {
		// Medians by hand: 10, 20, 30, 40 and 50 tokens a second, one kind each.
		const ramp = machineRamp(
			[
				...jobs('e', 'Fifth', [50, 49, 51]),
				...jobs('a', 'First', [9, 10, 11]),
				...jobs('c', 'Third', [30]),
				...jobs('b', 'Second', [20, 20]),
				...jobs('d', 'Fourth', [40, 38, 42])
			],
			COLOUR
		);
		expect(ramp.rows.map((row) => `${row.name}:${row.step}`)).toEqual([
			'First:1',
			'Second:2',
			'Third:3',
			'Fourth:4',
			'Fifth:5'
		]);
		expect(ramp.rows.map((row) => row.rate)).toEqual([10, 20, 30, 40, 50]);
		// The fastest step is the hue itself, and every step is that one hue.
		expect(ramp.rows[4].colour).toBe(`var(${MACHINE_HUE})`);
		expect(ramp.rows.every((row) => row.colour.includes(`var(${MACHINE_HUE})`))).toBe(true);
		expect(ramp.steps.map((step) => [step.low, step.high])).toEqual([
			[10, 10],
			[20, 20],
			[30, 30],
			[40, 40],
			[50, 50]
		]);
	});

	test('the steps are cut from each kind, not from every job, so a busy machine takes one step', () => {
		// One machine gives a hundred readings at 8, as one machine gave 102 of
		// 176 on the committed record. Cut over every job, all four cuts land on
		// 8 and the other four kinds share the top step; cut over the kinds' own
		// medians, the five kinds take five steps.
		const busy = jobs('busy', 'Busy', Array.from({ length: 100 }, () => 8));
		const ramp = machineRamp(
			[
				...busy,
				...jobs('b', 'B', [12]),
				...jobs('c', 'C', [19]),
				...jobs('d', 'D', [24]),
				...jobs('e', 'E', [27])
			],
			COLOUR
		);
		expect(ramp.at.get('busy')?.step).toBe(1);
		expect(new Set(ramp.rows.map((row) => row.step)).size).toBe(5);
	});

	test('a different arrival order gives the same steps', () => {
		const placements = [...jobs('a', 'A', [9, 10]), ...jobs('b', 'B', [30]), ...jobs('c', 'C', [20])];
		const forward = machineRamp(placements, COLOUR);
		const backward = machineRamp([...placements].reverse(), COLOUR);
		const steps = (ramp: ReturnType<typeof machineRamp>) =>
			ramp.rows.map((row) => `${row.key}:${row.step}:${row.colour}`);
		expect(steps(forward)).toEqual(steps(backward));
	});

	test('two kinds on one step share its colour, and each keeps its own name and speed', () => {
		// Seven kinds on five steps: at least two steps hold two kinds.
		const ramp = machineRamp(
			[10, 11, 20, 30, 31, 40, 50].map((rate, index) => jobs(`k${index}`, `Kind ${index}`, [rate])).flat(),
			COLOUR
		);
		const byStep = new Map<number, string[]>();
		for (const row of ramp.rows) byStep.set(row.step ?? 0, [...(byStep.get(row.step ?? 0) ?? []), row.name]);
		expect([...byStep.values()].some((names) => names.length > 1)).toBe(true);
		expect(new Set(ramp.rows.map((row) => row.name)).size).toBe(7);
	});

	test('a machine with no reading and no machine at all are the grey, and no machine is last', () => {
		const ramp = machineRamp(
			[
				...jobs(UNRECORDED_KEY, '', [15]),
				...jobs('timed', 'Timed', [12]),
				...jobs('untimed', 'Untimed', [null, null])
			],
			COLOUR
		);
		expect(ramp.rows.map((row) => row.key)).toEqual(['timed', 'untimed', UNRECORDED_KEY]);
		const untimed = ramp.at.get('untimed');
		expect(untimed?.step).toBeNull();
		expect(untimed?.rate).toBeNull();
		expect(untimed?.colour).toBe(GREY);
		const absent = ramp.at.get(UNRECORDED_KEY);
		expect(absent?.name).toBe(UNRECORDED_NAME);
		expect(absent?.colour).toBe(GREY);
		// An absence takes no speed, even where its jobs read prompts.
		expect(absent?.rate).toBeNull();
		expect(ramp.at.get('timed')?.colour).not.toBe(GREY);
	});
});

test.describe('reading against writing, machine by machine', () => {
	const split = splitByMachine(onlyRun(FOUR_SHARDS), { colour: COLOUR });
	const named = (name: string) => split.groups.find((group) => group.identity.name === name);

	test('one group per machine drawn, slowest first, and the two spellings are one machine', () => {
		expect(split.groups).toHaveLength(3);
		// Xeon reads at 10 a second and the EPYC at 60, so the Xeon comes first.
		expect(split.groups.map((group) => group.identity.name)).toEqual([
			'Intel Xeon Platinum 8573C',
			'AMD EPYC 7763',
			UNRECORDED_NAME
		]);
		const xeon = split.groups[0];
		expect(xeon.shards).toBe(2);
		expect(xeon.identity.step).toBe(1);
		expect(named('AMD EPYC 7763')?.identity.step).toBe(COLOUR.stops);
	});

	test('every rate is that machine shards summed, never a mean of their rates', () => {
		const epyc = named('AMD EPYC 7763');
		const xeon = named('Intel Xeon Platinum 8573C');
		// EPYC: 12,000 tokens over 200 s. Xeon: 2,000 + 1,000 over 200 + 100.
		expect(epyc?.readTokensPerSecond).toBeCloseTo(60, 6);
		expect(xeon?.readTokensPerSecond).toBeCloseTo(3000 / 300, 6);
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
			{ colour: COLOUR }
		);
		// Summed: 11,000 over 300 = 36.67. A mean of 10 and 90 would be 50.
		expect(tilted.groups[0].readTokensPerSecond).toBeCloseTo(11_000 / 300, 6);
	});

	test('the write cost of a machine is that machine own two rates', () => {
		const epyc = named('AMD EPYC 7763');
		// 60 read a second against 1,000 written over 100 s, which is 10.
		expect(epyc?.writeTokensPerSecond).toBeCloseTo(10, 6);
		expect(epyc?.writeCostRatio).toBeCloseTo(6, 6);
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
		const one = splitByMachine(onlyRun([FOUR_SHARDS[1], FOUR_SHARDS[2]]), { colour: COLOUR });
		expect(one.groups).toHaveLength(1);
		expect(one.oneMachine).toBe(true);
		expect(one.spread).toBeNull();
		expect(one.slowest).toBeNull();
	});

	test('a run that named no machine at all pools, and the page is told to say so', () => {
		const pooled = splitByMachine(onlyRun([FOUR_SHARDS[3]]), { colour: COLOUR });
		expect(pooled.noMachineNamed).toBe(true);
		expect(pooled.groups).toHaveLength(1);
		expect(pooled.groups[0].identity.colour).toBe(GREY);
		expect(pooled.groups[0].identity.name).toBe(UNRECORDED_NAME);
	});

	test('a run with no complete shard splits nothing rather than splitting zero', () => {
		const bare = onlyRun([{ shard: 0 }, { shard: 1 }]);
		const view = splitByMachine(bare, { colour: COLOUR });
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
		const pooledByName = splitByMachine(onlyRun(rows), { colour: COLOUR });
		expect(pooledByName.groups).toHaveLength(1);

		const byFingerprint = splitByMachine(onlyRun(rows), {
			colour: COLOUR,
			fingerprints: new Map([
				[0, '1111111111111111'],
				[1, '2222222222222222']
			])
		});
		expect(byFingerprint.groups).toHaveLength(2);
		expect(byFingerprint.groups.every((group) => group.identity.name === 'AMD EPYC 7763')).toBe(true);
		expect(byFingerprint.spread).toBeCloseTo(6, 6);
	});

	test('a shard carries the fingerprint its machine record holds, so no map is needed', () => {
		// The counters kept the processor name and dropped the digest until
		// 2026-09-30, so a shard of a machine whose name has two digests became a
		// third machine on the page. The packed row carries the digest; the shard
		// keeps it.
		const run = onlyRun([
			{ ...FOUR_SHARDS[0], fingerprint: '1111111111111111' },
			{ ...FOUR_SHARDS[0], shard: 1, fingerprint: '2222222222222222' }
		]);
		expect(run.reported.map((shard) => shard.fingerprint)).toEqual([
			'1111111111111111',
			'2222222222222222'
		]);
		const split = splitByMachine(run, { colour: COLOUR });
		expect(split.groups.map((group) => group.identity.key).sort()).toEqual([
			'1111111111111111',
			'2222222222222222'
		]);
	});
});
