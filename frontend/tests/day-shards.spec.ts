import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { machineRecordDays } from '../src/lib/server/host-fingerprint';
import { dayShardFiles, readDayShards } from '../src/lib/server/payload';

/**
 * The server-side day walk: a day is a `<DD>/` directory of writer-owned files,
 * the cover counts days rather than files, and a name the walk cannot place is
 * skipped rather than thrown over.
 *
 * All in plain Node against fixtures, so nothing depends on the committed
 * archive (`CLAUDE.md` section 13). The claim the cover carries is Guardrail #12:
 * `LEDGER_WINDOW_DAYS` keeps meaning the newest recorded days however many files
 * a day holds, so the read cannot grow with the archive behind it.
 */

const COLUMNS = 'date,run_id,item_id,outcome,code,summarize_ms';

/** One recorded day: a `<DD>/` directory holding one writer's file. */
function day(root: string, date: string, rows: string[]): void {
	const dir = join(root, 'item-health', date.slice(0, 4), date.slice(5, 7), date.slice(8, 10));
	mkdirSync(dir, { recursive: true });
	writeFileSync(
		join(dir, `${date}-1-1-work-00.csv`),
		[COLUMNS, ...rows].join('\n'),
		'utf8'
	);
}

function row(date: string, itemId: string): string {
	return `${date},r1,${itemId},ok,,1200`;
}

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

test('a <DD>.csv beside the day directories is not a recorded day', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		const target = '2026-09-15';
		day(root, target, [row(target, 'real')]);
		// There is no head above a day, so this name is one no writer spells. A
		// reader that still took it would report a day twice - once from the file
		// and once from the directory beside it.
		writeFileSync(
			join(root, 'item-health', '2026', '09', '14.csv'),
			[COLUMNS, row('2026-09-14', 'a-day-file-item')].join('\n'),
			'utf8'
		);

		const dir = join(root, 'item-health');
		expect(dayShardFiles(dir, -1).map((shard) => shard.date)).toEqual([target]);
		expect(readDayShards(dir, -1).rows.map((entry) => entry.item_id)).toEqual(['real']);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

/**
 * A day directory of writer-owned files, committed rather than built on the
 * spot: the shape is the thing under test and a fixture a person can open is
 * the cheapest description of it. Read inside the test, and small enough that
 * its cost cannot follow what the archive holds (`CLAUDE.md` section 13).
 */
const SHAPES = join(import.meta.dirname, 'fixtures', 'day-shards');

test('dayShardFiles reads every writer file of a day as one recorded day', () => {
	const dir = join(SHAPES, 'item-health');

	expect(dayShardFiles(dir, -1).map((shard) => shard.date)).toEqual(['2026-09-18', '2026-09-18']);
	// The cover counts recorded days, never files. The day is two writer files
	// and it is still one day, so a cover of 1 takes both of them.
	expect(dayShardFiles(dir, 1).map((shard) => shard.date)).toEqual(['2026-09-18', '2026-09-18']);
	expect(readDayShards(dir, -1).rows.map((entry) => entry.item_id)).toEqual([
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
