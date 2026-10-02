/** Drive the machine panel's four states through its real index requests. */
import type { Page } from '@playwright/test';

export type MachineRecordState = 'loading' | 'missing' | 'quiet' | 'unreachable';

export async function machineRecordState(page: Page, state: MachineRecordState): Promise<void> {
	await page.route('**/state/compact/host-fingerprint/index/*.json', async (route) => {
		if (state === 'loading') return;
		if (state === 'missing') {
			await route.fulfill({ status: 404, body: '' });
			return;
		}
		if (state === 'unreachable') {
			await route.abort('failed');
			return;
		}
		const response = await route.fetch();
		const index = await response.json();
		await route.fulfill({
			response,
			json: { ...index, entries: index.entries.map((entry: Record<string, unknown>) => ({ ...entry, rows: 0 })) }
		});
	});
}