import { expect, test } from '@playwright/test';
import { cpSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { ledgerCopy, publishedLedgers } from '../scripts/published-ledgers.mjs';
import { siteKeepsFrom, siteMayHaveTrimmed } from '../src/lib/data/site-window';
import { daysBetween } from '../src/lib/data/slice';

/**
 * Which files of `state/` the build copies for a published ledger, and when it stops.
 *
 * `scripts/published-ledgers.mjs` reads each published ledger's three indexes and
 * lists what they name; `copy-visuals.mjs` stages that list. Each case below
 * writes a small state tree holding one fault, or one stage of a ledger's life,
 * and reads the answer, so none of them needs a site build. What the built site
 * holds is `published-ledgers.spec.ts`.
 */

/** A state tree under this test's own output directory: path under the root -> text. */
function aStateTree(files: Record<string, string>, name = 'state'): string {
	const root = test.info().outputPath(name);
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

/** A whole ledger: all indexes, every file they name, and a stray file no index names. */
function aWholeLedger(ledger: string): Record<string, string> {
	return {
		[`compact/${ledger}/index/daily.json`]: anIndex(ledger, 'daily', ['2026-09-01', '2026-09-02']),
		[`compact/${ledger}/index/monthly.json`]: anIndex(ledger, 'monthly', ['2026-08']),
		[`compact/${ledger}/index/yearly.json`]: anIndex(ledger, 'yearly', ['2025']),
		[`compact/${ledger}/daily/2026/09/01.parquet`]: 'PAR1',
		[`compact/${ledger}/daily/2026/09/02.parquet`]: 'PAR1',
		[`compact/${ledger}/monthly/2026/08.parquet`]: 'PAR1',
		[`compact/${ledger}/yearly/2025/2025.parquet`]: 'PAR1',
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

/** A daily index naming every UTC day from `first` to `last`, each a day that held no row. */
function quietDays(ledger: string, first: string, last: string): string {
	const entries = daysBetween(first, last).map((covers) => ({ bytes: 0, covers, rows: 0, state: 'empty' }));
	return `${JSON.stringify({ entries, ledger, period: 'daily', version: '2026-10-04' }, null, 2)}\n`;
}

test('a 90-day copy keeps the entries that overlap 18 Mar to 15 Jun 2030, and the rule says when older days may be the archive\'s', () => {
	// Each root is a ledger whose newest day is 15 Jun 2030. Every expected value is written out.
	expect(siteKeepsFrom('2030-06-15', 90)).toBe('2030-03-18');
	const roots = [
		{ name: 'began-120-days-before', months: [], days: ['2030-02-15', '2030-06-15'], keptMonths: [], keptDays: ['2030-03-18', '2030-06-15', 90], siteFirst: '2030-03-18', mayHaveTrimmed: true },
		{ name: 'began-30-days-before', months: [], days: ['2030-05-16', '2030-06-15'], keptMonths: [], keptDays: ['2030-05-16', '2030-06-15', 31], siteFirst: '2030-05-16', mayHaveTrimmed: false },
		{ name: 'closed-months', months: ['2030-02', '2030-03'], days: ['2030-04-01', '2030-06-15'], keptMonths: ['2030-03'], keptDays: ['2030-04-01', '2030-06-15', 76], siteFirst: '2030-03-01', mayHaveTrimmed: true },
		// Nothing was dropped, but the site alone cannot tell: one needless archive read.
		{ name: 'began-on-the-first-kept-day', months: [], days: ['2030-03-18', '2030-06-15'], keptMonths: [], keptDays: ['2030-03-18', '2030-06-15', 90], siteFirst: '2030-03-18', mayHaveTrimmed: true }
	] as const;
	for (const root of roots) {
		const tree: Record<string, string> = {
			'compact/item-health/index/daily.json': quietDays('item-health', root.days[0], root.days[1]),
			'compact/item-health/index/monthly.json': anIndex('item-health', 'monthly', [...root.months]),
			'compact/item-health/index/yearly.json': anIndex('item-health', 'yearly', [])
		};
		for (const month of root.months) tree[`compact/item-health/monthly/${month.replace('-', '/')}.parquet`] = 'PAR1';
		const copy = ledgerCopy(aStateTree(tree, root.name), ['item-health'], 'state', 90);
		expect(copy.refused, root.name).toEqual([]);
		expect(copy.missing, root.name).toEqual([]);
		const days = coversIn(copy.indexes['compact/item-health/index/daily.json']);
		expect([days[0], days.at(-1), days.length], root.name).toEqual(root.keptDays);
		expect(coversIn(copy.indexes['compact/item-health/index/monthly.json']), root.name).toEqual(root.keptMonths);
		expect(siteMayHaveTrimmed(root.siteFirst, '2030-06-15', 90), root.name).toBe(root.mayHaveTrimmed);
	}
});

type Period = 'daily' | 'monthly' | 'yearly';

/** One index entry with every field the compaction writes. */
interface Entry {
	bytes: number;
	covers: string;
	lost_days: string[];
	rows: number;
	set_aside: number;
	state: 'packed' | 'empty' | 'lost';
}

function packed(covers: string, rows: number, more: Partial<Entry> = {}): Entry {
	return { bytes: 4, covers, lost_days: [], rows, set_aside: 0, state: 'packed', ...more };
}

function empty(covers: string): Entry {
	return { bytes: 0, covers, lost_days: [], rows: 0, set_aside: 0, state: 'empty' };
}

function lost(covers: string): Entry {
	return { bytes: 0, covers, lost_days: [], rows: 0, set_aside: 0, state: 'lost' };
}

/** An `empty` daily entry for every UTC day from `first` to `last`. */
function quiet(first: string, last: string): Entry[] {
	return daysBetween(first, last).map((covers) => empty(covers));
}

/** The file one entry names, under `compact/<ledger>/`. */
function fileOf(period: Period, covers: string): string {
	if (period === 'daily') return `daily/${covers.replaceAll('-', '/')}.parquet`;
	if (period === 'monthly') return `monthly/${covers.replace('-', '/')}.parquet`;
	return `yearly/${covers}/${covers}.parquet`;
}

/** A ledger whose three indexes hold exactly these entries, with a file for each packed one. */
function aLedgerHolding(ledger: string, indexes: Record<Period, Entry[]>): Record<string, string> {
	const tree: Record<string, string> = {};
	for (const period of ['daily', 'monthly', 'yearly'] as const) {
		const entries = indexes[period];
		tree[`compact/${ledger}/index/${period}.json`] =
			`${JSON.stringify({ entries, ledger, period, version: '2026-10-04' }, null, 2)}\n`;
		for (const entry of entries) {
			if (entry.state === 'packed') tree[`compact/${ledger}/${fileOf(period, entry.covers)}`] = 'PAR1';
		}
	}
	return tree;
}

const RAW_FILE = '01a0fbc4-1707-8428-b765-119571d6249f.parquet';
const INDEXES = [
	'compact/item-health/index/daily.json',
	'compact/item-health/index/monthly.json',
	'compact/item-health/index/yearly.json'
];

/**
 * Each stage of a ledger's life as the compaction leaves its indexes, copied with a 90-day
 * window. Every case writes out what the copy keeps and stages, the oldest day the site's
 * indexes then name, and what the shared trim rule says for that day. The rule's input is
 * written out too, so the copy and the rule are never checked against each other. A ledger
 * with no compact folder, and one trimmed for its age, have cases of their own in this file.
 */
interface Stage {
	stage: string;
	indexes: Record<Period, Entry[]>;
	/** Raw day folders, `YYYY/MM/DD`, each holding one writer file. */
	raw: string[];
	newest: string;
	kept: Record<Period, Entry[]>;
	/** Every data file and raw listing staged; the three indexes always are. */
	staged: string[];
	siteFirst: string;
	mayHaveTrimmed: boolean;
}

const STAGES: Stage[] = [
	{
		// A packed month with 0 rows is a file written before a quiet period got no file. It
		// is copied, so every entry the site's index names resolves.
		stage: 'a ledger that has never held a row',
		indexes: { daily: quiet('2026-10-01', '2026-10-15'), monthly: [packed('2026-09', 0)], yearly: [] },
		raw: [],
		newest: '2026-10-15',
		kept: { daily: quiet('2026-10-01', '2026-10-15'), monthly: [packed('2026-09', 0)], yearly: [] },
		staged: ['compact/item-health/monthly/2026/09.parquet'],
		siteFirst: '2026-09-01',
		mayHaveTrimmed: false
	},
	{
		// It began on 12 Aug 2026. Its month entry covers August from the 1st.
		stage: 'a ledger that began mid-month, once that month closed',
		indexes: { daily: quiet('2026-09-01', '2026-10-01'), monthly: [packed('2026-08', 3)], yearly: [] },
		raw: [],
		newest: '2026-10-01',
		kept: { daily: quiet('2026-09-01', '2026-10-01'), monthly: [packed('2026-08', 3)], yearly: [] },
		staged: ['compact/item-health/monthly/2026/08.parquet'],
		siteFirst: '2026-08-01',
		mayHaveTrimmed: false
	},
	{
		// It began on 12 Aug 2026, so nothing was dropped. Its year entry covers 2026 from
		// 1 January, which is on or before the first kept day, 6 Dec 2026, so the rule says
		// yes: one archive read that finds nothing.
		stage: 'a ledger whose first year packed, though it began in August',
		indexes: { daily: quiet('2027-02-01', '2027-03-05'), monthly: [empty('2027-01')], yearly: [packed('2026', 4)] },
		raw: [],
		newest: '2027-03-05',
		kept: { daily: quiet('2027-02-01', '2027-03-05'), monthly: [empty('2027-01')], yearly: [packed('2026', 4)] },
		staged: ['compact/item-health/yearly/2026/2026.parquet'],
		siteFirst: '2026-01-01',
		mayHaveTrimmed: true
	},
	{
		stage: 'a ledger whose writer paused and resumed',
		indexes: {
			daily: [packed('2026-09-01', 1), packed('2026-09-02', 1), packed('2026-09-03', 1), ...quiet('2026-09-04', '2026-09-08'), packed('2026-09-09', 1), packed('2026-09-10', 1)],
			monthly: [],
			yearly: []
		},
		raw: [],
		newest: '2026-09-10',
		kept: {
			daily: [packed('2026-09-01', 1), packed('2026-09-02', 1), packed('2026-09-03', 1), ...quiet('2026-09-04', '2026-09-08'), packed('2026-09-09', 1), packed('2026-09-10', 1)],
			monthly: [],
			yearly: []
		},
		staged: [
			'compact/item-health/daily/2026/09/01.parquet',
			'compact/item-health/daily/2026/09/02.parquet',
			'compact/item-health/daily/2026/09/03.parquet',
			'compact/item-health/daily/2026/09/09.parquet',
			'compact/item-health/daily/2026/09/10.parquet'
		],
		siteFirst: '2026-09-01',
		mayHaveTrimmed: false
	},
	{
		// Its writer stopped on 5 Aug 2026 and its quiet days went on to 10 Jan 2027. The copy
		// counts back from that quiet day, so August, which holds every row, and September end
		// before the first kept day, 13 Oct 2026: the site holds no row of it, and the rule
		// says the archive may.
		stage: 'a ledger whose writer stopped before the window began',
		indexes: {
			daily: quiet('2026-12-01', '2027-01-10'),
			monthly: [packed('2026-08', 4), empty('2026-09'), empty('2026-10'), empty('2026-11')],
			yearly: []
		},
		raw: [],
		newest: '2027-01-10',
		kept: { daily: quiet('2026-12-01', '2027-01-10'), monthly: [empty('2026-10'), empty('2026-11')], yearly: [] },
		staged: [],
		siteFirst: '2026-10-01',
		mayHaveTrimmed: true
	},
	{
		// Packing stopped after 2 Sep 2026 while the writer went on. The copy counts back from
		// the newest packed day, never from a raw day, and lists the raw days after it.
		stage: 'a ledger whose packing paused while its writer went on',
		indexes: { daily: [packed('2026-09-01', 1), packed('2026-09-02', 1)], monthly: [], yearly: [] },
		raw: ['2026/09/03', '2026/09/04', '2026/09/05'],
		newest: '2026-09-02',
		kept: { daily: [packed('2026-09-01', 1), packed('2026-09-02', 1)], monthly: [], yearly: [] },
		staged: [
			'compact/item-health/daily/2026/09/01.parquet',
			'compact/item-health/daily/2026/09/02.parquet',
			`raw/item-health/2026/09/03/${RAW_FILE}`,
			`raw/item-health/2026/09/04/${RAW_FILE}`,
			`raw/item-health/2026/09/05/${RAW_FILE}`,
			'raw/item-health/index/2026-09-03.json',
			'raw/item-health/index/2026-09-04.json',
			'raw/item-health/index/2026-09-05.json'
		],
		siteFirst: '2026-09-01',
		mayHaveTrimmed: false
	},
	{
		// A lost day and a month's lost days and set-aside count stay on their entries, and a
		// lost day names no file.
		stage: 'a ledger that lost days and set files aside',
		indexes: {
			daily: [packed('2026-10-01', 1), lost('2026-10-02'), packed('2026-10-03', 1)],
			monthly: [packed('2026-09', 5, { lost_days: ['2026-09-07'], set_aside: 2 })],
			yearly: []
		},
		raw: [],
		newest: '2026-10-03',
		kept: {
			daily: [packed('2026-10-01', 1), lost('2026-10-02'), packed('2026-10-03', 1)],
			monthly: [packed('2026-09', 5, { lost_days: ['2026-09-07'], set_aside: 2 })],
			yearly: []
		},
		staged: [
			'compact/item-health/daily/2026/10/01.parquet',
			'compact/item-health/daily/2026/10/03.parquet',
			'compact/item-health/monthly/2026/09.parquet'
		],
		siteFirst: '2026-09-01',
		mayHaveTrimmed: false
	}
];

for (const each of STAGES) {
	test(`${each.stage}: the copy keeps what its indexes record, and the trim rule says ${each.mayHaveTrimmed ? 'yes' : 'no'}`, () => {
		const tree = aLedgerHolding('item-health', each.indexes);
		for (const day of each.raw) tree[`raw/item-health/${day}/${RAW_FILE}`] = 'PAR1';
		const copy = ledgerCopy(aStateTree(tree), ['item-health'], 'state', 90);
		expect(copy.refused).toEqual([]);
		expect(copy.missing).toEqual([]);
		expect(copy.logs).toEqual([]);
		expect(copy.files).toEqual([...INDEXES, ...each.staged].sort());
		for (const period of ['daily', 'monthly', 'yearly'] as const) {
			const index = JSON.parse(copy.indexes[`compact/item-health/index/${period}.json`]);
			expect(index.entries, period).toEqual(each.kept[period]);
		}
		expect(siteMayHaveTrimmed(each.siteFirst, each.newest, 90)).toBe(each.mayHaveTrimmed);
	});
}

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
		const copy = ledgerCopy(aStateTree(tree), ['summary-quality-evals']);
		expect(copy.refused).toEqual([
			`summary-quality-evals: state/compact/summary-quality-evals/index/${period}.json is missing`
		]);
	});
}

test('a published ledger with no compact folder stages nothing, stops nothing, and the build log names it once', () => {
	// item-health has written a raw day and has never been packed: the state every ledger starts in.
	const tree = aWholeLedger('summary-quality-evals');
	tree['raw/item-health/2026/09/02/01a0fbc4-1707-8428-b765-119571d6249f.parquet'] = 'PAR1';
	const copy = ledgerCopy(aStateTree(tree), ['item-health', 'summary-quality-evals']);
	expect(copy.refused).toEqual([]);
	expect(copy.missing).toEqual([]);
	expect(copy.logs).toEqual([
		'published ledgers: state/compact/item-health/ is not there, so item-health is not packed yet and the site ' +
			'holds none of its files. If it was packed before, restore that folder from git history.'
	]);
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
});

test('a ledger with only its daily index still stops the build, once for each index it lacks', () => {
	const copy = ledgerCopy(
		aStateTree({
			'compact/item-health/index/daily.json': anIndex('item-health', 'daily', ['2026-09-01']),
			'compact/item-health/daily/2026/09/01.parquet': 'PAR1'
		}),
		['item-health']
	);
	expect(copy.refused).toEqual([
		'item-health: state/compact/item-health/index/monthly.json is missing',
		'item-health: state/compact/item-health/index/yearly.json is missing'
	]);
	expect(copy.logs).toEqual([]);
	expect(copy.files).toEqual([]);
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
	// The fixture's two writer files are 4 and 8 bytes long. Its listing, which an older
	// compaction wrote, carries the digest below: SHA-256 over the two names joined with one
	// newline, which `backend/tests/contracts/test_raw_day_listing_fixture.py` checks against
	// the Python rule.
	const first = '01a0fbc4-1707-8428-b765-119571d6249f.parquet';
	const second = '01a0fca4-b1cd-8c8b-a2ea-b2f6f3a7e52e.parquet';
	const fixtureDay = join(process.cwd(), '..', 'tests', 'fixtures', 'raw-day-listing', 'state', 'raw', 'item-health', '2026', '09', '02');
	const root = aStateTree({
		'compact/item-health/index/daily.json': anIndex('item-health', 'daily', ['2026-09-01']),
		'compact/item-health/index/monthly.json': anIndex('item-health', 'monthly', []),
		'compact/item-health/index/yearly.json': anIndex('item-health', 'yearly', []),
		'compact/item-health/daily/2026/09/01.parquet': 'PAR1'
	});
	const targetDay = join(root, 'raw', 'item-health', '2026', '09', '02');
	mkdirSync(targetDay, { recursive: true });
	for (const name of [first, second]) cpSync(join(fixtureDay, name), join(targetDay, name));

	const copy = ledgerCopy(root, ['item-health']);
	const staged = JSON.parse(copy.indexes['raw/item-health/index/2026-09-02.json']);
	expect(staged).toMatchObject({
		ledger: 'item-health',
		date: '2026-09-02',
		files: [first, second],
		content_sha256: 'd68833c946407d8c06fe5835c706cc425a3891d3e95f410652d0f7b5a6598495',
		bytes: [4, 8]
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
