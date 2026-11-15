/** Which Hardware questions share their original evidence endpoint? */
import * as queries from '../queries/machine';
import type { PanelQuery } from '../queries/window';
import type { LedgerName } from '../../data/ledger';

export const MACHINE_QUERY_GROUPS = [
	{
		id: 'native',
		ledgers: ['item-health', 'host-fingerprint', 'run-shards'],
		queries: [
			queries.runShardsQuery, queries.twoClocksQuery, queries.twoClocksHostsQuery,
			queries.slowerMachinesQuery, queries.platformMixQuery, queries.closestToMemoryQuery,
			queries.memoryHeldQuery, queries.contextHeadroomQuery, queries.articleCostQuery,
			queries.articleCostHostsQuery, queries.promptReuseQuery, queries.readAgainstWrittenQuery
		]
	},
	{
		id: 'slower-on-same-work',
		ledgers: ['item-health'],
		queries: [queries.slowerOnSameWorkQuery]
	}
] as const satisfies readonly { id: string; ledgers: readonly LedgerName[]; queries: readonly PanelQuery[] }[];
