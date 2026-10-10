/** Which cost and length panels must Summaries draw? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	modelPanels: {
		writeTimesChart: '[data-histogram="write-times"]',
		writeTimesReadout: '[data-write-times="readout"]',
		histograms: ['write-times', 'score-cost'],
		windowReadouts: ['[data-write-times="readout"]', '[data-score-cost="readout"]'],
		cardsNote: '[data-model-cards-note]',
		scoreCostReadout: '[data-score-cost="readout"]',
		scoreCostMedian: '[data-score-cost="median"]',
		scoreCostP95: '[data-score-cost="p95"]',
		scoreCostNote: 'after the model has finished',
		scoreColumn: 'score_ms',
		dailyControl: '[data-model-table-control] > summary',
		dailyTable: '[data-model="table"]',
		runLengthsChart: '[data-run-lengths="chart"]'
	},
	scoringStage: null
};
