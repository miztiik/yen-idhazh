/** Existing glyph identities name console destinations, never their health. */
import type { RouteId } from './band';

export const ROUTE_GLYPHS = {
	pipelines: 'shape-flow',
	model: 'docs',
	machine: 'console',
	judgement: 'shape-side-by-side',
	voices: 'topic-world',
	'data-explorer': 'ledgers'
} as const satisfies Record<RouteId, string>;
