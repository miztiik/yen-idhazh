import { expect, test } from './support/browser';

test('Voices keeps its failures-only preview usable without article rows or JavaScript', async ({ page, browser }) => {
	await page.goto('/console/voices/');
	const failures = page.locator('[data-console-panel-id="feeds-failed"]');
	await expect(failures.getByRole('heading', { name: 'Feed failures', exact: true })).toBeVisible();
	await expect(failures.getByText('No article fetches were recorded in this span; showing feed reads only.')).toBeVisible();
	const preview = failures.locator('[data-feed-preview="read"]');
	await expect(preview.locator('[data-lede]')).toHaveText('3 of 4 checked feeds failed at least once.');
	await expect(preview.locator('[data-feed-preview-coverage]')).toContainText('recorded on 2 of 14 days');
	await expect(preview).toContainText('7 Aug 2026 to 20 Aug 2026 UTC');

	await page.locator('[data-window-preset="90"]').click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '90');
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
	await expect(preview.locator('[data-feed-preview-coverage]')).toContainText('recorded on 2 of 90 days');

	const scriptless = await browser.newContext({ javaScriptEnabled: false });
	try {
		const fallback = await scriptless.newPage();
		await fallback.goto(page.url());
		const panel = fallback.locator('[data-console-panel-id="feeds-failed"]');
		await expect(panel.getByRole('heading', { name: 'Feed failures', exact: true })).toBeVisible();
		const scriptlessPreview = panel.locator('[data-feed-preview="read"]');
		await expect(scriptlessPreview.locator('[data-lede]')).toHaveText('3 of 4 checked feeds failed at least once.');
		await expect(scriptlessPreview.locator('[data-feed-row] strong')).toHaveText(['canary-flaky', 'canary-empty', 'canary-gone']);
		await expect(scriptlessPreview.locator('[data-feed-row="canary-empty"]')).toContainText('2 of 3 recorded reads failed.');
		await expect(scriptlessPreview.getByText('canary-steady', { exact: true })).toHaveCount(0);
		await expect(scriptlessPreview.getByText('canary-polite', { exact: true })).toHaveCount(0);
	} finally {
		await scriptless.close();
	}
});
