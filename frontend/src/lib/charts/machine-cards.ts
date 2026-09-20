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
 * **L3 and the copy rate are lengths on a track every card shares.** Two
 * numbers in two sentences on two cards is a subtraction the reader performs;
 * two bars on one domain is a difference the eye reads. The domain comes from
 * the cards drawn, because no runner model publishes a ceiling for either.
 *
 * Pure. The flag vocabulary, the colour ramp and the switch all arrive as
 * arguments, so a test drives them and Guardrail #6 keeps the knobs in `config/`.
 */

import type { HostFingerprint } from '$lib/server/host-fingerprint';
import type { MachineRun } from '$lib/server/machine-counters';
import { recordDestroyed, type LostDay } from '$lib/console/recording';
import { linearAxis } from './frame';
import { percentOf } from './rank';
import {
	machineKeys,
	machineRamp,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp,
	type MachineSeen
} from './machine-colour';

const MIB = 1024 * 1024;

/** One chip: a watched flag, and whether this machine reported it. */
export interface FlagChip {
	name: string;
	present: boolean;
}

/** Whether a reading is drawn against the other cards, and why not where it is
 * not.
 *
 * `absent` - nothing read it, so there is no length to draw. `alone` - under two
 * cards carry a reading of this kind, and a bar whose domain is its own value
 * fills its track whatever it says, which reads as a maximum rather than as the
 * only one. `cache` - the bandwidth probe never left L3, so that reading is
 * several times a memory one and shares no track with it
 * (`docs/reference/host-metrics.md`).
 */
export type CardBarState = 'drawn' | 'absent' | 'alone' | 'cache';

/** One reading on the track every card of this panel shares. */
export interface CardBar {
	/** Where the fill ends along the track, 0 to 1. Zero unless drawn. */
	fraction: number;
	/** The same fraction as a CSS length, so the card does no arithmetic. */
	percent: string;
	/** The top of the shared domain, in the reading's own unit. Zero unless
	 * drawn, and the same number on every card of one panel by construction. */
	top: number;
	/** How many cards the domain was built from. */
	of: number;
	state: CardBarState;
	/** The reading, and the top of its track, in one unit. One formatter builds
	 * both, so a label and the track it labels cannot disagree about the unit.
	 * Empty where there is nothing drawn. */
	valueWords: string;
	topWords: string;
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
	/** Which ledger built it. `name-only` is the item ledger's `cpu_model`, which
	 * carries a name and nothing else. */
	source: 'fingerprint' | 'name-only';
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
	/** This card's L3 on the track every card of this panel shares, in MiB. */
	l3Bar: CardBar;
	/** This card's copy rate on the shared track, in GiB/s. Memory readings
	 * only - a cache reading is refused rather than pooled with them. */
	bandwidthBar: CardBar;
	/** Jobs of this run that drew this machine, and jobs that recorded one. */
	jobsDrawn: number;
	jobsTotal: number;
	where: MachineWhere | null;
}

/** What the machine record was doing on the day this run ran, as one name.
 *
 * Always set, and that is the point. A page that says its state only by which
 * sentence it prints can be checked only by looking for a sentence, and an
 * assertion that a sentence is absent passes just as happily when the sentence
 * was renamed as when the state was fixed.
 *
 * `lost` is the state this type was added for: the day published articles and
 * the record kept no row of it.
 */
export type MachineRecordState = 'recorded' | 'off' | 'lost' | 'none';

export interface MachineCards {
	runId: string;
	date: string;
	cards: MachineCard[];
	/** Why there is nothing to draw. Null where there are cards. */
	nothing: 'recording-off' | 'record-lost' | 'no-machine' | null;
	/** False where the machine record is switched off.
	 *
	 * Carried even when there are cards, because the item ledger still names a
	 * processor: a panel that drew those cards silently would say the instruction
	 * set is missing when it was never asked for.
	 */
	recording: boolean;
	/** True where no card could carry an instruction set, so the panel says the
	 * flags, the cache and the bandwidth start on the day the record ran. */
	nameOnly: boolean;
	/** This run's day, where it published articles and the record kept no row of
	 * it. Null on every other day, including a day that published nothing. */
	lost: LostDay | null;
	/** That loss in words, or null. One builder, so the route and this panel
	 * cannot drift into two ways of saying the same thing. */
	lostNote: string | null;
	/** The state above as one name, for a page assertion that cannot fail open. */
	record: MachineRecordState;
}

/** One job of a run, as a thing that drew a machine. */
interface Placement {
	key: string;
	name: string;
	row: HostFingerprint | null;
}

