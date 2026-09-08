import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { dayMetrics } from '../src/lib/server/payload';
import { evalDays, type DayScoredCounts, type EvalInput } from '../src/lib/console/eval-instruments';
import { modelWork } from '../src/lib/server/model-work';

/**
 * Row 23: the console reads the three published-set counts back from the day
 * record instead of counting score-ledger rows.
 *
 * Three things are checked here, all in plain Node against fixtures so nothing
 * depends on the committed archive (`CLAUDE.md` section 13). First, the reader
 * opens only the dates it is asked for - never a listing of the tree - so its
 * cost is the window and not the archive (Rule #12). Second, `evalDays` and
 * `modelWork` take the distinct-published counts from the record where a day has
 * one, and fall back to the row counts where it does not. Third, every
 * measurement distribution still reads every row, so a re-score still counts
 * twice where a median means it to.
 */

// --- the reader opens the window, not the archive ---------------------------

function recordText(scored: number, drift = 0, suspect = 0): string {
	return JSON.stringify({
		summaries_scored: scored,
		determinism_violations: drift,
		extraction_suspect: suspect
	});
}

function writeRecord(root: string, date: string, body: string): void {
	const [year, month, day] = date.split('-');
	mkdirSync(join(root, 'day-metrics', year, month), { recursive: true });
	writeFileSync(join(root, 'day-metrics', year, month, `${day}.json`), body, 'utf8');
}

