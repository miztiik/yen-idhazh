import { expect, test } from '@playwright/test';
import { chartWidth, frame, linearAxis, logAxis, MARGIN } from '../src/lib/charts/frame';

/**
 * The coordinate frame every console chart draws through.
 *
 * These run in Node rather than in a page. The module is pure arithmetic, and
 * nothing on the console renders through it yet, so a rendered assertion would
 * be a proxy for the thing this file can state exactly.
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
