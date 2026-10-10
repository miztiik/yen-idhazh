/** What words and address must the Summaries tab keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'model',
	label: 'Summaries',
	path: '/console/model/',
	title: 'Summaries \u2014 Console',
	hasBand: true,
	namedAbsence: null,
	carryTo: 'machine',
	fallbackDescription: null,
	machinePanels: null
};
