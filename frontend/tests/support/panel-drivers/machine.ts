/** How is each judged Hardware panel put into its four nothings? */

import type { BasicNothing, Driver } from '../panel-gates';
import { machineRecordState } from '../machine-record-state';

const STATES: Readonly<Record<BasicNothing, Driver>> = {
		loading: (page) => machineRecordState(page, 'loading'),
		missing: (page) => machineRecordState(page, 'missing'),
		quiet: (page) => machineRecordState(page, 'quiet'),
		unreachable: (page) => machineRecordState(page, 'unreachable')
};
export const DRIVERS: Readonly<Record<string, Readonly<Record<BasicNothing, Driver>>>> = Object.fromEntries([
	'two-clocks', 'processor-lost', 'disk-reads', 'machine-cards', 'slower-machines', 'platform-mix',
	'slowest-articles', 'tail-trend', 'closest-to-memory', 'memory-held', 'context-headroom',
	'article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost'
].map((id) => [id, STATES]));

export const BUILD_TIME: readonly string[] = [];
