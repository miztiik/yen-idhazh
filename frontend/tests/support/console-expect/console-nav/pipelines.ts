/** What words and address must the Pipelines tab keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'pipelines',
	label: 'Pipelines',
	path: '/console/',
	title: 'Pipelines \u2014 Console',
	hasBand: true,
	namedAbsence: null,
	carryTo: 'model',
	fallbackDescription: null,
	machinePanels: null
};
