/** Retained request-dependency contracts, not a latency or throughput study. */
import { expect, test, type BrowserContext, type Page, type Request } from './support/door-page';

const MAX_HOPS = 4;
const COUNTED = new Set(['document', 'fetch', 'xhr']);
interface Timed { readonly url: string; readonly start: number; readonly end: number }

function longestChain(requests: readonly Timed[]): string[] {
	const depth: number[] = [];
	const cameFrom: number[] = [];
	let deepest = -1;
	for (let here = 0; here < requests.length; here += 1) {
		let best = 0;
		let from = -1;
		for (let before = 0; before < here; before += 1) {
			if (requests[before].end <= requests[here].start && depth[before] > best) {
				best = depth[before]; from = before;
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

async function coldPipelines(page: Page, context: BrowserContext, serialWaits: boolean) {
	const finished: Timed[] = [];
	const record = (request: Request) => {
		const url = new URL(request.url());
		const relevant = request.resourceType() === 'document' ||
			/\/state\/compact\/(item-health|summary-quality-evals)\//.test(url.pathname) ||
			url.pathname.endsWith('.wasm') || url.searchParams.has('serial-wait');
		if (!relevant || !COUNTED.has(request.resourceType())) return;
		// Browser timing avoids socket-dispatch batches turning a serial chain into one hop.
		const timing = request.timing();
		const end = timing.responseEnd >= 0 ? timing.startTime + timing.responseEnd : timing.startTime;
		finished.push({ url: request.url(), start: timing.startTime, end });
	};
	context.on('requestfinished', record);
	context.on('requestfailed', record);
	if (serialWaits) {
		await page.addInitScript(() => {
			const fetchResource = globalThis.fetch.bind(globalThis);
			let serial: Promise<void> | null = null;
			globalThis.fetch = async (...args: Parameters<typeof fetch>) => {
				const address = args[0] instanceof Request ? args[0].url : String(args[0]);
				if (/\/state\/compact\/(item-health|summary-quality-evals)\/index\//.test(address)) {
					serial ??= (async () => {
						for (const step of [1, 2]) {
							const answer = await fetchResource(`/favicon.svg?serial-wait=${step}`);
							await answer.arrayBuffer();
						}
					})();
					await serial;
				}
				return fetchResource(...args);
			};
		});
	}
	await page.goto('/console/');
	await page.waitForFunction(() =>
		document.querySelector('[data-console-panels="pipelines"]')?.getAttribute('data-route-state') === 'ok' &&
		document.querySelector('[data-timing="plot"]') !== null, undefined, { timeout: 20000 });
	finished.sort((left, right) => left.start - right.start);
	expect(finished.length, 'an empty request trace proves no dependency bound').toBeGreaterThan(0);
	const isWholeFile = (url: string) => /\/state\/compact\/(item-health|summary-quality-evals)\/(daily|monthly)\/.+\.parquet/.test(url);
	const isCore = (url: string) => /\/duckdb-eh\.[^/]+\.wasm$/.test(new URL(url).pathname);
	expect(finished.some((request) => isCore(request.url))).toBe(true);
	expect(finished.some((request) => request.url.endsWith('/parquet.duckdb_extension.wasm'))).toBe(true);
	const branches = ['item-health', 'summary-quality-evals'].flatMap((ledger) => {
		const own = finished.filter((request) => !request.url.includes('/state/compact/') ||
			request.url.includes(`/state/compact/${ledger}/`));
		return [longestChain(own.filter((request) => !isCore(request.url))),
			longestChain(own.filter((request) => !isWholeFile(request.url)))];
	});
	const chain = branches.reduce((longest, branch) => branch.length > longest.length ? branch : longest, [] as string[]);
	await test.info().attach('pipelines-cold-network', {
		body: JSON.stringify({ serialWaits, chain, branches, finished }), contentType: 'application/json'
	});
	return chain;
}

test('a cold console load settles inside four serial round trips', async ({ page, context }) => {
	expect((await coldPipelines(page, context, false)).length).toBeLessThanOrEqual(MAX_HOPS);
});
test('planted serial waits exceed the cold Pipelines budget', async ({ page, context }) => {
	expect((await coldPipelines(page, context, true)).length).toBeGreaterThan(MAX_HOPS);
});
for (const held of ['data', 'engine'] as const) {
	test(`Pipelines data and engine progress independently while ${held} responses are held`, async ({ page, context }) => {
		const dataFile = /\/state\/compact\/item-health\/(daily|monthly)\/.+\.parquet/;
		const coreWasm = /\/duckdb-eh\.[^/]+\.wasm(?:\?.*)?$/;
		let release = () => {};
		const gate = new Promise<void>((resolveGate) => { release = resolveGate; });
		let engineStarted = 0, dataFinished = 0, heldResponses = 0;
		context.on('request', (request) => { if (coreWasm.test(request.url())) engineStarted += 1; });
		context.on('requestfinished', (request) => { if (dataFile.test(request.url())) dataFinished += 1; });
		await context.route(held === 'data' ? dataFile : coreWasm, async (route) => {
			const response = await route.fetch();
			heldResponses += 1;
			await gate;
			await route.fulfill({ response });
		});
		try {
			await page.goto('/console/');
			await expect.poll(() => heldResponses).toBeGreaterThan(0);
			await expect.poll(() => held === 'data' ? engineStarted : dataFinished).toBeGreaterThan(0);
			await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'loading');
		} finally { release(); }
		await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'ok');
	});
}
test('the verdict band costs a cold load no round trip of its own', async ({ page }) => {
	const asked: string[] = [];
	page.on('request', (request) => asked.push(new URL(request.url()).pathname));
	await page.goto('/console/');
	await page.waitForSelector('[data-console-band]');
	expect(asked.filter((path) => path.endsWith('/console/band.json'))).toEqual([]);
});
