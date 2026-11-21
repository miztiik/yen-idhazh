/** Which stable categorical paint and qualified name belongs to each recorded machine kind? */
import { PALETTE, type ChartPaletteToken } from './theme';
import { UNRECORDED_KEY, UNRECORDED_NAME, type MachineIdentity } from './machine-colour';
import { RESERVED_GREY_INK } from './d3/ordered-colour';

export const FLEET_PALETTE = PALETTE.filter((token) => token !== '--chart-8');

export interface FleetIdentity {
	key: string;
	label: string;
	token: ChartPaletteToken;
	colour: string;
}

export function fleetIdentities(
	universe: readonly MachineIdentity[]
): ReadonlyMap<string, FleetIdentity> {
	const known = [...universe].filter((machine) => machine.key !== UNRECORDED_KEY)
		.sort((a, b) => a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
	const names = new Map<string, string[]>();
	for (const machine of known) names.set(machine.name, [...(names.get(machine.name) ?? []), machine.key]);
	const identities = known.map((machine, index): FleetIdentity => {
		const same = names.get(machine.name)!;
		const token = FLEET_PALETTE[index % FLEET_PALETTE.length];
		return {
			key: machine.key,
			label: same.length === 1 && machine.name !== UNRECORDED_NAME
				? machine.name : `${machine.name} (kind ${same.indexOf(machine.key) + 1})`,
			token, colour: `var(${token})`
		};
	});
	identities.push({
		key: UNRECORDED_KEY, label: UNRECORDED_NAME, token: '--chart-8',
		colour: RESERVED_GREY_INK
	});
	return new Map(identities.map((identity) => [identity.key, identity]));
}
