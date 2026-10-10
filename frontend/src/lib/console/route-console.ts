import { BAND_UNREAD, type RouteId } from './band';
import type { ConsoleConfig } from '../server/config';

export interface ConsolePanelGroup {
	readonly id: string;
	readonly title: string;
	readonly panels: readonly string[];
}

export interface RouteConsole {
	readonly panel_groups: readonly ConsolePanelGroup[];
	readonly judged: readonly string[];
	readonly knobs: Readonly<Record<string, number>>;
}

export type RouteConsoles = Readonly<Record<RouteId, RouteConsole>>;

export interface ConsoleDefine {
	readonly shared: ConsoleConfig;
	readonly routes: RouteConsoles;
}

function object(value: unknown, path: string): Record<string, unknown> {
	if (value === null || typeof value !== 'object' || Array.isArray(value)) {
		throw new Error(`${path} must be an object`);
	}
	return value as Record<string, unknown>;
}

function keys(value: Record<string, unknown>, expected: readonly string[], path: string): void {
	for (const key of expected) {
		if (!Object.hasOwn(value, key)) throw new Error(`${path} names no ${key}`);
	}
	for (const key of Object.keys(value)) {
		if (!expected.includes(key)) throw new Error(`${path} names unknown ${key}`);
	}
}

function strings(value: unknown, path: string): string[] {
	if (!Array.isArray(value) || value.some((entry) => typeof entry !== 'string' || !entry.trim())) {
		throw new Error(`${path} must be an array of nonempty panel ids`);
	}
	return [...value];
}

/** Parse authored route files without reading disk or the build-time define. */
export function routeConsolesFrom(files: Readonly<Record<string, unknown>>): RouteConsoles {
	const routes = BAND_UNREAD.routes.map(({ id }) => id);
	keys(object(files, 'config/console'), routes, 'config/console');
	const result = {} as Record<RouteId, RouteConsole>;
	const allPanels = new Set<string>();
	for (const route of routes) {
		const path = `config/console/${route}.json`;
		const value = object(files[route], path);
		keys(value, ['panel_groups', 'judged', 'knobs'], path);
		if (!Array.isArray(value.panel_groups)) throw new Error(`${path} panel_groups must be an array`);
		const groupIds = new Set<string>();
		const panels = new Set<string>();
		const groups: ConsolePanelGroup[] = value.panel_groups.map((entry, index) => {
			const at = `${path} panel_groups[${index}]`;
			const group = object(entry, at);
			keys(group, ['id', 'title', 'panels'], at);
			if (typeof group.id !== 'string' || !/^[a-z][a-z0-9-]*$/.test(group.id)) {
				throw new Error(`${at}.id must be a lower-case group id`);
			}
			if (groupIds.has(group.id)) throw new Error(`${at}.id repeats ${group.id}`);
			groupIds.add(group.id);
			if (typeof group.title !== 'string') throw new Error(`${at}.title must be a string`);
			const drawn = strings(group.panels, `${at}.panels`);
			if (!drawn.length) throw new Error(`${at}.panels must name at least one panel`);
			for (const panel of drawn) {
				if (panels.has(panel) || allPanels.has(panel)) {
					throw new Error(`${at}.panels repeats ${panel}`);
				}
				panels.add(panel);
				allPanels.add(panel);
			}
			return { id: group.id, title: group.title, panels: drawn };
		});
		if (groups.some((group) => group.title === '') && groups.some((group) => group.title !== '')) {
			throw new Error(`${path} panel_groups titles only some groups`);
		}
		const judged = strings(value.judged, `${path} judged`);
		const seenJudged = new Set<string>();
		for (const panel of judged) {
			if (!panels.has(panel)) throw new Error(`${path} judged names undrawn ${panel}`);
			if (seenJudged.has(panel)) throw new Error(`${path} judged repeats ${panel}`);
			seenJudged.add(panel);
		}
		const knobs = object(value.knobs, `${path} knobs`);
		const finite: Record<string, number> = {};
		for (const [key, knob] of Object.entries(knobs)) {
			if (typeof knob !== 'number' || !Number.isFinite(knob)) {
				throw new Error(`${path} knobs.${key} must be a finite number`);
			}
			Object.defineProperty(finite, key, { value: knob, enumerable: true });
		}
		result[route] = { panel_groups: groups, judged, knobs: finite };
	}
	return result;
}

export function routeConsole(route: RouteId): RouteConsole {
	return __CONSOLE__.routes[route];
}

export function consoleKnobs(): ConsoleConfig {
	return __CONSOLE__.shared;
}

export function routeKnobs<K extends string>(route: RouteId, wanted: readonly K[]): Readonly<Record<K, number>> {
	const knobs = routeConsole(route).knobs;
	const result = {} as Record<K, number>;
	for (const key of wanted) {
		if (!Object.hasOwn(knobs, key)) throw new Error(`config/console/${route}.json names no knobs.${key}`);
		Object.defineProperty(result, key, { value: knobs[key], enumerable: true });
	}
	return result;
}
