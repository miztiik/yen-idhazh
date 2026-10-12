/** Hardware is a config-only shell; every panel reserves an empty first frame. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	scope: 'route',
	doorPanels: {
		'two-clocks': '', 'processor-lost': '', 'disk-reads': '', 'machine-cards': '',
		'slower-machines': '', 'platform-mix': '', 'slowest-articles': '', 'tail-trend': '',
		'closest-to-memory': '', 'memory-held': '', 'context-headroom': '', 'article-cost': '',
		'prompt-reuse': '', 'read-against-written': '', 'counterfactual-cost': ''
	},
	reservedPanels: [
		'two-clocks', 'processor-lost', 'disk-reads', 'machine-cards', 'slower-machines',
		'platform-mix', 'slowest-articles', 'tail-trend', 'closest-to-memory', 'memory-held',
		'context-headroom', 'article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost'
	],
	pendingPanel: null,
	pageData: ['machineConfig']
};
