/** The margin between the merge line and the pairs marked as separate stories.
 *
 * No build and no browser: this file is in the `logic` group. Every value here
 * is written down, so the two states that matter most - a mark sitting exactly
 * on the line, and a line that sits below one - are checked without waiting for
 * the archive to produce them.
 */

import { expect, test } from '@playwright/test';

import {
	cosineInt8,
	holdoutMargin,
	holdoutNote,
	holdoutState,
	holdoutTone,
	marginDistance,
	pairScore,
	skipNote,
	weightsNote,
	type HoldoutMark,
	type ScoreWeights
} from '../src/lib/console/holdout';
import { numberFormat } from './support/number-format';

const WEIGHTS: ScoreWeights = { cosineWeight: 1 };

function mark(score: number, sameStory = false, leftTitle = 'one'): HoldoutMark {
	return {
		leftTitle,
		rightTitle: 'the other',
		sameStory,
		markedOn: '2026-09-19',
		note: 'read as two events',
		score
	};
}

test('the margin is the line minus the highest pair marked as two stories', () => {
	const outcome = holdoutMargin(0.94, [mark(0.9317), mark(0.9), mark(0.99, true)]);

	expect(outcome.closest?.score).toBeCloseTo(0.9317, 6);
	expect(outcome.margin).toBeCloseTo(0.0083, 6);
	expect(outcome.violations).toBe(0);
	// The one-story mark is no floor, so the margin is the closest of two pairs.
	expect(outcome.pairs).toBe(2);
});

test('a pair sitting exactly on the line is on the wrong side of it', () => {
	// THE BITE. `assemble` refuses on `score < floor_min`, so a pair scoring the
	// line clears the score check. Compare the other way and the mark sitting on the
	// boundary is filed as safe, which is the only mark that can ever be there.
	const outcome = holdoutMargin(0.94, [mark(0.94)]);

	expect(outcome.violations).toBe(1);
	expect(outcome.margin).toBeCloseTo(0, 9);
	expect(holdoutState(outcome)).toBe('violation');
});

test('a pair marked as one story sets no floor at all', () => {
	// Every same-story mark scores high by construction. Counting one as a floor
	// would make the margin negative on every healthy day.
	const outcome = holdoutMargin(0.94, [mark(0.99, true), mark(0.98, true)]);

	expect(outcome.closest).toBeNull();
	expect(outcome.margin).toBeNull();
	expect(outcome.pairs).toBe(0);
	expect(holdoutState(outcome)).toBe('no-marks');
});

test('a negative margin prints as a distance and never as a minus sign', () => {
	// The raw value renders `-0.0007 BELOW`, which reads as a double negative
	// and a typo. The word carries the direction and the figure carries the size.
	const outcome = holdoutMargin(0.94, [mark(0.9407)]);
	const figure = marginDistance(outcome.margin ?? 0, numberFormat);
	const note = holdoutNote(outcome, holdoutState(outcome), 0.94, numberFormat);

	expect(outcome.margin).toBeLessThan(0);
	expect(figure).toBe('0.0007');
	expect(figure).not.toContain('-');
	expect(note).toContain('BELOW');
	// The sentence carries no signed figure either.
	expect(note).not.toMatch(/-\d/);
});

test('the three states say three different things, each over the pairs the margin is the closest of', () => {
	const none = holdoutMargin(0.94, []);
	const clear = holdoutMargin(0.94, [mark(0.9317), mark(0.9)]);
	const over = holdoutMargin(0.94, [mark(0.9407), mark(0.9374), mark(0.9352), mark(0.9343)]);

	const said = [
		holdoutNote(none, holdoutState(none), 0.94, numberFormat),
		holdoutNote(clear, holdoutState(clear), 0.94, numberFormat),
		holdoutNote(over, holdoutState(over), 0.94, numberFormat)
	];

	expect(new Set(said).size).toBe(3);
	expect(said[0]).toBe('No scored pair marked as two stories was returned, so there is no measured margin.');
	expect(said[1]).toBe(
		'The line sits 0.0083 above the highest score among the 2 pairs marked as separate stories. None of the 2 scores reach it. The line is at 0.94.'
	);
	expect(said[2]).toBe(
		'The line is 0.0007 BELOW the highest score among the 4 pairs marked as separate stories. 1 of the 4 scores at or above it.'
	);
});

