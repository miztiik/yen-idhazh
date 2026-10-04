
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { connectSources, assetBaseUrl, encoderOrigins, engineOrigins, archiveOrigins } from '../asset-base.js';
import { COMPACT_INDEX_STAMP } from '../src/lib/data/compact-index';
import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, expectedAsk, expectedAskCost, EXPLORER_CANARY_DAY, openExplorer, runExplorer, tableRows } from './support/explorer-answer';
import { encodeQuestion } from '../src/lib/console/explorer/address';
import { consoleConfig, explorerConfig } from '../src/lib/server/config';
import { shortDate } from '../src/lib/format';
import type { LedgerName } from '../src/lib/data/ledger';
import { CONSOLE_CHROMES, consoleChromeOf } from '../src/lib/console/chrome';

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

test('THE ORACLE: Data explorer opens as the sixth tab and renders its two panels before a run', async ({ page }) => {
	const response = await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	expect([200, 404]).toContain(response?.status());
	await expect(page.locator('[data-console-route="data-explorer"]')).toHaveCount(1);
	await expect(page.locator('[data-console-tab="data-explorer"]')).toContainText('Data explorer');
	await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-idle]')).toContainText('Press Run');
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-explorer-idle]')).toContainText('If the answer holds a number');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('This page holds');
});

test('THE ORACLE: console chrome resolves to console unless the route asks for workbench', () => {
	expect(CONSOLE_CHROMES).toEqual(['console', 'workbench']);
	expect(consoleChromeOf(null)).toBe('console');
	expect(consoleChromeOf({})).toBe('console');
	expect(consoleChromeOf({ chrome: 'console' })).toBe('console');
	expect(consoleChromeOf({ chrome: 'workbench' })).toBe('workbench');
	expect(consoleChromeOf({ chrome: 'something-else' })).toBe('console');
});

test('THE ORACLE: Data explorer asks for workbench chrome and the other routes keep console chrome', async ({ page }) => {
	await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-surface="operator"]')).toHaveAttribute('data-console-chrome', 'workbench');
	await expect(page.locator('#console-top')).toHaveText('Console');
	await expect(page.locator('#console-top')).toHaveClass(/sr-only/);
	await expect(page.locator('[data-console-band]')).toHaveCount(0);
	await expect(page.locator('[data-console-completeness]')).toHaveCount(0);
	await expect(page.locator('[data-window-status]')).toHaveCount(0);
	await expect(page.locator('[data-console-carry]')).toHaveCount(0);
	await expect(page.locator('[data-console-noscript]')).toHaveCount(0);
	await expect(page.locator('[data-console-contents]')).toHaveCount(0);

	for (const route of ['/console/', '/console/model/', '/console/machine/', '/console/judgement/', '/console/voices/']) {
		await page.goto(route, { waitUntil: 'domcontentloaded' });
		await expect(page.locator('[data-surface="operator"]'), `${route} kept full chrome`).toHaveAttribute('data-console-chrome', 'console');
		await expect(page.locator('[data-console-band]'), `${route} kept the band`).toHaveCount(1);
		await expect(page.locator('[data-window-control]'), `${route} kept the strip span control`).toHaveCount(1);
	}
});

