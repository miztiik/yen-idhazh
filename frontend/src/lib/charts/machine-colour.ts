/** Which versioned machine identities and whole-record speed groups keep history ordered?
 *
 * The legacy ramp supplies ordering and fold membership. Machine history uses
 * fleet-identity.ts for categorical paint, independently of these speed groups.
 */

import { median } from 'd3-array';

import { orderedRamp, RESERVED_GREY, RESERVED_GREY_INK } from './d3/ordered-colour';
import { machineName } from './machine-name';
import type { ChartToken } from './theme';
import { formatNumber, type NumberFormatConfig } from '../number-format';

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

/** One whole-record machine identity and its established speed-group metadata. */
export interface MachineIdentity {
	key: string;
	/** Fingerprint algorithm, or null for a coarse name-only/unknown group. */
	fingerprintVersion: 1 | 2 | null;
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
	fingerprintVersion: 1 | 2 | null;
}

/** What a placement recorded about its machine. Either cell may be absent. */
export interface VersionedFingerprint {
	fingerprint: string | null;
	fingerprintVersion: number | null;
}

export interface MachineSeen extends VersionedFingerprint {
	cpuModel: string | null;
}

/** Version plus digest is an identity; name-only evidence never joins a fingerprint.
 * A digest without a CPU name remains named by its digest, not by colour alone. */
export function machineKeys(
	_population: readonly MachineSeen[]
): (seen: MachineSeen) => MachineKey {
	return (seen: MachineSeen): MachineKey => {
		const name = machineName(seen.cpuModel);
		const digest = seen.fingerprint === '' ? null : seen.fingerprint;
		const version =
			seen.fingerprintVersion === 1 || seen.fingerprintVersion === 2
				? seen.fingerprintVersion
				: null;
		if (digest !== null && version !== null) {
			return {
				key: `v${version}:${digest}`,
				name: name === '' ? digest : name,
				fingerprintVersion: version
			};
		}
		if (name === '') {
			return { key: UNRECORDED_KEY, name: '', fingerprintVersion: null };
		}
		return { key: `name:${name}`, name, fingerprintVersion: null };
	};
}

/** The key one placement resolves to, with nothing else to compare it against.
 *
 * The single-placement form of `machineKeys`, for a caller that has one row and
 * no population - a test, or a lookup that only needs the name.
 */
export function machineKey(
	fingerprintVersion: number | null,
	fingerprint: string | null,
	cpuModel: string | null
): MachineKey {
	const seen = { fingerprintVersion, fingerprint, cpuModel };
	return machineKeys([seen])(seen);
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
export function rateWords(rate: number, numberFormat: NumberFormatConfig): string {
	return `${formatNumber(rate, numberFormat)} tokens a second`;
}

/** The speed a machine's colour stands for, in words, so a colour is never the
 * only carrier of it. Null for no machine recorded, which has no speed to say. */
export function speedWords(identity: MachineIdentity, numberFormat: NumberFormatConfig): string | null {
	if (isUnrecorded(identity)) return null;
	return identity.rate === null ? 'no speed reading' : rateWords(identity.rate, numberFormat);
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
	const byKey = new Map<
		string,
		{ name: string; fingerprintVersion: 1 | 2 | null; rates: number[] }
	>();
	let unrecorded = false;
	for (const placement of placements) {
		const { key, name } = placement.machine;
		if (key === UNRECORDED_KEY) {
			unrecorded = true;
			continue;
		}
		const held = byKey.get(key) ?? {
			name,
			fingerprintVersion: placement.machine.fingerprintVersion,
			rates: []
		};
		if (name < held.name) held.name = name;
		if (placement.rate !== null && Number.isFinite(placement.rate)) held.rates.push(placement.rate);
		byKey.set(key, held);
	}

	const kinds = [...byKey.entries()].map(([key, held]) => ({
		key,
		name: held.name,
		fingerprintVersion: held.fingerprintVersion,
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
			fingerprintVersion: kind.fingerprintVersion,
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
			fingerprintVersion: null,
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
