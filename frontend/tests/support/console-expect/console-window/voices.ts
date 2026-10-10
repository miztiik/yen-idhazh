/** Voices reports its window on feed outcomes and source cuts. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: ['feed-outcomes', 'source-cuts'],
	dailyTable: false
};
