/** Which stable categorical paint and qualified name belongs to each recorded machine kind? */
import type { FillGradient } from './d3/dateSeries';
import { scaleOrdinal } from 'd3-scale';
import { colourScheme } from './colour-scheme';
import { PALETTE, type ChartPaletteToken } from './theme';
import type { ChartConfig } from '../server/config';
import { UNRECORDED_KEY, UNRECORDED_NAME, type MachineIdentity } from './machine-colour';
import { RESERVED_GREY_INK } from './d3/ordered-colour';

export interface FleetIdentity {
	key: string;
	label: string;
	token: ChartPaletteToken;
	colour: string;
	gradient: FillGradient | null;
	swatch: string;
}

export function fleetIdentities(
	universe: readonly MachineIdentity[],
	appearance: { gradients: boolean; floor: number; palette: ChartConfig['palette'] }
): ReadonlyMap<string, FleetIdentity> {
	const known = [...universe].filter((machine) => machine.key !== UNRECORDED_KEY)
		.sort((a, b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
	const palette = PALETTE.filter((token) => token !== '--chart-8');
	const colours = scaleOrdinal<string, string>()
		.domain(known.map((machine) => machine.key))
		.range(appearance.palette === 'categorical' ? palette.map((token) => `var(${token})`)
			: colourScheme(appearance.palette));
	const names = new Map<string, string[]>();
	for (const machine of known) names.set(machine.name, [...(names.get(machine.name) ?? []), machine.key]);
	const share = (1 - appearance.floor) * 100;
	const identities = known.map((machine, index): FleetIdentity => {
		const same = names.get(machine.name)!;
		const token = palette[index % palette.length];
		const colour = colours(machine.key);
		const top = `color-mix(in oklab, ${colour} ${share}%, var(--chart-identity-highlight))`;
		const gradient = appearance.gradients ? { top, bottom: colour } : null;
		return {
			key: machine.key,
			label: same.length === 1 && machine.name !== UNRECORDED_NAME
				? machine.name : `${machine.name} (kind ${same.indexOf(machine.key) + 1})`,
			token, colour, gradient,
			swatch: gradient === null ? colour : `${colour} linear-gradient(180deg, ${top}, ${colour})`
		};
	});
	identities.push({
		key: UNRECORDED_KEY, label: UNRECORDED_NAME, token: '--chart-8',
		colour: RESERVED_GREY_INK, gradient: null, swatch: RESERVED_GREY_INK
	});
	return new Map(identities.map((identity) => [identity.key, identity]));
}
