import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { ENCODER_DIMENSIONS, ENCODER_ID } from '../src/lib/assist/encoder';
import { searchable } from '../src/lib/assist/search';
import type { DigestDay } from '../src/lib/payload/types';

/**
 * The guard that decides whether a day may be searched at all.
 *
 * Both directions are tested and only one of them is obvious. Refusing a
 * foreign payload is the point of the guard. Accepting every committed one is
 * what stops the guard from switching search off for the whole archive - a
 * failure that is total, silent, and invisible to a type check, because a
 * stricter guard compiles exactly as well as a correct one.
 *
 * Pure functions over the committed payloads, so no page is loaded.
 */

const PUBLISHED = resolve(process.cwd(), 'public', 'digest');

interface Committed {
	path: string;
	day: DigestDay;
}

function committedDays(): Committed[] {
	const found: Committed[] = [];
	const walk = (at: string): void => {
		for (const entry of readdirSync(at, { withFileTypes: true })) {
			const next = join(at, entry.name);
			if (entry.isDirectory()) walk(next);
			else if (entry.name === 'digest.json')
				found.push({ path: next, day: JSON.parse(readFileSync(next, 'utf8')) as DigestDay });
		}
	};
	walk(PUBLISHED);
	return found;
}

function daysCarryingVectors(): Committed[] {
	const carrying = committedDays().filter(({ day }) => Boolean(day.embeddings));
	expect(carrying.length, 'no committed day carries an embeddings block').toBeGreaterThan(0);
	return carrying;
}

test('every committed day that carries vectors is still searchable', () => {
	const refused = daysCarryingVectors()
		.filter(({ day }) => !searchable(day, ENCODER_DIMENSIONS))
		.map(({ path, day }) => `${path}: model_id=${day.embeddings?.model_id}`);

	expect(refused, 'the guard switches search off for these committed days').toEqual([]);
});

test('a payload from another encoder of the same shape is refused', () => {
	const { day } = daysCarryingVectors()[0];
	const block = day.embeddings!;

	// The real day passes, so the only difference below is the identifier.
	expect(searchable(day, ENCODER_DIMENSIONS)).toBe(true);

	const foreign: DigestDay = {
		...day,
		embeddings: { ...block, model_id: 'some-other-int8-encoder' }
	};

	// Identical in every way the old guard could see: same width, same dtype,
	// same vectors. It passed, and it ranked them.
	expect(foreign.embeddings!.dimensions).toBe(block.dimensions);
	expect(foreign.embeddings!.dtype).toBe('int8');
	expect(foreign.embeddings!.model_id).not.toBe(ENCODER_ID);

	expect(searchable(foreign, ENCODER_DIMENSIONS)).toBe(false);
});
