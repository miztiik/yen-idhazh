
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { connectSources, assetBaseUrl, encoderOrigins, engineOrigins, archiveOrigins } from '../asset-base.js';
import { COMPACT_INDEX_STAMP } from '../src/lib/data/compact-index';
import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, expectedAsk, expectedAskCost, EXPLORER_CANARY_DAY, openExplorer, runExplorer, tableRows } from './support/explorer-answer';
import { encodeQuestion } from '../src/lib/console/explorer/address';
import type { LedgerName } from '../src/lib/data/ledger';

const JOIN_LEDGERS = ['published', 'item-health'] as const satisfies readonly LedgerName[];
const JOIN_SQL = 'SELECT \'published x item-health\' AS pair, CAST(count(*) AS VARCHAR) AS rows FROM "published" p, "item-health" h';
const JOIN_FROM = '2026-08-07';

function addDays(day: string, delta: number): string {
	const date = new Date(`${day}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() + delta);
	return date.toISOString().slice(0, 10);
}

function dataLedger(pathname: string): string | null {
	return pathname.match(/\/state\/(?:compact|raw)\/([^/]+)\//)?.[1] ?? null;
}

function dataPathCoversDay(pathname: string, day: string): boolean {
	const [year, month, date] = day.split('-');
	return pathname.includes(`/daily/${year}/${month}/${date}.parquet`) ||
		pathname.includes(`/monthly/${year}/${month}.parquet`) ||
		pathname.includes(`/yearly/${year}/${year}.parquet`) ||
		pathname.includes(`/raw/`) && pathname.includes(`/${year}/${month}/${date}/`);
}

function emptyIndex(ledger: LedgerName, period: string): string {
	return JSON.stringify({ version: COMPACT_INDEX_STAMP, ledger, period, entries: [] });
}

async function chooseOnly(page: Page, ledgers: readonly LedgerName[], sql: string) {
	while (await page.locator('[data-ledger-name] input:checked').count() > 0) {
		await page.locator('[data-ledger-name] input:checked').first().click();
	}
	for (const ledger of ledgers) await page.locator(`[data-ledger-name="${ledger}"] input`).check();
	await page.locator('#explorer-sql').fill(sql);
}

async function answerSnapshot(page: Page): Promise<{ text: string; tone: string; button: string }> {
	const panel = page.locator('[data-console-panel-id="data-explorer-rows"]');
	const state = panel.locator('[data-explorer-idle], [data-state], [data-explorer-answer], .shimmer').first();
	await expect(state).toBeVisible({ timeout: 60_000 });
	return {
		text: (await state.innerText().catch(() => '')).replace(/\s+/g, ' ').trim(),
		tone: `${await state.getAttribute('data-state') ?? await state.getAttribute('data-explorer-idle') ?? await state.getAttribute('data-explorer-answer') ?? ''}:${await state.getAttribute('class') ?? ''}`,
		button: (await panel.locator('button').evaluateAll((buttons) => buttons.map((button) => button.textContent?.trim() ?? '').join('|')))
	};
}

async function statePage(parent: Page, drive: (page: Page) => Promise<void>): Promise<{ text: string; tone: string; button: string }> {
	const page = await parent.context().newPage();
	try {
		await drive(page);
		return await answerSnapshot(page);
	} finally {
		await page.close();
	}
}

test('THE ORACLE: Records opens as the sixth tab and renders its two panels before a run', async ({ page }) => {
	const response = await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	expect([200, 404]).toContain(response?.status());
	await expect(page.locator('[data-console-route="data-explorer"]')).toHaveCount(1);
	await expect(page.locator('[data-console-tab="data-explorer"]')).toContainText('Records');
	await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-idle]')).toContainText('Press Run');
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-explorer-idle]')).toContainText('If the answer holds a number');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('This page holds');
});

test('THE ORACLE: the Records fallback document carries the shipped content policy', () => {
	const html = readFileSync(resolve(process.cwd(), 'build', '404.html'), 'utf8');
	expect(html).toContain('content-security-policy');
	const expected = `connect-src ${connectSources(assetBaseUrl(), [...encoderOrigins(), ...engineOrigins(), ...archiveOrigins()]).map((source) => source === 'self' ? "'self'" : source).join(' ')}`;
	expect(html).toContain(expected);
	expect(html).toContain('extensions.duckdb.org');
});


test('THE ORACLE: a typed join matches the query door and the run cost matches the network', async ({ page }) => {
	await openExplorer(page);
	const columnFetches: string[] = [];
	page.on('response', (response) => {
		const url = response.url();
		const pathname = new URL(url).pathname;
		if (pathname.includes('/state/') && pathname.endsWith('.parquet')) columnFetches.push(pathname);
	});
	await chooseExplorerQuestion(page, JOIN_LEDGERS, JOIN_SQL);
	expect(new Set(columnFetches.map((path) => path.match(/\/state\/(?:compact|raw)\/([^/]+)\//)?.[1]).filter(Boolean))).toEqual(
		new Set(JOIN_LEDGERS)
	);

	const runResponses: Promise<number>[] = [];
	page.on('response', (response) => {
		const url = response.url();
		const pathname = new URL(url).pathname;
		if (!pathname.includes('/state/') || !pathname.endsWith('.parquet')) return;
		runResponses.push(response.body().then((body) => body.byteLength).catch(() => 0));
	});
	await runExplorer(page);
	const expected = await expectedAsk(page, {
		ledgers: JOIN_LEDGERS,
		from: JOIN_FROM,
		to: EXPLORER_CANARY_DAY,
		sql: JOIN_SQL,
		maxChars: 5782,
		maxRows: 1000,
		maxFetchBytes: 64 * 1024 * 1024
	});
	expect(expected).toMatchObject({ state: 'ok' });
	if (expected.state !== 'ok') return;
	expect(await tableRows(page)).toEqual(expected.rows.map((row) => expected.columns.map((column) => String(row[column.name] ?? 'null'))));
	const line = page.locator('[data-explorer-action-line]');
	expect(Number(await line.getAttribute('data-files'))).toBeGreaterThan(0);
	expect(Number(await line.getAttribute('data-bytes'))).toBe((await Promise.all(runResponses)).reduce((sum, bytes) => sum + bytes, 0));
});

test('THE ORACLE: choosing ledgers fetches one through day for each chosen ledger and no other data file', async ({ page }) => {
	await openExplorer(page);
	const asked: string[] = [];
	page.on('response', (response) => {
		const pathname = new URL(response.url()).pathname;
		if (pathname.includes('/state/') && pathname.endsWith('.parquet')) asked.push(pathname);
	});
	await chooseExplorerQuestion(page, JOIN_LEDGERS, JOIN_SQL);
	const spanFrom = addDays(EXPLORER_CANARY_DAY, -13);
	const cost = await expectedAskCost(page, JOIN_LEDGERS, spanFrom, EXPLORER_CANARY_DAY);
	const byLedger = new Map<string, string[]>();
	for (const pathname of asked) {
		const ledger = dataLedger(pathname);
		if (ledger !== null) byLedger.set(ledger, [...(byLedger.get(ledger) ?? []), pathname]);
	}
	expect(new Set(byLedger.keys())).toEqual(new Set(JOIN_LEDGERS));
	for (const ledger of JOIN_LEDGERS) {
		const through = cost.through[ledger];
		expect(through, `${ledger} has no through day`).toBeDefined();
		const paths = byLedger.get(ledger) ?? [];
		expect(paths.length, `${ledger} fetched no column-description file`).toBeGreaterThan(0);
		for (const pathname of paths) {
			expect(dataPathCoversDay(pathname, through ?? ''), `${pathname} does not cover ${ledger}'s through day ${through}`).toBe(true);
		}
	}
});

