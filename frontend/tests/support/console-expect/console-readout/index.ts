/** Which column, record, fetched and explorer readouts must each route support? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly partition: boolean;
	readonly columns: boolean;
	readonly records: boolean;
	readonly fleetReady: string | null;
	readonly fetchedRows: boolean;
	readonly explorerShape: {
		readonly askPanel: string;
		readonly ledgersRegion: string;
		readonly ledgerNames: string;
		readonly shapePanel: string;
		readonly chartType: string;
	} | null;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
