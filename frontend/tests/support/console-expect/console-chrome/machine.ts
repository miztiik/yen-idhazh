/** Which Hardware readouts, controls and recording words must remain? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	readout: true,
	handWritten: null,
	engineSeries: null,
	keyboard: { id: 'read-against-written', dateSeries: true },
	shape: null,
	recording: {
		intro: '[data-machine="intro"]',
		forbidden: ['host_fingerprint', 'evaluation_enabled', 'sample_rate']
	},
	recordingLines: null
};
