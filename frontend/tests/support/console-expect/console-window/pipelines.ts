/** The newest-run timeline alone does not follow the day preset. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: [
		'at-a-glance',
		'chart-drawing',
		'extraction',
		'failure-mix',
		'article-age',
		'item-cost',
		'run-health',
		'site-cost-per-item',
		'slower-on-same-work',
		'stage-timings',
		'item-time-split'
	],
	dailyTable: true
};
