/** Row #17's shard store, and handback #104's calendar walk.
 *
 * The console holds telemetry as revision-owned month shards. This proves the
 * three things the row settled and the one the handback did, at the tier they
 * belong to - a pure reducer over built rows, no browser (`CLAUDE.md` section
 * 13). The wired oracle (a failed fetch heals on a later widen) is the browser
 * spec `console-telemetry-heal.spec.ts`; this file is the data structure under
 * it.
 */

import { expect, test } from '@playwright/test';
import {
	applyShard,
	heldMonths,
	holdRows,
	monthCeiling,
	monthsToLoad,
	seedHold,
	type TelemetryHold
} from '../src/lib/charts/telemetry-hold';
import type { TelemetryRow } from '../src/lib/charts/series';
import { daysInWindow, monthsInWindow, type TimeWindow } from '../src/lib/charts/viewport';

/** A telemetry row with only the fields an identity and a date need set. */
function trow(date: string, run: string, item: string, stage: string): TelemetryRow {
	return {
		date,
		run_id: run,
		item_id: item,
		vertical: 'ai',
		source_id: 'src',
		stage,
		outcome: 'ok',
		code: '',
		source_words: null,
		summary_words: null,
		source_words_before_cap: null,
		fetch_ms: null,
		extract_ms: null,
		summarize_ms: null,
		prefill_ms: null,
		decode_ms: null,
		input_tokens: null,
		output_tokens: null,
		cached_tokens: null
	};
}

/** The identities held, sorted, so a test can say what survived a merge. */
function heldIdentities(hold: TelemetryHold): string[] {
	return holdRows(hold)
		.map((row) => `${row.date}/${row.run_id}/${row.item_id}/${row.stage}`)
		.sort();
}

test('an observation is a run, an item AND a stage, so distinct stages both survive', () => {
	// Andre, decision 3. The old merge keyed on run+item, so fetch, extract,
	// summarize and publish for one item collapsed to whichever was seen last -
	// the failure-by-stage panels then read three missing stages. The stage is
	// part of the identity, so one item's four rows are four rows.
	const rows = [
		trow('2026-08-10', 'r1', 'a', 'fetch'),
		trow('2026-08-10', 'r1', 'a', 'extract'),
		trow('2026-08-10', 'r1', 'a', 'summarize'),
		trow('2026-08-10', 'r1', 'a', 'publish')
	];
	const hold = seedHold(rows, '2026-08-01');
	expect(holdRows(hold)).toHaveLength(4);
	expect(new Set(holdRows(hold).map((row) => row.stage))).toEqual(
		new Set(['fetch', 'extract', 'summarize', 'publish'])
	);
});

test('a failed fetch marks nothing, so a later widen still wants the month', () => {
	// The row's oracle, at the reducer. The seed covers 2026-08 back to 07-22;
	// month 2026-07 has older rows the seed never reached. A window that reaches
	// into 2026-07 wants it - and goes on wanting it until a shard actually
	// arrives, because nothing but `applyShard` marks a month in hand.
	const hold = seedHold([trow('2026-08-10', 'r1', 'a', 'publish')], '2026-07-22');
	const available = ['2026-07', '2026-08'];
	const wide: TimeWindow = { start: '2026-05-23', end: '2026-08-20' };

	// Widen: 2026-07 is wanted (older than the seed reach), 2026-08 is not.
	expect(monthsToLoad(hold, wide, available)).toEqual(['2026-07']);
	// A fetch that failed applies no shard, so the month is wanted again.
	expect(monthsToLoad(hold, wide, available)).toEqual(['2026-07']);
	// The fetch succeeds this time: the month is in hand and no longer wanted.
	const filled = applyShard(hold, '2026-07', [trow('2026-07-11', 'r0', 'z', 'publish')], 15);
	expect(monthsToLoad(filled, wide, available)).toEqual([]);
	expect(holdRows(filled).some((row) => row.date === '2026-07-11')).toBe(true);
});

test('a month the pipeline never published is never wanted', () => {
	const hold = seedHold([trow('2026-08-10', 'r1', 'a', 'publish')], '2026-08-01');
	// 2026-05 and 2026-06 are in the window but not on the server: asking for
	// them would only 404. Only the published, unseeded month is wanted.
	const wide: TimeWindow = { start: '2026-05-23', end: '2026-08-20' };
	expect(monthsToLoad(hold, wide, ['2026-07', '2026-08'])).toEqual(['2026-07']);
});

test('the default window fetches nothing: the seed already covers it', () => {
	const hold = seedHold([trow('2026-08-10', 'r1', 'a', 'publish')], '2026-07-22');
	const within: TimeWindow = { start: '2026-07-22', end: '2026-08-20' };
	expect(monthsToLoad(hold, within, ['2026-07', '2026-08'])).toEqual([]);
});