test('one marked pair is named as the only pair, not as the highest-scoring of one', () => {
	const only = holdoutMargin(0.94, [mark(0.9317)]);
	const over = holdoutMargin(0.94, [mark(0.9407)]);

	expect(holdoutNote(only, holdoutState(only), 0.94, numberFormat)).toBe(
		'The line sits 0.0083 above the score of the only pair marked as separate stories. The line is at 0.94.'
	);
	expect(holdoutNote(over, holdoutState(over), 0.94, numberFormat)).toBe(
		'The line is 0.0007 BELOW the score of the only pair marked as separate stories. Its score clears the line.'
	);
});

test('the violation count is the marks at or above the line, not all of them', () => {
	const outcome = holdoutMargin(0.94, [mark(0.9407), mark(0.9374), mark(0.9352), mark(0.9343)]);

	// The committed file's four marked-apart pairs at the former 0.94 line. One
	// of the four is over it and the other three are not.
	expect(outcome.violations).toBe(1);
	expect(outcome.closest?.score).toBeCloseTo(0.9407, 6);
});

test('the panel takes the hue of what it means, and only a pair on the wrong side turns it', () => {
	// A panel that looks the same reporting a fault as reporting a clear day is
	// the one thing this one may not be.
	for (const [marks, tone] of [
		[[mark(0.9407)], 'bad'],
		[[mark(0.9374)], 'neutral'],
		[[mark(0.9)], 'neutral'],
		[[], 'neutral']
	] as const) {
		expect(holdoutTone(holdoutState(holdoutMargin(0.94, marks)))).toBe(tone);
	}
});

test('two stored int8 vectors score the angle between them, not their length', () => {
	// The quantisation scale cancels, so doubling one side changes nothing. A
	// decoder that forgot to normalise would fail this and still look plausible.
	const left = Int8Array.from([3, 4, 0]);
	const right = Int8Array.from([6, 8, 0]);

	expect(cosineInt8(left, right)).toBeCloseTo(1, 9);
	expect(cosineInt8(Int8Array.from([1, 0]), Int8Array.from([0, 1]))).toBeCloseTo(0, 9);
});

test('two vectors of different widths score nothing rather than a prefix', () => {
	// Two widths are two encoders. A dot product over the shorter of them is a
	// number that looks exactly like a score and means nothing.
	expect(cosineInt8(Int8Array.from([1, 0, 0]), Int8Array.from([1, 0]))).toBe(0);
	expect(cosineInt8(Int8Array.from([]), Int8Array.from([]))).toBe(0);
});

test('the score is the cosine under its weight, and nothing else', () => {
	expect(pairScore(0.9, WEIGHTS)).toBeCloseTo(0.9, 9);
	expect(pairScore(0.9, { cosineWeight: 0.8 })).toBeCloseTo(0.72, 9);
});

test('the printed weight names the committed config as where it came from', () => {
	expect(weightsNote(WEIGHTS)).toBe('Scored at 1 on the cosine, the weight in the committed config.');
});

test('a mark the day tree cannot answer for is counted with its reason', () => {
	// A blank dot would say the margin is fine. A counted skip says the mark
	// could not be checked, which is a different fact.
	expect(skipNote([])).toBeNull();
	const said = skipNote([
		{ leftTitle: 'one', rightTitle: 'two', reason: 'the day it names is no longer published' }
	]);
	expect(said).toContain('1 marked pair could not be checked');
	expect(said).toContain('no longer published');
});
