/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

/** The offline reader.
 *
 * A day a reader has already opened can be read again with no network. That is
 * the whole feature, and it is the only reason this file exists.
 *
 * **The way out is written before the way in, and it is checked before a single
 * byte is spent.** A worker is the only code this project ships that outlives
 * the tab, so a broken one cannot be fixed by the reader closing it. Every
 * entry point below asks the same committed file - `service-worker-kill.json`
 * at the site root - whether workers at this version must retire, and a worker
 * that must retire deletes every cache it owns and unregisters itself. It asks
 * at **install**, so a retired worker precaches nothing, and at **activate**,
 * which is where the retirement lands.
 *
 * **The page asks the same question, in `$lib/offline.ts`, and that is the half
 * that does not depend on this file working.** A worker whose activate handler
 * is broken is precisely the reader-pinned-to-a-bad-bundle failure the switch
 * exists for, and a switch only this file could read would be no way out of it.
 * It is also what makes a retirement converge: the layout registers on every
 * load, and a registration pending removal is resurrected by the next
 * `register()`.
 * **Rule #1 is unaffected, and this file is where that is checkable rather than
 * asserted.** Every request below is refused unless it is a GET for our own
 * origin. Nothing is reported anywhere, there is no notification, no push and
 * no background sync, and `frontend/tests/manifest.spec.ts` reads this source
 * and fails on any of those names.
 *
 * **What it caches, and what it will not.** On install, the shell's own assets
 * and its stylesheets: the font, the icons, the manifest, the CSS. Not the
 * app's JavaScript, and that was measured rather than assumed - `build` is
 * 23.56 MB, of which 21.60 MB is the search encoder's runtime and 1.47 MB is
 * two libraries that only the operator console and the search panel ever load.
 * Downloading those for a reader who opened one day is the same spend that
 * argued against precaching days. The code a page needs is fetched by that page
 * and kept at that moment, which is what makes a day already opened read again.
 *
 * A day payload is kept only after that day has been fetched once. Never a day
 * nobody asked for: that spends a stranger's data on a guess and grows with the
 * archive. Never the encoder's model and runtime, 43.2 MB together, which keep
 * their own store. Never the switch itself.
 *
 * **Both caches have a rule, and neither of them is "whatever a page asked
 * for".** The kept days are bounded twice - by `ui.offline_days_kept` and by
 * `ui.offline_bytes_kept` - because one day payload runs from 11,547 to
 * 1,924,051 bytes (measured 2026-09-06 over the 17 committed days), so fourteen
 * of them is anything from 162 KB to 27 MB and a count promises the reader
 * nothing about their storage. The shell cache keeps what this build emitted
 * and the pages the reader opened; every other file this site publishes is
 * served and then forgotten, so a store named for one build's shell stops
 * taking a share of the archive.
 *
 * **The shell is network-first and a day is served from the device first.** The
 * shell changes on every deploy, so a stale one is the bug the switch above
 * exists for. A day is different: an archived day never changes again, so
 * reading it off the device is correct. **Today's day is the exception, and it
 * is why this is not a plain cache-first.** The pipeline republishes the current
 * day several times an hour, so a reader who opened it at nine would otherwise
 * be held at nine for the rest of the day. What ships returns the copy on the
 * device at once and refreshes it behind the reader, which costs exactly the
 * request they would have made with no worker at all.
 */

import { base, build, files, version } from '$service-worker';
import {
	BYTES_HELD,
	DAY_CACHE,
	DAY_PAYLOAD,
	KILL_FILE,
	SHELL_CACHE_PREFIX,
	evictions,
	ours,
	shellKeeps,
	type HeldDay
} from '$lib/offline';
import {
	OFFLINE_BYTES_KEPT,
	OFFLINE_DAYS_KEPT,
	OFFLINE_VERSION
} from '$lib/offline.generated';

const sw = self as unknown as ServiceWorkerGlobalScope;

/** One shell cache per build. `version` is SvelteKit's own build id, which
 * moves on every build, so a deploy never reads the last one's chunks. */
const SHELL_CACHE = `${SHELL_CACHE_PREFIX}${version}`;
const KILL_URL = `${base}/${KILL_FILE}`;

/** Every path this build emitted, as a path rather than as a URL, so a request
 * can be looked up in it. `$service-worker` names them once, at build time, and
 * that list is the shell - which is what makes the shell cache's membership a
 * question with an answer rather than "whatever a page asked for". */
