/** The published surface's knobs, read at build time.
 *
 * Nothing in a component is hardcoded that an operator might reasonably want
 * different (Rule #6).
 *
 * Two files, and the split is along who edits them and how often.
 * `config/appearance.json` owns everything the surface is DRAWN from - the
 * frame, the tokens, the charts, the icons, the digest and console knobs.
 * `config/idhazh.json` owns the pipeline, and this module still reads the two
 * blocks the console needs from it to say whether a run went well.
 *
 * The appearance blocks moved on 2026-08-29 and the move is backwards
 * compatible: a reader prefers `appearance.json` and falls back to the legacy
 * `ui`, `console` and `assist` blocks in `idhazh.json`, so a checkout that has
 * not been migrated still resolves (CLAUDE.md section 11).
 *
 * Each reader mirrors one block and is named after it. A single reader
 * returning a mixture would hide which knob came from where, and the next
 * person to move a knob would have to read this file to find out.
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

/** How wide the page is, and where the reading measure lives.
 *
 * The measure is a property of a text element and never of the shell. Putting
 * it on the shell is the defect behind the 2026-08-28 measurement: one
 * `max-w-2xl` on the root layout gave the whole application a paragraph's
 * width, and the page used 40.6 percent of a 1536px screen.
 */
export interface FrameConfig {
	reading_max_px: number;
	console_max_px: number;
	measure_ch: number;
	gutter_min_px: number;
	gutter_max_px: number;
	/** Exactly three, ascending. A breakpoint must earn a structural change. */
	breakpoints_px: [number, number, number];
}

/** What the surface is allowed to draw with. */
export interface ThemeConfig {
	gradient_enabled: boolean;
	elevation_enabled: boolean;
	display_face_enabled: boolean;
	surface_tint_alpha: number;
}

/** How a chart is drawn, and what it does when a pointer reaches it. */
export interface ChartConfig {
	height_px: number;
	/** The width the SERVER draws at. The client re-measures once a script runs. */
	width_px: number;
	hover_readout: boolean;
	palette: 'categorical' | 'sequential';
	tick_density: number;
	sparkline_height_px: number;
	donut_thickness_px: number;
}

export interface IconsConfig {
	size_px: number;
	tint_mode: 'semantic' | 'mono';
	topic_icons_enabled: boolean;
}

export interface MotionConfig {
	enabled: boolean;
	duration_fast_ms: number;
	duration_base_ms: number;
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
const FRAME_DEFAULTS: FrameConfig = {
	reading_max_px: 1280,
	console_max_px: 1600,
	measure_ch: 68,
	gutter_min_px: 16,
	gutter_max_px: 32,
	breakpoints_px: [640, 1024, 1400]
};
const THEME_DEFAULTS: ThemeConfig = {
	gradient_enabled: true,
	elevation_enabled: true,
	display_face_enabled: true,
	surface_tint_alpha: 0.07
};
const CHART_DEFAULTS: ChartConfig = {
	height_px: 220,
	width_px: 760,
	hover_readout: true,
	palette: 'categorical',
	tick_density: 6,
	sparkline_height_px: 36,
	donut_thickness_px: 10
};
const ICONS_DEFAULTS: IconsConfig = {
	size_px: 16,
	tint_mode: 'semantic',
	topic_icons_enabled: true
};
const MOTION_DEFAULTS: MotionConfig = {
	enabled: true,
	duration_fast_ms: 120,
	duration_base_ms: 200
};

interface RawConfig {
	ui?: Partial<UiConfig>;
	run?: Partial<RunConfig>;
	collect?: Partial<CollectConfig>;
	summarize?: Partial<SummarizeConfig>;
	console?: Partial<ConsoleConfig>;
	assist?: Partial<AssistConfig>;
}

interface RawAppearance {
	digest?: Partial<UiConfig>;
	console?: Partial<ConsoleConfig>;
	assist?: Partial<AssistConfig>;
	frame?: Partial<FrameConfig>;
	theme?: Partial<ThemeConfig>;
	chart?: Partial<ChartConfig>;
	icons?: Partial<IconsConfig>;
	motion?: Partial<MotionConfig>;
}

function readJson<T>(...segments: string[]): T | null {
	const path = join(REPO_ROOT, ...segments);
	if (!existsSync(path)) return null;
	return JSON.parse(readFileSync(path, 'utf8')) as T;
}

/** The pipeline file, or nothing. A fresh clone runs on the defaults (section 1a). */
function raw(): RawConfig {
	return readJson<RawConfig>('config', 'idhazh.json') ?? {};
}

/** The appearance file, or nothing.
 *
 * Absent on a checkout taken before 2026-08-29, which is exactly the case the
 * fallback below exists for.
 */
function appearance(): RawAppearance {
	return readJson<RawAppearance>('config', 'appearance.json') ?? {};
}

/** Three layers, most specific last: defaults, the legacy block, the new file.
 *
 * The legacy block sits in the middle rather than being ignored, so a knob a
 * migrated file does not mention still resolves to whatever `idhazh.json` said
 * rather than snapping back to a default nobody chose. That is the whole of the
 * read-side migration (CLAUDE.md section 11), and it is exported so a test can
 * drive it in both directions without touching the disk.
 */
export function mergeLayers<T extends object>(
	defaults: T,
	legacy: Partial<T> | undefined,
	current: Partial<T> | undefined
): T {
	return { ...defaults, ...(legacy ?? {}), ...(current ?? {}) };
}

export function uiConfig(): UiConfig {
	return mergeLayers(DEFAULTS, raw().ui, appearance().digest);
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
	return mergeLayers(CONSOLE_DEFAULTS, raw().console, appearance().console);
}

export function assistConfig(): AssistConfig {
	return mergeLayers(ASSIST_DEFAULTS, raw().assist, appearance().assist);
}

export function frameConfig(): FrameConfig {
	return { ...FRAME_DEFAULTS, ...(appearance().frame ?? {}) };
}

export function themeConfig(): ThemeConfig {
	return { ...THEME_DEFAULTS, ...(appearance().theme ?? {}) };
}

export function chartConfig(): ChartConfig {
	return { ...CHART_DEFAULTS, ...(appearance().chart ?? {}) };
}

export function iconsConfig(): IconsConfig {
	return { ...ICONS_DEFAULTS, ...(appearance().icons ?? {}) };
}

export function motionConfig(): MotionConfig {
	return { ...MOTION_DEFAULTS, ...(appearance().motion ?? {}) };
}
