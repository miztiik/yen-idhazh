/** The published surface's knobs, read from `config/idhazh.json` at build time.
 *
 * Nothing in a component is hardcoded that an operator might reasonably want
 * different (Holy Law #6).
 *
 * Each reader mirrors one block of the file and is named after it. A single
 * reader returning a mixture would hide which knob came from where, and the
 * next person to move a knob would have to read this file to find out.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { REPO_ROOT } from './payload';

export interface UiConfig {
	sections: string[];
	theme_default: 'system' | 'light' | 'dark';
	visual_side: 'above' | 'leading' | 'trailing';
	source_mark: boolean;
	show_filter: boolean;
	repo_url: string;
	site_title: string;
	tagline: string;
	read_mark_days: number;
}

/** What the console needs to say whether a run went well. */
export interface RunConfig {
	success_floor_pct: number;
}

/** What the console needs to say how close a feed is to being rested. */
export interface CollectConfig {
	quarantine_after_failures: number;
}

const DEFAULTS: UiConfig = {
	sections: ['notice', 'topics', 'items'],
	theme_default: 'system',
	visual_side: 'above',
	source_mark: true,
	show_filter: true,
	repo_url: 'https://github.com/miztiik/yen-idhazh',
	site_title: 'yen-idhazh',
	tagline: 'A daily digest that checks its own work.',
	read_mark_days: 7
};

const RUN_DEFAULTS: RunConfig = { success_floor_pct: 70 };
const COLLECT_DEFAULTS: CollectConfig = { quarantine_after_failures: 5 };

interface RawConfig {
	ui?: Partial<UiConfig>;
	run?: Partial<RunConfig>;
	collect?: Partial<CollectConfig>;
}

/** The file, or nothing. A fresh clone runs on the defaults (section 1a). */
function raw(): RawConfig {
	const path = join(REPO_ROOT, 'config', 'idhazh.json');
	if (!existsSync(path)) return {};
	return JSON.parse(readFileSync(path, 'utf8')) as RawConfig;
}

export function uiConfig(): UiConfig {
	return { ...DEFAULTS, ...(raw().ui ?? {}) };
}

export function runConfig(): RunConfig {
	return { ...RUN_DEFAULTS, ...(raw().run ?? {}) };
}

export function collectConfig(): CollectConfig {
	return { ...COLLECT_DEFAULTS, ...(raw().collect ?? {}) };
}
