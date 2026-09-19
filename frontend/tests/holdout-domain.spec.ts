/** The scale the holdout margin is drawn on, and what one day's fall reaches.
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
	DAYS_ABOVE,
	DAYS_BELOW,
	holdoutDomain,
	holdoutMargin,
	holdoutReach,
	holdoutState,
	holdoutTone,
	markedApart,
	reachNote,
	reachZone,
	scoreRange,
	type HoldoutMark
} from '../src/lib/console/holdout';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

/** The line and the daily step as committed, read inside a test.
 *
 * A fixture opened while the module loads fails before any test exists to own
 * the failure, and takes every other test in the file with it.
 */
function knobs(): { applied: number; maxDownStep: number; band: [number, number] } {
	const block = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble
		.same_story;
	return {
		applied: block.floor_min,
		maxDownStep: block.adaptive_dedup_threshold.max_down_step,
		band: [block.adaptive_dedup_threshold.band_low, block.adaptive_dedup_threshold.band_high]
	};
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
 * The plot the review measured: 1033 px of drawable width inside a panel on a
 * 1440 screen.
 */
function pixels(distance: number, domain: [number, number], innerWidth = 1033): number {
	const box = frame(innerWidth + 42, 220);
	const axis = linearAxis(domain, [box.left, box.right], { zero: false, nice: false });
	return Math.abs(axis.scale(domain[0] + distance) - axis.scale(domain[0]));
}

test('the axis is the line and one day of legal fall, never the band', () => {
	// The band is already the axis of `MergeLinePlot` further up the route. Here
	// it is the reason 95 percent of the box had no ink on it.
	const { applied, maxDownStep, band } = knobs();
	const domain = holdoutDomain(applied, maxDownStep);

	expect(domain[0]).toBeCloseTo(applied - DAYS_BELOW * maxDownStep, 9);
	expect(domain[1]).toBeCloseTo(applied + DAYS_ABOVE * maxDownStep, 9);
	expect(domain[1] - domain[0]).toBeCloseTo((DAYS_BELOW + DAYS_ABOVE) * maxDownStep, 9);
	// Strictly inside the band on both sides, so the axis is a magnification of
	// it rather than a different question.
	expect(domain[0]).toBeGreaterThan(band[0]);
	expect(domain[1]).toBeLessThan(band[1]);
});

test('the axis follows the line, so a fitted line takes its scale with it', () => {
	// The domain is the line and one knob. A fit that moves the line moves the
	// window, which is what keeps the margin the same size on the screen on the
	// day the line changes.
	const { maxDownStep } = knobs();
	const here = holdoutDomain(0.94, maxDownStep);
	const lower = holdoutDomain(0.93, maxDownStep);

	expect(lower[0]).toBeCloseTo(here[0] - 0.01, 9);
	expect(lower[1]).toBeCloseTo(here[1] - 0.01, 9);
	expect(lower[1] - lower[0]).toBeCloseTo(here[1] - here[0], 9);
});

test('the margin draws at a width a person can see', () => {
	// THE BITE, and the number this whole change exists for. The committed margin
	// is 0.0007. On the band it drew at 5.8 px of a 1033 px plot - half a percent
	// of the box - so a reader could not tell the dot from the rule.
	const { applied, maxDownStep, band } = knobs();
	const margin = Math.abs(applied - COMMITTED[0]);

	const onTheBand = pixels(margin, band);
	const onTheScale = pixels(margin, holdoutDomain(applied, maxDownStep));

	expect(onTheBand).toBeLessThan(7);
	expect(onTheScale).toBeGreaterThan(40);
	// A dot is r=5 with a 1.5 px stroke, so it reaches 6.5 px either side of its
	// own centre. Two of those plus a pixel of daylight is the width at which a
	// reader can see which side of the rule the dot is on.
	expect(onTheScale).toBeGreaterThan(2 * 6.5 + 1);
});

test('every pair the committed file marks apart is on the scale', () => {
	// An axis that pinned the lowest of the four would print a count of marks it
	// had not drawn, which is the defect the count was added to remove.
	const { applied, maxDownStep } = knobs();
	const domain = holdoutDomain(applied, maxDownStep);

	for (const score of COMMITTED) {
		expect(score, `${score} is off the scale`).toBeGreaterThanOrEqual(domain[0]);
		expect(score, `${score} is off the scale`).toBeLessThanOrEqual(domain[1]);
	}
});

test('the zone goes down from the line and never up', () => {
	// THE BITE. `fit.clamp` is one-sided - `lowest_today = previous -
	// max_down_step`, with no upward clamp - so a zone drawn either side of the
	// line would draw a constraint that does not exist.
	const zone = reachZone(0.94, 0.005);

	expect(zone[1]).toBeCloseTo(0.94, 9);
	expect(zone[0]).toBeCloseTo(0.935, 9);
	expect(zone[1]).toBeLessThanOrEqual(0.94);
});

test('the zone is where one more day would fold a pair', () => {
	const { applied, maxDownStep } = knobs();
	const zone = reachZone(applied, maxDownStep);
	const inside = COMMITTED.filter((score) => score >= zone[0] && score < zone[1]);

	// 0.9374 and 0.9352 clear the line today and would not after one day's fall.
	expect(inside).toEqual([0.9374, 0.9352]);
});

test('the reach counts the marks today, tomorrow and the day after', () => {
	// One of the four is over the line as committed. After one day's legal fall
	// it is three, and after two it is all four - which is the sentence the
	// headline carries and the reason the axis reaches two days down.
	const { applied, maxDownStep } = knobs();
	const reach = holdoutReach(applied, maxDownStep, COMMITTED.map((score) => mark(score)));

	expect(reach).toEqual({ today: 1, tomorrow: 3, dayAfter: 4 });
});

test('a pair read as one story is in no reach at all', () => {
	// Every same-story mark scores high by construction. Counting one would make
	// the reach report a fault on every healthy day.
	const reach = holdoutReach(0.94, 0.005, [mark(0.99, true), mark(0.9385, true)]);

	expect(reach).toEqual({ today: 0, tomorrow: 0, dayAfter: 0 });
});

test('the headline says what one more day costs, not just the distance', () => {
	const { applied, maxDownStep } = knobs();
	const marks = COMMITTED.map((score) => mark(score));
	const said = reachNote(holdoutReach(applied, maxDownStep, marks), maxDownStep, marks.length);

	expect(said).toContain('0.005');
	expect(said).toContain('2 more marks');
	expect(said).toContain("tomorrow's reach");
	expect(said).toContain('4 of 4');
});

test('a day nothing is inside reach of says so rather than printing a zero', () => {
	const marks = [mark(0.90), mark(0.85)];
	const said = reachNote(holdoutReach(0.94, 0.005, marks), 0.005, marks.length);

	expect(said).toContain('no further mark');
	expect(said).not.toContain('0 more');
});

test('the panel takes the hue of what it means', () => {
	// A panel that looks the same reporting a fault as reporting a clear day is
	// the one thing this one may not be.
	const over = holdoutMargin(0.94, [mark(0.9407)]);
	const inReach = holdoutMargin(0.94, [mark(0.9374)]);
	const clear = holdoutMargin(0.94, [mark(0.90)]);

	expect(holdoutTone(holdoutState(over, true), holdoutReach(0.94, 0.005, [mark(0.9407)]))).toBe(
		'bad'
	);
	expect(
		holdoutTone(holdoutState(inReach, true), holdoutReach(0.94, 0.005, [mark(0.9374)]))
	).toBe('warn');
	expect(holdoutTone(holdoutState(clear, true), holdoutReach(0.94, 0.005, [mark(0.90)]))).toBe(
		'neutral'
	);
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
	const said = agreedNote([0.7316, 0.9378, 0.9914, 0.9385], 0.94);

	expect(said).toContain('4 pairs were read as one story');
	expect(said).toContain('0.7316');
	expect(said).toContain('0.9914');
	expect(said).toContain('3 of them score below the line');
	expect(said).toContain('see those stories twice');
});

test('a panel with no one-story marks says so rather than drawing an empty strip', () => {
	expect(agreedNote([], 0.94)).toContain('No pair has been read as one story yet');
});
