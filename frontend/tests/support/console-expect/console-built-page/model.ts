/** Summaries' declared door panels contain no prerendered ledger values. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	scope: 'route',
	doorPanels: { 'model-throughput': '', 'call-ending': '', faithfulness: 'How each of these measures is scored',
		'source-doubts': '', 'write-cost': '', 'score-cost': '', 'summary-length': '' },
	pageData: ['cardDays', 'cardReads', 'instruments', 'reasons', 'windowDay', 'chart', 'summarizeBands', 'matchThresholds', 'recordingNotes',
		'measurementOff', 'recordNotes', 'throughputReference', 'faithfulnessReference'],
	reservedPanels: ['model-throughput', 'call-ending', 'faithfulness', 'source-doubts', 'write-cost', 'score-cost', 'summary-length'],
	pendingPanel: null
};
