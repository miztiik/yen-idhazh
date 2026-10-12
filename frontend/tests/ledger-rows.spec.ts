import { expect, test } from '@playwright/test';
import { existsSync, mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { windowOfDays, type TimeWindow } from '../src/lib/charts/viewport';
import {
	describeMissingMarkers,
	measurementOff,
	recordingNotes,
	recordNotes,
	type OfferedWindow,
	type RecordNote,
	type RecordRead,
	type RouteRecord
} from '../src/lib/console/recording';
import { checkedRequest } from '../src/lib/data/slice-shapes';
import { daysBetween } from '../src/lib/data/slice';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { datedFirst, evalRows, itemHealthRows, ITEM_HEALTH_COLUMNS, SCORE_COLUMNS, windowRows } from '../src/lib/server/ledger-rows';
import { carriesServerCounters } from '../src/lib/console/machine/counters';
import { countersFrom, fingerprints } from '../src/lib/console/machine/records';
import { machineCardsQuery, platformMixQuery } from '../src/lib/console/queries/machine';
import { listManifestDays } from '../src/lib/server/model-work';
import { HOLDOUT_SCORE_COLUMNS, markedPairs, markReach, mergeLineHoldoutScore } from '../src/lib/server/content-similarity-holdout';
import { windowDay } from '../src/lib/server/window-day';
import { buildLedger, buildRows, daysBefore, everyDay, quietDays, type BuiltDay } from './support/ledger-lifecycle';
import { publishedSite } from './support/published-site';
import { serverCompiler } from './support/server-render';

/**
 * How a console route reads a packed record at build time, and what it says
 * about the read.
 *
 * Each reader case builds the record it reads with the lifecycle builder, in the
 * test's own output folder, with days counted back from a UTC day the test pins,
 * through the actual article and score readers. The window cases build their
 * own site and ledger the same way. Nothing here grows with the archive (`CLAUDE.md` section 13), and nothing
 * touches the network but the engine, whose first query on a machine downloads
 * its parquet add-on (owner ruling, 2026-09-28).
 */

const here = path.dirname(fileURLToPath(import.meta.url));
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

test('the actual article reader keeps explicitly supplied roots isolated', async ({}, info) => {
	const date = '2030-06-15';
	const left = info.outputPath('left-root');
	const right = info.outputPath('right-root');
	for (const [root, source] of [[left, 'left-source'], [right, 'right-source']]) {
		await buildRows(root, 'item-health', [{
			covers: date, rows: [{ date, run_id: `${date}-1`, item_id: 'one', source_id: source }]
		}]);
	}
	expect((await itemHealthRows(days(date, date), left)).rows.map((row) => row.source_id)).toEqual(['left-source']);
	expect((await itemHealthRows(days(date, date), right)).rows.map((row) => row.source_id)).toEqual(['right-source']);
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
			['machine', machineCardsQuery.columns],
			['holdout score', HOLDOUT_SCORE_COLUMNS]
		] as const) {
			expect(new Set(columns).size, `${name} names a column twice`).toBe(columns.length);
			expect(() =>
				checkedRequest({ columns: datedFirst(columns), from: '2026-09-01', to: '2026-09-02' })
			).not.toThrow();
		}
	});
});

test.describe('a record filed inside its family folder', () => {
	/** One reading of the merge line against the marks, every cell of it chosen. */
	const READING = {
		run_id: '2030-06-14-1',
		applied_line: 0.94,
		labeller: 'a-labeller',
		merged_and_one_story: 79,
		merged_and_two_stories: 1,
		apart_and_one_story: 117,
		apart_and_two_stories: 3,
		pairs_unresolved: 0,
		labelled_two_story_pairs: 4
	};

	test('the holdout score is read from its family folder, and the newest day wins', async () => {
		// Packed with one reading on 13 and 14 Jun 2030, under compact/content-similarity-judge/.
		// A reader that took the ledger's own name for its folder would find nothing there.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'merge-line-holdout-scores',
			pinned: PINNED,
			days: [{ ago: 2, rows: 1 }, { ago: 1, rows: 1 }],
			columns: READING
		});
		const folder = path.join(state, 'compact', 'content-similarity-judge', 'merge-line-holdout-scores');
		expect(existsSync(path.join(folder, 'index', 'daily.json'))).toBe(true);

		const scored = await mergeLineHoldoutScore(days('2030-06-01', PINNED), state);

		expect(scored.read.state).toBe('read');
		expect(scored.score).toEqual({
			date: '2030-06-14',
			runId: '2030-06-14-1',
			appliedLine: 0.94,
			labeller: 'a-labeller',
			mergedAndOneStory: 79,
			mergedAndTwoStories: 1,
			apartAndOneStory: 117,
			apartAndTwoStories: 3,
			pairsUnresolved: 0,
			labelledTwoStoryPairs: 4
		});
	});

	test('a holdout score with no packed file is no reading, rather than an error', async () => {
		const root = test.info().outputPath('unscored');
		try {
			expect(await mergeLineHoldoutScore(days('2030-06-01', PINNED), root)).toEqual({ score: null, read: { state: 'not-packed' } });
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});

	test('a window that starts after the newest reading reads none, rather than an old one', async () => {
		// Packed with one reading on 6 May 2030, 40 days before the pinned day, and quiet after.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'merge-line-holdout-scores',
			pinned: PINNED,
			days: [...everyDay(40, 40), ...quietDays(39, 0)],
			columns: READING
		});

		const empty = await mergeLineHoldoutScore(days('2030-06-01', PINNED), state);
		expect(empty.score).toBeNull();
		expect(empty.read.state).toBe('read');
	});
});

