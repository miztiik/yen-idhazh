/** How is each judged Hardware panel put into its four nothings? */

import type { BasicNothing, Driver } from '../panel-gates';
import { machineRecordState } from '../machine-record-state';

export const DRIVERS: Readonly<Record<string, Readonly<Record<BasicNothing, Driver>>>> = {
	'platform-mix': {
		loading: (page) => machineRecordState(page, 'loading'),
		missing: (page) => machineRecordState(page, 'missing'),
		quiet: (page) => machineRecordState(page, 'quiet'),
		unreachable: (page) => machineRecordState(page, 'unreachable')
	}
};

export const BUILD_TIME: readonly string[] = [];
