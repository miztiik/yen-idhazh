import { expect, test } from '@playwright/test';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { recordNotes, type RecordRead } from '../src/lib/console/recording';
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
 * zero-row day on 09-03, a hole on 09-04, and a monthly file for 2026-08.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(here, '..', '..', 'tests', 'fixtures', 'ledger-door', 'state');
const PACKED = path.join('compact', 'host-fingerprint');

/** A state tree holding only the fixture's packed days up to and including `through`, and no months. */
function packedUpTo(through: string): string {
	const root = mkdtempSync(path.join(tmpdir(), 'idhazh-packed-'));
	const index = JSON.parse(
		readFileSync(path.join(FIXTURE, PACKED, 'index', 'daily.json'), 'utf8')
	) as { entries: { covers: string }[] };
	index.entries = index.entries.filter((entry) => entry.covers <= through);
	for (const entry of index.entries) {
		const [year, month, day] = entry.covers.split('-');
		const at = path.join(root, PACKED, 'daily', year, month);
		mkdirSync(at, { recursive: true });
		copyFileSync(path.join(FIXTURE, PACKED, 'daily', year, month, `${day}.parquet`), path.join(at, `${day}.parquet`));
	}
	mkdirSync(path.join(root, PACKED, 'index'), { recursive: true });
	writeFileSync(path.join(root, PACKED, 'index', 'daily.json'), JSON.stringify(index));
	return root;
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

	test('a packed day missing from the middle makes the whole read unreadable, at that day', async () => {
		// Every packed day from the first, and 2026-09-04 is named by neither index.
		// Drawing the days either side of it would draw a gap as a quiet day.
		const table = await machineRecord(-1, FIXTURE);
		expect(table.read).toEqual({ state: 'unreadable', at: '2026-09-04' });
		expect(table.rows).toEqual([]);
	});

	test('the newest day reads on its own, and every cell comes back as the day files spelled it', async () => {
		const table = await machineRecord(1, FIXTURE);
		expect(table.read).toEqual({ state: 'read', through: '2026-09-05' });
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
			expect(table.read).toEqual({ state: 'read', through: '2026-09-03' });
			expect([...new Set(table.rows.map((row) => row.date))]).toEqual(['2026-09-01', '2026-09-02']);
			expect(table.rows).toHaveLength(3 + 2);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('a span never starts before the first packed day, whatever it asks for', async () => {
		// A day before the first one packed is a day no index names, and the door
		// answers one as a hole. Ninety days back from 2026-09-03 would ask for June.
		const root = packedUpTo('2026-09-03');
		try {
			const table = await machineRecord(90, root);
			expect(table.read).toEqual({ state: 'read', through: '2026-09-03' });
			expect([...new Set(table.rows.map((row) => row.date))]).toEqual([
				'2026-08-31',
				'2026-09-01',
				'2026-09-02'
			]);
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
	const read = (through: string): RecordRead => ({ state: 'read', through });

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
				{ record: 'machine', read: { state: 'unreadable', at: '2026-09-04' } },
				{ record: 'article', read: { state: 'unreadable', at: null } }
			],
			'2026-09-29'
		);
		expect(notes.map((note) => note.kind)).toEqual(['unreadable', 'unreadable']);
		expect(notes[0].text).toBe(
			"The machine record's day for 4 Sep 2026 did not load, so nothing below that uses it has anything to show. This is a fault to fix, not a quiet day."
		);
		expect(notes[1].text).toBe(
			"The article record's list of packed days did not load, so nothing below that uses it has anything to show. This is a fault to fix, not a quiet day."
		);
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

	test('the route prints one line a note, and only a record that did not load looks like a fault', async () => {
		// Compiled and rendered for real, because the canary packs every record as
		// far as its own day and so never shows a route one of these lines.
		const module = await serverCompiler(path.resolve(here, '..', 'test-results', 'ledger-rows'))(
			'src/lib/console/RecordNotes.svelte',
			'RecordNotes',
			[]
		);
		const RecordNotes = (await import(pathToFileURL(module).href)).default;
		const notes = recordNotes(
			[
				{ record: 'article', read: { state: 'not-packed' } },
				{ record: 'machine', read: { state: 'unreadable', at: '2026-09-04' } },
				{ record: 'score', read: read('2026-09-25') }
			],
			'2026-09-29'
		);
		const lines = [...render(RecordNotes, { props: { notes } }).body.matchAll(/<p\b([^>]*)>([\s\S]*?)<\/p>/g)];
		const attribute = (attributes: string, name: string) => new RegExp(`${name}="([^"]*)"`).exec(attributes)?.[1];
		expect(lines.map(([, attributes]) => attribute(attributes, 'data-record-note'))).toEqual([
			'not-packed',
			'unreadable',
			'behind'
		]);
		expect(lines.map(([, attributes]) => attribute(attributes, 'data-records'))).toEqual(['article', 'machine', 'score']);
		expect(lines.map(([, attributes]) => /\brecord-fault\b/.test(attributes))).toEqual([false, true, false]);
		expect(lines.map(([, , text]) => text.replace(/<!--[\s\S]*?-->/g, '').trim())).toEqual(
			notes.map((note) => note.text)
		);
		expect(render(RecordNotes, { props: { notes: [] } }).body).not.toContain('<p');
	});
});
