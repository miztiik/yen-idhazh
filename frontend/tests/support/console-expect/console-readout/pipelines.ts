/** Pipelines must support column, record and fetched-row readouts. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	partition: true,
	columns: true,
	records: true,
	fleetReady: null,
	fetchedRows: true,
	explorerShape: null
};
