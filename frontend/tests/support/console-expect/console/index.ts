/** The route-owned caps, column formats and retained panels this spec checks. */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly bansRouter: boolean;
	readonly failureListMax?: number;
	readonly feedRows?: number;
	readonly minAttempts?: number;
	readonly stageHeading?: string;
	readonly renamedFigures?: readonly { readonly selector: string; readonly count: number }[];
	readonly cellFormats?: Readonly<Record<string, RegExp>>;
	readonly unscoredCells?: readonly string[];
	readonly internalColumns?: readonly string[];
	readonly sectionHeading?: string;
	readonly chartHeading?: string;
	readonly throughputLink?: { readonly label: string; readonly href: string };
	readonly readoutRows?: readonly string[];
	readonly readoutSeries?: readonly string[];
	readonly readoutHint?: string;
	readonly sectionOrder?: readonly string[];
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines,
	model,
	machine,
	judgement,
	voices,
	'data-explorer': dataExplorer
};
