/** The grid reader accepts only its real, source-backed fixture. */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import {
	isWhowhatGridData,
	publishedWhowhatGrid,
	refusedWhowhatGridData,
	WHOWHAT_GRID_MAX_ROWS,
	WHOWHAT_GRID_VERSION,
	WHOWHAT_SOURCE_SPAN_MAX
} from '../src/lib/payload/whowhat-grid';
import { whowhatVisualState } from '../src/lib/visual/whowhat-state';
import type { WhowhatGridData } from '../src/lib/payload/types';

const fixtureRoot = join(process.cwd(), '..', 'tests', 'fixtures');
const itemId = 'ai-17';

function gridFixture(): WhowhatGridData {
	return JSON.parse(
		readFileSync(join(fixtureRoot, 'contracts', 'whowhat-grid', 'whowhat.json'), 'utf8')
	) as WhowhatGridData;
}

test('the real grid fixture is versioned, rectangular and re-slices both cells', () => {
	const grid = gridFixture();
	const article = readFileSync(
		join(fixtureRoot, 'visual-validator', 'articles', 'whowhat.txt'),
		'utf8'
	).trim();

	expect(grid.version).toBe(WHOWHAT_GRID_VERSION);
	expect(isWhowhatGridData(grid, itemId)).toBe(true);
	expect(grid.rows.length).toBeLessThanOrEqual(WHOWHAT_GRID_MAX_ROWS);
	expect(grid.rows.some((row) => row.actor === null && row.claim === null)).toBe(true);
	for (const row of grid.rows) {
		expect(row.actor === null).toBe(row.claim === null);
		if (!row.actor || !row.claim) continue;
		expect(row.actor.sentence_index).toBe(row.claim.sentence_index);
		expect(article.slice(row.actor.span_start, row.actor.span_end)).toBe(row.actor.span_excerpt);
		expect(article.slice(row.claim.span_start, row.claim.span_end)).toBe(row.claim.span_excerpt);
		expect(row.actor.display_text).toBe(row.actor.span_excerpt);
		if (row.claim.display_text !== row.claim.span_excerpt) {
			expect(row.claim.display_text.endsWith('...')).toBe(true);
			expect(row.claim.span_excerpt.startsWith(row.claim.display_text.slice(0, -3))).toBe(true);
		}
		for (const span of [row.actor, row.claim]) {
			expect(Array.from(span.span_excerpt).length).toBeLessThanOrEqual(
				WHOWHAT_SOURCE_SPAN_MAX
			);
		}
	}
});

test('the reader rejects invented actor or claim display text', () => {
	const valid = gridFixture();
	for (const cell of ['actor', 'claim'] as const) {
		const invented = structuredClone(valid);
		const row = invented.rows[0]!;
		const span = row[cell];
		if (!span) throw new Error(`fixture row has no ${cell} span`);
		span.display_text = 'invented text...';
		expect(refusedWhowhatGridData(invented, itemId)).toContain('invalid rectangular rows');
	}
});

test('the grid reader refuses a partial pair, cross-sentence pair and foreign item', () => {
	const valid = gridFixture();
	const partial = structuredClone(valid);
	partial.rows[0].claim = null;
	expect(refusedWhowhatGridData(partial, itemId)).toContain('rectangular');

	const crossSentence = structuredClone(valid);
	const pair = crossSentence.rows.find((row) => row.actor && row.claim)!;
	pair.claim!.sentence_index += 1;
	expect(refusedWhowhatGridData(crossSentence, itemId)).toContain('rectangular');

	expect(refusedWhowhatGridData(valid, 'ai-18')).toContain('another item');
});

test('the grid reader refuses row objects with a missing cell key', () => {
	const valid = gridFixture();
	const missingActor: unknown = {
		...valid,
		rows: valid.rows.map((row, index) =>
			index === 0 ? { claim: row.claim } : row
		)
	};
	const missingClaim: unknown = {
		...valid,
		rows: valid.rows.map((row, index) =>
			index === 0 ? { actor: row.actor } : row
		)
	};

	expect(refusedWhowhatGridData(missingActor, itemId)).toContain('rectangular');
	expect(refusedWhowhatGridData(missingClaim, itemId)).toContain('rectangular');
});

test('the grid reader refuses unknown versions, bad offsets and grids without a pair', () => {
	const valid = gridFixture();
	const unknownVersion = structuredClone(valid);
	unknownVersion.version = '2099-01-01';
	expect(refusedWhowhatGridData(unknownVersion, itemId)).toContain('unknown grid contract');

	const badOffsets = structuredClone(valid);
	const pair = badOffsets.rows.find((row) => row.actor && row.claim)!;
	pair.actor!.span_end += 1;
	expect(refusedWhowhatGridData(badOffsets, itemId)).toContain('rectangular');

	const noPair = structuredClone(valid);
	for (const row of noPair.rows) {
		row.actor = null;
		row.claim = null;
	}
	expect(refusedWhowhatGridData(noPair, itemId)).toContain('no source-backed');
});

test('the browser accepts only the current published item path for the grid', () => {
	expect(publishedWhowhatGrid('digest/2026/10/28/ai-17.json', itemId)).toBe(true);
	expect(publishedWhowhatGrid('https://example.test/ai-17.json', itemId)).toBe(false);
	expect(publishedWhowhatGrid('../ai-17.json', itemId)).toBe(false);
	expect(publishedWhowhatGrid('digest/2026/10/28/ai-18.json', itemId)).toBe(false);
});

test('a failed grid request exposes retry state until the reader starts again', () => {
	const file = 'digest/2026/10/28/ai-17.json';

	expect(whowhatVisualState(file, file, { file, data: null })).toBe('failed');
	expect(whowhatVisualState(file, null, null)).toBe('loading');
	expect(whowhatVisualState(null, null, null)).toBe('idle');
});

test('the grid component exposes the failed state with a keyboard-accessible retry', () => {
	const source = readFileSync(
		join(process.cwd(), 'src', 'lib', 'visual', 'WhowhatVisual.svelte'),
		'utf8'
	);

	expect(source).toContain('data-whowhat-state={gridState}');
	expect(source).toContain("gridState === 'failed'");
	expect(source).toContain('role="status"');
	expect(source).toContain('aria-live="polite"');
	expect(source).toContain('onclick={retry}');
	expect(source).toContain('focus-visible:outline');
	expect(source).toContain('Try again');
	expect(source).toContain("{row.actor?.display_text ?? ''}");
	expect(source).toContain("{row.claim?.display_text ?? ''}");
});
