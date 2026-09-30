/** Which colour a machine takes: its speed, as one hue in steps.
 *
 * Three panels on the hardware console draw a machine - the kinds the platform
 * gave us day by day, one run's shards split by machine, and one card a machine
 * - so the three have to agree about which machine is which colour. They agree
 * by deriving it here, once for the page, from one list of placements.
 *
 * **The colour is the machine's speed, and nothing else.** A kind of machine
 * takes the step of an ordered ramp its median prompt reading speed falls in -
 * `server_prompt_tokens` over `server_prompt_seconds`, one reading a job that
 * took one - and the steps are cut at the quantiles of every kind's median over
 * the whole record the page holds. So a machine keeps its colour when the
 * operator changes the span, and a stronger colour is a faster machine in
 * either theme. The steps are cut from each kind's median rather than from
 * every job's reading, because one machine gives most of the readings - 102 of
 * 176 on 2026-09-30 - and would otherwise take most of the steps for itself.
 *
 * **Kinds on one step share its colour, so a colour never names a machine.**
 * The name and the speed are printed beside every machine a panel draws. Until
 * 2026-09-30 the colour was a hue a machine, handed out in the order of an
 * arbitrary key, and a machine whose key sorted late went without a colour
 * however often it ran.
 *
 * **A kind is one fingerprint, not a processor name.** Two records of one
 * processor read prompts at 8.7 and 12.3 tokens a second, measured 2026-09-30,
 * so a name is not a speed.
 *
 * **Two greys sit outside the ramp.** A job whose machine nobody recorded is the
 * reserved grey, flat. A known machine none of whose jobs took a speed reading
 * is that grey in stripes, because it is a machine and not an absence.
 *
 * Pure, so the browser suite drives it in plain Node.
 */

import { median } from 'd3-array';

import { orderedRamp, RESERVED_GREY, RESERVED_GREY_INK } from './d3/ordered-colour';
import { machineName } from './machine-name';
import type { ChartToken } from './theme';

/** The key the shards that recorded no machine are grouped under.
 *
 * The same sentinel `backend/idhazh/contracts/machine_panels.py` declares. A key
 * rather than an empty string, so the group sorts and keys a DOM node like any
 * other and nothing has to carry a special case for it.
 */
export const UNRECORDED_KEY = 'unrecorded';

/** What that group is called on screen. Never the name of a column or a switch. */
export const UNRECORDED_NAME = 'Machine not recorded';

/** The grey of the chart ramp, kept for that group and given to nothing else.
 *
 * An absence is not a machine and must not take a machine's hue.
 */
export const UNRECORDED_STOP = RESERVED_GREY;

/** The one hue the speed ramp mixes. One hue, because a speed has a direction
 * and nobody can rank several hues; the first chart hue, because it holds the
 * most contrast against the panel in both themes. */
export const MACHINE_HUE: ChartToken = '--chart-1';

/** One machine as the page draws it: a key, a name and the colour of its speed. */
export interface MachineIdentity {
	key: string;
	/** The machine in words. On the row, always. */
	name: string;
	/** The 1-based step of the speed ramp, slowest first. Null for a machine
	 * none of whose jobs took a speed reading, and for no machine recorded. */
	step: number | null;
	/** The kind's median prompt reading speed over the record, in tokens a
	 * second. Null where no job of the kind took a reading. */
	rate: number | null;
	/** The fill this machine is drawn in: a step of the ramp, or the reserved
	 * grey. A machine with no speed reading is drawn in this grey as stripes. */
	colour: string;
}

/** A machine as a caller knows it, before a colour has been decided. */
export interface MachineKey {
	key: string;
	name: string;
}

/** What a placement recorded about its machine. Either cell may be absent. */
export interface MachineSeen {
	fingerprint: string | null;
	cpuModel: string | null;
}

/** The one key every panel groups, sorts and colours a machine by.
 *
 * The digest where the machine record reached this job, because two machines
 * reporting one model name are not the same machine - four draws all reporting
 * AMD EPYC 7763 differed by 8.8 percent on decode
 * (`docs/reference/host-metrics.md`). The processor's own name where it did
 * not, which is coarser and is the best key the counters ledger holds.
 *
 * **A job the record missed joins the machine of the same name when the
 * population holds exactly one digest for that name.** Without that rule one
 * machine draws two cards under one heading - the recorded job's and the
 * counters-only job's - which reads as a defect rather than as the honest
 * absence it is. Where a name really does carry two digests they stay apart,
 * and a name-only job keeps a group of its own, because which of the two it was
 * is the thing nobody knows.
 *
 * Neither cell recorded is `UNRECORDED_KEY`, and the name is left empty: a
 * caller with nothing has a different sentence to print, and a placeholder name
 * here would take it away.
 *
 * **A machine that recorded a digest but no model name is named by its digest.**
 * That is not much of a name, and it is a real identifier the record holds - the
 * same machine carries the same one on every row. An empty name is the one thing
 * that cannot ship, because colour would then be the only carrier.
 */
export function machineKeys(
	population: readonly MachineSeen[]
): (seen: MachineSeen) => MachineKey {
	const digestsByName = new Map<string, Set<string>>();
	for (const seen of population) {
		if (seen.fingerprint === null || seen.fingerprint === '') continue;
		const name = machineName(seen.cpuModel);
		if (name === '') continue;
		const held = digestsByName.get(name);
		if (held === undefined) digestsByName.set(name, new Set([seen.fingerprint]));
		else held.add(seen.fingerprint);
	}
	return (seen: MachineSeen): MachineKey => {
		const name = machineName(seen.cpuModel);
		const digest = seen.fingerprint === '' ? null : seen.fingerprint;
		if (name === '') {
			return digest === null ? { key: UNRECORDED_KEY, name: '' } : { key: digest, name: digest };
		}
		const known = digestsByName.get(name);
		if (known !== undefined && known.size === 1) return { key: [...known][0], name };
		return { key: digest ?? name, name };
	};
}

