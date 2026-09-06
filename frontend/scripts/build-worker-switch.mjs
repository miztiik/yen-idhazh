/** Write the two numbers the offline reader is built and retired by.
 *
 * The site ships a service worker, and a worker is the only code this project
 * ships that outlives the tab. So the switch that turns it off is a committed
 * file rather than a code edit: `config/appearance.json` names the version this
 * build's worker carries and the version through which workers must retire, and
 * this script puts each of them where it is read.
 *
 * The bounds on what the worker keeps ride the same way, for the same reason: a
 * worker cannot read `config/` at run time.
 *
 * Two outputs, because they are read in two different places:
 *
 * - `src/lib/offline.generated.ts` is baked into the worker at build time. A
 *   worker cannot read `config/` at run time and must not be asked to.
 * - `static/service-worker-kill.json` is served at the site root and fetched by
 *   the worker itself. That is what lets a retirement reach a worker already
 *   installed on a reader's device: one file changes, and every worker at or
 *   below the version it names deletes its caches and unregisters.
 *
 * Both are committed, for the same reason `frame.generated.css` is: a fresh
 * clone and `npm run dev` work without running this first, and the build
 * regenerates them, so `git diff --exit-code` after a build catches a config
 * edit that was never regenerated.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const REPO = join(FRONTEND, '..');
const CONSTANTS = join(FRONTEND, 'src', 'lib', 'offline.generated.ts');
const SWITCH = join(FRONTEND, 'static', 'service-worker-kill.json');

/** Mirrors the defaults on `UiConfig` in
 * backend/idhazh/contracts/app_config.py. A knob missing from the config
 * resolves here, so a fresh clone builds a worker rather than a broken one. */
const DEFAULTS = {
	offline_version: 1,
	offline_retired_through: 0,
	offline_days_kept: 14,
	offline_bytes_kept: 20_000_000
};

function digestBlock() {
	const appearance = join(REPO, 'config', 'appearance.json');
	const legacy = join(REPO, 'config', 'idhazh.json');
	const read = (path, key) =>
		existsSync(path) ? (JSON.parse(readFileSync(path, 'utf8'))[key] ?? {}) : {};
	// The same three layers `uiConfig()` merges, most specific last.
	return { ...DEFAULTS, ...read(legacy, 'ui'), ...read(appearance, 'digest') };
}

const knobs = digestBlock();
const version = Number(knobs.offline_version ?? DEFAULTS.offline_version);
const retiredThrough = Number(knobs.offline_retired_through ?? DEFAULTS.offline_retired_through);
const daysKept = Number(knobs.offline_days_kept ?? DEFAULTS.offline_days_kept);
const bytesKept = Number(knobs.offline_bytes_kept ?? DEFAULTS.offline_bytes_kept);

const constants = `/* Generated from config/appearance.json by scripts/build-worker-switch.mjs.
   Do not hand-edit: the build regenerates it and a diff fails the gate. */

/** The version this build's offline reader carries. */
export const OFFLINE_VERSION = ${version};

/** How many opened days the offline reader keeps on the reader's device. */
export const OFFLINE_DAYS_KEPT = ${daysKept};

/** The most bytes of kept days the offline reader leaves on the reader's
 * device. The second bound, because a day count cannot bound bytes. */
export const OFFLINE_BYTES_KEPT = ${bytesKept};
`;

// One key and one number. The worker reads this file with the HTTP cache turned
// off, so keeping it small is keeping a per-navigation request small.
const kill = `${JSON.stringify({ retired_through: retiredThrough }, null, 2)}\n`;

let wrote = 0;
for (const [path, text] of [
	[CONSTANTS, constants],
	[SWITCH, kill]
]) {
	const previous = existsSync(path) ? readFileSync(path, 'utf8') : null;
	if (previous === text) continue;
	writeFileSync(path, text, { encoding: 'utf8' });
	wrote += 1;
}

console.log(
	wrote === 0
		? 'worker switch: unchanged'
		: `worker switch: wrote ${wrote} file(s), version ${version}, retired through ${retiredThrough}`
);
