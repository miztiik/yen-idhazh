import { expect, test } from '@playwright/test';
test('a story links to its own anchor on the day that published it', async ({ page }) => {
    await page.goto('/archive/');
    const first = page.locator('[data-story-list="rows"] li a').first();
    await expect(first).toBeVisible();
    expect(await first.getAttribute('href')).toMatch(/\/\d{4}-\d{2}-\d{2}\/#[a-z0-9-]+$/);
    await first.click();
    await expect(page.locator('article').first()).toBeVisible();
});
