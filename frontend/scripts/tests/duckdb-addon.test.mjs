import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { cachedParquetAddon, parquetAddon } from '../duckdb-addon.ts';
import { groupedSpecs } from '../test-groups.ts';

test('the installed engine names the same shared add-on used by Node', async () => {
	const addon = await parquetAddon();
	assert.match(addon.engineVersion, /^v\d+\.\d+\.\d+/);
	assert.equal(addon.platform, 'wasm_eh');
	assert.equal(basename(addon.file), 'parquet.duckdb_extension.wasm');
	assert.ok(addon.cacheKey.includes(addon.packageVersion));
	assert.ok(addon.url.endsWith(`/${addon.engineVersion}/${addon.platform}/parquet.duckdb_extension.wasm`));
	assert.ok(cachedParquetAddon(addon).length > 8);
});

test('an absent or invalid cached add-on names the setup command without downloading', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'duckdb-addon-'));
	try {
		const addon = { ...await parquetAddon(), file: join(directory, 'parquet.duckdb_extension.wasm') };
		assert.throws(() => cachedParquetAddon(addon), /not cached.*npm --prefix frontend run setup:duckdb/);
		writeFileSync(addon.file, 'not a WebAssembly file');
		assert.throws(() => cachedParquetAddon(addon), /not WebAssembly.*--refresh/);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('Hardware browser tests share the cached add-on and HTTP-cache tests keep their own host', () => {
	const directory = fileURLToPath(new URL('../../tests/', import.meta.url));
	assert.match(readFileSync(join(directory, 'support', 'door-page.ts'), 'utf8'), /export \* from '\.\/browser';/);
	for (const [group, filenames] of Object.entries(groupedSpecs(directory))) {
		if (group === 'logic') continue;
		for (const filename of filenames) {
			const source = readFileSync(join(directory, filename), 'utf8');
			if (/\/console\/machine|console-panels|CONSOLE_ROUTES/.test(source)) {
				assert.match(source, /from '\.\/support\/(?:browser|door-page)'/, filename);
			}
		}
	}
	assert.doesNotMatch(readFileSync(join(directory, 'ledger-ranges.spec.ts'), 'utf8'), /support\/browser/);
});