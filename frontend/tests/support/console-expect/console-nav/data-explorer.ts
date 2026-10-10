/** What fallback words and address must Data explorer keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'data-explorer',
	label: 'Data explorer',
	path: '/console/data-explorer/',
	title: 'Data explorer \u2014 Console',
	hasBand: false,
	namedAbsence: null,
	carryTo: null,
	fallbackDescription: 'What the ledgers hold, and whatever you ask of them.',
	machinePanels: null
};
