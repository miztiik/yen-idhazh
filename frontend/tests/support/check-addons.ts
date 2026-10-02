/** Refuse a test run whose shared Parquet add-on has not been prepared. */
import { cachedParquetAddon, parquetAddon } from '../../scripts/duckdb-addon';

export default async function checkAddons(): Promise<void> {
	cachedParquetAddon(await parquetAddon());
}