/** Emit configured frame and console-only tokens before the first paint. */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveConsoleStyle } from '../src/lib/console/console-style.ts';

/**
 * @typedef {import('../src/lib/console/console-style.ts').ConsoleStyleConfig} ConsoleStyleConfig
 * @typedef {import('../src/lib/console/console-style.ts').ConsoleStyleInput} ConsoleStyleInput
 * @typedef {import('../src/lib/console/console-style.ts').ConsoleFontFace} ConsoleFontFace
 * @typedef {import('../src/lib/console/console-style.ts').ConsoleShadow} ConsoleShadow
 * @typedef {import('../src/lib/server/config.ts').FrameConfig} FrameConfig
 * @typedef {import('../src/lib/server/config.ts').ThemeConfig} ThemeConfig
 * @typedef {import('../src/lib/server/config.ts').MotionConfig} MotionConfig
 * @typedef {Record<string, string | number>} CssTokens
 */

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const REPO = join(FRONTEND, '..');
const OUT = join(FRONTEND, 'src', 'styles', 'frame.generated.css');
const SCOPE = ":root:has([data-surface='operator'])";
const SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
const MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
const FACES = { inter: `'InterVariable', ${SANS}`, 'system-sans': SANS, 'system-mono': MONO };
const DEFAULTS = {
	reading_max_px: 1280, console_max_px: 1600, measure_ch: 68,
	gutter_min_px: 16, gutter_max_px: 32, zone_mark_rem: 1.75, zone_rail_rem: 14, zone_aside_rem: 18,
	duration_fast_ms: 120, duration_base_ms: 200, display_face_enabled: true, elevation_enabled: true,
	surface_tint_alpha: 0.07,
	movement_good_light: '#2f6f5e', movement_bad_light: '#96453a',
	movement_good_dark: '#7fc9ae', movement_bad_dark: '#e3a396'
};

/** @param {CssTokens} values */
function declarations(values) {
	return Object.entries(values).map(([key, value]) => `\t--${key}: ${value};`).join('\n');
}

/** @param {ConsoleShadow} value @param {boolean} enabled */
function shadow(value, enabled) {
	return enabled && value.alpha > 0
		? `0 ${value.y_px}px ${value.blur_px}px rgba(0, 0, 0, ${value.alpha})`
		: 'none';
}

/**
 * @param {ConsoleStyleConfig} style
 * @param {'light' | 'dark'} mode
 * @param {Pick<ThemeConfig, 'elevation_enabled' | 'surface_tint_alpha'>} theme
 */
function consoleColors(style, mode, theme) {
	const colors = style.colors[mode];
	const depth = style.elevation[mode];
	/** @type {CssTokens} */
	const values = {
		'color-bg': colors.canvas, 'color-surface-sunken': colors.inset,
		'color-surface': colors.surface, 'color-surface-raised': colors.raised,
		'color-text': colors.text, 'color-text-secondary': colors.text_secondary,
		'color-text-tertiary': colors.text_tertiary, 'color-rule': colors.rule,
		'color-rule-strong': colors.rule_strong, 'color-accent': colors.accent,
		'color-accent-strong': colors.accent_hover, 'color-on-accent': colors.on_accent,
		'color-focus': colors.focus, 'color-mark': colors.selected, 'console-selected': colors.selected,
		'chart-axis': colors.chart_axis, 'chart-grid': colors.chart_grid, 'chart-label': colors.text_secondary,
		'chart-marker': colors.text_secondary, 'chart-readout-bg': colors.inset, 'chart-readout-text': colors.text,
		'item-edge': colors.rule,
		'shadow-sm': shadow(depth.panel, theme.elevation_enabled),
		'shadow-panel': shadow(depth.panel, theme.elevation_enabled),
		'shadow-md': shadow(depth.floating, theme.elevation_enabled),
		'shadow-lg': shadow(depth.floating, theme.elevation_enabled),
		'shadow-focus': `0 0 0 var(--console-chart-line-width) ${colors.focus}`,
		'tint-accent': colors.selected, 'color-tint-accent': colors.selected,
		'tint-neutral': colors.inset,
		'code-ground': colors.inset, 'code-text': colors.text,
		'code-keyword': colors.accent_hover, 'code-comment': colors.text_tertiary,
		'code-string': colors.categorical[2], 'code-number': colors.categorical[3],
		'type-text': 'var(--code-string)', 'type-number': 'var(--code-number)',
		'type-time': colors.categorical[0], 'type-truth': colors.categorical[1],
		'gradient-panel': 'none', 'gradient-wash': 'none',
		'shimmer-band': `color-mix(in srgb, ${colors.text} ${theme.surface_tint_alpha * 100}%, transparent)`
	};
	colors.categorical.forEach((value, index) => { values[`chart-${index + 1}`] = value; });
	for (let index = 1; index <= 4; index += 1) values[`series-${index}`] = `var(--chart-${index})`;
	for (const [name, band] of [['good', 'high'], ['warn', 'medium'], ['bad', 'low']]) {
		values[`tint-${name}`] = `color-mix(in srgb, var(--band-${band}) ${theme.surface_tint_alpha * 100}%, ${colors.surface})`;
	}
	values['tint-info'] = `color-mix(in srgb, var(--chart-1) ${theme.surface_tint_alpha * 100}%, ${colors.surface})`;
	return declarations(values);
}

/**
 * Callers supply repository-authored, native-validated appearance values.
 * @param {{frame?: Partial<FrameConfig>, theme?: Partial<ThemeConfig>, motion?: Partial<MotionConfig>, console_style?: ConsoleStyleInput}} raw
 */
