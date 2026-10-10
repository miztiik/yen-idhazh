/** Which words, addresses and document states does each console route owe? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly id: RouteId;
	readonly label: string;
	readonly path: string;
	readonly title: string;
	readonly hasBand: boolean;
	readonly namedAbsence: {
		readonly id: RouteId;
		readonly path: string;
	} | null;
	readonly carryTo: RouteId | null;
	readonly fallbackDescription: string | null;
	readonly machinePanels: {
		readonly intro: string;
		readonly minimumIntroLength: number;
		readonly minimumPanelCount: number;
		readonly emptyPanels: string;
		readonly minimumEmptyLength: number;
		readonly newestRunExemption: string;
		readonly newestRunWords: string;
		readonly twoClocksSubtitle: string;
		readonly twoClocksWords: string;
	} | null;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
