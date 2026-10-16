/** Voices declares its windowed native surfaces; newest-day choice is explicitly exempt. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: ['feeds-failed', 'fetch-time', 'source-cuts', 'watchlist'],
	dailyTable: false
};
