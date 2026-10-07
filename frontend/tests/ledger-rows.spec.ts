import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { windowOfDays, type TimeWindow } from '../src/lib/charts/viewport';
import {
	measurementOff,
	recordingNotes,
	recordNotes,
	type OfferedWindow,
	type RecordNote,
	type RecordRead,
	type RouteRecord
} from '../src/lib/console/recording';
import { checkedRequest } from '../src/lib/data/slice-shapes';
import { HOST_FINGERPRINT_COLUMNS, machineRecord } from '../src/lib/server/host-fingerprint';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { datedFirst, ITEM_HEALTH_COLUMNS, SCORE_COLUMNS, windowRows } from '../src/lib/server/ledger-rows';
import { windowDay } from '../src/lib/server/window-day';
import { buildLedger, daysBefore, everyDay, quietDays, type BuiltDay } from './support/ledger-lifecycle';
import { publishedSite } from './support/published-site';
import { serverCompiler } from './support/server-render';

/**
 * How a console route reads a packed record at build time, and what it says
 * about the read.
 *
 * Each reader case builds the record it reads with the lifecycle builder, in the
 * test's own output folder, with days counted back from a UTC day the test pins,
 * through the machine record: the article and score records take the same path
 * with other columns. The window cases build their own site and ledger the same
 * way. Nothing here grows with the archive (`CLAUDE.md` section 13), and nothing
 * touches the network but the engine, whose first query on a machine downloads
 * its parquet add-on (owner ruling, 2026-09-28).
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const PACKED = path.join('compact', 'host-fingerprint');
/** The UTC day every built record counts its days back from. */
const PINNED = '2030-06-15';

/** The RecordNotes component, compiled and imported for a server render. */
async function recordNotesComponent() {
	const module = await serverCompiler(path.resolve(here, '..', 'test-results', 'ledger-rows'))(
		'src/lib/console/RecordNotes.svelte',
		'RecordNotes',
		[]
	);
	return (await import(pathToFileURL(module).href)).default;
}

/** Each line the route prints, as its note kind, its records, whether it looks like a fault,
 *  whether it is the quietest line, and its text. */
async function printedNotes(notes: RecordNote[]) {
	const RecordNotes = await recordNotesComponent();
	const lines = [...render(RecordNotes, { props: { notes } }).body.matchAll(/<p\b([^>]*)>([\s\S]*?)<\/p>/g)];
	const attribute = (attributes: string, name: string) => new RegExp(`${name}="([^"]*)"`).exec(attributes)?.[1];
	return lines.map(([, attributes, text]) => ({
		kind: attribute(attributes, 'data-record-note'),
		records: attribute(attributes, 'data-records'),
		fault: /\brecord-fault\b/.test(attributes),
		quiet: /\btext-text-tertiary\b/.test(attributes),
		text: text.replace(/<!--[\s\S]*?-->/g, '').trim()
	}));
}

/** A window of the fixture's days, both ends included. */
const days = (start: string, end: string): TimeWindow => ({ start, end });

