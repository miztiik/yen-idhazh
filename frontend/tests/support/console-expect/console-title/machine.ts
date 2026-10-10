/** Hardware keeps the machine address and its nineteen headings. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	href: '/console/machine/',
	label: 'Hardware',
	minimumHeadings: 19,
	renamedTitles: [
		'Whether the speed numbers can be trusted',
		'Whether the slowest articles are getting slower'
	]
};
