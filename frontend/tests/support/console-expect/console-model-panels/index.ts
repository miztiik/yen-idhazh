/** Which distribution panels and scoring-stage exclusions belong to each route? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly modelPanels: {
		readonly writeTimesChart: string;
		readonly writeTimesReadout: string;
		readonly histograms: readonly string[];
		readonly windowReadouts: readonly string[];
		readonly cardsNote: string;
		readonly scoreCostReadout: string;
		readonly scoreCostMedian: string;
		readonly scoreCostP95: string;
		readonly scoreCostNote: string;
		readonly scoreColumn: string;
		readonly dailyControl: string;
		readonly dailyTable: string;
		readonly runLengthsChart: string;
	} | null;
	readonly scoringStage: {
		readonly absent: readonly string[];
		readonly plot: string;
		readonly seriesAttribute: string;
		readonly maximumSeries: number;
	} | null;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
