/** Which panels each console route draws, and which of them the sufficiency gates judge?
 *
 * Read out of `config/appearance.json` at the moment a test asks, never when a
 * module loads, so a malformed file fails the test that needed it rather than
 * every test in the file. A key the readers compute on is refused by name when
 * it is missing: this file carries no default of its own, because a second
 * copy of a default is a second answer somebody has to keep in step.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

/** The address each `console.panel_groups` route is drawn at.
 *
 * The route key is the config's and the address is the route tree's, so the
 * pair lives here, where the two meet. A key with no address is a route no
 * capture can open, and `consolePanels` refuses it by name.
 */
export const CONSOLE_ROUTE_PATHS: Readonly<Record<string, string>> = {
	pipelines: '/console/',
	machine: '/console/machine/',
	'data-explorer': '/console/data-explorer/'
};

export interface ConsoleRoute {
	key: string;
	address: string;
	/** Every panel id the route draws, in drawn order. */
	panels: string[];
}

export interface ConsolePanels {
	routes: ConsoleRoute[];
	/** The route key each panel id is drawn on. */
	routeOf: ReadonlyMap<string, string>;
	/** `console.judged_panel_ids`: the panels the sufficiency gates hold to account. */
	judged: readonly string[];
	/** `console.plot_min_fill_share`: gate 1's floor, as a share of one. */
	fillFloor: number;
}

interface PanelGroup {
	panels: string[];
}

export function consolePanels(): ConsolePanels {
	const parsed = JSON.parse(readFileSync(path.join(repo, 'config', 'appearance.json'), 'utf8')) as {
		console?: Record<string, unknown>;
	};
	const block = parsed.console ?? {};
	const named = (key: string): unknown => {
		if (!(key in block)) throw new Error(`config/appearance.json names no console.${key}`);
		return block[key];
	};
	const groups = named('panel_groups') as Record<string, PanelGroup[]>;
	const judged = named('judged_panel_ids') as string[];
	const fillFloor = named('plot_min_fill_share') as number;

	const routeOf = new Map<string, string>();
	const routes = Object.entries(groups).map(([key, list]): ConsoleRoute => {
		const address = CONSOLE_ROUTE_PATHS[key];
		if (address === undefined) {
			throw new Error(
				`console.panel_groups names the route ${key}, and no capture knows its address - add it to CONSOLE_ROUTE_PATHS`
			);
		}
		const panels = list.flatMap((group) => group.panels);
		for (const id of panels) {
			const other = routeOf.get(id);
			if (other !== undefined) {
				throw new Error(`console.panel_groups names ${id} on ${other} and on ${key}, so their images would overwrite each other`);
			}
			routeOf.set(id, key);
		}
		return { key, address, panels };
	});
	for (const id of judged) {
		if (!routeOf.has(id)) {
			throw new Error(`console.judged_panel_ids names ${id}, and no route in console.panel_groups draws it`);
		}
	}
	return { routes, routeOf, judged, fillFloor };
}
