/**
 * Which files of `state/` does the site publish, and which faults stop the build?
 *
 * For every ledger `ledger.published` names in `config/idhazh.json`, the site
 * carries that ledger's three compact indexes trimmed to the widest console span
 * and every compact file those trimmed indexes name, each at the path it has
 * under `state/`, so the address a browser asks for and the committed path are
 * one string. `copy-visuals.mjs` stages what this returns; nothing here writes.
 *
 * **The indexes are the compact list, and raw days have one bounded exception.** A reader asks only
 * for compact files an index names, so a compact file no index names is bytes nobody fetches.
 * The copy is capped from each ledger's newest packed period rather than the
 * build clock, so a canary build keeps publishing the same fixture files next month.
 * Reading the list rather than the tree also keeps `daily/watermark.json`, the
 * gardener's own marker, and any stray file off the site with no list of things
 * to leave out. The raw-day walk checks at most the widest console preset of
 * day directories after the newest packed day, so the door can read files a
 * writer produced before compaction takes them.
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

import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { daysBetween, newestNamed } from '../src/lib/data/slice.ts';

/** The tunable knobs, the same file `backend/idhazh/contracts/app_config.py` validates. */
const CONFIG_FILE = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'config', 'idhazh.json');
const APPEARANCE_FILE = join(
	dirname(fileURLToPath(import.meta.url)),
	'..',
	'..',
	'config',
	'appearance.json'
);

/** A ledger name as `LedgerName` spells one: lower-case words joined by hyphens. */
const LEDGER_NAME = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

/** The compact periods, each with one index. A format literal of the ledger layout. */
const PERIODS = /** @type {const} */ (['daily', 'monthly', 'yearly']);

/** @typedef {(typeof PERIODS)[number]} Period */

/**
 * @typedef {object} LedgerCopy
 * @property {string[]} files Every file to publish, as a POSIX path under the state root.
 * @property {Record<string, string>} indexes Trimmed index payloads, keyed by the same path in `files`.
 * @property {string[]} refused One line a fault that stops the build; empty when it may go on.
 * @property {string[]} missing Every data file an index names and the tree lacks, under the state root.
 * @property {string[]} logs Lines about bounded raw-day listing decisions.
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
 * @param {Period} period
 * @param {number} firstDay
 * @param {number} lastDay
 * @returns {{files: string[], text: string} | string} The named files and trimmed index, or why it was refused.
 */
