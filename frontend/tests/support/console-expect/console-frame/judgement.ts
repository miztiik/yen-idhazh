/** Keep publication evidence separate from nightly judge diagnostics. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	layout: null,
	groups: [
		{ id: 'judgement', title: 'Published grouping', panels: ['merged-stories', 'holdout-margin'] },
		{ id: 'council-activity', title: 'Council activity', panels: ['council-runs'] },
		{ id: 'judge-observations', title: 'Judge: Content Similarity', panels: ['judge-coverage', 'judge-score-ranges', 'pair-score-drift'] }
	],
	verdict: null,
	runSquares: false,
	prerender: true
};
