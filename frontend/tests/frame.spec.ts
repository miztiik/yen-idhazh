import { expect, test } from '@playwright/test';
import {
	chartWidth,
	coverage,
	type Coverage,
	coverageRegions,
	dayColumns,
	dayTicks,
	frame,
	linearAxis,
	logAxis,
	MARGIN,
	nearestColumn,
	type ReadoutMark,
	SPARSE_COVERAGE
} from '../src/lib/charts/frame';

/**
 * The coordinate frame every console chart draws through.
 *
 * These run in Node rather than in a page. Every console chart renders through
 * this module now, and the rendered assertions live in `console.spec.ts`. What
 * is left here is the arithmetic, which this file can state exactly where a
 * rendered check could only approximate it.
 *
 * The defect it exists to prevent: a chart that draws into an arbitrary
 * `viewBox` and lets the browser stretch it renders its type at the stretch
 * factor. Measured 2026-08-25 at a 1057px window, the same `font-size="10"`
 * came out 4.5px in one panel and 16.6px in the next.
 */

test('the plot box is the frame less its margins', () => {
	const box = frame(600, 200);
	expect(box.left).toBe(MARGIN.left);
	expect(box.top).toBe(MARGIN.top);
	expect(box.right).toBe(600 - MARGIN.right);
	expect(box.bottom).toBe(200 - MARGIN.bottom);
	expect(box.innerWidth).toBe(600 - MARGIN.left - MARGIN.right);
	expect(box.innerHeight).toBe(200 - MARGIN.top - MARGIN.bottom);
});

test('a frame narrower than its own margins does not turn inside out', () => {
	const box = frame(20, 10);
	expect(box.innerWidth).toBe(0);
	expect(box.innerHeight).toBe(0);
	expect(box.right).toBeGreaterThanOrEqual(box.left);
	expect(box.bottom).toBeGreaterThanOrEqual(box.top);
});

test('one data unit is one pixel: the domain ends land on the plot edges', () => {
	const box = frame(600, 200);
	const axis = linearAxis([0, 100], [box.left, box.right]);
	expect(axis.scale(axis.domain[0])).toBeCloseTo(box.left, 6);
	expect(axis.scale(axis.domain[1])).toBeCloseTo(box.right, 6);
});

test('a y axis is the same rule with the range inverted', () => {
	const box = frame(600, 200);
	const axis = linearAxis([0, 50], [box.bottom, box.top]);
	expect(axis.scale(0)).toBeCloseTo(box.bottom, 6);
	expect(axis.scale(axis.domain[1])).toBeCloseTo(box.top, 6);
});

test('a linear domain is zero-anchored and rounded to numbers a reader can place', () => {
	const axis = linearAxis([3, 37, 41], [0, 100]);
	expect(axis.domain[0]).toBe(0);
	expect(axis.domain[1]).toBeGreaterThanOrEqual(41);
	expect(axis.ticks[0]).toBe(0);
	expect(axis.ticks.at(-1)).toBe(axis.domain[1]);
});

test('a linear domain keeps the zero anchor off when asked', () => {
	const axis = linearAxis([120, 180], [0, 100], { zero: false });
	expect(axis.domain[0]).toBeGreaterThan(0);
	expect(axis.domain[0]).toBeLessThanOrEqual(120);
});

test('a linear domain keeps the rounding off when asked, and still gets d3 ticks', () => {
	// 207 was the longest summary on the console on 2026-08-25. Rounded, the
	// domain runs to 250 and every point moves down the plot - to buy a set of
	// tick labels that reads the same either way.
	const axis = linearAxis([0, 207], [180, 0], { nice: false });
	expect(axis.domain).toEqual([0, 207]);
	expect(axis.ticks).toEqual([0, 50, 100, 150, 200]);
	expect(axis.scale(207)).toBeCloseTo(0, 6);

	// Rounding stays the default, so turning it off has to be asked for.
	expect(linearAxis([0, 207], [180, 0]).domain).toEqual([0, 250]);
});

test('an empty series still returns an axis instead of NaN', () => {
	const axis = linearAxis([], [0, 100]);
	expect(Number.isFinite(axis.domain[0])).toBe(true);
	expect(Number.isFinite(axis.domain[1])).toBe(true);
	expect(axis.domain[0]).toBeLessThan(axis.domain[1]);
	expect(Number.isFinite(axis.scale(0))).toBe(true);
});

test('one repeated value does not collapse the domain to a point', () => {
	const axis = linearAxis([7, 7, 7], [0, 100]);
	expect(axis.domain[1]).toBeGreaterThan(axis.domain[0]);
	expect(Number.isFinite(axis.scale(7))).toBe(true);
});

