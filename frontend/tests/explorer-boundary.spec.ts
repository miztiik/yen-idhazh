import { expect, type BrowserContext, type Page } from './support/browser';
import { test } from './support/browser';
import { copyFileSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';
import svelteConfig from '../svelte.config.js';
import { engineExtensionRepository, ledgerArchiveBaseUrl } from '../src/lib/server/config';
import { chooseExplorerQuestion, runExplorer, tableRows } from './support/explorer-answer';
import { buildLedger, everyDay, serveToPage } from './support/ledger-lifecycle';
import { addonCache, startRangeHost } from './support/range-host';

const here = path.dirname(fileURLToPath(import.meta.url));
const source = path.join(here, 'support', 'explorer-page');
const work = path.resolve(here, '..', 'test-results', 'explorer-boundary');
const pageSource = path.join(work, 'source');
const pageBuild = path.join(work, 'page');

const META_FORBIDDEN = new Set(['frame-ancestors', 'sandbox', 'report-uri']);
const KEYWORDS = new Set(['self', 'none', 'unsafe-inline', 'unsafe-eval', 'wasm-unsafe-eval', 'strict-dynamic']);

function cspValue(value: string): string {
	if (KEYWORDS.has(value) || /^sha(256|384|512)-/.test(value)) return `'${value}'`;
	return value;
}

function cspMeta(): string {
	const directives = svelteConfig.kit.csp.directives as Record<string, string[]>;
	return Object.entries(directives)
		.filter(([name]) => !META_FORBIDDEN.has(name))
		.map(([name, values]) => `${name} ${values.map(cspValue).join(' ')}`)
		.join('; ');
}

async function buildPage(): Promise<void> {
	mkdirSync(pageSource, { recursive: true });
	copyFileSync(path.join(source, 'explorer.ts'), path.join(pageSource, 'explorer.ts'));
	copyFileSync(path.join(source, 'paths.ts'), path.join(pageSource, 'paths.ts'));
	writeFileSync(
		path.join(pageSource, 'index.html'),
		`<!doctype html>\n<html>\n\t<head>\n\t\t<meta charset="utf-8" />\n\t\t<meta http-equiv="content-security-policy" content="${cspMeta().replaceAll('"', '&quot;')}" />\n\t\t<title>Explorer boundary</title>\n\t</head>\n\t<body>\n\t\t<script type="module" src="/explorer.ts"></script>\n\t</body>\n</html>\n`
	);
	await build({
		configFile: false,
		root: pageSource,
		base: '/',
		logLevel: 'warn',
		resolve: { alias: { '$app/paths': path.join(pageSource, 'paths.ts') } },
		define: {
			__ASSET_BASE_URL__: JSON.stringify('/root'),
			__RAW_LISTED_THROUGH__: JSON.stringify({})
		},
		build: { outDir: pageBuild, emptyOutDir: true, target: 'es2022', assetsInlineLimit: 0, reportCompressedSize: false }
	});
}

type RequestRecord = { url: string; failed: string | null; responded: boolean };

function watchExternal(context: BrowserContext): RequestRecord[] {
	const external: RequestRecord[] = [];
	context.on('request', (request) => {
		if (request.url().includes('example.invalid')) external.push({ url: request.url(), failed: null, responded: false });
	});
	context.on('requestfailed', (request) => {
		const found = external.find((entry) => entry.url === request.url() && entry.failed === null);
		if (found) found.failed = request.failure()?.errorText ?? null;
	});
	context.on('response', (response) => {
		const found = external.find((entry) => entry.url === response.url());
		if (found) found.responded = true;
	});
	return external;
}

type Attached = { sessionId: string; targetInfo: { type: string } };
type TargetMessage = { sessionId: string; message: string };

async function watchWorkerLog(page: Page, context: BrowserContext): Promise<string[]> {
	const session = await context.newCDPSession(page);
	const workerSessions = new Set<string>();
	const lines: string[] = [];
	session.on('Target.attachedToTarget', (event: Attached) => {
		if (event.targetInfo.type !== 'worker') return;
		workerSessions.add(event.sessionId);
		void session.send('Target.sendMessageToTarget', {
			sessionId: event.sessionId,
			message: JSON.stringify({ id: 1, method: 'Log.enable' })
		});
		void session.send('Target.sendMessageToTarget', {
			sessionId: event.sessionId,
			message: JSON.stringify({ id: 2, method: 'Network.enable' })
		});
	});
	session.on('Target.receivedMessageFromTarget', (event: TargetMessage) => {
		if (!workerSessions.has(event.sessionId)) return;
		const message = JSON.parse(event.message) as { method?: string; params?: { entry?: { text?: string } } };
		if (message.method === 'Log.entryAdded' && message.params?.entry?.text) lines.push(message.params.entry.text);
	});
	await session.send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: false, flatten: false });
	return lines;
}

