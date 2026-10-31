import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { visualAttemptDays, writtenTypeCounts } from '../src/lib/console/pipelines/visual-attempts';
import { visualAttemptRows } from '../src/lib/server/ledger-rows';
import { attemptNotes } from '../src/lib/console/pipelines/attempt-notes';
import { buildLedger, buildRows } from './support/ledger-lifecycle';
import { serverCompiler, renderConfigured } from './support/server-render';
import type { Row } from '../src/lib/data/ledger';

function fixture(): Row[] {
	return JSON.parse(readFileSync(new URL('../../tests/fixtures/visual-attempt-console.json', import.meta.url), 'utf8'));
}

test('UTC refusal counts and written type pairs match the named attempt fixture', async ({}, info) => {
	const rows = fixture();
	const root = info.outputPath('attempts');
	await buildRows(root, 'visual-design-attempts', ['2030-06-13', '2030-06-14', '2030-06-15'].map((date) => ({
		covers: date, rows: rows.filter((row) => row.date === date).map((row) => ({ ...row, run_id: 'run' }))
	})));
	const table = await visualAttemptRows({ start: '2030-06-13', end: '2030-06-15' }, root);
	const days = visualAttemptDays(table.rows);
	const expectedRefusals = rows.filter((row) => row.rejection_reason).reduce<Record<string, number>>((held, row) => {
		const key = `${row.date}/${row.rejection_reason}`;
		held[key] = (held[key] ?? 0) + 1;
		return held;
	}, {});
	expect(Object.fromEntries(days.flatMap((day) => day.refusals.map((refusal) =>
		[`${day.date}/${refusal.reason}`, refusal.count])))).toEqual(expectedRefusals);
	const expectedWritten = rows.filter((row) => row.rendered_type).reduce<Record<string, number>>((held, row) => {
		const key = `${row.planned_type}/${row.rendered_type}`;
		held[key] = (held[key] ?? 0) + 1;
		return held;
	}, {});
	expect(Object.fromEntries(writtenTypeCounts(days).map((pair) =>
		[`${pair.planned}/${pair.rendered}`, pair.count]))).toEqual(expectedWritten);
	expect(days.map((day) => day.date)).toEqual(['2030-06-13', '2030-06-14', '2030-06-15']);
	expect(days.find((day) => day.date === '2030-06-15')?.refusals).toEqual([]);
	expect(days.reduce((total, day) => total + day.untypedWritten, 0)).toBe(1);
	expect(writtenTypeCounts(days.filter((day) => day.date === '2030-06-14'))).toEqual([
		{ planned: 'bar', rendered: 'bar', count: 1 }
	]);

	const compile = serverCompiler(info.outputPath('compiled'));
	const module = await compile('src/lib/console/pipelines/VisualAttempts.svelte', 'VisualAttempts', []);
	const component = (await import(module)).default;
	const evidence = attemptNotes(table.read);
	const refusalHtml = renderConfigured(component, { props: { days, read: evidence.state, notes: evidence.notes, kind: 'refusals' } }).body;
	for (const day of days) for (const refusal of day.refusals) {
		expect(refusalHtml).toContain(`data-refusal-date="${day.date}" data-refusal-reason="${refusal.reason}" data-count="${refusal.count}"`);
	}
	const writtenHtml = renderConfigured(component, { props: { days, read: evidence.state, notes: evidence.notes, kind: 'written' } }).body;
	for (const pair of writtenTypeCounts(days)) {
		expect(writtenHtml).toContain(`data-planned-type="${pair.planned}" data-rendered-type="${pair.rendered}" data-count="${pair.count}"`);
	}
	expect(writtenHtml).toContain('not necessarily published');
	expect(writtenHtml).toContain('Written attempts with no recorded type: 1');
});

test('missing, lost and truncated evidence stays incomplete rather than quiet', async ({}, info) => {
	const compile = serverCompiler(info.outputPath('compiled'));
	const module = await compile('src/lib/console/pipelines/VisualAttempts.svelte', 'VisualAttempts', []);
	const component = (await import(module)).default;
	const missing = await visualAttemptRows({ start: '2030-06-13', end: '2030-06-15' }, info.outputPath('missing'));
	const unread = attemptNotes(missing.read);
	for (const kind of ['refusals', 'written']) {
		const html = renderConfigured(component, { props: { days: [], read: unread.state, notes: unread.notes, kind } }).body;
		expect(html).toContain('not packed');
		expect(html).not.toContain('data-empty');
	}
	const root = info.outputPath('incomplete');
	const { date: _date, ...columns } = fixture()[0];
	await buildLedger(root, {
		ledger: 'visual-design-attempts', pinned: '2030-06-15',
		days: [{ ago: 2, rows: 1, setAside: 2 }, { ago: 1, state: 'lost' }, { ago: 0, state: 'empty' }],
		columns: { ...columns, run_id: 'run' }
	});
	const partial = await visualAttemptRows({ start: '2030-06-13', end: '2030-06-15' }, root);
	const evidence = attemptNotes(partial.read);
	expect(partial.read.state).toBe('read');
	if (partial.read.state !== 'read') throw new Error('Expected a partial readable ledger.');
	expect(partial.read.lostDays).toEqual(['2030-06-14']);
	expect(partial.read.setAside['2030-06-13']).toBe(2);
	const wider = attemptNotes(partial.read, { start: '2030-06-12', end: '2030-06-16' });
	expect(wider.notes.join(' ')).toContain('not the whole selected window');
	expect(wider.notes.join(' ')).toContain('incomplete');
	expect(attemptNotes(partial.read, { start: '2030-06-15', end: '2030-06-15' }).notes).toEqual([]);
	const days = visualAttemptDays(partial.rows);
	for (const kind of ['refusals', 'written']) {
		const html = renderConfigured(component, { props: { days, read: evidence.state, notes: evidence.notes, kind } }).body;
		expect(html).toContain('data-record-note');
		expect(html).toContain('data-record-incomplete');
		for (const note of evidence.notes) expect(html).toContain(note);
		expect(html).not.toContain('data-refusal-date="2030-06-14"');
	}
});