test.describe('reading a packed record', () => {
	test('a record with no packed file is not packed, and says so rather than throwing', async () => {
		const root = mkdtempSync(path.join(tmpdir(), 'idhazh-unpacked-'));
		try {
			const table = await machineRecord(days('2026-09-01', '2026-09-05'), root);
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
		// Packed on 10, 11, 12 and 15 Jun 2030, quiet on the 13th, and the 14th named by no
		// index. Drawing the days either side of it would draw a gap as a quiet day.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 5, rows: 1 }, { ago: 4, rows: 3 }, { ago: 3, rows: 2 }, { ago: 2, state: 'empty' }, { ago: 0, rows: 2 }]
		});
		const table = await machineRecord(days('2030-06-10', '2030-06-15'), state);
		expect(table.read).toEqual({ state: 'unreadable', at: '2030-06-14', fault: 'day-missing' });
		expect(table.rows).toEqual([]);
	});

	test('a packed file the list names and the disk lacks makes the read unreadable, named file-missing', async () => {
		// Packed on 12 and 13 Jun 2030 and quiet on the 14th; the 13th's file is then removed.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 3, rows: 1 }, { ago: 2, rows: 2 }, { ago: 1, state: 'empty' }]
		});
		rmSync(path.join(state, PACKED, 'daily', '2030', '06', '13.parquet'));
		const table = await machineRecord(days('2030-06-13', '2030-06-14'), state);
		expect(table.read).toEqual({ state: 'unreadable', at: '2030-06-13', fault: 'file-missing' });
		expect(table.rows).toEqual([]);
	});

	test('one day reads on its own, and every cell comes back as the day files spelled it', async () => {
		// Packed with one row on 14 Jun 2030 and two on the 15th, each holding a text,
		// a whole number and a fraction the machine record reads. The rule, stated
		// here rather than borrowed: nothing is '', a number is its decimal, and text
		// is itself.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 1, rows: 1 }, { ago: 0, rows: 2 }],
			columns: { run_id: '2030-06-15-1', job: 'work', cpu_model: 'AMD EPYC 7763 64-Core Processor', cores: 4, job_seconds: 612.5 }
		});
		const table = await machineRecord(days('2030-06-15', '2030-06-15'), state);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-15',
			lastRows: { period: 'daily', covers: '2030-06-15' },
			lostDays: [],
			setAside: {}
		});
		const nothing = Object.fromEntries(HOST_FINGERPRINT_COLUMNS.map((name) => [name, '']));
		const spelled = {
			...nothing,
			date: '2030-06-15',
			run_id: '2030-06-15-1',
			job: 'work',
			cpu_model: 'AMD EPYC 7763 64-Core Processor',
			cores: '4',
			job_seconds: '612.5'
		};
		expect(table.rows).toEqual([spelled, spelled]);
	});

	test('a window whose packed days hold no row reads no row, and names where the rows stop instead of reaching back', async () => {
		// Packed on 12 and 13 Jun 2030, and quiet on the 14th. The reader used to read back to
		// the 13th to fill the window; now the window is the read.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 3, rows: 1 }, { ago: 2, rows: 2 }, { ago: 1, state: 'empty' }]
		});
		const table = await machineRecord(days('2030-06-14', '2030-06-14'), state);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-14',
			lastRows: { period: 'daily', covers: '2030-06-13' },
			lostDays: [],
			setAside: {}
		});
		expect(table.rows).toEqual([]);
	});

	test('a window that starts before the first packed day is read from that day', async () => {
		// Ninety days to 15 Jun 2030 start on 18 Mar, and the door cuts the days before the
		// first packed day, the 12th: they are before the record began.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 3, rows: 1 }, { ago: 2, rows: 3 }, { ago: 1, rows: 2 }, { ago: 0, state: 'empty' }]
		});
		const table = await machineRecord(days('2030-03-18', '2030-06-15'), state);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-15',
			lastRows: { period: 'daily', covers: '2030-06-14' },
			lostDays: [],
			setAside: {}
		});
		expect(table.rows.map((row) => row.date)).toEqual([
			'2030-06-12',
			'2030-06-13',
			'2030-06-13',
			'2030-06-13',
			'2030-06-14',
			'2030-06-14'
		]);
	});

	test('a day the packing recorded lost comes back named, beside the files each day set aside', async () => {
		// Packed on 10, 11 and 12 Jun 2030 and quiet on the 13th. The 14th is lost with
		// two files set aside, and the 15th kept its rows but set one file aside.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [
				{ ago: 5, rows: 1 },
				{ ago: 4, rows: 3 },
				{ ago: 3, rows: 2 },
				{ ago: 2, state: 'empty' },
				{ ago: 1, state: 'lost', setAside: 2 },
				{ ago: 0, rows: 2, setAside: 1 }
			]
		});
		const table = await machineRecord(days('2030-06-10', '2030-06-15'), state);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-15',
			lastRows: { period: 'daily', covers: '2030-06-15' },
			lostDays: ['2030-06-14'],
			setAside: { '2030-06-14': 2, '2030-06-15': 1 }
		});
		expect(table.rows.map((row) => row.date)).toEqual([
			'2030-06-10',
			'2030-06-11',
			'2030-06-11',
			'2030-06-11',
			'2030-06-12',
			'2030-06-12',
			'2030-06-15',
			'2030-06-15'
		]);
	});

	test('a day lost before the window is not named, because nothing before the window is read', async () => {
		// 11 Jun 2030 set a file aside and the 12th is lost, both before the window of the 13th
		// and 14th: the reader used to reach back over them, and named them.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 4, rows: 1, setAside: 1 }, { ago: 3, state: 'lost' }, { ago: 2, rows: 2 }, { ago: 1, state: 'empty' }]
		});
		const table = await machineRecord(days('2030-06-13', '2030-06-14'), state);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-14',
			lastRows: { period: 'daily', covers: '2030-06-13' },
			lostDays: [],
			setAside: {}
		});
		expect(table.rows.map((row) => row.date)).toEqual(['2030-06-13', '2030-06-13']);
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

