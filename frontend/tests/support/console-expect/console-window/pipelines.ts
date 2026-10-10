/** Pipelines reports its window on ten surfaces and its two stacked charts. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: [
		'band-distance',
		'chart-drawing',
		'extraction',
		'failure-mix',
		'failure-rate',
		'item-cost',
		'run-health',
		'site-cost-per-item',
		'telemetry-viewport',
		'time-split'
	],
	dailyTable: true
};
