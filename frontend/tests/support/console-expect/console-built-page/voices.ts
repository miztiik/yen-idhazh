/** Voices reserves every native-query surface and serializes only unpublished inputs. */
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect | null = {
	scope: 'route',
	doorPanels: { 'feeds-failed': '', 'fetch-time': '', 'source-cuts': '', 'why-chosen': '', watchlist: '' },
	pageData: ['sourceView', 'retiring', 'feedInput', 'chart'],
	reservedPanels: ['feeds-failed', 'fetch-time', 'source-cuts', 'why-chosen', 'watchlist'],
	pendingPanel: null
};
