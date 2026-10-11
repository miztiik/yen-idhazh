/** Hardware reports its window on ten measured surfaces. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: [
		'machine-article-cost',
		'machine-context',
		'machine-cost',
		'machine-disk-reads',
		'machine-fleet',
		'machine-latency',
		'machine-processor-lost',
		'machine-prompt-reuse',
		'machine-tokens'
	],
	dailyTable: false,
	ready: '[data-console-panels="machine"]:not([data-route-state="loading"])'
};
