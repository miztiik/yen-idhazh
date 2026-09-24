/** The margin between the merge line and the pairs a person marked apart.
 *
 * No build and no browser: this file is in the `logic` group. Every value here
 * is written down, so the two states that matter most - a mark sitting exactly
 * on the line, and a line that has fallen below one - are checked without
 * waiting for the archive to produce them.
 */

import { expect, test } from '@playwright/test';

import {
	cosineInt8,
	holdoutMargin,
	holdoutNote,
	holdoutState,
	marginDistance,
	pairScore,
	scoredNote,
	skipNote,
	weightsNote,
	type HoldoutMark,
	type ScoreWeights
} from '../src/lib/console/holdout';

const WEIGHTS: ScoreWeights = { cosineWeight: 1, fittedOn: '2026-09-18' };

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
});

test('a pair sitting exactly on the line is on the wrong side of it', () => {
	// THE BITE. `assemble` refuses on `score < floor_min`, so a pair scoring the
	// line merges. Compare the other way and the one mark sitting on the
	// boundary is filed as safe, which is the only mark that can ever be there.
	const outcome = holdoutMargin(0.94, [mark(0.94)]);

	expect(outcome.violations).toBe(1);
	expect(outcome.margin).toBeCloseTo(0, 9);
	expect(holdoutState(outcome, true)).toBe('violation');
});

test('a pair marked as one story sets no floor at all', () => {
	// Every same-story mark scores high by construction. Counting one as a floor
	// would make the margin negative on every healthy day.
	const outcome = holdoutMargin(0.94, [mark(0.99, true), mark(0.98, true)]);

	expect(outcome.closest).toBeNull();
	expect(outcome.margin).toBeNull();
	expect(holdoutState(outcome, true)).toBe('no-marks');
});

test('a negative margin prints as a distance and never as a minus sign', () => {
	// The raw value renders `-0.0007 BELOW`, which reads as a double negative
	// and a typo. The word carries the direction and the figure carries the size.
	const outcome = holdoutMargin(0.94, [mark(0.9407)]);
	const figure = marginDistance(outcome.margin ?? 0);
	const note = holdoutNote(outcome, holdoutState(outcome, true), 200, 0.94);

	expect(outcome.margin).toBeLessThan(0);
	expect(figure).toBe('0.0007');
	expect(figure).not.toContain('-');
	expect(note).toContain('BELOW');
	// The sentence carries no signed figure either. `hand-marked` is a hyphen in
	// a word, so the check is on what sits next to a digit.
	expect(note).not.toMatch(/-\d/);
});

test('the four states say four different things', () => {
	const none = holdoutMargin(0.94, []);
	const clear = holdoutMargin(0.94, [mark(0.9317)]);
	const over = holdoutMargin(0.94, [mark(0.9407)]);

	const said = [
		holdoutNote(none, holdoutState(none, true), 0, 0.94),
		holdoutNote(clear, holdoutState(clear, false), 1, 0.94),
		holdoutNote(clear, holdoutState(clear, true), 1, 0.94),
		holdoutNote(over, holdoutState(over, true), 1, 0.94)
	];

	expect(new Set(said).size).toBe(4);
	expect(said[0]).toContain('nothing to hold the line against');
	expect(said[1]).toContain('No day has fitted a line yet');
	expect(said[2]).toContain('No hand-marked pair is on the wrong side');
	expect(said[3]).toContain('would merge them');
});

test('a violation is reported before the day has ever fitted a line', () => {
	// THE BITE. A marked-apart pair above the line would be merged whether or
	// not a fit has run, so the provenance note may not swallow it. Return
	// `no-fit` here and the panel's worst state is invisible on every day before
	// the first fit - which is every day the flag has been off.
	const over = holdoutMargin(0.94, [mark(0.9407)]);

	expect(holdoutState(over, false)).toBe('violation');
	expect(holdoutNote(over, holdoutState(over, false), 1, 0.94)).toContain('would merge them');
});

test('the violation count is the marks at or above the line, not all of them', () => {
	const outcome = holdoutMargin(0.94, [mark(0.9407), mark(0.9374), mark(0.9352), mark(0.9343)]);

	// The committed file's four marked-apart pairs, at the committed line. One
	// of the four is over it and the other three are not.
	expect(outcome.violations).toBe(1);
	expect(outcome.closest?.score).toBeCloseTo(0.9407, 6);
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
	expect(pairScore(0.9, { cosineWeight: 0.8, fittedOn: null })).toBeCloseTo(0.72, 9);
});

test('the printed weight names where it came from', () => {
	expect(weightsNote(WEIGHTS)).toContain('2026-09-18');
	expect(weightsNote({ cosineWeight: 1, fittedOn: null })).toContain('committed config');
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

test('a tree nobody has scored says so, and never prints four zeros', () => {
	// THE BITE. A person types the verb that writes the committed row, so a tree
	// where nobody has run it has none. Four zeros would read as a line that
	// merged nothing rather than as a reading nobody took.
	const said = scoredNote(null);

	expect(said).toContain('has not been scored');
	expect(said).toContain('score-merge-line-holdout');
	expect(said).not.toContain('0 of the');
});

test('the committed row is printed with the population each count came from', () => {
	// A rate read without its denominator is the whole reason the row carries
	// counts and no percentage: 196 of these 200 marks are on one side.
	const said = scoredNote({
		date: '2026-09-21',
		appliedLine: 0.94,
		labeller: 'claude-opus-4.6',
		mergedAndOneStory: 79,
		mergedAndTwoStories: 1,
		apartAndOneStory: 117,
		apartAndTwoStories: 3,
		pairsUnresolved: 0,
		labelledTwoStoryPairs: 4
	});

	expect(said).toContain('2026-09-21');
	expect(said).toContain('0.9400');
	expect(said).toContain('claude-opus-4.6');
	expect(said).toContain('joined 1 of the 4 pairs marked as two stories');
	expect(said).toContain('left 117 pairs marked as one story apart');
	expect(said).not.toContain('could not be scored');
});

test('pairs the tree could not score are named rather than left out', () => {
	// Silence here would make a comparison look complete at whatever size
	// retention had left it.
	const said = scoredNote({
		date: '2026-09-21',
		appliedLine: 0.94,
		labeller: 'claude-opus-4.6',
		mergedAndOneStory: 40,
		mergedAndTwoStories: 1,
		apartAndOneStory: 60,
		apartAndTwoStories: 1,
		pairsUnresolved: 98,
		labelledTwoStoryPairs: 4
	});

	expect(said).toContain('98 could not be scored');
	expect(said).toContain('no longer published');
});
