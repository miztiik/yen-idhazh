/** The published surface's knobs, read from `config/idhazh.json` at build time.
 *
 * Nothing in a component is hardcoded that an operator might reasonably want
 * different (Rule #6).
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
	items_per_topic: number;
	repo_url: string;
	site_title: string;
	tagline: string;
	read_mark_days: number;
	archive_page_size: number;
}

/** What the console needs to say whether a run went well. */
export interface RunConfig {
	success_floor_pct: number;
}

/** What the console needs to say how close a feed is to being rested. */
export interface CollectConfig {
	quarantine_after_failures: number;
}

export interface SummaryBand {
	min_source_words: number;
	target_words_min: number;
	target_words_max: number;
}

export interface SummarizeConfig {
	bands: SummaryBand[];
}

export interface ConsoleConfig {
	default_window_days: number;
	today_anchor: 'right' | 'centre';
	pan_days: number;
	zoom_factor: number;
	min_window_days: number;
	max_window_days: number;
	min_attempts_for_rate: number;
	chart_height: number;
	chart_width: number;
	failure_list_max: number;
}

/** What on-device archive search reads, keeps and shows. */
export interface AssistConfig {
	similarity_floor: number;
	result_limit: number;
	search_months: number;
	search_min_days: number;
}

const DEFAULTS: UiConfig = {
	sections: ['notice', 'topics', 'items'],
	theme_default: 'system',
	visual_side: 'above',
	source_mark: true,
	show_filter: true,
	items_per_topic: 3,
	repo_url: 'https://github.com/miztiik/yen-idhazh',
	site_title: 'yen-idhazh',
	tagline: 'A daily digest that checks its own work.',
	read_mark_days: 7,
	archive_page_size: 25
};

const RUN_DEFAULTS: RunConfig = { success_floor_pct: 70 };
const COLLECT_DEFAULTS: CollectConfig = { quarantine_after_failures: 5 };
const SUMMARIZE_DEFAULTS: SummarizeConfig = {
	bands: [
		{ min_source_words: 0, target_words_min: 50, target_words_max: 90 },
		{ min_source_words: 700, target_words_min: 70, target_words_max: 150 },
		{ min_source_words: 2000, target_words_min: 110, target_words_max: 200 }
	]
};
const CONSOLE_DEFAULTS: ConsoleConfig = {
	default_window_days: 30,
	today_anchor: 'right',
	pan_days: 7,
	zoom_factor: 1.5,
	min_window_days: 7,
	max_window_days: 366,
	min_attempts_for_rate: 5,
	chart_height: 180,
	chart_width: 600,
	failure_list_max: 25
};
const ASSIST_DEFAULTS: AssistConfig = {
	similarity_floor: 0.35,
	result_limit: 10,
	search_months: 1,
	search_min_days: 7
};

interface RawConfig {
	ui?: Partial<UiConfig>;
	run?: Partial<RunConfig>;
	collect?: Partial<CollectConfig>;
	summarize?: Partial<SummarizeConfig>;
	console?: Partial<ConsoleConfig>;
	assist?: Partial<AssistConfig>;
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

export function summarizeConfig(): SummarizeConfig {
	return { ...SUMMARIZE_DEFAULTS, ...(raw().summarize ?? {}) };
}

export function consoleConfig(): ConsoleConfig {
	return { ...CONSOLE_DEFAULTS, ...(raw().console ?? {}) };
}

export function assistConfig(): AssistConfig {
	return { ...ASSIST_DEFAULTS, ...(raw().assist ?? {}) };
}
