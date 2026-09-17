/** What machines one run drew, and what each of them can do.
 *
 * The panel this feeds was called "The host under the newest run" and printed
 * one line of semicolon-joined processor strings. Measured 2026-09-17 over the
 * committed counters ledger, 86 of the 90 runs that name a processor drew more
 * than one kind, so "the host" was false on 95.6 percent of runs - which is why
 * the title moved before anything else did.
 *
 * **A card carries every watched flag, present or absent.** An empty `flags`
 * cell is a reading and not a gap: the machine this project draws most, the
 * EPYC 7763, reports none of the watched AVX-512 entries at all
 * (`docs/reference/host-metrics.md`). A list of what a machine has cannot say
 * what it has not, and what it has not is the reason to look.
 *
 * **Never read the instruction set and reported none of them are different
 * facts.** The first draws no chips and says so; the second draws twelve
 * outlines. Twelve outlines for the first would publish a guess as a reading.
 *
 * Pure. The flag vocabulary, the colour ramp and the switch all arrive as
 * arguments, so a test drives them and Guardrail #6 keeps the knobs in `config/`.
 */

import type { HostFingerprint } from '$lib/server/host-fingerprint';
import type { RunCounters } from '$lib/server/runtime-counters';
import {
	machineKeys,
	machineRamp,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp,
	type MachineSeen
} from './machine-colour';

/** One chip: a watched flag, and whether this machine reported it. */
export interface FlagChip {
	name: string;
	present: boolean;
}

/** Where the platform put a machine, and which microcode it was running. */
export interface MachineWhere {
	vmSize: string | null;
	vmLocation: string | null;
	vmZone: string | null;
	vmFaultDomain: string | null;
	microcode: string | null;
	/** The host's own `model name` line, so a normalised heading is checkable. */
	cpuModelRaw: string | null;
}

export interface MachineCard {
	identity: MachineIdentity;
	/** Which ledger built it. `counters` carries a name and nothing else. */
	source: 'fingerprint' | 'counters';
	/** Family, model and stepping as `25/1/1`. */
	part: string | null;
	/** Twelve chips, or none at all where the instruction set was never read. */
	flags: FlagChip[];
	flagsRecorded: boolean;
	l3CacheBytes: number | null;
	memcpyGibPerSecond: number | null;
	memcpyProbeMib: number | null;
	/** True where the probe buffer was at or below L3, so it measured cache. */
	measuredCache: boolean;
	/** Jobs of this run that drew this machine, and jobs that recorded one. */
	jobsDrawn: number;
	jobsTotal: number;
	where: MachineWhere | null;
}

export interface MachineCards {
	runId: string;
	date: string;
	cards: MachineCard[];
	/** Why there is nothing to draw. Null where there are cards. */
	nothing: 'recording-off' | 'no-machine' | null;
	/** False where the machine record is switched off.
	 *
	 * Carried even when there are cards, because the counters ledger still names
	 * a processor: a panel that drew those cards silently would say the
	 * instruction set is missing when it was never asked for.
	 */
	recording: boolean;
	/** True where no card could carry an instruction set, so the panel says the
	 * flags, the cache and the bandwidth start on the day the record ran. */
	nameOnly: boolean;
}

/** One job of a run, as a thing that drew a machine. */
interface Placement {
	key: string;
	name: string;
	row: HostFingerprint | null;
}

function part(row: HostFingerprint): string | null {
	const cells = [row.cpuFamily, row.cpuModelNumber, row.cpuStepping];
	if (cells.some((cell) => cell === null)) return null;
	return cells.join('/');
}

function chips(row: HostFingerprint | null, watched: readonly string[]): FlagChip[] {
	if (row === null || watched.length === 0) return [];
	const present = new Set(row.flags);
	return watched.map((name) => ({ name, present: present.has(name) }));
}

/** The machines the newest run drew, one card each.
 *
 * `fingerprints` are the machine record's rows for this run - one a job, so a
 * work shard, the planner and the assembler each contribute one. A work shard
 * the record did not reach still contributes a placement, off the counters
 * ledger, carrying its processor's name and nothing else.
 */