const EMITTED = new Set(
	[...build, ...files].map((path) => new URL(path, sw.location.href).pathname)
);

/** Set once this worker has retired. Everything below it stops answering, so a
 * worker waiting for its last client to go away never serves from a cache it
 * has already deleted. */
let retired = false;

/** Whether the committed switch names this worker's version, or a later one.
 *
 * A switch that cannot be read is not a switch that says yes. A reader in a
 * tunnel would otherwise lose every day they had saved because one small file
 * could not be fetched - and a worker that retires itself whenever the network
 * is down is a worker that never works offline, which is the whole feature.
 */
async function mustRetire(): Promise<boolean> {
	try {
		const answer = await fetch(KILL_URL, { cache: 'no-store' });
		if (!answer.ok) return false;
		const named = (await answer.json())?.retired_through;
		return typeof named === 'number' && Number.isFinite(named) && named >= OFFLINE_VERSION;
	} catch {
		return false;
	}
}

/** Leave the reader's device the way this worker found it. */
async function retire(): Promise<void> {
	retired = true;
	const names = await caches.keys();
	await Promise.all(names.filter(ours).map((name) => caches.delete(name)));
	await sw.registration.unregister();
	console.warn(
		`[offline] ${KILL_FILE} retires readers at version ${OFFLINE_VERSION}; caches cleared`
	);
}

/** What the shell paints with, out of everything the build emitted.
 *
 * A stylesheet is the one thing a page cannot fetch late without the reader
 * watching it happen, and all of them together are 69 KB. Every other build
 * output is code, and code is kept when the page that needs it asks for it.
 */
function isStylesheet(path: string): boolean {
	return path.endsWith('.css');
}

/** The encoder's files. It caches its own model and answers range requests for
 * it, so a second cache in front of that is bytes twice and correctness once. */
function isEncoder(path: string): boolean {
	const rest = path.startsWith(base) ? path.slice(base.length) : path;
	return rest.startsWith('/assist/');
}

sw.addEventListener('install', (event) => {
	event.waitUntil(
		(async () => {
			if (await mustRetire()) return;
			const cache = await caches.open(SHELL_CACHE);
			// Degrade, do not fail (CLAUDE.md section 1a). `addAll` is all-or-nothing,
			// so one asset the host will not serve would fail the install - and a
			// worker that never installs is a worker that never reaches its own
			// activate handler, which is where the switch is read.
			// `files` is the shell's own assets and nothing else - `svelte.config.js`
			// decides that, and it is the one place the decision belongs.
			await Promise.all(
				[...files, ...build.filter(isStylesheet)].map((path) =>
					cache.add(path).catch((error) => {
						console.warn(`[offline] ${path} was not kept for offline reading`, error);
					})
				)
			);
		})()
	);
	// A reader with a stale worker is the failure this file is careful about, so
	// a new one takes over at once rather than waiting for every tab to close.
	// It is also what makes a retirement land on the next reload.
	sw.skipWaiting();
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			if (await mustRetire()) {
				await retire();
				return;
			}
			const names = await caches.keys();
			await Promise.all(
				names
					.filter((name) => ours(name) && name !== SHELL_CACHE && name !== DAY_CACHE)
					.map((name) => caches.delete(name))
			);
			await sw.clients.claim();
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	if (retired) return;

	const request = event.request;
	if (request.method !== 'GET') return;

	let url: URL;
	try {
		url = new URL(request.url);
	} catch {
		return;
	}
	// Rule #1, checkable rather than promised: nothing off our own origin is
	// touched, so no third party can be reached through this worker at all.
	if (url.origin !== sw.location.origin) return;
	// The way out is never served from a cache. A switch a worker reads out of
	// its own store is a switch that says whatever it said last time.
	if (url.pathname === KILL_URL) return;
	if (isEncoder(url.pathname)) return;

	event.respondWith(
		DAY_PAYLOAD.test(url.pathname) ? fromDayCache(event) : fromNetworkFirst(request, url)
	);
});

/** A published day: from the device if it is there, and refreshed behind the
 * reader either way.
 *
 * An archived day never changes again, so the copy on the device is the right
 * answer and no reader should wait for the network to confirm it. The day being
 * published right now does change - several times an hour - so the copy is
 * replaced as soon as the network answers, and the next read is current.
 *
 * A miss is an ordinary fetch, and a fetch that fails throws - which is the
 * designed Unreachable state the reading page already draws
 * (docs/concepts/ui-shell.md), not an error this worker should swallow.
 */
