import { expect, test } from '@playwright/test';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';
import { engineExtensionRepository } from '../src/lib/server/config';
import { startRangeHost, type RangeHost } from './support/range-host';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..', '..');
const fixture = path.join(repo, 'tests', 'fixtures', 'ledger-door', 'state');
const work = path.resolve(here, '..', 'test-results', 'explorer-boundary');
const pageBuild = path.join(work, 'page');

function addonCache(repository: string): string {
	const address = new URL(repository);
	const last = `${address.host}${address.pathname}`.split('/').filter((part) => part !== '').at(-1) ?? address.host;
	return path.join(os.homedir(), '.duckdb', 'extensions', last);
}

async function buildPage(): Promise<void> {
	await build({
		configFile: false,
		root: path.join(here, 'support', 'explorer-page'),
		base: '/',
		logLevel: 'warn',
		resolve: { alias: { '$app/paths': path.join(here, 'support', 'explorer-page', 'paths.ts') } },
		define: {
			__ASSET_BASE_URL__: JSON.stringify(''),
			__ENGINE_EXTENSION_REPOSITORY__: JSON.stringify(engineExtensionRepository()),
			__RAW_LISTED_THROUGH__: JSON.stringify({})
		},
		build: { outDir: pageBuild, emptyOutDir: true, target: 'es2022', assetsInlineLimit: 0, reportCompressedSize: false }
	});
}

test.describe('explorer boundary', () => {
	test.describe.configure({ mode: 'serial' });
	let host: RangeHost;

	test.beforeAll(async () => {
		mkdirSync(path.join(here, 'support', 'explorer-page'), { recursive: true });
		writeFileSync(path.join(here, 'support', 'explorer-page', 'paths.ts'), "export const base = '';\n");
		rmSync(work, { recursive: true, force: true });
		await buildPage();
		host = await startRangeHost({ site: pageBuild, plain: { ext: addonCache(engineExtensionRepository()) }, data: { root: { dir: fixture } }, maxAge: 600 });
	});

	test.afterAll(async () => {
		if (host) writeFileSync(path.join(work, 'requests.json'), JSON.stringify(host.log, null, 1));
		await host?.close();
	});

	test('the browser content policy refuses a statement fetch to an unlisted origin', async ({ page }) => {
		const messages: string[] = [];
		page.on('console', (message) => messages.push(message.text()));
		const external: string[] = [];
		page.on('request', (request) => { if (request.url().includes('example.invalid')) external.push(request.url()); });
		await page.goto(`${host.origin}/`);
		await page.waitForFunction(() => window.explorerAsk !== undefined);
		const answer = await page.evaluate(() => window.explorerAsk({
			ledgers: ['host-fingerprint'],
			from: '2026-09-01',
			to: '2026-09-01',
			sql: "SELECT * FROM read_csv('https://example.invalid/x.csv')",
			maxChars: 500,
			maxRows: 10,
			maxFetchBytes: 100000000
		}));
		await page.waitForTimeout(200);
		expect(answer).toMatchObject({ state: 'refused', because: { kind: 'engine-error' } });
		expect(messages.join('\n')).toContain('connect-src');
		expect(messages.join('\n')).toContain('https://example.invalid/x.csv');
		expect(external).toEqual([]);
	});
});