/** Each window the control offers on a route, placed on `day`: 1, 7, 14, 30 and 90 days. */
function offeredOn(day: string): OfferedWindow[] {
	return [1, 7, 14, 30, 90].map((count) => ({ days: count, ...windowOfDays(day, count, 'right') }));
}

/** The offered window of `count` days that ends on `day`. */
function openOn(day: string, count: number): OfferedWindow {
	return { days: count, ...windowOfDays(day, count, 'right') };
}

/** The notes a route prints for its 14-day window, which ends on `newestDay`. */
function notesFor(reads: readonly RouteRecord[], newestDay: string | null, count = 14): RecordNote[] {
	const day = newestDay ?? '2026-09-29';
	return recordNotes(reads, newestDay, openOn(day, count), offeredOn(day));
}

/** The newest day the built sites publish. */
const PUBLISHED = '2030-06-15';

/** A site published on 14 and 15 Jun 2030, and a machine record built with `days` counted
 *  back from the newest published day, in the test's own output folder. */
async function builtSite(days: readonly BuiltDay[]): Promise<{ digest: string; state: string }> {
	const { digest } = publishedSite(test.info().outputPath('site'), { published: ['2030-06-14', PUBLISHED] });
	const state = test.info().outputPath('state');
	await buildLedger(state, { ledger: 'host-fingerprint', pinned: PUBLISHED, days });
	return { digest, state };
}

/** A machine record whose rows stop 40 days before the newest published day: one row a day
 *  from 1 to 6 May 2030, then packed with empty days from 7 May to 14 Jun, the day before it. */
const STOPPED = [...everyDay(45, 40), ...quietDays(39, 1)];

