/** Give browser contexts the installed Parquet add-on without a network download. */
import { test as playwright } from '@playwright/test';
import { cachedParquetAddon, parquetAddon, type ParquetAddon } from '../../scripts/duckdb-addon';

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
		await use(context);
	}
});