test('a shard replaces its own rows, so a corrected-away row is retracted', () => {
	// Fowler, decision 2. The old merge only ever added, so a row a re-run
	// dropped lived on. A shard owns its month: applying it again with one row
	// gone takes that row off the page.
	let hold = seedHold([], null);
	hold = applyShard(
		hold,
		'2026-07',
		[trow('2026-07-11', 'r0', 'a', 'publish'), trow('2026-07-11', 'r0', 'b', 'publish')],
		15
	);
	expect(heldIdentities(hold)).toEqual([
		'2026-07-11/r0/a/publish',
		'2026-07-11/r0/b/publish'
	]);
	// The correction re-fetches 2026-07 with `b` removed.
	hold = applyShard(hold, '2026-07', [trow('2026-07-11', 'r0', 'a', 'publish')], 15);
	expect(heldIdentities(hold)).toEqual(['2026-07-11/r0/a/publish']);
});

test('a shard owns only its own month, so a stray row is ignored', () => {
	let hold = seedHold([], null);
	hold = applyShard(
		hold,
		'2026-07',
		[trow('2026-07-11', 'r0', 'a', 'publish'), trow('2026-08-01', 'r0', 'b', 'publish')],
		15
	);
	expect(heldIdentities(hold)).toEqual(['2026-07-11/r0/a/publish']);
});

test('held fetched months are bounded, oldest touch first, and never the seed', () => {
	// Carmack, decision 1. The seed is the fallback and a fixed size, so it is
	// never evicted; the fetched shards are what a long session of panning
	// accumulates, and the ceiling bounds them. Oldest touch goes first.
	let hold = seedHold([trow('2026-12-05', 'r', 'seed', 'publish')], '2026-12-01');
	const ceiling = 3;
	for (const month of ['2026-06', '2026-07', '2026-08', '2026-09', '2026-10']) {
		hold = applyShard(hold, month, [trow(`${month}-15`, 'r', 'x', 'publish')], ceiling);
	}
	// The seed month stays, and only the three newest-touched fetched months.
	expect(heldMonths(hold)).toEqual(['2026-08', '2026-09', '2026-10', '2026-12']);
});

test('re-touching a month keeps it, evicting an older one instead', () => {
	let hold = seedHold([], null);
	const ceiling = 2;
	hold = applyShard(hold, '2026-06', [trow('2026-06-15', 'r', 'x', 'publish')], ceiling);
	hold = applyShard(hold, '2026-07', [trow('2026-07-15', 'r', 'x', 'publish')], ceiling);
	// Re-fetching 2026-06 moves it to the newest touch. Adding 2026-08 now evicts
	// 2026-07, the oldest touch, not 2026-06.
	hold = applyShard(hold, '2026-06', [trow('2026-06-16', 'r', 'y', 'publish')], ceiling);
	hold = applyShard(hold, '2026-08', [trow('2026-08-15', 'r', 'x', 'publish')], ceiling);
	expect(heldMonths(hold)).toEqual(['2026-06', '2026-08']);
});

test('the ceiling is the months the widest window can touch, and never zero', () => {
	// From the knob, not a literal: 366 days touches at most 15 calendar months,
	// so the widest read is always in hand. 30 days can touch three - Jan 31,
	// February, March 1 - so the ceiling is a safe over-count, never an under.
	expect(monthCeiling(366)).toBe(15);
	expect(monthCeiling(30)).toBe(3);
	expect(monthCeiling(1)).toBe(1);
	expect(monthCeiling(0)).toBe(1);
});

/** Handback #104: months by day-walk, the arithmetic being replaced. */
function monthsByDay(window: TimeWindow): string[] {
	const months: string[] = [];
	for (const day of daysInWindow(window)) {
		const month = day.slice(0, 7);
		if (!months.includes(month)) months.push(month);
	}
	return months;
}

test('handback 104: monthsInWindow is by month, and identical to the day walk', () => {
	// The oracle: the same months for any window, but stepped by month rather
	// than by day. Held against the day-walk reference over single days, month
	// seams, a year seam and a window wider than a year.
	const windows: TimeWindow[] = [
		{ start: '2026-08-20', end: '2026-08-20' },
		{ start: '2026-07-31', end: '2026-08-01' },
		{ start: '2026-05-23', end: '2026-08-20' },
		{ start: '2026-12-15', end: '2027-01-14' },
		{ start: '2025-12-31', end: '2026-12-31' },
		{ start: '2024-01-01', end: '2025-03-15' }
	];
	for (const window of windows) {
		expect(monthsInWindow(window), `${window.start}..${window.end}`).toEqual(monthsByDay(window));
	}
	// And the shapes the reference is too slow to be worth checking every day:
	// the months are in order and unique, and the seam months are both present.
	expect(monthsInWindow({ start: '2026-12-15', end: '2027-01-14' })).toEqual(['2026-12', '2027-01']);
	expect(monthsInWindow({ start: '2025-12-31', end: '2026-12-31' })).toHaveLength(13);
});
