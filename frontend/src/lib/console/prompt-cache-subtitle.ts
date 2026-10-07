/** The subtitle over the prompt-cache figures, for one window.
 *
 * The panel below this sentence prints how many items had nothing in memory
 * at all - `readWhole` out of `counted` - so a subtitle claiming every
 * article's instructions carry over is false whenever that count is above
 * zero. This function says only what the window's own figures show. The
 * words are Reader's. The span's own words come from `span-words.ts`, like
 * every windowed sentence's. The readings behind the figures are in
 * `docs/architecture/publishing/what-the-pipelines-route-draws.md`.
 */

import { grouped } from '../charts/series';
import type { ItemCost } from './item-cost';
import { nameSpan } from './span-words';

/** The subtitle for one window. Assumes `counted` is above zero - the page
 * prints a different sentence in full when no item recorded a token count.
 * A one-item window takes its own sentences (Reader, 2026-10-07): a bare
 * count next to "items" is wrong English when there is only one, the same
 * fault row L17 removed from every windowed day count. */
export function describePromptCacheSubtitle({
	days,
	counted,
	readWhole
}: Pick<ItemCost, 'days' | 'counted' | 'readWhole'>): string {
	const span = nameSpan(days);
	if (counted === 1) {
		return readWhole === 0
			? `Over ${span}, the one item reused part of an earlier prompt - it did not start from scratch.`
			: `Over ${span}, the one item had to read its prompt whole, with nothing saved from before.`;
	}
	if (readWhole === 0) {
		return `Over ${span}, every one of the ${grouped(counted)} items reused part of an earlier prompt - none had to start from scratch.`;
	}
	if (readWhole === counted) {
		return `Over ${span}, all ${grouped(counted)} items had to read their prompts whole, with nothing saved from before.`;
	}
	const pronoun = readWhole === 1 ? 'its prompt' : 'their prompts';
	return `Over ${span}, ${grouped(readWhole)} of ${grouped(counted)} items had to read ${pronoun} whole, with nothing saved from before. The rest reused part of an earlier prompt instead.`;
}
