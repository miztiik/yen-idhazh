/** How does a test show a console panel that sits behind a tab, the way a reader would? */

import { expect, type Page } from './browser';

/**
 * Press the tab that controls the panel `id` when the panel stands in a hidden tab panel, and
 * wait until it shows. A panel on no tab, or on the tab already open, is left as it is.
 */
export async function showPanel(page: Page, id: string): Promise<void> {
	const panel = page.locator(`[data-console-panel-id="${id}"]`);
	const hiddenTab = await panel.evaluate((node) => {
		const tabPanel = node.closest('[role="tabpanel"]');
		return tabPanel !== null && tabPanel.getClientRects().length === 0 ? tabPanel.id : null;
	});
	if (hiddenTab === null) return;
	await page.locator(`[role="tab"][aria-controls="${hiddenTab}"]`).click();
	await expect(panel).toBeVisible();
}