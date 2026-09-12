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
 * one origin for the drawings valve and, since 2026-09-10, the origins the
 * encoder's failover leg reaches - every one of them computed here from our own
 * config at build time. No payload field, no model output and no fetched text
 * can reach any of them (Guardrail #11), and `'self'` stays first in the list, so
 * every request the page already makes is unaffected.
 *
 * **A second origin is only safe because of what it is paired with.** The
 * encoder half is not just a URL: `encoderSource()` refuses to hand back a
 * fetch address at all unless a SHA-256 manifest and a revision come with it,
 * and the browser discards every arriving file on a single mismatch. The
 * widening lets a second party answer a request; the manifest is what stops it
 * being an answer the reader has to trust.
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
 * The `connect-src` sources a page needs, given that prefix and any extra origins.
 *
 * The origin and nothing else: a path in a value is a directory on that host,
 * not a permission, and CSP has no business knowing about it. `'self'` stays
 * first and every origin is listed once, so a host named twice in config does
 * not appear twice in the header.
 *
 * @param {string} prefix
 * @param {string[]} [extra] Origins from `encoderOrigins()`. Empty by default,
 *   so a caller that asks only about the drawings valve gets the old answer.
 * @returns {string[]}
 */
export function connectSources(prefix, extra = []) {
	const sources = ['self'];
	if (prefix) sources.push(new URL(prefix).origin);
	for (const origin of extra) {
		if (!sources.includes(origin)) sources.push(origin);
	}
	return sources;
}

/**
 * Where a browser may fetch the encoder when this site cannot serve it, and
 * what it must prove about every byte that arrives.
 *
 * **Our own origin is primary and the committed weights stay.** This is the
 * failover leg, and it is off unless every part of it is present: a base URL, a
 * 40-hex revision, a non-empty digest manifest and a deadline. A URL without a
 * manifest would be a permission for a second party to put bytes into a
 * reader's tab rather than a fallback, so an incomplete block answers the empty
 * one and the browser keeps exactly the behaviour it had before this file
 * learned the keys.
 *
 * @returns {{ baseUrl: string, cdnOrigins: string[], revision: string,
 *   digests: Record<string, string>, deadlineMs: number }}
 */
export function encoderSource() {
	const off = { baseUrl: '', cdnOrigins: [], revision: '', digests: {}, deadlineMs: 0 };
	if (!existsSync(CONFIG_FILE)) return off;
	try {
		const assist = JSON.parse(readFileSync(CONFIG_FILE, 'utf8'))?.assist ?? {};
		const baseUrl = typeof assist.model_base_url === 'string' ? assist.model_base_url : '';
		const revision = typeof assist.model_revision === 'string' ? assist.model_revision : '';
		const deadlineMs =
			typeof assist.model_fetch_deadline_ms === 'number' ? assist.model_fetch_deadline_ms : 0;
		const cdnOrigins = Array.isArray(assist.model_cdn_origins)
			? assist.model_cdn_origins.filter((/** @type {unknown} */ value) => typeof value === 'string')
			: [];
		/** @type {Record<string, string>} */
		const digests = {};
		for (const [path, digest] of Object.entries(assist.model_digests ?? {})) {
			if (typeof digest === 'string') digests[path] = digest;
		}
		if (!baseUrl || !/^[0-9a-f]{40}$/.test(revision)) return off;
		if (Object.keys(digests).length === 0 || deadlineMs <= 0) return off;
		return { baseUrl, cdnOrigins, revision, digests, deadlineMs };
	} catch {
		return off;
	}
}

/**
 * The origins the encoder's failover leg reaches, for `connect-src`.
 *
 * The CDN origins are listed as well as the base host because a browser checks
 * a redirect target against the header: measured 2026-09-09 from the live Pages
 * origin, the four small files answer on the base host and the 23 MB of weights
 * answers 302 to a CDN. Listing the base host alone would pass the small files
 * and block the model, which is the worst of both.
 *
 * @returns {string[]}
 */
export function encoderOrigins() {
	const { baseUrl, cdnOrigins } = encoderSource();
	if (!baseUrl) return [];
	const origins = [new URL(baseUrl).origin];
	for (const value of cdnOrigins) {
		try {
			const origin = new URL(value).origin;
			if (!origins.includes(origin)) origins.push(origin);
		} catch {
			continue;
		}
	}
	return origins;
}