test.describe('what a route says about the records it read', () => {
	const read = (
		through: string,
		lostDays: string[] = [],
		setAside: Record<string, number> = {},
		lastRows: { period: 'daily' | 'monthly' | 'yearly'; covers: string } | null = { period: 'daily', covers: through }
	): RecordRead => ({ state: 'read', through, lastRows, lostDays, setAside });

	test('records read and packed as far as the newest published day say nothing', () => {
		expect(
			notesFor(
				[
					{ record: 'article', read: read('2026-09-29') },
					{ record: 'score', read: read('2026-09-29') }
				],
				'2026-09-29'
			)
		).toEqual([]);
	});

	test('records not packed share one plain sentence that is not a fault', () => {
		const notes = notesFor(
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
					'The article and score records have not been packed yet, so nothing below that uses them has anything to show. That is a step not yet run, not a quiet pipeline.',
				emptiesWindow: true
			}
		]);
	});

	test('a record that did not load is a fault, named with the day that failed where there is one', () => {
		const notes = notesFor(
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
		const notes = notesFor(
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
				text: 'The machine record lists a packed file for 4 Sep 2026 that is not there, so nothing below that uses this record has anything to show. This is a fault to fix, not a quiet day.',
				emptiesWindow: true
			},
			{
				kind: 'unreadable',
				records: ['score'],
				text: 'The score record is missing 4 Sep 2026, a day between packed days, so nothing below that uses this record has anything to show. This is a fault to fix, not a quiet day.',
				emptiesWindow: true
			}
		]);
	});

	test('a record packed short of the day before the newest published day says where it stops', () => {
		const notes = notesFor(
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
				text: 'The article and score records are packed as far as 25 Sep 2026, so the 4 days after it are not shown yet.',
				emptiesWindow: false
			},
			{
				kind: 'behind',
				records: ['machine'],
				text: 'The machine record is packed as far as 27 Sep 2026, so the 2 days after it are not shown yet.',
				emptiesWindow: false
			}
		]);
		// A window that holds no packed day is empty because packing is late.
		expect(notesFor([{ record: 'machine', read: read('2026-09-27') }], '2026-09-29', 1)).toEqual([
			{
				kind: 'behind',
				records: ['machine'],
				text: 'The machine record is packed as far as 27 Sep 2026, so the 2 days after it are not shown yet.',
				emptiesWindow: true
			}
		]);
	});

	test('records packed as far as the day before the newest published day print the quietest line, last', () => {
		// A day is packed only after it ends, so this is every day in normal running.
		expect(
			notesFor(
				[
					{ record: 'machine', read: read('2026-10-05', ['2026-10-01']) },
					{ record: 'article', read: read('2026-10-05') }
				],
				'2026-10-06'
			)
		).toEqual([
			{
				kind: 'lost',
				records: ['machine'],
				text: 'There is no machine record for 1 Oct 2026, so nothing below that uses this record shows that day. The record for that day was lost and could not be recovered; it was not a quiet day.',
				emptiesWindow: false
			},
			{
				kind: 'on-time',
				records: ['machine', 'article'],
				text: 'The machine and article records are packed as far as 5 Oct 2026, so nothing below that uses them shows 6 Oct 2026 yet. That is normal: a day is packed only after it ends.',
				emptiesWindow: false
			}
		]);
		// One record, and a one-day window, which holds only the day not packed yet.
		expect(notesFor([{ record: 'machine', read: read('2026-10-05') }], '2026-10-06', 1)).toEqual([
			{
				kind: 'on-time',
				records: ['machine'],
				text: 'The machine record is packed as far as 5 Oct 2026, so nothing below that uses it shows 6 Oct 2026 yet. That is normal: a day is packed only after it ends.',
				emptiesWindow: true
			}
		]);
	});

	test('a record whose packed rows stop before the window says from when, and names the window that reaches back to them', () => {
		// Packed as far as the newest published day, 6 Oct 2026, with no rows after
		// 6 Sep. The 14-day window starts on 23 Sep and the 30-day one on 7 Sep, so
		// the narrowest window that reaches back to 6 Sep is 90 days.
		const stopped = read('2026-10-06', [], {}, { period: 'daily', covers: '2026-09-06' });
		expect(notesFor([{ record: 'machine', read: stopped }], '2026-10-06')).toEqual([
			{
				kind: 'rows-end',
				records: ['machine'],
				text: 'The newest packed rows in the machine record are from 6 Sep 2026. The packed days since then hold no rows, so nothing below that uses this record has anything to show in these 14 days. This page cannot tell if that is a quiet stretch or a fault. The 90-day window reaches back to 6 Sep 2026.',
				emptiesWindow: true
			}
		]);
		// Two records that stop on one day share a sentence, and a window that holds
		// their last rows prints nothing about them.
		const both = [
			{ record: 'article' as const, read: read('2026-10-06', [], {}, { period: 'daily', covers: '2026-09-28' }) },
			{ record: 'score' as const, read: read('2026-10-06', [], {}, { period: 'daily', covers: '2026-09-28' }) }
		];
		expect(notesFor(both, '2026-10-06', 7).map((note) => note.text)).toEqual([
			'The newest packed rows in the article and score records are from 28 Sep 2026. The packed days since then hold no rows, so nothing below that uses them has anything to show in these 7 days. This page cannot tell if that is a quiet stretch or a fault. The 14-day window reaches back to 28 Sep 2026.'
		]);
		expect(notesFor(both, '2026-10-06', 14)).toEqual([]);
		// The one-day window names its day.
		expect(notesFor([{ record: 'machine', read: stopped }], '2026-10-06', 1)[0].text).toContain(
			'has anything to show on 6 Oct 2026.'
		);
	});

	test('rows that stop in a closed month or a packed year are named as that month or year', () => {
		const month = read('2026-10-05', [], {}, { period: 'monthly', covers: '2026-08' });
		// The 90-day window starts on 9 Jul, so it reaches back to the whole of August.
		expect(notesFor([{ record: 'machine', read: month }], '2026-10-06', 30).map((note) => note.text)).toEqual([
			'The newest packed rows in the machine record are from August 2026. The packed days since then hold no rows, so nothing below that uses this record has anything to show in these 30 days. This page cannot tell if that is a quiet stretch or a fault. The 90-day window reaches back to August 2026.'
		]);
		// No window reaches back to the whole of 2025, so nothing sends the operator to one.
		const year = read('2026-10-06', [], {}, { period: 'yearly', covers: '2025' });
		expect(notesFor([{ record: 'score', read: year }], '2026-10-06').map((note) => note.text)).toEqual([
			'The newest packed rows in the score record are from 2025. The packed days since then hold no rows, so nothing below that uses this record has anything to show in these 14 days. This page cannot tell if that is a quiet stretch or a fault.'
		]);
	});

	test('a record whose rows stop says so once: not on time as well, and not where the route says its measurement is off', () => {
		const stopped = read('2026-10-05', [], {}, { period: 'daily', covers: '2026-09-06' });
		expect(notesFor([{ record: 'machine', read: stopped }], '2026-10-06').map((note) => note.kind)).toEqual(['rows-end']);
		expect(notesFor([{ record: 'machine', read: stopped, switchedOff: true }], '2026-10-06').map((note) => note.kind)).toEqual([
			'on-time'
		]);
		// A record that has never held a row has no rows to stop: its quiet days stay quiet.
		expect(notesFor([{ record: 'machine', read: read('2026-10-06', [], {}, null) }], '2026-10-06')).toEqual([]);
	});

	test('a day a record has no record for is named plainly, and the files it set aside say where they wait', () => {
		const notes = notesFor([{ record: 'machine', read: read('2026-08-20', ['2026-08-19'], { '2026-08-19': 2 }) }], '2026-08-20');
		expect(notes).toEqual([
			{
				kind: 'lost',
				records: ['machine'],
				text: 'There is no machine record for 19 Aug 2026, so nothing below that uses this record shows that day. The record for that day was lost and could not be recovered; it was not a quiet day.',
				emptiesWindow: false
			},
			{
				kind: 'set-aside',
				records: ['machine'],
				text: '2 machine record files were set aside unread when this data was packed, so anything below that uses this record may be missing their rows. They wait in state/raw/host-fingerprint/set-aside/ for a person to read.',
				emptiesWindow: false
			}
		]);
	});

	test('lost days read as runs with the year once, one file reads as one file, and a new year names both years', () => {
		const notes = notesFor(
			[{ record: 'article', read: read('2026-08-20', ['2026-08-14', '2026-08-15', '2026-08-16', '2026-08-19'], { '2026-08': 1 }) }],
			'2026-08-20'
		);
		expect(notes.map((note) => note.text)).toEqual([
			'There is no article record for 14 Aug to 16 Aug and 19 Aug 2026, so nothing below that uses this record shows those days. The record for those days was lost and could not be recovered; they were not quiet days.',
			'1 article record file was set aside unread when this data was packed, so anything below that uses this record may be missing its rows. It waits in state/raw/item-health/set-aside/ for a person to read.'
		]);
		// "31 Dec to 1 Jan 2027" would name the wrong December.
		const [turn] = notesFor([{ record: 'score', read: read('2027-01-02', ['2026-12-31', '2027-01-01']) }], '2027-01-02');
		expect(turn.text).toContain('There is no score record for 31 Dec 2026 to 1 Jan 2027, so');
	});

	test('the route prints one line a note, and only a record that did not load looks like a fault', async () => {
		// Compiled and rendered for real, because the canary packs every record as
		// far as its own day and so never shows a route one of these lines.
		const notes = notesFor(
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
		expect(printed.map((line) => line.quiet)).toEqual([false, false, false, false, false]);
		expect(printed.map((line) => line.text)).toEqual(notes.map((note) => note.text));
		expect(await printedNotes([])).toEqual([]);
	});

	test('the line for the day not packed yet prints a step quieter than the others, and last', async () => {
		const notes = notesFor(
			[
				{ record: 'machine', read: read('2026-10-05', [], {}, { period: 'daily', covers: '2026-09-06' }) },
				{ record: 'article', read: read('2026-10-05') }
			],
			'2026-10-06'
		);
		const printed = await printedNotes(notes);
		expect(printed.map((line) => [line.kind, line.records, line.fault, line.quiet])).toEqual([
			['rows-end', 'machine', false, false],
			['on-time', 'article', false, true]
		]);
	});
});

