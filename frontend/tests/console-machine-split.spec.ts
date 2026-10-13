/** Native machine identities, speed colours and independent shard rates. */

import { expect, test } from './support/browser';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { machineName } from '../src/lib/charts/machine-name';
import {
	machineKeys,
	machineRamp,
	MACHINE_HUE,
	UNRECORDED_KEY,
	UNRECORDED_NAME,
	UNRECORDED_STOP,
	type Placement
} from '../src/lib/charts/machine-colour';
import { fleetJobs } from '../src/lib/charts/fleet';
import {
	machineCounters,
	type MachineLimits,
	type MachineRun
} from '../src/lib/console/machine/counters';
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

	test('fingerprint algorithms are distinct and name-only rows never join either', () => {
		const rows = [
			{ fingerprint: 'aaaaaaaaaaaaaaaa', fingerprintVersion: 1, cpuModel: 'Same CPU' },
			{ fingerprint: 'aaaaaaaaaaaaaaaa', fingerprintVersion: 2, cpuModel: 'Same CPU' },
			{ fingerprint: null, fingerprintVersion: null, cpuModel: 'Same CPU' }
		];
		const resolve = machineKeys(rows);
		expect(rows.map(resolve).map((row) => row.key)).toEqual([
			'v1:aaaaaaaaaaaaaaaa',
			'v2:aaaaaaaaaaaaaaaa',
			'name:Same Cpu'
		]);
	});
});

test.describe('which colour a machine takes', () => {
	/** A kind's jobs, each reading at the rate given. */
	const jobs = (key: string, name: string, rates: (number | null)[]): Placement[] =>
		rates.map((rate) => ({ machine: { key, name, fingerprintVersion: null }, rate }));

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

test.describe('the native callers retain the measured machine and shard', () => {
	test('read and write rates stay on the measured shards, including the unnamed host', () => {
		const run = onlyRun(FOUR_SHARDS);
		expect(run.reported.map((one) => [one.shard, one.readTokensPerSecond, one.writeTokensPerSecond])).toEqual([
			[0, 60, 10], [1, 10, 5], [2, 10, 5], [3, 20, 10]
		]);
		expect(run.reported[3].cpuModel).toBeNull();
		expect(run.reported[3].promptTokens).toBe(600);
		expect(run.readSpread.value).toBe(6);
		const bare = onlyRun([{ shard: 0 }, { shard: 1 }]);
		expect(bare.reported.every((one) => one.readTokensPerSecond === null && one.writeTokensPerSecond === null)).toBe(true);
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
		const keys = machineKeys(run.reported);
		expect(run.reported.map(keys).map((one) => one.key).sort()).toEqual([
			'v2:1111111111111111',
			'v2:2222222222222222'
		]);
	});

	test('native fleet placement rates never borrow another shard or fingerprint algorithm', () => {
		const { hosts } = ledgers([
			{ ...FOUR_SHARDS[0], fingerprint: '1111111111111111' },
			{ ...FOUR_SHARDS[0], shard: 1, fingerprint: '1111111111111111', serverPromptTokens: 2000 }
		]);
		hosts[0].version = '2026-09-20';
		hosts[0].fingerprint_version = '1';
		const jobs = fleetJobs(hosts);
		expect(jobs.map((one) => one.rate)).toEqual([60, 10]);
		const keys = machineKeys(jobs);
		expect(jobs.map(keys).map((one) => one.key)).toEqual(['v1:1111111111111111', 'v2:1111111111111111']);
	});
});
