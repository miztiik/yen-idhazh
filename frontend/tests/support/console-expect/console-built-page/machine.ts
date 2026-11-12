/** Hardware is a config-only shell; every panel reserves an empty first frame. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	scope: 'route',
	doorPanels: {
		'two-clocks': '',
		'slower-machines': '', 'platform-mix': '', 'tail-trend': '',
		'closest-to-memory': '', 'memory-held': '', 'context-headroom': '', 'article-cost': '',
		'prompt-reuse': '', 'read-against-written': ''
	},
	reservedPanels: [
		'two-clocks', 'slower-machines',
		'platform-mix', 'tail-trend', 'closest-to-memory', 'memory-held',
		'context-headroom', 'article-cost', 'prompt-reuse', 'read-against-written'
	],
	pendingPanel: null,
	pageData: ['machineConfig']
};
