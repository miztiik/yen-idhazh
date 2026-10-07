/** Browser contexts that never reach the network: the installed Parquet add-on is served from
 *  disk, and the committed archive host, a real one, refuses every request unless a test serves
 *  it a root the test built (`serveArchiveToPage` in `ledger-lifecycle.ts`): a route added later wins. */
import { test as playwright } from '@playwright/test';
import { cachedParquetAddon, parquetAddon, type ParquetAddon } from '../../scripts/duckdb-addon';
import { ledgerArchiveBaseUrl } from '../../src/lib/server/config';

export * from '@playwright/test';

interface AddonFixtures {
	parquet: { addon: ParquetAddon; bytes: Buffer };
}

export const test = playwright.extend<object, AddonFixtures>({
	parquet: [async ({}, use) => {
		const addon = await parquetAddon();
		await use({ addon, bytes: cachedParquetAddon(addon) });
	}, { scope: 'worker' }],
	context: async ({ context, parquet }, use) => {
		await context.route(parquet.addon.url, (route) => route.fulfill({
			status: 200,
			contentType: 'application/wasm',
			body: parquet.bytes
		}));
		const archive = ledgerArchiveBaseUrl();
		if (archive !== '') await context.route(`${archive}/**`, (route) => route.abort('blockedbyclient'));
		await use(context);
	}
});