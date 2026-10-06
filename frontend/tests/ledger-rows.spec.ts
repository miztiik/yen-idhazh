import { expect, test } from '@playwright/test';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { recordingNotes, recordNotes, type RecordNote, type RecordRead } from '../src/lib/console/recording';
import { checkedRequest, type Row } from '../src/lib/data/slice-shapes';
import { HOST_FINGERPRINT_COLUMNS, machineRecord } from '../src/lib/server/host-fingerprint';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { datedFirst, ITEM_HEALTH_COLUMNS, SCORE_COLUMNS } from '../src/lib/server/ledger-rows';
import { serverCompiler } from './support/server-render';

/**
 * How a console route reads a packed record at build time, and what it says
 * about the read.
 *
 * The readers are driven over the query door's own fixture under
 * `tests/fixtures/ledger-door/`, through the machine record: the article and
 * score records take the same path with other columns. Each case reads inside
 * the test that asks, and a case that needs a tree the fixture does not hold
 * builds it in a temporary directory from the fixture's own files, so nothing
 * here grows with the archive (`CLAUDE.md` section 13). Nothing touches the
 * network but the engine, whose first query on a machine downloads its parquet
 * add-on (owner ruling, 2026-09-28).
 *
 * The fixture holds daily files for 2026-08-31, 09-01, 09-02 and 09-05, a
 * zero-row day on 09-03, a hole on 09-04, and a monthly file for 2026-08. A
 * tree that needs a period the packing could not fill records the zero-row day
 * `empty` and the hole `lost`, as the packing now does.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(here, '..', '..', 'tests', 'fixtures', 'ledger-door', 'state');
const PACKED = path.join('compact', 'host-fingerprint');

/** One daily index entry, as the packing writes it. */
type DayEntry = { covers: string; rows: number; bytes: number; state?: 'packed' | 'empty' | 'lost'; set_aside?: number };

/** The fixture's daily entries, as its index names them. */
function fixtureDays(): DayEntry[] {
	return (JSON.parse(readFileSync(path.join(FIXTURE, PACKED, 'index', 'daily.json'), 'utf8')) as { entries: DayEntry[] })
		.entries;
}

/** A state tree whose daily index names `entries`, each one that has a file copied from the
 *  fixture, and a month and a year index that name nothing, as the packing writes them. */
function packedTree(entries: readonly DayEntry[]): string {
	const root = mkdtempSync(path.join(tmpdir(), 'idhazh-packed-'));
	for (const entry of entries) {
		if (entry.state !== undefined && entry.state !== 'packed') continue;
		const [year, month, day] = entry.covers.split('-');
		const at = path.join(root, PACKED, 'daily', year, month);
		mkdirSync(at, { recursive: true });
		copyFileSync(path.join(FIXTURE, PACKED, 'daily', year, month, `${day}.parquet`), path.join(at, `${day}.parquet`));
	}
	const daily = JSON.parse(readFileSync(path.join(FIXTURE, PACKED, 'index', 'daily.json'), 'utf8')) as object;
	mkdirSync(path.join(root, PACKED, 'index'), { recursive: true });
	writeFileSync(path.join(root, PACKED, 'index', 'daily.json'), JSON.stringify({ ...daily, entries }));
	for (const period of ['monthly', 'yearly']) {
		const coarser = JSON.parse(readFileSync(path.join(FIXTURE, PACKED, 'index', `${period}.json`), 'utf8')) as object;
		writeFileSync(path.join(root, PACKED, 'index', `${period}.json`), JSON.stringify({ ...coarser, entries: [] }));
	}
	return root;
}

/** A state tree holding only the fixture's packed days up to and including `through`. */
function packedUpTo(through: string): string {
	return packedTree(fixtureDays().filter((entry) => entry.covers <= through));
}

/** The fixture's day `covers`, as its index names it. */
function fixtureDay(covers: string): DayEntry {
	const entry = fixtureDays().find((one) => one.covers === covers);
	if (entry === undefined) throw new Error(`the fixture packs no ${covers}`);
	return entry;
}

