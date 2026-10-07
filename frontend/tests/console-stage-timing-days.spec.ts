/** What does each day's stage-timing entry hold, over item rows a test writes? */
import { expect, test } from '@playwright/test';
import { stageTimingDays } from '../src/lib/server/stage-timing-days';

/** One item row on a day, with only the cells a case names. Every cell is text, as a ledger row holds it. */
function item(date: string, cells: Record<string, string> = {}): Record<string, string> {
	return { date, ...cells };
}

test('each stage is the median of the items it timed, an empty cell is no reading, and the newest day comes first', () => {
	const days = stageTimingDays([
		// Three items, each timed at fetch and at extract and none at summarize. The
		// scorer's clock is not a stage an item waits on, so it moves nothing.
		item('2030-06-13', { fetch_ms: '100', extract_ms: '0', summarize_ms: '', score_ms: '99999' }),
		item('2030-06-13', { fetch_ms: '900', extract_ms: '0', summarize_ms: '' }),
		item('2030-06-13', { fetch_ms: '200', extract_ms: '0', summarize_ms: '' }),
		// Five items, four of them timed at summarize: the median of an even count is
		// the middle pair's mean.
		item('2030-06-14', { summarize_ms: '400' }),
		item('2030-06-14', { summarize_ms: '100' }),
		item('2030-06-14', { summarize_ms: '' }),
		item('2030-06-14', { summarize_ms: '300' }),
		item('2030-06-14', { summarize_ms: '200' })
	]);
	expect(days).toEqual([
		{
			date: '2030-06-14',
			items: 5,
			fetch: { ms: null, timed: 0, total: 5 },
			extract: { ms: null, timed: 0, total: 5 },
			summarize: { ms: 250, timed: 4, total: 5 }
		},
		{
			date: '2030-06-13',
			items: 3,
			fetch: { ms: 200, timed: 3, total: 3 },
			extract: { ms: 0, timed: 3, total: 3 },
			summarize: { ms: null, timed: 0, total: 3 }
		}
	]);
});

test('a day whose only reading is a zero is kept, and a day nothing timed is left out', () => {
	const days = stageTimingDays([
		// A zero is a reading: the stage finished inside the clock's resolution.
		item('2030-06-12', { fetch_ms: '', extract_ms: '0', summarize_ms: '' }),
		// Nothing timed at any stage, and the scorer's clock is no stage at all.
		item('2030-06-11', { fetch_ms: '', extract_ms: '', summarize_ms: '', score_ms: '500' }),
		item('2030-06-11'),
		// A row with no day belongs to no day.
		item('', { fetch_ms: '50' })
	]);
	expect(days).toEqual([
		{
			date: '2030-06-12',
			items: 1,
			fetch: { ms: null, timed: 0, total: 1 },
			extract: { ms: 0, timed: 1, total: 1 },
			summarize: { ms: null, timed: 0, total: 1 }
		}
	]);
});
