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
			selector: '[data-voices="reliability"], [data-console-empty="voices"]'
		},
		{ name: 'the feed failure record', selector: '[data-window-exempt="feeds"]' },
		{ name: 'the truncation cap cost', selector: '[data-windowed="source-cuts"]' }
	],
	ownedSelectors: [
		'[data-feed]',
		'[data-feeds]',
		'[data-feed-result]',
		'[data-feed-reliability]',
		'[data-feed-clean-name]',
		'[data-feed-ineligible-name]',
		'[data-feed-strip]',
		'[data-feed-axis]',
		'[data-rested]',
		'[data-source-health]',
		'[data-source-health-lead]',
		'[data-source-state]',
		'[data-source-note]',
		'[data-source-cut]',
		'[data-source-cuts-intro]',
		'[data-windowed="source-cuts"]',
		'[data-windowed="feed-outcomes"]',
		'[data-window-exempt="feeds"]',
		'[data-window-exempt="source-health"]'
	]
};