test.describe('THE ORACLE for the Hardware note: a day the machine record lost reads as a day with no record', () => {
	test('it is printed once as a plain note, and the recording note never dates the start after it', async () => {
		// A quiet day, then a lost day, then the first day with rows: read the old way,
		// the lost day was a day before the record started, and the start the day after it.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PINNED,
			days: [{ ago: 2, state: 'empty' }, { ago: 1, state: 'lost' }, { ago: 0, rows: 2 }]
		});
		const machine = await machineRecord(days('2030-06-13', '2030-06-15'), state);
		expect(machine.read).toEqual({
			state: 'read',
			through: '2030-06-15',
			lastRows: { period: 'daily', covers: '2030-06-15' },
			lostDays: ['2030-06-14'],
			setAside: {}
		});
		const printed = await printedNotes(notesFor([{ record: 'machine', read: machine.read }], '2030-06-15'));
		expect(printed).toEqual([
			{
				kind: 'lost',
				records: 'machine',
				fault: false,
				quiet: false,
				text: 'There is no machine record for 14 Jun 2030, so nothing below that uses this record shows that day. The record for that day was lost and could not be recovered; it was not a quiet day.'
			}
		]);
		const recording = recordingNotes({
			enabled: true,
			recorded: [...new Set(machine.rows.map((row) => row.date))],
			window: ['2030-06-14', '2030-06-15'],
			daysWithNoRecord: machine.read.state === 'read' ? machine.read.lostDays : [],
			figures: 'machine record'
		});
		expect(recording.startedMidWindow).toBeNull();
	});
});

