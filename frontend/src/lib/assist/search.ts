/** Search the archive on the reader's own device.
 *
 * The item vectors were computed on the runner and committed as one raw int8
 * file a month, so this file does two cheap things: read a slice of that file
 * back into a unit vector, and take dot products. The only model work in the
 * tab is embedding the query.
 *
 * **It ranks over the month index, not over day payloads.** The archive used to
 * carry every committed day whole so this module could reach the vectors inside
 * them, which put 1.7 MB gzipped on a page a reader opens to find one story.
 * The index carries the same vectors for a fraction of the bytes, and an entry
 * names the day a result came from - so a result is rendered from the day it
 * names, fetched only when it is on screen.
 *
 * There is no generative model anywhere near this. The worst failure mode is a
 * bad ranking, which a reader can see and judge, rather than a confident
 * falsehood, which they cannot.
 */

import type { MonthIndex } from './month';
import type { SearchIndexEntry } from '$lib/payload/types';
import { ENCODER_ID } from './encoder';

/** One month with its vectors in hand. Both halves, or the month is not searched. */
export interface SearchableMonth {
	index: MonthIndex;
	vectors: Int8Array;
}

export interface SearchHit {
	entry: SearchIndexEntry;
	score: number;
}

/** One stored vector back to the unit vector the runner produced, or null.
 *
 * The scale comes from the shard's own header rather than from a constant here.
 * The index projects bytes that are already int8, so it cannot tighten the
 * quantisation - but the encoder can, and when it does the header changes and
 * this decoder follows it. A hardcoded 127 would keep decoding and start
 * lying.
 *
 * Re-normalising after dequantisation matters: rounding to 255 levels shortens
 * the vector slightly, and an un-normalised vector makes the dot product a
 * function of magnitude as well as direction.
 *
 * Null when the file is shorter than the offset claims. A truncated download
 * has to drop a result, never rank half a vector.
 */
export function decodeVectorAt(
	bytes: Int8Array,
	offset: number,
	dimensions: number,
	scale: number
): number[] | null {
	if (offset < 0 || offset + dimensions > bytes.length) return null;
	const values = new Array<number>(dimensions);
	let sum = 0;
	for (let index = 0; index < dimensions; index += 1) {
		const signed = bytes[offset + index]! * scale;
		values[index] = signed;
		sum += signed * signed;
	}
	const length = Math.sqrt(sum) || 1;
	for (let index = 0; index < dimensions; index += 1) values[index] /= length;
	return values;
}

/** Both sides are unit-length, so similarity is the dot product. */
export function cosine(left: number[], right: number[]): number {
	let total = 0;
	for (let index = 0; index < left.length; index += 1) total += left[index]! * right[index]!;
	return total;
}

/** True when a month carries vectors this build knows how to read.
 *
 * Three checks, and only two of them are about decoding. The width and the
 * dtype catch a shard this decoder would misread, and a wrong answer there is
 * loud. The identifier catches the shard it would decode perfectly and still
 * get wrong: another encoder of the same width and dtype produces vectors of
 * exactly the right shape in a different space, so every dot product is
 * meaningless and every score still looks like a score.
 */
export function searchable(index: MonthIndex, dimensions: number): boolean {
	return (
		index.model_id === ENCODER_ID && index.dtype === 'int8' && index.dimensions === dimensions
	);
}

/** How the archive is searched. All three values come from `config/idhazh.json`.
 *
 * They were literals here with no override path, which is what Rule #6 forbids.
 * The floor in particular is a measured quantity - see `assist.similarity_floor`
 * in the contract for the null distribution it was cut from.
 */
export interface RankOptions {
	/** How many results the flat list shows. */
	limit: number;
	/** Below this a result is noise wearing a number. A selector, never a grade. */
	minScore: number;
}

/** Rank the entries of every month whose vectors are in hand.
 *
 * An entry with no vector is skipped rather than scored. Two of the 2,237
 * committed items are in that state, and the token-budget work adds more on
 * purpose: they browse, and they are not searchable.
 */
export function rank(
	months: SearchableMonth[],
	query: number[],
	options: RankOptions
): SearchHit[] {
	const { limit, minScore } = options;

	const hits: SearchHit[] = [];
	for (const { index, vectors } of months) {
		if (!searchable(index, query.length)) continue;
		for (const entry of index.entries) {
			if (entry.vector === null || entry.vector === undefined) continue;
			const vector = decodeVectorAt(vectors, entry.vector, index.dimensions, index.scale);
			if (vector === null) continue;
			const score = cosine(query, vector);
			if (score >= minScore) hits.push({ entry, score });
		}
	}

	// Score, then most recent, then item id. The last key is what makes two
	// identical searches return identical lists.
	hits.sort(
		(left, right) =>
			right.score - left.score ||
			right.entry.date.localeCompare(left.entry.date) ||
			left.entry.item_id.localeCompare(right.entry.item_id)
	);
	return hits.slice(0, limit);
}
