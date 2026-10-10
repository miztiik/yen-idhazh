/** Which independently declared first frames and page-data keys does each route owe? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as voices } from './voices';
import { EXPECT as judgement } from './judgement';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly scope: 'route' | 'platform-mix-only';
	readonly doorPanels: Readonly<Record<string, string>>;
	readonly pageData: readonly string[];
	readonly reservedPanels: readonly string[];
	readonly pendingPanel: {
		readonly selector: string;
		readonly stateAttribute: string;
		readonly emptyAttributes: readonly string[];
	} | null;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, voices, judgement, 'data-explorer': dataExplorer
};
