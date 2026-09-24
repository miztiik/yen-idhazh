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
 * **Both cases are here on purpose.** Prerendering used to serialise every story
 * a day published, so a story the contract refused failed the build and reached
 * nobody. A reading document has carried a seed since 2026-09-01 and the browser
 * fetches the rest, so the build never opens the stories past it. Two things
 * replaced that one guarantee and they only mean anything together: `idhazh
 * validate-days` stops the day, and the loader survives one that got past it. A
 * test proving either alone would leave the other free to rot.
 *
 * Case one runs the real command as a process and reads its exit code, over a
 * real pipeline-written day broken three ways. A day composed by hand drifts
 * from the one the pipeline writes, and a guard that only ever refuses proves
 * nothing - so the same command over the unbroken day has to come back clean.
 *
 * Case two serves broken bytes to the shipped loader in a real browser, over a
 * real network interception, and prints what it intercepted. Its payloads are
 * small on purpose: the loader reads four names off a story and nothing else,
 * so a whole day here would be testing the fixture. A degraded case that
 * intercepts nothing is a null result, not a pass.
 *
 * **The day case one breaks is the canary day, not a committed one** (2026-09-14).
 * It used to take the newest day under `frontend/public/digest`, which is a walk
 * over a collection every run appends to - banned by `CLAUDE.md` section 13 and
 * Guardrail #12 - and it cost more than a rule: on 2026-09-14 the pipeline
 * published an empty day, `items[items.length - 1]!` was `undefined`, and the
 * `TypeError` fired while the module was loading and took all of case one and all
 * of case two down with it. The canary day is written by the same contract models
 * and the same producer, so the "a hand-composed day drifts" intent holds, and it
 * is fixed in size.
 *
 * **What moved with it.** The third shape used to sit at the end of a day far
 * longer than `ui.shell_seed_items`, so it also demonstrated that no document
 * carried that story. The canary day is shorter than the seed, so that
 * demonstration is gone and nothing on the canary tree can replace it - there is
 * one hostile article per file under `tests/fixtures/canaries` and the day is as
 * long as that list. What case one still proves, and what was always the
 * load-bearing half, is that `validate-days` projects EVERY story through the
 * served contract and names that contract when one fails.
 */

const REPO = path.resolve(process.cwd(), '..');
const CANARY = path.join(REPO, 'backend', 'var', 'canary', 'digest');
const scratch = path.join(process.cwd(), 'test-results', 'malformed-day');

type Day = { date: string; text: string; assets: string[] };

/** The canary day that carries stories, as text, with the files filed under them.
 *
 * The tree is fixed: `backend/utilities/build_canary_day.py` writes one day of
 * stories and nineteen quiet ones, so reading it is a bounded read and not a
 * growing one. The day is found rather than named because the builder owns the
 * date, and a second copy of it here would be a constant that drifts
 * (Guardrail #6). Exactly one day may carry stories - if that stops being true
 * the builder changed shape, and this says so instead of picking one.
 */
