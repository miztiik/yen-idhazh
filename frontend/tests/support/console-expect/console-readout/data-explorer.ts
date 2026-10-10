/** Data explorer must declare the shape chart's readout after a question runs. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	partition: false,
	columns: false,
	records: false,
	fleetReady: null,
	fetchedRows: false,
	explorerShape: {
		askPanel: '[data-console-panel-id="data-explorer-ask"]',
		ledgersRegion: '[data-workbench-region="ledgers"]',
		ledgerNames: '[data-ledger-name]',
		shapePanel: '[data-console-panel-id="data-explorer-shape"]',
		chartType: 'dateSeries'
	}
};
