/** The offline reader, from the page's side.
 *
 * The site ships a service worker so a day a reader has already opened can be
 * read again with no network, and an installed window is a reader rather than a
 * bookmark. This module is the half that runs in the page: it registers the
 * worker, and it answers which days the reader still holds.
 *
 * **It imports nothing from `$app`,** which is what lets the worker import the
 * cache names from here and a test import the whole module in plain Node. The
 * one value it would want, `base`, is passed in by the caller that already has
 * it.
 *
 * **Nothing here is on the reading path.** A browser that refuses to register a
 * worker, a private window with no cache storage, and a first visit all end in
 * the same place: the page renders from what it was served, and this module
 * has added nothing to wait for.
 */

/** Every cache this project owns starts with this. The encoder's own store is
 * `transformers-cache` and is not ours - a retirement that deleted it would
 * cost a reader a 43.2 MB download they never asked to repeat. */
export const CACHE_PREFIX = 'idhazh-';

/** The shell's cache, one per build. The build version is in the name, so a new
 * deploy never reads the last one's chunks. */
export const SHELL_CACHE_PREFIX = `${CACHE_PREFIX}shell-`;

/** The days a reader has opened. Not keyed on the build: a published day never
 * changes after its last run, so throwing it away on every deploy would spend a
 * reader's data to fetch back what they already had. */
export const DAY_CACHE = `${CACHE_PREFIX}days`;

/** The committed file that retires a worker, at the site root. */
export const KILL_FILE = 'service-worker-kill.json';

/** A served day, and the date it carries. The same three-part shape
 * `dayUrl` in `$lib/assist/day.ts` builds, checked rather than trusted. */
export const DAY_PAYLOAD = /\/digest\/(\d{4})\/(\d{2})\/(\d{2})\/digest\.json$/;

/** The data SvelteKit serves beside a prerendered document, for a page reached
 * without a fresh navigation. */
export const ROUTE_DATA = /\/__data\.json$/;

/** Whether a cache belongs to this project. */
export function ours(cacheName: string): boolean {
	return cacheName.startsWith(CACHE_PREFIX);
}

/** The header the worker stamps a kept day with, holding what its body costs
 * the device in bytes.
 *
 * Measured from the body that is stored, never read off `content-length`. That
 * header names the length of what came down the wire, and what came down the
 * wire is compressed while what is kept is the decoded body - so a ceiling set
 * from it would be a ceiling set from the wrong number.
 */
export const BYTES_HELD = 'x-idhazh-bytes';

/** One day on the reader's device: what it is cached under, and what it costs. */
export interface HeldDay {
	/** The URL the day is cached under. */
	key: string;
	/** The bytes its body takes on the device. */
	bytes: number;
}

/** The two bounds on the kept set. */
export interface OfflineBounds {
	/** `ui.offline_days_kept`. */
	days: number;
	/** `ui.offline_bytes_kept`. */
	bytes: number;
}

/** Which held days a fresh one pushes off the device, oldest first.
 *
 * **Two bounds, because a day count cannot bound bytes.** Measured 2026-09-06
 * over the 17 committed days, one day payload runs 11,547 to 1,924,051 bytes -
 * a factor of 167 - so the same fourteen days is anything from 162 KB to 27 MB
 * and the count alone promises the reader nothing about their storage.
 *
 * `held` is oldest first, which is the order `Cache.keys()` answers in, and a
 * day that is fetched again is put again and so moves to the back. So the front
 * of the list is the day the reader has gone longest without opening.
 *
 * **One day is always kept, whatever it costs.** A ceiling that evicts a day as
 * fast as it arrives is worse than no cache at all: the reader pays the
 * download and keeps nothing. `ui.offline_bytes_kept` has a floor above the
 * largest day measured, so this is a guard rather than a path today.
 */
export function evictions(held: readonly HeldDay[], bounds: OfflineBounds): string[] {
	const days = Math.max(1, Math.trunc(bounds.days));
	const ceiling = Math.max(0, bounds.bytes);
	const cost = (day: HeldDay) => Math.max(0, day.bytes);
	let total = held.reduce((sum, day) => sum + cost(day), 0);
	let left = held.length;
	const going: string[] = [];
	for (const day of held) {
		if (left <= 1) break;
		if (left <= days && total <= ceiling) break;
		going.push(day.key);
		total -= cost(day);
		left -= 1;
	}
	return going;
}

/** Whether the shell cache keeps a response the network just answered.
 *
 * **An allow-list, and that is the point of it.** The shell cache used to take
 * any successful same-origin GET, so every file the pipeline publishes - a
 * drawing, a telemetry shard, a month index - landed in it the moment a page
 * asked for one. That is a store that grows with the archive rather than with
 * the shell, in a cache with no byte bound of its own.
 *
 * What is on the list is what this build emitted, plus the pages the reader
 * opened: the documents and the data SvelteKit serves beside them. Reading data
 * is not here - a day payload has its own cache, its own bounds and its own
 * rule, because it has to survive the deploy that empties this one.
 */
