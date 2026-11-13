/** Native first frames contain no ledger facts; the private panels are separate. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	scope: 'route',
	doorPanels: {
		'failure-mix': '', 'item-time-split': '', 'tail-trend': '', 'stage-timings': '',
		'write-cost': '', 'run-timeline': '', 'slowest-articles': '', 'article-age': ''
	},
	pageData: [
		'manifests', 'charts', 'publishedItems', 'grid', 'floorPct', 'runYieldDays', 'chart', 'windowDay', 'visualAttempts'
	],
	reservedPanels: ['failure-mix', 'item-time-split', 'stage-timings', 'write-cost', 'tail-trend', 'run-timeline', 'slowest-articles', 'article-age'],
	pendingPanel: null
};
