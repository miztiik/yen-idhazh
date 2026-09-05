import { defineConfig, devices } from '@playwright/test';
import { createHash } from 'node:crypto';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FRONTEND_GROUPS, groupedSpecs } from './scripts/test-groups';

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
 * The same set `backend/utilities/gate_lock.py` reads. Preview server reuse is
 * disabled in every environment; only the port and reporting differ in CI.
 */
const CI_OFF = new Set(['', '0', 'false', 'no', 'off']);

export function runningInCi(env: Record<string, string | undefined>): boolean {
	return !CI_OFF.has((env.CI ?? '').trim().toLowerCase());
}

/**
 * Which port this checkout's preview server listens on.
 *
 * Reusing a server previously let a suite read another checkout's build. Reuse
 * is now disabled, and deriving the port makes a rejected collision uncommon.
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
 * The shared selector decides from all changed paths. Shared and unknown inputs
 * include console coverage; main always runs every group. Test counts are
 * discovered rather than copied here.
 *
 * Skipping is opt-in through the environment and never the default: a bare
 * `npm run test:browser` runs all browser groups. The build-independent group
 * runs separately through `npm run test:logic` without starting a server.
 */
const SKIP_CONSOLE = (process.env.SKIP_CONSOLE_SUITE ?? '').trim() === 'true';
const GROUPS = groupedSpecs(fileURLToPath(new URL('./tests/', import.meta.url)));

/**
 * The one spec this config may never run, whatever is asked for on the command
 * line.
 *
 * The browser gate serves the canary day out of `frontend/build`, and
 * `whole-day.spec.ts` is a question about a real published day at day scale -
 * six hundred stories and forty-three drawings against the canary's eight and
 * two. Handed the canary it refuses to load rather than reporting a pass, so
 * leaving it in this file set would turn the gate red. `testIgnore` filters
 * before a command-line argument does, so naming the file cannot reach it
 * either; `playwright.whole-day.config.ts` is the only way in.
 */
const WHOLE_DAY = /whole-day\.spec\.ts$/;

export default defineConfig({
	testDir: 'tests',
	outputDir: 'test-results/browser',
	testIgnore: SKIP_CONSOLE ? [WHOLE_DAY, /console.*\.spec\.ts$/] : WHOLE_DAY,
	fullyParallel: false,
	forbidOnly: Boolean(process.env.CI),
	retries: 0,
	workers: 1,
	reporter: process.env.CI ? 'github' : 'list',
	timeout: 180_000,
	expect: { timeout: 15_000 },
	use: {
		baseURL: `http://127.0.0.1:${PORT}`,
		// The site ships a service worker, and every spec but one is about the
		// page rather than about the worker. Left on, the worker would answer a
		// second request for a day out of its own cache, which is exactly the
		// request a spec routes to fake a failure - so a passing arm would be
		// measuring a cache instead of the code under test. `service-worker.spec.ts`
		// turns them back on for itself.
		serviceWorkers: 'block',
		trace: 'retain-on-failure'
	},
	projects: FRONTEND_GROUPS.filter((name) => name !== 'logic').map((name) => ({
		name,
		testMatch: GROUPS[name].map((filename) => `**/${filename}`),
		use: { ...devices['Desktop Chrome'] }
	})),
	webServer: {
		// `--host 127.0.0.1` is load-bearing on a runner. Left to itself vite binds
		// to `localhost`, which resolves to ::1 first on ubuntu-latest, so polling
		// 127.0.0.1 times out and the whole suite fails before a test runs.
		command: `node scripts/verified-preview.ts --port ${PORT} --strictPort --host 127.0.0.1`,
		url: `http://127.0.0.1:${PORT}/`,
		reuseExistingServer: false,
		timeout: 120_000,
		stdout: 'pipe',
		stderr: 'pipe'
	}
});
