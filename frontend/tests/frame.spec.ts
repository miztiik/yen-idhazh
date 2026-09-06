import { expect, test } from '@playwright/test';
import {
	chartWidth,
	dayColumns,
	frame,
	linearAxis,
	logAxis,
	MARGIN,
	nearestColumn,
	type ReadoutMark
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

