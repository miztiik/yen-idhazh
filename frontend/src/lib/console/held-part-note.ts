/** What the note under the prompt-cache share says, for one window.
 *
 * The share is printed and never drawn as a line over time, because a longer
 * article lowers it while the part of the prompt already in memory stays put.
 * That reason holds only while that part stays put, so the note checks it on
 * the two figures it prints: the middle item's count and the most any item had.
 * Where the most is twice the middle or more, the note says the amount changed
 * a lot, and that a lower share can then mean less in memory. Where it is under
 * twice the middle, the note states the two figures and claims nothing about
 * change: a window can pass on those two while some of its days held far less.
 *
 * The words are fixed - Reader and Jony chose them - and only the span and the
 * two counts inside them are computed. The readings behind the rule are in
 * `docs/architecture/publishing/what-the-pipelines-route-draws.md`.
 */

import { spanWords } from '../charts/fleet';
import { grouped } from '../charts/series';
import type { ItemCost } from './item-cost';

/** The note for one window, or null where no item had anything in memory.
 *
 * Null where every item read its prompt whole: the share is then 0 percent at
 * any article length, so there is nothing to explain, and the figures above it
 * already say that every item was read whole. Null as well where no item
 * recorded a count, because a note that names two figures prints only when it
 * has them.
 */
export function describeHeldPart({
	days,
	reusedMedian: middle,
	reusedWidest: largest
}: Pick<ItemCost, 'days' | 'reusedMedian' | 'reusedWidest'>): string | null {
	if (middle === null || largest === null || largest === 0) return null;
	const span = spanWords(days);
	if (largest - middle < middle) {
		return `In ${span}, the middle item had ${grouped(middle)} tokens already in memory, and the most any item had was ${grouped(largest)} tokens. A longer article makes the percentage lower, even if the amount in memory does not change. Read the token counts, not the rise or fall of the percentages.`;
	}
	return `In ${span}, the amount already in memory changed a lot. The middle item had ${grouped(middle)} tokens in memory, and the most any item had was ${grouped(largest)} tokens. So here a lower percentage can mean less in memory, not only a longer article. Read the token counts, not the rise or fall of the percentages.`;
}
