/** Which route owns the state drivers and build-time declarations for its judged panels? */

import type { RouteId } from '../../../src/lib/console/band';
import type { BasicNothing, Driver, Nothing } from '../panel-gates';
import * as pipelines from './pipelines';
import * as model from './model';
import * as machine from './machine';
import * as voices from './voices';
import * as judgement from './judgement';
import * as explorer from './data-explorer';

/** Every driven panel has the four nothings; a refusing reader also has `refused`. */
export type PanelDrivers = Readonly<Record<BasicNothing, Driver>> &
	Partial<Readonly<Record<Nothing, Driver>>>;

export interface RouteDrivers {
	readonly DRIVERS: Readonly<Record<string, PanelDrivers>>;
	readonly BUILD_TIME: readonly string[];
}

export const BY_ROUTE: Readonly<Record<RouteId, RouteDrivers>> = {
	pipelines,
	model,
	machine,
	voices,
	judgement,
	'data-explorer': explorer
};
