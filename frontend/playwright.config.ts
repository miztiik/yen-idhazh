import { defineConfig, devices } from '@playwright/test';

/**
 * The browser suite runs against a real build, not a dev server.
 *
 * A dev server transforms modules on the fly, so it can pass while the shipped
 * bundle fails - and what a reader receives is the bundle.
 */
export default defineConfig({
	testDir: 'tests',
	fullyParallel: false,
	forbidOnly: Boolean(process.env.CI),
	retries: 0,
	workers: 1,
	reporter: process.env.CI ? 'github' : 'list',
	timeout: 180_000,
	expect: { timeout: 15_000 },
	use: {
		baseURL: 'http://127.0.0.1:4173',
		trace: 'retain-on-failure'
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
	webServer: {
		// `--host 127.0.0.1` is load-bearing on a runner. Left to itself vite binds
		// to `localhost`, which resolves to ::1 first on ubuntu-latest, so polling
		// 127.0.0.1 times out and the whole suite fails before a test runs.
		command: 'npm run preview -- --port 4173 --strictPort --host 127.0.0.1',
		url: 'http://127.0.0.1:4173/',
		reuseExistingServer: !process.env.CI,
		timeout: 120_000,
		stdout: 'pipe',
		stderr: 'pipe'
	}
});
