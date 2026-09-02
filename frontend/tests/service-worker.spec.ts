import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * The offline reader, and the way out of it.
 *
 * Two arms, in one file on purpose. A worker whose exit has not been
 * demonstrated is the one failure a static site cannot recover from - a reader
 * pinned to a bundle with no way to reach the fix - so the arm that proves the
 * feature and the arm that proves the switch are read together or not at all.
 *
 * **A null result is a failure here, twice over.** An offline arm that
 * intercepted nothing has proved that a page loaded, which it would have done
 * anyway. A cleared-cache arm that started from an empty cache has cleared
 * nothing. Both counts are printed and both are asserted above zero before the
 * thing they are evidence for is asserted at all.
 *
 * Service workers are blocked for the rest of the suite (`playwright.config.ts`)
 * and turned back on here. Every test takes a fresh browser context, so nothing
 * one arm registers can reach the next.
 */

const BUILD = resolve(process.cwd(), 'build');
const GENERATED = resolve(process.cwd(), 'src', 'lib', 'offline.generated.ts');
const CACHE_PREFIX = 'idhazh-';

/** Where the switch has to be rewritten for the host to serve the new one.
 *
 * **Not `build/`, and that is the whole trap.** `playwright.config.ts` runs
 * `npm run preview`, and SvelteKit's preview server serves
 * `.svelte-kit/output/client` - the generated client assets plus the contents of
 * `static/` - rather than the adapter's `build/` directory. Writing the killed
 * switch into `build/` changes nothing the browser can see, and the arm then
 * fails on a worker that was behaving correctly. Both are written so the two
 * trees never disagree, and both are gitignored.
 */
const SWITCH_PATHS = [
	resolve(process.cwd(), '.svelte-kit', 'output', 'client', 'service-worker-kill.json'),
	join(BUILD, 'service-worker-kill.json')
];

test.use({ serviceWorkers: 'allow' });

/** The version the worker in `build/` was built with, read off the same
 * generated file the worker imports rather than restated here. */
function offlineVersion(): number {
	const named = /export const OFFLINE_VERSION = (\d+);/.exec(readFileSync(GENERATED, 'utf8'));
	if (named === null) throw new Error('the offline reader has no version to retire');
	return Number(named[1]);
}

/** The newest day the built site actually serves. */
function newestServedDay(): string {
	const root = join(BUILD, 'digest');
	const deepest = (at: string, depth: number): string[] =>
		depth === 0
			? [at]
			: readdirSync(at, { withFileTypes: true })
					.filter((entry) => entry.isDirectory())
					.flatMap((entry) => deepest(join(at, entry.name), depth - 1));
	const days = deepest(root, 3)
		.filter((path) => existsSync(join(path, 'digest.json')))
		.map((path) => path.slice(root.length + 1).split(/[\\/]/).join('-'))
		.sort();
	if (days.length === 0) throw new Error('the built site serves no day, so neither arm can run');
	return days[days.length - 1];
}

/** Resolved inside the run rather than at import time: a spec that throws while
 * it is being loaded fails every test in the suite, not its own. */
let DATE = '';
let DAY_URL = '';
let published = '';

test.beforeAll(() => {
	DATE = newestServedDay();
	DAY_URL = `/digest/${DATE.split('-').join('/')}/digest.json`;
	published = readFileSync(SWITCH_PATHS[0], 'utf8');
});

/** Publish a switch that retires this build's worker.
 *
 * The digit is replaced in place rather than the file rewritten, because the
 * preview server's static handler caches each file's size when it starts. A
 * body of a different length would be served against the old `Content-Length`,
 * which reads as a corrupt response rather than as a test that changed a file.
 */
function publishRetirement(): string {
	const killed = published.replace(
		/"retired_through":\s*\d+/,
		`"retired_through": ${offlineVersion()}`
	);
	expect(
		killed.length,
		'the killed switch is a different length, so the host will serve it truncated'
	).toBe(published.length);
	for (const path of SWITCH_PATHS) writeFileSync(path, killed, { encoding: 'utf8' });
	return killed;
}

/** The worker is registered on mount and controls the page from the moment it
 * claims it. That is the only honest "the offline reader is on". */
async function controlled(page: Page): Promise<void> {
	await page.waitForFunction(() => navigator.serviceWorker.controller !== null, null, {
		timeout: 60_000
	});
}

/** Only the caches this project owns. The encoder's own store is not ours and
 * must survive everything below. */
async function ourCaches(page: Page): Promise<string[]> {
	return page.evaluate(
		async (prefix) => (await caches.keys()).filter((name) => name.startsWith(prefix)),
		CACHE_PREFIX
	);
}

/** Every request the worker answered, named by the browser rather than by the
 * worker. `workerStart` is non-zero on exactly the entries that went through a
 * service worker, so this needs nothing added to the worker to be measured.
 *
 * It is a floor rather than a total: the app's own chunks are served with an
 * immutable cache-control, so a reload takes them out of the browser's own
 * cache and they never reach the worker at all. */
async function servedByWorker(page: Page): Promise<string[]> {
	return page.evaluate(() => {
		const entries = [
			...performance.getEntriesByType('navigation'),
			...performance.getEntriesByType('resource')
		] as PerformanceResourceTiming[];
		return entries
			.filter((entry) => entry.workerStart > 0)
			.map((entry) => new URL(entry.name, location.href).pathname);
	});
}

