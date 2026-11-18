/** Native timing rows retain nearest-rank readings and timed coverage, not retired CSV shaping. */
import { expect, test } from '@playwright/test';
import { nativeStageTimings } from '../src/lib/console/pipelines/stage-timings';

test('each stage uses its recorded numeric sample, including zero, and days come oldest first', () => {
	const days = nativeStageTimings([
		{ date: '2030-06-13', fetch_ms: 100, extract_ms: 0, summarize_ms: null, score_ms: 99999 },
		{ date: '2030-06-13', fetch_ms: 900, extract_ms: 0, summarize_ms: null },
		{ date: '2030-06-13', fetch_ms: 200, extract_ms: 0, summarize_ms: null },
		{ date: '2030-06-14', summarize_ms: 400 },
		{ date: '2030-06-14', summarize_ms: 100 },
		{ date: '2030-06-14', summarize_ms: null },
		{ date: '2030-06-14', summarize_ms: 300 },
		{ date: '2030-06-14', summarize_ms: 200 }
	]);
	expect(days).toEqual([
		{ date: '2030-06-13', items: 3, fetch: { ms: 200, timed: 3 },
			extract: { ms: 0, timed: 3 }, summarize: { ms: null, timed: 0 } },
		{ date: '2030-06-14', items: 5, fetch: { ms: null, timed: 0 },
			extract: { ms: null, timed: 0 }, summarize: { ms: 300, timed: 4 } }
	]);
});

test('unmeasured native rows retain their day without manufacturing a zero or a scorer stage', () => {
	expect(nativeStageTimings([
		{ date: '2030-06-12', fetch_ms: null, extract_ms: 0, summarize_ms: null },
		{ date: '2030-06-11', score_ms: 500 }, { date: '2030-06-11' }
	])).toEqual([
		{ date: '2030-06-11', items: 2, fetch: { ms: null, timed: 0 },
			extract: { ms: null, timed: 0 }, summarize: { ms: null, timed: 0 } },
		{ date: '2030-06-12', items: 1, fetch: { ms: null, timed: 0 },
			extract: { ms: 0, timed: 1 }, summarize: { ms: null, timed: 0 } }
	]);
});
