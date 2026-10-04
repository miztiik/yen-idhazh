import { expect, test } from '@playwright/test';

import { gapLines } from '../src/lib/console/explorer/gaps';

/**
 * What a data-explorer answer says about the days and files its ledgers are
 * missing. Pure: the browser case in `console-data-explorer.spec.ts` drives the
 * same lines through a served index and a real answer.
 */

test('each ledger says what it is missing, lost days first, in the order the ledgers were chosen', () => {
	expect(
		gapLines([
			{ ledger: 'item-health', lostDays: ['2026-08-18', '2026-08-19'], setAside: { '2026-08-20': 2 } },
			{ ledger: 'published', lostDays: [], setAside: { '2026-08': 1 } }
		])
	).toEqual([
		{
			kind: 'lost',
			ledger: 'item-health',
			text: 'There is no item-health record for 18 Aug to 19 Aug 2026, so nothing from those days is in this answer. The record for those days was lost and could not be recovered; they were not quiet days.'
		},
		{
			kind: 'set-aside',
			ledger: 'item-health',
			text: '2 item-health files were set aside unread when this data was packed, so this answer may be missing their rows. They wait in state/raw/item-health/set-aside/ for a person to read.'
		},
		{
			kind: 'set-aside',
			ledger: 'published',
			text: '1 published file was set aside unread when this data was packed, so this answer may be missing its rows. It waits in state/raw/published/set-aside/ for a person to read.'
		}
	]);
});

test('an answer whose ledgers miss nothing says nothing', () => {
	expect(gapLines([])).toEqual([]);
	expect(gapLines([{ ledger: 'seen', lostDays: [], setAside: {} }])).toEqual([]);
});
