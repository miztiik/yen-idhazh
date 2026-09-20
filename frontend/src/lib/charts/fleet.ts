/** What the platform has been giving us, counted over a window.
 *
 * One entry per kind of machine, counted over the job placements the machine
 * record holds for the open span. A count of what happened and never a rate: the
 * share of a *future* draw is precisely what the processor lottery refuses to
 * quote, so no percentage, no probability and no pie belongs on this panel.
 *
 * **Under a stated number of rows it is a list and not a chart.** Bars over a
 * handful of placements read as a distribution and it is not one - and the
 * damage is not cosmetic, because a reader who has read a distribution off nine
 * rows will act on it. `console.fleet_min_rows` is the number, a declared
 * estimate derived from the rarest kind's 3.1 percent share of 356 committed
 * counter rows and the 5-observation floor `console.min_attempts_for_rate`
 * already sets.
 *
 * Pure. The threshold, the window and the switch arrive as arguments.
 */

import type { HostFingerprint } from '$lib/server/host-fingerprint';
import type { LostDay } from '$lib/console/recording';
import {
	machineKeys,
	machineRamp,
	type MachineIdentity,
	type MachineKey,
	type MachineRamp,
	type MachineSeen
} from './machine-colour';
import { rank, type Ranked, type RankedDisplay } from './rank';

export interface FleetView {
	/** Ranked by count, descending. Empty where nothing was recorded. */
	ranked: Ranked<RankedDisplay>;
	/** Every kind and its count, in the same order, with its colour. */
	kinds: { identity: MachineIdentity; placements: number }[];
	/** Job placements the count was made from. The denominator, printed. */
	placements: number;
	/** Days the window covers. */
	days: number;
	/** The threshold, so the sentence under the gate can state it. */
	minRows: number;
	/** True at or above the threshold. Below it the panel lists and draws no bar. */
	drawBars: boolean;
	/** Why there is nothing. Null where there is something.
	 *
	 * `record-lost` and `none` are the two the panel could not tell apart until
	 * 2026-09-17: a window whose every recorded day published articles and kept
	 * no row is a window that lost its count, not one waiting for a first run.
	 */
	nothing: 'recording-off' | 'record-lost' | 'none' | null;
}

/** Machine kinds over the window, ranked by how often the platform gave us one. */
export function fleetOverWindow(
	rows: readonly HostFingerprint[],
	options: {
		days: number;
		minRows: number;
		colourStops: number;
		/** False where the machine record is switched off. */
		recording: boolean;
		ramp?: MachineRamp;
		/** The page's own key resolver, built over the same population as the ramp. */
		keys?: (seen: MachineSeen) => MachineKey;
		/** Rows outside the open span are dropped before they are counted. */
		start?: string;
		end?: string;
		/** Days in this span that published articles and that the record kept no
		 * row of. Only their presence is read here; the sentence is the route's. */
		lost?: readonly LostDay[];
	}
): FleetView {
	const inWindow = rows.filter(
		(row) =>
			(options.start === undefined || row.date >= options.start) &&
			(options.end === undefined || row.date <= options.end)
	);
	const seen = inWindow.map((row) => ({ fingerprint: row.fingerprint, cpuModel: row.cpu_model }));
	const resolve = options.keys ?? machineKeys(seen);
	const keys = seen.map(resolve);
	const ramp = options.ramp ?? machineRamp(keys, options.colourStops);

	const counts = new Map<string, number>();
	for (const key of keys) {
		const identity = ramp.at.get(key.key);
		if (identity === undefined) continue;
		counts.set(identity.key, (counts.get(identity.key) ?? 0) + 1);
	}

	const kinds = ramp.rows
		.filter((identity) => (counts.get(identity.key) ?? 0) > 0)
		.map((identity) => ({ identity, placements: counts.get(identity.key) ?? 0 }))
		.sort((a, b) => b.placements - a.placements || a.identity.key.localeCompare(b.identity.key));

	// No cap: the ramp already bounds the row count, so a `Show more` here would
	// reveal nothing (`console.machine_colour_stops` plus the reserved grey).
	const ranked = rank(
		kinds.map((kind) => ({
			key: kind.identity.key,
			value: kind.placements,
			row: {
				label: kind.identity.name,
				value: `${kind.placements}`,
				context: kind.identity.folded.length > 0 ? kind.identity.folded.join(', ') : null
			}
		})),
		0
	);

	return {
		ranked,
		kinds,
		placements: inWindow.length,
		days: options.days,
		minRows: options.minRows,
		drawBars: inWindow.length >= options.minRows,
		nothing: !options.recording
			? 'recording-off'
			: inWindow.length > 0
				? null
				: (options.lost ?? []).length > 0
					? 'record-lost'
					: 'none'
	};
}
