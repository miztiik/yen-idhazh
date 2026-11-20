import { expect, test } from './support/browser';

test('Voices keeps its combined reading and gives the scriptless page a failures-only preview', async ({ page, browser }) => {
	await page.goto('/console/voices/');
	const failures = page.locator('[data-console-panel-id="feeds-failed"]');
	const reliability = failures.locator('[data-feed-reliability]');
	await expect(reliability).toHaveCount(1);
	const counts = await reliability.evaluate((element) => ({
		clean: Number(element.getAttribute('data-feed-clean')),
		failed: Number(element.getAttribute('data-feed-failed')),
		checked: Number(element.getAttribute('data-feed-checked'))
	}));
	expect(counts.clean + counts.failed).toBe(counts.checked);

	await page.locator('[data-window-preset="90"]').click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '90');
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
	await expect(failures.locator('[data-feed-reliability]')).toHaveCount(1);

	const scriptless = await browser.newContext({ javaScriptEnabled: false });
	try {
		const fallback = await scriptless.newPage();
		await fallback.goto(page.url());
		const panel = fallback.locator('[data-console-panel-id="feeds-failed"]');
		await expect(panel.getByRole('heading', { name: 'Feed failures', exact: true })).toBeVisible();
		const preview = panel.locator('[data-feed-preview="read"]');
		await expect(preview.locator('[data-lede]')).toHaveText('3 of 4 checked feeds failed at least once.');
		await expect(preview.locator('[data-feed-row] strong')).toHaveText(['canary-flaky', 'canary-empty', 'canary-gone']);
		await expect(preview.locator('[data-feed-row="canary-empty"]')).toContainText('2 of 3 recorded reads failed.');
		await expect(preview.getByText('canary-steady', { exact: true })).toHaveCount(0);
		await expect(preview.getByText('canary-polite', { exact: true })).toHaveCount(0);
	} finally {
		await scriptless.close();
	}
});
