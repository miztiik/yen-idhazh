/** Which groups and opening verdict does Hardware draw? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	layout: null,
	groups: [
		{
			id: 'what-the-machine-was-doing',
			title: 'What the machine was doing',
			panels: ['two-clocks', 'processor-lost', 'disk-reads', 'machine-cards', 'reading-against-writing', 'platform-mix']
		},
		{
			id: 'where-the-time-went',
			title: 'Where the time went',
			panels: ['shard-board', 'tail-trend']
		},
		{
			id: 'how-close-to-the-limits',
			title: 'How close we are to the limits',
			panels: ['memory-board', 'memory-held', 'context-headroom']
		},
		{
			id: 'what-the-model-spends',
			title: 'What the model spends',
			panels: ['article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost']
		}
	],
	verdict: { state: 'route', question: 'is it working' },
	runSquares: false,
	prerender: false
};
