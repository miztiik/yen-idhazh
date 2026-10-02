import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { publishedLedgers } from '../scripts/published-ledgers.mjs';
import { COMPACT_PERIODS, readIndex } from '../src/lib/data/compact-index';
import { dataPath, indexPath } from '../src/lib/data/slice-reader';
import type { LedgerName } from '../src/lib/data/slice-shapes';

/**
 * Every address the query door asks a published ledger for resolves on the
 * built site, and nothing else of `state/` is there.
 *
 * `scripts/copy-visuals.mjs` copies each ledger `ledger.published` names out of
 * the state root: its three indexes and every compact file they name, at the path
 * each has under `state/`. This file reads the build the preview server is about
 * to serve and asks it the door's own questions - the addresses
 * `slice-reader.ts` composes and the guard `compact-index.ts` applies to an
 * index - so the copy and the door cannot drift apart. It cannot say whether a
 * browser can query the files; `ledger-door.spec.ts` does that.
 *
 * The walk covers what the published indexes name, and the build copies
 * nothing else, so its cost is set by each ledger's keep windows and not by the
 * archive (Guardrail #12). Runs in Node, like `staged-day.spec.ts`: no page is
 * loaded.
 */

const STATE = resolve(process.cwd(), 'build', 'state');
const BUILD = resolve(process.cwd(), 'build');

/** Every file under a directory, as a POSIX path relative to it. */
function filesUnder(root: string, prefix = ''): string[] {
	if (!existsSync(root)) return [];
	return readdirSync(root, { withFileTypes: true }).flatMap((entry) =>
		entry.isDirectory()
			? filesUnder(join(root, entry.name), `${prefix}${entry.name}/`)
			: [`${prefix}${entry.name}`]
	);
}

function at(path: string): string {
	return join(STATE, ...path.split('/'));
}

function dayNumber(day: string): number {
	const [year, month, date] = day.split('-').map(Number);
	return Math.floor(Date.UTC(year, month - 1, date) / 86_400_000);
}

function rangeFor(period: string, covers: string): { first: number; last: number } {
	if (period === 'daily') {
		const day = dayNumber(covers);
		return { first: day, last: day };
	}
	if (period === 'monthly') {
		const [year, month] = covers.split('-').map(Number);
		const first = Math.floor(Date.UTC(year, month - 1, 1) / 86_400_000);
		const after = Math.floor(Date.UTC(year, month, 1) / 86_400_000);
		return { first, last: after - 1 };
	}
	const year = Number(covers);
	const first = Math.floor(Date.UTC(year, 0, 1) / 86_400_000);
	const after = Math.floor(Date.UTC(year + 1, 0, 1) / 86_400_000);
	return { first, last: after - 1 };
}

/** What the published indexes send the door to, and each file's size as its entry names it. */
function addressed(): { sizes: Map<string, number | null>; problems: string[] } {
	const sizes = new Map<string, number | null>();
	const problems: string[] = [];
	for (const ledger of publishedLedgers() as LedgerName[]) {
		for (const period of COMPACT_PERIODS) {
			const index = indexPath(ledger, period);
			sizes.set(index, null);
			if (!existsSync(at(index))) {
				problems.push(`state/${index} is not in the build`);
				continue;
			}
			const reading = readIndex(JSON.parse(readFileSync(at(index), 'utf8')), ledger, period);
			if ('refused' in reading) {
				problems.push(`state/${index} is one the door will not act on: ${JSON.stringify(reading.refused)}`);
				continue;
			}
			for (const entry of reading.index.entries) sizes.set(dataPath(ledger, period, entry.covers), entry.bytes);
		}
	}
	return { sizes, problems };
}

test('THE ORACLE: every address a published index names is in the build, at the size it names', () => {
	expect(publishedLedgers().length, 'config/idhazh.json publishes no ledger').toBeGreaterThan(0);
	const { sizes, problems } = addressed();
	for (const [path, bytes] of sizes) {
		// An index has no size to check, and `addressed` has already read it.
		if (bytes === null) continue;
		if (!existsSync(at(path))) {
			problems.push(`state/${path} is named by its index and not in the build`);
			continue;
		}
		const size = statSync(at(path)).size;
		if (size !== bytes) problems.push(`state/${path} is ${size} bytes and its index says ${bytes}`);
	}
	expect(problems, 'a browser would get a 404 or a file the door refuses').toEqual([]);
	expect(
		[...sizes.values()].filter((bytes) => bytes !== null).length,
		'no published index names a file, so nothing here was checked'
	).toBeGreaterThan(0);
});

test('nothing else of state/ reaches the site: no raw day, no watermark, no other ledger', () => {
	const { sizes } = addressed();
	const built = filesUnder(STATE);
	expect(
		built.filter((path) => !path.startsWith('compact/')),
		'the raw tier, or anything outside the compact tier, is in the build'
	).toEqual([]);
	expect(
		built.filter((path) => !sizes.has(path)),
		'a file no published index names is in the build'
	).toEqual([]);
});

test('every published index is capped to the widest console span, anchored on its ledger data', () => {
	const appearance = JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8'));
	const widest = Math.max(...appearance.console.window_presets);
	for (const ledger of publishedLedgers() as LedgerName[]) {
		const daily = readIndex(
			JSON.parse(readFileSync(at(indexPath(ledger, 'daily')), 'utf8')),
			ledger,
			'daily'
		);
		expect('index' in daily && daily.index.entries.length, `${ledger} has no newest day`).toBeTruthy();
		if (!('index' in daily)) continue;
		const newest = Math.max(...daily.index.entries.map((entry) => dayNumber(entry.covers)));
		const first = newest - widest + 1;
		for (const period of COMPACT_PERIODS) {
			const reading = readIndex(JSON.parse(readFileSync(at(indexPath(ledger, period)), 'utf8')), ledger, period);
			expect('index' in reading, `${ledger} ${period} index is refused`).toBeTruthy();
			if (!('index' in reading)) continue;
			for (const entry of reading.index.entries) {
				const range = rangeFor(period, entry.covers);
				expect(
					range.last >= first && range.first <= newest,
					`${ledger} ${period} ${entry.covers} is outside the widest published span`
				).toBeTruthy();
			}
		}
	}
});

test('the ledger registry is copied verbatim to the site', () => {
	const committed = readFileSync(resolve(process.cwd(), '..', 'config', 'ledgers.json'), 'utf8');
	const staged = readFileSync(join(BUILD, 'config', 'ledgers.json'), 'utf8');
	expect(staged).toBe(committed);
});
