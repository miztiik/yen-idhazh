/** Which native questions share an evidence endpoint on Pipelines? */
import * as queries from '../queries/pipelines';
import type { PanelQuery } from '../queries/window';
import type { LedgerName } from '../../data/ledger';

export const PIPELINES_QUERY_GROUPS = [
	{
		id: 'native',
		ledgers: ['item-health'],
		queries: [
			queries.failureMixQuery, queries.failedRuleQuery, queries.itemTimeSplitQuery, queries.slowerOnSameWorkQuery,
			queries.stageTimingsQuery, queries.itemCostQuery, queries.runTimelineQuery, queries.articleAgeQuery
		]
	},
	{
		id: 'slowest-articles',
		ledgers: ['item-health', 'host-fingerprint', 'run-shards'],
		queries: [queries.slowestArticlesQuery]
	}
] as const satisfies readonly { id: string; ledgers: readonly LedgerName[]; queries: readonly PanelQuery[] }[];
