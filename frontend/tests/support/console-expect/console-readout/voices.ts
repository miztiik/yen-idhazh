/** Voices must declare its HTML charts and support record keyboard readouts. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	partition: true,
	columns: false,
	records: true,
	fleetReady: null,
	fetchedRows: false,
	explorerShape: null
};
