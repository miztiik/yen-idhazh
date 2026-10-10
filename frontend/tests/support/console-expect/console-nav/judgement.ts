/** What words must the six Judgement panels keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'judgement',
	label: 'Judgement',
	path: '/console/judgement/',
	title: 'Judgement \u2014 Console',
	hasBand: true,
	namedAbsence: null,
	carryTo: 'model',
	fallbackDescription: null,
	machinePanels: null
};
