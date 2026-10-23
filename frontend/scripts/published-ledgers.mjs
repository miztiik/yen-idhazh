/**
 * Which files of `state/` does the site publish, and which faults stop the build?
 *
 * For every ledger whose registry entry consents to explorer publication, the site
 * carries that ledger's three compact indexes trimmed to the widest console span
 * and every compact file those trimmed indexes name, each at the path it has
 * under `state/`, so the address a browser asks for and the committed path are
 * one string. `stage-publication.mjs` stages what this returns; nothing here writes.
 *
 * **The indexes are the compact list.** A reader asks only for compact files an
 * index names, so a compact file no index names is bytes nobody fetches.
 * An entry `empty` or `lost` stays in its index and names no file, so it is never copied or
 * reported missing.
 * The copy is capped from each ledger's newest packed period rather than the
 * build clock, so a canary build keeps publishing the same fixture files next month.
 * That window is `src/lib/data/site-window.ts`. Reading the list rather than
 * the tree also keeps any stray file off the site.
 *
 * **A ledger not packed yet is left out; a missing index stops the build; a
 * missing data file does not.** A published ledger with no compact folder has not
 * been packed yet, which is how every ledger starts: nothing is copied for it, the
 * build log names it, and the browser's query door answers `missing` for it. A
 * ledger with a compact folder but not all three indexes is published wrongly,
 * and a 404 would be the only sign of it, because the browser asks for a
 * ledger's indexes before anything else. A data file an index names and the tree
 * lacks is one lost day: the rest is copied, the build log names the file and the
 * fix, and the browser's query door answers `unreachable` for a span that reaches
 * it - degrade, do not fail (CLAUDE.md section 1a).
 *
 * **Every path is built from checked parts.** A ledger name is lower-case words
 * joined by hyphens, and a `covers` value is a UTC day, month or year in digits, or
 * the name or the index is refused, so no value in a file can move where a copy
 * lands.
 */

import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { siteKeepsFrom } from '../src/lib/data/site-window.ts';
import { namesFile, newestNamed } from '../src/lib/data/slice.ts';
import { CONFIG_ROOT, ledgerCatalog, ledgerFolders, REGISTRY } from './ledger-prefixes.mjs';

const APPEARANCE_FILE = join(CONFIG_ROOT, 'appearance.json');

/** The compact periods, each with one index. A format literal of the ledger layout. */
const PERIODS = /** @type {const} */ (['daily', 'monthly', 'yearly']);

/** @typedef {(typeof PERIODS)[number]} Period */

/**
 * @typedef {object} LedgerCopy
 * @property {string[]} files Every file to publish, as a POSIX path under the state root.
 * @property {Record<string, string>} indexes Trimmed index payloads, keyed by the same path in `files`.
 * @property {string[]} refused One line a fault that stops the build; empty when it may go on.
 * @property {string[]} missing Every data file an index names and the tree lacks, under the state root.
 * @property {string[]} logs Lines for the build log: a ledger not packed yet.
 */

/**
 * The ledgers whose validated registry entries consent to explorer publication.
 *
 * An unreadable or invalid registry throws: the build cannot know what to
 * publish, and a guess is a site that says less than the committed tree.
 *
 * @param {string} [registryFile]
 * @returns {string[]}
 */
export function publishedLedgers(registryFile = REGISTRY) {
	return ledgerCatalog(registryFile).entries
		.filter((entry) => entry.publish_to_data_explorer)
		.map((entry) => entry.name);
}

export function publishedWindowDays(file = APPEARANCE_FILE) {
	const presets = JSON.parse(readFileSync(file, 'utf8'))?.console?.window_presets ?? [];
	if (!Array.isArray(presets) || presets.length === 0) {
		throw new Error('console.window_presets in config/appearance.json is not a non-empty list');
	}
	const values = presets.filter((value) => Number.isInteger(value) && value > 0);
	if (values.length !== presets.length) {
		throw new Error('console.window_presets in config/appearance.json names a non-positive day count');
	}
	return Math.max(...values);
}

/** @param {string} day */
function dayNumber(day) {
	const found = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
	if (!found) return null;
	return Math.floor(Date.UTC(Number(found[1]), Number(found[2]) - 1, Number(found[3])) / 86_400_000);
}

/** @param {string} month */
function monthRange(month) {
	const found = /^(\d{4})-(\d{2})$/.exec(month);
	if (!found) return null;
	const first = Math.floor(Date.UTC(Number(found[1]), Number(found[2]) - 1, 1) / 86_400_000);
	const after = Math.floor(Date.UTC(Number(found[1]), Number(found[2]), 1) / 86_400_000);
	return { first, last: after - 1 };
}

