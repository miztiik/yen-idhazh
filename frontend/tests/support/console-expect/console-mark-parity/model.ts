/** Which Summaries marks must survive a resize? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	charts: [
		{
			name: 'run lengths',
			root: '[data-run-lengths="chart"]',
			domainAttr: 'data-run-domain',
			frame: '[data-run-lengths="chart"] svg',
			itemSel: '[data-run-length]',
			attrs: ['data-run-length', 'data-run-low', 'data-run-median', 'data-run-high', 'data-run-items']
		},
		{
			name: 'time histogram',
			root: '[data-histogram-n]',
			domainAttr: 'data-hist-domain',
			frame: '[data-histogram-n] svg',
			itemSel: '[data-hist-bin]',
			attrs: ['data-hist-bin', 'data-hist-bin-n']
		}
	]
};
