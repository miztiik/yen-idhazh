/** Fetch the site's registry and use the same validation as publication staging. */
import { base } from '$app/paths';
import { parseLedgerCatalog, type LedgerCatalog, type LedgerCatalogEntry } from '../../data/ledger-catalog';

export type RegistryLedger = LedgerCatalogEntry;
export type LedgerRegistry = LedgerCatalog;

export async function fetchRegistry(fetcher: typeof fetch = fetch): Promise<LedgerRegistry> {
	const response = await fetcher(`${base}/config/ledgers.json`, { cache: 'no-store' });
	if (!response.ok) throw new Error(`config/ledgers.json did not arrive (${response.status})`);
	return parseLedgerCatalog(await response.json());
}