test('THE ORACLE: every Records answer state renders distinct words, tint and action', async ({ page, browser }) => {
	const seen = new Map<string, { text: string; tone: string; button: string }>();
	const remember = (name: string, snap: { text: string; tone: string; button: string }) => {
		const key = JSON.stringify(snap);
		expect([...seen.entries()].find(([, value]) => JSON.stringify(value) === key)?.[0], `${name} duplicates another state`).toBeUndefined();
		seen.set(name, snap);
	};

	remember('idle', await statePage(page, async (one) => openExplorer(one)));

	const engineContext = await browser.newContext({ serviceWorkers: 'block' });
	try {
		const one = await engineContext.newPage();
		await one.route(/duckdb.*(?:wasm|worker).*$/, (route) => route.abort());
		await openExplorer(one, false);
		await chooseOnly(one, ['published'], 'SELECT count(*) AS rows FROM "published"');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="unreachable"]')).toBeVisible();
		remember('engine did not start', await answerSnapshot(one));
	} finally {
		await engineContext.close();
	}

	remember('loading', await statePage(page, async (one) => {
		await openExplorer(one);
		let release!: () => void;
		const held = new Promise<void>((resolve) => { release = resolve; });
		await one.route('**/state/**/*.parquet*', async (route) => {
			await held;
			await route.continue();
		}, { times: 1 });
		await one.getByRole('button', { name: /^Run$/ }).click();
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] .shimmer')).toBeVisible();
		release();
	}));

	remember('quiet', await statePage(page, async (one) => {
		await openExplorer(one);
		await chooseExplorerQuestion(one, ['published'], 'SELECT * FROM "published" WHERE false');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="quiet"]')).toBeVisible();
	}));

	remember('missing not published', await statePage(page, async (one) => {
		await openExplorer(one);
		await chooseOnly(one, ['feed-health'], 'SELECT count(*) AS rows FROM "feed-health"');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="missing"]')).toBeVisible();
	}));

	remember('missing no days yet', await statePage(page, async (one) => {
		await one.route('**/state/compact/host-fingerprint/index/*.json', (route) => {
			const period = new URL(route.request().url()).pathname.match(/\/index\/([^/.]+)\.json$/)?.[1] ?? 'daily';
			return route.fulfill({ status: 200, contentType: 'application/json', body: emptyIndex('host-fingerprint', period) });
		});
		await openExplorer(one);
		await chooseOnly(one, ['host-fingerprint'], 'SELECT count(*) AS rows FROM "host-fingerprint"');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="missing"]')).toBeVisible();
	}));

	remember('unreachable file did not arrive', await statePage(page, async (one) => {
		await openExplorer(one);
		await one.route('**/state/**/*.parquet*', (route) => route.abort());
		await chooseOnly(one, ['counterfactual-scores'], 'SELECT count(*) AS rows FROM "counterfactual-scores"');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="unreachable"]')).toBeVisible();
	}));

	remember('unreachable gap', await statePage(page, async (one) => {
		await openExplorer(one);
		await one.route('**/state/**/*.parquet*', (route) => route.fulfill({ status: 404, body: '' }));
		await chooseOnly(one, ['seen'], 'SELECT count(*) AS rows FROM "seen"');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="unreachable"]')).toBeVisible();
	}));

	remember('refused', await statePage(page, async (one) => {
		await openExplorer(one);
		await chooseExplorerQuestion(one, ['published'], 'SELECT 1; SELECT 2');
		await runExplorer(one);
		await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="refused"]')).toBeVisible();
	}));

	expect(seen.size).toBe(9);
});

