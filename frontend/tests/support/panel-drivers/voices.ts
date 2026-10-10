/** Which judged Voices panels have state drivers or build-time inputs? */

import type { Driver, BasicNothing } from '../panel-gates';
import { test } from '@playwright/test';
import { unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { judgementRoute } from '../judgement-route';
import { buildRows, type BuiltCell } from '../ledger-lifecycle';
import type { Row } from '../../../src/lib/data/ledger';
import type { SourceHealthView } from '../../../src/lib/server/payload';

export const VOICES_CENSUS: SourceHealthView = {
	generated_at: '2030-06-15T19:00:00Z', run_id: '2030-06-15-10', headline_sentence: 'Two sources were read.',
	reliability_floor: 0.5, reliability_window_days: 30, min_complete_days: 7, complete_dates: 20, yield_readable: true,
	first_date: '2030-05-27', last_date: '2030-06-15', yield_alarm_point: 0.5, yield_alarm_min_decisions: 30,
	dwell_days: 14, auto_retire: false, dwell_dates: ['2030-06-14', '2030-06-15'],
	sources: [
		{ source_id: 'alpha', title: 'Alpha desk', vertical: 'world', permission: 'allowed', availability: 'failing', retired: false, retired_on: null,
			opportunities: 40, publications: 12, source_failures: 28, reliability: 0.5, reliability_reads: 4,
			recent_days: ['2030-06-14', '2030-06-15'].map((date) => ({ date, opportunities: 10, publications: 1, source_failures: 9 })),
			days_under_the_mark: 2, retires_on: '2030-06-27' },
		{ source_id: 'beta', title: 'Beta desk', vertical: 'world', permission: 'allowed', availability: 'answering', retired: false, retired_on: null,
			opportunities: 30, publications: 30, source_failures: 0, reliability: 1, reliability_reads: 4,
			recent_days: [], days_under_the_mark: 0, retires_on: null }
	]
};

export const VOICES_ROWS: readonly Row[] = [
	article({ date: '2030-06-14', item_id: 'a', url_key: 'a', fetch_ms: 1000, robots_ms: 100, retry_total_ms: 200, retry_count: 1, fetch_connect_ms: 100, fetch_ttfb_ms: 100, code: 'http_rate_limited', http_status: 429, outcome: 'failed', source_words_before_cap: 2000, source_words: 1000, watchlist_hit: true, on_front_page: true }),
	article({ date: '2030-06-14', item_id: 'a-second', url_key: 'a', fetch_ms: 2000, robots_ms: 200, retry_total_ms: 0, retry_count: 0, fetch_connect_ms: 200, fetch_ttfb_ms: 100, code: 'network_error', outcome: 'failed', source_words_before_cap: 4000, source_words: 1000, watchlist_hit: true, on_front_page: true }),
	article({ date: '2030-06-14', item_id: 'c', url_key: 'c', source_id: 'beta', fetch_ms: 3000, robots_ms: 0, retry_total_ms: 0, retry_count: 0, fetch_connect_ms: 200, fetch_ttfb_ms: null, watchlist_hit: true }),
	article({ date: '2030-06-14', item_id: 'd', url_key: 'd', source_id: 'beta', fetch_ms: 4000, source_words_before_cap: 100, source_words: 80, watchlist_hit: false }),
	article({ date: '2030-06-15', run_id: '2030-06-15-2', item_id: 'a', url_key: 'a', stage: 'planned', selection_score: 1.2, authority_score: 0.9, feed_weight: 0.9, recency_bonus: 0.1, lens_bonus: 0, watchlist_bonus: 0.2, carriage_step: 0, watchlist_hit: true, on_front_page: true }),
	article({ date: '2030-06-15', run_id: '2030-06-15-10', item_id: 'a', url_key: 'a', stage: 'planned', selection_score: 1.5, authority_score: 1, recency_bonus: 0.2, lens_bonus: 0.1, watchlist_bonus: 0.2, carriage_step: 0, watchlist_hit: true, on_front_page: true }),
	article({ date: '2030-06-15', run_id: '2030-06-15-10', item_id: 'b', url_key: 'b', source_id: 'beta', stage: 'planned', selection_score: 1, authority_score: 0.8, feed_weight: 0.8, recency_bonus: 0.2, lens_bonus: 0, watchlist_bonus: 0, carriage_step: 0, watchlist_hit: false, on_front_page: false, source_words_before_cap: 500, source_words: 500 })
];
function article(over: Partial<Row>): Row {
	return {
		date: '2030-06-14', run_id: '2030-06-14-1', item_id: '', url_key: '', source_id: 'alpha',
		stage: 'fetch', outcome: 'ok', code: 'ok', http_status: null, source_form: 'rss', tier: 1,
		fetch_ms: null, robots_ms: null, retry_total_ms: null, retry_count: null, fetch_connect_ms: null, fetch_ttfb_ms: null,
		source_words_before_cap: null, source_words: null,
		selection_score: null, authority_score: null, tier_score: 1, feed_weight: 1, feed_reliability: 1,
		recency_bonus: null, lens_bonus: null, watchlist_bonus: null, carriage_step: null,
		watchlist_hit: null, on_front_page: null,
		...over
	};
}
export async function publishVoicesFixture(state: string, publishedRoot?: string): Promise<void> {
	if (publishedRoot !== undefined) writeFileSync(join(publishedRoot, 'source-health.json'), JSON.stringify(VOICES_CENSUS));
	await buildRows(state, 'item-health', ['2030-06-14', '2030-06-15'].map((covers) => ({
		covers, rows: VOICES_ROWS.filter((row) => row.date === covers) as readonly Readonly<Record<string, BuiltCell>>[]
	})));
	await buildRows(state, 'feed-health', ['2030-06-14', '2030-06-15'].map((covers) => ({
		covers, rows: ['alpha', 'beta'].map((feed_id) => ({
			run_id: `${covers}-1`, date: covers, feed_id, checked_at: `${covers}T12:00:00Z`,
			outcome: feed_id === 'alpha' ? 'transient' : 'ok', status: feed_id === 'alpha' ? 429 : 200,
			items: feed_id === 'alpha' ? 0 : 4, detail: feed_id === 'alpha' ? 'rate limited' : ''
		}))
	})));
}

const states = Object.fromEntries((['loading', 'quiet', 'missing', 'unreachable'] as const).map((state) => [
	state, (async (page) => {
		const route = await judgementRoute(test.info().outputPath(`voices-${state}`), {
			voicesWait: state === 'loading',
			voices: async (root) => {
				if (state !== 'missing') await buildRows(root, 'item-health', [{ covers: '2030-06-15', rows: [] }]);
				await buildRows(root, 'feed-health', [{ covers: '2030-06-15', rows: [] }]);
			}
		});
		if (state === 'unreachable') unlinkSync(join(route.staticRoot, 'state', 'compact', 'item-health', 'index', 'monthly.json'));
		return {
			afterOpen: async () => { await page.goto(`${route.origin}console/voices/`); },
			afterRead: async () => { route.release(); await route.close(); }
		};
	}) satisfies Driver
])) as Readonly<Record<BasicNothing, Driver>>;
export const DRIVERS: Readonly<Record<string, Readonly<Record<BasicNothing, Driver>>>> = {
	'feeds-failed': states, 'fetch-time': states, 'source-cuts': states, 'why-chosen': states, watchlist: states
};
export const BUILD_TIME: readonly string[] = ['source-health', 'retiring', 'ranking-discount'];
