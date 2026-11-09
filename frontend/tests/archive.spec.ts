import { expect, test } from '@playwright/test';
test('a story links to its own anchor on the day that published it', async ({ page }) => {
    await page.addInitScript(() => {
        Object.defineProperty(globalThis, 'WebAssembly', { value: undefined });
    });
    await page.goto('/archive/');
    const first = page.locator('[data-story-list="rows"] li a').first();
    await expect(first).toBeVisible();
    await expect(page.locator('[data-search-state]')).toContainText('this browser cannot run it');
    await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeDisabled();
    const field = page.locator('#archive-query');
    await field.click();
    const original = await field.elementHandle();
    const position = await field.boundingBox();
    const title = await first.innerText();
    for (const character of title.slice(0, 3)) {
        await page.keyboard.insertText(character);
        await expect(field).toBeFocused();
        expect(await field.evaluate((node, initial) => node === initial, original)).toBe(true);
        expect((await field.boundingBox())?.y).toBe(position?.y);
    }
    await page.keyboard.press('ControlOrMeta+A');
    await page.keyboard.insertText('no matching archive story');
    await expect(page.locator('[data-story-list="rows"] li a')).toHaveCount(0);
    await expect(page.locator('[data-story-list="empty"]')).toContainText('Change the filter or open a day above.');
    await expect(field).toBeFocused();
    await page.keyboard.press('ControlOrMeta+A');
    await page.keyboard.press('Backspace');
    await expect(first).toBeVisible();
    await expect(field).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-search-state]')).toContainText('this browser cannot run it');
    expect(await first.getAttribute('href')).toMatch(/\/\d{4}-\d{2}-\d{2}\/#[a-z0-9-]+$/);
    await first.click();
    await expect(page.locator('article').first()).toBeVisible();
});
