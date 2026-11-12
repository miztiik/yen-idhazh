import { expect, test } from './support/browser';

test('Voices keeps feed evidence and its native readings usable across a window change', async ({ page }) => {
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
});
