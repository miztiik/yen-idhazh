/** Search the archive on the reader's own device.
 *
 * The item vectors were computed on the runner and committed inside each day's
 * payload, so this file does two cheap things: decode base64 into unit vectors,
 * and take dot products. The only model work in the tab is embedding the query.
 *
 * There is no generative model anywhere near this. The worst failure mode is a
 * bad ranking, which a reader can see and judge, rather than a confident
 * falsehood, which they cannot.
 */

import type { DigestDay, DigestEmbeddings, DigestItem } from '$lib/payload/types';

export interface SearchHit {
	item: DigestItem;
	date: string;
	score: number;
}

/** base64 of int8 back to the unit vector the runner produced.
 *
 * Re-normalising after dequantisation matters: rounding to 255 levels shortens
 * the vector slightly, and an un-normalised vector makes the dot product a
 * function of magnitude as well as direction.
 */
export function decodeVector(encoded: string): number[] {
	const binary = atob(encoded);
	const values = new Array<number>(binary.length);
	let sum = 0;
	for (let index = 0; index < binary.length; index += 1) {
		const byte = binary.charCodeAt(index);
		const signed = (byte > 127 ? byte - 256 : byte) / 127;
		values[index] = signed;
		sum += signed * signed;
	}
	const length = Math.sqrt(sum) || 1;
	for (let index = 0; index < values.length; index += 1) values[index] /= length;
	return values;
}

/** Both sides are unit-length, so similarity is the dot product. */
export function cosine(left: number[], right: number[]): number {
	let total = 0;
	for (let index = 0; index < left.length; index += 1) total += left[index] * right[index];
	return total;
}

/** True when a day carries vectors this build knows how to read.
 *
 * The width check is not defensive clutter. A payload written by a future
 * encoder would otherwise be decoded against the wrong dimensionality and
 * produce plausible nonsense rather than an error.
 */
export function searchable(day: DigestDay, dimensions: number): boolean {
	const block: DigestEmbeddings | null = day.embeddings;
	return Boolean(block && block.dtype === 'int8' && block.dimensions === dimensions);
}

/** Rank items across every day that carries vectors. */
export function rank(
	days: DigestDay[],
	query: number[],
	options: { limit?: number; minScore?: number } = {}
): SearchHit[] {
	const limit = options.limit ?? 10;
	// Below this a result is noise wearing a number. Showing it would imply the
	// archive holds an answer it does not hold.
	const minScore = options.minScore ?? 0.2;

	const hits: SearchHit[] = [];
	for (const day of days) {
		if (!searchable(day, query.length)) continue;
		const vectors = day.embeddings!.vectors;
		for (const item of day.items) {
			const encoded = vectors[item.item_id];
			if (!encoded) continue;
			const score = cosine(query, decodeVector(encoded));
			if (score >= minScore) hits.push({ item, date: day.date, score });
		}
	}

	// Score, then most recent, then item id. The last key is what makes two
	// identical searches return identical lists.
	hits.sort(
		(left, right) =>
			right.score - left.score ||
			right.date.localeCompare(left.date) ||
			left.item.item_id.localeCompare(right.item.item_id)
	);
	return hits.slice(0, limit);
}
