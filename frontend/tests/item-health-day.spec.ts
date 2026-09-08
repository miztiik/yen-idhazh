import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { itemHealthForDay, readShards } from '../src/lib/server/payload';

/**
 * Row 24: the standing console band reads the newest published day's item-health
 * from that one month's shard, never a walk of every shard.
 *
 * All in plain Node against fixtures, so nothing depends on the committed
 * archive (`CLAUDE.md` section 13). The claim is Rule #12: the band's health
 * read opens a fixed number of files whatever the archive holds behind it. The
 * proof is by construction - a row bearing the target date is planted in every
 * OTHER month's shard, and the reader still returns only the row in the target
 * month's own shard, because it opens `<month-of-date>.csv` and nothing else. A
 * reader that listed the directory would return them all. The contrast case
 * shows exactly that: `readShards`, the whole-archive read the band no longer
 * uses, returns every planted row, so its cost is the shard count and not the
 * day.
 */

const COLUMNS = 'date,run_id,item_id,outcome,code,summarize_ms';

function shard(root: string, month: string, rows: string[]): void {
	mkdirSync(join(root, 'item-health'), { recursive: true });
	writeFileSync(join(root, 'item-health', `${month}.csv`), [COLUMNS, ...rows].join('\n'), 'utf8');
}

function row(date: string, itemId: string): string {
	return `${date},r1,${itemId},ok,,1200`;
}

test('itemHealthForDay opens the target month shard alone, whatever else is in the tree', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		const target = '2026-09-15';
		// The target date's row sits in its own month. Every other month carries a
		// decoy row bearing the SAME date: a reader that scanned the tree would pick
		// them up, and this one may not.
		shard(root, '2026-09', [row(target, 'real')]);
		shard(root, '2026-08', [row(target, 'decoy-08')]);
		shard(root, '2026-07', [row(target, 'decoy-07')]);

		const rows = itemHealthForDay(target, root);
		expect(rows.map((entry) => entry.item_id)).toEqual(['real']);

		// The whole-archive read the band dropped returns every planted row, so its
		// cost is the shard count and not the day - the exact defect this row removes.
		const walked = readShards(join(root, 'item-health')).rows.filter(
			(entry) => entry.date === target
		);
		expect(walked.map((entry) => entry.item_id).sort()).toEqual(['decoy-07', 'decoy-08', 'real']);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('itemHealthForDay stays one file as the archive grows behind it', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		const target = '2026-09-15';
		shard(root, '2026-09', [row(target, 'real'), row('2026-09-14', 'other-day')]);
		// Two years of older months, each with a decoy on the target date. The
		// answer may not move, because none of these files is the target month's
		// shard - so the read the band makes cannot grow with the archive.
		for (let year = 2024; year <= 2025; year += 1) {
			for (let month = 1; month <= 12; month += 1) {
				const stem = `${year}-${String(month).padStart(2, '0')}`;
				shard(root, stem, [row(target, `decoy-${stem}`)]);
			}
		}
		expect(itemHealthForDay(target, root).map((entry) => entry.item_id)).toEqual(['real']);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('itemHealthForDay degrades to no rows when the month shard or date is absent', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		shard(root, '2026-09', [row('2026-09-15', 'real')]);
		// A month with no shard yet reads nothing, does not throw, and does not walk
		// the tree looking for one.
		expect(itemHealthForDay('2026-10-01', root)).toEqual([]);
		// A malformed date reads nothing rather than constructing a bad path.
		expect(itemHealthForDay('not-a-date', root)).toEqual([]);
		// A date whose month shard exists but holds no such day is empty.
		expect(itemHealthForDay('2026-09-16', root)).toEqual([]);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
