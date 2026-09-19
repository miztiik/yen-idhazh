/** How reading and writing split, on each machine one run drew.
 *
 * This replaces one pooled figure that was wrong about nearly every run. The
 * panel summed four counters over the shards of a run and printed one rate in
 * bold, and its own source comment claimed the mismatch between the two rows was
 * "a fact about the model rather than about which shards answered which
 * question". Measured 2026-09-17 over the committed counters ledger - 380 rows,
 * 95 runs, 19 dates - that claim was false on **86 of the 90 runs that name a
 * processor**: 39 runs drew two kinds of processor, 43 drew three and 4 drew
 * four. Inside one run the read rate between the fastest and the slowest machine
 * runs 1.00x to 6.08x, median 2.32x, and the worst run read at 59.71 tokens a
 * second on one machine and 9.83 on another. A rate pooled across those two is
 * a number about neither.
 *
 * So the unit here is the machine, not the run. Each group sums over its own
 * shards - sum over sum, never a mean of per-shard rates, which is the existing
 * rule now applied one level down.
 *
 * **Shards that recorded no processor are their own group and are never merged
 * into a named one.** 24 of the 380 committed rows have an empty `cpu_model`,
 * and folding them into a machine would attribute somebody else's seconds to it.
 *
 * Pure. It takes its shards and its colour ramp as arguments, reaches no disk
 * and no network, and the browser suite drives it in plain Node.
 */

import type { MachineRun, ShardCounters } from '$lib/server/machine-counters';
import { seconds } from './machine';
import {
	machineKeys,
	machineRamp,
	UNRECORDED_KEY,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp,
	type MachineSeen
} from './machine-colour';
import { percentOf } from './rank';
import { grouped } from './series';

/** One 100-percent row inside a machine's group: how a quantity split. */
export interface SplitRow {
	/** `Seconds` or `Tokens`. */
	label: string;
	readValue: number;
	writeValue: number;
	readWidth: string;
	writeWidth: string;
	/** Reading's share, whole percent. */
	readPct: number;
	totalText: string;
	readText: string;
	writeText: string;
}

/** One machine's shards, and what they did. */
export interface MachineSplit {
	identity: MachineIdentity;
	/** Shards of this machine that reported all four counters. */
	shards: number;
	rows: SplitRow[];
	readTokens: number;
	readTokensPerSecond: number | null;
	writeTokensPerSecond: number | null;
	/** Read tokens one written token costs, on this machine's shards alone. */
	writeCostRatio: number | null;
}

export interface SplitByMachine {
	runId: string;
	groups: MachineSplit[];
	/** The group that read the most tokens. The one headline that survives. */
	headline: MachineSplit | null;
	/** The slowest and the fastest read rate across the groups, and the multiple.
	 * Null where fewer than two groups have a rate - there is no spread in one. */
	slowest: MachineSplit | null;
	fastest: MachineSplit | null;
	spread: number | null;
	/** True where every shard that reported drew the same machine. A good state. */
	oneMachine: boolean;
	/** True where no shard named a machine, so the one group IS the pooled split. */
	noMachineNamed: boolean;
	/** Shards that reported all four counters, and shards the run planned. Null
	 * where its manifest recorded no count. */
	from: number;
	outOf: number | null;
	empty: boolean;
}

function sum(values: readonly number[]): number {
	return values.reduce((total, value) => total + value, 0);
}

/** A whole shard: one that reported all four counters the split needs. */
function whole(shard: ShardCounters): boolean {
	return (
		shard.readSeconds !== null &&
		shard.writeSeconds !== null &&
		shard.promptTokens !== null &&
		shard.writtenTokens !== null
	);
}

/** What each shard recorded about its machine.
 *
 * `fingerprints` carries the digest the machine record wrote for this run's work
 * shards where it reached them; a shard it missed carries only the processor's
 * own string, which the same record holds on its other half.
 */
function seenBy(shard: ShardCounters, fingerprints: ReadonlyMap<number, string>): MachineSeen {
	return { fingerprint: fingerprints.get(shard.shard) ?? null, cpuModel: shard.cpuModel };
}

