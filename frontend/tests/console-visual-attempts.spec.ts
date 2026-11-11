import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { visualAttemptDays, writtenTypeCounts } from '../src/lib/console/pipelines/visual-attempts';
import { refusalLines } from '../src/lib/console/pipelines/visual-refusals';
import type { RecordRead } from '../src/lib/console/recording';
import { frame } from '../src/lib/charts/frame';
import { dateSeries, numberFormat } from './support/number-format';
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
	const lines = refusalLines(days, table.read, { start: '2030-06-13', end: '2030-06-15' }, numberFormat);
	for (const day of days) for (const refusal of day.refusals) {
		expect(lines.find((line) => line.reason === refusal.reason)?.series.points.find((point) => point.date === day.date)?.value)
			.toBe(refusal.count);
	}
	const writtenHtml = renderConfigured(component, { props: { days, read: evidence.state, notes: evidence.notes } }).body;
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
	const html = renderConfigured(component, { props: { days: [], read: unread.state, notes: unread.notes } }).body;
	expect(html).toContain('not packed');
	expect(html).not.toContain('data-empty');
	expect(refusalLines([], missing.read, { start: '2030-06-13', end: '2030-06-15' }, numberFormat)).toEqual([]);
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
	const partialHtml = renderConfigured(component, { props: { days, read: evidence.state, notes: evidence.notes } }).body;
	expect(partialHtml).toContain('data-record-note');
	expect(partialHtml).toContain('data-record-incomplete');
	for (const note of evidence.notes) expect(partialHtml).toContain(note);
});

const WINDOW = { start: '2030-06-01', end: '2030-06-07' };
const READ: RecordRead = {
	state: 'read', first: '2030-06-02', through: '2030-06-06', lastRows: null,
	lostDays: ['2030-06-05'], setAside: { '2030-06-06': 1 }
};

test('daily refusal lines keep recorded zeros, unknown dates, partial counts and exact attempt readouts distinct', () => {
	const days = visualAttemptDays([
		{ date: '2030-06-02', rejection_reason: 'enough_data', rendered_type: 'bar' },
		{ date: '2030-06-02', rejection_reason: 'enough_data' },
		{ date: '2030-06-03' },
		{ date: '2030-06-06', rejection_reason: 'no_invented_values' }
	]);
	const lines = refusalLines(days, READ, WINDOW, numberFormat);
	const enough = lines.find((line) => line.reason === 'enough_data')!;
	const invented = lines.find((line) => line.reason === 'no_invented_values')!;
	expect(enough.series.points.map((point) => point.value)).toEqual([null, 2, 0, null, null, null, null]);
	expect(invented.series.points.map((point) => point.value)).toEqual([null, 0, 0, null, null, 1, null]);
	expect(enough.readout.series.find((series) => series.label === 'Recorded attempts')?.values)
		.toEqual([null, '2 attempts', '1 attempt', null, null, '1 attempt', null]);
	expect(enough.readout.notMeasuredAt[4]).toContain('was lost');
	expect(enough.readout.events[4]).toEqual([]);
	expect(enough.readout.events[5][0].value).toContain('unreadable');
	expect(enough.readout.notMeasuredAt[0]).toContain('Outside');
	expect(enough.readout.notMeasuredAt[3]).toContain('No visual attempt');
	expect(enough.readout.columns).toEqual([
		'1 Jun 2030 UTC', '2 Jun 2030 UTC', '3 Jun 2030 UTC', '4 Jun 2030 UTC',
		'5 Jun 2030 UTC', '6 Jun 2030 UTC', '7 Jun 2030 UTC'
	]);
	const shape = dateSeries([invented.series], { frame: frame(760, 220), density: 6, valueTicks: 5, padding: 0.2 });
	expect(shape?.lines[0].points.find((point) => point.date === '2030-06-06')).toMatchObject({ value: 1, alone: true });
	expect(shape?.lines[0].path.match(/M/g)).toHaveLength(2);
});

test('every recorded reason remains drawable beyond the shared plot vocabulary, including a lone day', () => {
	const reasons = [
		'element_exists', 'semantically_compatible', 'units_convertible', 'roles_valid_for_type',
		'stacked_bar_exhaustive', 'pie_exhaustive', 'enough_data', 'no_duplicate_in_role',
		'no_invented_values', 'numerals_matched', 'plan_version_current'
	];
	const window = { start: '2030-06-02', end: '2030-06-02' };
	const lines = refusalLines(visualAttemptDays(reasons.map((rejection_reason) => ({
		date: window.start, rejection_reason
	}))), { ...READ, state: 'read', setAside: {}, lostDays: [] }, window, numberFormat);
	expect(lines.map((line) => line.reason).sort()).toEqual([...reasons].sort());
	for (const line of lines) {
		const shape = dateSeries([line.series], { frame: frame(390, 220), density: 6, valueTicks: 5, padding: 0.2 });
		expect(shape?.lines[0].points).toMatchObject([{ value: 1, alone: true }]);
		expect(line.readout.series.find((series) => series.label === 'Recorded attempts')?.values).toEqual(['11 attempts']);
	}
});

test('a known quiet check day draws zero, but unread, empty and unreadable-period days invent no counts', () => {
	const window = { start: '2030-06-02', end: '2030-06-02' };
	const days = visualAttemptDays([{ date: window.start }]);
	const quiet = refusalLines(days, { ...READ, state: 'read', setAside: {} }, window, numberFormat);
	expect(quiet[0].series.points).toEqual([{ date: window.start, value: 0 }]);
	expect(refusalLines([], READ, window, numberFormat)).toEqual([]);
	const unreadable: RecordRead = { state: 'unreadable', at: null, fault: null };
	expect(refusalLines(days, unreadable, window, numberFormat)).toEqual([]);
	expect(attemptNotes(unreadable).notes[0]).toContain('not a quiet day');
	for (const period of ['2030', '2030-06']) {
		const partial = refusalLines(days, { ...READ, state: 'read', setAside: { [period]: 1 } }, window, numberFormat);
		expect(partial[0].series.points[0].value).toBeNull();
		expect(partial[0].readout.events[0][0].value).toContain('incomplete');
	}
});
