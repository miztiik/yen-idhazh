/** Judgement reports its window on four judge surfaces. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	windowed: ['judge-agreement', 'merge-line', 'merged-stories', 'record-gates'],
	dailyTable: false
};
