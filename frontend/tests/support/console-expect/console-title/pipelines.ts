/** Pipelines keeps its address and the run-health panel's new title. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	href: '/console/',
	label: 'Pipelines',
	minimumHeadings: 3,
	renamedTitles: ['Articles published against planned']
};
