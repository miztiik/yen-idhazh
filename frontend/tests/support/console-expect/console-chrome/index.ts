/** Which chart-chrome checks apply to each console route? */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly readout: boolean;
	readonly handWritten: { readonly id: string; readonly rateSuffix: string } | null;
	readonly engineSeries: { readonly id: string; readonly labels: readonly string[] } | null;
	readonly keyboard: { readonly id: string } | null;
	readonly shape: {
		readonly control: string;
		readonly chart: string;
		readonly initial: string;
		readonly next: string;
		readonly nextLabel: RegExp;
		readonly initialLabel: RegExp;
	} | null;
	readonly recording: { readonly intro: string; readonly forbidden: readonly string[] } | null;
	readonly recordingLines: {
		readonly group: string;
		readonly section: string;
		readonly heading: string;
	} | null;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines, model, machine, judgement, voices, 'data-explorer': dataExplorer
};