/** A day the packing recorded `empty` or `lost`: an entry with no file. */
const noFile = (covers: string, state: 'empty' | 'lost', setAside = 0): DayEntry => ({
	covers,
	rows: 0,
	bytes: 0,
	state,
	set_aside: setAside
});

/** The RecordNotes component, compiled and imported for a server render. */
async function recordNotesComponent() {
	const module = await serverCompiler(path.resolve(here, '..', 'test-results', 'ledger-rows'))(
		'src/lib/console/RecordNotes.svelte',
		'RecordNotes',
		[]
	);
	return (await import(pathToFileURL(module).href)).default;
}

/** Each line the route prints, as its note kind, its records, whether it looks like a fault, and its text. */
async function printedNotes(notes: RecordNote[]) {
	const RecordNotes = await recordNotesComponent();
	const lines = [...render(RecordNotes, { props: { notes } }).body.matchAll(/<p\b([^>]*)>([\s\S]*?)<\/p>/g)];
	const attribute = (attributes: string, name: string) => new RegExp(`${name}="([^"]*)"`).exec(attributes)?.[1];
	return lines.map(([, attributes, text]) => ({
		kind: attribute(attributes, 'data-record-note'),
		records: attribute(attributes, 'data-records'),
		fault: /\brecord-fault\b/.test(attributes),
		text: text.replace(/<!--[\s\S]*?-->/g, '').trim()
	}));
}

