/** The scale the holdout margin is drawn on.
 *
 * No build and no browser: this file is in the `logic` group. The arithmetic
 * that decides whether the panel is legible is arithmetic, so it is checked
 * here rather than by looking at a screenshot - `holdout.spec.ts` owns the
 * margin itself and this file owns the scale under it.
 *
 * **The number that failed review is in here.** On the 0.88 to 1.00 band the
 * committed margin drew at 5.8 px of a 1033 px plot, and the dot landed on top
 * of the rule it was measured against. The two tests that check a px width are
 * that finding turned into a gate.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { frame, linearAxis } from '../src/lib/charts/frame';
import {
	agreedNote,
	belowLine,
	holdoutDomain,
	markedApart,
	scoreRange,
	type HoldoutMark
} from '../src/lib/console/holdout';
import { formatNumber, numberFormat } from './support/number-format';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

/** The 0.88 to 1.00 band the review measured the margin on. */
const BAND: [number, number] = [0.88, 1.0];

/** The merge line and the two axis distances as committed, read inside a test.
 *
 * A fixture opened while the module loads fails before any test exists to own
 * the failure, and takes every other test in the file with it.
 */
function knobs(): { line: number; below: number; above: number } {
	const line = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble
		.same_story.floor_min;
	const axis = JSON.parse(readFileSync(join(REPO, 'config', 'console', 'judgement.json'), 'utf8'))
		.knobs;
	return { line, below: axis.holdout_axis_below_line, above: axis.holdout_axis_above_line };
}

/** The four pairs the committed file marks as two stories, at the scores the
 * committed day payloads give them. Written down rather than recomputed: the
 * point of this file is the drawing, and a score read off the archive would
 * make it a test of the archive. */
const COMMITTED = [0.9407, 0.9374, 0.9352, 0.9343];

function mark(score: number, sameStory = false): HoldoutMark {
	return {
		leftTitle: `at ${score}`,
		rightTitle: 'the other',
		sameStory,
		markedOn: '2026-09-19',
		note: 'read as two events',
		score
	};
}

/** How many pixels a distance draws at, on the axis the panel actually uses.
 *
 * The plot the review measured: 1033 px of drawable width inside a full-row
 * panel on a 1440 screen.
 */
function pixels(distance: number, domain: [number, number], innerWidth = 1033): number {
	const box = frame(innerWidth + 42, 220);
	const axis = linearAxis(domain, [box.left, box.right], { zero: false, nice: false });
	return Math.abs(axis.scale(domain[0] + distance) - axis.scale(domain[0]));
}

test('the axis is the line and two configured distances, never the band', () => {
	// On the band, 95 percent of the box had no ink on it.
	const { line, below, above } = knobs();
	const domain = holdoutDomain(line, below, above);

	expect(domain[0]).toBeCloseTo(line - below, 9);
	expect(domain[1]).toBeCloseTo(line + above, 9);
	expect(domain[1] - domain[0]).toBeCloseTo(below + above, 9);
	// Strictly inside the band on both sides, so the axis is a magnification of
	// it rather than a different question.
	expect(domain[0]).toBeGreaterThan(BAND[0]);
	expect(domain[1]).toBeLessThan(BAND[1]);
});

test('the axis follows the line, so a line set elsewhere takes its scale with it', () => {
	// The domain is the line and two knobs. Editing the floor moves the window,
	// which keeps the margin the same size on the screen on the day it changes.
	const { below, above } = knobs();
	const here = holdoutDomain(0.94, below, above);
	const lower = holdoutDomain(0.93, below, above);

	expect(lower[0]).toBeCloseTo(here[0] - 0.01, 9);
	expect(lower[1]).toBeCloseTo(here[1] - 0.01, 9);
	expect(lower[1] - lower[0]).toBeCloseTo(here[1] - here[0], 9);
});

test('the margin draws at a width a person can see', () => {
	// THE BITE, and the number this whole panel exists for. The committed margin
	// is 0.0007. On the band it drew at 5.8 px of a 1033 px plot - half a percent
	// of the box - so a reader could not tell the dot from the rule. On this scale
	// it draws at 24 px, read 2026-09-19 off a 1033 px plot.
	const { line, below, above } = knobs();
	const margin = Math.abs(line - COMMITTED[0]);

	const onTheBand = pixels(margin, BAND);
	const onTheScale = pixels(margin, holdoutDomain(line, below, above));

	expect(onTheBand).toBeLessThan(7);
	// A dot is r=5 with a 1.5 px stroke, so it reaches 6.5 px either side of its
	// own centre. Two of those plus a pixel of daylight is the width at which a
	// reader can see which side of the rule the dot is on. The gate is that width
	// and not the reading above it, because the reading moves with the axis knobs.
	expect(onTheScale).toBeGreaterThan(2 * 6.5 + 1);
});

test('every pair the committed file marks apart is on the scale', () => {
	// An axis that pinned the lowest of the four would print a count of marks it
	// had not drawn, which is the defect the count was added to remove.
	const { line, below, above } = knobs();
	const domain = holdoutDomain(line, below, above);

	for (const score of COMMITTED) {
		expect(score, `${score} is off the scale`).toBeGreaterThanOrEqual(domain[0]);
		expect(score, `${score} is off the scale`).toBeLessThanOrEqual(domain[1]);
	}
});

test('the marked-apart pairs come back highest first, and only them', () => {
	const ordered = markedApart([mark(0.9352), mark(0.99, true), mark(0.9407), mark(0.9343)]);

	expect(ordered.map((entry) => entry.score)).toEqual([0.9407, 0.9352, 0.9343]);
});

test('a population is its lowest, its middle and its highest', () => {
	expect(scoreRange([0.94, 0.90, 0.98, 0.92])).toEqual({ min: 0.9, median: 0.92, max: 0.98 });
	// One mark is a range of one, which is what the canary has. A strip that
	// refused to draw it would leave the panel's second population invisible on
	// the one tree the browser suite can reach.
	expect(scoreRange([0.4862])).toEqual({ min: 0.4862, median: 0.4862, max: 0.4862 });
	expect(scoreRange([])).toBeNull();
});

test('the one-story pairs below the line are the other cost of the number', () => {
	// A pair read as ONE story scoring under the line is a pair the run will not
	// fold, so the reader sees that story twice. A panel reporting only the
	// violations reports one of the two costs the line has.
	expect(belowLine([0.93, 0.94, 0.95, 0.9399], 0.94)).toBe(2);
	expect(belowLine([], 0.94)).toBe(0);
});

test('the one-story sentence names the count, the range and the misses', () => {
	const said = agreedNote([0.7316, 0.9378, 0.9914, 0.9385], 0.94, numberFormat);

	expect(said).toContain('4 pairs were read as one story');
	expect(said).toContain(formatNumber(0.7316, { si: false }));
	expect(said).toContain(formatNumber(0.9914, { si: false }));
	expect(said).toContain('3 of them score below the line');
	expect(said).toContain('see those stories twice');
});

test('a panel with no one-story marks says so rather than drawing an empty strip', () => {
	expect(agreedNote([], 0.94, numberFormat)).toBe('No scored pair marked as one story was returned, so there is no second population to draw.');
});
