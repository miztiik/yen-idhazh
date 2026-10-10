/** Summaries must support the column readout checks. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	partition: true,
	columns: true,
	records: false,
	fleetReady: null,
	fetchedRows: false,
	explorerShape: null
};
