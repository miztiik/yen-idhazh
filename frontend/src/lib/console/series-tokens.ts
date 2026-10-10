/** Which colour belongs to a console quantity, independent of its position. */
import type { ChartToken } from '../charts/theme';

export const SERIES_TOKENS = {
	fetch: '--chart-1',
	'failed-fetch': '--chart-1',
	extract: '--chart-2',
	summarize: '--chart-3',
	'model-time': '--chart-3',
	'label-call': '--chart-4',
	'summary-call': '--chart-5',
	'visual-plan': '--chart-6',
	checking: '--chart-7',
	unattributed: '--chart-8',
	other: '--chart-8',
	'never-fetched': '--chart-8',
	'not-recorded': '--chart-8',
	'never-checked': '--chart-8',
	'fetch-rest': '--chart-8',
	'other-memory': '--chart-8',
	'queue-wait': '--chart-axis',
	'reading-prompt': '--chart-6',
	'writing-reply': '--chart-7',
	'done-by-then': '--chart-3',
	'model-server-memory': '--chart-1',
	'worker-memory': '--chart-3',
	'free-memory': null,
	'robots-check': '--chart-3',
	'waiting-headers': '--chart-2',
	retries: '--chart-4',
	connecting: '--chart-5',
	authority: '--chart-1',
	recency: '--chart-2',
	lens: '--chart-4',
	watchlist: '--chart-5',
	'watchlist-day': '--chart-5',
	carriage: '--chart-7',
	'length-limit': '--chart-4',
	'other-ending': '--chart-2',
	'ended-on-own': '--chart-axis',
	'unsupported-numbers': '--chart-1',
	'does-not-match': '--chart-2',
	'opening-left-out': '--chart-4',
	'maybe-as-fact': '--chart-5'
} as const satisfies Record<string, ChartToken | null>;

export type Quantity = keyof typeof SERIES_TOKENS;

export function quantityToken(quantity: Quantity): ChartToken | null {
	return SERIES_TOKENS[quantity];
}

/** Kept callers retain their established colours until they adopt named quantities. */
export const KEPT_COST_TOKENS = { read: '--chart-1', written: '--chart-4', running: '--chart-2' } as const;

export const KEPT_TIME_TOKENS = {
	fetch: '--chart-1', extract: '--chart-2', label: '--chart-3', summary: '--chart-4',
	plan: '--chart-5', model: '--chart-6', faithfulness: '--chart-7', gap: '--chart-8'
} as const;