test.afterEach(async ({ page, context }) => {
	// A worker outlives the page that registered it, and the switch is a file on
	// disk. Neither may reach the next test.
	await context.setOffline(false);
	if (published !== '') {
		for (const path of SWITCH_PATHS) writeFileSync(path, published, { encoding: 'utf8' });
	}
	await page
		.evaluate(async () => {
			for (const registration of await navigator.serviceWorker.getRegistrations()) {
				await registration.unregister();
			}
			for (const name of await caches.keys()) await caches.delete(name);
		})
		.catch(() => {
			// The kill-switch arm ends on a page that could not load. There is
			// nothing left to clean up there, and the context is discarded anyway.
		});
});

test.describe('a day already opened', () => {
	test('reads again with no network at all', async ({ page, context }) => {
		await page.goto(`/${DATE}/`);
		await controlled(page);

		// The day payload goes onto the device the way a reader puts it there: by
		// asking for it once. Nothing prefetched it and nothing will.
		const first = await page.evaluate((url) => fetch(url).then((answer) => answer.status), DAY_URL);
		expect(first, 'the day this arm is about is not served').toBe(200);

		// One reload online, so the document itself is on the device too. The
		// first load came from the network - a worker claims a page it did not
		// serve.
		await page.reload();
		await controlled(page);
		const online = await page.locator('article.item[id]').count();
		expect(online, 'the day rendered no stories, so there is nothing to read again').toBeGreaterThan(
			0
		);

		const held = await ourCaches(page);
		expect(held, 'nothing was kept, so an offline read would prove nothing').not.toEqual([]);

		await context.setOffline(true);
		await page.reload();

		// The same day, the same stories, with the host unreachable.
		expect(await page.locator('article.item[id]').count(), 'the day read short offline').toBe(
			online
		);
		await expect(page.locator('[data-payload-state]')).not.toHaveAttribute(
			'data-payload-state',
			'unreachable'
		);

		// The body is read, not just the status. A resource-timing entry lands when
		// the response is finished, so a fetch left half-read is a request the
		// count below cannot see - which would leave the arm reporting one.
		const offline = await page.evaluate(
			(url) =>
				fetch(url)
					.then(async (answer) => {
						await answer.arrayBuffer();
						return answer.status;
					})
					.catch(() => 0),
			DAY_URL
		);
		expect(offline, 'the day payload did not come off the device').toBe(200);

		// The shell's own assets, kept on install. Nothing on the way here fetched
		// this, so a 200 with the host unreachable can only be the install cache.
		const shell = await page.evaluate(() =>
			fetch('/manifest.webmanifest')
				.then(async (answer) => {
					await answer.arrayBuffer();
					return answer.status;
				})
				.catch(() => 0)
		);
		expect(shell, 'the shell assets were not kept on install').toBe(200);

		await expect
			.poll(async () => (await servedByWorker(page)).length, { timeout: 15_000 })
			.toBeGreaterThan(1);
		const answered = await servedByWorker(page);
		console.log(
			`[service-worker] requests the worker answered offline: ${answered.length} ` +
				`[${answered.join(', ')}]`
		);
	});
});

test.describe('the way out', () => {
	test('the switch unregisters the worker and clears every cache it owns', async ({
		page,
		context
	}) => {
		await page.goto(`/${DATE}/`);
		await controlled(page);
		await page.evaluate((url) => fetch(url), DAY_URL);
		await page.reload();
		await controlled(page);

		const before = await ourCaches(page);
		console.log(`[service-worker] caches before the switch: ${before.length} [${before.join(', ')}]`);
		expect(before.length, 'nothing was cached, so clearing it would prove nothing').toBeGreaterThan(
			0
		);
		const encoderCache = 'transformers-cache';
		await page.evaluate((name) => caches.open(name), encoderCache);

		// Publish the switch. This is the committed file the build writes, named
		// at this build's own version - the one edit an operator makes to retire
		// every worker already on a reader's device.
		publishRetirement();
		const named = await page.evaluate(async () => {
			const answer = await fetch('/service-worker-kill.json', { cache: 'no-store' });
			return (await answer.json()).retired_through;
		});
		expect(named, 'the host is still serving the old switch, so nothing was published').toBe(
			offlineVersion()
		);

		// One reload. The worker reads the switch on the navigation it just
		// served, and retires itself.
		await page.reload();

		await expect.poll(async () => (await ourCaches(page)).length, { timeout: 60_000 }).toBe(0);

		// One more, and this is what "it unregistered itself" means to a reader: the
		// page they load next is served by nobody. A retired worker never claims a
		// client, and the one that retired is gone - so no worker controls this
		// page. Counting registrations instead would be a race, because the layout
		// registers on mount and a registration pending removal is resurrected by
		// the next `register()`.
		await page.reload();
		await expect
			.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null), {
				timeout: 60_000
			})
			.toBe(false);
		const after = await ourCaches(page);
		console.log(
			`[service-worker] caches after the switch: ${after.length}, and no worker controls the page`
		);
		expect(after, 'a cache came back after the retirement').toEqual([]);

		// The cache that is not ours is still there. A retirement that took the
		// encoder's 43.2 MB with it would cost a reader a download they never
		// asked to repeat.
		expect(
			await page.evaluate((name) => caches.has(name), encoderCache),
			'the retirement deleted a cache this project does not own'
		).toBe(true);

		// The second reload, and the assertion the whole row turns on: with the
		// worker gone and its caches gone, the page can only come from the
		// network. Take the network away and it cannot come at all.
		await context.setOffline(true);
		const refused = await page.reload().then(
			() => null,
			(error: Error) => error.message
		);
		expect(
			refused,
			'the page loaded with no network after the retirement, so something is still serving it'
		).not.toBeNull();
	});
});