/** A card before its bars. The tracks are built over every card, so no card
 * can carry one until all of them exist. */
type CardParts = Omit<MachineCard, 'l3Bar' | 'bandwidthBar'>;

function part(row: HostFingerprint): string | null {
	const cells = [row.cpu_family, row.cpu_model_number, row.cpu_stepping];
	if (cells.some((cell) => cell === null)) return null;
	return cells.join('/');
}

function chips(row: HostFingerprint | null, watched: readonly string[]): FlagChip[] {
	if (row === null || watched.length === 0) return [];
	// The contract's own shape is one space-joined cell, split here rather than in
	// the reader: that module is server-only and this one is bundled for a browser.
	const present = new Set(row.flags.split(/\s+/).filter((flag) => flag !== ''));
	return watched.map((name) => ({ name, present: present.has(name) }));
}

/** Where a fraction of the shared track falls, and how far the track runs. */
interface SharedTrack {
	top: number;
	of: number;
	at: (value: number) => number;
	words: (value: number) => string;
}

/** One measure's track, built once and shared by every card the panel draws.
 *
 * The domain is the readings drawn, anchored at zero and niced by the scale
 * library. Neither L3 nor a copy rate has a ceiling across the machines a
 * runner pool hands out - the record holds 32, 260 and 480 MiB of L3 - so there
 * is no limit to measure distance from, and a fixed maximum would clip the next
 * bigger machine or spend the track on room nothing reaches
 * (`docs/concepts/console-design.md`).
 *
 * Under two readings the track is refused. A lone bar's domain is its own
 * value, so it fills the track whatever it says, and a full bar reads as a
 * maximum rather than as the only one this run drew.
 */
function sharedTrack(
	values: readonly (number | null)[],
	words: (value: number) => string
): SharedTrack {
	const kept = values.filter(
		(value): value is number => value !== null && Number.isFinite(value) && value > 0
	);
	if (kept.length < 2) return { top: 0, of: kept.length, at: () => 0, words };
	const axis = linearAxis(kept, [0, 1]);
	return { top: axis.domain[1], of: kept.length, at: axis.scale, words };
}

/** One card's reading on that track, or the name of why it is not on it.
 *
 * `refuse` is the reading this domain will not hold. A non-positive reading has
 * no length to draw and is named absent; the sentence beside it still prints
 * what was read.
 */
function cardBar(
	value: number | null,
	track: SharedTrack,
	refuse: CardBarState | null = null
): CardBar {
	const state: CardBarState =
		value === null || !Number.isFinite(value) || value <= 0
			? 'absent'
			: (refuse ?? (track.of < 2 ? 'alone' : 'drawn'));
	const drawn = state === 'drawn' && value !== null;
	const fraction = drawn ? track.at(value) : 0;
	return {
		fraction,
		percent: percentOf(fraction),
		top: track.top,
		of: track.of,
		state,
		valueWords: drawn && value !== null ? track.words(value) : '',
		topWords: drawn ? track.words(track.top) : ''
	};
}

/** The machines the newest run drew, one card each.
 *
 * `fingerprints` are the machine record's rows for this run - one a job, so a
 * work shard, the planner and the assembler each contribute one. A work shard
 * the record did not reach still contributes a placement, off the item ledger's
 * own `cpu_model`, carrying its processor's name and nothing else.
 */
