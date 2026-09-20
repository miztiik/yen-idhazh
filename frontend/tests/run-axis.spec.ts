import { expect, test } from '@playwright/test';
import { boundaryDates, firstOfDay, inSpan, runTicks } from '../src/lib/console/machine/run-axis';

/**
 * The axis rules a chart whose columns are RUNS, rather than days, needs.
 *
 * These run in Node rather than in a page. Every one of them is about a day
 * that holds more than one run, which is the case a calendar axis never meets
 * and the case most committed days are in. Until the Hardware panels became
 * files, these four functions sat inside a route component and no test could
 * reach them.
 */

test('a span keeps the rows on both of its end dates', () => {
	const rows = [{ date: '2026-09-01' }, { date: '2026-09-05' }, { date: '2026-09-09' }];
	expect(inSpan(rows, '2026-09-01', '2026-09-09')).toHaveLength(3);
	expect(inSpan(rows, '2026-09-02', '2026-09-08').map((row) => row.date)).toEqual(['2026-09-05']);
});

test('only the first run of a day carries its date', () => {
	// A day with three runs is three columns carrying one date, and a model
	// change drawn on each of them would say the pipeline changed three times.
	expect(
		firstOfDay([{ date: '2026-09-01' }, { date: '2026-09-01' }, { date: '2026-09-02' }])
	).toEqual(['2026-09-01', '', '2026-09-02']);
});

test('the newer of two runs on one day keeps the axis label', () => {
	const ticks = runTicks(['2026-09-01', '2026-09-02', '2026-09-02'], [60, 400, 740], 3);
	expect(ticks.map((tick) => tick.date)).toEqual(['2026-09-01', '2026-09-02', '2026-09-02']);
	// The tick mark stays on every column, because a reader counting columns
	// needs the grid whether or not the date survived.
	expect(ticks).toHaveLength(3);
	expect(ticks[2].text).not.toBe('');
	expect(ticks[1].text).toBe('');
	expect(ticks[0].text).not.toBe('');
});

test('the first drawn column never takes a model-change rule', () => {
	// '2026-09-01' is in the change list and is the first column, so it draws no
	// rule: there is no edge between two runs to draw between.
	const on = boundaryDates(['2026-09-01', '2026-09-02'], ['2026-09-01', '', '2026-09-02']);
	expect([...on]).toEqual(['2026-09-02']);
});
