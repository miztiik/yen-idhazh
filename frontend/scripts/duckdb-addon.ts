/** Which Parquet add-on does the installed engine need, and is it cached? */
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { nodeEngine } from '../src/lib/data/engine.ts';

const PACKAGE = '@duckdb/duckdb-wasm';
const resolver = createRequire(import.meta.url);
const WASM_MAGIC = Buffer.from([0, 97, 115, 109]);

export interface ParquetAddon {
	packageVersion: string;
	engineVersion: string;
	platform: string;
	url: string;
	file: string;
	cacheKey: string;
}

export async function parquetAddon(): Promise<ParquetAddon> {
	const config = JSON.parse(readFileSync(new URL('../../config/idhazh.json', import.meta.url), 'utf8'));
	const repository: unknown = config.ledger?.engine_extension_repository;
	if (typeof repository !== 'string' || !repository) {
		throw new Error('config/idhazh.json needs ledger.engine_extension_repository');
	}
	const engine = await nodeEngine((specifier) => resolver.resolve(specifier), repository);
	const [versionRows, platformRows] = await Promise.all([
		engine.rows('SELECT version() AS version', []),
		engine.rows('PRAGMA platform', [])
	]);
	const engineVersion = String(versionRows[0].version);
	const platform = String(platformRows[0].platform);
	const manifest = join(dirname(resolver.resolve(PACKAGE)), '..', 'package.json');
	const packageVersion = String(JSON.parse(readFileSync(manifest, 'utf8')).version);
	const address = new URL(`${engineVersion}/${platform}/parquet.duckdb_extension.wasm`, `${repository.replace(/\/$/, '')}/`);
	return {
		packageVersion,
		engineVersion,
		platform,
		url: address.href,
		file: join(homedir(), '.duckdb', 'extensions', address.host, ...address.pathname.split('/').filter(Boolean)),
		cacheKey: `duckdb-parquet-${packageVersion}-${engineVersion}-${platform}`
	};
}

export function cachedParquetAddon(addon: ParquetAddon): Buffer {
	let bytes: Buffer;
	try {
		bytes = readFileSync(addon.file);
	} catch (error) {
		throw new Error(`Parquet add-on ${addon.engineVersion}/${addon.platform} is not cached. Run npm --prefix frontend run setup:duckdb.`, { cause: error });
	}
	if (bytes.length < 8 || !bytes.subarray(0, WASM_MAGIC.length).equals(WASM_MAGIC)) {
		throw new Error(`Cached Parquet add-on ${addon.engineVersion}/${addon.platform} is not WebAssembly. Run npm --prefix frontend run setup:duckdb -- --refresh.`);
	}
	return bytes;
}