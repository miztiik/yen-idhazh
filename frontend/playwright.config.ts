import { defineConfig, devices } from '@playwright/test';
import { createHash } from 'node:crypto';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * The browser suite runs against a real build, not a dev server.
 *
 * A dev server transforms modules on the fly, so it can pass while the shipped
 * bundle fails - and what a reader receives is the bundle.
 */

/** The port a runner uses, and the number this file has always defaulted to.
 *
 * A GitHub runner is one job alone on its own machine (Rule #2), so it has
 * nothing to collide with and nothing about a CI run moves.
 */
export const CI_PREVIEW_PORT = 4173;

/** The derived range: `DERIVED_PORT_SPAN` ports starting at `DERIVED_PORT_FLOOR`.
 *
 * Two lines bound it. The floor clears the band a person reaches for when 4173
 * is taken: 4173, 4181, 4187, 4193, 4196, 4209, 4213, 4241, 4271 and 4301 have
 * each been held by a sibling checkout on this machine, and every one of them
 * is under 4400. The ceiling stays under 32768, where Linux starts handing out
 * ephemeral ports, and so also under 49152, where Windows does - so the
 * operating system never gives this number to something else mid-suite.
 *
 * Ten thousand ports do not make a collision impossible and no finite range
 * would. Two of sixteen checkouts land on one port about 1.2 percent of the
 * time. That case costs those two exactly what today costs them and no more,
 * and `PREVIEW_PORT` clears it in one command - so the range turns a certainty
 * into a rarity rather than pretending to remove it.
 */
export const DERIVED_PORT_FLOOR = 20000;
export const DERIVED_PORT_SPAN = 10000;

/** What an unset or switched-off `CI` looks like. GitHub Actions sets `CI=true`.
 *
 * The same set `backend/utilities/gate_lock.py` reads, so the lock and the
 * suite cannot disagree about whether this machine is a runner. `forbidOnly`,
 * `reporter` and `reuseExistingServer` below keep the plain truthiness test
 * they already had - every value a runner actually sets reads the same either
 * way, and this change is about the port alone.
 */
const CI_OFF = new Set(['', '0', 'false', 'no', 'off']);

export function runningInCi(env: Record<string, string | undefined>): boolean {
	return !CI_OFF.has((env.CI ?? '').trim().toLowerCase());
}

/**
 * Which port this checkout's preview server listens on.
 *
 * Two checkouts on one port do not queue. `reuseExistingServer` lets the second
 * adopt the first one's server, so a whole suite passes against another
 * worktree's build and says nothing about it - and a `--strictPort` preview
 * that failed to bind still answers 200, from the sibling that already holds
 * the port. Deriving the port from the checkout removes the collision instead
 * of asking a person to remember one number per worktree.
 *
 * `worktree` is a directory that differs per checkout. Sibling paths differ by
 * a single character, which is why this hashes rather than sums: a character
 * sum would map `yi-g01`, `yi-g02` and `yi-g03` to three neighbouring ports and
 * rebuild the very clustering the range exists to escape.
 */
export function previewPort(worktree: string, env: Record<string, string | undefined>): number {
	const asked = (env.PREVIEW_PORT ?? '').trim();
	if (asked !== '') {
		const port = Number(asked);
		if (!Number.isInteger(port) || port < 1 || port > 65535) {
			throw new Error(`PREVIEW_PORT must be a port from 1 to 65535, not ${JSON.stringify(asked)}`);
		}
		return port;
	}
	if (runningInCi(env)) return CI_PREVIEW_PORT;
	const digest = createHash('sha256').update(worktree).digest();
	return DERIVED_PORT_FLOOR + (digest.readUInt32BE(0) % DERIVED_PORT_SPAN);
}

// This file's own directory, never `process.cwd()`: one checkout has to answer
// one port whether the suite starts from `frontend/` or from the repository
// root.
const PORT = previewPort(dirname(fileURLToPath(import.meta.url)), process.env);

/**
 * The operator console's own specs, skipped when nothing it renders has moved.
 *
 * 233 of the suite's 411 tests are `console-*.spec.ts`. None of them is about
 * the digest: the console is the operator's dashboard, and a reader never opens
 * it. `.github/scripts/browser-suite-needed.sh` decides, from the paths a pull
 * request touched, and a push to `main` always runs everything - so a path
 * nobody thought of costs a red merge commit rather than a broken page.
 *
 * Skipping is opt-in through the environment and never the default: a bare
 * `npm run test:browser` on a developer box runs the whole suite, and so does
 * every scheduled and manual run.
 */
const SKIP_CONSOLE = (process.env.SKIP_CONSOLE_SUITE ?? '').trim() === 'true';

export default defineConfig({
	testDir: 'tests',
	testIgnore: SKIP_CONSOLE ? /console.*\.spec\.ts$/ : undefined,
	fullyParallel: false,
	forbidOnly: Boolean(process.env.CI),
	retries: 0,
	workers: 1,
	reporter: process.env.CI ? 'github' : 'list',
	timeout: 180_000,
	expect: { timeout: 15_000 },
	use: {
		baseURL: `http://127.0.0.1:${PORT}`,
		trace: 'retain-on-failure'
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
	webServer: {
		// `--host 127.0.0.1` is load-bearing on a runner. Left to itself vite binds
		// to `localhost`, which resolves to ::1 first on ubuntu-latest, so polling
		// 127.0.0.1 times out and the whole suite fails before a test runs.
		command: `npm run preview -- --port ${PORT} --strictPort --host 127.0.0.1`,
		url: `http://127.0.0.1:${PORT}/`,
		reuseExistingServer: !process.env.CI,
		timeout: 120_000,
		stdout: 'pipe',
		stderr: 'pipe'
	}
});