test.describe('THE ORACLE: a console window ends on the site\'s newest published day, and reads only its own days', () => {
	test('a record whose rows stop 40 days before the newest published day reads nothing before the window, and the note names its last day', async () => {
		// Published on 14 and 15 Jun 2030. The machine record holds one row a day up to
		// 6 May, 40 days before the newest published day, and is packed with empty days
		// from 7 May to 14 Jun, the day before it.
		const { digest, state } = await builtSite(STOPPED);
		expect(daysBefore(PUBLISHED, 40)).toBe('2030-05-06');

		const day = windowDay(digest);
		expect(day).toBe(PUBLISHED);
		const open = { days: 30, ...windowOfDays(day, 30, 'right') };
		expect(open).toEqual({ days: 30, start: '2030-05-17', end: '2030-06-15' });

		const asked: [string, string][] = [];
		const table = await windowRows(state, 'host-fingerprint', open, HOST_FINGERPRINT_COLUMNS, (from, to) => {
			asked.push([from, to]);
			return sliceFromDisk(state, 'host-fingerprint', { columns: [...datedFirst(HOST_FINGERPRINT_COLUMNS)], from, to });
		});
		expect(asked).toEqual([['2030-05-17', '2030-06-15']]);
		expect(table.rows).toEqual([]);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-14',
			lastRows: { period: 'daily', covers: '2030-05-06' },
			lostDays: [],
			setAside: {}
		});
		// The machine record's own reader answers the same window the same way.
		expect(await machineRecord(open, state)).toEqual(table);

		const notes = recordNotes([{ record: 'machine', read: table.read }], day, open, offeredOn(day));
		expect(notes.map((note) => note.text)).toEqual([
			'The newest packed rows in the machine record are from 6 May 2030. The packed days since then hold no rows, so nothing below that uses this record has anything to show in these 30 days. This page cannot tell if that is a quiet stretch or a fault. The 90-day window reaches back to 6 May 2030.'
		]);
	});

	test('a site that has published nothing places every window on the build\'s own UTC day', () => {
		const empty = test.info().outputPath('nothing-published');
		mkdirSync(path.join(empty, 'digest'), { recursive: true });
		const before = new Date().toISOString().slice(0, 10);
		const day = windowDay(path.join(empty, 'digest'));
		const after = new Date().toISOString().slice(0, 10);
		expect([before, after]).toContain(day);
	});
});

