/** Prepare the shared Parquet add-on before a build or test starts. */
import { randomUUID } from 'node:crypto';
import { mkdir, rename, rm, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { parseArgs } from 'node:util';
import { cachedParquetAddon, parquetAddon } from './duckdb-addon.ts';

const { values } = parseArgs({
	options: {
		check: { type: 'boolean', default: false },
		refresh: { type: 'boolean', default: false },
		key: { type: 'boolean', default: false }
	}
});
const addon = await parquetAddon();

if (values.key) {
	console.log(addon.cacheKey);
} else if (values.check) {
	console.log(`Cached Parquet add-on: ${cachedParquetAddon(addon).length} bytes (${addon.engineVersion}/${addon.platform}).`);
} else {
	let ready = false;
	if (!values.refresh) {
		try {
			cachedParquetAddon(addon);
			ready = true;
		} catch {
			ready = false;
		}
	}
	if (!ready) {
		const response = await fetch(addon.url);
		if (!response.ok) throw new Error(`Parquet add-on setup received HTTP ${response.status} from ${addon.url}`);
		const temporary = `${addon.file}.${randomUUID()}.tmp`;
		await mkdir(dirname(addon.file), { recursive: true });
		try {
			await writeFile(temporary, new Uint8Array(await response.arrayBuffer()));
			cachedParquetAddon({ ...addon, file: temporary });
			await rename(temporary, addon.file);
		} finally {
			await rm(temporary, { force: true });
		}
	}
	console.log(`Parquet add-on ready: ${cachedParquetAddon(addon).length} bytes (${addon.engineVersion}/${addon.platform}).`);
}