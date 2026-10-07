/**
 * Does each payload ceiling in config bound a file of a finished build, and is every such file inside it?
 *
 * `bundle-gate.mjs` asks this of `page_weight.payload_ceilings_bytes` in
 * `config/idhazh.json`, prints the answer and fails on it. The check lives here
 * because the gate runs every check when it is loaded, so a test could not call
 * one of them on a build tree of its own.
 *
 * A key is a build-relative POSIX path, and its shape says what it bounds. A
 * key naming a file bounds that file. A key ending in `/` bounds every file
 * under that directory, each on its own - a month series takes one number
 * rather than one a month, so a shard landing in October needs no config edit
 * and gets no free pass either.
 *
 * **A key that covers no file fails**, for the same reason an unmatched route
 * ceiling does: a bound over nothing still reads as a bound somebody checked.
 * Two kinds of key cover no file by design, and each is reported as not
 * weighed, with its reason, instead:
 * - every key under `state/` while `visuals.asset_base_url` is set, because the
 *   build then copies no ledger and the browser asks that host for them;
 * - the index key of a published ledger while the build holds none of that
 *   ledger's files. The ledger is not packed yet, which is how every ledger
 *   starts, and the site copy stages nothing for it (`ledgerCopy` in
 *   `published-ledgers.mjs`). A compact folder deleted by accident reads the same
 *   way, as it does in the site build, so the reason names the ledger.
 * A published ledger with some of its files in the build and no index still
 * fails, because a browser asks for a ledger's indexes before anything else.
 *
 * The walk is over the named keys and not over the build, so what this costs is
 * set by how many ceilings are written rather than by how much the pipeline has
 * accumulated (Guardrail #12). A ledger's files are the two folders the site
 * copy stages for it, `state/compact/<ledger>/` and `state/raw/<ledger>/`, so
 * whether the build holds any of them is one existence check on each named
 * path. A directory key does read every file under itself, and that read grows -
 * a month a run appends is a file this opens. It is bounded where it matters by
 * retention: the gardener's telemetry-aggregate task keeps the public-copy
 * series of config/gardener/telemetry-aggregate.json, 14 months, so the
 * directory holds fourteen shards however long the project runs.
 */

import { existsSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Where the published ledgers sit in a build: `copy-visuals.mjs` copies each
 * file to the path it has under the repository's `state/`.
 */
export const LEDGERS = 'state/';

/**
 * @typedef {object} WeighedFile
 * @property {string} key The ceiling key that covers the file.
 * @property {string} path The file, as a build-relative POSIX path.
 * @property {number} bytes What the file weighs, by the measure the caller passes.
 * @property {number} ceiling The key's ceiling, in the same unit.
 */

/**
 * @typedef {object} PayloadWeights
 * @property {WeighedFile[]} weighed Every file a key covers: keys in sorted order, the heaviest file first within a key.
 * @property {WeighedFile[]} over Every weighed file heavier than its key's ceiling. Each one fails the gate.
 * @property {{key: string, ceiling: number}[]} namesNothing Every key that covers no file and has no reason to. Each one fails the gate.
 * @property {{key: string, reason: string}[]} notWeighed Every key that covers no file by design, and why. None fails the gate.
 */

/**
 * Every file one key covers in the build, by name, or none when nothing is at its path.
 *
 * @param {string} build
 * @param {string} key
 * @returns {{path: string, file: string}[]}
 */
function filesCovered(build, key) {
	const target = join(build, ...key.split('/').filter(Boolean));
	let stat;
	try {
		stat = statSync(target);
	} catch {
		return [];
	}
	if (!stat.isDirectory()) return [{ path: key, file: target }];
	return readdirSync(target)
		.sort()
		.filter((name) => !statSync(join(target, name)).isDirectory())
		.map((name) => ({ path: `${key}${name}`, file: join(target, name) }));
}

/**
 * The published ledger whose index key this is, when the build holds none of that ledger's files.
 *
 * @param {string} build
 * @param {string} key
 * @param {readonly string[]} published
 * @returns {string | undefined}
 */
function notPackedYet(build, key, published) {
	const ledger = published.find((name) => key === `${LEDGERS}compact/${name}/index/`);
	if (ledger === undefined) return undefined;
	const folders = [`${LEDGERS}compact/${ledger}`, `${LEDGERS}raw/${ledger}`];
	return folders.some((folder) => existsSync(join(build, ...folder.split('/')))) ? undefined : ledger;
}

/**
 * Weigh every file each payload key covers in a finished build, and say which keys fail.
 *
 * @param {string} build The finished build's root directory.
 * @param {Readonly<Record<string, number>>} ceilings `page_weight.payload_ceilings_bytes`: key -> its ceiling.
 * @param {readonly string[]} published `ledger.published`: the ledgers the site copy stages.
 * @param {string} servedFrom `visuals.asset_base_url`: the host that serves the ledgers, or `''` for this site.
 * @param {(file: string) => number} weigh What one file weighs, given its path on disk. The gate passes its gzip -5 size.
 * @returns {PayloadWeights}
 */
export function weighPayloads(build, ceilings, published, servedFrom, weigh) {
	/** @type {PayloadWeights} */
	const answer = { weighed: [], over: [], namesNothing: [], notWeighed: [] };
	for (const key of Object.keys(ceilings).sort()) {
		const ceiling = ceilings[key];
		if (servedFrom !== '' && key.startsWith(LEDGERS)) {
			answer.notWeighed.push({
				key,
				reason: `visuals.asset_base_url serves the published ledgers from ${servedFrom}`
			});
			continue;
		}
		const files = filesCovered(build, key)
			.map(({ path, file }) => ({ key, path, bytes: weigh(file), ceiling }))
			.sort((left, right) => right.bytes - left.bytes);
		if (files.length > 0) {
			answer.weighed.push(...files);
			answer.over.push(...files.filter(({ bytes }) => bytes > ceiling));
			continue;
		}
		const ledger = notPackedYet(build, key, published);
		if (ledger === undefined) {
			answer.namesNothing.push({ key, ceiling });
			continue;
		}
		answer.notWeighed.push({
			key,
			reason:
				`${ledger} is not packed yet, so the build holds none of its files. ` +
				`If it was packed before, restore ${LEDGERS}compact/${ledger}/ from git history.`
		});
	}
	return answer;
}
