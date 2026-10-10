/** Where do Summaries' recording lines sit relative to its sections? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	readout: true,
	handWritten: null, engineSeries: null, keyboard: null, shape: null, recording: null,
	recordingLines: {
		group: '[data-recording-lines]',
		section: '[data-model-section]',
		heading: 'What the model did'
	}
};
