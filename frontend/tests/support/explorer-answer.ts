import { expect, type Page } from '@playwright/test';
import { createRequire } from 'node:module';
import { readAsk, readAskCost } from '../../src/lib/data/ask-reader';
import { nodeEngine } from '../../src/lib/data/engine';
import { fetchedBytes } from '../../src/lib/data/fetched-bytes';
import { pageKeeper } from '../../src/lib/data/page-keeper';
import { engineExtensionRepository } from '../../src/lib/server/config';
import type { AskOptions, AskResult, DateStamp, LedgerName, SpanCost } from '../../src/lib/data/ledger';

export const EXPLORER_CANARY_DAY = '2026-08-20';
const resolver = createRequire(import.meta.url);
const locate = (specifier: string): string => resolver.resolve(specifier);

export async function openExplorer(page: Page, waitReady = true) {
	await page.clock.setFixedTime(`${EXPLORER_CANARY_DAY}T12:00:00Z`);
	await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toBeVisible();
	await expect(page.locator('[data-ledger-name]').first()).toBeVisible();
	if (waitReady) await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
}

export async function runExplorer(page: Page) {
	await page.getByRole('button', { name: /^Run$/ }).click();
	await page.locator('[data-console-panel-id="data-explorer-rows"] [data-explorer-answer], [data-console-panel-id="data-explorer-rows"] [data-state]').first().waitFor({ timeout: 60_000 });
}

export async function chooseExplorerQuestion(page: Page, ledgers: readonly LedgerName[], sql: string) {
	while (await page.locator('[data-ledger-name] input:checked').count() > 0) {
		await page.locator('[data-ledger-name] input:checked').first().click();
	}
	for (const ledger of ledgers) {
		await page.locator(`[data-ledger-name="${ledger}"] input`).check();
	}
	await page.locator('#explorer-sql').fill(sql);
	if (ledgers.length > 0) {
		await expect(page.locator('[data-explorer-columns]')).toContainText(`${ledgers[ledgers.length - 1]}.`, { timeout: 60_000 });
	}
	await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
}

export async function tableRows(page: Page): Promise<string[][]> {
	return page.locator('[data-explorer-answer] tbody tr').evaluateAll((rows) =>
		rows.map((row) => Array.from(row.querySelectorAll('td'), (cell) => (cell.textContent ?? '').trim()))
	);
}

export async function expectedAsk(page: Page, options: AskOptions): Promise<AskResult> {
	const origin = new URL(page.url()).origin;
	const keeper = pageKeeper(
		fetchedBytes(origin, (url, init) => fetch(url, init)),
		() => nodeEngine(locate, engineExtensionRepository())
	);
	try {
		return await readAsk(keeper, options, {});
	} finally {
		await keeper.release();
	}
}

export async function expectedAskCost(page: Page, ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost> {
	const origin = new URL(page.url()).origin;
	const keeper = pageKeeper(
		fetchedBytes(origin, (url, init) => fetch(url, init)),
		() => nodeEngine(locate, engineExtensionRepository())
	);
	try {
		return await readAskCost(keeper, ledgers, from, to, {});
	} finally {
		await keeper.release();
	}
}
