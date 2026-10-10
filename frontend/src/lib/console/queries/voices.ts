/** What does each Voices panel ask the published item ledger? */
import type { PanelQuery } from './window';

export const feedsFailedQuery = {
	name: 'feedsFailedQuery', ledger: 'item-health',
	columns: ['date', 'source_id', 'stage', 'outcome', 'code', 'http_status', 'source_form', 'tier'],
	where: [{ column: 'stage', op: '=', value: 'fetch' }],
	span: 'window'
} as const satisfies PanelQuery;

export const fetchTimeQuery = {
	name: 'fetchTimeQuery', ledger: 'item-health',
	columns: ['source_id', 'fetch_ms', 'fetch_connect_ms', 'fetch_ttfb_ms', 'robots_ms', 'retry_total_ms', 'retry_count'],
	span: 'window'
} as const satisfies PanelQuery;

export const sourceCutsQuery = {
	name: 'sourceCutsQuery', ledger: 'item-health',
	columns: ['date', 'source_id', 'url_key', 'source_words_before_cap', 'source_words'],
	span: 'window'
} as const satisfies PanelQuery;

export const whyChosenQuery = {
	name: 'whyChosenQuery', ledger: 'item-health',
	columns: ['date', 'run_id', 'item_id', 'source_id', 'selection_score', 'authority_score', 'tier_score', 'feed_weight', 'feed_reliability', 'recency_bonus', 'lens_bonus', 'watchlist_bonus', 'carriage_step'],
	span: 'newest-day'
} as const satisfies PanelQuery;

export const watchlistQuery = {
	name: 'watchlistQuery', ledger: 'item-health',
	columns: ['date', 'url_key', 'watchlist_hit', 'on_front_page'],
	span: 'window'
} as const satisfies PanelQuery;
