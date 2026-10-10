/** Which Hardware readouts, controls and recording words must remain? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	readout: true,
	handWritten: null,
	engineSeries: { id: 'clocks', labels: ['Item ledger', 'Model server', 'Apart'] },
	keyboard: { id: 'read-against-written' },
	shape: {
		control: 'cost-shape', chart: 'counterfactual-cost',
		initial: 'daily', next: 'running',
		nextLabel: /added up day by day/, initialLabel: /one column a day/
	},
	recording: {
		intro: '[data-machine="intro"]',
		forbidden: ['host_fingerprint', 'evaluation_enabled', 'sample_rate']
	},
	recordingLines: null
};
