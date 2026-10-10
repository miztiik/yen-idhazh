/** Which Pipelines chart must read every model-change boundary? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	boundaryReadout: {
		chart: '[data-model-rule-name="timings"]',
		row: '[data-readout-row="How summaries are written"]'
	}
};