test.describe('explorer boundary', () => {
	test.describe.configure({ mode: 'serial' });

	test.beforeAll(async () => {
		rmSync(work, { recursive: true, force: true });
		await buildPage();
	});

	test('the browser content policy refuses a statement fetch to an unlisted origin', async ({ page, context }) => {
		// The page reads host-fingerprint as this test builds it: one row on 15 Jun 2030, the day the statement asks for.
		const root = test.info().outputPath('state');
		await buildLedger(root, { ledger: 'host-fingerprint', pinned: '2030-06-15', days: everyDay(0, 0) });
		const host = await startRangeHost({ site: pageBuild, plain: { ext: addonCache(engineExtensionRepository()) }, data: { root: { dir: root } }, maxAge: 600 });
		try {
			// Playwright forwards console API calls from workers, but not worker log entries such as content-policy refusals.
			const workerLog = await watchWorkerLog(page, context);
			const external = watchExternal(context);
			await page.goto(`${host.origin}/`);
			await page.waitForFunction(() => window.explorerAsk !== undefined);
			const answer = await page.evaluate(() => window.explorerAsk({
				ledgers: ['host-fingerprint'],
				from: '2030-06-15',
				to: '2030-06-15',
				sql: "SELECT * FROM read_csv('https://example.invalid/x.csv')",
				maxChars: 500,
				maxRows: 10,
				maxFetchBytes: 100000000
			}));
			expect(answer).toMatchObject({ state: 'refused', because: { kind: 'engine-error' } });
			await expect.poll(() => workerLog.join('\n')).toContain('connect-src');
			const text = workerLog.join('\n');
			expect(text).toContain('https://example.invalid/x.csv');
			expect(external.length).toBeGreaterThan(0);
			expect(external.every((request) => request.failed === 'csp')).toBe(true);
			expect(external.every((request) => !request.responded)).toBe(true);
		} finally {
			await host.close();
		}
	});
});

test('days before a ledger began are cut from the selected window, the page names that day, and the archive host gets no request', async ({ page, context }) => {
	// The page reads host-fingerprint as a ledger this test builds: it began on 10 Jun 2030, five
	// days before the day the test pins, and the test selects 2 to 15 Jun.
	const ledger = 'host-fingerprint';
	const root = test.info().outputPath('state');
	await buildLedger(root, { ledger, pinned: '2030-06-15', days: everyDay(5, 0) });
	await serveToPage(context, root, ledger);
	const archive = ledgerArchiveBaseUrl();
	expect(archive, 'the shipped config names an archive, so the page has one it could ask').not.toBe('');
	const archiveAsked: string[] = [];
	context.on('request', (request) => {
		if (request.url().startsWith(`${archive}/`)) archiveAsked.push(request.url());
	});

	await page.clock.setFixedTime('2030-06-15T12:00:00Z');
	await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	await chooseExplorerQuestion(page, [ledger], `SELECT min("covers") AS first_day FROM "${ledger}"`);
	await page.getByRole('textbox', { name: 'From (UTC)' }).fill('2030-06-02');
	await runExplorer(page);
	const panel = page.locator('[data-console-panel-id="data-explorer-rows"]');
	await expect(panel.locator('.answer-note')).toContainText('Days before 10 Jun 2030 are not on this site.');
	await expect(panel.locator('.warn')).toHaveCount(0);
	expect(await tableRows(page)).toEqual([['2030-06-10']]);
	expect(archiveAsked).toEqual([]);
});
