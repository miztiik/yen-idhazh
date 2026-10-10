/** What panel-frame behaviour does Pipelines promise? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	layout: { minChartWidth: 320, minNamedCharts: 6 },
	groups: null,
	verdict: { state: 'route', question: 'is it working' },
	runSquares: true,
	prerender: true
};
