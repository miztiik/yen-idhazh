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
	theme_default: 'light' | 'dark';
	visual_side: 'above' | 'leading' | 'trailing';
	source_mark: boolean;
	show_filter: boolean;
	/** How many characters a reader types before an in-place filter narrows a
	 * list. The day page and the archive share one panel, so they share this. */
	filter_min_chars: number;
	/** How many topic pills stay on the row before the rest go in a disclosure. */
	topic_pills_max: number;
	/** How long a reader may wait for the rest of a day before the page says one
	 * sentence about it. The one knob in this block ONLY a browser reads, which
	 * is why it travels in the prerendered document and `shell_seed_items` does
	 * not. */
	payload_slow_ms: number;
	repo_url: string;
	site_title: string;
	tagline: string;
	read_mark_days: number;
	archive_page_size: number;
}

/** What the console needs to say whether a run went well. */
export interface RunConfig {
	success_floor_pct: number;
	/** The most articles one run may publish. The console divides the site's
	 * headroom by this rather than by an average of the days on disk: a quiet
	 * day is not evidence the next one will be quiet, and a runway has to be the
	 * worst case to be worth printing (Rule #10). */
	safety_ceiling_per_run: number;
	/** When the platform stops a work shard. The ceiling the machine page reads
	 * `job_seconds` against - 4,208 seconds means nothing until 150 minutes sits
	 * beside it. */
	shard_timeout_minutes: number;
}

/** What the console needs to say how much room a prompt had left.
 *
 * One knob of the pipeline's `models.inference` block, not the whole of it: the
 * machine page reads `n_tokens_max` against the window, and a counter without
 * its ceiling is not a measurement.
 */
export interface InferenceConfig {
	n_ctx: number;
}

/** What the console needs to say how much room the site has left. */
export interface RetentionConfig {
	/** Where the build starts warning, below the platform's own ceiling.
	 * `backend/idhazh/retention.py` reads the same number. */
	site_budget_mb: number;
}

/** The rate the Machine route prices a run's tokens at, and what was recorded.
 *
 * Part of the pipeline's `observability` block, not the whole of it. The price
 * is here because Rule #6 forbids a literal in a component and CLAUDE.md Rule
 * #10's one carve-out requires the figure to say where its rate came from.
 *
 * The two switches and the rate are here for the opposite reason: a page whose
 * ledger is empty has to say **why** it is empty, and "the measurement is
 * switched off" and "nothing happened" are different facts an operator acts on
 * differently. Without them every off state reads as a broken pipeline.
 *
 * **Nothing bills us.** These are a hosted provider's prices, and the number the
 * page draws from them is a counterfactual - what the run would have cost
 * somewhere else - never an amount owed.
 */
export interface ObservabilityConfig {
	/** ISO 4217, so the page names the currency rather than assuming a symbol. */
	cost_currency: string;
	cost_input_per_million: number;
	cost_output_per_million: number;
	/** Whether the faithfulness scorer runs at all. */
	evaluation_enabled: boolean;
	/** Whether a work shard scrapes the model server's own counters. */
	runtime_counters_scrape: boolean;
	/** The share of runs the scorer is drawn for. 1.0 measures every run. */
	sample_rate: number;
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
	/** The spans the window control offers, ascending. `default_window_days` is
	 * one of them - the contract refuses a config where it is not. */
	window_presets: number[];
	today_anchor: 'right' | 'centre';
	pan_days: number;
	zoom_factor: number;
	min_window_days: number;
	max_window_days: number;
	min_attempts_for_rate: number;
	chart_height: number;
	chart_width: number;
	failure_list_max: number;
	/** How many sources the failure section ranks by articles lost, before the
	 * tail sentence. */
	source_rows: number;
	/** How many failing feeds the feed section lists, before the tail sentence. */
	feed_rows: number;
	/** How many summaries the band section names before the tail sentence. */
	band_outlier_rows: number;
	/** How many sources the Summaries route ranks by the summaries its checker
	 * doubted, before the tail sentence. */
	doubt_rows: number;
	/** The span the chart arm's retirement rule is stated over. Under it the
	 * section prints the rule's own span and no median. */
	chart_arm_rule_days: number;
	/** Router minutes per published chart that retires the arm. */
	chart_arm_minutes_target: number;
	/** The share of a day's published items that must carry a chart, in whole percent. */
	chart_arm_coverage_pct: number;
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
	/** `--movement-good` and `--movement-bad`, one value per theme. Read by
	 * `scripts/build-frame-css.mjs`, not by a component: a colour that has to be
	 * right on the first painted frame cannot be injected from a layout. */
	movement_good_light: string;
	movement_bad_light: string;
	movement_good_dark: string;
	movement_bad_dark: string;
}

/** How a chart is drawn, and what it does when a pointer reaches it. */
export interface ChartConfig {
	height_px: number;
	/** The width the SERVER draws at. The client re-measures once a script runs. */
	width_px: number;
	hover_readout: boolean;
	/** The widest the readout strip under a plot may be, as a share of that plot. */
	readout_max_share: number;
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
	sections: ['notice', 'leads', 'topics', 'items'],
	theme_default: 'dark',
	visual_side: 'above',
	source_mark: true,
	show_filter: true,
	filter_min_chars: 2,
	topic_pills_max: 8,
	payload_slow_ms: 1200,
	repo_url: 'https://github.com/miztiik/yen-idhazh',
	site_title: 'yen-idhazh',
	tagline: 'A daily digest that checks its own work.',
	read_mark_days: 7,
	archive_page_size: 25
};

