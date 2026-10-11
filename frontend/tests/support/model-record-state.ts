/** Drive all declared Summaries doors with actual quiet indexes or failed transport. */
import type { Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { buildRows, serveToPage } from './ledger-lifecycle';

export async function modelRecordState(page: Page, state: 'loading' | 'missing' | 'quiet' | 'unreachable') {
	if (state === 'quiet') {
		const root = resolve('..', 'backend', 'var', 'model-gates', randomUUID());
		mkdirSync(root, { recursive: true });
		for (const ledger of ['item-health', 'summary-quality-evals'] as const) {
			await buildRows(root, ledger, [{ covers: '2026-08-20', rows: [] }]);
			await serveToPage(page.context(), root, ledger);
		}
		return;
	}
	await page.route('**/state/compact/*/index/*.json', async (route) => {
		if (state === 'loading') return;
		if (state === 'missing') await route.fulfill({ status: 404, body: '' });
		else await route.abort('failed');
	});
}
