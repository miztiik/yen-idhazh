import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { machineRecordDays } from '../src/lib/server/host-fingerprint';
import { dayShardFiles, itemHealthForDay, readDayShards } from '../src/lib/server/payload';

/**
 * Row 24: the standing console band reads the newest published day's item-health
 * from that one day's file, never a walk of the ledger.
 *
 * All in plain Node against fixtures, so nothing depends on the committed
 * archive (`CLAUDE.md` section 13). The claim is Guardrail #12: the band's health
 * read opens a fixed number of files whatever the archive holds behind it. The
 * proof is by construction - a row bearing the target date is planted in every
 * OTHER day's file, and the reader still returns only the row in the target
 * day's own file, because it opens `<YYYY>/<MM>/<DD>.csv` and nothing else. A
 * reader that walked the tree would return them all. The contrast case shows
 * exactly that: `readDayShards`, the windowed read the band does not use, returns
 * every planted row, so its cost is the day count and not the day.
 *
 * **The decoys are what the grain change made stronger.** At month grain a decoy
 * had to live in another month, so a reader that opened the right month and
 * filtered by date still passed. Here one sits in the day file next door, so only
 * a reader that names a single file passes.
 */

const COLUMNS = 'date,run_id,item_id,outcome,code,summarize_ms';

function day(root: string, date: string, rows: string[]): void {
	const dir = join(root, 'item-health', date.slice(0, 4), date.slice(5, 7));
	mkdirSync(dir, { recursive: true });
	writeFileSync(join(dir, `${date.slice(8, 10)}.csv`), [COLUMNS, ...rows].join('\n'), 'utf8');
}

function row(date: string, itemId: string): string {
	return `${date},r1,${itemId},ok,,1200`;
}

test('itemHealthForDay opens the target day file alone, whatever else is in the tree', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		const target = '2026-09-15';
		// The target date's row sits in its own day file. Its neighbour and a file a
		// month back each carry a decoy row bearing the SAME date: a reader that
		// walked the tree would pick them up, and this one may not.
		day(root, target, [row(target, 'real')]);
		day(root, '2026-09-14', [row(target, 'decoy-next-door')]);
		day(root, '2026-08-15', [row(target, 'decoy-last-month')]);

		const rows = itemHealthForDay(target, root);
		expect(rows.map((entry) => entry.item_id)).toEqual(['real']);

		// The windowed read returns every planted row, so its cost is the day count
		// and not the day - the exact defect naming one file removes.
		const walked = readDayShards(join(root, 'item-health'), -1).rows.filter(
			(entry) => entry.date === target
		);
		expect(walked.map((entry) => entry.item_id).sort()).toEqual([
			'decoy-last-month',
			'decoy-next-door',
			'real'
		]);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('itemHealthForDay stays one file as the archive grows behind it', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		const target = '2026-09-15';
		day(root, target, [row(target, 'real')]);
		day(root, '2026-09-14', [row('2026-09-14', 'other-day')]);
		// Two years of older days, each with a decoy on the target date. The answer
		// may not move, because none of these files is the target day's - so the
		// read the band makes cannot grow with the archive.
		for (let year = 2024; year <= 2025; year += 1) {
			for (let month = 1; month <= 12; month += 1) {
				const stem = `${year}-${String(month).padStart(2, '0')}-05`;
				day(root, stem, [row(target, `decoy-${stem}`)]);
			}
		}
		expect(itemHealthForDay(target, root).map((entry) => entry.item_id)).toEqual(['real']);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('itemHealthForDay degrades to no rows when the day file or date is absent', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		day(root, '2026-09-15', [row('2026-09-15', 'real')]);
		// A day with no file reads nothing, does not throw, and does not walk the
		// tree looking for one. A month the tree has never held is the same.
		expect(itemHealthForDay('2026-09-16', root)).toEqual([]);
		expect(itemHealthForDay('2026-10-01', root)).toEqual([]);
		// A malformed date reads nothing rather than constructing a bad path. A
		// month stem is malformed here where it was the whole address before.
		expect(itemHealthForDay('not-a-date', root)).toEqual([]);
		expect(itemHealthForDay('2026-09', root)).toEqual([]);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('readDayShards keeps the newest recorded days and opens nothing behind them', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		// Five recorded days across a month boundary, so the slice has a boundary to
		// cross rather than only a run of stems in one directory.
		for (const date of ['2026-08-30', '2026-08-31', '2026-09-01', '2026-09-02', '2026-09-03']) {
			day(root, date, [row(date, `item-${date}`)]);
		}
		const dir = join(root, 'item-health');

		expect(readDayShards(dir, 2).rows.map((entry) => entry.date)).toEqual([
			'2026-09-02',
			'2026-09-03'
		]);
		expect(readDayShards(dir, -1).rows).toHaveLength(5);
		// A cover wider than the record is not an error and not a starve.
		expect(readDayShards(dir, 90).rows).toHaveLength(5);
		expect(readDayShards(join(root, 'nothing-here'), 7).rows).toEqual([]);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

/**
 * Row 5 of the no-file-has-two-writers plan: a day is a `<DD>.csv` file today
 * and a `<DD>/` directory of writer-owned files once more than one job writes
 * the ledger, and every reader here has to take both.
 *
 * Nothing writes a directory yet, so the fixture is where the second shape
 * exists at all. Committed, read inside the test, and small enough that its
 * cost cannot follow what the archive holds (`CLAUDE.md` section 13).
 */
const SHAPES = join(import.meta.dirname, 'fixtures', 'day-shards');

test('dayShardFiles reads a day file and a day directory as one ledger', () => {
	const dir = join(SHAPES, 'item-health');

	expect(dayShardFiles(dir, -1).map((shard) => shard.date)).toEqual([
		'2026-09-17',
		'2026-09-18',
		'2026-09-18'
	]);
	// The cover counts recorded days, never files. The newest day is two writer
	// files and it is still one day, so a cover of 1 takes both of them.
	expect(dayShardFiles(dir, 1).map((shard) => shard.date)).toEqual(['2026-09-18', '2026-09-18']);
	expect(readDayShards(dir, -1).rows.map((entry) => entry.item_id)).toEqual([
		'a-day-file-item',
		'shard-zero-item',
		'shard-one-item'
	]);
	// A cover of 1 reads the day directory whole and opens nothing behind it.
	expect(readDayShards(dir, 1).rows.map((entry) => entry.item_id)).toEqual([
		'shard-zero-item',
		'shard-one-item'
	]);
});

test('machineRecordDays reports one date a day, however many files the day holds', () => {
	// The record's own day directory holds two writer files. A reader asking
	// which days the instrument ran gets one answer for that day, not two.
	expect(machineRecordDays(-1, SHAPES)).toEqual(['2026-09-18']);
});

test('a day directory with no readable file stops the read rather than drawing nothing', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-shards-'));
	try {
		// Not in the committed fixture, because git carries no empty directory.
		mkdirSync(join(root, 'item-health', '2026', '09', '18'), { recursive: true });
		expect(() => dayShardFiles(join(root, 'item-health'), -1)).toThrow(
			/day directory with no readable \.csv file/
		);
		// A stray anywhere else is still skipped: the producer refuses it at write
		// time, and a throw here would white-screen a page over one file.
		writeFileSync(join(root, 'item-health', '2026', '09', 'notes.txt'), '', 'utf8');
		mkdirSync(join(root, 'scores', '2026', '09'), { recursive: true });
		writeFileSync(join(root, 'scores', '2026', '09', 'notes.txt'), '', 'utf8');
		expect(dayShardFiles(join(root, 'scores'), -1)).toEqual([]);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
