import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import {
	copyFileSync,
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync
} from 'node:fs';
import path from 'node:path';
import { Intercepted, loaderSource, servedDayUrl, type Loader } from './support/day-loader';

/**
 * A day that no reader can read: refused before it merges, survived when it
 * somehow arrives.
 *
 * **Both arms are here on purpose.** Prerendering used to serialise every story
 * a day published, so a story the contract refused failed the build and reached
 * nobody. A reading document has carried a seed since 2026-09-01 and the browser
 * fetches the rest, so the build never opens the stories past it. Two things
 * replaced that one guarantee and they only mean anything together: `idhazh
 * validate-days` stops the day, and the loader survives one that got past it. A
 * test proving either alone would leave the other free to rot.
 *
 * Arm one runs the real command as a process and reads its exit code, over a
 * REAL committed day broken three ways. A day composed by hand drifts from the
 * one the pipeline writes, and a guard that only ever refuses proves nothing -
 * so the same command over the unbroken day has to come back clean.
 *
 * Arm two serves broken bytes to the shipped loader in a real browser, over a
 * real network interception, and prints what it intercepted. Its payloads are
 * small on purpose: the loader reads four names off a story and nothing else,
 * so a whole committed day here would be testing the fixture. A degraded arm
 * that intercepts nothing is a null result, not a pass.
 */

const REPO = path.resolve(process.cwd(), '..');
const scratch = path.join(process.cwd(), 'test-results', 'malformed-day');

/** The newest committed day, as text, with the drawings that belong to it.
 * The tree is never empty - `backend/tests/test_contracts.py` asserts that on
 * its own. */
function newestCommittedDay(): { date: string; text: string; drawings: string[] } {
	const root = path.join(process.cwd(), 'public', 'digest');
	const dirs = (at: string): string[] =>
		readdirSync(at, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort();
	const found: string[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(path.join(root, year))) {
			for (const day of dirs(path.join(root, year, month))) {
				const file = path.join(root, year, month, day, 'digest.json');
				if (existsSync(file)) found.push(file);
			}
		}
	}
	expect(found.length, 'no committed day to break, so arm one proves nothing').toBeGreaterThan(0);
	const file = found[found.length - 1]!;
	const parts = file.split(path.sep);
	const where = path.dirname(file);
	return {
		date: parts.slice(-4, -1).join('-'),
		text: readFileSync(file, 'utf8'),
		drawings: readdirSync(where)
			.filter((name) => name.endsWith('.svg'))
			.map((name) => path.join(where, name))
	};
}

const COMMITTED = newestCommittedDay();

/** The same day, with one thing wrong with it. */
function broken(how: (day: Record<string, unknown>) => void): string {
	const day = JSON.parse(COMMITTED.text) as Record<string, unknown>;
	how(day);
	return JSON.stringify(day);
}

/** Three ways a committed day is broken.
 *
 * The third is the one prerendering used to catch and no longer can: the story
 * is at the END of a day far longer than `ui.shell_seed_items`, so no document
 * carries it and no build ever opens it.
 */
const BROKEN: Record<string, string> = {
	notJson: '{ this was never JSON',
	noItemList: broken((day) => {
		day.items = null;
	}),
	oneStoryPastTheSeed: broken((day) => {
		const items = day.items as Record<string, unknown>[];
		items[items.length - 1]!.key_points = [];
	})
};

/** Which python runs the command.
 *
 * A runner installs the backend onto the interpreter on `PATH`, and the
 * documented local setup is a `.venv` at the repository root. `IDHAZH_PYTHON`
 * is the escape for a worktree borrowing another checkout's environment, which
 * is how several agents share one machine
 * ([docs/reference/agent-notes.md](../../docs/reference/agent-notes.md)).
 */
function python(): string {
	const named = process.env.IDHAZH_PYTHON;
	if (named) return named;
	for (const candidate of [
		path.join(REPO, '.venv', 'Scripts', 'python.exe'),
		path.join(REPO, '.venv', 'bin', 'python')
	]) {
		if (existsSync(candidate)) return candidate;
	}
	return 'python';
}

/** One committed day on disk, in the layout the command globs for.
 *
 * The day's pictures come with it. `validate-days` holds a payload against the
 * directory it sits in - two stories on one chart, a chart the payload names
 * and cannot find, a file no story claims - so a tree carrying the JSON and
 * none of the drawings is not a healthy day with parts missing, it is a broken
 * one, and the command is right to say so.
 */
function treeHolding(name: string, payload: string): string {
	const root = path.join(scratch, name, 'digest');
	rmSync(path.join(scratch, name), { recursive: true, force: true });
	const [year, month, day] = COMMITTED.date.split('-');
	const where = path.join(root, year!, month!, day!);
	mkdirSync(where, { recursive: true });
	writeFileSync(path.join(where, 'digest.json'), payload, 'utf8');
	for (const drawing of COMMITTED.drawings) {
		copyFileSync(drawing, path.join(where, path.basename(drawing)));
	}
	return root;
}

