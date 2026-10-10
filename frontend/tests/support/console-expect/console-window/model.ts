/** Summaries reports its window on its cards and daily figures. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: ['daily-figures', 'model-cards'],
	dailyTable: true
};
