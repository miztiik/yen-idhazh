import { expect, test } from '@playwright/test';
import { mkdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { weighPayloads } from '../scripts/payload-ceilings.mjs';

/**
 * Which payload keys the bundle gate weighs, which keys fail it, and which it reports as not weighed.
 *
 * `scripts/payload-ceilings.mjs` gives the gate its answer, and the gate prints
 * that answer and fails on it. Each case below writes a small build tree and
 * reads the answer, so none of them needs a site build. Each case weighs a file
 * at its length on disk, so every number below is the length of a string the
 * case wrote; the gate passes its gzip -5 size instead.
 */

/** A build tree under this test's own output directory: build-relative path -> text. */
function aBuildTree(files: Record<string, string>): string {
	const root = test.info().outputPath('build');
	for (const [path, text] of Object.entries(files)) {
		const file = join(root, ...path.split('/'));
		mkdirSync(dirname(file), { recursive: true });
		writeFileSync(file, text);
	}
	return root;
}

function onDisk(file: string): number {
	return statSync(file).size;
}

test('a published ledger whose build holds none of its files is not weighed, and the answer names it', () => {
	const build = aBuildTree({
		'state/compact/seen/index/daily.json': 'daily',
		'state/compact/seen/index/monthly.json': 'monthly',
		'state/compact/seen/index/yearly.json': 'yearly'
	});
	const ceilings = { 'state/compact/item-health/index/': 2200, 'state/compact/seen/index/': 2200 };
	expect(weighPayloads(build, ceilings, ['item-health', 'seen'], '', onDisk)).toEqual({
		weighed: [
			{ key: 'state/compact/seen/index/', path: 'state/compact/seen/index/monthly.json', bytes: 7, ceiling: 2200 },
			{ key: 'state/compact/seen/index/', path: 'state/compact/seen/index/yearly.json', bytes: 6, ceiling: 2200 },
			{ key: 'state/compact/seen/index/', path: 'state/compact/seen/index/daily.json', bytes: 5, ceiling: 2200 }
		],
		over: [],
		namesNothing: [],
		notWeighed: [
			{
				key: 'state/compact/item-health/index/',
				reason:
					'item-health is not packed yet, so the build holds none of its files. ' +
					'If it was packed before, restore state/compact/item-health/ from git history.'
			}
		]
	});
});

test('a key that names nothing and belongs to no published ledger still fails', () => {
	const build = aBuildTree({ 'state/compact/seen/index/daily.json': 'daily' });
	const ceilings = {
		'console/band.json': 2000,
		'state/compact/feed-health/index/': 2200,
		'state/compact/seen/index/': 2200
	};
	expect(weighPayloads(build, ceilings, ['seen'], '', onDisk)).toEqual({
		weighed: [
			{ key: 'state/compact/seen/index/', path: 'state/compact/seen/index/daily.json', bytes: 5, ceiling: 2200 }
		],
		over: [],
		namesNothing: [
			{ key: 'console/band.json', ceiling: 2000 },
			{ key: 'state/compact/feed-health/index/', ceiling: 2200 }
		],
		notWeighed: []
	});
});

const filesWithNoIndex: Record<string, Record<string, string>> = {
	'a compact data file': { 'state/compact/item-health/daily/2026/10/01.parquet': 'PAR1' },
	'a listed raw day': {
		'state/raw/item-health/index/2026-10-02.json': '{}',
		'state/raw/item-health/2026/10/02/0001.parquet': 'PAR1'
	}
};

for (const [held, files] of Object.entries(filesWithNoIndex)) {
	test(`a published ledger with ${held} in the build and nothing at its index key still fails`, () => {
		const build = aBuildTree(files);
		expect(
			weighPayloads(build, { 'state/compact/item-health/index/': 2200 }, ['item-health'], '', onDisk)
		).toEqual({
			weighed: [],
			over: [],
			namesNothing: [{ key: 'state/compact/item-health/index/', ceiling: 2200 }],
			notWeighed: []
		});
	});
}

test('a file over its ceiling fails, a file at its ceiling does not, and a directory key bounds each file on its own', () => {
	const build = aBuildTree({
		'console/band.json': 'band',
		'telemetry/2026-09.csv': 'september',
		'telemetry/2026-10.csv': 'october'
	});
	expect(weighPayloads(build, { 'console/band.json': 4, 'telemetry/': 8 }, [], '', onDisk)).toEqual({
		weighed: [
			{ key: 'console/band.json', path: 'console/band.json', bytes: 4, ceiling: 4 },
			{ key: 'telemetry/', path: 'telemetry/2026-09.csv', bytes: 9, ceiling: 8 },
			{ key: 'telemetry/', path: 'telemetry/2026-10.csv', bytes: 7, ceiling: 8 }
		],
		over: [{ key: 'telemetry/', path: 'telemetry/2026-09.csv', bytes: 9, ceiling: 8 }],
		namesNothing: [],
		notWeighed: []
	});
});

test('with the ledgers served from another host, no key under state/ is weighed and every other key is', () => {
	const build = aBuildTree({ 'config/ledgers.json': '{}' });
	const ceilings = { 'config/ledgers.json': 3400, 'state/compact/seen/index/': 2200 };
	expect(weighPayloads(build, ceilings, ['seen'], 'https://ledgers.example.org', onDisk)).toEqual({
		weighed: [{ key: 'config/ledgers.json', path: 'config/ledgers.json', bytes: 2, ceiling: 3400 }],
		over: [],
		namesNothing: [],
		notWeighed: [
			{
				key: 'state/compact/seen/index/',
				reason: 'visuals.asset_base_url serves the published ledgers from https://ledgers.example.org'
			}
		]
	});
});