function filesNamedIn(text, ledger, period, firstDay, lastDay) {
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
		files.push(`compact/${ledger}/${file}`);
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
	/** @type {Record<Period, {covers: string, rows: number, bytes: number}[]>} */
	const byPeriod = { daily: [], monthly: [], yearly: [] };
	/** @type {string[]} */
	const errors = [];
	for (const period of PERIODS) {
		const index = `compact/${ledger}/index/${period}.json`;
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

/** @param {string} day */
function dayParts(day) {
	return day.split('-');
}

/** @param {number} day */
function dayString(day) {
	return new Date(day * 86_400_000).toISOString().slice(0, 10);
}

/** @param {string[]} names */
function rawDigest(names) {
	return createHash('sha256').update(names.join('\n'), 'utf8').digest('hex');
}

/**
 * @param {string} ledger
 * @param {string} day
 * @param {string[]} names
 * @param {number[]} sizes
 * @param {string} listedAt
 */
function listingText(ledger, day, names, sizes, listedAt) {
	return `${JSON.stringify(
		{
			ledger,
			date: day,
			files: names,
			content_sha256: rawDigest(names),
			bytes: sizes,
			listed_at: listedAt
		},
		null,
		2
	)}\n`;
}

/**
 * Stage raw days not packed yet. The bound is one directory check per day, for at most
 * the widest console preset per published ledger; publishing more history cannot widen it.
 *
 * @param {string} stateRoot
 * @param {string} ledger
 * @param {number | null} newestPacked
 * @param {number} spanDays
 * @param {string} listedAt
 * @param {string} rootName
 * @returns {{files: string[], listings: Record<string, string>, logs: string[]}}
 */
function rawDaysNotPackedYet(stateRoot, ledger, newestPacked, spanDays, listedAt, rootName) {
	if (newestPacked === null) {
		return { files: [], listings: {}, logs: [`published ledgers: ${ledger} has no packed day; raw-day walk skipped.`] };
	}
	const start = newestPacked + 1;
	const end = start + spanDays - 1;
	if (start > end) return { files: [], listings: {}, logs: [] };
	/** @type {{day: string, directory: string, exists: boolean}[]} */
	const checked = [];
	let newestRaw = null;
	for (const day of daysBetween(dayString(start), dayString(end))) {
		const [year, month, date] = dayParts(day);
		const directory = join(stateRoot, 'raw', ledger, year, month, date);
		const exists = existsSync(directory) && statSync(directory).isDirectory();
		checked.push({ day, directory, exists });
		if (exists) newestRaw = day;
	}
	if (newestRaw === null) return { files: [], listings: {}, logs: [] };
	/** @type {string[]} */
	const files = [];
	/** @type {Record<string, string>} */
	const listings = {};
	/** @type {string[]} */
	const logs = [];
	for (const dayInfo of checked) {
		if (dayInfo.day > newestRaw) break;
		const listing = `raw/${ledger}/index/${dayInfo.day}.json`;
		if (!dayInfo.exists) {
			listings[listing] = listingText(ledger, dayInfo.day, [], [], listedAt);
			files.push(listing);
			continue;
		}
		const names = readdirSync(dayInfo.directory)
			.filter((name) => statSync(join(dayInfo.directory, name)).isFile())
			.sort();
		const refused = names.filter((name) => !name.endsWith('.parquet'));
		if (refused.length > 0) {
			for (const name of refused) {
				logs.push(
					`published ledgers: ${rootName}/raw/${ledger}/${dayInfo.day.replaceAll('-', '/')}/${name} is not parquet; ${dayInfo.day} is left unlisted.`
				);
			}
			continue;
		}
		const sizes = names.map((name) => statSync(join(dayInfo.directory, name)).size);
		listings[listing] = listingText(ledger, dayInfo.day, names, sizes, listedAt);
		files.push(listing);
		for (const name of names) {
			const [year, month, date] = dayParts(dayInfo.day);
			files.push(`raw/${ledger}/${year}/${month}/${date}/${name}`);
		}
	}
	return { files, listings, logs };
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
	const copy = { files: [], indexes: {}, refused: [], missing: [], logs: [] };
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
	const spanDays = publishedWindowDays();
	const listedAt = new Date(Date.now()).toISOString().replace(/\.\d{3}Z$/, 'Z');
	for (const ledger of ledgers) {
		const missingIndexes = PERIODS.filter(
			(period) => !existsSync(join(stateRoot, 'compact', ledger, 'index', `${period}.json`))
		);
		if (missingIndexes.length > 0) {
			for (const period of missingIndexes) {
				copy.refused.push(`${ledger}: ${rootName}/compact/${ledger}/index/${period}.json is missing`);
			}
			continue;
		}
		const packed = readPackedIndexes(stateRoot, ledger, rootName);
		if (packed.errors.length > 0) {
			copy.refused.push(...packed.errors);
			continue;
		}
		const newest = packed.newest;
		if (newest === null) {
			for (const period of PERIODS) {
				const index = `compact/${ledger}/index/${period}.json`;
				copy.indexes[index] = readFileSync(join(stateRoot, ...index.split('/')), 'utf8');
				files.add(index);
			}
			copy.logs.push(`published ledgers: ${ledger} has no packed day; raw-day walk skipped.`);
			continue;
		}
		const firstDay = newest - spanDays + 1;
		for (const period of PERIODS) {
			const index = `compact/${ledger}/index/${period}.json`;
			const at = join(stateRoot, ...index.split('/'));
			if (!existsSync(at)) {
				copy.refused.push(`${ledger}: ${rootName}/${index} is missing`);
				continue;
			}
			const named = filesNamedIn(readFileSync(at, 'utf8'), ledger, period, firstDay, newest);
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
		const raw = rawDaysNotPackedYet(stateRoot, ledger, newest, spanDays, listedAt, rootName);
		copy.logs.push(...raw.logs);
		for (const file of raw.files) files.add(file);
		Object.assign(copy.indexes, raw.listings);
	}
	copy.files = [...files].sort();
	copy.missing = [...missing].sort();
	return copy;
}
