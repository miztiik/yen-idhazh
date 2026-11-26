/** Existing glyph identities name console destinations, never their health. */
import type { ConsoleDestinationId } from './console-destinations';
import type { IconId } from '../icons/generated';

export const ROUTE_GLYPHS = {
	pipelines: 'shape-flow',
	operations: 'operations',
	model: 'summaries',
	machine: 'console',
	judgement: 'judgement',
	voices: 'voices',
	'data-explorer': 'ledgers'
} as const satisfies Record<ConsoleDestinationId, IconId>;
