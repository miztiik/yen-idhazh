/** Which model-stage rule has the most recorded refusals in this window? */
import type { Row } from '../../data/ledger';
import { failureRuleRows, failureRules } from '../failure-rules';

export const MODEL_STAGES = ['summarize', 'label', 'visual-plan'] as const;

export function refusingRule(rows: readonly Row[], window: { start: string; end: string }) {
	const ranking = failureRuleRows(rows).filter((row) => MODEL_STAGES.some((stage) => stage === row.stage));
	const counts = failureRules(ranking, window, 'summarize');
	const top = [...counts.rules].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))[0];
	return { ranking, top, failed: counts.failed };
}