test('a log domain snaps to whole decades and labels each one', () => {
	const axis = logAxis([37, 412, 8412], [0, 360]);
	expect(axis.domain).toEqual([10, 10000]);
	expect(axis.ticks).toEqual([10, 100, 1000, 10000]);
	expect(axis.scale(10)).toBeCloseTo(0, 6);
	expect(axis.scale(10000)).toBeCloseTo(360, 6);
	expect(axis.scale(100)).toBeCloseTo(120, 6);
});

test('a log domain drops values that cannot sit on it', () => {
	const axis = logAxis([0, -5, 250], [0, 100]);
	expect(axis.domain[0]).toBeGreaterThan(0);
	expect(Number.isFinite(axis.scale(0))).toBe(true);
	expect(axis.scale(0)).toBe(axis.scale(axis.domain[0]));
});

test('a log domain over one decade still spans a decade', () => {
	const axis = logAxis([120, 140], [0, 100]);
	expect(axis.domain[1]).toBeGreaterThan(axis.domain[0]);
	expect(axis.ticks.length).toBeGreaterThanOrEqual(2);
});

test('the drawn width is the measured one, and the knob until there is one', () => {
	expect(chartWidth(null, 600)).toBe(600);
	expect(chartWidth(0, 600)).toBe(600);
	expect(chartWidth(573.4, 600)).toBe(573);
});

/**
 * Which column a pointer lands on.
 *
 * The rule used to be a walk over every mark on every pointer move, so a chart
 * with a column a day over ninety days did ninety subtractions to answer a
 * question the reader asks sixty times a second. `nearestColumn` works the
 * layout out once per set of marks and then answers in a step or in a binary
 * search.
 *
 * That is only worth having if it answers the same. So every test below is a
 * parity test against `scanned`, which is the walk it replaced, and the answer
 * has to match at every probe: on a mark, between two marks, on the exact
 * halfway point where two marks tie, past either end, and on a set where
 * several marks sit at one x.
 */

/** The rule this replaced, kept as the thing parity is measured against.
 *
 * Copied from `pointerReadout`'s own `nearest` at `4e91d463`, less the element
 * geometry: turning a client x into a chart x is unchanged and is not what this
 * oracle is about. `distance < gap` is the whole of the tie rule - the first
 * mark at the shortest distance wins, and a later one at the same distance
 * does not displace it.
 */
function scanned(marks: readonly ReadoutMark[], x: number): number | null {
	if (marks.length === 0) return null;
	let best = 0;
	let gap = Number.POSITIVE_INFINITY;
	marks.forEach((mark, index) => {
		const distance = Math.abs(mark.x - x);
		if (distance < gap) {
			gap = distance;
			best = index;
		}
	});
	return best;
}

function marksAt(xs: readonly number[]): ReadoutMark[] {
	return xs.map((x) => ({ x }));
}

/** Every x worth asking about, for one set of marks.
 *
 * The halfway points are the ones that matter: that is where the two answers
 * can differ by one column while every other probe agrees, and a reader
 * dragging along an axis crosses one at every column boundary.
 */
function probes(xs: readonly number[]): number[] {
	const asked: number[] = [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY];
	for (const x of xs) asked.push(x, x - 1, x + 1, x - 0.0001, x + 0.0001);
	for (let index = 1; index < xs.length; index += 1) {
		asked.push((xs[index - 1] + xs[index]) / 2);
	}
	const low = Math.min(...xs, 0);
	const high = Math.max(...xs, 1);
	for (let step = 0; step <= 400; step += 1) {
		asked.push(low - 50 + ((high - low + 100) * step) / 400);
	}
	return asked;
}

function agreesWithTheScan(xs: readonly number[]): void {
	const marks = marksAt(xs);
	const lookup = nearestColumn(marks);
	const asked = probes(xs);
	// One assertion over every probe rather than one per probe: an expectation is
	// far dearer than the arithmetic it is checking, and a list of every x that
	// disagreed says more than the first one would.
	const apart = asked
		.map((x) => ({ x, fast: lookup.at(x), walk: scanned(marks, x) }))
		.filter((one) => one.fast !== one.walk);
	expect(asked.length, 'the probe set is not empty').toBeGreaterThan(100);
	expect(apart, `${lookup.rule} over ${xs.length} marks`).toEqual([]);
}

const BOX = frame(760, 220);
/** The real geometry: `dayColumns` is what every day chart on the console
 * passes, so the even-spacing rule is tested on the arithmetic it will meet. */