const RUN_DEFAULTS: RunConfig = {
	success_floor_pct: 70,
	safety_ceiling_per_run: 160,
	shard_timeout_minutes: 150
};
const INFERENCE_DEFAULTS: InferenceConfig = { n_ctx: 8192 };
const RETENTION_DEFAULTS: RetentionConfig = { site_budget_mb: 800 };
// The same three values `ObservabilityConfig` declares in the contract, so a
// checkout with no config file prices a run at the documented starting rate
// rather than at nothing (section 1a).
const OBSERVABILITY_DEFAULTS: ObservabilityConfig = {
	cost_currency: 'USD',
	cost_input_per_million: 0.2,
	cost_output_per_million: 0.6,
	evaluation_enabled: true,
	runtime_counters_scrape: true,
	sample_rate: 1
};
const COLLECT_DEFAULTS: CollectConfig = { quarantine_after_failures: 5 };
const SUMMARIZE_DEFAULTS: SummarizeConfig = {
	bands: [
		{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
		{ min_source_words: 60, target_words_min: 50, target_words_max: 90 },
		{ min_source_words: 700, target_words_min: 70, target_words_max: 150 },
		{ min_source_words: 2000, target_words_min: 110, target_words_max: 200 },
		{ min_source_words: 3000, target_words_min: 150, target_words_max: 230 }
	]
};
const CONSOLE_DEFAULTS: ConsoleConfig = {
	default_window_days: 30,
	window_presets: [7, 14, 30, 90],
	today_anchor: 'right',
	pan_days: 7,
	zoom_factor: 1.5,
	min_window_days: 7,
	max_window_days: 366,
	min_attempts_for_rate: 5,
	chart_height: 180,
	chart_width: 600,
	failure_list_max: 25,
	source_rows: 10,
	feed_rows: 10,
	band_outlier_rows: 10,
	doubt_rows: 10,
	chart_arm_rule_days: 14,
	chart_arm_minutes_target: 6,
	chart_arm_coverage_pct: 5
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
	surface_tint_alpha: 0.07,
	movement_good_light: '#2f6f5e',
	movement_bad_light: '#96453a',
	movement_good_dark: '#7fc9ae',
	movement_bad_dark: '#e3a396'
};
const CHART_DEFAULTS: ChartConfig = {
	height_px: 220,
	width_px: 760,
	hover_readout: true,
	readout_max_share: 0.33,
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
	ui?: DigestBlock;
	run?: Partial<RunConfig>;
	retention?: Partial<RetentionConfig>;
	collect?: Partial<CollectConfig>;
	summarize?: Partial<SummarizeConfig>;
	console?: Partial<ConsoleConfig>;
	assist?: Partial<AssistConfig>;
	observability?: Partial<ObservabilityConfig>;
	models?: { inference?: Partial<InferenceConfig> };
}

/** Keys the `digest` block carries that no page reads.
 *
 * Whatever `uiConfig()` returns is inlined into every prerendered document, so
 * a number no component opens would ride to every reader on every page for
 * ever. `shell_seed_items` is read by the build alone. The six leading-block
 * knobs are read by the pipeline, which decides the block at assemble and
 * publishes the answer on the day - the page draws what it is handed and
 * re-decides nothing. `items_per_topic` is retired and read by nothing at all.
 */
const BUILD_ONLY_KEYS = [
	'shell_seed_items',
	'items_per_topic',
	'leading_stories',
	'leading_per_desk',
	'leading_min',
	'lead_cluster_floor',
	'lead_shared_subject_weight',
	'lead_max_yesterday'
] as const;

/** The `digest` block: everything `UiConfig` holds, plus the knobs
 * `uiConfig()` deliberately leaves out of what it hands a browser. */
type DigestBlock = Partial<UiConfig> &
	Partial<Record<(typeof BUILD_ONLY_KEYS)[number], number>>;

interface RawAppearance {
	digest?: DigestBlock;
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
	const ui = mergeLayers(DEFAULTS, raw().ui, appearance().digest) as DigestBlock;
	// These share the block and must not ride along - see BUILD_ONLY_KEYS.
	for (const key of BUILD_ONLY_KEYS) delete ui[key];
	return ui as UiConfig;
}

/** How many of a day's stories a prerendered document carries.
 *
 * Read on its own rather than through `uiConfig()`, because it is the one knob
 * in the `digest` block no browser reads: whatever `uiConfig()` returns is
 * inlined into every prerendered document, so a build-only number put there
 * would ride to every reader on every page for ever.
 *
 * The fallback is the same number `UiConfig.shell_seed_items` defaults to, and
 * `backend/tests/test_contracts.py` fails if the two copies drift.
 */
const SHELL_SEED_ITEMS = 15;

export function shellSeedItems(): number {
	return appearance().digest?.shell_seed_items ?? raw().ui?.shell_seed_items ?? SHELL_SEED_ITEMS;
}

export function runConfig(): RunConfig {
	return { ...RUN_DEFAULTS, ...(raw().run ?? {}) };
}

export function inferenceConfig(): InferenceConfig {
	return { ...INFERENCE_DEFAULTS, ...(raw().models?.inference ?? {}) };
}

export function retentionConfig(): RetentionConfig {
	return { ...RETENTION_DEFAULTS, ...(raw().retention ?? {}) };
}

export function observabilityConfig(): ObservabilityConfig {
	return { ...OBSERVABILITY_DEFAULTS, ...(raw().observability ?? {}) };
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
