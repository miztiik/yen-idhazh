/** Put browser destinations beside the routes reported by the published band. */
import { CLEAR, type ConsoleRoute, type RouteId } from './band';

export type ConsoleDestination = Omit<ConsoleRoute, 'id'> & { id: RouteId | 'operations' };
export type ConsoleDestinationId = ConsoleDestination['id'];

const operations: ConsoleDestination = {
	id: 'operations', label: 'Operations', href: '/console/operations/',
	description: 'What Council reported and which packs Gardener wrote.', worst: null, severity: CLEAR
};

export const consoleDestinationIds = [
	'pipelines', 'operations', 'machine', 'model', 'judgement', 'voices', 'data-explorer'
] as const satisfies readonly ConsoleDestinationId[];

export function consoleDestinations(routes: readonly ConsoleRoute[]): ConsoleDestination[] {
	const ordered = new Map(routes.map((route) => [route.id, route]));
	return consoleDestinationIds.map((id) => {
		if (id === 'operations') return operations;
		const route = ordered.get(id);
		if (route === undefined) throw new Error(`The Console band does not supply ${id}.`);
		return route;
	});
}
