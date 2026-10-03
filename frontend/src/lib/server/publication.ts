/** Read the producer's named publication inventory without discovering files. */
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export interface PublicationInventory {
	version: string;
	changelog: { version: string; change: string; why: string }[];
	dates: string[];
	entries: { root: 'public' | 'state'; path: string; bytes: number; items: number }[];
	total_bytes: number;
	total_items: number;
}

type NamedEntry = Pick<PublicationInventory['entries'][number], 'root' | 'path'>;

function readInventory(root: string): { entries: NamedEntry[]; dates: string[] } {
	const file = join(root, 'publication.json');
	if (!existsSync(file)) {
		throw new Error('Publication inventory is missing. Initialize publication.json with an explicit named seed.');
	}
	const parsed: unknown = JSON.parse(readFileSync(file, 'utf8'));
	if (parsed === null || typeof parsed !== 'object') throw new Error('Publication inventory is not an object.');
	const inventory = parsed as Partial<PublicationInventory> & { files?: unknown; state_files?: unknown };
	let entries: NamedEntry[] | undefined = inventory.entries;
	if (!Array.isArray(entries) && Array.isArray(inventory.files)) {
		entries = inventory.files.map((file: unknown): NamedEntry => {
			if (typeof file !== 'string') throw new Error('Legacy publication inventory names a non-string path.');
			return file.startsWith('state/')
				? { root: 'state', path: file.slice('state/'.length) }
				: { root: 'public', path: file };
		});
		if (Array.isArray(inventory.state_files)) {
			for (const file of inventory.state_files) {
				if (typeof file !== 'string') throw new Error('Legacy publication inventory names a non-string state path.');
				if (!entries.some((entry) => entry.root === 'state' && entry.path === file)) {
					entries.push({ root: 'state', path: file });
				}
			}
		}
		console.warn('Publication inventory uses the older file lists; upgrade it with the named-file utility.');
	}
	if (typeof inventory.version !== 'string' || !Array.isArray(inventory.changelog) ||
		!Array.isArray(inventory.dates) || !Array.isArray(entries)) {
		throw new Error('Publication inventory is missing version, changelog, dates or entries.');
	}
	for (const entry of entries) {
		if (entry === null || typeof entry !== 'object' || !['public', 'state'].includes(entry.root)) {
			throw new Error('Publication inventory names an invalid file root.');
		}
		const path = entry.path;
		if (typeof path !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._/-]*$/.test(path) ||
			path.split('/').some((part) => part === '..' || part === '.' || part === '')) {
			throw new Error('Publication inventory names an invalid relative file path.');
		}
	}
	if (inventory.dates.some((date) => typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date))) {
		throw new Error('Publication inventory names an invalid UTC date.');
	}
	return { entries, dates: inventory.dates };
}

export function publicFiles(root: string): string[] {
	return readInventory(root).entries.filter((entry) => entry.root === 'public').map((entry) => entry.path);
}

export function stateFiles(root: string): string[] {
	return readInventory(root).entries.filter((entry) => entry.root === 'state').map((entry) => entry.path);
}
