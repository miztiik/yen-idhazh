/** Which judged Summaries panels have state drivers or build-time inputs? */

import type { Driver, Nothing } from '../panel-gates';

export const DRIVERS: Readonly<Record<string, Readonly<Record<Nothing, Driver>>>> = {};
export const BUILD_TIME: readonly string[] = [];