function canaryDay(): Day {
	if (!existsSync(CANARY)) {
		throw new Error(
			`no canary tree at ${CANARY}. Run \`python backend/utilities/build_canary_day.py\`, ` +
				'which `npm run build:canary` does for the browser suite'
		);
	}
	const dirs = (at: string): string[] =>
		readdirSync(at, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort();
	const carrying: Day[] = [];
	for (const year of dirs(CANARY)) {
		for (const month of dirs(path.join(CANARY, year))) {
			for (const day of dirs(path.join(CANARY, year, month))) {
				const where = path.join(CANARY, year, month, day);
				const file = path.join(where, 'digest.json');
				if (!existsSync(file)) continue;
				const text = readFileSync(file, 'utf8');
				const items = (JSON.parse(text) as { items?: unknown[] }).items ?? [];
				if (items.length === 0) continue;
				carrying.push({
					date: `${year}-${month}-${day}`,
					text,
					// Everything the day directory holds for its stories. `run.json`
					// and `digest.json` belong to the day rather than to any story,
					// which is the same line `render.write.assets_in_day` draws.
					assets: readdirSync(where)
						.filter((name) => name !== 'digest.json' && name !== 'run.json')
						.map((name) => path.join(where, name))
				});
			}
		}
	}
	if (carrying.length !== 1) {
		throw new Error(
			`the canary tree holds ${carrying.length} days with stories, not 1, so case one ` +
				'cannot say which day it broke'
		);
	}
	return carrying[0]!;
}

/** The same day, with one thing wrong with it. */
function broken(day: Day, how: (payload: Record<string, unknown>) => void): string {
	const payload = JSON.parse(day.text) as Record<string, unknown>;
	how(payload);
	return JSON.stringify(payload);
}

/** A day that was never JSON. Shared by both cases, so it is not built from one. */
const NOT_JSON = '{ this was never JSON';

/** Three ways a published day is broken.
 *
 * The third is the one prerendering used to catch and no longer can: a story
 * the day holds that the served contract refuses. The build opens the stories
 * in the document's seed and no more, so past that seed this command is the
 * only thing that opens them at all.
 */
function brokenShapes(day: Day): Record<string, string> {
	const stories = (JSON.parse(day.text) as { items: unknown[] }).items;
	if (stories.length < 2) {
		throw new Error(`the canary day holds ${stories.length} stories, so breaking one proves little`);
	}
	return {
		notJson: NOT_JSON,
		noItemList: broken(day, (payload) => {
			payload.items = null;
		}),
		oneStoryTheViewRefuses: broken(day, (payload) => {
			const items = payload.items as Record<string, unknown>[];
			items[items.length - 1]!.summary = '';
		})
	};
}

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

/** One day on disk, in the layout the command globs for.
 *
 * The day's pictures come with it. `validate-days` holds a payload against the
 * directory it sits in - two stories on one chart, a chart the payload names
 * and cannot find, a file no story claims - so a tree carrying the JSON and
 * none of the visual data is not a healthy day with parts missing, it is a
 * broken one, and the command is right to say so.
 */
function treeHolding(day: Day, name: string, payload: string): string {
	const root = path.join(scratch, name, 'digest');
	rmSync(path.join(scratch, name), { recursive: true, force: true });
	const [year, month, date] = day.date.split('-');
	const where = path.join(root, year!, month!, date!);
	mkdirSync(where, { recursive: true });
	writeFileSync(path.join(where, 'digest.json'), payload, 'utf8');
	for (const asset of day.assets) {
		copyFileSync(asset, path.join(where, path.basename(asset)));
	}
	return root;
}

/** The command, run as a process. Its exit code and what it said.
 *
 * `--state-root` travels with `--digest-root` and the command refuses the pair
 * unless it does. A receipt records a payload's length and a day is settled on
 * that length, never on a re-read, so the committed receipts would settle these
 * scratch days without opening them - and the `unbroken` case, which is here
 * because a guard that only ever refuses proves nothing, would pass on a receipt
 * about a different file. It did: measured 2026-09-13, this case reported `0 of
 * them opened`. The same forgotten flag also filed receipts about scratch trees
 * into the tracked `state/day-validations.csv`, which
 * [build-state.ts](../scripts/build-state.ts) fingerprints, so the group changed
 * one of its own build's inputs while it ran (defect 20).
 */
function validateDays(root: string): { code: number; said: string } {
	const state = path.join(path.dirname(root), 'state');
	mkdirSync(state, { recursive: true });
	try {
		execFileSync(
			python(),
			['-m', 'idhazh', 'validate-days', '--digest-root', root, '--state-root', state],
			{
				cwd: REPO,
				encoding: 'utf8',
				stdio: 'pipe'
			}
		);
		return { code: 0, said: '' };
	} catch (thrown) {
		const failure = thrown as { status?: number; stderr?: string; message?: string };
		return { code: failure.status ?? -1, said: failure.stderr ?? failure.message ?? '' };
	}
}

/** A story the loader can render: the three names it reads, and no more. */
function story(n: number): Record<string, unknown> {
	return {
		item_id: `ai-${n}`,
		title: `A story that is fine, number ${n}`,
		summary: 'A summary long enough to be a summary.'
	};
}

const SERVED_DATE = '2026-08-30';
const WANTED = servedDayUrl(SERVED_DATE);
const PATTERN = `**${WANTED}`;

/** What a browser is handed, for each way the day is broken. */
const SERVED: Record<string, string> = {
	notJson: NOT_JSON,
	noItemList: JSON.stringify({ version: '2026-09-01T09:00', items: null }),
	oneStoryTheViewRefuses: JSON.stringify({
		version: '2026-09-01T09:00',
		items: [story(1), { ...story(2), summary: undefined }, story(3)]
	})
};

test('a malformed day is refused before it merges, and survived if it arrives', async ({
	page
}) => {
	// --- Case one: the guard refuses it, and names the day and the contract.
	//
	// The fixture is read here rather than at module load. A fixture this case
	// cannot use has to fail this test with a sentence naming the builder, not
	// throw while the file is loading and take case two down with it - which is
	// exactly what the committed-archive version did on 2026-09-14.
	const day = canaryDay();
	const shapes = brokenShapes(day);
	const refused: Record<string, { code: number; said: string }> = {};
	for (const [shape, payload] of Object.entries(shapes)) {
		refused[shape] = validateDays(treeHolding(day, shape, payload));
	}
	const healthy = validateDays(treeHolding(day, 'healthy', day.text));

	console.log(
		`[malformed-day] validate-days over canary ${day.date}: ` +
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
		expect(result.said, `the ${shape} failure never named the day`).toContain(day.date);
	}
	expect(
		refused.oneStoryTheViewRefuses!.said,
		'the failure did not name the contract that refused it'
	).toContain('digest-view.schema.json');

	// --- Case two: the same shapes reach a browser anyway, and nothing breaks.
	//
	// Not hypothetical. `ci.yml` never starts from a push the pipeline made, so
	// case one is a merge gate first and a publish gate second - and either way a
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

		if (shape === 'oneStoryTheViewRefuses') {
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
		// this case exists to rule out (`CLAUDE.md` section 12).
		await expect(page.locator('main').first()).toBeVisible();
	}

	// Printed, because a case that intercepted nothing served nothing and proves
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
