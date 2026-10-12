/** Read only the exact approved Summaries declarations through the ledger door. */
import * as queries from '../queries/model';
import { sliceOnce, type PanelQuery, type Range } from '../queries/window';

export function modelSlice(query: PanelQuery, range: Range) {
	switch (query.name) {
		case 'modelThroughputQuery': return sliceOnce(queries.modelThroughputQuery, range);
		case 'callEndingQuery': return sliceOnce(queries.callEndingQuery, range);
		case 'failedRuleQuery': return sliceOnce(queries.failedRuleQuery, range);
		case 'faithfulnessQuery': return sliceOnce(queries.faithfulnessQuery, range);
		case 'sourceDoubtsQuery': return sliceOnce(queries.sourceDoubtsQuery, range);
		case 'sourceDoubtsItemsQuery': return sliceOnce(queries.sourceDoubtsItemsQuery, range);
		case 'writeCostQuery': return sliceOnce(queries.writeCostQuery, range);
		case 'scoreCostQuery': return sliceOnce(queries.scoreCostQuery, range);
		case 'summaryLengthQuery': return sliceOnce(queries.summaryLengthQuery, range);
		case 'modelChangeQuery': return sliceOnce(queries.modelChangeQuery, range);
		case 'modelChangeItemsQuery': return sliceOnce(queries.modelChangeItemsQuery, range);
		default: throw new Error(`No declared Summaries query is named ${query.name}.`);
	}
}
