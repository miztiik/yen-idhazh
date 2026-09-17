/** Which colour a machine takes, and why it is the same one at every span.
 *
 * Two panels on the hardware console draw a mark per machine and a third counts
 * them, so the three have to agree about which machine is which colour. They
 * agree by deriving it here from one key rather than by each assigning its own.
 *
 * **Ascending by key, and the key is arbitrary on purpose.** The fingerprint
 * where the machine record reached a run, and the processor's own model-name
 * string where it did not. Sorting by speed or by draw count would encode an
 * ordering the chart ramp does not mean, and sorting by order of first
 * appearance would change a machine's colour when the operator changes the
 * window - which is the control the colour exists to survive.
 *
 * **Colour is never the only carrier.** Every identity here holds the machine's
 * name in words, and every row that takes an edge prints that name beside it.
 *
 * Pure and dependency-free, so the browser suite drives it in plain Node.
 */

import { machineName } from './machine-name';

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
export const UNRECORDED_STOP = 8;

/** What the fold row is called once the ramp runs out. */
export const FOLDED_NAME = 'Other machines';

export const FOLDED_KEY = 'other-machines';

/** One machine as the page draws it: a key, a name and a stop of the ramp. */
export interface MachineIdentity {
	key: string;
	/** The machine in words. On the row, always. */
	name: string;
	/** 1-based stop of `--chart-1` to `--chart-8`. */
	colourStop: number;
	/** The machines folded into this row, named in words. Empty on a real one. */
	folded: string[];
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

/** The CSS custom property a stop resolves to. */
export function machineColour(stop: number): string {
	return `var(--chart-${stop})`;
}

/** Whether this identity is the one the ramp reserves for an absence. */
export function isUnrecorded(identity: MachineIdentity): boolean {
	return identity.key === UNRECORDED_KEY;
}

/** The ramp as a whole: the rows a legend draws, and where any key lands.
 *
 * `at` resolves every key handed in, folded ones included, so a caller never has
 * to ask whether the ramp ran out before it can draw a machine.
 */
export interface MachineRamp {
	rows: MachineIdentity[];
	at: ReadonlyMap<string, MachineIdentity>;
}

/** Every distinct machine, in key order, with the stop it keeps at every span.
 *
 * Shards that recorded no machine arrive under `UNRECORDED_KEY` and leave with
 * the reserved stop, whatever else is on the list.
 *
 * **Folding only happens when it has to.** With `stops` of seven, seven machines
 * take seven stops. An eighth is what folds: the first `stops - 1` keep a colour
 * of their own and everything past them becomes one row on the last stop,
 * naming its members. Handing the fold row a stop a machine already holds would
 * put two machines in one colour with nothing on the page to say so, and taking
 * the reserved grey would say the fold was an absence.
 */
export function machineRamp(machines: readonly MachineKey[], stops: number): MachineRamp {
	const byKey = new Map<string, string>();
	for (const machine of machines) {
		if (!byKey.has(machine.key)) byKey.set(machine.key, machine.name);
	}
	const unrecorded = byKey.has(UNRECORDED_KEY);
	byKey.delete(UNRECORDED_KEY);

	const named = [...byKey.entries()].sort(([left], [right]) =>
		left < right ? -1 : left > right ? 1 : 0
	);
	const room = Math.max(1, Math.min(stops, UNRECORDED_STOP - 1));

	const rows: MachineIdentity[] = [];
	const at = new Map<string, MachineIdentity>();
	const keep = named.length <= room ? named : named.slice(0, room - 1);
	keep.forEach(([key, name], index) => {
		const identity = { key, name, colourStop: index + 1, folded: [] };
		rows.push(identity);
		at.set(key, identity);
	});
	if (named.length > room) {
		const folded = named.slice(room - 1);
		const identity: MachineIdentity = {
			key: FOLDED_KEY,
			name: FOLDED_NAME,
			colourStop: room,
			folded: folded.map(([, name]) => name)
		};
		rows.push(identity);
		for (const [key] of folded) at.set(key, identity);
	}
	if (unrecorded) {
		const identity: MachineIdentity = {
			key: UNRECORDED_KEY,
			name: UNRECORDED_NAME,
			colourStop: UNRECORDED_STOP,
			folded: []
		};
		rows.push(identity);
		at.set(UNRECORDED_KEY, identity);
	}
	return { rows, at };
}
