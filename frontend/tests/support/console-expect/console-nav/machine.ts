/** What words and address must the Hardware tab keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'machine',
	label: 'Hardware',
	path: '/console/machine/',
	title: 'Hardware \u2014 Console',
	hasBand: true,
	namedAbsence: null,
	carryTo: 'pipelines',
	fallbackDescription: null,
	machinePanels: {
		intro: '[data-machine="intro"]',
		minimumIntroLength: 40,
		minimumPanelCount: 5,
		emptyPanels: '[data-machine-panel-empty]',
		minimumEmptyLength: 20,
		newestRunExemption: '[data-window-exempt="newest-run"]',
		newestRunWords: 'newest run',
		twoClocksSubtitle: '[data-console-panel-id="two-clocks"] > header > p',
		twoClocksWords: 'the newest run'
	}
};
