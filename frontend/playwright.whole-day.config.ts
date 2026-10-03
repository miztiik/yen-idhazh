import { defineConfig, devices } from '@playwright/test';
import base from './playwright.config';

const webServer = Array.isArray(base.webServer) ? base.webServer[0] : base.webServer;
if (!webServer) throw new Error('Whole-day checks require the verified preview server.');

/**
 * Whole-day reader checks use one fixed canary day, not committed history.
 *
 * This config selects the canary build. Its named day must extend beyond the
 * configured seed and carry a drawing after it, so the browser exercises the
 * fetch and lazy-render paths. The shared config supplies the preview server
 * and browser settings.
 */
export default defineConfig({
	...base,
	testIgnore: undefined,
	testMatch: /whole-day\.spec\.ts$/,
	outputDir: 'test-results/whole-day',
	projects: [{ name: 'whole-day', use: { ...devices['Desktop Chrome'] } }],
	webServer: { ...webServer, env: { ...webServer.env, IDHAZH_TEST_BUILD: 'canary' } }
});