const MONTH = dayColumns(30, BOX);
const WEEK_PADDED = dayColumns(7, BOX, 12);
/** Article lengths on a log axis, which is what the source-cut range draws.
 * Ascending and unevenly spaced, so it is the ordered search's own case. Powers
 * of two would not be: a doubling series on a log axis comes out evenly spaced,
 * and the first draft of this fixture was answered by the arithmetic rule. */
const LOG_LENGTHS = [120, 340, 900, 1100, 4200, 9000].map(
	(words) =>
		BOX.left +
		(BOX.innerWidth * (Math.log10(words) - 2)) / 2
);
/** Duplicate positions and exact ties. Two marks at one x is what a chart
 * drawing two runs of one day produces, and 250 is exactly halfway between
 * 100 and 400 so the far pair ties as well. */
const TIED = [0, 100, 100, 100, 250, 250, 400];
/** What `columnStrip` builds before `Chart.svelte` gives it real shares: every
 * mark at zero, so every distance is equal and only the tie rule decides. */
const FLAT = [0, 0, 0, 0];
const SHUFFLED = [400, 0, 250, 100, 900, 100];

test('an evenly spaced axis is answered by arithmetic, and answers the same', () => {
	expect(nearestColumn(marksAt(MONTH)).rule).toBe('even');
	expect(nearestColumn(marksAt(WEEK_PADDED)).rule).toBe('even');
	agreesWithTheScan(MONTH);
	agreesWithTheScan(WEEK_PADDED);
});

test('an unevenly spaced axis is answered by search, and answers the same', () => {
	expect(nearestColumn(marksAt(LOG_LENGTHS)).rule).toBe('ordered');
	agreesWithTheScan(LOG_LENGTHS);
});

test('marks sharing an x pick the first of them, exactly as the walk did', () => {
	expect(nearestColumn(marksAt(TIED)).rule).toBe('ordered');
	agreesWithTheScan(TIED);
	agreesWithTheScan(FLAT);

	// Stated outright as well as through parity, because this is the one
	// behaviour a faster rule is most likely to drop.
	const tied = nearestColumn(marksAt(TIED));
	expect(tied.at(100), 'on the duplicate itself').toBe(1);
	expect(tied.at(175), 'halfway between 100 and 250').toBe(1);
	expect(tied.at(325), 'halfway between 250 and 400').toBe(4);
	expect(nearestColumn(marksAt(FLAT)).at(9999), 'every mark at one x').toBe(0);
});

test('marks in no order fall back to the walk rather than guessing', () => {
	expect(nearestColumn(marksAt(SHUFFLED)).rule).toBe('scan');
	agreesWithTheScan(SHUFFLED);
});

test('a chart with one column or none answers without a special case', () => {
	agreesWithTheScan([42]);
	expect(nearestColumn([]).at(0)).toBeNull();
	expect(nearestColumn([]).at(500)).toBeNull();
});

test('a mark that is not a real number costs the answer nothing', () => {
	const marks = marksAt([0, Number.NaN, 200]);
	const lookup = nearestColumn(marks);
	expect(lookup.rule, 'no fast rule can promise anything about it').toBe('scan');
	for (const x of [-10, 0, 100, 199, 200, 500]) {
		expect(lookup.at(x), `at x=${x}`).toBe(scanned(marks, x));
	}
});

/**
 * The data-dependent geometry - an axis bound and a run of empty columns - is
 * prepared in one pass over its input and comes out the same whether a data
 * change, a window change or a resize asked for it. The Oracle for Row #14.
 *
 * `linearAxis` and `logAxis` used to filter their values into a fresh array and
 * hand that to `d3.extent`; `coverage` counted its flags and then grouped them
 * in a second pass. Every assertion here holds against the rule that replaced,
 * so the output is unchanged - what the reads count pins is the one thing that
 * did: each column is read once, not twice. The tick grid and the mark
 * placement are Jony's to keep and are checked to move only with the box.
 */

/** The two-pass coverage this row replaced, kept as the parity reference. */
function twoPassCoverage(measured: readonly boolean[], threshold = SPARSE_COVERAGE): Coverage {
	const days = measured.length;
	const count = measured.filter(Boolean).length;
	const gaps: [number, number][] = [];
	let open: number | null = null;
	measured.forEach((seen, index) => {
		if (!seen && open === null) open = index;
		if (seen && open !== null) {
			gaps.push([open, index - 1]);
			open = null;
		}
	});
	if (open !== null) gaps.push([open, days - 1]);
	return {
		days,
		measured: count,
		sparse: days > 0 && count > 0 && count / days < threshold,
		gaps
	};
}

