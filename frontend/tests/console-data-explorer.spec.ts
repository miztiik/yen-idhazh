
import { readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { connectSources, assetBaseUrl, encoderOrigins, engineOrigins, archiveOrigins } from '../asset-base.js';
import { publishedWindowDays } from '../scripts/published-ledgers.mjs';
import { daysBetween } from '../src/lib/data/slice';
import { expect, test, type Page } from './support/browser';
import { chooseExplorerQuestion, expectAnswer, openExplorer, runExplorer, serveBuilt, tableRows } from './support/explorer-answer';
import { buildLedger, everyDay, quietDays, serveArchiveToPage, serveToPage, siteCopy } from './support/ledger-lifecycle';
import { encodeQuestion, explorerAddress, requestTargetBytes } from '../src/lib/console/explorer/address';
import { consoleConfig, explorerConfig, ledgerArchiveBaseUrl } from '../src/lib/server/config';
import type { LedgerName } from '../src/lib/data/ledger';
import { CONSOLE_CHROMES, consoleChromeOf } from '../src/lib/console/chrome';

/** The UTC day every test here pins as the page's today. A built ledger's days count back from it. */
const PINNED = '2030-06-15';
const JOIN_LEDGERS = ['published', 'item-health'] as const satisfies readonly LedgerName[];
const JOIN_SQL = 'SELECT \'published x item-health\' AS pair, CAST(count(*) AS VARCHAR) AS rows FROM "published" p, "item-health" h';

function addDays(day: string, delta: number): string {
	const date = new Date(`${day}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() + delta);
	return date.toISOString().slice(0, 10);
}

/** The path under `state/` a request named, or null for a request outside a state tree. */
function stateFile(url: string): string | null {
	const pathname = new URL(url).pathname;
	const at = pathname.indexOf('/state/');
	return at === -1 ? null : pathname.slice(at + '/state/'.length);
}

/** Every data file this page fetches from now on, by its path under `state/`, in arrival order. */
function fetchedFiles(page: Page): string[] {
	const fetched: string[] = [];
	page.on('response', (response) => {
		const file = stateFile(response.url());
		if (file?.endsWith('.parquet')) fetched.push(file);
	});
	return fetched;
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
	await expect(page.locator('[data-explorer-action-line]')).not.toContainText('This page holds');
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

test('THE ORACLE: Data explorer puts the span, dates and Run in the editor head', async ({ page }) => {
	await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-workbench-region="toolbar"]')).toHaveCount(0);
	const head = page.locator('[data-workbench-region="editor"] .editor-head');
	await expect(page.locator('[data-window-control]')).toHaveCount(1);
	await expect(head.locator('[data-window-control]')).toHaveCount(1);
	await expect(head.getByRole('textbox', { name: 'From (UTC)' })).toHaveCount(1);
	await expect(head.getByRole('textbox', { name: 'To (UTC)' })).toHaveCount(1);
	await expect(head.getByRole('button', { name: /^Run$/ })).toHaveCount(1);
});

test('THE ORACLE: the column rail always names the selected ledger\'s own columns', async ({ page, context }) => {
	// A built ledger's files hold three columns: covers, date and n.
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'host-fingerprint', pinned: PINNED, days: everyDay(2, 0) });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['host-fingerprint'], 'SELECT * FROM "host-fingerprint"');
	const rail = page.locator('[data-explorer-columns] li code');
	const before = await page.locator('[data-explorer-columns]').innerText();
	await expect(rail).toHaveText(['host-fingerprint.covers', 'host-fingerprint.date', 'host-fingerprint.n']);
	await runExplorer(page);
	await expectAnswer(page, 'table');
	await expect(page.locator('[data-explorer-columns] h3')).toHaveText('Ledger columns');
	await expect(rail).toHaveText(['host-fingerprint.covers', 'host-fingerprint.date', 'host-fingerprint.n']);
	expect(await page.locator('[data-explorer-columns]').innerText()).toBe(before);
});

test('THE ORACLE: the Data explorer fallback document carries the shipped content policy', () => {
	const html = readFileSync(resolve(process.cwd(), 'build', '404.html'), 'utf8');
	expect(html).toContain('content-security-policy');
	const expected = `connect-src ${connectSources(assetBaseUrl(), [...encoderOrigins(), ...engineOrigins(), ...archiveOrigins()]).map((source) => source === 'self' ? "'self'" : source).join(' ')}`;
	expect(html).toContain(expected);
	expect(html).toContain('extensions.duckdb.org');
});

test('THE ORACLE: custom date inputs expose reach bounds and presets end today', async ({ page }) => {
	await openExplorer(page, PINNED);
	const from = page.getByRole('textbox', { name: 'From (UTC)' });
	const to = page.getByRole('textbox', { name: 'To (UTC)' });
	expect(await to.getAttribute('max'), 'the page does not take the pinned day as today').toBe(PINNED);
	expect(await from.getAttribute('min')).toBe(addDays(PINNED, 1 - explorerConfig().reach_days));
	expect(await from.getAttribute('max')).toBe(PINNED);
	expect(await to.getAttribute('min')).toBe(await from.inputValue());

	await page.locator('[data-window-preset="30"]').click();
	await expect(to).toHaveValue(PINNED);
	await expect(from).toHaveValue(addDays(PINNED, -29));

	await from.fill(PINNED);
	await expect(to).toHaveAttribute('min', PINNED);
	await to.fill(addDays(PINNED, -10));
	await expect(to).toHaveValue(PINNED);
});

test('THE ORACLE: with no archive prefix, an old custom span reads from the site\'s oldest day and says so', async ({ page, context }) => {
	// published is built to begin 10 days before the pinned day, on 5 Jun 2030, with one row a day.
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(10, 0) });
	await page.addInitScript(() => {
		Object.defineProperty(globalThis, '__ARCHIVE_BASE_URL__', { value: '', configurable: true });
	});
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], 'SELECT min("covers") AS first_day, count(*) AS rows FROM "published"');
	// 365 UTC days that end on the pinned day.
	await page.getByRole('textbox', { name: 'From (UTC)' }).fill('2029-06-16');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	const panel = page.locator('[data-console-panel-id="data-explorer-rows"]');
	await expect(panel.locator('.answer-note')).toContainText('Days before 5 Jun 2030 are not on this site.');
	await expect(panel.locator('.warn')).toHaveCount(0);
	expect(await tableRows(page)).toEqual([['2030-06-05', '11']]);
});

test('THE ORACLE: the 14-day preset cuts a ledger that began 5 days ago at its first day, and reads only the last 14 days of one that began 4 years ago, asking the archive nothing', async ({ page, context }) => {
	// host-fingerprint begins 5 days before the pinned day. seen begins 1,461 days, four years,
	// before it, with every month before May 2030 closed, and its site copy is trimmed by the site
	// build's own rule, so the archive holds its older days. The archive host serves the whole of
	// both ledgers, as this test built them.
	const archiveRoot = test.info().outputPath('archive');
	const siteRoot = test.info().outputPath('site');
	await buildLedger(archiveRoot, { ledger: 'host-fingerprint', pinned: PINNED, days: everyDay(5, 0) });
	const closedMonths = [...new Set(daysBetween('2026-06-15', '2030-04-30').map((day) => day.slice(0, 7)))];
	await buildLedger(archiveRoot, { ledger: 'seen', pinned: PINNED, days: everyDay(1461, 0), closedMonths });
	for (const ledger of ['host-fingerprint', 'seen'] as const) {
		siteCopy(archiveRoot, siteRoot, ledger, publishedWindowDays());
		await serveToPage(context, siteRoot, ledger);
	}
	await serveArchiveToPage(context, archiveRoot);
	const archive = ledgerArchiveBaseUrl();
	const archiveAsked: string[] = [];
	context.on('request', (request) => {
		if (request.url().startsWith(`${archive}/`)) archiveAsked.push(request.url());
	});
	const note = page.locator('[data-console-panel-id="data-explorer-rows"] .answer-note');

	await openExplorer(page, PINNED);
	await page.locator('[data-window-preset="14"]').click();
	await chooseExplorerQuestion(page, ['host-fingerprint'], 'SELECT min("covers") AS first_day, count(*) AS rows FROM "host-fingerprint"');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['2030-06-10', '6']]);
	await expect(note).toContainText('Days before 10 Jun 2030 are not on this site.');

	const fetched = fetchedFiles(page);
	await chooseExplorerQuestion(page, ['seen'], 'SELECT min("covers") AS first_day, count(*) AS rows FROM "seen"');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['2030-06-02', '14']]);
	await expect(note).not.toContainText('are not on this site');
	expect(fetched.sort()).toEqual(daysBetween('2030-06-02', PINNED).map((day) => `compact/seen/daily/${day.replaceAll('-', '/')}.parquet`));
	expect(archiveAsked).toEqual([]);
});

test('THE ORACLE: a typed join counts the rows of two built ledgers, fetches only their files in the span, and the run cost matches the network', async ({ page, context }) => {
	// In the 14 days that end on the pinned day, published holds 3 rows and item-health 2, so the
	// join holds 6. Each also holds one row on a day before those 14.
	await serveBuilt(context, test.info().outputPath('state'),
		{ ledger: 'published', pinned: PINNED, days: [{ ago: 20, rows: 1 }, ...quietDays(19, 3), ...everyDay(2, 0)] },
		{ ledger: 'item-health', pinned: PINNED, days: [{ ago: 30, rows: 1 }, ...quietDays(29, 6), { ago: 5, rows: 2 }] });
	await openExplorer(page, PINNED);
	const fetched = fetchedFiles(page);
	await chooseExplorerQuestion(page, JOIN_LEDGERS, JOIN_SQL);

	const runResponses = new Map<string, Promise<number>>();
	page.on('response', (response) => {
		if (!stateFile(response.url())?.endsWith('.parquet')) return;
		runResponses.set(response.url(), response.body().then((body) => body.byteLength).catch(() => 0));
	});
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['published x item-health', '6']]);
	expect(fetched.sort()).toEqual([
		'compact/item-health/daily/2030/06/10.parquet',
		'compact/published/daily/2030/06/13.parquet',
		'compact/published/daily/2030/06/14.parquet',
		'compact/published/daily/2030/06/15.parquet'
	]);
	// Choosing the ledgers read each one's newest day, so the run fetched the other two.
	const line = page.locator('[data-explorer-action-line]');
	await expect(line).toHaveAttribute('data-files', '2');
	expect(Number(await line.getAttribute('data-bytes'))).toBe((await Promise.all([...runResponses.values()])).reduce((sum, bytes) => sum + bytes, 0));
});

test('THE ORACLE: choosing ledgers fetches one through day for each chosen ledger and no other data file', async ({ page, context }) => {
	// published's newest day is the pinned day, and item-health's is two days before it.
	await serveBuilt(context, test.info().outputPath('state'),
		{ ledger: 'published', pinned: PINNED, days: everyDay(3, 0) },
		{ ledger: 'item-health', pinned: PINNED, days: everyDay(4, 2) });
	await openExplorer(page, PINNED);
	const fetched = fetchedFiles(page);
	await chooseExplorerQuestion(page, JOIN_LEDGERS, JOIN_SQL);
	expect(fetched.sort()).toEqual([
		'compact/item-health/daily/2030/06/13.parquet',
		'compact/published/daily/2030/06/15.parquet'
	]);
});

test('THE ORACLE: every Data explorer answer state renders distinct words, tint and action', async ({ page, browser, context }) => {
	const seen = new Map<string, { text: string; tone: string; button: string }>();
	const remember = (name: string, snap: { text: string; tone: string; button: string }) => {
		const key = JSON.stringify(snap);
		expect([...seen.entries()].find(([, value]) => JSON.stringify(value) === key)?.[0], `${name} duplicates another state`).toBeUndefined();
		seen.set(name, snap);
	};
	const answer = (one: Page) => one.locator('[data-console-panel-id="data-explorer-rows"]');

	// Each state comes from a ledger built for it: published holds the two days before the pinned
	// day, candidate-models names no day at all, counterfactual-scores holds the pinned day, seen
	// leaves out 13 Jun, two days before the pinned day, and feed-health, which this site does not
	// publish, has no folder.
	const root = test.info().outputPath('state');
	await serveBuilt(context, root,
		{ ledger: 'published', pinned: PINNED, days: everyDay(1, 0) },
		{ ledger: 'candidate-models', pinned: PINNED, days: [] },
		{ ledger: 'counterfactual-scores', pinned: PINNED, days: everyDay(0, 0) },
		{ ledger: 'seen', pinned: PINNED, days: [...everyDay(3, 3), ...everyDay(1, 0)] });
	await serveToPage(context, root, 'feed-health');

	remember('idle', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await expect(answer(one).locator('[data-explorer-idle]')).toBeVisible();
	}));

	const engineContext = await browser.newContext({ serviceWorkers: 'block' });
	try {
		await serveToPage(engineContext, root, 'published');
		const one = await engineContext.newPage();
		await one.route(/duckdb.*(?:wasm|worker).*$/, (route) => route.abort());
		await openExplorer(one, PINNED, { ready: false });
		await chooseOnly(one, ['published'], 'SELECT count(*) AS rows FROM "published"');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="unreachable"]')).toBeVisible();
		remember('engine did not start', await answerSnapshot(one));
	} finally {
		await engineContext.close();
	}

	// The run fetches 14 Jun, the day choosing the ledger did not read. That fetch waits until the
	// picture is taken and is then refused, so it never leaves the page.
	const loading = await context.newPage();
	try {
		await openExplorer(loading, PINNED);
		await chooseExplorerQuestion(loading, ['published'], 'SELECT count(*) AS rows FROM "published"');
		let release!: () => void;
		const held = new Promise<void>((resolve) => { release = resolve; });
		await loading.route('**/state/**/*.parquet*', async (route) => {
			await held;
			await route.abort();
		}, { times: 1 });
		await loading.getByRole('button', { name: /^Run$/ }).click();
		await expect(answer(loading).locator('[data-state="loading"]')).toBeVisible();
		remember('loading', await answerSnapshot(loading));
		release();
	} finally {
		await loading.close();
	}

	remember('quiet', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await chooseExplorerQuestion(one, ['published'], 'SELECT * FROM "published" WHERE false');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="quiet"]')).toBeVisible();
	}));

	remember('missing not published', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await chooseOnly(one, ['feed-health'], 'SELECT count(*) AS rows FROM "feed-health"');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="missing"]')).toContainText('feed-health');
	}));

	remember('missing no days yet', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await chooseOnly(one, ['candidate-models'], 'SELECT count(*) AS rows FROM "candidate-models"');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="missing"]')).toContainText('candidate-models');
	}));

	remember('unreachable file did not arrive', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await one.route('**/state/**/*.parquet*', (route) => route.abort());
		await chooseOnly(one, ['counterfactual-scores'], 'SELECT count(*) AS rows FROM "counterfactual-scores"');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="unreachable"]')).toContainText('counterfactual-scores for 2030-06-15');
	}));

	remember('unreachable gap', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await chooseOnly(one, ['seen'], 'SELECT count(*) AS rows FROM "seen"');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="unreachable"]')).toContainText('seen for 2030-06-13');
	}));

	remember('refused', await statePage(page, async (one) => {
		await openExplorer(one, PINNED);
		await chooseExplorerQuestion(one, ['published'], 'SELECT 1; SELECT 2');
		await runExplorer(one);
		await expect(answer(one).locator('[data-state="refused"]')).toBeVisible();
	}));

	expect(seen.size).toBe(9);
});

test('THE ORACLE: a refused run after a fetch does not show held-byte text', async ({ page, context }) => {
	// The page is opened on published alone, built with one day, so the one file it holds is that day's.
	const root = test.info().outputPath('state');
	await serveBuilt(context, root, { ledger: 'published', pinned: PINNED, days: [{ ago: 0, rows: 3 }] });
	const size = String(statSync(join(root, 'compact', 'published', 'daily', '2030', '06', '15.parquet')).size);
	// The link names no question, so Run waits for one to be written before it is ready.
	await openExplorer(page, PINNED, { address: `?ledgers=published&from=${PINNED}&end=${PINNED}`, ready: false });
	await page.locator('#explorer-sql').fill('SELECT count(*) AS rows FROM "published"');
	await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['3']]);
	const line = page.locator('[data-explorer-action-line]');
	await expect(line).not.toHaveAttribute('data-held-bytes');
	await page.locator('#explorer-sql').fill('SELECT 1; SELECT 2');
	await runExplorer(page);
	await expectAnswer(page, 'refused');
	await expect(line).not.toContainText('This page holds');
	await expect(line).not.toHaveAttribute('data-held-bytes');
});

test('THE ORACLE: Data explorer does not scroll sideways at phone width', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 900 });
	await openExplorer(page, PINNED);
	const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
	expect(width.scroll).toBeLessThanOrEqual(width.client);
});

test('THE ORACLE: the browser refuses an origin outside connect-src', async ({ page }) => {
	await openExplorer(page, PINNED);
	const violated = page.evaluate(() => new Promise<string>((resolve) => {
		document.addEventListener('securitypolicyviolation', (event) => resolve(event.violatedDirective), { once: true });
		void fetch('https://example.invalid/x').catch(() => undefined);
	}));
	await expect(violated).resolves.toContain('connect-src');
});


test('THE ORACLE: hostile cell text stays plain in the real table', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], 'SELECT \'<script>alert(1)</script> https://example.invalid/x\' AS hostile FROM "published" LIMIT 1');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	const table = page.locator('[data-explorer-answer]');
	await expect(table).toContainText('<script>alert(1)</script> https://example.invalid/x');
	await expect(table.locator('a, script, img')).toHaveCount(0);
});

test('THE ORACLE: a shared address fills the editor and does not run itself', async ({ page, context }) => {
	// published is built with 1, 2 and 3 rows on the three days that end on the pinned day.
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: [{ ago: 2, rows: 1 }, { ago: 1, rows: 2 }, { ago: 0, rows: 3 }] });
	const sql = 'SELECT "covers", count(*) AS rows FROM "published" GROUP BY 1 ORDER BY 1';
	const q = await encodeQuestion(sql);
	const fetched = fetchedFiles(page);
	await openExplorer(page, PINNED, { address: `?ledgers=published&days=14&q=${q}` });
	await expect(page.locator('#explorer-sql')).toHaveValue(sql);
	await expect(page.locator('[data-explorer-action-line]')).toContainText('This question came from a link');
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(0);
	await expect(page.locator('[data-explorer-action-line]')).not.toContainText('Answered in');
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-idle]')).toContainText('Press Run');
	await expect(page.locator('[data-console-panel-id="data-explorer-shape"] [data-explorer-idle]')).toContainText('If the answer holds a number');
	await expect(page.locator('[data-explorer-columns]')).toContainText('published.');
	expect(fetched, 'a shared link fetched more than the newest day before Run').toEqual(['compact/published/daily/2030/06/15.parquet']);
	const beforeType = page.url();
	await page.locator('#explorer-sql').fill(`${sql} `);
	expect(page.url()).toBe(beforeType);
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['2030-06-13', '1'], ['2030-06-14', '2'], ['2030-06-15', '3']]);
	expect(page.url()).not.toBe(beforeType);
});

test('THE ORACLE: link notices render on the page', async ({ page }) => {
	await page.clock.setFixedTime(`${PINNED}T12:00:00Z`);
	await page.goto('/console/data-explorer/?ledgers=published,unknown-ledger&days=365&q=not-valid-***', { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-explorer-action-line]')).toContainText('The link named "unknown-ledger"');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('The link asked for 365 days');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('The question in this link could not be read');
});

/** A question of `count` scattered CJK characters. They deflate poorly, so its link grows with every one. */
function scattered(count: number): string {
	let state = 7;
	let out = '';
	for (let index = 0; index < count; index += 1) {
		state = (1664525 * state + 1013904223) >>> 0;
		out += String.fromCharCode(0x4e00 + ((state >>> 8) % 0x5000));
	}
	return out;
}

test('THE ORACLE: Copy link carries the question while the link fits console.explorer_link_max_bytes, and leaves it out one character past', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	const limit = explorerConfig().link_max_bytes;
	expect(limit, 'console.explorer_link_max_bytes does not reach the page').toBeGreaterThan(0);
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], 'SELECT 1 AS one');
	const copyLink = page.getByRole('button', { name: /^Copy link$/ });
	await copyLink.click();
	await expect.poll(() => new URL(page.url()).searchParams.has('q')).toBe(true);
	const shared = new URL(page.url());
	const params = shared.searchParams;
	const span = { ledgers: (params.get('ledgers') ?? '').split(',') as LedgerName[], days: Number(params.get('days')), from: params.get('from') ?? undefined, end: params.get('end') ?? undefined };
	// The page's own link writer with no limit, so each question's link is sized as the page sizes it.
	const linkFor = async (statement: string) => (await explorerAddress({ basePath: shared.pathname, ...span, statement })).href;
	expect(await linkFor('SELECT 1 AS one'), 'the test does not write the link the page wrote').toBe(`${shared.pathname}${shared.search}`);
	const bytes = async (statement: string) => requestTargetBytes(await linkFor(statement));
	let fits = 1;
	let over = 5000;
	expect(await bytes(scattered(fits))).toBeLessThanOrEqual(limit);
	expect(await bytes(scattered(over))).toBeGreaterThan(limit);
	while (over - fits > 1) {
		const middle = Math.floor((fits + over) / 2);
		if ((await bytes(scattered(middle))) <= limit) fits = middle;
		else over = middle;
	}

	await page.locator('#explorer-sql').fill(scattered(fits));
	await copyLink.click();
	await expect.poll(() => new URL(page.url()).searchParams.get('q'), 'the page left out a question whose link fits').toBe(await encodeQuestion(scattered(fits)));
	await expect(page.getByRole('button', { name: /^Copy question$/ })).toHaveCount(0);

	await page.locator('#explorer-sql').fill(scattered(over));
	await copyLink.click();
	await expect(page.getByRole('button', { name: /^Copy question$/ })).toBeVisible();
	expect(new URL(page.url()).searchParams.has('q'), 'the page linked a question whose link is too long').toBe(false);
});

test('THE ORACLE: a link naming a day that does not exist shows the span notice, and the page still loads its ledgers', async ({ page }) => {
	const thrown: string[] = [];
	page.on('pageerror', (error) => thrown.push(error.message));
	await page.clock.setFixedTime(`${PINNED}T12:00:00Z`);
	await page.goto(`/console/data-explorer/?ledgers=published&from=2026-08-32&end=${PINNED}`, { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-explorer-action-line]')).toContainText(
		'The link asked for 2026-08-32 to 2030-06-15, which is not a span this page can read, so it ends today.'
	);
	await expect(page.locator('[data-ledger-name="published"] input')).toBeChecked({ timeout: 60_000 });
	expect(thrown).toEqual([]);
});

test('THE ORACLE: a count by day names the day a ledger lost and the files it set aside, and draws no row for the lost day', async ({ page, context }) => {
	// item-health is built to lose 13 Jun 2030 and to set 2 files aside on 14 Jun.
	await serveBuilt(context, test.info().outputPath('state'), {
		ledger: 'item-health',
		pinned: PINNED,
		days: [{ ago: 4, rows: 2 }, { ago: 3, rows: 1 }, { ago: 2, state: 'lost' }, { ago: 1, rows: 3, setAside: 2 }, { ago: 0, rows: 1 }]
	});
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['item-health'], 'SELECT "covers" AS day, count(*) AS rows FROM "item-health" GROUP BY 1 ORDER BY 1');
	await runExplorer(page);
	await expectAnswer(page, 'table');

	const lost = 'There is no item-health record for 13 Jun 2030, so nothing from that day is in this answer. The record for that day was lost and could not be recovered; it was not a quiet day.';
	const note = page.locator('[data-console-panel-id="data-explorer-rows"] .answer-note');
	await expect(note.locator('[data-explorer-gap="lost"][data-ledger="item-health"]')).toHaveText(lost);
	await expect(note.locator('[data-explorer-gap="set-aside"][data-ledger="item-health"]')).toHaveText(
		'2 item-health files were set aside unread when this data was packed, so this answer may be missing their rows. They wait in state/raw/item-health/set-aside/ for a person to read.'
	);
	expect(await tableRows(page)).toEqual([['2030-06-11', '2'], ['2030-06-12', '1'], ['2030-06-14', '3'], ['2030-06-15', '1']]);

	// A span of nothing but the lost day is quiet, and the quiet answer names the day too.
	await page.getByRole('textbox', { name: 'From (UTC)' }).fill('2030-06-13');
	await page.getByRole('textbox', { name: 'To (UTC)' }).fill('2030-06-13');
	await runExplorer(page);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"] [data-state="quiet"] [data-explorer-gap="lost"]')).toHaveText(lost);
});

test('THE ORACLE: a count by day across a lost day breaks its line there, and the strip prints no number for that day', async ({ page, context }) => {
	// item-health is built to lose 14 Jun 2030, the day before the pinned day.
	await serveBuilt(context, test.info().outputPath('state'), {
		ledger: 'item-health',
		pinned: PINNED,
		days: [{ ago: 3, rows: 1 }, { ago: 2, rows: 2 }, { ago: 1, state: 'lost' }, { ago: 0, rows: 3 }]
	});
	await openExplorer(page, PINNED);
	// `covers` is stored as text, so the question casts it: a text day column is ranked, not drawn over time.
	await chooseExplorerQuestion(page, ['item-health'], 'SELECT CAST("covers" AS DATE) AS day, count(*) AS rows FROM "item-health" GROUP BY 1 ORDER BY 1');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page), 'the answer is not the built days with rows').toEqual([['2030-06-12', '1'], ['2030-06-13', '2'], ['2030-06-15', '3']]);

	const panel = page.locator('[data-console-panel-id="data-explorer-shape"]');
	await page.getByRole('tab', { name: 'Chart' }).click();
	const plot = panel.locator('[data-chart-type="dateSeries"]');
	await expect(plot).toHaveCount(1);
	const line = panel.locator('[data-date-series-marks="data-explorer-shape"] path');
	await expect(line).toHaveCount(1);
	expect((await line.getAttribute('d'))?.match(/M/g)?.length, 'the line joined the days either side of the lost day').toBe(2);
	// Three days with rows, and the lost day between them.
	await expect(panel.locator('[data-readout-columns]')).toHaveAttribute('data-readout-columns', '4');

	// The lost day is the column before the newest: step onto it and read the strip.
	await plot.focus();
	await page.keyboard.press('End');
	await page.keyboard.press('ArrowLeft');
	await expect(panel.locator('[data-readout-day]')).toHaveText('2030-06-14');
	await expect(panel.locator('[data-readout-row]')).toHaveText(['No number for this day']);
});

test('THE ORACLE: every chart case draws its type with a populated readout', async ({ page, context }) => {
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await openExplorer(page, PINNED);
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
		await expectAnswer(page, 'table');
		await page.getByRole('tab', { name: 'Chart' }).click();
		if (await page.locator(`[data-shape-choice="${type}"] input`).count()) {
			await page.locator(`[data-shape-choice="${type}"] input`).check();
		}
		await expect(panel.locator(`[data-chart-type="${type}"]`)).toHaveCount(1);
		await expect(panel.locator('[data-readout] [data-readout-row]').first()).toBeVisible();
		await expect(panel.locator('[data-lede]'), `${type} main figure`).toHaveText(lede);
		await expect(panel.locator('[data-comparison]')).toContainText('against');
		await expect(panel.locator('[title], title')).toHaveCount(0);
	}

	await chooseExplorerQuestion(page, ['published'], 'SELECT "covers" FROM "published" LIMIT 1');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	const none = panel.locator('[data-shape-none]');
	await expect(none).toContainText('Nothing here to draw');
	const height = await none.boundingBox().then((box) => box?.height ?? 0);
	expect(height, 'the no-chart sentence did not keep the chart room').toBeGreaterThanOrEqual(consoleConfig().chart_height);
});

test('THE ORACLE: Save, recent runs and Markdown copy preserve text without running a saved question', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await serveBuilt(context, test.info().outputPath('state'), { ledger: 'published', pinned: PINNED, days: everyDay(0, 0) });
	await openExplorer(page, PINNED);
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
	await expectAnswer(page, 'table');
	await page.getByRole('button', { name: /^Copy as table$/ }).click();
	await expect(page.locator('[data-notice]')).toContainText('Copied 1 row as a table.');
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
	await openExplorer(page, PINNED);
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

test('THE ORACLE: a question kept with a day that is not on the calendar is dropped when the page reads browser storage', async ({ page }) => {
	// Written as text, 2026-08-32 sorts inside the reach once August has ended, so the clock stands after it.
	const kept = { id: 'not-a-day', name: 'Not a day', statement: 'SELECT 1', ledgers: ['published'], days: 14, from: '2026-08-32', end: '2026-09-01', updatedAt: '2026-09-01T00:00:00Z' };
	await page.addInitScript((entry) => {
		localStorage.setItem('yen-idhazh:data-explorer:saved', JSON.stringify([entry]));
		localStorage.setItem('yen-idhazh:data-explorer:history', JSON.stringify([{ ...entry, rows: 1, ms: 1, askedAt: '2026-09-01T00:00:00Z' }]));
	}, kept);
	const logs: string[] = [];
	page.on('console', (message) => logs.push(message.text()));
	await page.clock.setFixedTime('2026-09-01T12:00:00Z');
	await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
	await expect(page.locator('.saved-chip')).toHaveCount(0);
	await page.locator('.history-list summary').click();
	await expect(page.locator('.history-list button')).toHaveCount(0);
	expect(logs.filter((line) => line.startsWith('Data explorer storage'))).toEqual([
		'Data explorer storage yen-idhazh:data-explorer:saved entry was invalid and was dropped.',
		'Data explorer storage yen-idhazh:data-explorer:history entry was invalid and was dropped.'
	]);
});
