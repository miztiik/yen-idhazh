import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { machineRecordDays } from '../src/lib/server/host-fingerprint';
import {
	dayShardFiles,
	ITEM_HEALTH_KEY,
	ITEM_HEALTH_RULE,
	OBSERVATION_KEY,
	readDayShards,
	settledDayShards,
	settleRows
} from '../src/lib/server/payload';

/**
 * The server-side day walk: a day is a `<DD>/` directory of writer-owned files,
 * the cover counts days rather than files, and a name the walk cannot place is
 * skipped rather than thrown over. Plus the settlement the keyed reads apply to
 * what that walk hands back, because two writers describe every record.
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

/**
 * The settlement `itemHealthRows` and `evalRows` apply to what the walk above
 * hands back.
 *
 * A day directory holds one file per writer, and two writers describe every
 * record: the work shard as the item settles, and assemble over the whole day
 * afterwards. Both files are the same day to the walk, so both accounts of one
 * record reach a reader that does not settle them - which is a doubled count on
 * every console panel and a repeated key in every list drawn per item.
 *
 * `ledger.ITEM_HEALTH_KEY`, `ledger.ITEM_HEALTH_RULE` and
 * `ledger.OBSERVATION_KEY` are the backend twins. Rows are built here rather
 * than read from the archive, so the cost of this cannot follow what the
 * pipeline has piled up (`CLAUDE.md` section 13).
 */
function census(cells: Record<string, string> = {}): Record<string, string> {
	return {
		date: '2026-09-23',
		run_id: '2026-09-23-1',
		item_id: 'ai-one',
		job: 'work',
		shard: '3',
		outcome: 'ok',
		...cells
	};
}

const settledCensus = (rows: readonly Record<string, string>[]) =>
	settleRows(rows, ITEM_HEALTH_KEY, ITEM_HEALTH_RULE);

test('two jobs describing one item settle to one row', () => {
	// The shape the committed ledger holds on the day a run is publishing:
	// assemble re-states the row the shard sealed, cell for cell.
	const rows = [census({ job: 'assemble', shard: '0' }), census()];

	expect(settledCensus(rows)).toHaveLength(1);
	// The defect this closes: a list keyed by item id draws one story twice.
	expect(settledCensus(rows).map((entry) => entry.item_id)).toEqual(['ai-one']);
});

test('each cell of the key separates two records rather than collapsing them', () => {
	// Three rows that repeat the item id and differ in one key cell each. None of
	// them is a repeat, so a settlement keyed on the item id alone would report
	// one run's work as three days of it - or three runs as one.
	const rows = [
		census(),
		census({ date: '2026-09-22' }),
		census({ run_id: '2026-09-23-2' }),
		census({ item_id: 'ai-two' })
	];

	expect(settledCensus(rows)).toHaveLength(4);
});

test('the row that names the job beats the row that does not, whichever arrived first', () => {
	// `job` and `shard` are the one moment either is known: a shard's rebuild
	// carries them, and assemble's rebuild leaves both empty because it ran on a
	// machine that read none of the items. The identity is better evidence than
	// its absence, so arrival order does not decide.
	const named = census({ job: 'work', shard: '3' });
	const anonymous = census({ job: '', shard: '' });

	expect(settledCensus([anonymous, named])).toEqual([named]);
	expect(settledCensus([named, anonymous])).toEqual([named]);
});