/** The key one placement resolves to, with nothing else to compare it against.
 *
 * The single-placement form of `machineKeys`, for a caller that has one row and
 * no population - a test, or a lookup that only needs the name.
 */
export function machineKey(fingerprint: string | null, cpuModel: string | null): MachineKey {
	return machineKeys([{ fingerprint, cpuModel }])({ fingerprint, cpuModel });
}

/** Whether this identity is the one the ramp reserves for an absence. */
export function isUnrecorded(identity: MachineIdentity): boolean {
	return identity.key === UNRECORDED_KEY;
}

/** Whether this is a known machine that never took a speed reading, which is
 * drawn as the grey in stripes rather than as a step of the ramp. */
export function isUntimed(identity: MachineIdentity): boolean {
	return identity.key !== UNRECORDED_KEY && identity.step === null;
}

/** Prompt tokens read a second, or null where either cell is missing or no time
 * was spent. The one definition every caller computes a job's speed with. */
export function promptRate(tokens: number | null, seconds: number | null): number | null {
	if (tokens === null || seconds === null || !(seconds > 0) || !Number.isFinite(tokens)) return null;
	return tokens / seconds;
}

/** A reading speed in words, to one decimal: `8.8 tokens a second`. */
export function rateWords(rate: number): string {
	return `${rate.toFixed(1)} tokens a second`;
}

/** The speed a machine's colour stands for, in words, so a colour is never the
 * only carrier of it. Null for no machine recorded, which has no speed to say. */
export function speedWords(identity: MachineIdentity): string | null {
	if (isUnrecorded(identity)) return null;
	return identity.rate === null ? 'no speed reading' : rateWords(identity.rate);
}

/** One job as the ramp takes it: which machine, and its reading speed where the
 * job took one. */
export interface Placement {
	machine: MachineKey;
	/** Prompt tokens read a second, or null where the job took no reading. */
	rate: number | null;
}

/** One step of the ramp as a key names it. */
export interface MachineStep {
	step: number;
	colour: string;
	/** The slowest and the fastest kind median on this step over the record, or
	 * null where no kind sits on it. A key names a step by the speeds that landed
	 * on it, never by a cut, which is where the ramp divides and not a reading. */
	low: number | null;
	high: number | null;
}

/** The ramp as a whole: every machine, where any key lands, and each step. */
export interface MachineRamp {
	/** Every machine, slowest first, then the machines with no speed reading,
	 * then no machine recorded. */
	rows: MachineIdentity[];
	at: ReadonlyMap<string, MachineIdentity>;
	steps: MachineStep[];
}

/** Every machine in the placements, with the step its speed takes at every span.
 *
 * `placements` is every job the page can show at any span, so the steps are cut
 * over the whole record rather than the window on screen. `stops` is how many
 * steps the ramp has and `floor` the share of the hue the slowest carries, both
 * from `config/appearance.json`.
 */
export function machineRamp(
	placements: readonly Placement[],
	options: { stops: number; floor: number }
): MachineRamp {
	const byKey = new Map<string, { name: string; rates: number[] }>();
	let unrecorded = false;
	for (const placement of placements) {
		const { key, name } = placement.machine;
		if (key === UNRECORDED_KEY) {
			unrecorded = true;
			continue;
		}
		const held = byKey.get(key) ?? { name, rates: [] };
		if (placement.rate !== null && Number.isFinite(placement.rate)) held.rates.push(placement.rate);
		byKey.set(key, held);
	}

	const kinds = [...byKey.entries()].map(([key, held]) => ({
		key,
		name: held.name,
		rate: held.rates.length === 0 ? null : (median(held.rates) ?? null)
	}));
	const ramp = orderedRamp(
		kinds.flatMap((kind) => (kind.rate === null ? [] : [kind.rate])),
		options.stops,
		MACHINE_HUE,
		options.floor
	);

	const identities: MachineIdentity[] = kinds.map((kind) => {
		const step = ramp === null || kind.rate === null ? null : ramp.stepOf(kind.rate);
		return {
			key: kind.key,
			name: kind.name,
			step,
			rate: kind.rate,
			colour: ramp === null || step === null ? RESERVED_GREY_INK : ramp.colours[step - 1]
		};
	});
	// Slowest first, so every list a panel draws off this reads slower to faster.
	identities.sort(
		(a, b) =>
			(a.rate === null ? 1 : 0) - (b.rate === null ? 1 : 0) ||
			(a.rate ?? 0) - (b.rate ?? 0) ||
			a.name.localeCompare(b.name) ||
			a.key.localeCompare(b.key)
	);
	if (unrecorded) {
		identities.push({
			key: UNRECORDED_KEY,
			name: UNRECORDED_NAME,
			step: null,
			rate: null,
			colour: RESERVED_GREY_INK
		});
	}

	const steps: MachineStep[] = Array.from({ length: options.stops }, (_, index) => {
		const step = index + 1;
		const on = identities.flatMap((identity) =>
			identity.step === step && identity.rate !== null ? [identity.rate] : []
		);
		return {
			step,
			colour: ramp === null ? RESERVED_GREY_INK : ramp.colours[index],
			low: on.length === 0 ? null : Math.min(...on),
			high: on.length === 0 ? null : Math.max(...on)
		};
	});

	return {
		rows: identities,
		at: new Map(identities.map((identity) => [identity.key, identity])),
		steps
	};
}