test.describe('THE ORACLE: the "Measurement is off" line names only a day on screen', () => {
	/** The line a route prints over each window it offers, when the record's switch is off. A
	 *  route reads its widest window once, and the days it recorded are the days its rows hold. */
	async function linesOver(digest: string, state: string): Promise<[number, string | null][]> {
		const day = windowDay(digest);
		const offered = offeredOn(day);
		const machine = await machineRecord(openOn(day, 90), state);
		const recorded = [...new Set(machine.rows.map((row) => row.date))];
		return offered.map((open) => [
			open.days,
			measurementOff({ enabled: false, recorded, read: machine.read, open, offered })
		]);
	}

	test('a record whose rows stop 40 days before the newest published day names no day outside each window, and never says nothing was recorded at all', async () => {
		const { digest, state } = await builtSite(STOPPED);
		// Only the 90-day window, from 18 Mar to 15 Jun 2030, holds 6 May. The 1-day window
		// holds no packed day: the record is packed as far as 14 Jun.
		expect(await linesOver(digest, state)).toEqual([
			[1, 'Measurement is off. Turn it on in config/idhazh.json.'],
			[7, 'Measurement is off. Nothing was recorded in these 7 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'],
			[14, 'Measurement is off. Nothing was recorded in these 14 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'],
			[30, 'Measurement is off. Nothing was recorded in these 30 days. Turn it on in config/idhazh.json. The 90-day window reaches back to the last recorded day.'],
			[90, 'Measurement is off. Nothing has been recorded since 6 May 2030. Turn it on in config/idhazh.json.']
		]);
	});

	test('a record that never held a row says nothing has been recorded at all, in every window', async () => {
		// Packed with no row from 1 to 6 May 2030, as the packing once packed a quiet day, then
		// empty from 7 May to 14 Jun: no entry of its index holds a row.
		const { digest, state } = await builtSite([...everyDay(45, 40, 0), ...quietDays(39, 1)]);
		const at = 'Measurement is off. Nothing has been recorded at all. Turn it on in config/idhazh.json.';
		expect(await linesOver(digest, state)).toEqual([
			[1, at],
			[7, at],
			[14, at],
			[30, at],
			[90, at]
		]);
	});
});