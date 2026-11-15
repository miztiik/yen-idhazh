/** Which native questions share an evidence endpoint on Pipelines? */
import * as queries from '../queries/pipelines';
import type { PanelQuery } from '../queries/window';
import type { LedgerName } from '../../data/ledger';

export const PIPELINES_QUERY_GROUPS = [
	{
		id: 'native',
		ledgers: ['item-health'],
		queries: [
			queries.failureMixQuery, queries.failedRuleQuery, queries.itemTimeSplitQuery,
			queries.stageTimingsQuery, queries.runTimelineQuery, queries.articleAgeQuery
		]
	},
	{
		id: 'hardware-timing',
		ledgers: ['item-health', 'host-fingerprint', 'run-shards'],
		queries: [queries.slowestArticlesQuery, queries.tailTrendQuery]
	},
	{
		id: 'write-cost',
		ledgers: ['item-health', 'summary-quality-evals'],
		queries: [queries.writeCostQuery]
	}
] as const satisfies readonly { id: string; ledgers: readonly LedgerName[]; queries: readonly PanelQuery[] }[];
