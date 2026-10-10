/** What words and named absence must Judgement keep? */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect = {
	id: 'judgement',
	label: 'Judgement',
	path: '/console/judgement/',
	title: 'Judgement \u2014 Console',
	hasBand: true,
	namedAbsence: { id: 'judgement', path: '/console/judgement/' },
	carryTo: 'model',
	fallbackDescription: null,
	machinePanels: null
};
