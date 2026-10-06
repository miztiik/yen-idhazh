/**
 * How does a browser test drive the Data explorer, on a day it pins and over data it serves?
 *
 * `openExplorer` pins the UTC day its caller names and opens the page. `serveBuilt` builds each
 * ledger a test names and serves it to the page, so an answer reads what that test built and
 * nothing the canary holds. Nothing here works out an expected answer: a test writes its
 * expected values out from what it built.
 */

import { expect, type BrowserContext, type Page } from '@playwright/test';
import type { DateStamp, LedgerName } from '../../src/lib/data/ledger';
import { buildLedger, serveToPage, type BuiltLedger } from './ledger-lifecycle';

/** What the answer panel shows after a run: `table` for an answer with rows, or the state it names. */
export type AnswerState = 'table' | 'quiet' | 'missing' | 'unreachable' | 'refused';

/** Pin `day` as the page's UTC today and open the Data explorer, at `address`, a query string such
 *  as a shared link carries, when one is given. Waits for Run to be ready unless `ready` is false. */
export async function openExplorer(page: Page, day: DateStamp, options: { address?: string; ready?: boolean } = {}) {
	await page.clock.setFixedTime(`${day}T12:00:00Z`);
	await page.goto(`/console/data-explorer/${options.address ?? ''}`, { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toBeVisible();
	await expect(page.locator('[data-workbench-region="ledgers"]')).toBeVisible();
	await expect.poll(() => page.locator('[data-ledger-name]').count()).toBeGreaterThan(0);
	if (options.ready ?? true) await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
}

/** Build each ledger under `root` and serve it to every page of `context`. */
export async function serveBuilt(context: BrowserContext, root: string, ...ledgers: readonly BuiltLedger[]): Promise<void> {
	for (const built of ledgers) {
		await buildLedger(root, built);
		await serveToPage(context, root, built.ledger);
	}
}

export async function runExplorer(page: Page) {
	await page.getByRole('button', { name: /^Run$/ }).click();
	await page.waitForFunction(() => {
		const panel = document.querySelector('[data-console-panel-id="data-explorer-rows"]');
		const state = panel?.querySelector('[data-state]')?.getAttribute('data-state');
		return panel?.querySelector('[data-explorer-answer]') !== null || (state !== null && state !== undefined && state !== 'loading');
	}, undefined, { timeout: 60_000 });
}

/** Fail unless the answer panel shows `state`, so the checks after it read the answer they need. */
export async function expectAnswer(page: Page, state: AnswerState) {
	const panel = page.locator('[data-console-panel-id="data-explorer-rows"]');
	const shown = state === 'table' ? panel.locator('[data-explorer-answer]') : panel.locator(`[data-state="${state}"]`);
	await expect(shown, `the answer is not ${state}`).toHaveCount(1);
}

export async function chooseExplorerQuestion(page: Page, ledgers: readonly LedgerName[], sql: string, waitForColumns = true) {
	const ensureLedgersOpen = async () => {
		const firstLedger = page.locator('[data-ledger-name]').first();
		if (await firstLedger.count() > 0 && !(await firstLedger.isVisible())) {
			await page.locator('[data-workbench-region="ledgers"] summary').click();
		}
	};
	await ensureLedgersOpen();
	while (await page.locator('[data-ledger-name] input:checked').count() > 0) {
		await page.locator('[data-ledger-name] input:checked').first().click();
	}
	await ensureLedgersOpen();
	for (const ledger of ledgers) {
		await page.locator(`[data-ledger-name="${ledger}"] input`).check();
	}
	await page.locator('#explorer-sql').fill(sql);
	if (ledgers.length > 0 && waitForColumns) {
		await expect(page.locator('[data-explorer-columns]')).toContainText(`${ledgers[ledgers.length - 1]}.`, { timeout: 60_000 });
	}
	await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
}

export async function tableRows(page: Page): Promise<string[][]> {
	return page.locator('[data-explorer-answer] tbody tr').evaluateAll((rows) =>
		rows.map((row) => Array.from(row.querySelectorAll('td'), (cell) => (cell.textContent ?? '').trim()))
	);
}
