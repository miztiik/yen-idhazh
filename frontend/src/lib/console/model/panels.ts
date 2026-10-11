import * as queries from '../queries/model';
import type { PanelQuery, Range } from '../queries/window';
import type { ConsoleShell } from '../band';
import { settingsRules } from '../settings-moved';
import { nameSpan } from '../span-words';

export const panelQueries: Readonly<Record<string, readonly PanelQuery[]>> = {
	'model-throughput': [queries.modelThroughputQuery], 'call-ending': [queries.callEndingQuery],
	'refusing-rule': [queries.failedRuleQuery], faithfulness: [queries.faithfulnessQuery],
	'source-doubts': [queries.sourceDoubtsQuery, queries.sourceDoubtsItemsQuery],
	'write-cost': [queries.writeCostQuery], 'score-cost': [queries.scoreCostQuery],
	'summary-length': [queries.summaryLengthQuery], 'model-change': [queries.modelChangeQuery, queries.modelChangeItemsQuery]
};
export const titles: Readonly<Record<string, string>> = {
	'model-cards': 'What the model did', 'model-throughput': 'Model tokens per second',
	'call-ending': 'How a model call ended', 'refusing-rule': 'Which rule refused a reply',
	'doubt-reasons': 'Why a summary was doubted', faithfulness: 'Summary faithfulness, day by day',
	'source-doubts': 'Which sources the checker doubts', 'write-cost': 'What one summary cost',
	'score-cost': 'What checking one summary cost', 'summary-length': 'How long summaries came out',
	'model-change': 'What the model change moved'
};
export function modelRuleFor(id: string, shell: ConsoleShell, range: Range) {
	if (['refusing-rule', 'source-doubts', 'write-cost', 'score-cost'].includes(id)) {
		return { declined: 'One ranking or distribution pools the window and has no dated change position.' } as const;
	}
	if (id === 'model-change') return { declined: 'This panel compares the two sides of the model change itself.' } as const;
	return settingsRules(shell, { from: range.from, to: range.to }, id === 'faithfulness' ? 'score' : 'none', nameSpan(range.days));
}
