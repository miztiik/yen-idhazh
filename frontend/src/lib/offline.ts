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

/** Whether a cache belongs to this project. */
export function ours(cacheName: string): boolean {
	return cacheName.startsWith(CACHE_PREFIX);
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
