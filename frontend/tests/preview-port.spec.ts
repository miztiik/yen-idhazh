/** The preview port one checkout uses, driven as a pure function.
 *
 * Two checkouts that share a port do not queue. `reuseExistingServer` lets the
 * second adopt the first one's server, so a whole suite can pass against
 * another worktree's build and report nothing wrong - and a `--strictPort`
 * preview that failed to bind still answers 200, from the sibling that already
 * holds the port. Both have happened on this machine.
 *
 * Three properties make the derived port safe, and all three are asserted here
 * because each one fails silently on its own: two checkouts differ, one
 * checkout does not move between calls, and a runner keeps the number it has
 * always used.
 *
 * Pure functions only - no browser, no server, no SvelteKit alias. A spec that
 * imports anything resolving `$app/...` fails the WHOLE suite at load with
 * `Cannot find package '$app'`, not one test.
 */

import { expect, test } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import config, {
	CI_PREVIEW_PORT,
	DERIVED_PORT_FLOOR,
	DERIVED_PORT_SPAN,
	previewPort,
	runningInCi
} from '../playwright.config';

/** Real shapes. Four of the five are siblings differing in one character,
 * which is the case a weak hash maps to neighbouring numbers. The last is the
 * path a GitHub runner checks out into. */
const WORKTREES = [
	'C:\\Users\\dev\\gitrepos\\yen-idhazh\\frontend',
	'C:\\Users\\dev\\gitrepos\\yi-g01\\frontend',
	'C:\\Users\\dev\\gitrepos\\yi-g02\\frontend',
	'C:\\Users\\dev\\gitrepos\\yi-g03\\frontend',
	'/home/runner/work/yen-idhazh/yen-idhazh/frontend'
];

/** No `CI`, no `PREVIEW_PORT`. Every case states its own environment rather
 * than inheriting the machine's, or it measures whichever state this box
 * happens to be in instead of the behaviour. */
const NOTHING_SET: Record<string, string | undefined> = {};

/** The values `backend/utilities/gate_lock.py` reads as "not a runner". */
const CI_MEANS_OFF = ['', '0', 'false', 'no', 'off', ' FALSE ', 'Off'];

test.describe('the preview port', () => {
	test('two checkouts never derive one port', () => {
		const ports = WORKTREES.map((worktree) => previewPort(worktree, NOTHING_SET));
		expect(new Set(ports).size, `derived ${ports.join(', ')}`).toBe(WORKTREES.length);
	});

	test('one checkout derives the same port on every call', () => {
		for (const worktree of WORKTREES) {
			const first = previewPort(worktree, NOTHING_SET);
			expect(previewPort(worktree, NOTHING_SET), worktree).toBe(first);
			expect(previewPort(worktree, NOTHING_SET), worktree).toBe(first);
		}
	});

	test('a runner keeps 4173, whichever checkout it is', () => {
		expect(CI_PREVIEW_PORT).toBe(4173);
		for (const worktree of WORKTREES) {
			expect(previewPort(worktree, { CI: 'true' }), worktree).toBe(4173);
			// And the derived answer is a different number, so the line above is
			// a claim about the carve-out rather than a restatement of the default.
			expect(previewPort(worktree, NOTHING_SET), worktree).not.toBe(4173);
		}
	});

	test('a CI value that means off derives instead of returning 4173', () => {
		for (const off of CI_MEANS_OFF) {
			expect(runningInCi({ CI: off }), JSON.stringify(off)).toBe(false);
			expect(previewPort(WORKTREES[1], { CI: off }), JSON.stringify(off)).toBe(
				previewPort(WORKTREES[1], NOTHING_SET)
			);
		}
		for (const on of ['true', 'TRUE', '1', 'yes']) {
			expect(runningInCi({ CI: on }), on).toBe(true);
		}
	});

	test('an explicit PREVIEW_PORT still wins, on a runner and off one', () => {
		expect(previewPort(WORKTREES[0], { PREVIEW_PORT: '4187' })).toBe(4187);
		expect(previewPort(WORKTREES[0], { PREVIEW_PORT: '4187', CI: 'true' })).toBe(4187);
		// An empty value is nobody asking for anything, not a request for port 0.
		expect(previewPort(WORKTREES[0], { PREVIEW_PORT: '  ' })).toBe(
			previewPort(WORKTREES[0], NOTHING_SET)
		);
	});

	test('a PREVIEW_PORT that is not a port fails loudly', () => {
		// The old default read `Number(process.env.PREVIEW_PORT ?? 4173)`, so a
		// typo became NaN and the suite spent two minutes polling a URL that
		// could never answer.
		for (const bad of ['port', '0', '65536', '4187.5', '-1']) {
			expect(() => previewPort(WORKTREES[0], { PREVIEW_PORT: bad }), bad).toThrow(/PREVIEW_PORT/);
		}
	});

	test('the range clears the ports a person picks and the ones the system hands out', () => {
		// Every number a sibling checkout has held on this machine is under 4400.
		expect(DERIVED_PORT_FLOOR).toBeGreaterThan(4400);
		// Linux hands out ephemeral ports from 32768, Windows from 49152. Staying
		// under the lower of the two keeps the operating system out of the range.
		expect(DERIVED_PORT_FLOOR + DERIVED_PORT_SPAN).toBeLessThanOrEqual(32768);

		for (const worktree of WORKTREES) {
			const port = previewPort(worktree, NOTHING_SET);
			expect(port, worktree).toBeGreaterThanOrEqual(DERIVED_PORT_FLOOR);
			expect(port, worktree).toBeLessThan(DERIVED_PORT_FLOOR + DERIVED_PORT_SPAN);
		}
	});

	test('baseURL, the poll URL and the preview command all carry one port', () => {
		// The derivation being right buys nothing if the config wired only one of
		// the three places the port appears.
		const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
		const expected = previewPort(frontend, process.env);

		const server = Array.isArray(config.webServer) ? config.webServer[0] : config.webServer;
		expect(server, 'the config must start its own preview server').toBeTruthy();

		const baseUrl = config.use?.baseURL ?? '';
		const pollUrl = server?.url ?? '';
		const command = server?.command ?? '';

		expect(baseUrl, 'baseURL').toBe(`http://127.0.0.1:${expected}`);
		expect(pollUrl, 'the poll URL').toBe(`http://127.0.0.1:${expected}/`);
		expect(command, 'the preview command').toContain(`--port ${expected} `);
	});
});
