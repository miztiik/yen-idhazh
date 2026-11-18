import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { dayMetrics } from '../src/lib/server/payload';
import { evalDays, type DayScoredCounts, type EvalInput } from '../src/lib/console/eval-instruments';
import { modelWork } from '../src/lib/server/model-work';

/**
 * The console reads distinct published counts from the day record instead of
 * counting score-ledger rows.
 *
 * Three things are checked here, all in plain Node against fixtures so nothing
 * depends on the committed archive (`CLAUDE.md` section 13). First, the reader
 * opens only the dates it is asked for - never a listing of the tree - so its
 * cost is the window and not the archive (Guardrail #12). Second, `modelWork`
 * takes the distinct-published counts from the record where a day has one, and
 * falls back to the row counts where it does not. Third, every
 * measurement distribution still reads every row, so a re-score still counts
 * twice where a median means it to.
 */

// --- the reader opens the window, not the archive ---------------------------

function recordText(scored: number, suspect = 0): string {
	return JSON.stringify({
		// The producer declares these three as required non-null ints on every
		// record it writes, so the reader treats an absent one as a malformed
		// record rather than as an older shape. A helper that left them out would
		// be asserting a shape production has never written.
		items_planned: scored + 2,
		items_published: scored + 1,
		items_failed: 1,
		summaries_scored: scored,
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
		writeRecord(root, '2026-08-21', recordText(5, 2));
		writeRecord(root, '2026-08-22', recordText(3));

		// A one-day window reads one record and the two beside it stay untouched,
		// so the cost is the window and not the tree it sits in.
		const one = dayMetrics(['2026-08-21'], root);
		expect([...one.keys()]).toEqual(['2026-08-21']);
		expect(one.get('2026-08-21')).toEqual({
			date: '2026-08-21',
			itemsPlanned: 7,
			itemsPublished: 6,
			itemsFailed: 1,
			summariesScored: 5,
			extractionSuspect: 2,
			itemsTruncated: null,
			// And the extraction block, which a record written before 2026-09-08
			// does not have. Null rather than a block of zeros: zero facts found is
			// an extractor that stopped working, and this is a day that measured
			// nothing.
			extraction: null
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

test('the extraction block is read whole, or not at all', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	const block = {
		items: 40,
		span_integrity_pass: 39,
		elements_found: 180,
		chartable: 11,
		narrative: 16,
		unclassified: 12,
		chartable_published: 9,
		chartable_charted: 6
	};
	try {
		writeRecord(
			root,
			'2026-09-08',
			JSON.stringify({ ...JSON.parse(recordText(8)), extraction: block })
		);
		// A cell missing is a record this build cannot reduce. It reads null, the
		// same as no block at all - a zero substituted for it would say the
		// extractor found nothing on a day nobody can answer for.
		const { chartable_charted: _dropped, ...short } = block;
		writeRecord(
			root,
			'2026-09-07',
			JSON.stringify({ ...JSON.parse(recordText(8)), extraction: short })
		);

		const found = dayMetrics(['2026-09-08', '2026-09-07'], root);
		expect(found.get('2026-09-08')?.extraction).toEqual({
			items: 40,
			spanIntegrityPass: 39,
			elementsFound: 180,
			chartable: 11,
			narrative: 16,
			unclassified: 12,
			chartablePublished: 9,
			chartableCharted: 6
		});
		expect(found.get('2026-09-07')?.extraction).toBeNull();
		// The day itself still loads: one unreadable block is not one lost day.
		expect(found.get('2026-09-07')?.summariesScored).toBe(8);
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

test('an item count missing is a malformed record, not an older shape', () => {
	// Required item counts still refuse a malformed record. The optional cut
	// count below can remain unknown without dropping the day.
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		const whole = JSON.parse(recordText(4)) as Record<string, unknown>;
		for (const [index, cell] of ['items_planned', 'items_published', 'items_failed'].entries()) {
			const { [cell]: _dropped, ...short } = whole;
			writeRecord(root, `2026-08-0${index + 1}`, JSON.stringify(short));
		}
		writeRecord(root, '2026-08-04', JSON.stringify({ ...whole, items_planned: 'ten' }));
		writeRecord(root, '2026-08-05', recordText(4));

		const found = dayMetrics(
			['2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04', '2026-08-05'],
			root
		);
		expect([...found.keys()]).toEqual(['2026-08-05']);
		expect(found.get('2026-08-05')?.itemsPlanned).toBe(6);
		expect(found.get('2026-08-05')?.itemsPublished).toBe(5);
		expect(found.get('2026-08-05')?.itemsFailed).toBe(1);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

// --- the reducers take the count from the record where it has one -----------

const DATE = '2026-08-29';

/**
 * A day whose ledger holds more rows than the day published: item `a` re-scored
 * under a second stamp (two rows, one item), and item `gone` scored then
 * dropped (a row for an item no published day holds). Four rows, three distinct
 * ids, and the record says two distinct items were published.
 */
const ROWS: EvalInput[] = [
	{ date: DATE, item_id: 'a', hhem: '0.9' },
	{ date: DATE, item_id: 'a', hhem: '0.7' },
	{ date: DATE, item_id: 'b', hhem: '0.5' },
	{ date: DATE, item_id: 'gone', hhem: '0.3' }
];

const SETTLED = new Map<string, DayScoredCounts>([
	[DATE, { scored: 2 }]
]);

test('evalDays reads every row, so a re-score counts twice in a median', () => {
	const [day] = evalDays(ROWS);
	// Four hhem readings for three distinct items: the re-scored one counts twice.
	expect(day.matched).toBe(4);
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
		[DATE, { scored: 0 }]
	]);
	const [row] = modelWork([], health, zero);
	expect(row.kind).toBe('day');
	if (row.kind === 'day') expect(row.day.summaries).toBeNull();
});

// --- retained counts do not depend on retired diagnostics ------------------

test('a day without retired aggregates keeps its published count and extraction cuts', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		writeRecord(
			root,
			'2026-08-21',
			JSON.stringify({
				items_planned: 8,
				items_published: 7,
				items_failed: 1,
				summaries_scored: 5,
				extraction_suspect: 2,
				items_truncated: 6
			})
		);
		const found = dayMetrics(['2026-08-21'], root).get('2026-08-21');
		expect(found?.summariesScored).toBe(5);
		expect(found?.itemsTruncated).toBe(6);
		expect(found).not.toHaveProperty('determinismViolations');
		expect(found).not.toHaveProperty('notSure');
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('an unrecorded cut count remains unknown without dropping the day', () => {
	const root = mkdtempSync(join(tmpdir(), 'day-metrics-'));
	try {
		writeRecord(root, '2026-08-21', recordText(5, 2));
		const found = dayMetrics(['2026-08-21'], root).get('2026-08-21');
		expect(found?.summariesScored).toBe(5);
		expect(found?.itemsTruncated).toBeNull();
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
