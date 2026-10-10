/** Which standing-band checks apply to each console route? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly viewports: readonly {
		readonly name: string;
		readonly width: number;
		readonly height: number;
		readonly band: number;
		readonly chart: number;
	}[];
	readonly chromeOrder: boolean;
	readonly worstState: boolean;
	readonly runSquares: boolean;
	readonly sharedBand: boolean;
	readonly windowStable: boolean;
	readonly firstPayload: {
		readonly routeData: string;
		readonly band: string;
		readonly panels: string;
	} | null;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