/** @param {string} year */
function yearRange(year) {
	if (!/^\d{4}$/.test(year)) return null;
	const first = Math.floor(Date.UTC(Number(year), 0, 1) / 86_400_000);
	const after = Math.floor(Date.UTC(Number(year) + 1, 0, 1) / 86_400_000);
	return { first, last: after - 1 };
}

/**
 * @param {Period} period
 * @param {unknown} covers
 */
function entryRange(period, covers) {
	if (typeof covers !== 'string') return null;
	if (period === 'daily') {
		const day = dayNumber(covers);
		return day === null ? null : { first: day, last: day };
	}
	if (period === 'monthly') return monthRange(covers);
	return yearRange(covers);
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
 * The files one index names after trimming it to the published window, or the reason it cannot be acted on.
 *
 * Only what the copy needs is checked: that the file is this ledger's index for
 * this period, and that every entry covers a day, month or year of that period.
 * The browser's door checks the rest of the shape when it reads the file.
 *
 * @param {string} text
 * @param {string} ledger
 * @param {string} folder
 * @param {Period} period
 * @param {number} firstDay
 * @param {number} lastDay
 * @returns {{files: string[], text: string} | string} The named files and trimmed index, or why it was refused.
 */
function filesNamedIn(text, ledger, folder, period, firstDay, lastDay) {
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
	const entries = [];
	for (const entry of held.entries) {
		const covers = entry !== null && typeof entry === 'object' ? entry.covers : undefined;
		const file = namedFile(period, covers);
		if (file === null) {
			const unit = period === 'daily' ? 'day' : period === 'monthly' ? 'month' : 'year';
			return `names ${JSON.stringify(covers)}, which is not a UTC ${unit}`;
		}
		const range = entryRange(period, covers);
		if (range === null) return `names ${JSON.stringify(covers)}, which is not a UTC period`;
		if (range.last < firstDay || range.first > lastDay) continue;
		entries.push(entry);
		if (namesFile(entry)) files.push(`compact/${folder}/${file}`);
	}
	return { files, text: `${JSON.stringify({ ...held, entries }, null, 2)}\n` };
}

/**
 * @param {string} stateRoot
 * @param {string} ledger
 * @param {string} [rootName]
 * @returns {{ newest: number | null, days: string[], errors: string[] }}
 */
export function readPackedIndexes(stateRoot, ledger, rootName = 'state') {
	const folder = ledgerFolders([ledger])[ledger];
	return packedIndexes(stateRoot, ledger, folder, rootName);
}

/**
 * @param {string} stateRoot
 * @param {string} ledger
 * @param {string} folder Validated at the registry boundary.
 * @param {string} rootName
 */
function packedIndexes(stateRoot, ledger, folder, rootName) {
	/** @type {Record<Period, {covers: string, rows: number, bytes: number}[]>} */
	const byPeriod = { daily: [], monthly: [], yearly: [] };
	/** @type {string[]} */
	const errors = [];
	for (const period of PERIODS) {
		const index = `compact/${folder}/index/${period}.json`;
		const at = join(stateRoot, ...index.split('/'));
		let parsed;
		try {
			parsed = JSON.parse(readFileSync(at, 'utf8'));
		} catch {
			errors.push(`${ledger}: ${rootName}/${index} is not JSON`);
			continue;
		}
		if (parsed === null || typeof parsed !== 'object') {
			errors.push(`${ledger}: ${rootName}/${index} is not an index`);
			continue;
		}
		const held = /** @type {{ledger?: unknown, period?: unknown, entries?: unknown}} */ (parsed);
		if (held.ledger !== ledger || held.period !== period) {
			errors.push(
				`${ledger}: ${rootName}/${index} describes ${String(held.ledger)} ${String(held.period)}, not ${ledger} ${period}`
			);
			continue;
		}
		if (!Array.isArray(held.entries)) {
			errors.push(`${ledger}: ${rootName}/${index} has no list of entries`);
			continue;
		}
		/** @type {{covers: string, rows: number, bytes: number}[]} */
		const entries = [];
		for (const entry of held.entries) {
			const covers = entry !== null && typeof entry === 'object' ? entry.covers : undefined;
			const range = entryRange(period, covers);
			if (range === null) {
				const unit = period === 'daily' ? 'day' : period === 'monthly' ? 'month' : 'year';
				errors.push(
					`${ledger}: ${rootName}/${index} names ${JSON.stringify(covers)}, which is not a UTC ${unit}`
				);
				continue;
			}
			entries.push(/** @type {{covers: string, rows: number, bytes: number}} */ (entry));
		}
		byPeriod[period] = entries;
	}
	const newest = newestNamed(byPeriod.daily, byPeriod.monthly, byPeriod.yearly);
	return { newest: newest === null ? null : dayNumber(newest), days: byPeriod.daily.map((entry) => entry.covers), errors };
}

/**
 * @param {string} stateRoot
 * @param {string} ledger
 * @param {string} [rootName]
 * @returns {number | null}
 */
export function newestPackedDay(stateRoot, ledger, rootName = 'state') {
	const read = readPackedIndexes(stateRoot, ledger, rootName);
	if (read.errors.length > 0) throw new Error(read.errors.join('\n'));
	return read.newest;
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
 * @param {string} [rootName] How a refusal or a log line names `stateRoot`: a repository path, never an absolute one.
 * @param {number} [spanDays] How many UTC days the compact copy keeps: the widest console preset, unless a test names its own.
 * @param {string} [registryFile] The validated registry used to resolve the supplied ledger names.
 * @returns {LedgerCopy}
 */
export function ledgerCopy(
	stateRoot,
	ledgers,
	rootName = 'state',
	spanDays = publishedWindowDays(),
	registryFile = REGISTRY
) {
	/** @type {LedgerCopy} */
	const copy = { files: [], indexes: {}, refused: [], missing: [], logs: [] };
	if (ledgers.length === 0) return copy;
	const folders = ledgerFolders(ledgers, registryFile);
	if (!existsSync(stateRoot) || !statSync(stateRoot).isDirectory()) {
		copy.refused.push(
			`the state root ${rootName}/ is not there, and explorer consent names ${ledgers.join(', ')}`
		);
		return copy;
	}
	/** @type {Set<string>} */
	const files = new Set();
	/** @type {Set<string>} */
	const missing = new Set();
	for (const ledger of ledgers) {
		const folder = folders[ledger];
		if (!existsSync(join(stateRoot, 'compact', ...folder.split('/')))) {
			copy.logs.push(
				`published ledgers: ${rootName}/compact/${folder}/ is not there, so ${ledger} is not packed yet ` +
					'and the site holds none of its files. If it was packed before, restore that folder from git history.'
			);
			continue;
		}
		const missingIndexes = PERIODS.filter(
			(period) => !existsSync(join(stateRoot, 'compact', ...folder.split('/'), 'index', `${period}.json`))
		);
		if (missingIndexes.length > 0) {
			for (const period of missingIndexes) {
				copy.refused.push(`${ledger}: ${rootName}/compact/${folder}/index/${period}.json is missing`);
			}
			continue;
		}
		const packed = packedIndexes(stateRoot, ledger, folder, rootName);
		if (packed.errors.length > 0) {
			copy.refused.push(...packed.errors);
			continue;
		}
		const newest = packed.newest;
		if (newest === null) {
			for (const period of PERIODS) {
				const index = `compact/${folder}/index/${period}.json`;
				copy.indexes[index] = readFileSync(join(stateRoot, ...index.split('/')), 'utf8');
				files.add(index);
			}
			copy.logs.push(`published ledgers: ${ledger} has no packed day.`);
			continue;
		}
		const newestDay = new Date(newest * 86_400_000).toISOString().slice(0, 10);
		const firstDay = /** @type {number} */ (dayNumber(siteKeepsFrom(newestDay, spanDays)));
		for (const period of PERIODS) {
			const index = `compact/${folder}/index/${period}.json`;
			const at = join(stateRoot, ...index.split('/'));
			if (!existsSync(at)) {
				copy.refused.push(`${ledger}: ${rootName}/${index} is missing`);
				continue;
			}
			const named = filesNamedIn(readFileSync(at, 'utf8'), ledger, folder, period, firstDay, newest);
			if (typeof named === 'string') {
				copy.refused.push(`${ledger}: ${rootName}/${index} ${named}`);
				continue;
			}
			copy.indexes[index] = named.text;
			files.add(index);
			for (const file of named.files) {
				if (existsSync(join(stateRoot, ...file.split('/')))) files.add(file);
				else missing.add(file);
			}
		}
	}
	copy.files = [...files].sort();
	copy.missing = [...missing].sort();
	return copy;
}
