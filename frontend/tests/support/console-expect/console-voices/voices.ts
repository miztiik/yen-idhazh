/** Voices owns each moved source panel and every attribute under them. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	href: '/console/voices/',
	panelCopies: 1,
	panels: [
		{
			name: 'the source census',
			selector: '[data-source-health-lead], [data-source-health="absent"]'
		},
		{
			name: 'the ranking weight',
			selector: '[data-console-panel-id="ranking-discount"]'
		},
		{ name: 'the feed and article failure record', selector: '[data-console-panel-id="feeds-failed"]' },
		{ name: 'the truncation cap cost', selector: '[data-console-panel-id="source-cuts"]' },
		{ name: 'the fetch clock record', selector: '[data-console-panel-id="fetch-time"]' },
		{ name: 'the retirement distance', selector: '[data-console-panel-id="retiring"]' },
		{ name: 'the newest choice', selector: '[data-console-panel-id="why-chosen"]' },
		{ name: 'the watchlist catch', selector: '[data-console-panel-id="watchlist"]' }
	],
	ownedSelectors: [
		'[data-failed-source]',
		'[data-feeds]',
		'[data-feed-reliability]',
		'[data-feed-clean-name]',
		'[data-feed-ineligible-name]',
		'[data-source-health]',
		'[data-source-health-lead]',
		'[data-source-state]',
		'[data-source-note]',
		'[data-source-cut]',
		'[data-source-cuts-intro]',
		'[data-windowed="source-cuts"]',
		'[data-window-exempt="source-health"]'
	]
};
