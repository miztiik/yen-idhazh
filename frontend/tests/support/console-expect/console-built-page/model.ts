/** Summaries' declared door panels contain no prerendered ledger values. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	scope: 'route',
	doorPanels: { 'model-throughput': '', 'item-cost': '', 'call-ending': '', faithfulness: 'How each of these measures is scored',
		'score-cost': '', 'summary-length': '' },
	pageData: ['cardDays', 'cardReads', 'instruments', 'publishedDates', 'windowDay', 'chart', 'summarizeBands', 'matchThresholds', 'recordingNotes',
		'measurementOff', 'recordNotes', 'throughputReference', 'faithfulnessReference'],
	reservedPanels: ['model-throughput', 'item-cost', 'call-ending', 'faithfulness', 'score-cost', 'summary-length'],
	pendingPanel: null
};
