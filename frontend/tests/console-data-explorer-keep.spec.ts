import { expect, test } from '@playwright/test';

import { keepRecentRun, keepSavedQuestion, suggestedSaveName, type KeptQuestion, type RecentRun } from '../src/lib/console/explorer/keep';

function saved(id: string, name = id): KeptQuestion {
	return { id, name, statement: `select '${id}'`, ledgers: ['seen'], days: 14, updatedAt: `2026-10-0${id.length}T00:00:00Z` };
}

function run(id: string): RecentRun {
	return { id, statement: `select '${id}'`, ledgers: ['seen'], days: 14, rows: id.length, ms: id.length * 10, askedAt: `2026-10-0${id.length}T00:00:00Z` };
}

test('the saved list keeps exactly the saved maximum and names the dropped question', () => {
	const result = keepSavedQuestion([saved('newer', 'Newer'), saved('middle', 'Middle'), saved('oldest', 'Oldest')], saved('fresh', 'Fresh'), 3);
	expect(result.items.map((item) => item.name)).toEqual(['Fresh', 'Newer', 'Middle']);
	expect(result.dropped?.name).toBe('Oldest');
	expect(result.notice).toBe('Saved "Fresh". "Oldest" was the oldest of 3 and is no longer kept.');
});

test('saving an existing question moves it to the front without evicting another', () => {
	const result = keepSavedQuestion([saved('one', 'One'), saved('two', 'Two')], { ...saved('two', 'Two renamed'), statement: 'select 2' }, 2);
	expect(result.items.map((item) => [item.id, item.name, item.statement])).toEqual([
		['two', 'Two renamed', 'select 2'],
		['one', 'One', "select 'one'"]
	]);
	expect(result.notice).toBeNull();
});

test('recent runs stay newest first and keep the history maximum', () => {
	expect(keepRecentRun([run('one'), run('two'), run('three')], run('four'), 2).map((item) => item.id)).toEqual(['four', 'one']);
	expect(keepRecentRun([run('one'), run('two')], { ...run('two'), rows: 99 }, 3)).toMatchObject([{ id: 'two', rows: 99 }, { id: 'one' }]);
});

test('saved questions and recent runs keep custom dates when present', () => {
	const customSaved = { ...saved('custom'), from: '2026-04-05', end: '2026-04-12' };
	expect(keepSavedQuestion([], customSaved, 3).items[0]).toMatchObject({ from: '2026-04-05', end: '2026-04-12' });
	const customRun = { ...run('custom'), from: '2026-04-05', end: '2026-04-12' };
	expect(keepRecentRun([], customRun, 3)[0]).toMatchObject({ from: '2026-04-05', end: '2026-04-12' });
	expect(keepSavedQuestion([], saved('old'), 3).items[0]).not.toHaveProperty('from');
	expect(keepRecentRun([], run('old'), 3)[0]).not.toHaveProperty('from');
});

test('a save name comes from the first line and the caller supplies the bound', () => {
	expect(suggestedSaveName('   select * from seen\nwhere day = current_date', 12)).toBe('select * fro');
	expect(suggestedSaveName('\nsecond line', 40)).toBe('');
});
