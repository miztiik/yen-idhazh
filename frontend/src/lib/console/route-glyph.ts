/** Existing glyph identities name console destinations, never their health. */
import type { RouteId } from './band';

export const ROUTE_GLYPHS = {
	pipelines: 'shape-flow',
	model: 'summaries',
	machine: 'console',
	judgement: 'judgement',
	voices: 'voices',
	'data-explorer': 'ledgers'
} as const satisfies Record<RouteId, string>;
