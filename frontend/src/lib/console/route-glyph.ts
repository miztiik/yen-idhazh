/** Existing glyph identities name console destinations, never their health. */
import type { RouteId } from './band';
import type { IconId } from '../icons/generated';

export const ROUTE_GLYPHS = {
	pipelines: 'shape-flow',
	model: 'summaries',
	machine: 'console',
	judgement: 'judgement',
	voices: 'voices',
	'data-explorer': 'ledgers'
} as const satisfies Record<RouteId, IconId>;
