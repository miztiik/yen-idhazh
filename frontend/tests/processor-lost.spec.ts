import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
	processorLostOverDays,
	processorLostOverShards,
	BUSY_HELD_BOTH_BEFORE,
	type LostThresholds
} from '../src/lib/console/machine/processor-lost';

/**
 * What the host gave to another tenant, and the three things a tile can say.
 *
 * **Driven by rows written here, and it has to be.** The canary names
 * `cpu_steal_pct` among its item columns and leaves every cell of it empty on
 * purpose, because a plausible figure nobody measured is worse than a dash in
 * the file the console's arithmetic is checked against. So the loud case and
 * the quiet case cannot be reached in a browser at all, and asserting them
 * there would be an oracle that never bites. The rows below are four fields
 * each, fixed in number, and they carry the two states the archive has never
 * produced.
 *
 * The last case is the drift gate. The correction the panel prints names the
 * date the busy figure stopped holding both halves, and the same date is
 * written into `cpu_busy_pct`'s own description in the generated contract. Two
 * copies of one fact drift, so this reads the contract and fails here rather
 * than letting the page print a correction for a day that moved.
 */

/** The committed shares, so a case says loud or quiet on the same line the page
 * does. Read from the config rather than typed, which is what makes a raised
 * threshold fail here instead of silently redrawing the panel. */
const ROOT = resolve(process.cwd(), '..');
const appearance = JSON.parse(
	readFileSync(resolve(ROOT, 'config/appearance.json'), 'utf8')
) as { console: { processor_lost_pct_marked: number; processor_lost_pct_named: number } };
const THRESHOLDS: LostThresholds = {
	marked: appearance.console.processor_lost_pct_marked,
	named: appearance.console.processor_lost_pct_named
};

/** One item row in the cells this panel reads. A row with no `cpu_steal_pct`
 * key is a row written before the ledger split it out of the busy share. */
function row(
	date: string,
	shard: string,
	steal?: number
): Record<string, string> {
	const built: Record<string, string> = { date, run_id: `${date}-1`, shard };
	if (steal !== undefined) built.cpu_steal_pct = String(steal);
	return built;
}

test('a day where one article lost a known share draws loud and prints the share', () => {
	const span = processorLostOverDays(
		[
			row('2026-09-21', '0', 0.0),
			row('2026-09-21', '1', 12.5),
			row('2026-09-22', '0', 0.1)
		],
		THRESHOLDS
	);

	const loud = span.days.find((day) => day.key === '2026-09-21');
	expect(loud?.state, 'a day holding a 12.5% loss is not drawn loud').toBe('marked');
	expect(loud?.worstPct, 'the tile reports something other than its worst article').toBe(12.5);
	expect(loud?.says, 'the loud tile does not print the share it found').toBe('12.5%');
	// The worst article and not a typical one: two of the three articles that
	// day lost nothing, and a mean of them would have drawn the day quiet.
	expect(loud?.from, 'the tile counted the wrong number of recording articles').toBe(2);

	expect(span.named?.key, 'the span names no day, though one passed the naming share').toBe(
		'2026-09-21'
	);
	expect(span.days.find((day) => day.key === '2026-09-22')?.state).toBe('quiet');
});

test('a window with no steal draws every tile outlined and names no day', () => {
	const span = processorLostOverDays(
		[row('2026-09-21', '0', 0), row('2026-09-21', '1', 0.04), row('2026-09-22', '0', 0)],
		THRESHOLDS
	);

	expect(
		span.days.map((day) => day.state),
		'a quiet window drew something other than two outlined tiles'
	).toEqual(['quiet', 'quiet']);
	expect(span.named, 'a quiet window named a worst day').toBeNull();
	// A true 0.04% rounds to `0.0%`, and a printed zero would promise a host
	// that took nothing. The quiet tile prints the share it stayed under.
	expect(span.days[0].says, 'a quiet tile printed a rounded figure').toBe(
		`under ${THRESHOLDS.marked}%`
	);
	expect(span.daysRecording, 'the quiet sentence would be bounded to the wrong day count').toBe(2);
});

