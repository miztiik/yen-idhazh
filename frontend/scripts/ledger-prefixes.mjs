/** Which validated registry prefixes belong to the named raw-and-compact ledgers? */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseLedgerCatalog } from '../src/lib/data/ledger-catalog.ts';

export const CONFIG_ROOT = process.env.CONFIG_ROOT
	? resolve(process.env.CONFIG_ROOT)
	: fileURLToPath(new URL('../../config', import.meta.url));
export const REGISTRY = resolve(CONFIG_ROOT, 'ledgers.json');

/** @param {string} [file] */
export function ledgerCatalog(file) {
	return parseLedgerCatalog(JSON.parse(readFileSync(file ?? REGISTRY, 'utf8')));
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