test('the settlement reads the day the walk built, not a list somebody handed it', () => {
	const root = mkdtempSync(join(tmpdir(), 'item-health-'));
	try {
		const date = '2026-09-23';
		const dir = join(root, 'item-health', '2026', '09', '23');
		mkdirSync(dir, { recursive: true });
		const columns = 'date,run_id,item_id,job,shard,outcome';
		const entry = (itemId: string, job: string, shard: string) =>
			`${date},${date}-1,${itemId},${job},${shard},ok`;
		// Both shapes the two writers really produce, taken from the committed
		// ledger. For an item a shard sealed a record for, assemble re-states that
		// row cell for cell - `job` says `work` in assemble's own file, and no row
		// in the tree has ever said `assemble`. For an item no shard sealed one,
		// assemble has no job or shard to name and leaves both empty.
		//
		// Sorted by name, so assemble is read first either way - the order the
		// arrival of the two files used to decide by.
		writeFileSync(
			join(dir, `${date}-35833646522-1-assemble-00.csv`),
			[columns, entry('ai-sealed', 'work', '3'), entry('ai-unsealed', '', '')].join('\n'),
			'utf8'
		);
		writeFileSync(
			join(dir, `${date}-35833646522-1-work-03.csv`),
			[columns, entry('ai-sealed', 'work', '3'), entry('ai-unsealed', 'work', '3')].join('\n'),
			'utf8'
		);

		const walked = join(root, 'item-health');
		expect(readDayShards(walked, -1).rows, 'the day really does hold both writers').toHaveLength(
			4
		);
		const settled = settledDayShards(walked, ITEM_HEALTH_KEY, ITEM_HEALTH_RULE, -1);
		expect(settled.rows.map((row) => row.item_id)).toEqual(['ai-sealed', 'ai-unsealed']);
		// The rule earns its keep on the unsealed item: assemble's row arrived
		// first and names no job, so keeping the first would have lost the shard.
		expect(settled.rows.map((row) => row.shard)).toEqual(['3', '3']);
		// The header survives the settlement: a panel reads columns from the table
		// it was handed, and an empty header draws an empty panel.
		expect(settled.columns).toEqual(columns.split(','));
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

/**
 * `state/scores/` is the same shape with a different key and no preference.
 *
 * `ledger.OBSERVATION_KEY` is the address, the digest of the words that came
 * out, and the version of the instrument that read them. It carries no date, so
 * the day a key is filed under is not part of what makes two rows one record -
 * which is exactly why the settlement is per day and not over the whole cover.
 */
const SCORE_COLUMNS = 'date,url_key,output_digest,scorer_version,faithfulness';

function scoreDay(root: string, date: string, files: Record<string, string[]>): void {
	const dir = join(root, 'scores', date.slice(0, 4), date.slice(5, 7), date.slice(8, 10));
	mkdirSync(dir, { recursive: true });
	for (const [name, rows] of Object.entries(files)) {
		writeFileSync(join(dir, name), [SCORE_COLUMNS, ...rows].join('\n'), 'utf8');
	}
}

function score(date: string, urlKey: string, faithfulness: string): string {
	return `${date},${urlKey},d33c,hhem-2.1@1,${faithfulness}`;
}

test('two jobs scoring one observation settle to one row', () => {
	const root = mkdtempSync(join(tmpdir(), 'scores-'));
	try {
		const date = '2026-09-23';
		scoreDay(root, date, {
			[`${date}-1-assemble-00.csv`]: [score(date, 'an-article', '0.91')],
			[`${date}-1-work-03.csv`]: [score(date, 'an-article', '0.91')]
		});
		const dir = join(root, 'scores');

		expect(readDayShards(dir, -1).rows, 'the day really does hold both writers').toHaveLength(2);
		expect(settledDayShards(dir, OBSERVATION_KEY, undefined, -1).rows).toHaveLength(1);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('a key with no preference keeps the first row it saw', () => {
	// The backend reads an absent preference as keep-first, because a repeat
	// under this key is one attempt written twice and the two rows agree. The
	// committed ledger bears that out: measured 2026-09-23, all 204 repeated
	// keys of the publishing day agreed cell for cell.
	const first = { url_key: 'a', output_digest: 'd', scorer_version: 'v', faithfulness: '0.91' };
	const second = { ...first, faithfulness: '0.42' };

	expect(settleRows([first, second], OBSERVATION_KEY)).toEqual([first]);
	expect(settleRows([second, first], OBSERVATION_KEY)).toEqual([second]);
});

test('one key on two days is two measurements, not a repeat', () => {
	const root = mkdtempSync(join(tmpdir(), 'scores-'));
	try {
		// The same article, the same words, the same instrument, measured on two
		// days. `OBSERVATION_KEY` carries no date, so a settlement over the
		// flattened walk would delete the second - and the committed ledger holds
		// exactly one of these, measured 2026-09-23 across 12,463 keys.
		scoreDay(root, '2026-09-19', { '2026-09-19-1-work-00.csv': [score('2026-09-19', 'a', '0.9')] });
		scoreDay(root, '2026-09-20', { '2026-09-20-1-work-00.csv': [score('2026-09-20', 'a', '0.9')] });
		const dir = join(root, 'scores');

		const settled = settledDayShards(dir, OBSERVATION_KEY, undefined, -1);
		expect(settled.rows.map((entry) => entry.date)).toEqual(['2026-09-19', '2026-09-20']);
		// And the cover still bounds it, so neither the settlement nor the walk
		// grows with the archive (Guardrail #12).
		expect(settledDayShards(dir, OBSERVATION_KEY, undefined, 1).rows).toHaveLength(1);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
