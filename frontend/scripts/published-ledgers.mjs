/**
 * Which files of `state/` does the site publish, and which faults stop the build?
 *
 * For every ledger `ledger.published` names in `config/idhazh.json`, the site
 * carries that ledger's three compact indexes and every compact file they name,
 * each at the path it has under `state/`, so the address a browser asks for and
 * the committed path are one string. `copy-visuals.mjs` stages what this
 * returns; nothing here writes.
 *
 * **The indexes are the list, and no directory is walked.** A reader asks only
 * for files an index names, so a file no index names is bytes nobody fetches.
 * Reading the list rather than the tree also keeps `daily/watermark.json`, the
 * gardener's own marker, and any stray file off the site with no list of things
 * to leave out.
 *
 * **A missing index stops the build; a missing data file does not.** The
 * browser asks for a published ledger's indexes before anything else, so a
 * published ledger without all three is published wrongly and a 404 would be the only
 * sign of it. A data file an index names and the tree lacks is one lost day: the
 * rest is copied, the build log names the file and the fix, and the browser's
 * query door answers `unreachable` for a span that reaches it - degrade, do not
 * fail (CLAUDE.md section 1a).
 *
 * **Every path is built from checked parts.** A ledger name is lower-case words
 * joined by hyphens, and a `covers` value is a UTC day, month or year in digits, or
 * the name or the index is refused, so no value in a file can move where a copy
 * lands.
 */

import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** The tunable knobs, the same file `backend/idhazh/contracts/app_config.py` validates. */
const CONFIG_FILE = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'config', 'idhazh.json');

/** A ledger name as `LedgerName` spells one: lower-case words joined by hyphens. */
const LEDGER_NAME = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

/** The compact periods, each with one index. A format literal of the ledger layout. */
const PERIODS = /** @type {const} */ (['daily', 'monthly', 'yearly']);

/** @typedef {(typeof PERIODS)[number]} Period */

/**
 * @typedef {object} LedgerCopy
 * @property {string[]} files Every file to publish, as a POSIX path under the state root.
 * @property {string[]} refused One line a fault that stops the build; empty when it may go on.
 * @property {string[]} missing Every data file an index names and the tree lacks, under the state root.
 */

/**
 * The ledgers the committed config publishes.
 *
 * A config that cannot be read, or a name that is not a ledger name, throws: the
 * build cannot know what to publish, and a guess is a site that says less than
 * the committed tree.
 *
 * @param {string} [file]
 * @returns {string[]}
 */
export function publishedLedgers(file = CONFIG_FILE) {
	const named = JSON.parse(readFileSync(file, 'utf8'))?.ledger?.published ?? [];
	if (!Array.isArray(named)) throw new Error('ledger.published in config/idhazh.json is not a list');
	for (const name of named) {
		if (typeof name !== 'string' || !LEDGER_NAME.test(name)) {
			throw new Error(
				`ledger.published in config/idhazh.json names ${JSON.stringify(name)}, which is not a ledger name`
			);
		}
	}
	return named;
}

/**
 * The file one index entry names, under `compact/<ledger>/`, or null when
 * `covers` is not that period's shape.
 *
 * @param {Period} period
 * @param {unknown} covers
 * @returns {string | null}
 */
function namedFile(period, covers) {
	if (typeof covers !== 'string') return null;
	if (period === 'daily') {
		const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(covers);
		return day ? `daily/${day[1]}/${day[2]}/${day[3]}.parquet` : null;
	}
	if (period === 'yearly') {
		return /^\d{4}$/.test(covers) ? `yearly/${covers}/${covers}.parquet` : null;
	}
	const month = /^(\d{4})-(\d{2})$/.exec(covers);
	return month ? `monthly/${month[1]}/${month[2]}.parquet` : null;
}

/**
 * The files one index names, or the reason it cannot be acted on.
 *
 * Only what the copy needs is checked: that the file is this ledger's index for
 * this period, and that every entry covers a day, month or year of that period.
 * The browser's door checks the rest of the shape when it reads the file.
 *
 * @param {string} text
 * @param {string} ledger
 * @param {Period} period
 * @returns {string[] | string} The named files, or why the index was refused.
 */
function filesNamedIn(text, ledger, period) {
	/** @type {unknown} */
	let index;
	try {
		index = JSON.parse(text);
	} catch {
		return 'is not JSON';
	}
	if (index === null || typeof index !== 'object') return 'is not an index';
	const held = /** @type {{ledger?: unknown, period?: unknown, entries?: unknown}} */ (index);
	if (held.ledger !== ledger || held.period !== period) {
		return `describes ${String(held.ledger)} ${String(held.period)}, not ${ledger} ${period}`;
	}
	if (!Array.isArray(held.entries)) return 'has no list of entries';
	/** @type {string[]} */
	const files = [];
	for (const entry of held.entries) {
		const covers = entry !== null && typeof entry === 'object' ? entry.covers : undefined;
		const file = namedFile(period, covers);
		if (file === null) {
			const unit = period === 'daily' ? 'day' : period === 'monthly' ? 'month' : 'year';
			return `names ${JSON.stringify(covers)}, which is not a UTC ${unit}`;
		}
		files.push(`compact/${ledger}/${file}`);
	}
	return files;
}

/**
 * What the site publishes out of one state root for these ledgers.
 *
 * `stateRoot` is `STATE_ROOT`, or `state/` at the repository root, so a canary
 * build publishes the fixture's packed ledgers and never the real ones. A root
 * that is not there refuses the build whenever a ledger is published: an empty
 * ledger and a working one both render, so a build that quietly copied nothing
 * would look like a quiet week.
 *
 * @param {string} stateRoot
 * @param {readonly string[]} ledgers
 * @param {string} [rootName] How a refusal names `stateRoot`: a repository path, never an absolute one.
 * @returns {LedgerCopy}
 */
export function ledgerCopy(stateRoot, ledgers, rootName = 'state') {
	/** @type {LedgerCopy} */
	const copy = { files: [], refused: [], missing: [] };
	if (ledgers.length === 0) return copy;
	if (!existsSync(stateRoot) || !statSync(stateRoot).isDirectory()) {
		copy.refused.push(
			`the state root ${rootName}/ is not there, and ledger.published names ${ledgers.join(', ')}`
		);
		return copy;
	}
	/** @type {Set<string>} */
	const files = new Set();
	/** @type {Set<string>} */
	const missing = new Set();
	for (const ledger of ledgers) {
		for (const period of PERIODS) {
			const index = `compact/${ledger}/index/${period}.json`;
			const at = join(stateRoot, ...index.split('/'));
			if (!existsSync(at)) {
				copy.refused.push(`${ledger}: ${rootName}/${index} is missing`);
				continue;
			}
			const named = filesNamedIn(readFileSync(at, 'utf8'), ledger, period);
			if (typeof named === 'string') {
				copy.refused.push(`${ledger}: ${rootName}/${index} ${named}`);
				continue;
			}
			files.add(index);
			for (const file of named) {
				if (existsSync(join(stateRoot, ...file.split('/')))) files.add(file);
				else missing.add(file);
			}
		}
	}
	copy.files = [...files].sort();
	copy.missing = [...missing].sort();
	return copy;
}