async function fromDayCache(event: FetchEvent): Promise<Response> {
	const request = event.request;
	const cache = await caches.open(DAY_CACHE);
	const held = await cache.match(request, { ignoreVary: true });
	const fresh = fetch(request).then(async (answer) => {
		if (answer.ok && answer.status === 200 && !answer.redirected) {
			await cache.put(request, await measured(answer));
			await evict(cache);
		}
		return answer;
	});
	if (held === undefined) return fresh;
	// The refresh outlives the response, so the worker is asked to stay awake for
	// it. A refresh that fails is a reader with no network, which is the whole
	// point of the copy just returned.
	event.waitUntil(fresh.then(noop, noop));
	return held;
}

function noop(): void {}

/** The same body, carrying what it costs the device.
 *
 * The size is taken once, here, from the body that is about to be stored. The
 * alternative is to read every kept day back on every eviction, which is up to
 * `OFFLINE_BYTES_KEPT` of blob reads for an answer this line already had.
 *
 * `content-length` and `content-encoding` are dropped with it, because they
 * describe what came down the wire and this is the decoded body.
 */
async function measured(answer: Response): Promise<Response> {
	const body = await answer.clone().arrayBuffer();
	const headers = new Headers(answer.headers);
	headers.delete('content-encoding');
	headers.delete('content-length');
	headers.set(BYTES_HELD, String(body.byteLength));
	return new Response(body, {
		status: answer.status,
		statusText: answer.statusText,
		headers
	});
}

/** What a kept day costs, off its own stamp, or off its body when a worker
 * before this one stored it without one. */
async function costOf(held: Response | undefined): Promise<number> {
	if (held === undefined) return 0;
	const stamp = held.headers.get(BYTES_HELD);
	if (stamp !== null && Number.isFinite(Number(stamp))) return Math.max(0, Number(stamp));
	return (await held.clone().arrayBuffer()).byteLength;
}

/** Keep the days the two bounds allow, and no more.
 *
 * `keys()` answers in insertion order, so the front of the list is the day
 * added longest ago. Without a bound the kept set grows with the archive, which
 * is the argument that was made against caching days at all - and a day count
 * alone is not that bound, because one day payload runs from 11,547 to
 * 1,924,051 bytes (measured 2026-09-06 over the 17 committed days), so fourteen
 * of them is anything from 162 KB to 27 MB.
 *
 * **Reading a stamp is not reading a body.** `match` hands back a response
 * whose body is untouched until something asks for it, so the walk below costs
 * one header read a kept day and never the bytes themselves.
 */
async function evict(cache: Cache): Promise<void> {
	const keys = await cache.keys();
	const held: HeldDay[] = [];
	for (const request of keys) {
		const answer = await cache.match(request, { ignoreVary: true });
		held.push({ key: request.url, bytes: await costOf(answer) });
	}
	const going = new Set(
		evictions(held, { days: OFFLINE_DAYS_KEPT, bytes: OFFLINE_BYTES_KEPT })
	);
	if (going.size === 0) return;
	await Promise.all(
		keys.filter((request) => going.has(request.url)).map((request) => cache.delete(request))
	);
}

/** The shell: from the network, and from the device only when there is no
 * network. A stale shell is the one thing this worker may not serve while the
 * host is answering.
 *
 * **What is kept here is what this build emitted plus the pages the reader
 * opened, and nothing else.** Anything the pipeline publishes - a drawing, a
 * telemetry shard, a month index - is served and then forgotten, so this cache
 * holds one build's shell rather than a share of the archive.
 */
async function fromNetworkFirst(request: Request, url: URL): Promise<Response> {
	const cache = await caches.open(SHELL_CACHE);
	const keep = shellKeeps({
		pathname: url.pathname,
		navigation: request.mode === 'navigate',
		emitted: EMITTED
	});
	try {
		const answer = await fetch(request);
		if (keep && answer.ok && answer.status === 200 && !answer.redirected) {
			await cache.put(request, answer.clone());
		}
		return answer;
	} catch (error) {
		const held = await cache.match(request, { ignoreVary: true });
		if (held) return held;
		throw error;
	}
}