test('THE ORACLE: every published example runs without refusal or unreachable state', async ({ page }) => {
	await openExplorer(page);
	const titles = await page.locator('.question-strip button.example').evaluateAll((buttons) => buttons.map((button) => button.textContent?.trim() ?? '').filter(Boolean) as string[]);
	expect(titles.length).toBeGreaterThan(0);
	for (const title of titles) {
		await statePage(page, async (one) => {
			await openExplorer(one);
			await one.getByRole('button', { name: title }).click();
			await expect(one.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
			await runExplorer(one);
			await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-state="refused"], [data-console-panel-id="data-explorer-rows"] [data-state="unreachable"]')).toHaveCount(0);
			await expect(one.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-answer], [data-console-panel-id="data-explorer-rows"] [data-state="quiet"], [data-console-panel-id="data-explorer-rows"] [data-state="missing"]')).toHaveCount(1);
		});
	}
});

test('THE ORACLE: a refused run after a fetch still shows the page-held bytes', async ({ page }) => {
	await openExplorer(page);
	await chooseExplorerQuestion(page, JOIN_LEDGERS, JOIN_SQL);
	await runExplorer(page);
	const line = page.locator('[data-explorer-action-line]');
	await expect.poll(async () => Number(await line.getAttribute('data-held-bytes'))).toBeGreaterThan(0);
	const held = Number(await line.getAttribute('data-held-bytes'));
	await page.locator('#explorer-sql').fill('SELECT 1; SELECT 2');
	await runExplorer(page);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-state="refused"]')).toBeVisible();
	await expect.poll(async () => Number(await line.getAttribute('data-held-bytes'))).toBe(held);
	await expect(line).not.toContainText('This page holds 0.0 MB');
});

