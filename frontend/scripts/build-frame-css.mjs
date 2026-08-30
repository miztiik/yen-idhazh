/** Write the frame tokens from `config/appearance.json` into a CSS file.
 *
 * The frame has to be right on the FIRST painted frame, so it cannot be
 * fetched. The obvious alternative - inject a style block from the layout -
 * was measured on 2026-08-29 and costs 397 to 700 gzipped bytes of JavaScript
 * on every route, including `/404` and `/evals/`, which render nothing. That is
 * head-management machinery shipped to seven routes so that one config value
 * can reach CSS.
 *
 * At build time it costs nothing. The output is committed so a fresh clone and
 * `npm run dev` both work without running this first, and the build regenerates
 * it, so `git diff --exit-code` after a build catches a config edit that was
 * never regenerated - the same shape as the schema drift gate.
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const REPO = join(FRONTEND, '..');
const OUT = join(FRONTEND, 'src', 'styles', 'frame.generated.css');

/** Mirrors FRAME_DEFAULTS and MOTION_DEFAULTS in src/lib/server/config.ts, and
 * the same names in tokens.css. A knob missing from the config resolves here,
 * so the generated file is always complete rather than partial. */
const DEFAULTS = {
	reading_max_px: 1280,
	console_max_px: 1600,
	measure_ch: 68,
	gutter_min_px: 16,
	gutter_max_px: 32,
	duration_fast_ms: 120,
	duration_base_ms: 200
};

function config() {
	const path = join(REPO, 'config', 'appearance.json');
	if (!existsSync(path)) return {};
	return JSON.parse(readFileSync(path, 'utf8'));
}

const raw = config();
const frame = { ...DEFAULTS, ...(raw.frame ?? {}) };
const motion = { enabled: true, ...(raw.motion ?? {}) };
const fast = motion.enabled ? (motion.duration_fast_ms ?? DEFAULTS.duration_fast_ms) : 0;
const base = motion.enabled ? (motion.duration_base_ms ?? DEFAULTS.duration_base_ms) : 0;

const css = `/* Generated from config/appearance.json by scripts/build-frame-css.mjs.
   Do not hand-edit: the build regenerates it and a diff fails the gate. */
:root {
	--frame-reading: ${frame.reading_max_px}px;
	--frame-console: ${frame.console_max_px}px;
	--measure: ${frame.measure_ch}ch;
	--gutter-min: ${frame.gutter_min_px}px;
	--gutter-max: ${frame.gutter_max_px}px;
	--dur-fast: ${fast}ms;
	--dur-base: ${base}ms;
}
`;

const previous = existsSync(OUT) ? readFileSync(OUT, 'utf8') : null;
if (previous !== css) {
	writeFileSync(OUT, css, { encoding: 'utf8' });
	console.log(`frame css: wrote ${OUT.slice(REPO.length + 1).split('\\').join('/')}`);
} else {
	console.log('frame css: unchanged');
}