test('dayMetrics opens only the dates asked for, whatever else is in the tree', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		writeRecord(root, '2026-08-20', recordText(8));
		writeRecord(root, '2026-08-21', recordText(5, 1, 2));
		writeRecord(root, '2026-08-22', recordText(3));

		// A one-day window reads one record and the two beside it stay untouched,
		// so the cost is the window and not the tree it sits in.
		const one = dayMetrics(['2026-08-21'], root);
		expect([...one.keys()]).toEqual(['2026-08-21']);
		expect(one.get('2026-08-21')).toEqual({
			date: '2026-08-21',
			summariesScored: 5,
			determinismViolations: 1,
			extractionSuspect: 2,
			// This fixture carries only the strict triple, so the band's two extra
			// counts read null (they are proven present further down).
			notSure: null,
			itemsTruncated: null
		});

		// A date with no record is skipped, not walked to. The caller falls back
		// to the ledger for it.
		const some = dayMetrics(['2026-08-20', '2099-01-01'], root);
		expect([...some.keys()]).toEqual(['2026-08-20']);

		// No dates, no reads.
		expect(dayMetrics([], root).size).toBe(0);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('dayMetrics degrades a malformed record instead of failing the build', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		writeRecord(root, '2026-08-20', '{ not json');
		writeRecord(root, '2026-08-21', JSON.stringify({ summaries_scored: 'seven' }));
		writeRecord(root, '2026-08-22', recordText(4));

		const found = dayMetrics(['2026-08-20', '2026-08-21', '2026-08-22'], root);
		// The unreadable and the wrong-typed records drop out; the caller reads
		// the ledger for those two days. The good day is read.
		expect([...found.keys()]).toEqual(['2026-08-22']);
		expect(found.get('2026-08-22')?.summariesScored).toBe(4);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

// --- the reducers take the count from the record where it has one -----------

const DATE = '2026-08-29';
const LEAD_FLOOR = 0.3;

/**
 * A day whose ledger holds more rows than the day published: item `a` re-scored
 * under a second stamp (two rows, one item), and item `gone` scored then
 * dropped (a row for an item no published day holds). Four rows, three distinct
 * ids, and the record says two distinct items were published, one drifting and
 * one extraction-suspect.
 */
const ROWS: EvalInput[] = [
	{ date: DATE, item_id: 'a', hhem: '0.9', coverage: '0.8', determinism_violation: 'True', extraction_suspect: 'False' },
	{ date: DATE, item_id: 'a', hhem: '0.7', coverage: '0.6', determinism_violation: 'True', extraction_suspect: 'False' },
	{ date: DATE, item_id: 'b', hhem: '0.5', coverage: '0.4', determinism_violation: 'False', extraction_suspect: 'True' },
	{ date: DATE, item_id: 'gone', hhem: '0.3', coverage: '0.2', determinism_violation: 'True', extraction_suspect: 'True' }
];

const SETTLED = new Map<string, DayScoredCounts>([
	[DATE, { scored: 2, determinismViolations: 1, extractionSuspect: 1 }]
]);

test('evalDays without a record counts the ledger rows, as it always did', () => {
	const [day] = evalDays(ROWS, LEAD_FLOOR);
	expect(day.scored).toBe(4);
	expect(day.fired.determinism_violation).toBe(3);
	expect(day.fired.extraction_suspect).toBe(2);
});

test('evalDays with a record counts the distinct-published items', () => {
	const [day] = evalDays(ROWS, LEAD_FLOOR, SETTLED);
	// The three published-set counts are corrected.
	expect(day.scored).toBe(2);
	expect(day.fired.determinism_violation).toBe(1);
	expect(day.fired.extraction_suspect).toBe(1);
	// Every measurement distribution still reads every row: four hhem readings,
	// and the median is the same number the rows gave without the record.
	expect(day.matched).toBe(4);
	expect(day.matchMid).toBe(evalDays(ROWS, LEAD_FLOOR)[0].matchMid);
});

const SCORES: Record<string, string>[] = ROWS.map((row) => ({ ...row, model_id: 'm' })) as Record<
	string,
	string
>[];

test('modelWork without a record reports the ledger row count', () => {
	const [row] = modelWork(SCORES, []);
	expect(row.kind).toBe('day');
	if (row.kind === 'day') expect(row.day.summaries).toBe(4);
});

test('modelWork with a record reports the distinct-published count', () => {
	const [row] = modelWork(SCORES, [], SETTLED);
	expect(row.kind).toBe('day');
	if (row.kind === 'day') expect(row.day.summaries).toBe(2);
});

test('modelWork keeps null summaries for a day the scorer never ran', () => {
	// A day with a summarize timing but no score row: the record would say zero
	// distinct scored, but the panel means "the scorer never ran", which a zero
	// cannot say. Null is preserved whether or not a record is handed in.
	const health: Record<string, string>[] = [{ date: DATE, summarize_ms: '1200' }];
	const zero = new Map<string, DayScoredCounts>([
		[DATE, { scored: 0, determinismViolations: 0, extractionSuspect: 0 }]
	]);
	const [row] = modelWork([], health, zero);
	expect(row.kind).toBe('day');
	if (row.kind === 'day') expect(row.day.summaries).toBeNull();
});

// --- the band's two extra counts, read leniently from the same record --------

test('dayMetrics reads the band counts from bands.low and items_truncated', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		// A full record, as the producer writes it: the band's `notSure` is the low
		// confidence band and its `readInPart` is the cut count, both distinct-
		// published (row 24).
		writeRecord(
			root,
			'2026-08-21',
			JSON.stringify({
				summaries_scored: 5,
				determinism_violations: 1,
				extraction_suspect: 2,
				bands: { high: 3, medium: 1, low: 4 },
				items_truncated: 6
			})
		);
		const found = dayMetrics(['2026-08-21'], root).get('2026-08-21');
		expect(found?.notSure).toBe(4);
		expect(found?.itemsTruncated).toBe(6);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('dayMetrics leaves the band counts null on a record without them', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		// A record carrying only the strict triple still reads, so the model route
		// keeps its correction; the band's two extra counts fall to null for that day
		// rather than dropping the whole record.
		writeRecord(root, '2026-08-21', recordText(5, 1, 2));
		const found = dayMetrics(['2026-08-21'], root).get('2026-08-21');
		expect(found?.summariesScored).toBe(5);
		expect(found?.notSure).toBeNull();
		expect(found?.itemsTruncated).toBeNull();
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