/** The command, run as a process. Its exit code and what it said. */
function validateDays(root: string): { code: number; said: string } {
	try {
		execFileSync(python(), ['-m', 'idhazh', 'validate-days', '--digest-root', root], {
			cwd: REPO,
			encoding: 'utf8',
			stdio: 'pipe'
		});
		return { code: 0, said: '' };
	} catch (thrown) {
		const failure = thrown as { status?: number; stderr?: string; message?: string };
		return { code: failure.status ?? -1, said: failure.stderr ?? failure.message ?? '' };
	}
}

/** A story the loader can render: the four names it reads, and no more. */
function story(n: number): Record<string, unknown> {
	return {
		item_id: `ai-${n}`,
		title: `A story that is fine, number ${n}`,
		summary: 'A summary long enough to be a summary.',
		key_points: ['One point.']
	};
}

const SERVED_DATE = '2026-08-30';
const WANTED = servedDayUrl(SERVED_DATE);
const PATTERN = `**${WANTED}`;

/** What a browser is handed, for each way the day is broken. */
const SERVED: Record<string, string> = {
	notJson: BROKEN.notJson!,
	noItemList: JSON.stringify({ version: '2026-09-01T09:00', items: null }),
	oneStoryPastTheSeed: JSON.stringify({
		version: '2026-09-01T09:00',
		items: [story(1), { ...story(2), key_points: undefined }, story(3)]
	})
};

test('a malformed day is refused before it merges, and survived if it arrives', async ({
	page
}) => {
	// --- Arm one: the guard refuses it, and names the day and the contract.
	const refused: Record<string, { code: number; said: string }> = {};
	for (const [shape, payload] of Object.entries(BROKEN)) {
		refused[shape] = validateDays(treeHolding(shape, payload));
	}
	const healthy = validateDays(treeHolding('healthy', COMMITTED.text));

	console.log(
		`[malformed-day] validate-days over ${COMMITTED.date}: ` +
			Object.entries(refused)
				.map(([shape, result]) => `${shape} exit ${result.code}`)
				.join(', ') +
			`, unbroken exit ${healthy.code}`
	);

	expect(
		healthy.code,
		`the guard refuses a day it should accept, so its rejections prove nothing:\n${healthy.said}`
	).toBe(0);
	for (const [shape, result] of Object.entries(refused)) {
		expect(result.code, `a ${shape} day was accepted`).toBe(1);
		expect(result.said, `the ${shape} failure never named the day`).toContain(COMMITTED.date);
	}
	expect(
		refused.oneStoryPastTheSeed!.said,
		'the failure did not name the contract that refused it'
	).toContain('digest-view.schema.json');

	// --- Arm two: the same shapes reach a browser anyway, and nothing breaks.
	//
	// Not hypothetical. `ci.yml` never starts from a push the pipeline made, so
	// arm one is a merge gate first and a publish gate second - and either way a
	// reader's browser is the last thing standing.
	await page.addInitScript({ content: await loaderSource('malformed-day') });

	const uncaught: string[] = [];
	const said: string[] = [];
	page.on('pageerror', (error) => uncaught.push(String(error)));
	page.on('console', (message) => {
		if (message.type() === 'warning' || message.type() === 'error') said.push(message.text());
	});

	const served = new Intercepted();
	for (const [shape, payload] of Object.entries(SERVED)) {
		await page.unroute(PATTERN);
		await page.route(PATTERN, async (route) => {
			served.take(route.request().url());
			await route.fulfill({ contentType: 'application/json', body: payload });
		});

		// A fresh document each time, so the loader's held answer for this date
		// starts empty and every shape really reaches the network.
		await page.goto('/');
		const met = await page.evaluate(async (date: string) => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			const states: string[] = [];
			const day = await loader.watchDay(date, {
				slowMs: 30_000,
				onStatus: (status: string) => states.push(status)
			});
			return { states, items: day === null ? null : day.items.length };
		}, SERVED_DATE);

		if (shape === 'oneStoryPastTheSeed') {
			// A day is not thrown away over one story it cannot draw (`CLAUDE.md`
			// section 1a). The two it can draw are kept and the third is dropped.
			expect(met.states, 'a day with one bad story was thrown away whole').toEqual([
				'loading',
				'ready'
			]);
			expect(met.items, 'the loader kept a story the page cannot render').toBe(2);
		} else {
			// Nothing usable arrived, so the page says so and offers a retry rather
			// than claiming the day was never published.
			expect(met.states, `a ${shape} payload did not end in a designed state`).toEqual([
				'loading',
				'unreachable'
			]);
			expect(met.items, `a ${shape} payload handed back a day`).toBeNull();
		}

		// The page a reader is on is still a page. A white screen is the failure
		// this arm exists to rule out (`CLAUDE.md` section 12).
		await expect(page.locator('main').first()).toBeVisible();
	}

	// Printed, because an arm that intercepted nothing served nothing and proves
	// nothing about a malformed day.
	console.log(`[malformed-day] payload interceptions: ${served.count}`);
	expect(
		served.count,
		'nothing was intercepted, so no malformed payload ever reached the loader'
	).toBe(Object.keys(SERVED).length);
	expect(served.urls.every((url) => url === WANTED)).toBe(true);

	expect(uncaught, 'a malformed day threw where a reader could see it').toEqual([]);
	expect(
		said.filter((line) => line.includes(SERVED_DATE)),
		'nothing in the console named the day that could not be read'
	).not.toEqual([]);
});
