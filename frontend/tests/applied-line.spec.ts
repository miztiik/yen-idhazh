/** Which merge line a build used on a given day, worked out on records and rows the test writes.
 *
 * The day's run record names the line its last build grouped at, and that is
 * the answer wherever it holds one: `findBuiltLine`. Where it holds none, the
 * rule is `applied_line()` in `backend/idhazh/similarity/applied.py`, and the
 * console holds one copy of it, `findAppliedLine`. The Judgement route asks once,
 * for the newest published day, and its merge line, verdict split and holdout
 * margin draw the answer. Every record and row here is written in the test, so
 * no case depends on what the canary or the archive holds.
 *
 * No build and no browser: this file is in the `logic` group.
 */

import { expect, test } from '@playwright/test';

import { findAppliedLine, findBuiltLine, type FittedLine } from '../src/lib/console/applied-line';

/** The newest published day every case asks about. */
const DAY = '2030-06-15';

/** The committed floor. */
const FLOOR = 0.94;

/** How many days before its own a build looks back for a line, so the build on
 * 15 Jun reads the lines of 8 to 15 Jun. */
const LOOKBACK_DAYS = 7;

/** A day a fit applied `line` on, or a held day that kept `line`. */
function lineOn(date: string, line: number, heldReason = 'none'): FittedLine {
	return { date, applied: line, heldReason };
}

/** Each case's rows, oldest first, and the line its build used, written out. */
const CASES: { state: string; enabled: boolean; rows: FittedLine[]; line: number }[] = [
	{
		state: 'the switch is off, though a line of 0.937 was fitted 3 days before',
		enabled: false,
		rows: [lineOn('2030-06-12', 0.937)],
		line: 0.940
	},
	{
		state: 'the switch is on and the only fitted line is 8 days before, a day the build did not read',
		enabled: true,
		rows: [lineOn('2030-06-07', 0.937)],
		line: 0.940
	},
	{
		state: 'the switch is on and a line of 0.937 was fitted 3 days before',
		enabled: true,
		rows: [lineOn('2030-06-12', 0.937)],
		line: 0.937
	},
	{
		state: 'the switch is on and the line was fitted 7 days before, the first day the build read',
		enabled: true,
		rows: [lineOn('2030-06-08', 0.937)],
		line: 0.937
	},
	{
		state: 'the switch is on and the newest day was held, keeping a line fitted 14 days before',
		enabled: true,
		rows: [lineOn('2030-06-01', 0.937), lineOn(DAY, 0.937, 'judge_unstable')],
		line: 0.940
	},
	{
		state: 'the switch is on, the one fitted line is 8 days before, and a day the build read was held at 0.951',
		enabled: true,
		rows: [lineOn('2030-06-07', 0.937), lineOn('2030-06-13', 0.951, 'judge_unstable')],
		line: 0.940
	}
];

test.describe('the line a build used on the newest published day', () => {
	for (const one of CASES) {
		test(`THE ORACLE: the build on 15 Jun 2030 used ${one.line.toFixed(3)} when ${one.state}`, () => {
			const knobs = { enabled: one.enabled, applied_lookback_days: LOOKBACK_DAYS };

			expect(findAppliedLine(DAY, one.rows, knobs, FLOOR)).toBe(one.line);
		});
	}
});

/** Days whose run record names one line while the rows and the switch work out
 * another. The record is what the day's last build wrote down, so it is the answer. */
const RECORDED_CASES: {
	state: string;
	enabled: boolean;
	rows: FittedLine[];
	recorded: number;
}[] = [
	{
		state: 'its build recorded 0.940, while a line of 0.937 fitted 3 days before is in the rows',
		enabled: true,
		rows: [lineOn('2030-06-12', 0.937)],
		recorded: 0.94
	},
	{
		state: 'its build recorded 0.937, while the switch now reads off',
		enabled: false,
		rows: [lineOn('2030-06-12', 0.937)],
		recorded: 0.937
	}
];

test.describe('the line the newest published day was built with, record first', () => {
	for (const one of RECORDED_CASES) {
		test(`THE ORACLE: the build on 15 Jun 2030 used ${one.recorded.toFixed(3)} when ${one.state}`, () => {
			const knobs = { enabled: one.enabled, applied_lookback_days: LOOKBACK_DAYS };

			expect(findBuiltLine(DAY, one.recorded, one.rows, knobs, FLOOR)).toBe(one.recorded);
		});
	}

	for (const one of CASES) {
		test(`with no line recorded, the build used ${one.line.toFixed(3)} when ${one.state}`, () => {
			const knobs = { enabled: one.enabled, applied_lookback_days: LOOKBACK_DAYS };

			expect(findBuiltLine(DAY, null, one.rows, knobs, FLOOR)).toBe(one.line);
		});
	}
});