export function machineCards(
	run: MachineRun | null,
	fingerprints: readonly HostFingerprint[],
	options: {
		watchedFlags: readonly string[];
		colourStops: number;
		/** False where the machine record is switched off. */
		recording: boolean;
		ramp?: MachineRamp;
		/** The page's own key resolver, built over the same population as the ramp. */
		keys?: (seen: MachineSeen) => MachineKey;
		/** This run's day where it published articles and the record kept no row of
		 * it. The caller does the join, because only it reads both ledgers. */
		lost?: LostDay | null;
	}
): MachineCards {
	const runId = run?.runId ?? '';
	const date = run?.date ?? '';
	const lost = options.lost ?? null;
	const lostNote = recordDestroyed(lost === null ? [] : [lost]);
	const forRun = run === null ? [] : fingerprints.filter((row) => row.run_id === run.runId);
	const covered = new Set(
		forRun.filter((row) => row.job === 'work').map((row) => String(row.shard))
	);

	const seen: MachineSeen[] = [
		...forRun.map((row) => ({ fingerprint: row.fingerprint, cpuModel: row.cpu_model })),
		...(run?.reported ?? [])
			.filter((shard) => !covered.has(String(shard.shard)))
			.map((shard) => ({ fingerprint: null, cpuModel: shard.cpuModel }))
	];
	const resolve = options.keys ?? machineKeys(seen);

	const placements: Placement[] = [];
	for (const row of forRun) {
		placements.push({
			...resolve({ fingerprint: row.fingerprint, cpuModel: row.cpu_model }),
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
			// A day that published and kept no row is a loss, and it is named before
			// the quiet-day sentence gets a chance to claim it.
			nothing: !options.recording ? 'recording-off' : lost !== null ? 'record-lost' : 'no-machine',
			recording: options.recording,
			nameOnly: true,
			lost,
			lostNote,
			record: recordState(options.recording, lost, false)
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

	const cards: CardParts[] = [];
	for (const identity of ramp.rows) {
		const drawn = byIdentity.get(identity.key) ?? [];
		if (drawn.length === 0) continue;
		// The richest row wins, and a row is richer when it read the instruction
		// set. Every row for one fingerprint reports the same cells by
		// construction - the digest is taken over exactly those cells - so this
		// only ever chooses between a recorded row and an absent one.
		const row = drawn.find((placement) => placement.row !== null)?.row ?? null;
		const l3 = row?.l3_cache_bytes ?? null;
		const buffer = row?.memcpy_probe_mib ?? null;
		cards.push({
			identity,
			source: row === null ? 'name-only' : 'fingerprint',
			part: row === null ? null : part(row),
			flags: chips(row, options.watchedFlags),
			flagsRecorded: row !== null && options.watchedFlags.length > 0,
			l3CacheBytes: l3,
			memcpyGibPerSecond: row?.memcpy_gib_s ?? null,
			memcpyProbeMib: buffer,
			measuredCache:
				buffer !== null && buffer > 0 && l3 !== null && buffer * MIB <= l3,
			jobsDrawn: drawn.length,
			jobsTotal: placements.length,
			where:
				row === null
					? null
					: {
							vmSize: row.vm_size,
							vmLocation: row.vm_location,
							vmZone: row.vm_zone,
							vmFaultDomain: row.vm_fault_domain,
							microcode: row.microcode,
							cpuModelRaw: row.cpu_model
						}
		});
	}

	// Both tracks are built over every card first, so the same domain reaches
	// each of them. A per-card domain would delete the one comparison the bars
	// exist for (`docs/concepts/console-design.md`).
	const l3Track = sharedTrack(
		cards.map((card) => cacheMib(card.l3CacheBytes)),
		(mib) => cacheWords(mib * MIB)
	);
	const rateTrack = sharedTrack(
		cards.map((card) => (card.measuredCache ? null : card.memcpyGibPerSecond)),
		rateWords
	);
	const drawnCards: MachineCard[] = cards.map((card) => ({
		...card,
		l3Bar: cardBar(cacheMib(card.l3CacheBytes), l3Track),
		bandwidthBar: cardBar(
			card.memcpyGibPerSecond,
			rateTrack,
			card.measuredCache ? 'cache' : null
		)
	}));

	return {
		runId,
		date,
		cards: drawnCards,
		nothing: null,
		recording: options.recording,
		nameOnly: cards.every((card) => card.source === 'name-only'),
		lost,
		lostNote,
		record: recordState(
			options.recording,
			lost,
			cards.some((card) => card.source === 'fingerprint')
		)
	};
}

function recordState(
	recording: boolean,
	lost: LostDay | null,
	anyRecorded: boolean
): MachineRecordState {
	if (!recording) return 'off';
	if (lost !== null) return 'lost';
	return anyRecorded ? 'recorded' : 'none';
}

/** A cache size in MiB, the unit its track and its words are both in. Null in,
 * null out - an absent cache is not a cache of zero. */
function cacheMib(bytes: number | null): number | null {
	return bytes === null ? null : bytes / MIB;
}

/** A copy rate in the unit the probe reports it in. The bar's label and the
 * sentence under it both come through here, so they cannot round differently. */
function rateWords(rate: number): string {
	return `${rate.toFixed(1)} GiB/s`;
}

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
	const rate = rateWords(card.memcpyGibPerSecond);
	if (card.memcpyProbeMib === null) return `${rate}. The buffer it used was not recorded.`;
	const against =
		card.l3CacheBytes === null
			? `over a ${card.memcpyProbeMib} MiB buffer`
			: `over a ${card.memcpyProbeMib} MiB buffer against ${cacheWords(card.l3CacheBytes)} of L3`;
	return card.measuredCache
		? `${rate}, ${against} - this measured cache, not memory.`
		: `${rate}, ${against}.`;
}
