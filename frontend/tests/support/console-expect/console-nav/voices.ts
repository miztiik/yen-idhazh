/** What words and address must the Voices tab keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'voices',
	label: 'Voices',
	path: '/console/voices/',
	title: 'Voices \u2014 Console',
	hasBand: true,
	namedAbsence: null,
	carryTo: 'pipelines',
	fallbackDescription: null,
	machinePanels: null
};