test.describe('the hand marks, once a pair over their reach', () => {
	/** One hand mark of two articles, as a harvest files it. */
	const mark = (key: string, sameStory: boolean, markedOn: string) => ({
		left_url: `https://left.test/${key}`,
		right_url: `https://right.test/${key}`,
		left_date: '2030-06-01',
		right_date: '2030-06-01',
		left_title: `Left story ${key}`,
		right_title: `Right story ${key}`,
		same_story: sameStory,
		marked_on: markedOn,
		note: 'a-labeller at score 0.9500'
	});
	/** Each read mark as the panel reads it: the left address, the mark and its day. */
	const read = (rows: Record<string, string>[]) =>
		rows.map((row) => [row.left_url, row.same_story, row.marked_on]).sort();

	test('THE ORACLE: a pair marked again on a later day reads once, with its second mark', async () => {
		// Packed under compact/content-similarity-judge/holdout-pairs/, with no `date` cell:
		// two marks on 10 Jun 2030, a quiet 11 Jun, and one of them marked again on 12 Jun.
		const state = test.info().outputPath('state');
		await buildRows(state, 'holdout-pairs', [
			{ covers: '2030-06-10', rows: [mark('corrected', true, '2030-06-10'), mark('kept', true, '2030-06-10')] },
			{ covers: '2030-06-11', rows: [] },
			{ covers: '2030-06-12', rows: [mark('corrected', false, '2030-06-12')] }
		]);

		const marks = await markedPairs(markReach(PINNED, 730), state);
		expect(marks.read.state).toBe('read');
		expect(read(marks.rows)).toEqual([
			['https://left.test/corrected', 'False', '2030-06-12'],
			['https://left.test/kept', 'True', '2030-06-10']
		]);
	});

	test('the reach names both its ends, and a mark filed before it is not read', async () => {
		// One mark filed 31 days before the pinned day, outside a 30-day reach, and another
		// filed 30 days before it, on the reach's first day.
		const state = test.info().outputPath('state');
		await buildRows(state, 'holdout-pairs', [
			{ covers: daysBefore(PINNED, 31), rows: [mark('a-pair', true, daysBefore(PINNED, 31))] },
			{ covers: daysBefore(PINNED, 30), rows: [mark('another-pair', false, daysBefore(PINNED, 30))] }
		]);

		expect(markReach(PINNED, 30)).toEqual({ start: daysBefore(PINNED, 30), end: PINNED });
		expect(read((await markedPairs(markReach(PINNED, 30), state)).rows)).toEqual([
			['https://left.test/another-pair', 'False', daysBefore(PINNED, 30)]
		]);
	});

	test('no packed mark reads as none, rather than an error', async () => {
		const root = test.info().outputPath('unmarked');
		try {
			expect(await markedPairs(markReach(PINNED, 730), root)).toEqual({ rows: [], read: { state: 'not-packed' } });
		} finally {
			rmSync(root, { recursive: true, force: true });
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

/** A site published on 14 and 15 Jun 2030, and an article record built with `days` counted
 *  back from the newest published day, in the test's own output folder. */
async function builtSite(days: readonly BuiltDay[]): Promise<{ digest: string; state: string }> {
	const { digest } = publishedSite(test.info().outputPath('site'), { published: ['2030-06-14', PUBLISHED] });
	const state = test.info().outputPath('state');
	await buildLedger(state, { ledger: 'item-health', pinned: PUBLISHED, days });
	return { digest, state };
}

/** An article record whose rows stop 40 days before the newest published day: one row a day
 *  from 1 to 6 May 2030, then packed with empty days from 7 May to 14 Jun, the day before it. */
const STOPPED = [...everyDay(45, 40), ...quietDays(39, 1)];

test.describe('what a route says about the records it read', () => {
	/** A record read whole; every record here began long before the window its notes are for. */
	const read = (
		through: string,
		lostDays: string[] = [],
		setAside: Record<string, number> = {},
		lastRows: { period: 'daily' | 'monthly' | 'yearly'; covers: string } | null = { period: 'daily', covers: through }
	): RecordRead => ({ state: 'read', through, first: '2025-01-01', lastRows, lostDays, setAside });

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

test.describe('THE ORACLE: a lost article day is not a quiet day or a later recording start', () => {
	test('it is printed once as a plain note, and the recording note never dates the start after it', async () => {
		// A quiet day, then a lost day, then the first day with rows: read the old way,
		// the lost day was a day before the record started, and the start the day after it.
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'item-health',
			pinned: PINNED,
			days: [{ ago: 2, state: 'empty' }, { ago: 1, state: 'lost' }, { ago: 0, rows: 2 }]
		});
		const articles = await itemHealthRows(days('2030-06-13', '2030-06-15'), state);
		expect(articles.read).toEqual({
			state: 'read',
			through: '2030-06-15',
			first: '2030-06-13',
			lastRows: { period: 'daily', covers: '2030-06-15' },
			lostDays: ['2030-06-14'],
			setAside: {}
		});
		const printed = await printedNotes(notesFor([{ record: 'article', read: articles.read }], '2030-06-15'));
		expect(printed).toEqual([
			{
				kind: 'lost',
				records: 'article',
				fault: false,
				quiet: false,
				text: 'There is no article record for 14 Jun 2030, so nothing below that uses this record shows that day. The record for that day was lost and could not be recovered; it was not a quiet day.'
			}
		]);
		const recording = recordingNotes({
			enabled: true,
			recorded: [...new Set(articles.rows.map((row) => row.date))],
			window: ['2030-06-14', '2030-06-15'],
			reads: [articles.read],
			from: '2030-06-13',
			open: { days: 3, start: '2030-06-13', end: '2030-06-15' },
			figures: 'server figures'
		});
		expect(recording.startedMidWindow).toBeNull();
	});
});

test.describe('THE ORACLE: a console window ends on the site\'s newest published day, and reads only its own days', () => {
	test('a record whose rows stop 40 days before the newest published day reads nothing before the window, and the note names its last day', async () => {
		// Published on 14 and 15 Jun 2030. The article record holds one row a day up to
		// 6 May, 40 days before the newest published day, and is packed with empty days
		// from 7 May to 14 Jun, the day before it.
		const { digest, state } = await builtSite(STOPPED);
		expect(daysBefore(PUBLISHED, 40)).toBe('2030-05-06');

		const day = windowDay(digest);
		expect(day).toBe(PUBLISHED);
		const open = { days: 30, ...windowOfDays(day, 30, 'right') };
		expect(open).toEqual({ days: 30, start: '2030-05-17', end: '2030-06-15' });

		const asked: [string, string][] = [];
		const table = await windowRows(state, 'item-health', open, ITEM_HEALTH_COLUMNS, (from, to) => {
			asked.push([from, to]);
			return sliceFromDisk(state, 'item-health', { columns: [...datedFirst(ITEM_HEALTH_COLUMNS)], from, to });
		});
		expect(asked).toEqual([['2030-05-17', '2030-06-15']]);
		expect(table.rows).toEqual([]);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-14',
			first: '2030-05-01',
			lastRows: { period: 'daily', covers: '2030-05-06' },
			lostDays: [],
			setAside: {}
		});
		expect(await itemHealthRows(open, state)).toEqual(table);

		const notes = recordNotes([{ record: 'article', read: table.read }], day, open, offeredOn(day));
		expect(notes.map((note) => note.text)).toEqual([
			'The newest packed rows in the article record are from 6 May 2030. The packed days since then hold no rows, so nothing below that uses this record has anything to show in these 30 days. This page cannot tell if that is a quiet stretch or a fault. The 90-day window reaches back to 6 May 2030.'
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
		const articles = await itemHealthRows(openOn(day, 90), state);
		const recorded = [...new Set(articles.rows.map((row) => row.date))];
		return offered.map((open) => [
			open.days,
			measurementOff({ enabled: false, recorded, read: articles.read, open, offered })
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

test.describe('THE ORACLE: a started line names a start the open window shows, and only a true one', () => {
	/** The started line each window offers, for an article record built with `days` and read over
	 *  the widest window, as the routes read it. The instrument recorded the days the record holds
	 *  rows on, from `recordedFrom`, and every day had a run. A route hands each window the whole
	 *  read, from its first day; a caller may hand only the window's days, from the window's first
	 *  day. Either way no line may be false. */
	async function startedOver(
		days: readonly BuiltDay[],
		handed: 'read' | 'window',
		recordedFrom = '2000-01-01'
	): Promise<[number, string | null][]> {
		const { digest, state } = await builtSite(days);
		const day = windowDay(digest);
		const read = openOn(day, 90);
		const articles = await itemHealthRows(read, state);
		const recorded = [...new Set(articles.rows.map((row) => row.date))].filter((date) => date >= recordedFrom);
		return offeredOn(day).map((open) => {
			const span = handed === 'read' ? read : open;
			return [
				open.days,
				recordingNotes({
					enabled: true,
					recorded: recorded.filter((date) => date >= span.start && date <= span.end),
					window: daysBetween(span.start, span.end),
					reads: [articles.read],
					from: span.start,
					open
				}).startedMidWindow
			];
		});
	}

	/** One row a day from 16 Apr to 31 May 2030, quiet from 1 to 7 Jun, then one row a day to 14
	 *  Jun, the day before the newest published day. The 14-day window, 2 to 15 Jun, starts with
	 *  6 quiet days, so its first recorded day is 8 Jun; the record began on 16 Apr, which only
	 *  the 90-day window, from 18 Mar, holds. */
	const BEGAN_BEFORE = [...everyDay(60, 15), ...quietDays(14, 8), ...everyDay(7, 1)];

	for (const handed of ['read', 'window'] as const) {
		test(`a record that began before a window is never said to start inside it, handed the ${handed}'s days`, async () => {
			expect(await startedOver(BEGAN_BEFORE, handed)).toEqual([
				[1, null],
				[7, null],
				[14, null],
				[30, null],
				[90, 'Server figures started on 16 Apr 2030. Earlier in this window, 29 days had a run but no server figures.']
			]);
		});
	}

	test('a record that began inside a window names its first day there, and in no window that does not show it', async () => {
		// One row a day from 10 to 14 Jun 2030. The 1-day window, 15 Jun, does not show the 10th.
		expect(await startedOver(everyDay(5, 1), 'read')).toEqual([
			[1, null],
			[7, 'Server figures started on 10 Jun 2030. Earlier in this window, 1 day had a run but no server figures.'],
			[14, 'Server figures started on 10 Jun 2030. Earlier in this window, 8 days had a run but no server figures.'],
			[30, 'Server figures started on 10 Jun 2030. Earlier in this window, 24 days had a run but no server figures.'],
			[90, 'Server figures started on 10 Jun 2030. Earlier in this window, 84 days had a run but no server figures.']
		]);
	});

	test('an instrument that began after its record did names its own first day in each window that shows it', async () => {
		// The record holds a row every day from 16 Apr 2030, and this instrument records from 26
		// May: the read holds the record from its first day, so the 26th is when it started.
		expect(await startedOver(everyDay(60, 1), 'read', '2030-05-26')).toEqual([
			[1, null],
			[7, null],
			[14, null],
			[30, 'Server figures started on 26 May 2030. Earlier in this window, 9 days had a run but no server figures.'],
			[90, 'Server figures started on 26 May 2030. Earlier in this window, 69 days had a run but no server figures.']
		]);
	});
});

test.describe("THE ORACLE: native server evidence is independent of article rows", () => {
	test('the real declared host slice keeps migration and counter presence separate from article-only runs', async () => {
		// Published on 14 and 15 Jun 2030. The machine record's indexes begin on 16 May, and it holds
		// no row until 10 Jun, when one run's work job filed the server's two cells; quiet after. The
		// article record holds rows from 31 May, and from 3 Jun one run a day took them on shard 0.
		const { digest } = publishedSite(test.info().outputPath('site'), { published: ['2030-06-14', PUBLISHED] });
		const state = test.info().outputPath('state');
		await buildLedger(state, {
			ledger: 'host-fingerprint',
			pinned: PUBLISHED,
			days: [...quietDays(30, 6), { ago: 5, rows: 2 }, ...quietDays(4, 1)],
			columns: {
				run_id: '2030-06-10-1',
				job: 'work',
				shard: 0,
				fingerprint: 'f00d',
				cores: 4,
				mhz_at_probe: 2445,
				server_prompt_tokens: 900,
				server_prompt_seconds: 9
			}
		});
		const day = windowDay(digest);
		const read = openOn(day, 90);
		const answer = await sliceFromDisk(state, platformMixQuery.ledger, {
			columns: [...platformMixQuery.columns], from: read.start, to: read.end
		});
		expect(answer.state).toBe('ok');
		expect(answer.rows).toHaveLength(2);
		expect(fingerprints(answer.rows).map((host) => [
			host.version, host.fingerprint_version, host.cpu_physical_cores,
			host.cpu_logical_processors, host.cpu_observed_mhz
		])).toEqual([
			['2026-10-10', 1, null, null, 2445],
			['2026-10-10', 1, null, null, 2445]
		]);
		const articles = daysBetween('2030-06-03', '2030-06-14').map((date) => ({
			date,
			run_id: `${date}-1`,
			machine_job: 'work',
			machine_shard: 0
		}));
		const { runs, refused } = countersFrom(answer.rows, articles, [], { contextWindow: null, jobTimeoutSeconds: null });
		expect(refused).toEqual([]);
		expect(runs).toHaveLength(12);
		expect(runs.filter(carriesServerCounters).map((run) => [run.date, run.clocks.server.rate])).toEqual([
			['2030-06-10', 100]
		]);
		expect(runs.filter((run) => run.date !== '2030-06-10').every((run) =>
			run.promptTokens.value === null && run.readSeconds.value === null)).toBe(true);
	});
});

test.describe('THE ORACLE: a score read that did not read is named on the charts it cost a marker, never silent', () => {
	/** Runs on 2 to 14 Jun 2030, and run manifests name what ran from 6 Jun, so a marker on 2 to 5
	 *  Jun could only come from the score record. */
	const RAN = daysBetween('2030-06-02', '2030-06-14');
	const IDENTIFIED = listManifestDays(
		daysBetween('2030-06-06', '2030-06-14').map((date) => ({ date, records: [{ inputs: { model: 'test-model' } }] }))
	);
	const OPEN = openOn(PINNED, 14);
	const others = ' This chart shows every change on the other days.';

	test('a score record with no packed file says it is not packed yet', async () => {
		const state = test.info().outputPath('state');
		mkdirSync(state, { recursive: true });
		const scores = await evalRows(openOn(PINNED, 90), state);
		expect(scores.read).toEqual({ state: 'not-packed' });
		expect(describeMissingMarkers({ read: scores.read, ran: RAN, identified: IDENTIFIED, open: OPEN })).toBe(
			`This chart cannot show whether the setup changed on 2 Jun to 5 Jun 2030, because the score record has not been packed yet. That is a step not yet run.${others}`
		);
	});

	test('a packed file the score record lists and the disk lacks is named as that fault', async () => {
		const state = test.info().outputPath('state');
		await buildLedger(state, { ledger: 'summary-quality-evals', pinned: PINNED, days: everyDay(14, 1) });
		rmSync(path.join(state, 'compact', 'summary-quality-evals', 'daily', '2030', '06', '03.parquet'));
		const scores = await evalRows(openOn(PINNED, 90), state);
		expect(scores.read).toEqual({ state: 'unreadable', at: '2030-06-03', fault: 'file-missing' });
		expect(describeMissingMarkers({ read: scores.read, ran: RAN, identified: IDENTIFIED, open: OPEN })).toBe(
			`This chart cannot show whether the setup changed on 2 Jun to 5 Jun 2030, because the score record lists a packed file for 3 Jun 2030 that is not there. This is a fault to fix.${others}`
		);
	});

	test('a score record that read costs no marker, so no line prints', async () => {
		const state = test.info().outputPath('state');
		await buildLedger(state, { ledger: 'summary-quality-evals', pinned: PINNED, days: everyDay(14, 1) });
		const scores = await evalRows(openOn(PINNED, 90), state);
		expect(scores.read.state).toBe('read');
		expect(describeMissingMarkers({ read: scores.read, ran: RAN, identified: IDENTIFIED, open: OPEN })).toBeNull();
	});
});