export function shellKeeps(what: {
	/** The request's path, base included. */
	pathname: string;
	/** Whether the browser asked for a document rather than a subresource. */
	navigation: boolean;
	/** Every path this build emitted, as `$service-worker` names them. */
	emitted: ReadonlySet<string>;
}): boolean {
	return what.navigation || ROUTE_DATA.test(what.pathname) || what.emitted.has(what.pathname);
}

/** Start the offline reader, retire it, or leave the page exactly as it was.
 *
 * **The page reads the switch too, and that is not a duplicate of the worker's
 * own check.** It is the half that does not depend on the worker being well. A
 * worker whose activate handler is broken is exactly the reader-pinned-to-a-bad-
 * bundle failure the switch exists for, and a page that asked the broken worker
 * to please stop would have no way out of it. It is also the half that
 * converges: the layout registers on every load, and a registration pending
 * removal is resurrected by the next `register()`, so a worker that only
 * retired itself would come straight back.
 *
 * `updateViaCache: 'none'` is the other load-bearing option. It makes the
 * browser revalidate the worker script on every navigation instead of serving
 * it from the HTTP cache, which is how a new worker reaches a reader who has
 * one installed.
 *
 * A rejected registration is caught rather than left to become an unhandled
 * rejection. Offline reading is a bonus, so its absence is a line in the
 * console (CLAUDE.md section 1b) and never a state a reader has to act on.
 */
export async function startOfflineReader(where: {
	/** `<base>/service-worker.js`, built by the caller that has `base`. */
	worker: string;
	/** `<base>/service-worker-kill.json`. */
	switchFile: string;
	/** The version this build's worker carries. */
	version: number;
	isDev?: boolean;
}): Promise<void> {
	if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;
	if ((await retiredThrough(where.switchFile)) >= where.version) {
		await retireOfflineReader(where.worker);
		return;
	}
	try {
		await navigator.serviceWorker.register(where.worker, {
			type: where.isDev ? 'module' : 'classic',
			updateViaCache: 'none'
		});
	} catch (error) {
		console.warn('[offline] this browser is not keeping a copy of what you read', error);
	}
}

/** The version the committed switch retires through, or -1 when it cannot be
 * read.
 *
 * A switch that cannot be read is not a switch that says yes. A reader in a
 * tunnel would otherwise lose every day they had saved because one small file
 * could not be fetched, and -1 is below the lowest version a worker can carry.
 */
async function retiredThrough(switchFile: string): Promise<number> {
	try {
		const answer = await fetch(switchFile, { cache: 'no-store' });
		if (!answer.ok) return -1;
		const named = (await answer.json())?.retired_through;
		return typeof named === 'number' && Number.isFinite(named) ? named : -1;
	} catch {
		return -1;
	}
}

/** Leave the device the way the site found it: our worker gone, our caches
 * gone, and every other origin's storage untouched. */
async function retireOfflineReader(worker: string): Promise<void> {
	try {
		const script = new URL(worker, location.href).href;
		for (const registration of await navigator.serviceWorker.getRegistrations()) {
			// Only ours. `getRegistrations()` answers for the whole origin, and on a
			// project path that origin is shared with every other site the owner
			// publishes there.
			if (registration.active?.scriptURL === script) await registration.unregister();
		}
		if (typeof caches === 'undefined') return;
		for (const name of await caches.keys()) {
			if (ours(name)) await caches.delete(name);
		}
	} catch (error) {
		console.warn('[offline] the offline reader could not be retired', error);
	}
}

/** The published dates the reader can still read with no network, newest first.
 *
 * Read straight off the cache rather than asked of the worker. The page owns
 * this question, the answer is already on the device, and a message channel to
 * a worker that may be asleep is machinery for nothing.
 *
 * Empty is the designed answer: no cache storage, no worker, a first visit, or
 * a browser that threw all end here, and the caller shows what it would have
 * shown anyway.
 */
export async function daysHeldOffline(): Promise<string[]> {
	if (typeof caches === 'undefined') return [];
	try {
		if (!(await caches.has(DAY_CACHE))) return [];
		const held = await (await caches.open(DAY_CACHE)).keys();
		const dates: string[] = [];
		for (const request of held) {
			const parts = DAY_PAYLOAD.exec(new URL(request.url).pathname);
			if (parts !== null) dates.push(`${parts[1]}-${parts[2]}-${parts[3]}`);
		}
		return [...new Set(dates)].sort().reverse();
	} catch (error) {
		console.warn('[offline] the days held on this device could not be read', error);
		return [];
	}
}
