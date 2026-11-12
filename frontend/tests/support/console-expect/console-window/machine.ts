/** Which retained Hardware surfaces follow the selected window? */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: [
		'machine-article-cost',
		'machine-context',
		'machine-fleet',
		'machine-latency',
		'machine-prompt-reuse',
		'machine-tokens'
	],
	dailyTable: false,
	ready: '[data-console-panels="machine"]:not([data-route-state="loading"])'
};
