/** The console reads the telemetry projection by column name, not by position.
 *
 * `parseTelemetryCsv` used to take every cell by index, `cpu_model` from
 * `cells[46]`. An index that has moved does not throw - it hands back the
 * neighbouring column, and a processor name drawn from the wrong column reads
 * like a measurement. So the shape under test is that moving a column changes
 * nothing and removing one is visible.
 *
 * Every shard here is BUILT. A test that reads `frontend/public/telemetry/`
 * costs more every published month (Guardrail #12), and the two headers that
 * matter most - one with a column inserted, one with a column gone - are ones
 * the committed archive has never carried.
 */

import { expect, test } from '@playwright/test';

import {
	TELEMETRY_COLUMNS,
	parseTelemetryCsv,
	telemetryColumnIndex
} from '../src/lib/charts/series';

/** One cell of every column, distinct enough that a misread names its source. */
const CELLS: Record<string, string> = {
	date: '2026-08-20',
	run_id: '2026-08-20-1',
	item_id: 'ai-01',
	vertical: 'ai',
	source_id: 'canary',
	stage: 'publish',
	outcome: 'ok',
	cpu_model: 'AMD EPYC 7763 64-Core Processor',
	cpu_busy_pct: '61',
	load_1m: '3.5',
	item_total_ms: '800',
	fetch_ms: '100'
};

/** A shard with the columns in the order asked for, written here and nowhere else. */
function shard(columns: readonly string[]): string {
	const row = columns.map((name) => CELLS[name] ?? '').join(',');
	return `${columns.join(',')}\n${row}\n`;
}

test('a column that moved is still the column that is read', () => {
	// The old reader took `cpu_model` from position 46. Here it is position 0,
	// where `date` used to be, and `date` is last.
	const moved = [...TELEMETRY_COLUMNS].reverse();
	expect(moved[0]).toBe('load_1m');

	const rows = parseTelemetryCsv(shard(moved));

	expect(rows).toHaveLength(1);
	expect(rows[0].cpu_model).toBe('AMD EPYC 7763 64-Core Processor');
	expect(rows[0].date).toBe('2026-08-20');
	expect(rows[0].cpu_busy_pct).toBe(61);
	expect(rows[0].load_1m).toBe(3.5);
});

test('a column inserted before the ones the console reads moves nothing', () => {
	// What a sibling writer does when it adds a cell mid-header. Every position
	// after the insert shifts by one, and every value below must be unchanged.
		// `shard` is a real census column this projection deliberately never carries.
		const grown = ['shard', ...TELEMETRY_COLUMNS];
	expect(rows[0].cpu_model).toBe('AMD EPYC 7763 64-Core Processor');
	expect(rows[0].date).toBe('2026-08-20');
	expect(rows[0].item_total_ms).toBe(800);
	expect(rows[0].fetch_ms).toBe(100);
});

test('a column the header does not carry is named, not guessed at', () => {
	const short = TELEMETRY_COLUMNS.filter(
		(name) => name !== 'cpu_model' && name !== 'load_1m'
	);

	const { at, missing } = telemetryColumnIndex(short);

	expect(missing).toEqual(['cpu_model', 'load_1m']);
	expect(at.has('cpu_model')).toBe(false);
	// Every other name still resolves, so one absent column degrades one cell.
	expect(at.size).toBe(TELEMETRY_COLUMNS.length - 2);
});

test('an absent column draws as absence rather than as its neighbour', () => {
	const short = TELEMETRY_COLUMNS.filter((name) => name !== 'cpu_model');

	const rows = parseTelemetryCsv(shard(short));

	// Empty, which is what the panel already draws for a run that named no
	// processor - not `cpu_busy_pct`, which is the cell that took the position.
	expect(rows[0].cpu_model).toBe('');
	expect(rows[0].cpu_busy_pct).toBe(61);
	expect(rows[0].date).toBe('2026-08-20');
});

test('a header carrying no identity cell is refused', () => {
	// Not this projection: a 200 that served something else. The console catches
	// this, marks the month refused and draws its gap.
	const other = ['version', 'shard', 'job_seconds'];

	expect(() => parseTelemetryCsv(shard(other))).toThrow(/carries no date, run_id, item_id/);
});

test('a name repeated in a header resolves to its first cell', () => {
	// A second copy of a name is the writer's defect either way. Taking the first
	// takes the cell that was filled rather than a trailing empty one.
	const doubled = ['cpu_model', ...TELEMETRY_COLUMNS];
	const row = TELEMETRY_COLUMNS.map((name) => CELLS[name] ?? '').join(',');

	const rows = parseTelemetryCsv(`${doubled.join(',')}\nAMD EPYC 9V45,${row}\n`);

	expect(rows[0].cpu_model).toBe('AMD EPYC 9V45');
});
