/** The address, label and heading floor each route keeps after a rename. */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly href: string;
	readonly label: string;
	readonly minimumHeadings: number | null;
	readonly renamedTitles: readonly string[];
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines,
	model,
	machine,
	judgement,
	voices,
	'data-explorer': dataExplorer
};
