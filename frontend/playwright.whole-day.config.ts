import { defineConfig } from '@playwright/test';
import base from './playwright.config';

/**
 * The one check that has to see a real published day.
 *
 * `frontend/build` is a single directory that `npm run build` and
 * `npm run build:canary` both write, and the browser gate serves the canary -
 * eight stories on one desk, against a seed of fifteen. `whole-day.spec.ts`
 * asks what a page does at six hundred stories and forty-three drawings, so
 * handed the canary it would assert almost nothing and report a pass. That is
 * the failure this file exists to make impossible.
 *
 * It is the only config that selects that spec: `playwright.config.ts` ignores
 * the file, so `npm run test:browser` cannot reach it and neither can naming it
 * on the command line. Everything else - the derived preview port, the blocked
 * service workers, one worker, no retries - is inherited, because a second
 * opinion about how the site is served is exactly what a second config must not
 * introduce.
 *
 * The timeout is its own, and it is sized from the worst case rather than the
 * average (Rule #10). Drawing a six-hundred-story day and walking it down one
 * screen at a time measured 68 seconds an arm on an Intel Core i7-1265U on
 * 2026-09-05, spread 9 seconds over four arms on a machine shared with other
 * agents. Ten minutes is that worst case with room for a box under load, and it
 * is deliberately generous: `layout-overflow.spec.ts` has crashed a browser
 * inside the full suite, and a crash reported as a timeout is a diagnosis
 * nobody can make.
 */
export default defineConfig({
	...base,
	testIgnore: undefined,
	testMatch: /whole-day\.spec\.ts$/,
	timeout: 600_000
});
