import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	BYTES_HELD,
	evictions,
	shellKeeps,
	type HeldDay,
	type OfflineBounds
} from '../src/lib/offline';
import { OFFLINE_BYTES_KEPT, OFFLINE_DAYS_KEPT } from '../src/lib/offline.generated';

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

/** A file the pipeline published that is not the shell and is not a day
 * payload: a drawing beside a day, or a telemetry shard.
 *
 * The shell cache used to keep whatever a page asked for, so this is the probe
 * that says whether it still does. It is discovered rather than named: a fixed
 * path would go stale, and a probe that 404s would make the arm prove nothing.
 */
function publishedButNotShell(): string {
	const under = (root: string, suffix: string): string[] =>
		existsSync(root)
			? readdirSync(root, { recursive: true, encoding: 'utf8' })
					.map((name) => name.replaceAll('\\', '/'))
					.filter((name) => name.endsWith(suffix))
					.map((name) => `${root.slice(BUILD.length).replaceAll('\\', '/')}/${name}`)
			: [];
	const found = [
		...under(join(BUILD, 'digest'), '.svg'),
		...under(join(BUILD, 'telemetry'), '.csv'),
		...under(join(BUILD, 'index'), '.json')
	].sort();
	if (found.length === 0) {
		throw new Error('the built site published no drawing, shard or index, so the probe is empty');
	}
	return found[0];
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

test.describe('the bounds on what is kept', () => {
	/** The measured extremes of a committed day payload: 2026-08-21 is 11,547
	 * bytes and 2026-08-24 is 1,924,051, over the 17 days committed on
	 * 2026-09-06. A factor of 167, which is why a day count cannot bound bytes. */
	const SMALLEST = 11_547;
	const LARGEST = 1_924_051;

	const BOUNDS: OfflineBounds = { days: OFFLINE_DAYS_KEPT, bytes: OFFLINE_BYTES_KEPT };

	/** Open one day after another, the way a reader does and the way the worker
	 * answers it: put the day, then evict, then look at what is left. */
	function opening(sizes: readonly number[], bounds: OfflineBounds) {
		let held: HeldDay[] = [];
		let peak = 0;
		let evicted = 0;
		const opened: string[] = [];
		sizes.forEach((bytes, n) => {
			const key = `https://example.test/digest/2026/09/${String(n).padStart(2, '0')}/digest.json`;
			opened.push(key);
			held = [...held.filter((day) => day.key !== key), { key, bytes }];
			const going = new Set(evictions(held, bounds));
			evicted += going.size;
			held = held.filter((day) => !going.has(day.key));
			peak = Math.max(
				peak,
				held.reduce((sum, day) => sum + day.bytes, 0)
			);
		});
		return { held, peak, evicted, opened };
	}

	test('held bytes stay under the ceiling across a sequence of large and small days', () => {
		// Ten of the smallest days, then twenty of the largest, then ten small
		// again. The day count binds at both ends and cannot bind in the middle:
		// fourteen of the largest day is 26,936,714 bytes against a ceiling of
		// 20,000,000.
		const sizes = [
			...Array.from({ length: 10 }, () => SMALLEST),
			...Array.from({ length: 20 }, () => LARGEST),
			...Array.from({ length: 10 }, () => SMALLEST)
		];
		const run = opening(sizes, BOUNDS);
		// The same rule with the ceiling taken off, which is the rule that shipped
		// before today: days counted, bytes not. It is the control, and it is what
		// says this sequence can overrun at all.
		const counted = opening(sizes, { days: BOUNDS.days, bytes: Number.POSITIVE_INFINITY });
		const total = run.held.reduce((sum, day) => sum + day.bytes, 0);
		console.log(
			`[service-worker] ${sizes.length} days opened. Counting days alone holds up to ` +
				`${counted.peak.toLocaleString()} bytes; counting bytes too holds up to ` +
				`${run.peak.toLocaleString()}, against a ${BOUNDS.bytes.toLocaleString()} ceiling. ` +
				`${run.held.length} days left holding ${total.toLocaleString()} bytes.`
		);

		expect(
			counted.peak,
			'counting days alone already stayed under the ceiling here, so this sequence proves nothing'
		).toBeGreaterThan(BOUNDS.bytes);
		expect(
			run.peak,
			`the kept days reached ${run.peak.toLocaleString()} bytes, over the ` +
				`${BOUNDS.bytes.toLocaleString()} the reader's device was promised`
		).toBeLessThanOrEqual(BOUNDS.bytes);
		expect(total, 'the days left at the end are over the ceiling').toBeLessThanOrEqual(BOUNDS.bytes);
		expect(run.held.length, 'the days left at the end are over the day bound').toBeLessThanOrEqual(
			BOUNDS.days
		);
		// Both rules evict the same number of days over a whole run - what is opened
		// and not held is the same either way. What the ceiling changes is how much
		// the device is asked to hold on the way there.
		expect(
			run.peak,
			'both rules held the same bytes, so counting bytes changed nothing'
		).toBeLessThan(counted.peak);
	});

	test('eviction takes whole days off the oldest end, so a day still held is whole', () => {
		const sizes = [
			...Array.from({ length: 6 }, () => SMALLEST),
			...Array.from({ length: 12 }, () => LARGEST),
			...Array.from({ length: 6 }, () => SMALLEST)
		];
		const run = opening(sizes, BOUNDS);
		expect(run.evicted, 'nothing was evicted, so nothing was left to be whole').toBeGreaterThan(0);
		// What is left is the newest run of days, unbroken. A hole here would be a
		// day the reader still sees listed and cannot open.
		const tail = run.opened.slice(run.opened.length - run.held.length);
		expect(
			run.held.map((day) => day.key),
			'a day was taken out of the middle, so a day still held lost part of itself'
		).toEqual(tail);
	});

	test('a day bigger than the whole ceiling is still kept', () => {
		const huge = BOUNDS.bytes * 2;
		expect(
			evictions([{ key: 'https://example.test/digest/2026/09/01/digest.json', bytes: huge }], BOUNDS),
			'the only day held was evicted, so the reader paid the download and kept nothing'
		).toEqual([]);
	});

	test('the shell cache keeps this build and the pages a reader opened, and nothing else', () => {
		const emitted = new Set(['/_app/immutable/entry/app.js', '/manifest.webmanifest']);
		const keeps = (pathname: string, navigation = false) =>
			shellKeeps({ pathname, navigation, emitted });

		expect(keeps('/2026-09-06/', true), 'a page the reader opened is not kept').toBe(true);
		expect(keeps('/2026-09-06/__data.json'), 'the data beside that page is not kept').toBe(true);
		expect(keeps('/_app/immutable/entry/app.js'), 'this build emitted it and it is not kept').toBe(
			true
		);
		expect(keeps('/manifest.webmanifest'), 'a shell asset is not kept').toBe(true);

		for (const published of [
			'/digest/2026/09/06/ai-1234567890.svg',
			'/telemetry/2026-09.csv',
			'/index/2026-09.json',
			'/service-worker.js'
		]) {
			expect(keeps(published), `${published} is not the shell and the shell kept it`).toBe(false);
		}
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

	test('is kept with what it costs the device, measured off the body that was stored', async ({
		page
	}) => {
		await page.goto(`/${DATE}/`);
		await controlled(page);
		const first = await page.evaluate((url) => fetch(url).then((answer) => answer.status), DAY_URL);
		expect(first, 'the day this arm is about is not served').toBe(200);

		const stamp = await page.evaluate(
			async ([url, header]) => {
				const name = (await caches.keys()).find((cache) => cache.endsWith('days'));
				if (name === undefined) return null;
				const held = await (await caches.open(name)).match(url, { ignoreVary: true });
				if (held === undefined) return null;
				const said = held.headers.get(header);
				return { said, real: (await held.arrayBuffer()).byteLength };
			},
			[DAY_URL, BYTES_HELD] as const
		);

		expect(stamp, 'the day was not kept, so there is no measurement to check').not.toBeNull();
		console.log(
			`[service-worker] ${DATE} was kept as ${stamp?.said} bytes and its body is ${stamp?.real}`
		);
		expect(
			Number(stamp?.said),
			'the kept day is stamped with a size its own body does not have, so the ceiling counts the wrong number'
		).toBe(stamp?.real);
	});

	test('leaves what the pipeline published out of the shell cache', async ({ page }) => {
		const published = publishedButNotShell();
		await page.goto(`/${DATE}/`);
		await controlled(page);
		// One reload, so the document itself goes through the worker. A worker
		// claims a page it did not serve, so the first navigation never reached it
		// and the shell cache would be missing the one entry this arm needs kept.
		await page.reload();
		await controlled(page);

		// Ask for it the way a page does, so the worker sees it and gets its chance
		// to keep it. A probe that never reached the worker would prove nothing.
		const served = await page.evaluate(
			(url) =>
				fetch(url)
					.then(async (answer) => {
						await answer.arrayBuffer();
						return answer.status;
					})
					.catch(() => 0),
			published
		);
		expect(served, `${published} is not served, so the shell had nothing to refuse`).toBe(200);

		const shell = await page.evaluate(
			async ([probe, document, asset]) => {
				const name = (await caches.keys()).find((cache) => cache.startsWith('idhazh-shell-'));
				if (name === undefined) return null;
				const cache = await caches.open(name);
				const has = async (url: string) =>
					(await cache.match(url, { ignoreVary: true })) !== undefined;
				return {
					name,
					kept: (await cache.keys()).length,
					probe: await has(probe),
					document: await has(document),
					asset: await has(asset)
				};
			},
			[published, `/${DATE}/`, '/manifest.webmanifest'] as const
		);

		expect(shell, 'there is no shell cache, so this arm proves nothing').not.toBeNull();
		console.log(
			`[service-worker] ${shell?.name} holds ${shell?.kept} entries; ${published} kept: ${shell?.probe}`
		);
		expect(
			shell?.document,
			'the page the reader opened is not in the shell cache, so it cannot be read again offline'
		).toBe(true);
		expect(shell?.asset, 'a shell asset kept on install is gone').toBe(true);
		expect(
			shell?.probe,
			`the shell cache kept ${published}, which the pipeline publishes and the shell does not need`
		).toBe(false);
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
