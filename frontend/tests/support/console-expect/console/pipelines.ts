/** Pipelines keeps its failure cap and every figure of the renamed chart section. */
import type { RouteExpect } from './index';

export const EXPECT: RouteExpect | null = {
	bansRouter: true,
	failureListMax: 25,
	stageHeading: 'Time per item, by stage',
	renamedFigures: [
		{ selector: '[data-windowed="chart-drawing"] [data-rule-figure]', count: 2 },
		{ selector: '[data-windowed="chart-drawing"] [data-target-bar]', count: 2 },
		{ selector: '[data-windowed="chart-drawing"] [data-sparkline]', count: 2 },
		{ selector: '[data-flow]', count: 1 },
		{ selector: '[data-charts="table"] thead th', count: 8 }
	]
};
