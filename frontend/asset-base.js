/**
 * Where a browser asks for a published drawing, and what the page may reach.
 *
 * The published site has a 1 GB ceiling and the drawings are the part of it that
 * grows with every day. `visuals.asset_base_url` is the release valve for that:
 * name a host and the drawings a reader scrolls to are asked for there instead,
 * so their bytes stop counting against the ceiling. It ships empty, which means
 * this site, and empty is what is committed - a valve that changes the default
 * output is not a valve, it is a change.
 *
 * **The valve has two halves and one of them is the browser's.** The URL alone
 * does nothing: `connect-src 'self'` in `svelte.config.js` is what makes
 * exfiltration from a planted instruction a browser-level impossibility, and it
 * refuses an off-origin fetch for exactly the same reason. So both halves read
 * this one value. An operator who edits `config/idhazh.json` gets a working
 * site; an operator who has to edit the CSP too gets a page that fetches
 * nothing and says why only in a console the reader will never open.
 *
 * **What opening it widens, stated rather than implied.** `connect-src` gains
 * one origin and only one, computed here from our own config at build time. No
 * payload field, no model output and no fetched text can reach it (Rule #11),
 * and `'self'` stays first in the list, so every request the page already makes
 * is unaffected.
 *
 * This is a plain `.js` module and not `src/lib/server/config.ts` for two
 * reasons. `svelte.config.js` runs before Vite and cannot import a `.ts` module
 * that imports values, which `config.ts` does. And a `$lib/server` module can
 * never be reached from a client component, which is where the other half of
 * this value is needed. `build-frame-css.mjs` already mirrors a config default
 * in plain JS for the same reason.
 */

import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** The tunable knobs. Same file `backend/idhazh/contracts/app_config.py` validates. */
const CONFIG_FILE = join(dirname(fileURLToPath(import.meta.url)), '..', 'config', 'idhazh.json');

/**
 * The prefix a drawing's committed path is joined onto, or `''` for this site.
 *
 * Every failure answers `''`, which is the shipped default and the same site
 * that would have been asked anyway. A build cannot be broken by this file; a
 * config that names a value the contract refuses is caught by the contract,
 * which is where a bad value should be caught.
 *
 * @returns {string}
 */
export function assetBaseUrl() {
	if (!existsSync(CONFIG_FILE)) return '';
	try {
		const value = JSON.parse(readFileSync(CONFIG_FILE, 'utf8'))?.visuals?.asset_base_url;
		return typeof value === 'string' ? value : '';
	} catch {
		return '';
	}
}

/**
 * The `connect-src` sources a page needs, given that prefix.
 *
 * The origin and nothing else: a path in the value is a directory on that host,
 * not a permission, and CSP has no business knowing about it.
 *
 * @param {string} prefix
 * @returns {string[]}
 */
export function connectSources(prefix) {
	if (!prefix) return ['self'];
	return ['self', new URL(prefix).origin];
}
