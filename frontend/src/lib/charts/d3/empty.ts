/** How a chart with nothing to draw is drawn, in the words the console already uses.
 *
 * The words are not minted here. `waiting.ts` owns every nothing a console
 * panel can be in and the sentence each one prints, and this module re-exports
 * them. What it adds is only the drawing: a wait is the reserved box with its
 * shimmer and no words; every other nothing is a box of the chart's own height
 * that says which nothing it is; and only a failure takes a hue.
 *
 * **A nothing that says nothing is refused.** Every state but a wait needs its
 * sentence, and the type says so, because an empty frame with no words is the
 * one picture where a quiet pipeline and a broken fetch look the same.
 */
import type { ChartState } from '../../console/waiting';

export {
	missingSentence,
	refusedSentence,
	quietSentence,
	retryLabel,
	tooFewSentence,
	unreachableSentence,
	type ChartState,
	type PanelState
} from '../../console/waiting';

/** Every state a chart can be in when it has nothing to draw. */
export type EmptyKind = Exclude<ChartState, 'ready'>;

export interface EmptyDrawing {
	kind: EmptyKind;
	/** The reserved box with its sweep. Only a wait. */
	shimmer: boolean;
	/** Warn only where something failed. */
	tone: 'neutral' | 'warn';
	/** What the box says. Null only for a wait: a panel with rows on the way
	 * that printed "nothing" would be wrong in a second. */
	sentence: string | null;
}

export function emptyState(kind: 'loading'): EmptyDrawing;
export function emptyState(kind: Exclude<EmptyKind, 'loading'>, sentence: string): EmptyDrawing;
export function emptyState(kind: EmptyKind, sentence?: string): EmptyDrawing {
	if (kind === 'loading') return { kind, shimmer: true, tone: 'neutral', sentence: null };
	if (sentence === undefined || sentence.trim() === '') {
		throw new Error(`A chart that is ${kind} says so in words; it was given no sentence.`);
	}
	return { kind, shimmer: false, tone: kind === 'unreachable' ? 'warn' : 'neutral', sentence };
}
