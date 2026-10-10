/** Voices caps the feed list and names the minimum depth for a rate. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	bansRouter: false,
	feedRows: 10,
	minAttempts: 5
};
