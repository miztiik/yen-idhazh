import { expect, test } from '@playwright/test';
import { attemptNotes } from '../src/lib/console/pipelines/attempt-notes';
import { attemptCounts, downgradeFunnels, pipelineFunnels } from '../src/lib/console/pipelines/visual-funnels';
import { visualAttemptRows } from '../src/lib/server/ledger-rows';
import { buildRows } from './support/ledger-lifecycle';

const DATE = '2030-06-14';
const BASE = {
	date: DATE, decision: 'none', none_reason: '', rejection_reason: '',
	potential_primary: 'chartable', downgrade_depth: '0', state: 'absent'
};
const row = (over: Record<string, string>) => ({ ...BASE, ...over });

/** Chartable: 5 attempts. Narrative: 2. One attempt has no class. */
const ROWS = [
	row({ decision: 'visual', state: 'rendered', downgrade_depth: '1' }),
	row({ decision: 'visual', state: 'rendered' }),
	row({ decision: 'visual', none_reason: 'no_fit', rejection_reason: 'bad_axis', downgrade_depth: '2' }),
	row({ decision: 'visual', state: 'render_failed' }),
	row({ decision: 'none', none_reason: 'no_numbers' }),
	row({ potential_primary: 'narrative', decision: 'visual', state: 'rendered' }),
	row({ potential_primary: 'narrative', decision: 'none', none_reason: 'no_numbers' }),
	row({ potential_primary: '' , decision: 'none' })
];

test('each funnel counts its own class and says where attempts stopped', () => {
	const pipe = pipelineFunnels(attemptCounts(ROWS));
	const byClass = (name: string) => pipe.find((funnel) => funnel.group === name)!;
	expect(byClass('chartable').steps.map((step) => step.count)).toEqual([5, 4, 3, 2]);
	expect(byClass('chartable').steps.map((step) => step.share)).toEqual([100, 80, 60, 40]);
	expect(byClass('narrative').steps.map((step) => step.count)).toEqual([2, 1, 1, 1]);
	expect(byClass('narrative').steps[3].share).toBe(50);
	expect(byClass('unclassified').denominator).toBe(0);
	expect(byClass('unmeasured').denominator).toBe(1);
	expect(byClass('chartable').losses).toEqual([
		{ label: 'no_fit', count: 1 }, { label: 'no_numbers', count: 1 }, { label: 'render_failed', count: 1 }
	]);

	const down = downgradeFunnels(attemptCounts(ROWS)).find((funnel) => funnel.group === 'chartable')!;
	expect(down.steps.map((step) => [step.label, step.count])).toEqual([
		['Planned', 4], ['Refused as drafted', 1], ['Searched depth 1', 2], ['Searched depth 2', 1]
	]);
	expect(down.ends.map((end) => end.count)).toEqual([2, 1, 1]);
	expect(down.unaccounted).toBe(0);
});

test('a stage larger than the one before is marked, not hidden', () => {
	// Rendered without a recorded plan decision: Written exceeds Plan drafted.
	const odd = pipelineFunnels(attemptCounts([row({ decision: 'none', state: 'rendered' })]))
		.find((funnel) => funnel.group === 'chartable')!;
	expect(odd.steps.map((step) => step.grew)).toEqual([false, false, false, true]);
	const flat = pipelineFunnels(attemptCounts(ROWS)).find((funnel) => funnel.group === 'chartable')!;
	expect(flat.steps.some((step) => step.grew)).toBe(false);
});

test('the reader hands the funnels the packed record, and a missing record draws nothing', async ({}, info) => {
	const root = info.outputPath('attempts');
	await buildRows(root, 'visual-design-attempts', [{ covers: DATE, rows: ROWS.map((r) => ({ run_id: 'r', item_id: 'i', ...r })) }]);
	const table = await visualAttemptRows({ start: DATE, end: DATE }, root);
	const counts = attemptCounts(table.rows);
	expect(counts.reduce((total, count) => total + count.n, 0)).toBe(ROWS.length);
	expect(attemptNotes(table.read).state).toBe('read');

	const empty = await visualAttemptRows({ start: DATE, end: DATE }, info.outputPath('none'));
	const unread = attemptNotes(empty.read);
	expect(unread.state).toBe('not-packed');
	expect(unread.notes.join(' ')).toContain('not packed');
	expect(attemptCounts(empty.rows)).toEqual([]);
});
