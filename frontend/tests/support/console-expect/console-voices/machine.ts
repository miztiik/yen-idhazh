/** Hardware owns no copy of the source panels. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	href: '/console/machine/',
	panelCopies: 0,
	panels: [],
	ownedSelectors: []
};
