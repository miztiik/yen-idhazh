/** Which Pipelines chart exercises a hand-written multi-series readout? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	readout: true,
	handWritten: { id: 'failure-rate', rateSuffix: ' rate' },
	engineSeries: null, keyboard: null, shape: null, recording: null, recordingLines: null
};
