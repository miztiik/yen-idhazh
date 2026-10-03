import { expect, test } from '@playwright/test';
import { checkStatement } from '../src/lib/data/statement';

test('one read-only statement passes, including a final semicolon and comment', () => {
	expect(checkStatement('SELECT 1; -- done', 100).refusal).toBeNull();
});

test('two statements are refused', () => {
	expect(checkStatement('SELECT 1; DROP VIEW "item-health"', 100).refusal).toEqual({ kind: 'statements', count: 2 });
});

test('a write and a long question are refused before the engine sees them', () => {
	expect(checkStatement('CREATE TABLE t AS SELECT 1', 100).refusal).toEqual({ kind: 'not-read-only', word: 'CREATE' });
	expect(checkStatement('SELECT 12345', 6).refusal).toEqual({ kind: 'too-long', chars: 12, max: 6 });
});