test('a day predating the column draws a blank cell and reports neither state', () => {
	const span = processorLostOverDays(
		[row('2026-09-19', '0'), row('2026-09-19', '1'), row('2026-09-21', '0', 0)],
		THRESHOLDS
	);

	const older = span.days.find((day) => day.key === '2026-09-19');
	expect(older?.state, 'a day with no reading was drawn as a measurement').toBe('unrecorded');
	expect(older?.worstPct, 'a day with no reading invented a figure').toBeNull();
	expect(older?.from, 'a day with no reading counted an article as recording one').toBe(0);
	expect(older?.outOf, 'the tile forgot the articles it covers').toBe(2);
	// Never a zero. A zero there says the host took nothing from a run whose
	// busy figure was holding both halves at the time.
	expect(span.days.find((day) => day.key === '2026-09-21')?.state).toBe('quiet');
	expect(span.daysRecording, 'the unrecorded day was counted as one that answered').toBe(1);
});

test('a span with no reading at all reports none, and keeps the articles it read', () => {
	const span = processorLostOverDays([row('2026-09-19', '0'), row('2026-09-20', '0')], THRESHOLDS);

	expect(span.from, 'a span with no reading claimed one').toBe(0);
	expect(span.outOf, 'a span with no reading forgot the articles it covered').toBe(2);
	expect(span.daysRecording).toBe(0);
	expect(span.days.every((day) => day.state === 'unrecorded')).toBe(true);
});

test('the run grain reads one run and no other, a tile a shard', () => {
	const health = [
		row('2026-09-21', '0', 0),
		row('2026-09-21', '1', 9.5),
		row('2026-09-21', '10', 0),
		// A second run of the same day, which the run grain must not absorb.
		{ ...row('2026-09-21', '0', 40), run_id: '2026-09-21-2' },
		row('2026-09-20', '0', 30)
	];

	const run = processorLostOverShards(
		health,
		{ runId: '2026-09-21-1', date: '2026-09-21' },
		THRESHOLDS
	);

	// Numeric order, so shard 10 sits after shard 1 rather than after shard 0.
	expect(
		run.shards.map((shard) => shard.key),
		'the shards are not in the order a reader counts them'
	).toEqual(['0', '1', '10']);
	expect(run.shards.map((shard) => shard.state)).toEqual(['quiet', 'marked', 'quiet']);
	expect(run.shards[1].says, 'the loud shard does not print its share').toBe('9.5%');
	expect(run.outOf, 'the run grain absorbed a row from another run').toBe(3);
	expect(run.from).toBe(3);
});

test('no run to read draws no shards rather than an empty run', () => {
	const run = processorLostOverShards([row('2026-09-21', '0', 0)], null, THRESHOLDS);
	expect(run.runId).toBeNull();
	expect(run.shards).toEqual([]);
	expect(run.outOf).toBe(0);
});

test('THE ORACLE: the correction names the date the contract records', () => {
	// The generated TypeScript rather than the schema, because that is the file
	// the frontend compiles against - if the two ever disagree the drift gate
	// fails first, and this reads the one a reader of this code would read.
	const contract = readFileSync(
		resolve(ROOT, 'frontend/src/contracts/item-health-row.ts'),
		'utf8'
	);
	const said = contract.match(/A row written before (\d{4}-\d{2}-\d{2}) counted that time as ours/);

	expect(
		said,
		'`cpu_busy_pct` no longer records the date it stopped holding the stolen share, so the correction the panel prints cannot be checked against anything'
	).not.toBeNull();
	expect(
		said?.[1],
		'the panel prints a correction for a different day from the one the contract records'
	).toBe(BUSY_HELD_BOTH_BEFORE);
});
