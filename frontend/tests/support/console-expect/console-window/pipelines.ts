/** Newest-run snapshots do not narrow the run with the selected day preset. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: [
		'at-a-glance',
		'chart-drawing',
		'failure-mix',
		'article-age',
		'visual-refusals',
		'write-cost',
		'run-health',
		'site-cost-per-item',
		'slower-on-same-work',
		'stage-timings',
		'item-time-split'
	],
	dailyTable: true
};