export function splitByMachine(
	run: MachineRun | null,
	options: {
		colourStops: number;
		/** Shard index to fingerprint, for the shards the machine record reached. */
		fingerprints?: ReadonlyMap<number, string>;
		/** The page's own ramp, assigned over every machine any panel can show.
		 * Without it the ramp is assigned over this run alone, which is right for a
		 * test and wrong for a page whose window control can widen the key set. */
		ramp?: MachineRamp;
		/** The page's own key resolver, built over the same population as the ramp. */
		keys?: (seen: MachineSeen) => MachineKey;
	}
): SplitByMachine {
	const fingerprints = options.fingerprints ?? new Map<number, string>();
	const reported = run === null ? [] : run.reported.filter(whole);
	if (run === null || reported.length === 0) {
		return {
			runId: run?.runId ?? '',
			groups: [],
			headline: null,
			slowest: null,
			fastest: null,
			spread: null,
			oneMachine: false,
			noMachineNamed: false,
			from: 0,
			outOf: run?.shards ?? null,
			empty: true
		};
	}

	const seen = reported.map((shard) => seenBy(shard, fingerprints));
	const resolve = options.keys ?? machineKeys(seen);
	const keys = seen.map(resolve);
	const ramp = options.ramp ?? machineRamp(keys, options.colourStops);
	const byIdentity = new Map<string, ShardCounters[]>();
	reported.forEach((shard, index) => {
		const identity = ramp.at.get(keys[index].key);
		if (identity === undefined) return;
		const held = byIdentity.get(identity.key);
		if (held === undefined) byIdentity.set(identity.key, [shard]);
		else held.push(shard);
	});

	const row = (
		label: string,
		read: number,
		write: number,
		unit: (value: number) => string
	): SplitRow => {
		const total = read + write;
		const fraction = total > 0 ? read / total : 0;
		return {
			label,
			readValue: read,
			writeValue: write,
			readWidth: percentOf(fraction),
			writeWidth: percentOf(1 - fraction),
			readPct: Math.round(fraction * 100),
			totalText: unit(total),
			readText: unit(read),
			writeText: unit(write)
		};
	};

	const groups: MachineSplit[] = [];
	for (const identity of ramp.rows) {
		const shards = byIdentity.get(identity.key) ?? [];
		if (shards.length === 0) continue;
		const readSeconds = sum(shards.map((shard) => shard.readSeconds ?? 0));
		const writeSeconds = sum(shards.map((shard) => shard.writeSeconds ?? 0));
		const readTokens = sum(shards.map((shard) => shard.promptTokens ?? 0));
		const writeTokens = sum(shards.map((shard) => shard.writtenTokens ?? 0));
		// Sum over sum inside the machine. A mean of per-shard rates weighs a
		// shard that read twenty items like one that read forty.
		const readRate = readSeconds > 0 ? readTokens / readSeconds : null;
		const writeRate = writeSeconds > 0 ? writeTokens / writeSeconds : null;
		groups.push({
			identity,
			shards: shards.length,
			rows: [
				row('Seconds', readSeconds, writeSeconds, (value) => seconds(value)),
				row('Tokens', readTokens, writeTokens, (value) => `${grouped(Math.round(value))} tokens`)
			],
			readTokens,
			readTokensPerSecond: readRate,
			writeTokensPerSecond: writeRate,
			writeCostRatio: readRate !== null && writeRate !== null && writeRate > 0 ? readRate / writeRate : null
		});
	}

	// The machine that read the most tokens, not the fastest and not the first.
	// The surviving headline has to be the one an operator would have quoted the
	// pooled figure for, and that figure was dominated by whoever read most.
	const headline =
		groups.reduce<MachineSplit | null>(
			(best, group) => (best === null || group.readTokens > best.readTokens ? group : best),
			null
		) ?? null;

	const rated = groups.filter(
		(group): group is MachineSplit & { readTokensPerSecond: number } =>
			group.readTokensPerSecond !== null
	);
	const ordered = [...rated].sort((a, b) => a.readTokensPerSecond - b.readTokensPerSecond);
	const slowest = ordered[0] ?? null;
	const fastest = ordered.at(-1) ?? null;
	const named = groups.filter((group) => group.identity.key !== UNRECORDED_KEY);

	return {
		runId: run.runId,
		groups,
		headline,
		slowest: ordered.length > 1 ? slowest : null,
		fastest: ordered.length > 1 ? fastest : null,
		spread:
			ordered.length > 1 && slowest !== null && fastest !== null && slowest.readTokensPerSecond > 0
				? fastest.readTokensPerSecond / slowest.readTokensPerSecond
				: null,
		oneMachine: groups.length === 1 && named.length === 1,
		noMachineNamed: named.length === 0,
		from: reported.length,
		outOf: run.shards,
		empty: false
	};
}
