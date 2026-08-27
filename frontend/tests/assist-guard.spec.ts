import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { ENCODER_DIMENSIONS, ENCODER_ID } from '../src/lib/assist/encoder';
import { indexOf, type MonthIndex } from '../src/lib/assist/index';
import { searchable } from '../src/lib/assist/search';

/**
 * The guard that decides whether a month may be searched at all.
 *
 * Both directions are tested and only one of them is obvious. Refusing a
 * foreign shard is the point of the guard. Accepting every committed one is
 * what stops the guard from switching search off for the whole archive - a
 * failure that is total, silent, and invisible to a type check, because a
 * stricter guard compiles exactly as well as a correct one.
 *
 * It guards the month index rather than the day payload, because that is what a
 * reader's tab reads now. The day payloads still carry their own embeddings
 * block; nothing in the browser opens it.
 *
 * Pure functions over the committed shards, so no page is loaded.
 */

const INDEX = resolve(process.cwd(), 'public', 'assist', 'index');

interface Committed {
	month: string;
	path: string;
	index: MonthIndex;
}

function committedMonths(): Committed[] {
	const found: Committed[] = [];
	for (const name of readdirSync(INDEX)) {
		if (!/^\d{4}-\d{2}\.json$/.test(name)) continue;
		const path = join(INDEX, name);
		const index = indexOf(JSON.parse(readFileSync(path, 'utf8')));
		expect(index, `${name} does not parse as a month index`).not.toBeNull();
		found.push({ month: name.slice(0, 7), path, index: index! });
	}
	expect(found.length, 'no committed month index to guard').toBeGreaterThan(0);
	return found;
}

test('every committed month is still searchable', () => {
	const refused = committedMonths()
		.filter(({ index }) => !searchable(index, ENCODER_DIMENSIONS))
		.map(({ path, index }) => `${path}: model_id=${index.model_id}`);

	expect(refused, 'the guard switches search off for these committed months').toEqual([]);
});

test('a shard from another encoder of the same shape is refused', () => {
	const { index } = committedMonths()[0]!;

	// The real shard passes, so the only difference below is the identifier.
	expect(searchable(index, ENCODER_DIMENSIONS)).toBe(true);

	const foreign: MonthIndex = { ...index, model_id: 'some-other-int8-encoder' };

	// Identical in every way the width-and-dtype check could see: same width,
	// same dtype, same offsets. It would decode perfectly and rank nonsense.
	expect(foreign.dimensions).toBe(index.dimensions);
	expect(foreign.dtype).toBe('int8');
	expect(foreign.model_id).not.toBe(ENCODER_ID);

	expect(searchable(foreign, ENCODER_DIMENSIONS)).toBe(false);
});

/**
 * The offsets and the file have to agree, or a reader ranks a slice of the
 * wrong story. The writer holds this on its own side; this is the reader's.
 */
test('every committed offset lands inside the vector file it names', () => {
	for (const { month, index } of committedMonths()) {
		const bin = join(INDEX, `${month}.bin`);
		const bytes = statSync(bin).size;
		const offsets = index.entries
			.map((entry) => entry.vector)
			.filter((offset): offset is number => offset !== null);

		expect(offsets.length, `${month} carries no vector at all`).toBeGreaterThan(0);
		expect(bytes, `${month}.bin is not a whole number of vectors`).toBe(
			offsets.length * index.dimensions
		);

		const last = Math.max(...offsets);
		expect(last + index.dimensions, `${month} names a vector past the end of its file`).toBeLessThanOrEqual(
			bytes
		);
	}
});
