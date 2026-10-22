/**
 * Which newest raw day listing did the site build stage for each ledger?
 *
 * The folder is found from this file's own place, never from the working folder, so a build
 * reads the same folder wherever it runs. `frontend/static/` is committed, so a folder that is
 * not there is a wrong path, never a build with no raw day: it stops the build rather than
 * baking an empty list. A static folder with no `state/raw/` names no day.
 *
 * The read opens named config files, but only lists raw listing names, not their contents.
 * It reads what the last `stage-publication.mjs` run staged,
 * and that run empties `static/state/` first: one named registry prefix for
 * each ledger `ledger.published` names, each holding at most `max(console.window_presets)` days.
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ledgerFolders } from './ledger-prefixes.mjs';

const STATIC_ROOT = fileURLToPath(new URL('../static', import.meta.url));
const REPOSITORY = fileURLToPath(new URL('../..', import.meta.url));
const CONFIG = fileURLToPath(new URL('../../config/idhazh.json', import.meta.url));

export function rawListedThrough(staticRoot = STATIC_ROOT) {
	if (!existsSync(staticRoot)) {
		const named = relative(REPOSITORY, staticRoot).split(sep).join('/');
		throw new Error(`the static folder ${named}/ is not there, so the build cannot say which raw days it listed`);
	}
	const raw = join(staticRoot, 'state', 'raw');
	if (!existsSync(raw)) return {};
	const names = JSON.parse(readFileSync(CONFIG, 'utf8'))?.ledger?.published;
	if (!Array.isArray(names)) throw new Error('ledger.published in config/idhazh.json is not a list');
	const folders = ledgerFolders(names);
	/** @type {Record<string, string>} */
	const result = {};
	for (const [ledger, folder] of Object.entries(folders)) {
		const index = join(raw, ...folder.split('/'), 'index');
		if (!existsSync(index)) continue;
		const days = readdirSync(index)
			.filter((name) => /^\d{4}-\d{2}-\d{2}\.json$/.test(name))
			.map((name) => name.slice(0, -5))
			.sort();
		if (days.length > 0) result[ledger] = days[days.length - 1];
	}
	return result;
}
