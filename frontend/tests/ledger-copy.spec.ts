import { expect, test } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { ledgerCopy, publishedLedgers } from '../scripts/published-ledgers.mjs';

/**
 * Which files of `state/` the build copies for a published ledger, and when it stops.
 *
 * `scripts/published-ledgers.mjs` reads each published ledger's two indexes and
 * lists what they name; `copy-visuals.mjs` stages that list. Each case below
 * writes a small state tree holding one fault and reads the answer, so none of
 * them needs a site build. What the built site holds is
 * `published-ledgers.spec.ts`.
 */

/** A state tree under this test's own output directory: path under the root -> text. */
function aStateTree(files: Record<string, string>): string {
	const root = test.info().outputPath('state');
	for (const [path, text] of Object.entries(files)) {
		const file = join(root, ...path.split('/'));
		mkdirSync(dirname(file), { recursive: true });
		writeFileSync(file, text);
	}
	return root;
}

/** An index as the compaction writes one, naming these periods. */
function anIndex(ledger: string, period: 'daily' | 'monthly', covers: string[]): string {
	const entries = covers.map((each) => ({ bytes: 4, covers: each, rows: 1 }));
	return `${JSON.stringify({ entries, ledger, period, version: '2026-09-27' }, null, 2)}\n`;
}

/** A whole ledger: both indexes, every file they name, the watermark beside them and a stray file. */
function aWholeLedger(ledger: string): Record<string, string> {
	return {
		[`compact/${ledger}/index/daily.json`]: anIndex(ledger, 'daily', ['2026-09-01', '2026-09-02']),
		[`compact/${ledger}/index/monthly.json`]: anIndex(ledger, 'monthly', ['2026-08']),
		[`compact/${ledger}/daily/2026/09/01.parquet`]: 'PAR1',
		[`compact/${ledger}/daily/2026/09/02.parquet`]: 'PAR1',
		[`compact/${ledger}/monthly/2026/08.parquet`]: 'PAR1',
		[`compact/${ledger}/daily/watermark.json`]: '{}\n',
		[`compact/${ledger}/daily/2026/09/03.parquet`]: 'PAR1',
		[`raw/${ledger}/2026/09/03/2026-09-03-1-work-00.parquet`]: 'PAR1'
	};
}

test('a whole ledger publishes its two indexes and the files they name, and nothing else', () => {
	const copy = ledgerCopy(aStateTree(aWholeLedger('scores')), ['scores']);
	expect(copy).toEqual({
		files: [
			'compact/scores/daily/2026/09/01.parquet',
			'compact/scores/daily/2026/09/02.parquet',
			'compact/scores/index/daily.json',
			'compact/scores/index/monthly.json',
			'compact/scores/monthly/2026/08.parquet'
		],
		refused: [],
		missing: []
	});
});

test('a ledger missing either index stops the build, naming the ledger and the file', () => {
	const tree = aWholeLedger('scores');
	delete tree['compact/scores/index/monthly.json'];
	const copy = ledgerCopy(aStateTree(tree), ['scores', 'item-health']);
	expect(copy.refused).toEqual([
		'scores: state/compact/scores/index/monthly.json is missing',
		'item-health: state/compact/item-health/index/daily.json is missing',
		'item-health: state/compact/item-health/index/monthly.json is missing'
	]);
});

test('a file an index names and the tree lacks is reported, and the rest still ships', () => {
	const tree = aWholeLedger('host-fingerprint');
	delete tree['compact/host-fingerprint/daily/2026/09/02.parquet'];
	const copy = ledgerCopy(aStateTree(tree), ['host-fingerprint']);
	expect(copy.refused).toEqual([]);
	expect(copy.missing).toEqual(['compact/host-fingerprint/daily/2026/09/02.parquet']);
	expect(copy.files).toContain('compact/host-fingerprint/daily/2026/09/01.parquet');
	expect(copy.files).not.toContain('compact/host-fingerprint/daily/2026/09/02.parquet');
});

test('an index that is not this ledger\'s, or names a path rather than a day, stops the build', () => {
	const tree = aWholeLedger('scores');
	tree['compact/scores/index/daily.json'] = anIndex('item-health', 'daily', ['2026-09-01']);
	tree['compact/scores/index/monthly.json'] = anIndex('scores', 'monthly', ['../../../escape']);
	const copy = ledgerCopy(aStateTree(tree), ['scores']);
	expect(copy.refused).toEqual([
		'scores: state/compact/scores/index/daily.json describes item-health daily, not scores daily',
		'scores: state/compact/scores/index/monthly.json names "../../../escape", which is not a UTC month'
	]);
	expect(copy.files).toEqual([]);
});

test('a state root that is not there stops the build when a ledger is published, and only then', () => {
	const gone = join(test.info().outputPath('nowhere'), 'state');
	expect(ledgerCopy(gone, ['scores']).refused).toEqual([
		`the state root ${gone} is not there, and ledger.published names scores`
	]);
	expect(ledgerCopy(gone, [])).toEqual({ files: [], refused: [], missing: [] });
});

test('the published list is read from the config, and a name that is not a ledger name is refused', () => {
	const config = test.info().outputPath('idhazh.json');
	mkdirSync(dirname(config), { recursive: true });
	writeFileSync(config, JSON.stringify({ ledger: { published: ['host-fingerprint', 'scores'] } }));
	expect(publishedLedgers(config)).toEqual(['host-fingerprint', 'scores']);
	writeFileSync(config, JSON.stringify({ ledger: {} }));
	expect(publishedLedgers(config)).toEqual([]);
	writeFileSync(config, JSON.stringify({ ledger: { published: ['../scores'] } }));
	expect(() => publishedLedgers(config)).toThrow('which is not a ledger name');
});
