/** Fetch this compact session's registry with the publication parser. */
import { explorerBaseUrl } from '../../data/ledger';
import { parseLedgerCatalog, type LedgerCatalog, type LedgerCatalogEntry } from '../../data/ledger-catalog';

export type RegistryLedger = LedgerCatalogEntry;
export type LedgerRegistry = LedgerCatalog;

export async function fetchRegistry(fetcher: typeof fetch = fetch, prefix = explorerBaseUrl()): Promise<LedgerRegistry> {
	const response = await fetcher(`${prefix.replace(/\/+$/, '')}/config/ledgers.json`, { cache: 'no-store' });
	if (!response.ok) throw new Error(`config/ledgers.json did not arrive (${response.status})`);
	return parseLedgerCatalog(await response.json());
}