export function machineCards(
	run: RunCounters | null,
	fingerprints: readonly HostFingerprint[],
	options: {
		watchedFlags: readonly string[];
		colourStops: number;
		/** False where the machine record is switched off. */
		recording: boolean;
		ramp?: MachineRamp;
		/** The page's own key resolver, built over the same population as the ramp. */
		keys?: (seen: MachineSeen) => MachineKey;
	}
): MachineCards {
	const runId = run?.runId ?? '';
	const date = run?.date ?? '';
	const forRun = run === null ? [] : fingerprints.filter((row) => row.runId === run.runId);
	const covered = new Set(
		forRun.filter((row) => row.job === 'work').map((row) => String(row.shard))
	);

	const seen: MachineSeen[] = [
		...forRun.map((row) => ({ fingerprint: row.fingerprint, cpuModel: row.cpuModel })),
		...(run?.reported ?? [])
			.filter((shard) => !covered.has(String(shard.shard)))
			.map((shard) => ({ fingerprint: null, cpuModel: shard.cpuModel }))
	];
	const resolve = options.keys ?? machineKeys(seen);

	const placements: Placement[] = [];
	for (const row of forRun) {
		placements.push({
			...resolve({ fingerprint: row.fingerprint, cpuModel: row.cpuModel }),
			row
		});
	}
	for (const shard of run?.reported ?? []) {
		if (covered.has(String(shard.shard))) continue;
		const key = resolve({ fingerprint: null, cpuModel: shard.cpuModel });
		if (key.name === '') continue;
		placements.push({ ...key, row: null });
	}

	if (placements.length === 0) {
		return {
			runId,
			date,
			cards: [],
			nothing: options.recording ? 'no-machine' : 'recording-off',
			recording: options.recording,
			nameOnly: true
		};
	}

	const ramp = options.ramp ?? machineRamp(placements, options.colourStops);
	const byIdentity = new Map<string, Placement[]>();
	for (const placement of placements) {
		const identity = ramp.at.get(placement.key);
		if (identity === undefined) continue;
		const held = byIdentity.get(identity.key);
		if (held === undefined) byIdentity.set(identity.key, [placement]);
		else held.push(placement);
	}

	const cards: MachineCard[] = [];
	for (const identity of ramp.rows) {
		const drawn = byIdentity.get(identity.key) ?? [];
		if (drawn.length === 0) continue;
		// The richest row wins, and a row is richer when it read the instruction
		// set. Every row for one fingerprint reports the same cells by
		// construction - the digest is taken over exactly those cells - so this
		// only ever chooses between a recorded row and an absent one.
		const row = drawn.find((placement) => placement.row !== null)?.row ?? null;
		const l3 = row?.l3CacheBytes ?? null;
		const buffer = row?.memcpyProbeMib ?? null;
		cards.push({
			identity,
			source: row === null ? 'counters' : 'fingerprint',
			part: row === null ? null : part(row),
			flags: chips(row, options.watchedFlags),
			flagsRecorded: row !== null && options.watchedFlags.length > 0,
			l3CacheBytes: l3,
			memcpyGibPerSecond: row?.memcpyGibPerSecond ?? null,
			memcpyProbeMib: buffer,
			measuredCache:
				buffer !== null && buffer > 0 && l3 !== null && buffer * 1024 * 1024 <= l3,
			jobsDrawn: drawn.length,
			jobsTotal: placements.length,
			where:
				row === null
					? null
					: {
							vmSize: row.vmSize,
							vmLocation: row.vmLocation,
							vmZone: row.vmZone,
							vmFaultDomain: row.vmFaultDomain,
							microcode: row.microcode,
							cpuModelRaw: row.cpuModel
						}
		});
	}

	return {
		runId,
		date,
		cards,
		nothing: null,
		recording: options.recording,
		nameOnly: cards.every((card) => card.source === 'counters')
	};
}

const MIB = 1024 * 1024;

/** A cache size in the unit this fleet's caches are actually quoted in.
 *
 * L3 runs 32 MiB to 480 MiB across the machines drawn so far, so MiB is the
 * unit that keeps a whole number on the card. Null in, a dash out - an absent
 * cache is not a cache of zero.
 */
export function cacheWords(bytes: number | null): string {
	if (bytes === null) return '-';
	return `${Math.round(bytes / MIB)} MiB`;
}

/** The bandwidth reading and the buffer it was taken with, in one sentence.
 *
 * They are one sentence because they are one fact. A buffer smaller than L3
 * never leaves cache and reads several times higher than memory, so a rate
 * printed without its buffer is a number a reader will take for a memory figure
 * (`docs/reference/host-metrics.md`).
 *
 * **No reading is a different fact from a rate of zero**, and it gets its own
 * sentence rather than a dash: the probe can be switched off, and a job that was
 * never asked did not measure slowly.
 */
export function bandwidthSentence(card: MachineCard): string {
	if (card.memcpyGibPerSecond === null) {
		return 'Bandwidth was not measured on this job.';
	}
	const rate = `${card.memcpyGibPerSecond.toFixed(1)} GiB/s`;
	if (card.memcpyProbeMib === null) return `${rate}. The buffer it used was not recorded.`;
	const against =
		card.l3CacheBytes === null
			? `over a ${card.memcpyProbeMib} MiB buffer`
			: `over a ${card.memcpyProbeMib} MiB buffer against ${cacheWords(card.l3CacheBytes)} of L3`;
	return card.measuredCache
		? `${rate}, ${against} - this measured cache, not memory.`
		: `${rate}, ${against}.`;
}
