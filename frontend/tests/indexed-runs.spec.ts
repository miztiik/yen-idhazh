import { expect, test } from '@playwright/test';
import { indexedRuns } from '../src/lib/charts/indexed-runs';

test('adjacent readings keep their original positions and never cross a gap', () => {
	expect(indexedRuns([], () => true)).toEqual([]);
	expect(indexedRuns([null, null], (value) => value !== null)).toEqual([]);
	expect(indexedRuns([1, 2, 3], (value) => value !== null)).toEqual([[0, 1, 2]]);
	expect(indexedRuns([1, 2, null, 3, 4], (value) => value !== null)).toEqual([[0, 1], [3, 4]]);
	expect(indexedRuns([null, 0, null, null, 2, 3, null], (value) => value !== null))
		.toEqual([[1], [4, 5]]);
	expect(indexedRuns([1], (value) => value !== null)).toEqual([[0]]);
});

test('the caller chooses whether a measured zero breaks a run and whether to keep a singleton', () => {
	const values = [1, 2, 0, 3, null, 4, 5];
	expect(indexedRuns(values, (value) => value !== null)).toEqual([[0, 1, 2, 3], [5, 6]]);
	const positive = indexedRuns(values, (value) => value !== null && value > 0);
	expect(positive).toEqual([[0, 1], [3], [5, 6]]);
	expect(positive.filter((run) => run.length > 1)).toEqual([[0, 1], [5, 6]]);
});

test('the predicate reads each item once in order without changing the input', () => {
	const values = Object.freeze([0, null, 2]);
	const calls: [number | null, number][] = [];
	expect(indexedRuns(values, (value, index) => {
		calls.push([value, index]);
		return value !== null;
	})).toEqual([[0], [2]]);
	expect(calls).toEqual([[0, 0], [null, 1], [2, 2]]);
	expect(values).toEqual([0, null, 2]);
});
