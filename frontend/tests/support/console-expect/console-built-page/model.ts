/** Summaries' declared door panels contain no prerendered ledger values. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	scope: 'route',
	doorPanels: { 'model-throughput': '', 'call-ending': '', 'refusing-rule': '', faithfulness: 'How each of these measures is scored',
		'source-doubts': '', 'write-cost': '', 'score-cost': '', 'summary-length': '', 'model-change': '' },
	pageData: ['cardDays', 'instruments', 'reasons', 'windowDay', 'chart', 'summarizeBands', 'matchThresholds', 'recording',
		'buildRecord', 'throughputReference', 'faithfulnessReference'],
	reservedPanels: ['model-throughput', 'call-ending', 'refusing-rule', 'faithfulness', 'source-doubts', 'write-cost', 'score-cost', 'summary-length', 'model-change'],
	pendingPanel: null
};