test.describe('reading a packed record', () => {
	test('a record with no packed file is not packed, and says so rather than throwing', async () => {
		const root = mkdtempSync(path.join(tmpdir(), 'idhazh-unpacked-'));
		try {
			const table = await machineRecord(-1, root);
			expect(table.read).toEqual({ state: 'not-packed' });
			expect(table.rows).toEqual([]);
			// The header survives: a panel that reads its columns off the table still
			// has them, so an empty record draws an empty panel and not a broken one.
			expect(table.columns).toEqual([...HOST_FINGERPRINT_COLUMNS]);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('a packed day missing from the middle makes the whole read unreadable, at that day, named day-missing', async () => {
		// Every packed day from the first, and 2026-09-04 is named by neither index.
		// Drawing the days either side of it would draw a gap as a quiet day.
		const table = await machineRecord(-1, FIXTURE);
		expect(table.read).toEqual({ state: 'unreadable', at: '2026-09-04', fault: 'day-missing' });
		expect(table.rows).toEqual([]);
	});

	test('a packed file the list names and the disk lacks makes the read unreadable, named file-missing', async () => {
		const root = packedUpTo('2026-09-03');
		try {
			rmSync(path.join(root, PACKED, 'daily', '2026', '09', '02.parquet'));
			const table = await machineRecord(2, root);
			expect(table.read).toEqual({ state: 'unreadable', at: '2026-09-02', fault: 'file-missing' });
			expect(table.rows).toEqual([]);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('the newest day reads on its own, and every cell comes back as the day files spelled it', async () => {
		const table = await machineRecord(1, FIXTURE);
		expect(table.read).toEqual({ state: 'read', through: '2026-09-05', lostDays: [], setAside: {} });
		expect(table.rows.map((row) => row.date)).toEqual(['2026-09-05', '2026-09-05']);

		// The rule, stated here rather than borrowed: nothing is '', a number is its
		// decimal, and text is itself. Checked against the door's own answer for
		// the same day, so a cell the reader dropped or respelled fails by name.
		const raw = await sliceFromDisk(FIXTURE, 'host-fingerprint', {
			columns: [...datedFirst(HOST_FINGERPRINT_COLUMNS)],
			from: '2026-09-05',
			to: '2026-09-05'
		});
		expect(raw.state).toBe('ok');
		const spelled = (value: Row[string] | undefined) =>
			value === null || value === undefined ? '' : typeof value === 'boolean' ? (value ? 'True' : 'False') : String(value);
		expect(table.rows).toEqual(
			raw.rows.map((row) => Object.fromEntries(Object.entries(row).map(([name, value]) => [name, spelled(value)])))
		);
		for (const row of table.rows) {
			expect(Object.keys(row).sort()).toEqual([...HOST_FINGERPRINT_COLUMNS].sort());
			for (const [name, cell] of Object.entries(row)) expect(typeof cell, name).toBe('string');
		}
	});

	test('packed days that hold no row at the end are made up for at the start', async () => {
		// Packed through 2026-09-03, a day that holds no row. A window is anchored on
		// the newest day that holds one, 2026-09-02, so two days read back from the
		// newest PACKED day would reach one day too few. The reader reads the day
		// that makes up for it.
		const root = packedUpTo('2026-09-03');
		try {
			const table = await machineRecord(2, root);
			expect(table.read).toEqual({ state: 'read', through: '2026-09-03', lostDays: [], setAside: {} });
			expect([...new Set(table.rows.map((row) => row.date))]).toEqual(['2026-09-01', '2026-09-02']);
			expect(table.rows).toHaveLength(3 + 2);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('a span never starts before the first packed day, whatever it asks for', async () => {
		// Ninety days back from 2026-09-03 asks from June, and the door cuts the days
		// before the first packed day: they are before the record began.
		const root = packedUpTo('2026-09-03');
		try {
			const table = await machineRecord(90, root);
			expect(table.read).toEqual({ state: 'read', through: '2026-09-03', lostDays: [], setAside: {} });
			expect([...new Set(table.rows.map((row) => row.date))]).toEqual([
				'2026-08-31',
				'2026-09-01',
				'2026-09-02'
			]);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('a day the packing recorded lost comes back named, beside the files each day set aside', async () => {
		// The fixture's zero-row day recorded empty and its hole recorded lost with two
		// files set aside, and the newest day kept its rows but set one file aside.
		const root = packedTree([
			...fixtureDays().filter((entry) => entry.covers <= '2026-09-02'),
			noFile('2026-09-03', 'empty'),
			noFile('2026-09-04', 'lost', 2),
			{ ...fixtureDay('2026-09-05'), set_aside: 1 }
		]);
		try {
			const table = await machineRecord(-1, root);
			expect(table.read).toEqual({
				state: 'read',
				through: '2026-09-05',
				lostDays: ['2026-09-04'],
				setAside: { '2026-09-04': 2, '2026-09-05': 1 }
			});
			expect([...new Set(table.rows.map((row) => row.date))]).toEqual([
				'2026-08-31',
				'2026-09-01',
				'2026-09-02',
				'2026-09-05'
			]);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('the day read to make up for an empty end keeps what it is missing', async () => {
		// Two days back from 2026-09-03, which held no row, reach one day too few, so the
		// reader reads 2026-09-01 as well - lost here, with a file set aside.
		const root = packedTree([
			fixtureDay('2026-08-31'),
			noFile('2026-09-01', 'lost', 1),
			fixtureDay('2026-09-02'),
			noFile('2026-09-03', 'empty')
		]);
		try {
			const table = await machineRecord(2, root);
			expect(table.read).toEqual({
				state: 'read',
				through: '2026-09-03',
				lostDays: ['2026-09-01'],
				setAside: { '2026-09-01': 1 }
			});
			expect([...new Set(table.rows.map((row) => row.date))]).toEqual(['2026-09-02']);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});
});

test.describe('what a read asks the door for', () => {
	test('the day and the run lead, so rows come back oldest day first and a run together', () => {
		expect(datedFirst(['version', 'date', 'run_id', 'item_id'])).toEqual([
			'date',
			'run_id',
			'version',
			'item_id'
		]);
	});

	test('every column list is one the door accepts: named, unique, and in its alphabet', () => {
		// The door refuses a bad request before it reads a byte, and at build time
		// that refusal is a failed prerender. Asked here, it is a failed test naming
		// the list.
		for (const [name, columns] of [
			['article', ITEM_HEALTH_COLUMNS],
			['score', SCORE_COLUMNS],
			['machine', HOST_FINGERPRINT_COLUMNS]
		] as const) {
			expect(new Set(columns).size, `${name} names a column twice`).toBe(columns.length);
			expect(() =>
				checkedRequest({ columns: datedFirst(columns), from: '2026-09-01', to: '2026-09-02' })
			).not.toThrow();
		}
	});
});

test.describe('what a route says about the records it read', () => {
	const read = (through: string, lostDays: string[] = [], setAside: Record<string, number> = {}): RecordRead => ({
		state: 'read',
		through,
		lostDays,
		setAside
	});

	test('records read and current say nothing', () => {
		expect(
			recordNotes(
				[
					{ record: 'article', read: read('2026-09-28') },
					{ record: 'score', read: read('2026-09-29') }
				],
				'2026-09-29'
			)
		).toEqual([]);
	});

	test('records not packed share one plain sentence that is not a fault', () => {
		const notes = recordNotes(
			[
				{ record: 'article', read: { state: 'not-packed' } },
				{ record: 'score', read: { state: 'not-packed' } }
			],
			null
		);
		expect(notes).toEqual([
			{
				kind: 'not-packed',
				records: ['article', 'score'],
				text:
					'The article and score records have not been packed yet, so nothing below that uses them has anything to show. That is a step not yet run, not a quiet pipeline.'
			}
		]);
	});

	test('a record that did not load is a fault, named with the day that failed where there is one', () => {
		const notes = recordNotes(
			[
				{ record: 'machine', read: { state: 'unreadable', at: '2026-09-04', fault: null } },
				{ record: 'article', read: { state: 'unreadable', at: null, fault: null } }
			],
			'2026-09-29'
		);
		expect(notes.map((note) => note.kind)).toEqual(['unreadable', 'unreadable']);
		expect(notes[0].text).toBe(
			"The machine record's day for 4 Sep 2026 did not load, so nothing below that uses this record has anything to show. This is a fault to fix, not a quiet day."
		);
		expect(notes[1].text).toBe(
			"The article record's list of packed days did not load, so nothing below that uses it has anything to show. This is a fault to fix, not a quiet day."
		);
	});

	test('a missing file and a missing day each say which, because each has its own fix', () => {
		const notes = recordNotes(
			[
				{ record: 'machine', read: { state: 'unreadable', at: '2026-09-04', fault: 'file-missing' } },
				{ record: 'score', read: { state: 'unreadable', at: '2026-09-04', fault: 'day-missing' } }
			],
			'2026-09-29'
		);
		expect(notes).toEqual([
			{
				kind: 'unreadable',
				records: ['machine'],
				text: 'The machine record lists a packed file for 4 Sep 2026 that is not there, so nothing below that uses this record has anything to show. This is a fault to fix, not a quiet day.'
			},
			{
				kind: 'unreadable',
				records: ['score'],
				text: 'The score record is missing 4 Sep 2026, a day between packed days, so nothing below that uses this record has anything to show. This is a fault to fix, not a quiet day.'
			}
		]);
	});

	test('a record packed short of the day before the newest published day says where it stops', () => {
		// The day before the newest published day may not have ended when packing
		// last ran, so a record packed that far is as current as packing can be.
		expect(recordNotes([{ record: 'article', read: read('2026-09-28') }], '2026-09-29')).toEqual([]);
		const notes = recordNotes(
			[
				{ record: 'article', read: read('2026-09-25') },
				{ record: 'score', read: read('2026-09-25') },
				{ record: 'machine', read: read('2026-09-27') }
			],
			'2026-09-29'
		);
		expect(notes).toEqual([
			{
				kind: 'behind',
				records: ['article', 'score'],
				text: 'The article and score records are packed as far as 25 Sep 2026, so the 4 days after it are not shown yet.'
			},
			{
				kind: 'behind',
				records: ['machine'],
				text: 'The machine record is packed as far as 27 Sep 2026, so the 2 days after it are not shown yet.'
			}
		]);
	});

	test('a day a record has no record for is named plainly, and the files it set aside say where they wait', () => {
		const notes = recordNotes(
			[{ record: 'machine', read: read('2026-08-20', ['2026-08-19'], { '2026-08-19': 2 }) }],
			'2026-08-20'
		);
		expect(notes).toEqual([
			{
				kind: 'lost',
				records: ['machine'],
				text: 'There is no machine record for 19 Aug 2026, so nothing below that uses this record shows that day. The record for that day was lost and could not be recovered; it was not a quiet day.'
			},
			{
				kind: 'set-aside',
				records: ['machine'],
				text: '2 machine record files were set aside unread when this data was packed, so anything below that uses this record may be missing their rows. They wait in state/raw/host-fingerprint/set-aside/ for a person to read.'
			}
		]);
	});

	test('lost days read as runs with the year once, one file reads as one file, and a new year names both years', () => {
		const notes = recordNotes(
			[{ record: 'article', read: read('2026-08-20', ['2026-08-14', '2026-08-15', '2026-08-16', '2026-08-19'], { '2026-08': 1 }) }],
			'2026-08-20'
		);
		expect(notes.map((note) => note.text)).toEqual([
			'There is no article record for 14 Aug to 16 Aug and 19 Aug 2026, so nothing below that uses this record shows those days. The record for those days was lost and could not be recovered; they were not quiet days.',
			'1 article record file was set aside unread when this data was packed, so anything below that uses this record may be missing its rows. It waits in state/raw/item-health/set-aside/ for a person to read.'
		]);
		// "31 Dec to 1 Jan 2027" would name the wrong December.
		const [turn] = recordNotes([{ record: 'score', read: read('2027-01-02', ['2026-12-31', '2027-01-01']) }], '2027-01-02');
		expect(turn.text).toContain('There is no score record for 31 Dec 2026 to 1 Jan 2027, so');
	});

	test('the route prints one line a note, and only a record that did not load looks like a fault', async () => {
		// Compiled and rendered for real, because the canary packs every record as
		// far as its own day and so never shows a route one of these lines.
		const notes = recordNotes(
			[
				{ record: 'article', read: { state: 'not-packed' } },
				{ record: 'machine', read: { state: 'unreadable', at: '2026-09-04', fault: 'file-missing' } },
				{ record: 'score', read: read('2026-09-25', ['2026-09-20'], { '2026-09-20': 1 }) }
			],
			'2026-09-29'
		);
		const printed = await printedNotes(notes);
		expect(printed.map((line) => line.kind)).toEqual(['not-packed', 'unreadable', 'behind', 'lost', 'set-aside']);
		expect(printed.map((line) => line.records)).toEqual(['article', 'machine', 'score', 'score', 'score']);
		expect(printed.map((line) => line.fault)).toEqual([false, true, false, false, false]);
		expect(printed.map((line) => line.text)).toEqual(notes.map((note) => note.text));
		expect(await printedNotes([])).toEqual([]);
	});
});

test.describe('THE ORACLE for the Hardware note: a day the machine record lost reads as a day with no record', () => {
	test('it is printed once as a plain note, and the recording note never dates the start after it', async () => {
		// An empty day, then a lost day, then the first day with rows: read the old way,
		// the lost day was a day before the record started, and the start the day after it.
		const root = packedTree([noFile('2026-09-03', 'empty'), noFile('2026-09-04', 'lost'), fixtureDay('2026-09-05')]);
		try {
			const machine = await machineRecord(-1, root);
			expect(machine.read).toEqual({ state: 'read', through: '2026-09-05', lostDays: ['2026-09-04'], setAside: {} });
			const printed = await printedNotes(recordNotes([{ record: 'machine', read: machine.read }], '2026-09-05'));
			expect(printed).toEqual([
				{
					kind: 'lost',
					records: 'machine',
					fault: false,
					text: 'There is no machine record for 4 Sep 2026, so nothing below that uses this record shows that day. The record for that day was lost and could not be recovered; it was not a quiet day.'
				}
			]);
			const recording = recordingNotes({
				enabled: true,
				recorded: [...new Set(machine.rows.map((row) => row.date))],
				window: ['2026-09-04', '2026-09-05'],
				daysWithNoRecord: machine.read.state === 'read' ? machine.read.lostDays : [],
				figures: 'machine record'
			});
			expect(recording.startedMidWindow).toBeNull();
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});
});
