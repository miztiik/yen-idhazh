/** Which Pipelines marks must survive a resize? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	charts: [
		{
			name: 'stage timings',
			root: '[data-timing="plot"]',
			domainAttr: 'data-timing-domain',
			frame: '[data-timing="plot"]',
			itemSel: 'polyline[data-stage-mark], circle[data-stage-mark], circle[data-stage-zero]',
			attrs: ['data-stage-mark', 'data-stage-zero']
		},
		{
			name: 'band distance',
			root: '[data-band-distance]',
			domainAttr: 'data-band-domain',
			frame: '[data-band-distance] svg',
			itemSel: '[data-band-day]',
			attrs: ['data-band-day', 'data-band-inside', 'data-band-short', 'data-band-long', 'data-band-items']
		}
	]
};
