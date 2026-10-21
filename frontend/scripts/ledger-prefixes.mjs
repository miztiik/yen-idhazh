/** Which checked registry prefixes belong to the named raw-and-compact ledgers? */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const REGISTRY = fileURLToPath(new URL('../../config/ledgers.json', import.meta.url));
const SEGMENT = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

/**
 * @param {readonly string[]} names
 * @param {string} [file]
 * @returns {Record<string, string>}
 */
export function ledgerFolders(names, file = REGISTRY) {
	const registry = JSON.parse(readFileSync(file, 'utf8'));
	if (!Array.isArray(registry?.families)) throw new Error('config/ledgers.json has no families list');
	/** @type {Record<string, string>} */
	const folders = {};
	const prefixes = new Set();
	for (const family of registry.families) {
		if (!Array.isArray(family?.ledgers)) throw new Error('config/ledgers.json has no ledgers list');
		for (const entry of family.ledgers) {
			if (entry?.grain !== 'raw-and-compact') continue;
			if (typeof entry.name !== 'string' || !SEGMENT.test(entry.name)) {
				throw new Error('config/ledgers.json has an invalid ledger name');
			}
			if (!Array.isArray(entry.prefix) || entry.prefix.length === 0 ||
				entry.prefix.some((/** @type {unknown} */ part) => typeof part !== 'string' || !SEGMENT.test(part))) {
				throw new Error(`config/ledgers.json has an unsafe prefix for ${entry.name}`);
			}
			const prefix = entry.prefix.join('/');
			if (Object.hasOwn(folders, entry.name) || [...prefixes].some(
				(held) => held === prefix || held.startsWith(`${prefix}/`) || prefix.startsWith(`${held}/`)
			)) {
				throw new Error(`config/ledgers.json has an ambiguous ledger mapping for ${entry.name}`);
			}
			folders[entry.name] = prefix;
			prefixes.add(prefix);
		}
	}
	for (const name of names) {
		if (!Object.hasOwn(folders, name)) {
			throw new Error(`config/ledgers.json does not register ${JSON.stringify(name)} as raw-and-compact`);
		}
	}
	return Object.fromEntries(names.map((name) => [name, folders[name]]));
}