export function renderFrameCss(raw = {}) {
	const frame = { ...DEFAULTS, ...raw.frame };
	const motion = { enabled: true, ...raw.motion };
	const theme = { ...DEFAULTS, ...raw.theme };
	const style = resolveConsoleStyle(raw.console_style);
	const fast = motion.enabled ? (motion.duration_fast_ms ?? DEFAULTS.duration_fast_ms) : 0;
	const base = motion.enabled ? (motion.duration_base_ms ?? DEFAULTS.duration_base_ms) : 0;
	/** @param {ConsoleFontFace} name */
	const face = (name) => name === 'inter' && !theme.display_face_enabled ? SANS : FACES[name];
	const { ui_face, heading_face, data_face, ...typeRoles } = style.typography;
	/** @type {CssTokens} */
	const tokens = {
		'font-reading': face(ui_face),
		'font-display': face(heading_face),
		'font-data': face(data_face),
		'console-code-face': MONO
	};
	for (const [name, type] of Object.entries(typeRoles)) {
		const key = `console-${name.replaceAll('_', '-')}`;
		tokens[`${key}-size`] = `${type.size_rem}rem`;
		tokens[`${key}-leading`] = `${type.leading_rem}rem`;
		tokens[`${key}-weight`] = type.weight;
		tokens[`${key}-tracking`] = `${type.tracking_em}em`;
	}
	for (const [name, value] of Object.entries(style.layout)) {
		tokens[`console-${name.replace(/_rem$/, '').replaceAll('_', '-')}`] =
			name.endsWith('_rem') ? `${value}rem` : value;
	}
	for (const [name, value] of Object.entries(style.radii)) tokens[`console-${name.replace('_rem', '')}-radius`] = `${value}rem`;
	for (const [name, value] of Object.entries(style.chart)) {
		tokens[`console-chart-${name.replace(/_px$/, '').replaceAll('_', '-')}`] =
			value === null ? 'none' : Array.isArray(value) ? value.join(' ')
				: name.endsWith('_px') ? `${value}px` : value;
	}
	for (const [size, role] of [['xs', 'small'], ['sm', 'body'], ['base', 'body'], ['lg', 'panel-title'], ['xl', 'page-title'], ['2xl', 'value'], ['3xl', 'value']]) {
		tokens[`text-${size}`] = `var(--console-${role}-size)`;
		tokens[`leading-${size}`] = `var(--console-${role}-leading)`;
	}
	Object.assign(tokens, {
		'radius-sm': 'var(--console-control-radius)', 'radius-md': 'var(--console-control-radius)',
		'radius-lg': 'var(--console-panel-radius)', 'radius-xl': 'var(--console-panel-radius)',
		'workbench-control': 'var(--console-control-min-height)',
		'workbench-field-text': 'var(--console-body-size)', 'workbench-field-leading': 'var(--console-body-leading)',
		'workbench-row': 'calc(var(--console-small-leading) + 2 * var(--console-control-padding-block))',
		'tracking-label': 'var(--console-small-tracking)'
	});

	return `/* Generated from config/appearance.json by scripts/build-frame-css.mjs. */
:root {
${declarations({
		'frame-reading': `${frame.reading_max_px}px`, 'frame-console': `${frame.console_max_px}px`,
		measure: `${frame.measure_ch}ch`, 'gutter-min': `${frame.gutter_min_px}px`, 'gutter-max': `${frame.gutter_max_px}px`,
		'zone-mark': `${frame.zone_mark_rem}rem`, 'zone-rail': `${frame.zone_rail_rem}rem`, 'zone-aside': `${frame.zone_aside_rem}rem`,
		'dur-fast': `${fast}ms`, 'dur-base': `${base}ms`,
		'font-display': theme.display_face_enabled ? FACES.inter : 'var(--font-reading)'
	})}
}

:root,
[data-theme='dark'] {
${declarations({ 'movement-good': theme.movement_good_dark, 'movement-bad': theme.movement_bad_dark })}
}

[data-theme='light'] {
${declarations({ 'movement-good': theme.movement_good_light, 'movement-bad': theme.movement_bad_light })}
}

/* The selector includes the outer canvas and header, never a reading route. */
${SCOPE} {
${declarations(tokens)}
${consoleColors(style, 'dark', theme)}
}

${SCOPE}[data-theme='light'] {
${consoleColors(style, 'light', theme)}
}
`;
}

function build() {
	const path = join(REPO, 'config', 'appearance.json');
	const raw = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : {};
	const localPython = [join(REPO, '.venv', 'Scripts', 'python.exe'), join(REPO, '.venv', 'bin', 'python')].find((path) => existsSync(path));
	const python = process.env.IDHAZH_PYTHON ?? localPython ?? 'python';
	const validated = spawnSync(python, ['-c',
		'from idhazh.contracts.appearance_config import AppearanceConfig; import sys; print(AppearanceConfig.model_validate_json(sys.stdin.read()).model_dump_json())'
	], {
		cwd: REPO, encoding: 'utf8', input: JSON.stringify(raw),
		env: { ...process.env, PYTHONPATH: join(REPO, 'backend') }
	});
	if (validated.error) throw validated.error;
	if (validated.status !== 0) throw new Error(`config/appearance.json failed native validation:\n${validated.stderr}`);
	const css = renderFrameCss(JSON.parse(validated.stdout));
	const previous = existsSync(OUT) ? readFileSync(OUT, 'utf8') : null;
	if (previous !== css) writeFileSync(OUT, css, { encoding: 'utf8' });
	console.log(previous === css ? 'frame css: unchanged' : 'frame css: wrote src/styles/frame.generated.css');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) build();
