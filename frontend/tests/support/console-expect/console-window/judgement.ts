/** The holdout owns its reach; the selected-day ranges follow the selected digest. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: ['merged-stories', 'judge-coverage', 'pair-score-drift', 'judge-canaries'],
	dailyTable: false
};