for (const view of [
	{ width: 1440, height: 900 },
	{ width: 1024, height: 768 },
	{ width: 768, height: 900 },
	{ width: 390, height: 844 }
] as const) {
	test(`THE ORACLE: the workbench strip is one compact row at ${view.width}`, async ({ page }) => {
		await page.setViewportSize(view);
		await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
		const geometry = await page.locator('[data-console-strip]').evaluate((strip) => {
			const stripBox = strip.getBoundingClientRect();
			const tabs = [...strip.querySelectorAll('[data-console-tab]')].map((tab) => {
				const box = tab.getBoundingClientRect();
				return {
					id: tab.getAttribute('data-console-tab'),
					top: Math.round(box.top),
					bottom: Math.round(box.bottom),
					left: box.left,
					right: box.right,
					height: box.height,
					position: getComputedStyle(tab).position,
					text: (tab as HTMLElement).innerText.trim()
				};
			});
			const token = getComputedStyle(document.documentElement).getPropertyValue('--workbench-control').trim();
			const rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
			const control = token.endsWith('rem') ? parseFloat(token) * rootSize : parseFloat(token);
			return {
				height: stripBox.height,
				left: stripBox.left,
				right: stripBox.right,
				position: getComputedStyle(strip).position,
				control,
				tabs
			};
		});
		expect(new Set(geometry.tabs.map((tab) => tab.top)).size).toBe(1);
		expect(geometry.tabs).toHaveLength(6);
		expect(geometry.height).toBeLessThanOrEqual(geometry.control + 2);
		expect(geometry.position).not.toBe('sticky');
		const active = geometry.tabs.find((tab) => tab.id === 'data-explorer');
		const pipelines = geometry.tabs.find((tab) => tab.id === 'pipelines');
		expect(active, 'Data explorer tab was not drawn').toBeDefined();
		expect(active?.text).toContain('Data explorer');
		expect(active?.text).not.toContain('What the ledgers hold');
		expect(active?.height).toBeCloseTo(pipelines?.height ?? 0, 0);
		expect(active?.left ?? 0).toBeGreaterThanOrEqual(geometry.left - 0.5);
		expect(active?.right ?? 0).toBeLessThanOrEqual(geometry.right + 0.5);
	});
}

test('THE ORACLE: Data explorer puts the span and Run in the workbench toolbar', async ({ page }) => {
	await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	const toolbar = page.locator('[data-workbench-region="toolbar"]');
	await expect(toolbar).toHaveCount(1);
	await expect(page.locator('[data-window-control]')).toHaveCount(1);
	await expect(toolbar.locator('[data-window-control]')).toHaveCount(1);
	await expect(toolbar.getByRole('textbox', { name: 'From (UTC)' })).toHaveCount(1);
	await expect(toolbar.getByRole('textbox', { name: 'To (UTC)' })).toHaveCount(1);
	await expect(toolbar.getByRole('button', { name: /^Run$/ })).toHaveCount(1);
});

test('THE ORACLE: before a run the column rail names the selected ledger\'s own columns', async ({ page }) => {
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['host-fingerprint'], 'SELECT * FROM "host-fingerprint"');
	const rail = page.locator('[data-explorer-columns] li code');
	const before = await rail.allTextContents();
	expect(before.length, 'the rail names no column before a run').toBeGreaterThan(0);
	expect(before.filter((name) => !name.startsWith('host-fingerprint.')), 'a rail entry not named for its ledger').toEqual([]);
	await runExplorer(page);
	await expect(page.locator('[data-explorer-columns] h3')).toHaveText('Answer columns');
	const after = await rail.allTextContents();
	expect(new Set(before.map((name) => name.slice('host-fingerprint.'.length))), 'the rail before a run is not the ledger\'s columns').toEqual(new Set(after));
});

test('THE ORACLE: the Data explorer fallback document carries the shipped content policy', () => {
	const html = readFileSync(resolve(process.cwd(), 'build', '404.html'), 'utf8');
	expect(html).toContain('content-security-policy');
	const expected = `connect-src ${connectSources(assetBaseUrl(), [...encoderOrigins(), ...engineOrigins(), ...archiveOrigins()]).map((source) => source === 'self' ? "'self'" : source).join(' ')}`;
	expect(html).toContain(expected);
	expect(html).toContain('extensions.duckdb.org');
});

