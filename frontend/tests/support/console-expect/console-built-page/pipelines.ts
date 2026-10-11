/** Native first frames contain no ledger facts; the private panels are separate. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	scope: 'route',
	doorPanels: {
		'failure-mix': '', 'item-time-split': '', 'slower-on-same-work': '', 'stage-timings': '',
		'item-cost': '', 'run-timeline': '', 'article-age': ''
	},
	pageData: [
		'manifests', 'charts', 'publishedItems', 'grid', 'floorPct', 'extractionPublishedByWindow',
		'extractionDays', 'runYieldDays', 'chart', 'windowDay'
	],
	reservedPanels: ['failure-mix', 'item-time-split', 'slower-on-same-work', 'stage-timings', 'item-cost', 'run-timeline', 'article-age'],
	pendingPanel: null
};
