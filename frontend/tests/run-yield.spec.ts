import { expect, test } from '@playwright/test';
import { coverage, coverageRegions, dayColumns, frame } from '../src/lib/charts/frame';
import {
	placeOnYieldAxis,
	plannedDays,
	runYield,
	yieldRuns,
	YIELD_AXIS_TICKS,
	type RunYieldSource
} from '../src/lib/charts/run-yield';

/**
 * Items published against items planned, one group a day.
 *
 * The shape this replaced was a two-slice donut over every manifest the page
 * held: one ratio, no days in it. It could say 92 percent finished and it could
 * not say which day lost the items, which is the only question an operator
 * opens the console with.
 *
 * The defect these tests exist to prevent is the arithmetic that would make the
 * new chart lie in the same way. Three of them:
 *
 * - **A closed-up window.** A day with no record is a day the pipeline did not
 *   run. Dropping the column slides every later day one place left, so the
 *   chart draws a gap as if it were the next day along and the hatched span the
 *   component tints has nothing to tint.
 * - **A zero where there is no measurement.** A day that planned nothing has no
 *   share to report. A zero there says it planned work and published none of
 *   it, which is the one state on this chart worth acting on.
 *   `null` is what breaks the line.
 * - **A partition that is not one.** `planned` and `failed` are per-run sums and
 *   `published` is the day's own published set, so the three overlap. Treating
 *   them as three parts of one total is what would put a stack on the page, and
 *   a stack asserts a whole nobody measured.
 *
 * Node, not a browser: this is the arithmetic. That the component draws it as
 * three bars side by side rather than as a stack is asserted on the built page,
 * in `console-run-yield.spec.ts`.
 */

/** Four days that between them hold every case the chart has to survive: a
 * normal day where one item was skipped and so is in none of the three counts,
 * a day that planned nothing, a day that published more than it planned, and -
 * by its absence - a day with no record at all. */
function fixture(): RunYieldSource[] {
	return [
		{ date: '2026-09-01', itemsPlanned: 10, itemsPublished: 8, itemsFailed: 1 },
		{ date: '2026-09-02', itemsPlanned: 0, itemsPublished: 0, itemsFailed: 0 },
		// 2026-09-03 has no record at all.
		{ date: '2026-09-04', itemsPlanned: 4, itemsPublished: 5, itemsFailed: 0 }
	];
}

test('one column a day, including the days nothing recorded', () => {
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	expect(load.columns.map((column) => column.date)).toEqual([
		'2026-09-01',
		'2026-09-02',
		'2026-09-03',
		'2026-09-04'
	]);
});

test('a day with no record is a column of zeroes, not a missing column', () => {
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	const missing = load.columns[2];
	expect(missing.date).toBe('2026-09-03');
	expect(missing.planned).toBe(0);
	expect(missing.published).toBe(0);
	expect(missing.failed).toBe(0);
	// Zero planned is what the component's coverage test reads to tint the span.
	expect(missing.yield).toBeNull();
});

test('the window decides the columns, not the records', () => {
	// Two days either side of everything the fixture holds. A record outside the
	// window is not drawn, and a windowed day with no record still gets a column.
	const load = runYield(fixture(), { start: '2026-08-30', end: '2026-09-06' });
	expect(load.columns).toHaveLength(8);
	expect(load.columns[0].date).toBe('2026-08-30');
	expect(load.columns[7].date).toBe('2026-09-06');
	expect(load.columns[0].planned).toBe(0);
	expect(load.columns[7].planned).toBe(0);

	const narrow = runYield(fixture(), { start: '2026-09-04', end: '2026-09-04' });
	expect(narrow.columns).toHaveLength(1);
	expect(narrow.columns[0].date).toBe('2026-09-04');
});

test('the yield is published over planned, recomputed here and not read back', () => {
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	expect(load.columns[0].yield).toBeCloseTo(8 / 10, 10);
});

test('a day that planned nothing has no yield, which is what breaks the line', () => {
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	// The day that ran and planned nothing, and the day that never ran, answer
	// the same way. Neither is nought percent.
	expect(load.columns[1].planned).toBe(0);
	expect(load.columns[1].yield).toBeNull();
	expect(load.columns[2].yield).toBeNull();
	// The days either side of the break do have one, so the component has two
	// runs to draw rather than one line through the hole.
	expect(load.columns[0].yield).not.toBeNull();
	expect(load.columns[3].yield).not.toBeNull();
});

test('a day that published more than it planned keeps its true figure', () => {
	// A later run republishes a story an earlier run planned, so the day's own
	// published set can exceed the sum of what its runs planned. The axis is
	// fixed at nought to one and the component draws this at the ceiling; the
	// number it reports is not clamped, because a clamped number is a wrong one.
	const load = runYield(fixture(), { start: '2026-09-04', end: '2026-09-04' });
	expect(load.columns[0].yield).toBeCloseTo(5 / 4, 10);
	expect(load.columns[0].yield!).toBeGreaterThan(1);
});

test('the three counts are carried apart, never summed into one total', () => {
	// Published is not a slice of planned and failed is not the rest of it. If a
	// future edit ever stacks these, this is the row that says why it cannot:
	// published plus failed does not equal planned on either real day here.
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	const first = load.columns[0];
	expect(first.published + first.failed).not.toBe(first.planned);
	const last = load.columns[3];
	expect(last.published + last.failed).not.toBe(last.planned);
});

test('the peak is the largest single count anywhere in the window', () => {
	// The count axis is drawn to this, so the three bars of one day share one
	// scale and a tall day does not flatten a short one.
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	expect(load.peak).toBe(10);
});

