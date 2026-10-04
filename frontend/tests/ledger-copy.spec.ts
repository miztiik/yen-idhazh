import { expect, test } from '@playwright/test';
import { cpSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { ledgerCopy, publishedLedgers } from '../scripts/published-ledgers.mjs';

/**
 * Which files of `state/` the build copies for a published ledger, and when it stops.
 *
 * `scripts/published-ledgers.mjs` reads each published ledger's three indexes and
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
function anIndex(ledger: string, period: 'daily' | 'monthly' | 'yearly', covers: string[]): string {
	const entries = covers.map((each) => ({ bytes: 4, covers: each, rows: 1 }));
	return `${JSON.stringify({ entries, ledger, period, version: '2026-09-27' }, null, 2)}\n`;
}

function coversIn(index: string): string[] {
	return (JSON.parse(index).entries as { covers: string }[]).map((entry) => entry.covers);
}

/** A whole ledger: all indexes, every file they name, the watermark beside them and a stray file. */
function aWholeLedger(ledger: string): Record<string, string> {
	return {
		[`compact/${ledger}/index/daily.json`]: anIndex(ledger, 'daily', ['2026-09-01', '2026-09-02']),
		[`compact/${ledger}/index/monthly.json`]: anIndex(ledger, 'monthly', ['2026-08']),
		[`compact/${ledger}/index/yearly.json`]: anIndex(ledger, 'yearly', ['2025']),
		[`compact/${ledger}/daily/2026/09/01.parquet`]: 'PAR1',
		[`compact/${ledger}/daily/2026/09/02.parquet`]: 'PAR1',
		[`compact/${ledger}/monthly/2026/08.parquet`]: 'PAR1',
		[`compact/${ledger}/yearly/2025/2025.parquet`]: 'PAR1',
		[`compact/${ledger}/daily/watermark.json`]: '{}\n',
		[`compact/${ledger}/daily/2026/09/03.parquet`]: 'PAR1'
	};
}

test('a whole ledger publishes its three indexes and the files they name, and nothing else', () => {
	const copy = ledgerCopy(aStateTree(aWholeLedger('summary-quality-evals')), ['summary-quality-evals']);
	expect(copy.files).toEqual([
		'compact/summary-quality-evals/daily/2026/09/01.parquet',
		'compact/summary-quality-evals/daily/2026/09/02.parquet',
		'compact/summary-quality-evals/index/daily.json',
		'compact/summary-quality-evals/index/monthly.json',
		'compact/summary-quality-evals/index/yearly.json',
		'compact/summary-quality-evals/monthly/2026/08.parquet'
	]);
	expect(Object.keys(copy.indexes).sort()).toEqual([
		'compact/summary-quality-evals/index/daily.json',
		'compact/summary-quality-evals/index/monthly.json',
		'compact/summary-quality-evals/index/yearly.json'
	]);
	expect(copy).toMatchObject({
		files: [
			'compact/summary-quality-evals/daily/2026/09/01.parquet',
			'compact/summary-quality-evals/daily/2026/09/02.parquet',
			'compact/summary-quality-evals/index/daily.json',
			'compact/summary-quality-evals/index/monthly.json',
			'compact/summary-quality-evals/index/yearly.json',
			'compact/summary-quality-evals/monthly/2026/08.parquet'
		],
		refused: [],
		missing: []
	});
});

test('the copy is capped from the newest packed day and trims each index to the copied files', () => {
	const tree = {
		'compact/item-health/index/daily.json': anIndex('item-health', 'daily', [
			'2026-05-31',
			'2026-06-02',
			'2026-08-30'
		]),
		'compact/item-health/index/monthly.json': anIndex('item-health', 'monthly', ['2026-05', '2026-06']),
		'compact/item-health/index/yearly.json': anIndex('item-health', 'yearly', ['2025']),
		'compact/item-health/daily/2026/05/31.parquet': 'PAR1',
		'compact/item-health/daily/2026/06/02.parquet': 'PAR1',
		'compact/item-health/daily/2026/08/30.parquet': 'PAR1',
		'compact/item-health/monthly/2026/05.parquet': 'PAR1',
		'compact/item-health/monthly/2026/06.parquet': 'PAR1',
		'compact/item-health/yearly/2025/2025.parquet': 'PAR1'
	};
	const copy = ledgerCopy(aStateTree(tree), ['item-health']);
	expect(copy.files).toEqual([
		'compact/item-health/daily/2026/06/02.parquet',
		'compact/item-health/daily/2026/08/30.parquet',
		'compact/item-health/index/daily.json',
		'compact/item-health/index/monthly.json',
		'compact/item-health/index/yearly.json',
		'compact/item-health/monthly/2026/06.parquet'
	]);
	expect(coversIn(copy.indexes['compact/item-health/index/daily.json'])).toEqual([
		'2026-06-02',
		'2026-08-30'
	]);
	expect(coversIn(copy.indexes['compact/item-health/index/monthly.json'])).toEqual([
		'2026-06'
	]);
	expect(JSON.parse(copy.indexes['compact/item-health/index/yearly.json']).entries).toEqual([]);
});

test('an empty daily index anchors on the newest month and copies that month file', () => {
	const tree = {
		'compact/candidate-models/index/daily.json': anIndex('candidate-models', 'daily', []),
		'compact/candidate-models/index/monthly.json': anIndex('candidate-models', 'monthly', ['2026-06']),
		'compact/candidate-models/index/yearly.json': anIndex('candidate-models', 'yearly', ['2025']),
		'compact/candidate-models/monthly/2026/06.parquet': 'PAR1',
		'compact/candidate-models/yearly/2025/2025.parquet': 'PAR1'
	};
	const copy = ledgerCopy(aStateTree(tree), ['candidate-models']);
	expect(copy.refused).toEqual([]);
	expect(copy.files).toEqual([
		'compact/candidate-models/index/daily.json',
		'compact/candidate-models/index/monthly.json',
		'compact/candidate-models/index/yearly.json',
		'compact/candidate-models/monthly/2026/06.parquet'
	]);
	expect(coversIn(copy.indexes['compact/candidate-models/index/daily.json'])).toEqual([]);
	expect(coversIn(copy.indexes['compact/candidate-models/index/monthly.json'])).toEqual(['2026-06']);
	expect(coversIn(copy.indexes['compact/candidate-models/index/yearly.json'])).toEqual([]);
});

test('a ledger with three empty indexes stages the indexes and no data', () => {
	const tree = {
		'compact/candidate-models/index/daily.json': anIndex('candidate-models', 'daily', []),
		'compact/candidate-models/index/monthly.json': anIndex('candidate-models', 'monthly', []),
		'compact/candidate-models/index/yearly.json': anIndex('candidate-models', 'yearly', [])
	};
	const copy = ledgerCopy(aStateTree(tree), ['candidate-models']);
	expect(copy.refused).toEqual([]);
	expect(copy.missing).toEqual([]);
	expect(copy.files).toEqual([
		'compact/candidate-models/index/daily.json',
		'compact/candidate-models/index/monthly.json',
		'compact/candidate-models/index/yearly.json'
	]);
});

for (const period of ['daily', 'monthly', 'yearly']) {
	test(`a ledger missing its ${period} index stops the build, naming the ledger and the file`, () => {
		const tree = aWholeLedger('summary-quality-evals');
		delete tree[`compact/summary-quality-evals/index/${period}.json`];
		const copy = ledgerCopy(aStateTree(tree), ['summary-quality-evals', 'item-health']);
		expect(copy.refused).toEqual([
			`summary-quality-evals: state/compact/summary-quality-evals/index/${period}.json is missing`,
			'item-health: state/compact/item-health/index/daily.json is missing',
			'item-health: state/compact/item-health/index/monthly.json is missing',
			'item-health: state/compact/item-health/index/yearly.json is missing'
		]);
	});
}

test('a file an index names and the tree lacks is reported, and the rest still ships', () => {
	const tree = aWholeLedger('host-fingerprint');
	delete tree['compact/host-fingerprint/daily/2026/09/02.parquet'];
	const copy = ledgerCopy(aStateTree(tree), ['host-fingerprint']);
	expect(copy.refused).toEqual([]);
	expect(copy.missing).toEqual(['compact/host-fingerprint/daily/2026/09/02.parquet']);
	expect(copy.files).toContain('compact/host-fingerprint/daily/2026/09/01.parquet');
	expect(copy.files).not.toContain('compact/host-fingerprint/daily/2026/09/02.parquet');
});

test('an empty or a lost day stays in its index and names no file, so none is copied or missing', () => {
	const tree = aWholeLedger('host-fingerprint');
	const entries = [
		{ bytes: 4, covers: '2026-09-01', rows: 1 },
		{ bytes: 0, covers: '2026-09-02', rows: 0, state: 'empty' },
		{ bytes: 0, covers: '2026-09-03', rows: 0, state: 'lost' }
	];
	tree['compact/host-fingerprint/index/daily.json'] = `${JSON.stringify(
		{ entries, ledger: 'host-fingerprint', period: 'daily', version: '2026-10-04' },
		null,
		2
	)}\n`;
	delete tree['compact/host-fingerprint/daily/2026/09/02.parquet'];
	delete tree['compact/host-fingerprint/daily/2026/09/03.parquet'];
	const copy = ledgerCopy(aStateTree(tree), ['host-fingerprint']);
	expect(copy.refused).toEqual([]);
	expect(copy.missing).toEqual([]);
	expect(copy.files.filter((file) => file.startsWith('compact/host-fingerprint/daily/'))).toEqual([
		'compact/host-fingerprint/daily/2026/09/01.parquet'
	]);
	expect(coversIn(copy.indexes['compact/host-fingerprint/index/daily.json'])).toEqual([
		'2026-09-01',
		'2026-09-02',
		'2026-09-03'
	]);
});

test('an index that is not this ledger\'s, or names a path rather than a day, stops the build', () => {
	const tree = aWholeLedger('summary-quality-evals');
	tree['compact/summary-quality-evals/index/daily.json'] = anIndex('item-health', 'daily', ['2026-09-01']);
	tree['compact/summary-quality-evals/index/monthly.json'] = anIndex('summary-quality-evals', 'monthly', ['../../../escape']);
	tree['compact/summary-quality-evals/index/yearly.json'] = anIndex('summary-quality-evals', 'yearly', ['../../escape']);
	const copy = ledgerCopy(aStateTree(tree), ['summary-quality-evals']);
	expect(copy.refused).toEqual([
		'summary-quality-evals: state/compact/summary-quality-evals/index/daily.json describes item-health daily, not summary-quality-evals daily',
		'summary-quality-evals: state/compact/summary-quality-evals/index/monthly.json names "../../../escape", which is not a UTC month',
		'summary-quality-evals: state/compact/summary-quality-evals/index/yearly.json names "../../escape", which is not a UTC year'
	]);
	expect(copy.files).toEqual([]);
});

test('a state root that is not there stops the build when a ledger is published, and only then', () => {
	const gone = join(test.info().outputPath('nowhere'), 'state');
	expect(ledgerCopy(gone, ['summary-quality-evals']).refused).toEqual([
		'the state root state/ is not there, and ledger.published names summary-quality-evals'
	]);
	expect(ledgerCopy(gone, [])).toEqual({ files: [], indexes: {}, refused: [], missing: [], logs: [] });
});

test('a refusal names the state root the way the build was told to, never by its absolute path', () => {
	// The canary build reads its own tree, and a line saying `state/` would send
	// whoever reads it to the real one.
	const tree = aWholeLedger('summary-quality-evals');
	delete tree['compact/summary-quality-evals/index/monthly.json'];
	expect(ledgerCopy(aStateTree(tree), ['summary-quality-evals'], 'backend/var/canary/state').refused).toEqual([
		'summary-quality-evals: backend/var/canary/state/compact/summary-quality-evals/index/monthly.json is missing'
	]);
	const gone = join(test.info().outputPath('nowhere'), 'state');
	expect(ledgerCopy(gone, ['summary-quality-evals'], 'backend/var/canary/state').refused).toEqual([
		'the state root backend/var/canary/state/ is not there, and ledger.published names summary-quality-evals'
	]);
});

test('the published list is read from the config, and a name that is not a ledger name is refused', () => {
	const config = test.info().outputPath('idhazh.json');
	mkdirSync(dirname(config), { recursive: true });
	writeFileSync(config, JSON.stringify({ ledger: { published: ['host-fingerprint', 'summary-quality-evals'] } }));
	expect(publishedLedgers(config)).toEqual(['host-fingerprint', 'summary-quality-evals']);
	writeFileSync(config, JSON.stringify({ ledger: {} }));
	expect(publishedLedgers(config)).toEqual([]);
	writeFileSync(config, JSON.stringify({ ledger: { published: ['../summary-quality-evals'] } }));
	expect(() => publishedLedgers(config)).toThrow('which is not a ledger name');
});

test('raw days after the newest packed day are listed through the newest raw day, with sizes', () => {
	const first = '01a0fbc4-1707-8428-b765-119571d6249f.parquet';
	const second = '01a0fca4-b1cd-8c8b-a2ea-b2f6f3a7e52e.parquet';
	const copy = ledgerCopy(
		aStateTree({
			'compact/item-health/index/daily.json': anIndex('item-health', 'daily', ['2026-09-01']),
			'compact/item-health/index/monthly.json': anIndex('item-health', 'monthly', []),
			'compact/item-health/index/yearly.json': anIndex('item-health', 'yearly', []),
			'compact/item-health/daily/2026/09/01.parquet': 'PAR1',
			[`raw/item-health/2026/09/02/${second}`]: 'PAR1',
			[`raw/item-health/2026/09/02/${first}`]: 'PAR12345',
			[`raw/item-health/2026/09/04/${first}`]: 'PAR12'
		}),
		['item-health']
	);
	const listed = JSON.parse(copy.indexes['raw/item-health/index/2026-09-02.json']);
	expect(copy.refused).toEqual([]);
	expect(copy.files).toContain(`raw/item-health/2026/09/02/${first}`);
	expect(copy.files).toContain(`raw/item-health/2026/09/02/${second}`);
	expect(copy.files).toContain('raw/item-health/index/2026-09-03.json');
	expect(copy.files).toContain('raw/item-health/index/2026-09-04.json');
	expect(listed).toMatchObject({
		ledger: 'item-health',
		date: '2026-09-02',
		files: [first, second],
		bytes: [8, 4]
	});
	expect(listed).not.toHaveProperty('version');
	expect(listed.listed_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
	expect(JSON.parse(copy.indexes['raw/item-health/index/2026-09-03.json']).files).toEqual([]);
	expect(JSON.parse(copy.indexes['raw/item-health/index/2026-09-04.json']).bytes).toEqual([5]);
});

test('the build listing keeps the compaction listing digest and adds file sizes', () => {
	const fixtureRoot = join(process.cwd(), '..', 'tests', 'fixtures', 'raw-day-listing', 'state', 'raw', 'item-health');
	const fixtureDay = join(fixtureRoot, '2026', '09', '02');
	const root = aStateTree({
		'compact/item-health/index/daily.json': anIndex('item-health', 'daily', ['2026-09-01']),
		'compact/item-health/index/monthly.json': anIndex('item-health', 'monthly', []),
		'compact/item-health/index/yearly.json': anIndex('item-health', 'yearly', []),
		'compact/item-health/daily/2026/09/01.parquet': 'PAR1'
	});
	const targetDay = join(root, 'raw', 'item-health', '2026', '09', '02');
	mkdirSync(targetDay, { recursive: true });
	for (const name of ['01a0fbc4-1707-8428-b765-119571d6249f.parquet', '01a0fca4-b1cd-8c8b-a2ea-b2f6f3a7e52e.parquet']) {
		cpSync(join(fixtureDay, name), join(targetDay, name));
	}

	const copy = ledgerCopy(root, ['item-health']);
	const staged = JSON.parse(copy.indexes['raw/item-health/index/2026-09-02.json']);
	const fixture = JSON.parse(readFileSync(join(fixtureRoot, 'index', '2026-09-02.json'), 'utf8'));
	expect(staged).toMatchObject({
		ledger: fixture.ledger,
		date: fixture.date,
		files: fixture.files,
		content_sha256: fixture.content_sha256,
		bytes: fixture.files.map((name: string) => statSync(join(fixtureDay, name)).size)
	});
	expect(staged).not.toHaveProperty('version');
});

test('a raw day holding a non-parquet writer file is left unlisted and named in the build log', () => {
	const parquet = '01a0fbc4-1707-8428-b765-119571d6249f.parquet';
	const json = '01a0fbc4-1707-8428-b765-119571d6249f.json';
	const copy = ledgerCopy(
		aStateTree({
			'compact/seen/index/daily.json': anIndex('seen', 'daily', ['2026-09-01']),
			'compact/seen/index/monthly.json': anIndex('seen', 'monthly', []),
			'compact/seen/index/yearly.json': anIndex('seen', 'yearly', []),
			'compact/seen/daily/2026/09/01.parquet': 'PAR1',
			[`raw/seen/2026/09/02/${parquet}`]: 'PAR1',
			[`raw/seen/2026/09/02/${json}`]: '{}\n'
		}),
		['seen']
	);
	expect(copy.files).not.toContain('raw/seen/index/2026-09-02.json');
	expect(copy.files).not.toContain(`raw/seen/2026/09/02/${parquet}`);
	expect(copy.logs).toEqual([
		'published ledgers: state/raw/seen/2026/09/02/01a0fbc4-1707-8428-b765-119571d6249f.json is not parquet; 2026-09-02 is left unlisted.'
	]);
});

test('a ledger with no packed day stages no raw listings and logs the skipped walk', () => {
	const copy = ledgerCopy(
		aStateTree({
			'compact/candidate-models/index/daily.json': anIndex('candidate-models', 'daily', []),
			'compact/candidate-models/index/monthly.json': anIndex('candidate-models', 'monthly', []),
			'compact/candidate-models/index/yearly.json': anIndex('candidate-models', 'yearly', []),
			'raw/candidate-models/2026/09/02/01a0fbc4-1707-8428-b765-119571d6249f.parquet': 'PAR1'
		}),
		['candidate-models']
	);
	expect(copy.files).toEqual([
		'compact/candidate-models/index/daily.json',
		'compact/candidate-models/index/monthly.json',
		'compact/candidate-models/index/yearly.json'
	]);
	expect(copy.logs).toEqual([
		'published ledgers: candidate-models has no packed day; raw-day walk skipped.'
	]);
});

test('a raw directory inside the widest window is listed even when its date is after today', () => {
	const file = '01a0fbc4-1707-8428-b765-119571d6249f.parquet';
	const copy = ledgerCopy(
		aStateTree({
			'compact/item-health/index/daily.json': anIndex('item-health', 'daily', ['2099-01-01']),
			'compact/item-health/index/monthly.json': anIndex('item-health', 'monthly', []),
			'compact/item-health/index/yearly.json': anIndex('item-health', 'yearly', []),
			'compact/item-health/daily/2099/01/01.parquet': 'PAR1',
			[`raw/item-health/2099/01/02/${file}`]: 'PAR1'
		}),
		['item-health']
	);
	expect(copy.files).toContain('raw/item-health/index/2099-01-02.json');
	expect(copy.files).toContain(`raw/item-health/2099/01/02/${file}`);
});
