import { expect, test } from '@playwright/test';

import { groupColumns } from '../src/lib/console/explorer/column-groups';
import { configuredCatalog } from '../src/lib/data/configured-catalog';

/**
 * How the column rail groups names under their ledger. The page names a
 * ledger's column `{ledger}.{column}` and an answer's column by its own name;
 * these rules keep that grouping deterministic.
 */

test('a ledger\'s columns group under it in the order they came, shown without the prefix', () => {
	expect(groupColumns(configuredCatalog, [
		{ name: 'item-health.version', type: 'VARCHAR' },
		{ name: 'item-health.source_words_before_cap', type: 'BIGINT' },
		{ name: 'published.covers', type: 'DATE' },
		{ name: 'published.a.b', type: 'VARCHAR' }
	])).toEqual([
		{ ledger: 'item-health', columns: [
			{ name: 'item-health.version', type: 'VARCHAR', shown: 'version' },
			{ name: 'item-health.source_words_before_cap', type: 'BIGINT', shown: 'source_words_before_cap' }
		] },
		{ ledger: 'published', columns: [
			{ name: 'published.covers', type: 'DATE', shown: 'covers' },
			{ name: 'published.a.b', type: 'VARCHAR', shown: 'a.b' }
		] }
	]);
});

test('an answer\'s columns stand in one group with no ledger, names whole', () => {
	expect(groupColumns(configuredCatalog, [
		{ name: 'stage', type: 'VARCHAR' },
		{ name: 'count_star()', type: 'BIGINT' },
		{ name: 'not-a-ledger.x', type: 'DOUBLE' },
		{ name: '.x', type: 'DOUBLE' }
	])).toEqual([
		{ ledger: null, columns: [
			{ name: 'stage', type: 'VARCHAR', shown: 'stage' },
			{ name: 'count_star()', type: 'BIGINT', shown: 'count_star()' },
			{ name: 'not-a-ledger.x', type: 'DOUBLE', shown: 'not-a-ledger.x' },
			{ name: '.x', type: 'DOUBLE', shown: '.x' }
		] }
	]);
});

test('only neighbours share a group, and nothing is sorted', () => {
	const groups = groupColumns(configuredCatalog, [
		{ name: 'seen.b', type: 'VARCHAR' },
		{ name: 'answer', type: 'VARCHAR' },
		{ name: 'seen.a', type: 'VARCHAR' }
	]);
	expect(groups.map((group) => [group.ledger, group.columns.map((column) => column.shown)])).toEqual([
		['seen', ['b']],
		[null, ['answer']],
		['seen', ['a']]
	]);
	expect(groupColumns(configuredCatalog, [])).toEqual([]);
});
