/** Which scoring marks must stay off the critical-path timing chart? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	modelPanels: null,
	scoringStage: {
		absent: [
			'[data-readout="timings"] [data-readout-row="score"]',
			'[data-stage-mark="score"]',
			'[data-timing-note="score"]'
		],
		plot: '[data-timing="plot"]',
		seriesAttribute: 'data-timing-series',
		maximumSeries: 3
	}
};
