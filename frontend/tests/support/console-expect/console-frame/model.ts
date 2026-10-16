/** Summaries has one untitled panel group and a first-card verdict. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect | null = {
	layout: { minChartWidth: 320, minNamedCharts: 5 },
	groups: null,
	verdict: { state: 'route', question: 'is it working' },
	runSquares: false,
	prerender: true
};