/** An array that counts every read of a numbered cell, so a test can tell a
 * one-pass reduction from a two-pass one that returns the same answer. */
function countingReads(values: readonly boolean[]): { array: boolean[]; reads: () => number } {
	let reads = 0;
	const array = new Proxy([...values], {
		get(target, key, receiver) {
			if (typeof key === 'string' && /^\d+$/.test(key)) reads += 1;
			return Reflect.get(target, key, receiver);
		}
	}) as boolean[];
	return { array, reads: () => reads };
}

/** Every gap shape: none, one at each end, several inside, all measured, none
 * measured, one column, and none. */
const WINDOWS: boolean[][] = [
	[true, false, false, true, true, false, true],
	[false, false, true, true, true, false, false],
	[true, true, true, true],
	[false, false, false, false, false],
	[true],
	[false],
	[]
];

test('coverage reads each column once, and still answers the same', () => {
	for (const window of WINDOWS) {
		const { array, reads } = countingReads(window);
		const found = coverage(array);
		expect(found, `over ${window.length} columns`).toEqual(twoPassCoverage(window));
		expect(reads(), `${window.length} columns read once`).toBe(window.length);
	}
});

test('a linear axis prepares its bound once and is unchanged by a resize', () => {
	const values = [3, Number.NaN, 41, Number.POSITIVE_INFINITY, 12];
	const narrow = linearAxis(values, [0, 100]);
	const wide = linearAxis(values, [0, 500]);
	// The domain and the ticks are the data's; only the pixel mapping is the
	// frame's, so a resize moves the scale and nothing else.
	expect(wide.domain).toEqual(narrow.domain);
	expect(wide.ticks).toEqual(narrow.ticks);
	expect(narrow.scale(narrow.domain[1])).toBeCloseTo(100, 6);
	expect(wide.scale(wide.domain[1])).toBeCloseTo(500, 6);
	// The non-finite values are dropped from the bound, exactly as the filter did.
	expect(narrow.domain).toEqual(linearAxis([3, 41, 12], [0, 100]).domain);
	// A data change moves the domain a resize could not.
	expect(linearAxis([3, 41, 900], [0, 100]).domain).not.toEqual(narrow.domain);
});

test('a log axis prepares its bound once and is unchanged by a resize', () => {
	const values = [37, 0, -5, 412, Number.NaN, 8412];
	const narrow = logAxis(values, [0, 100]);
	const wide = logAxis(values, [0, 360]);
	expect(wide.domain).toEqual(narrow.domain);
	expect(wide.ticks).toEqual(narrow.ticks);
	// The values that cannot sit on a log axis are dropped from the bound, exactly
	// as the filter did.
	expect(narrow.domain).toEqual(logAxis([37, 412, 8412], [0, 100]).domain);
});

test('the empty span is the same gap across a data change and a resize', () => {
	const measured = [true, false, false, false, false, false, false, false, true, true];
	const dates = measured.map((_, index) => `2026-08-${String(index + 1).padStart(2, '0')}`);
	const found = coverage(measured);
	expect(found.sparse, 'the fixture has to be sparse for a span to draw').toBe(true);
	// A resize changes only the box. The tinted span moves and scales with it; the
	// gap it covers - its first and last date - does not.
	const narrow = frame(400, 200);
	const wide = frame(900, 200);
	const narrowSpans = coverageRegions(found, dates, dayColumns(measured.length, narrow), narrow);
	const wideSpans = coverageRegions(found, dates, dayColumns(measured.length, wide), wide);
	expect(wideSpans.map((span) => [span.from, span.to])).toEqual(
		narrowSpans.map((span) => [span.from, span.to])
	);
	expect(wideSpans[0].width, 'the geometry did move with the box').toBeGreaterThan(
		narrowSpans[0].width
	);
	// A data change changes the gap a resize could not.
	const filled = [...measured];
	filled[1] = true;
	expect(coverage(filled).gaps).not.toEqual(found.gaps);
});

test('the day-tick grid keeps its shape across a resize', () => {
	const dates = Array.from(
		{ length: 30 },
		(_, index) => `2026-08-${String(index + 1).padStart(2, '0')}`
	);
	const density = 6;
	const narrow = dayTicks(dates, { density, columns: dayColumns(30, frame(360, 200)) });
	const wide = dayTicks(dates, { density, columns: dayColumns(30, frame(900, 200)) });
	// The columns that carry a tick mark are chosen from the day count and the
	// density, never from the pixels, so a resize leaves the grid where it was -
	// only which labels survive the fit can change.
	expect(wide.map((tick) => tick.index)).toEqual(narrow.map((tick) => tick.index));
});

