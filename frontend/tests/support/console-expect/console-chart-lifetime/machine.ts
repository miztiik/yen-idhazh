/** Which Hardware charts exercise deferred drawing, updates and release? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	leaveTo: 'model',
	shape: { control: 'cost-shape', initial: 'daily', next: 'running' },
	window: { hostSelector: '[data-read-write-unit] [data-chart]' }
};
