/** Which judged Summaries panels have state drivers or build-time inputs? */

import type { Driver, BasicNothing } from '../panel-gates';
import { modelRecordState } from '../model-record-state';

const states: Readonly<Record<BasicNothing, Driver>> = {
	loading: (page) => modelRecordState(page, 'loading'),
	missing: (page) => modelRecordState(page, 'missing'),
	quiet: (page) => modelRecordState(page, 'quiet'),
	unreachable: (page) => modelRecordState(page, 'unreachable')
};
export const DRIVERS = Object.fromEntries([
	'model-throughput', 'call-ending', 'refusing-rule', 'faithfulness', 'source-doubts',
	'write-cost', 'score-cost', 'summary-length', 'model-change'
].map((id) => [id, states]));
export const BUILD_TIME: readonly string[] = ['model-cards', 'doubt-reasons'];
