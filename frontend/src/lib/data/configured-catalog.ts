/** The committed registry, validated identically in Node and browser builds. */
import registry from '../../../../config/ledgers.json' with { type: 'json' };
import { parseLedgerCatalog } from './ledger-catalog.ts';

export const configuredCatalog = parseLedgerCatalog(registry);