test('THE ORACLE: Records does not scroll sideways at phone width', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 900 });
	await openExplorer(page);
	const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
	expect(width.scroll).toBeLessThanOrEqual(width.client);
});

test('THE ORACLE: the browser refuses an origin outside connect-src', async ({ page }) => {
	await openExplorer(page);
	const violated = page.evaluate(() => new Promise<string>((resolve) => {
		document.addEventListener('securitypolicyviolation', (event) => resolve(event.violatedDirective), { once: true });
		void fetch('https://example.invalid/x').catch(() => undefined);
	}));
	await expect(violated).resolves.toContain('connect-src');
});


test('THE ORACLE: hostile cell text stays plain in the real table', async ({ page }) => {
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['published'], 'SELECT \'<script>alert(1)</script> https://example.invalid/x\' AS hostile FROM "published" LIMIT 1');
	await runExplorer(page);
	const table = page.locator('[data-explorer-answer]');
	await expect(table).toContainText('<script>alert(1)</script> https://example.invalid/x');
	await expect(table.locator('a, script, img')).toHaveCount(0);
});

test('THE ORACLE: a shared address fills the editor and does not run itself', async ({ page }) => {
	const sql = 'SELECT attempt, count(*) AS rows FROM "published" GROUP BY attempt ORDER BY attempt';
	const q = await encodeQuestion(sql);
	const fetched: string[] = [];
	page.on('response', (response) => {
		const pathname = new URL(response.url()).pathname;
		if (pathname.includes('/state/') && pathname.endsWith('.parquet')) fetched.push(pathname);
	});
	await page.clock.setFixedTime(`${EXPLORER_CANARY_DAY}T12:00:00Z`);
	await page.goto(`/console/data-explorer/?ledgers=published&days=14&q=${q}`, { waitUntil: 'domcontentloaded' });
	await expect(page.locator('#explorer-sql')).toHaveValue(sql);
	await expect(page.locator('[data-explorer-action-line]')).toContainText('This question came from a link');
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(0);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-idle]')).toContainText('Press Run');
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-explorer-idle]')).toContainText('If the answer holds a number');
	await expect.poll(() => fetched.length, { message: 'the link may only fetch column-description data before Run' }).toBeGreaterThan(0);
	await runExplorer(page);
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(1);
});

test('THE ORACLE: the chart panel follows the answer columns and keeps neutral no-chart words', async ({ page }) => {
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['summary-quality-evals'], "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)");
	await runExplorer(page);
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-chart-type="dateSeries"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-lede]')).toBeVisible();
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-comparison]')).toContainText('against');

	await chooseExplorerQuestion(page, ['published'], 'SELECT item_id FROM "published" LIMIT 1');
	await runExplorer(page);
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-shape-none]')).toContainText('Nothing here to draw');
});

test('THE ORACLE: Save, recent runs and Markdown copy preserve text without running a saved question', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await openExplorer(page);
	const sql = "SELECT '[x](https://example.invalid/a)|pipe' AS hostile FROM \"published\" LIMIT 1";
	await chooseExplorerQuestion(page, ['published'], sql);
	await page.getByRole('button', { name: /^Save$/ }).click();
	await page.getByLabel('Name').fill('Hostile copy');
	await page.getByRole('button', { name: /^Keep$/ }).click();
	await expect(page.locator('.saved-chip .example').filter({ hasText: 'Hostile copy' })).toHaveCount(1);

	await runExplorer(page);
	await page.getByRole('button', { name: /^Copy as table$/ }).click();
	await expect(page.locator('.copy-answer')).toContainText('Copied 1 row as a table.');
	const copied = await page.evaluate(() => navigator.clipboard.readText());
	expect(copied).toContain('`[x](https://example.invalid/a)\\|pipe`');

	await page.getByText('Asked in this browser').click();
	await expect(page.locator('.history-list button')).toContainText('1 row');
	await page.locator('.history-list button').first().click();
	await expect(page.locator('#explorer-sql')).toHaveValue(sql);
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(1);
});
