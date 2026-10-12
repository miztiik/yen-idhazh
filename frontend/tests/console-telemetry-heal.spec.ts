/** The native door must retry a failed packed file on a later widen. */
import { expect, test } from './support/door-page';
import { hydrated, setWindow } from './support/console-window/controls';
import { THROUGH, FIRST, dayBefore, timedRow, packedPipelines, servePipelines, settled } from './support/pipelines-ledgers';

let root: string;
const older = dayBefore(THROUGH, 60);
test.beforeAll(async () => {
	root = await packedPipelines('heal', [
		{ covers: FIRST, rows: [] },
		{ covers: older, rows: [timedRow(older), timedRow(older, { item_id: 'second' })] },
		{ covers: THROUGH, rows: [timedRow(THROUGH)] }
	]);
});

test('a failed packed file load heals on a later widen', async ({ page }) => {
	await servePipelines(page, root);
	let refusing = true;
	let asked = 0;
	await page.route((url) => url.pathname.endsWith(`/state/compact/item-health/daily/${older.replaceAll('-', '/')}.parquet`), (route) => {
		asked += 1;
		return refusing ? route.abort('failed') : route.fallback();
	});
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	expect(asked).toBe(0);
	await setWindow(page, 90);
	await expect.poll(() => asked).toBeGreaterThan(0);
	await settled(page);
	expect(asked).toBeGreaterThan(0);
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'unreachable');
	await expect(page.locator('[data-console-retry]')).toBeVisible();
	refusing = false;
	const before = asked;
	await setWindow(page, 1);
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'ok');
	await settled(page);
	await setWindow(page, 90);
	await expect.poll(() => asked).toBe(before + 1);
	await settled(page);
	expect(asked).toBe(before + 1);
	await expect(page.locator('[data-duration-cohort]')).toContainText('3 of 3 recorded item clocks');
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '90');
});
