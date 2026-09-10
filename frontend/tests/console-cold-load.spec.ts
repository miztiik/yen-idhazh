import { expect, test, type Request } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * How many round trips a reader waits through before the console has its rows.
 *
 * `bundle-gate.mjs` weighs files. It cannot weigh a wait, and a wait is what a
 * reader on a slow link actually pays: four fetches of 50 KB that must happen
 * one after another cost more than one fetch of 200 KB, and no byte ceiling
 * anywhere can tell the two apart. That is the whole reason this spec is here
 * rather than in the gate script.
 *
 * **The ceiling is four, and it is a design decision rather than a measurement**
 * (Carmack, row 10 decision 2, `docs/architecture/publishing/console-payloads.md`).
 * Measured 2026-09-10 on the real build, Intel Core i7-1265U / Windows 11 /
 * node 24.12.0, against `vite preview`: a cold `/console/` load makes 47
 * requests in **three** serial hops - the document and everything a
 * `modulepreload` names arrive together, then one telemetry shard, then the
 * next. So there is one hop of headroom, and it is not spare change: the page
 * fetches its months one after another, so a fourth month in the default
 * window is a fourth hop.
 *
 * **A hop is a request that could not have started until an earlier one had
 * finished**, and the chain is the longest run of those. Every request is a
 * node; a request that ends before another starts is an edge; the answer is the
 * longest path. That reads the dependency the browser actually had rather than
 * a number of requests: two payloads asked for at the same moment are one hop,
 * and two asked for in sequence are two.
 *
 * **What counts is the document and the fetches the page's own code makes.**
 * Scripts, styles and fonts are left out, and not because they are free - a
 * reader waits for those too. They are left out because they are not what this
 * bounds. The module graph is Vite's, it arrives as one `modulepreload` wave
 * the document names, and its depth on any given run is a fact about how fast
 * the machine ran rather than about the design: measured 2026-09-10, the same
 * page put its telemetry fetches beside the module wave on one run and behind
 * it on another, which moved a chain of three to a chain of five with no source
 * change at all. A ceiling that answers differently on a fast laptop and a slow
 * runner is not a ceiling. What row 10 decided, and what this holds, is how many
 * payload round trips the console may need before it can show a row.
 *
 * **Grouping the requests into waves was tried first and it is wrong.** It laid
 * them out in start order and opened a new wave whenever one began after every
 * request in the current wave had completed - which sounds like the same thing
 * and is not. One slow download holds its wave open, and a whole serial chain
 * running beside it is absorbed into that wave and counted once. It was proved
 * wrong by this file's own oracle: two round trips added ahead of the telemetry
 * fetches, so the real chain went from three to five, and the wave count did not
 * move. A guard that cannot fail is worse than no guard, because it reads as
 * one.
 *
 * The band is not one of them, and that is worth saying because it is the first
 * thing the console needs. `console/+layout.ts` is a universal load on a
 * prerendered route, so SvelteKit runs it at build time and serialises the
 * result into the document - a cold load pays nothing for the verdict. It costs
 * a hop only on a client-side navigation into the console, which is not a cold
 * load and not what this bounds.
 */

const REPO = resolve(process.cwd(), '..');

/** The ceiling, and the window that decides how many shards the page wants. */
const CONFIG = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')) as {
	console: { default_window_days: number };
};

const MAX_HOPS = 4;

/** The document, and every request the page's own code issued. */
const COUNTED = new Set(['document', 'fetch', 'xhr']);

interface Timed {
	readonly url: string;
	readonly start: number;
	readonly end: number;
}

/** The longest run of requests that each had to wait for the one before it. */
function longestChain(requests: readonly Timed[]): string[] {
	const depth: number[] = [];
	const cameFrom: number[] = [];
	let deepest = -1;
	for (let here = 0; here < requests.length; here += 1) {
		let best = 0;
		let from = -1;
		for (let before = 0; before < here; before += 1) {
			if (requests[before].end <= requests[here].start && depth[before] > best) {
				best = depth[before];
				from = before;
			}
		}
		depth[here] = best + 1;
		cameFrom[here] = from;
		if (deepest < 0 || depth[here] > depth[deepest]) deepest = here;
	}
	const chain: string[] = [];
	for (let at = deepest; at >= 0; at = cameFrom[at]) chain.unshift(new URL(requests[at].url).pathname);
	return chain;
}

test('a cold console load settles inside four serial round trips', async ({ page }) => {
	const finished: Timed[] = [];
	/** The browser's own network timing, never the moment this handler ran.
	 *
	 * `performance.now()` inside the event handler was tried and it is not a
	 * measurement: Playwright dispatches these over a socket, so a run of quick
	 * local responses can arrive batched and every end lands after every start.
	 * The chain then reads as one hop no matter what the page did. `timing()` is
	 * what Chromium recorded, in milliseconds, and `responseEnd` is relative to
	 * `startTime`.
	 */
	const record = (request: Request) => {
		if (!COUNTED.has(request.resourceType())) return;
		const timing = request.timing();
		const end = timing.responseEnd >= 0 ? timing.startTime + timing.responseEnd : timing.startTime;
		finished.push({ url: request.url(), start: timing.startTime, end });
	};

	page.on('requestfinished', record);
	// A request that never answers is still a wait. Counting it keeps a broken
	// fetch from reading as a shorter chain than a working one.
	page.on('requestfailed', record);

	await page.goto('/console/');
	// The count and not the flag: `data-telemetry-fetching` reads `no` before the
	// first fetch starts as well as after the last one lands.
	await page.waitForFunction(
		() =>
			Number(
				document.querySelector('[data-telemetry-rows]')?.getAttribute('data-telemetry-rows') ?? 0
			) > 0,
		undefined,
		{ timeout: 20_000 }
	);

	finished.sort((left, right) => left.start - right.start);
	expect(
		finished.length,
		'the trace recorded no document and no fetch, so it proves nothing about the chain'
	).toBeGreaterThan(0);

	const chain = longestChain(finished);
	const report = chain.map((path, at) => `  ${at + 1}. ${path}`).join('\n');

	expect(
		chain.length,
		`a cold /console/ load took ${chain.length} serial round trips, over the ${MAX_HOPS} ` +
			`the design allows at console.default_window_days=${CONFIG.console.default_window_days}.\n` +
			'Each telemetry month is fetched after the one before it, so the usual cause is a\n' +
			'wider default window or a payload that moved out of the document and landed\n' +
			'behind something the page was already waiting for. The chain the browser walked:\n' +
			report
	).toBeLessThanOrEqual(MAX_HOPS);
});

test('the verdict band costs a cold load no round trip of its own', async ({ page }) => {
	const asked: string[] = [];
	page.on('request', (request) => asked.push(new URL(request.url()).pathname));

	await page.goto('/console/');
	await page.waitForSelector('[data-console-band]');

	expect(
		asked.filter((path) => path.endsWith('/console/band.json')),
		'the console fetched its band on a cold load. `console/+layout.ts` is a universal ' +
			'load on a prerendered route, so the verdict is serialised into the document and ' +
			'costs no request - a fetch here means the route stopped prerendering, and every ' +
			'reader now waits a round trip before the page can say anything at all.'
	).toEqual([]);
});
