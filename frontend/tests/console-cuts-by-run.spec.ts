/** How many articles does each run count as read only in part, over item rows a test writes? */
import { expect, test } from '@playwright/test';
import { cutsByRun } from '../src/lib/server/cuts-by-run';

/** One item row: the run that wrote it, its address, and its length before and after the cap. */
function item(runId: string, address: Record<string, string>, before: string, after: string): Record<string, string> {
	return { run_id: runId, ...address, source_words_before_cap: before, source_words: after };
}

test('an article cut on two rows of one run is one article, and a run that cut nothing is not named', () => {
	const cuts = cutsByRun([
		// One address written twice by one run is one article.
		item('2030-06-15-1', { url_key: 'a' }, '5000', '2100'),
		item('2030-06-15-1', { url_key: 'a' }, '5000', '2100'),
		item('2030-06-15-1', { url_key: 'b' }, '3000', '2100'),
		// Read whole: as long after the cap as before it.
		item('2030-06-15-1', { url_key: 'c' }, '800', '800'),
		// A length nobody wrote down is no cut.
		item('2030-06-15-1', { url_key: 'd' }, '', '2100'),
		// The same article on a later run is that run's own cut.
		item('2030-06-15-2', { url_key: 'a' }, '5000', '2100'),
		// A row with no address is counted by its item.
		item('2030-06-15-2', { item_id: 'e' }, '4000', '2100'),
		item('2030-06-15-2', { item_id: 'e' }, '4000', '2100'),
		// A run whose every article was read whole.
		item('2030-06-15-3', { url_key: 'f' }, '900', '900')
	]);
	expect(cuts).toEqual(
		new Map([
			['2030-06-15-1', 2],
			['2030-06-15-2', 2]
		])
	);
});
