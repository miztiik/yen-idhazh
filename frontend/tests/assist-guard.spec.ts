import { expect, test } from '@playwright/test';
import { ENCODER_DIMENSIONS, ENCODER_ID } from '../src/lib/assist/encoder';
import type { MonthIndex } from '../src/lib/assist/month';
import { searchable } from '../src/lib/assist/search';
import { monthShard } from './support/month-shard';

/**
 * The guard that decides whether a month may be searched at all.
 *
 * Both directions are tested. Refusing a foreign shard is the point of the
 * guard. Accepting a shard this build wrote is what stops the guard from
 * switching search off for the whole archive - a failure that is total, silent,
 * and invisible to a type check, because a stricter guard compiles exactly as
 * well as a correct one.
 *
 * The shard is generated (`support/month-shard.ts`), never read from the
 * committed archive. Whether the runner and the browser name the same encoder
 * is held by `backend/tests/test_embed.py`, which reads `encoder.ts`; whether
 * the offsets fit the vector file is held on the writer's side.
 */

test('a shard from another encoder of the same shape is refused', () => {
	const { index } = monthShard('2026-08', 1, 1);

	// The shard this build wrote passes, so the only difference below is the identifier.
	expect(searchable(index, ENCODER_DIMENSIONS)).toBe(true);

	const foreign: MonthIndex = { ...index, model_id: 'some-other-int8-encoder' };

	// Identical in every way the width-and-dtype check could see: same width,
	// same dtype, same offsets. It would decode perfectly and rank nonsense.
	expect(foreign.dimensions).toBe(index.dimensions);
	expect(foreign.dtype).toBe('int8');
	expect(foreign.model_id).not.toBe(ENCODER_ID);

	expect(searchable(foreign, ENCODER_DIMENSIONS)).toBe(false);
});
