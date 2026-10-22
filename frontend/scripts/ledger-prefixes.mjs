/** Which validated registry prefixes belong to the named raw-and-compact ledgers? */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { configuredCatalog } from '../src/lib/data/configured-catalog.ts';
import { parseLedgerCatalog } from '../src/lib/data/ledger-catalog.ts';

export const REGISTRY = fileURLToPath(new URL('../../config/ledgers.json', import.meta.url));

/** @param {string} [file] */
export function ledgerCatalog(file) {
	return file === undefined ? configuredCatalog : parseLedgerCatalog(JSON.parse(readFileSync(file, 'utf8')));
}

/**
 * @param {readonly string[]} names
 * @param {string} [file]
 * @returns {Record<string, string>}
 */
export function ledgerFolders(names, file) {
	const catalog = ledgerCatalog(file);
	return Object.fromEntries(names.map((name) => {
		const entry = catalog.require(name);
		if (entry.grain !== 'raw-and-compact') throw new Error(`registry does not register ${JSON.stringify(name)} as raw-and-compact`);
		return [name, entry.prefix];
	}));
}
