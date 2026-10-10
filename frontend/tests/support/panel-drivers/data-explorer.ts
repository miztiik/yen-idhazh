/** How is one Data explorer answer put into each nothing for both of its panels? */

import { expect } from '../browser';
import { chooseExplorerQuestion, runExplorer } from '../explorer-answer';
import type { Driver, Nothing } from '../panel-gates';

const PINNED = '2026-08-20';

const driverFor = (state: Nothing): Driver => async (page) => {
	await page.clock.setFixedTime(`${PINNED}T12:00:00Z`);
	if (state === 'unreachable') await page.route('**/state/**/*.parquet*', (route) => route.abort());
	let release: (() => void) | undefined;
	return {
		afterOpen: async () => {
			await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toBeVisible();
			await expect(page.locator('[data-workbench-region="ledgers"]')).toBeVisible();
			await expect.poll(() => page.locator('[data-ledger-name]').count()).toBeGreaterThan(0);
			await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
			if (state === 'loading') {
				const held = new Promise<void>((resolve) => { release = resolve; });
				await page.route('**/state/**/*.parquet*', async (route) => {
					await held;
					await route.continue();
				});
				await chooseExplorerQuestion(page, ['published'], 'SELECT count(*) AS rows FROM "published"', false);
				await page.getByRole('button', { name: /^Run$/ }).click();
				return;
			}
			const sql =
				state === 'quiet' ? 'SELECT * FROM "published" WHERE false' :
				state === 'missing' ? 'SELECT count(*) AS rows FROM "feed-health"' :
				state === 'refused' ? 'SELECT 1; SELECT 2' :
				'SELECT count(*) AS rows FROM "published"';
			const ledgers = state === 'missing' ? (['feed-health'] as const) : (['published'] as const);
			await chooseExplorerQuestion(page, ledgers, sql, false);
			await runExplorer(page);
		},
		afterRead: async () => { release?.(); }
	};
};

// Both panels show one answer, so a route load drives that answer once.
const answer: Readonly<Record<Nothing, Driver>> = {
	loading: driverFor('loading'),
	quiet: driverFor('quiet'),
	missing: driverFor('missing'),
	unreachable: driverFor('unreachable'),
	refused: driverFor('refused')
};

export const DRIVERS: Readonly<Record<string, Readonly<Record<Nothing, Driver>>>> = {
	'data-explorer-rows': answer,
	'data-explorer-shape': answer
};

export const BUILD_TIME: readonly string[] = [];
