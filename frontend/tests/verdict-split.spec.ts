/** What the judge said about the line, split at the line itself.
 *
 * No build and no browser: this file is in the `logic` group. Every record here
 * is written down, so the two cases that matter most - a slot whose lower edge
 * IS the line, and a record with nothing above it - are checked without waiting
 * for the pipeline to produce them.
 */

import { expect, test } from '@playwright/test';

import {
	populationRange,
	precisionCorridor,
	precisionMiss,
	rebin,
	splitAtLine,
	type ScoreRecord
} from '../src/lib/console/verdict-split';

/** A five-slot band from 0.930 to 0.935, one slot per thousandth. */
function record(
	counts: { same?: number; different?: number; unclear?: number }[]
): ScoreRecord {
	return {
		bandLow: 0.93,
		bandHigh: 0.93 + counts.length * 0.001,
		binWidth: 0.001,
		daysCounted: 1,
		slots: counts.map((held, index) => ({
			binLow: 0.93 + index * 0.001,
			same: held.same ?? 0,
			different: held.different ?? 0,
			unclear: held.unclear ?? 0
		}))
	};
}

test('the slot whose lower edge is the line sits on the eligible side', () => {
	// A pair scoring exactly the line merges - `assemble` refuses on
	// `score < floor_min` - so the slot that opens AT the line is eligible. Put
	// it below and every count on the boundary is filed under the wrong verdict.
	const split = splitAtLine(record([{ same: 1 }, { same: 2 }, { same: 4 }]), 0.931);

	expect(split.eligibleAgreed).toBe(6);
	expect(split.refusedDisagreed).toBe(1);
});

test('each verdict lands in the cell its own side of the line names', () => {
	const split = splitAtLine(
		record([
			{ same: 1, different: 2 },
			{ same: 4, different: 8 }
		]),
		0.931
	);

	expect(split).toEqual({
		eligibleAgreed: 4,
		eligibleDisagreed: 8,
		refusedAgreed: 2,
		refusedDisagreed: 1
	});
});

test('a record with nothing above the line reports no share at all', () => {
	// A share of nothing is not a zero. A zero here would say the judge agreed
	// with every merge the day made, on a day it judged none of them.
	expect(precisionMiss(splitAtLine(record([{ same: 3 }]), 0.99))).toBeNull();
});

test('the share above the line is the one number that moves both ways', () => {
	const split = splitAtLine(record([{ same: 1 }, { same: 9, different: 1 }]), 0.931);

	expect(precisionMiss(split)).toBeCloseTo(0.1, 6);
});

test('the precision axis is the target times a knob, never the data', () => {
	// The fit aims for the discard share, so one percent is where this line
	// should hover. Ten times it shows the target and a tenfold overshoot on one
	// fixed scale.
	expect(precisionCorridor(0.01, 10)).toEqual([0, 0.1]);
});

test('a population that has never been recorded has no range', () => {
	expect(populationRange(record([{ same: 3 }]), 'different')).toBeNull();
});

test('a range is the lowest slot, the middle count and the highest slot', () => {
	// The middle is where the counts reach half, not the middle slot: a range
	// whose median was the midpoint of its span would say nothing about where the
	// population actually sits.
	const range = populationRange(
		record([{ different: 1 }, { different: 1 }, { different: 20 }, { different: 1 }]),
		'different'
	);

	expect(range?.min).toBeCloseTo(0.93, 6);
	expect(range?.max).toBeCloseTo(0.933, 6);
	expect(range?.median).toBeCloseTo(0.932, 6);
});

test('rebinning folds the slots and drops the rows holding nothing', () => {
	// A table where twenty of twenty-four rows are zero is a table nobody reads
	// to the end.
	const rows = rebin(
		record([{ same: 1 }, { same: 2 }, {}, {}, {}, { different: 4 }]),
		0.005
	);

	expect(rows).toHaveLength(2);
	expect(rows[0].same).toBe(3);
	expect(rows[0].from).toBeCloseTo(0.93, 6);
	expect(rows[0].to).toBeCloseTo(0.935, 6);
	expect(rows[1].different).toBe(4);
});

test('an exact bucket edge does not file one bucket low', () => {
	// `(0.935 - 0.93) / 0.005` is 0.9999999999999999 in binary floating point.
	// Without the tolerance the sixth slot joins the first bucket and the table
	// reports one row where there are two.
	const rows = rebin(record([{ same: 1 }, {}, {}, {}, {}, { same: 1 }]), 0.005);

	expect(rows.map((row) => row.same)).toEqual([1, 1]);
});
