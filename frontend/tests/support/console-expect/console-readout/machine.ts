/** Hardware readout checks wait for its fleet chart and drive columns and records. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	partition: true,
	columns: true,
	records: true,
	fleetReady: '[data-windowed="machine-fleet"]',
	fetchedRows: false,
	explorerShape: null
};