test('a window nothing was planned in is empty, not a window of zeroes', () => {
	const load = runYield(fixture(), { start: '2026-09-02', end: '2026-09-03' });
	expect(load.empty).toBe(true);
	// The columns are still there. The component prints a sentence instead of a
	// plot, and it needs the day count to say how long the quiet ran.
	expect(load.columns).toHaveLength(2);
});

test('a window with one planned day is not empty', () => {
	const load = runYield(fixture(), { start: '2026-09-02', end: '2026-09-04' });
	expect(load.empty).toBe(false);
});

test('no record at all is an empty window rather than a throw', () => {
	const load = runYield([], { start: '2026-09-01', end: '2026-09-03' });
	expect(load.empty).toBe(true);
	expect(load.peak).toBe(0);
	expect(load.columns.map((column) => column.yield)).toEqual([null, null, null]);
});

test('the share axis is nought to one whatever the window holds', () => {
	// The count axis follows `peak` and has to. This one must not: a share is
	// already on a known scale, and an axis that rescaled would draw a month that
	// published half of its plan at the same height as one that published all of
	// it. Nothing here reads the data, which is the assertion.
	expect(YIELD_AXIS_TICKS).toEqual([0, 0.25, 0.5, 0.75, 1]);
	expect(placeOnYieldAxis(0)).toBe(0);
	expect(placeOnYieldAxis(0.5)).toBe(0.5);
	expect(placeOnYieldAxis(1)).toBe(1);
});

test('a day over the ceiling draws at it and still reports its true share', () => {
	// Both halves of one rule, side by side, because splitting them is how a
	// later edit clamps the number as well as the mark and nothing goes red.
	const load = runYield(fixture(), { start: '2026-09-04', end: '2026-09-04' });
	const over = load.columns[0].yield;
	expect(over).toBeCloseTo(5 / 4, 10);
	expect(placeOnYieldAxis(over!)).toBe(1);
	expect(over).toBeGreaterThan(placeOnYieldAxis(over!));
});

test('the line breaks at a day with no share rather than crossing it', () => {
	// The drawn half of the null rule. `yield === null` above is the number; this
	// is what the chart does with it. An edit that skipped the null columns
	// instead of splitting on them would draw one straight line from the 1st to
	// the 4th, across two days the pipeline planned nothing on, and every
	// assertion above would stay green because no number would have moved.
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	expect(yieldRuns(load.columns)).toEqual([]);

	// One run each side of a single-day break, and each long enough to be a line.
	const split = runYield(
		[
			{ date: '2026-09-01', itemsPlanned: 10, itemsPublished: 8, itemsFailed: 1 },
			{ date: '2026-09-02', itemsPlanned: 10, itemsPublished: 9, itemsFailed: 0 },
			{ date: '2026-09-03', itemsPlanned: 0, itemsPublished: 0, itemsFailed: 0 },
			{ date: '2026-09-04', itemsPlanned: 4, itemsPublished: 3, itemsFailed: 0 },
			{ date: '2026-09-05', itemsPlanned: 4, itemsPublished: 4, itemsFailed: 0 }
		],
		{ start: '2026-09-01', end: '2026-09-05' }
	);
	expect(yieldRuns(split.columns)).toEqual([
		[0, 1],
		[3, 4]
	]);
});

test('a lone day is a dot and not a one-point line', () => {
	// The fixture's own shape: every day that has a share is fenced by a day that
	// has none, so there is no run of two anywhere and the chart draws three dots
	// and no line at all. A one-point polyline draws nothing, so emitting one
	// would be a mark a reader can never see.
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	expect(load.columns.filter((column) => column.yield !== null)).toHaveLength(2);
	expect(yieldRuns(load.columns)).toEqual([]);
});

test('a day with no record is an uncovered day, which is what marks the gap', () => {
	// The drawn half of the missing-day rule. `plannedDays` is the component's own
	// coverage input, and `coverage`/`coverageRegions` - proven in `frame.spec.ts`
	// - turn a false run into the span the page tints. Asserted end to end here,
	// against a fixture, because the committed tree may hold no gap at all in any
	// window the console offers and a test that needed one would be a test a run
	// can redden (`CLAUDE.md` section 13).
	const load = runYield(fixture(), { start: '2026-09-01', end: '2026-09-04' });
	expect(plannedDays(load.columns)).toEqual([true, false, false, true]);

	// The day that ran and planned nothing and the day that never ran at all are
	// one gap, not two. Found whatever the window holds - the tint below is the
	// part that waits for a threshold, the gap itself is not.
	expect(coverage(plannedDays(load.columns)).gaps).toEqual([[1, 2]]);

	// The span is tinted only where the blank part is the larger part of the
	// picture. A window missing a day or two already shows it as a break in the
	// line, and `frame.ts` reserves the tint for the case where the marks would
	// otherwise read as a chart squashed into one corner. So: two planned days in
	// six, which is under the half the helper asks for.
	const sparse = runYield(fixture(), { start: '2026-09-01', end: '2026-09-06' });
	const box = frame(400, 200);
	const spans = coverageRegions(
		coverage(plannedDays(sparse.columns)),
		sparse.columns.map((column) => column.date),
		dayColumns(sparse.columns.length, box),
		box
	);
	expect(spans.map((span) => [span.from, span.to])).toEqual([
		['2026-09-02', '2026-09-03'],
		['2026-09-05', '2026-09-06']
	]);
	for (const span of spans) expect(span.width).toBeGreaterThan(0);
});
