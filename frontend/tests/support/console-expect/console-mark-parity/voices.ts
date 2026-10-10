/** Which Voices marks must survive a resize? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	charts: [
		{
			name: 'source cut range',
			root: '[data-source-cuts="range"] svg',
			domainAttr: 'data-source-domain',
			frame: '[data-source-cuts="range"] svg',
			itemSel: '[data-source-cut]',
			attrs: ['data-source-cut', 'data-range-min', 'data-range-median', 'data-range-max', 'data-range-past']
		}
	]
};
