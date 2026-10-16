/** Which panel-frame checks apply to each console route? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly layout: {
		readonly minChartWidth: number;
		readonly minNamedCharts: number;
	} | null;
	readonly groups: readonly {
		readonly id: string;
		readonly title: string;
		readonly panels: readonly string[];
	}[] | null;
	readonly verdict: { readonly state: string; readonly question: string } | null;
	readonly runSquares: boolean;
	readonly prerender: boolean;
	readonly grains?: Readonly<Partial<Record<string, 'newest run' | 'newest day' | 'this one day' | `these ${number} days`>>>;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
