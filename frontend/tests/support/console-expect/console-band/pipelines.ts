/** What standing-band behaviour does Pipelines promise? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	viewports: [
		{ name: 'desktop', width: 1440, height: 1000, band: 130, chart: 800 },
		{ name: 'phone', width: 390, height: 844, band: 320, chart: 1200 }
	],
	chromeOrder: true,
	worstState: true,
	runSquares: true,
	sharedBand: true,
	windowStable: false,
	firstPayload: {
		routeData: '/console/__data.json',
		band: '/console/band.json',
		panels: '/telemetry/'
	}
};
