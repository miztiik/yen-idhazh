/** Voices groups source supply separately from ranking decisions. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	groups: [
		{ id: 'what-the-sources-supplied', title: 'What the sources supplied' },
		{ id: 'what-the-ranking-did', title: 'What the ranking did' }
	]
};
