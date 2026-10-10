/** Voices declares two ordered groups and its fully prerendered unpublished readings. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect | null = {
	layout: { minChartWidth: 280, minNamedCharts: 2 },
	groups: [
		{ id: 'what-the-sources-supplied', title: 'What the sources supplied', panels: ['source-health', 'feeds-failed', 'fetch-time', 'retiring', 'source-cuts'] },
		{ id: 'what-the-ranking-did', title: 'What the ranking did', panels: ['ranking-discount', 'why-chosen', 'watchlist'] }
	],
	verdict: null, runSquares: false, prerender: true
};
