/** Which panels each console route draws, and which of them the sufficiency gates judge?
 *
 * Read out of the named `config/console/<route>.json` files when a test asks, never when a
 * module loads, so a malformed file fails the test that needed it rather than
 * every test in the file. A key the readers compute on is refused by name when
 * it is missing: this file carries no default of its own, because a second
 * copy of a default is a second answer somebody has to keep in step.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { BAND_UNREAD, type RouteId } from '../../src/lib/console/band';
import { routeConsoles } from '../../src/lib/server/config';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

export interface ConsoleRoute {
	key: RouteId;
	address: string;
	/** Every panel id the route draws, in drawn order. */
	panels: readonly string[];
	/** The panels on this route held to the sufficiency gates. */
	judged: readonly string[];
}

export interface ConsolePanels {
	routes: ConsoleRoute[];
	/** The route key each panel id is drawn on. */
	routeOf: ReadonlyMap<string, RouteId>;
	/** Every route's `judged` list, in route order. */
	judged: readonly string[];
	/** `console.plot_min_fill_share`: gate 1's floor, as a share of one. */
	fillFloor: number;
}

export function consolePanels(): ConsolePanels {
	const configs = routeConsoles();
	const parsed = JSON.parse(readFileSync(path.join(repo, 'config', 'appearance.json'), 'utf8')) as {
		console?: Record<string, unknown>;
	};
	const block = parsed.console ?? {};
	const named = (key: string): unknown => {
		if (!(key in block)) throw new Error(`config/appearance.json names no console.${key}`);
		return block[key];
	};
	const fillFloor = named('plot_min_fill_share') as number;
	const routeOf = new Map<string, RouteId>();
	const routes = BAND_UNREAD.routes.map(({ id: key, href: address }): ConsoleRoute => {
		const { panel_groups, judged } = configs[key];
		const panels = panel_groups.flatMap((group) => group.panels);
		for (const id of panels) routeOf.set(id, key);
		return { key, address, panels, judged };
	});
	const judged = routes.flatMap((route) => route.judged);
	return { routes, routeOf, judged, fillFloor };
}
