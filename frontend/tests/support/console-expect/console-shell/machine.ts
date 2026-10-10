/** Hardware offers a jump link for each of its four groups. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	groups: [
		{ id: 'what-the-machine-was-doing', title: 'What the machine was doing' },
		{ id: 'where-the-time-went', title: 'Where the time went' },
		{ id: 'how-close-to-the-limits', title: 'How close we are to the limits' },
		{ id: 'what-the-model-spends', title: 'What the model spends' }
	]
};
