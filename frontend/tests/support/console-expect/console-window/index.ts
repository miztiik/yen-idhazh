/** The windowed surfaces and panel words each route publishes. */
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines';
import { EXPECT as model } from './model';
import { EXPECT as machine } from './machine';
import { EXPECT as judgement } from './judgement';
import { EXPECT as voices } from './voices';
import { EXPECT as dataExplorer } from './data-explorer';

export interface RouteExpect {
	readonly windowed: readonly string[];
	readonly dailyTable: boolean;
	readonly panelCases?: readonly {
		readonly state:
			| 'two items failed and one was timed'
			| 'three items were timed and none failed'
			| 'one item failed and two had no end-to-end clock'
			| 'no item was planned';
		readonly mix: Readonly<Record<1 | 7, number | string>>;
		readonly split: Readonly<Record<1 | 7, number | string>>;
	}[];
	readonly panelWords?: Readonly<
		Record<
			'failure-mix' | 'time-split',
			{
				readonly section: Readonly<Record<1 | 7, string>>;
				readonly chart: Readonly<Record<1 | 7, string>>;
				readonly empty: string;
			}
		>
	>;
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = {
	pipelines,
	model,
	machine,
	judgement,
	voices,
	'data-explorer': dataExplorer
};