test('THE ORACLE: custom date inputs expose reach bounds and presets end today', async ({ page }) => {
	await openExplorer(page);
	const from = page.getByRole('textbox', { name: 'From (UTC)' });
	const to = page.getByRole('textbox', { name: 'To (UTC)' });
	const today = await to.getAttribute('max');
	if (today === null) throw new Error('To (UTC) has no max');
	expect(await from.getAttribute('min')).toBe(addDays(today, 1 - explorerConfig().reach_days));
	expect(await from.getAttribute('max')).toBe(today);
	expect(await to.getAttribute('max')).toBe(today);
	expect(await to.getAttribute('min')).toBe(await from.inputValue());

	await page.locator('[data-window-preset="30"]').click();
	await expect(to).toHaveValue(today);
	await expect(from).toHaveValue(addDays(today, -29));

	await from.fill(today);
	await expect(to).toHaveAttribute('min', today);
	await to.fill(addDays(today, -10));
	await expect(to).toHaveValue(today);
});

test('THE ORACLE: with no archive prefix, an old custom span reads from the site\'s oldest day and says so', async ({ page }) => {
	await page.addInitScript(() => {
		Object.defineProperty(globalThis, '__ARCHIVE_BASE_URL__', { value: '', configurable: true });
	});
	await openExplorer(page);
	const from = addDays(EXPLORER_CANARY_DAY, 1 - explorerConfig().reach_days);
	await chooseExplorerQuestion(page, ['published'], 'SELECT min("covers") AS first_day FROM "published"');
	await page.getByRole('textbox', { name: 'From (UTC)' }).fill(from);
	const { siteFrom } = await expectedAskCost(page, ['published'], from, EXPLORER_CANARY_DAY);
	if (siteFrom === null) throw new Error(`this site holds published days from ${from}, so the span was not cut`);
	await runExplorer(page);
	const panel = page.locator('[data-console-panel-id="data-explorer-rows"]');
	await expect(panel.locator('.answer-note')).toContainText(`Days before ${shortDate(siteFrom)} are not on this site.`);
	await expect(panel.locator('.warn')).toHaveCount(0);
	const [[firstDay]] = await tableRows(page);
	expect(firstDay).toMatch(/^\d{4}-\d{2}-\d{2}$/);
	expect(firstDay >= siteFrom, `the answer starts on ${firstDay}, before the site's ${siteFrom}`).toBe(true);
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
	const fetchedLedgers = new Set(columnFetches.map((path) => path.match(/\/state\/(?:compact|raw)\/([^/]+)\//)?.[1]).filter(Boolean));
	for (const ledger of JOIN_LEDGERS) expect(fetchedLedgers.has(ledger)).toBe(true);

	const runResponses = new Map<string, Promise<number>>();
	page.on('response', (response) => {
		const url = response.url();
		const pathname = new URL(url).pathname;
		if (!pathname.includes('/state/') || !pathname.endsWith('.parquet')) return;
		runResponses.set(url, response.body().then((body) => body.byteLength).catch(() => 0));
	});
	await runExplorer(page);
	const expected = await expectedAsk(page, {
		ledgers: JOIN_LEDGERS,
		from: JOIN_FROM,
		to: EXPLORER_CANARY_DAY,
		sql: JOIN_SQL,
		maxChars: 5790,
		maxRows: 1000,
		maxFetchBytes: 64 * 1024 * 1024
	});
	expect(expected).toMatchObject({ state: 'ok' });
	if (expected.state !== 'ok') return;
	expect(await tableRows(page)).toEqual(expected.rows.map((row) => expected.columns.map((column) => String(row[column.name] ?? 'null'))));
	const line = page.locator('[data-explorer-action-line]');
	expect(Number(await line.getAttribute('data-files'))).toBeGreaterThan(0);
	expect(Number(await line.getAttribute('data-bytes'))).toBeGreaterThan(0);
	expect(Number(await line.getAttribute('data-bytes'))).toBe((await Promise.all([...runResponses.values()])).reduce((sum, bytes) => sum + bytes, 0));
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

test('THE ORACLE: every Data explorer answer state renders distinct words, tint and action', async ({ page, browser }) => {
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
	await page.getByLabel('From (UTC)').fill(EXPLORER_CANARY_DAY);
	await page.getByLabel('To (UTC)').fill(EXPLORER_CANARY_DAY);
	await chooseOnly(page, ['published'], 'SELECT count(*) AS rows FROM "published"');
	await runExplorer(page);
	const line = page.locator('[data-explorer-action-line]');
	const held = Number(await line.getAttribute('data-held-bytes'));
	await page.locator('#explorer-sql').fill('SELECT 1; SELECT 2');
	await runExplorer(page);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-state="refused"]')).toBeVisible();
	await expect.poll(async () => Number(await line.getAttribute('data-held-bytes'))).toBe(held);
});

test('THE ORACLE: Data explorer does not scroll sideways at phone width', async ({ page }) => {
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
	await expect(page.locator('[data-explorer-action-line]')).not.toContainText('Answered in');
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-idle]')).toContainText('Press Run');
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-explorer-idle]')).toContainText('If the answer holds a number');
	await expect(page.locator('[data-explorer-columns]')).toContainText('published.');
	expect(fetched.every((path) => dataLedger(path) === 'published' && dataPathCoversDay(path, EXPLORER_CANARY_DAY)), 'a shared link fetched a span file before Run').toBe(true);
	const beforeType = page.url();
	await page.locator('#explorer-sql').fill(`${sql} `);
	expect(page.url()).toBe(beforeType);
	await runExplorer(page);
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(1);
	expect(page.url()).not.toBe(beforeType);
});

test('THE ORACLE: link notices render on the page', async ({ page }) => {
	await page.clock.setFixedTime(`${EXPLORER_CANARY_DAY}T12:00:00Z`);
	await page.goto('/console/data-explorer/?ledgers=published,unknown-ledger&days=365&q=not-valid-***', { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-explorer-action-line]')).toContainText('The link named "unknown-ledger"');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('The link asked for 365 days');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('The question in this link could not be read');
});

test('THE ORACLE: every chart case draws its type with a populated readout', async ({ page }) => {
	await openExplorer(page);
	const panel = page.locator('[data-console-panel-id="data-explorer-shape"]');
	// Each main figure is worded by plan section 2.11 rule 7 from the answer's own rows, so a
	// figure that does not come from the data - a constant, a row count, the wrong column - fails.
	const cases = [
		{ type: 'dateSeries', lede: '8 rows on 2026-08-20', sql: "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)" },
		{ type: 'rankedList', lede: 'a: 9 rows', sql: "SELECT * FROM (VALUES ('a', 9), ('b', 4), ('c', 2)) AS t(name, rows)" },
		{ type: 'pairedScatter', lede: '170 rows of y against x', sql: "SELECT 'row-' || i::VARCHAR AS name, i AS x, 170 - i AS y FROM range(0, 170) AS t(i)" },
		{ type: 'distribution', lede: 'Half of rows is at or under 84.5', sql: 'SELECT * FROM range(0, 170) AS t(rows)' }
	] as const;
	for (const { type, lede, sql } of cases) {
		await chooseExplorerQuestion(page, ['published'], sql);
		await runExplorer(page);
		if (await page.locator(`[data-shape-choice="${type}"] input`).count()) {
			await page.locator(`[data-shape-choice="${type}"] input`).check();
		}
		await expect(panel.locator(`[data-chart-type="${type}"]`)).toHaveCount(1);
		await expect(panel.locator('[data-readout] [data-readout-row]').first()).toBeVisible();
		await expect(panel.locator('[data-lede]'), `${type} main figure`).toHaveText(lede);
		await expect(panel.locator('[data-comparison]')).toContainText('against');
		await expect(panel.locator('[title], title')).toHaveCount(0);
	}

	await chooseExplorerQuestion(page, ['published'], 'SELECT item_id FROM "published" LIMIT 1');
	await runExplorer(page);
	const none = panel.locator('[data-shape-none]');
	await expect(none).toContainText('Nothing here to draw');
	const height = await none.boundingBox().then((box) => box?.height ?? 0);
	expect(height, 'the no-chart sentence did not keep the chart room').toBeGreaterThanOrEqual(consoleConfig().chart_height);
});

test('THE ORACLE: Save, recent runs and Markdown copy preserve text without running a saved question', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await openExplorer(page);
	const sql = "SELECT 'header' AS label, '[x](https://example.invalid/a)|pipe\n`tick`' AS hostile FROM \"published\" LIMIT 1";
	await chooseExplorerQuestion(page, ['published'], sql);
	const beforeSave = page.url();
	await page.getByRole('button', { name: /^Save$/ }).click();
	await page.getByLabel('Name').fill('Hostile copy');
	await page.getByRole('button', { name: /^Keep$/ }).click();
	await expect(page.locator('.saved-chip .example').filter({ hasText: 'Hostile copy' })).toHaveCount(1);
	expect(page.url()).not.toBe(beforeSave);
	const beforeSavedPick = await page.locator('[data-explorer-action-line]').getAttribute('data-files');
	await page.locator('.saved-chip .example').filter({ hasText: 'Hostile copy' }).click();
	await expect(page.locator('#explorer-sql')).toHaveValue(sql);
	await expect(page.locator('[data-explorer-action-line]')).toHaveAttribute('data-files', beforeSavedPick ?? '');

	await runExplorer(page);
	await page.getByRole('button', { name: /^Copy as table$/ }).click();
	await expect(page.locator('.copy-answer')).toContainText('Copied 1 row as a table.');
	const copied = await page.evaluate(() => navigator.clipboard.readText());
	expect(copied).toContain('`label`');
	expect(copied).toContain('``[x](https://example.invalid/a)\\|pipe `tick```');
	expect(copied.split('\n')).toHaveLength(3);
	await expect(page.locator('[data-explorer-answer] a, [data-explorer-answer] img')).toHaveCount(0);

	await page.locator('.history-list summary').click();
	await expect(page.locator('.history-list button')).toContainText('1 row');
	await page.locator('.history-list button').first().click();
	await expect(page.locator('#explorer-sql')).toHaveValue(sql);
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(1);
});

test('THE ORACLE: browser storage is parsed against closed lists and saved overflow names the drop', async ({ page }) => {
	const bad = [
		{ id: 'bad-ledger', name: 'Bad ledger', statement: 'SELECT 1', ledgers: ['unknown-ledger'], days: 14, updatedAt: '2026-10-04T00:00:00Z' },
		{ id: 'bad-days', name: 'Bad days', statement: 'SELECT 1', ledgers: ['published'], days: 365, updatedAt: '2026-10-04T00:00:00Z' },
		{ id: 'bad-statement', name: 'Bad statement', statement: 1, ledgers: ['published'], days: 14, updatedAt: '2026-10-04T00:00:00Z' }
	];
	await page.addInitScript((entries) => {
		localStorage.setItem('yen-idhazh:data-explorer:saved', JSON.stringify(entries));
		localStorage.setItem('yen-idhazh:data-explorer:history', JSON.stringify(entries.map((entry) => ({ ...entry, rows: 1, ms: 1, askedAt: '2026-10-04T00:00:00Z' }))));
	}, bad);
	const logs: string[] = [];
	page.on('console', (message) => logs.push(message.text()));
	await openExplorer(page);
	await expect(page.locator('.saved-chip')).toHaveCount(0);
	await page.locator('.history-list summary').click();
	await expect(page.locator('.history-list button')).toHaveCount(0);
	expect(logs.filter((line) => line.includes('Data explorer storage')).length).toBeGreaterThanOrEqual(3);

	for (let index = 0; index < 21; index += 1) {
		await page.locator('#explorer-sql').fill(`SELECT ${index}`);
		await page.getByRole('button', { name: /^Save$/ }).click();
		await page.getByLabel('Name').fill(`Saved ${index}`);
		await page.getByRole('button', { name: /^Keep$/ }).click();
	}
	await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toContainText('Saved "Saved 20". "Saved 0" was the oldest of 20 and is no longer kept.');
	await expect(page.locator('.saved-chip .example')).toHaveCount(20);
});
