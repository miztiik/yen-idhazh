import { ENCODER_DIMENSIONS, ENCODER_ID } from '../../src/lib/assist/encoder';
import { indexOf, type MonthIndex } from '../../src/lib/assist/month';
import type { SearchIndexEntry } from '../../src/lib/payload/types';

/**
 * A month search shard built in memory, in the shape the pipeline publishes.
 *
 * The search specs need real structure - a header the guard accepts, entries
 * over several days, byte offsets into one vector file - and not real
 * headlines. The committed archive gave them that once, but the archive
 * changes on every run and loses its oldest month to retention. A test that
 * reads it can fail with no code change.
 *
 * Each vector is pseudo-random int8 from a fixed seed. In 384 dimensions two
 * such vectors are close to orthogonal, so a story's own vector scores 1.0
 * against itself and every other story sits far below the 0.35 floor.
 */
export interface MonthShard {
	index: MonthIndex;
	vectors: Int8Array;
}

export function monthShard(month: string, days: number, perDay: number): MonthShard {
	const count = days * perDay;
	const vectors = new Int8Array(count * ENCODER_DIMENSIONS);
	let seed = 0x2545f491;
	for (let at = 0; at < vectors.length; at += 1) {
		seed = (Math.imul(seed, 1103515245) + 12345) >>> 0;
		vectors[at] = (seed >>> 16) % 255 - 127;
	}

	const entries: SearchIndexEntry[] = [];
	for (let day = 1; day <= days; day += 1) {
		for (let story = 1; story <= perDay; story += 1) {
			const position = entries.length;
			entries.push({
				date: `${month}-${String(day).padStart(2, '0')}`,
				item_id: `d${day}-s${story}`,
				title: `Story ${story} of day ${day}`,
				vertical: 'ai',
				vector: position * ENCODER_DIMENSIONS
			});
		}
	}

	const index = indexOf({
		month,
		model_id: ENCODER_ID,
		dimensions: ENCODER_DIMENSIONS,
		dtype: 'int8',
		scale: 1 / 127,
		entries
	});
	if (index === null) throw new Error(`the generated ${month} shard did not parse`);
	return { index, vectors };
}
