/** Which charts must keep their data across a resize on each route? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface Chart {
	readonly name: string;
	readonly root: string;
	readonly domainAttr: string;
	readonly frame: string;
	readonly itemSel: string;
	readonly attrs: readonly string[];
}

export interface RouteExpect {
	readonly charts: readonly Chart[];
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
