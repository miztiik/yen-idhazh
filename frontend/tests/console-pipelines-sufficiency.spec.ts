/** A real populated route names the complete-clock cohort without counting missing clocks as zero. */
import { expect, test } from './support/door-page';
import { populatedPanels } from './support/panel-drivers/pipelines';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

test('native Pipelines reports which recorded item clocks qualified for the comparison', async ({ page }, info) => {
	await populatedPanels(page, info.workerIndex);
	await page.goto('/console/');
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'ok');
	const appearance = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8'));
	const count = 8 * Math.max(8, Math.ceil(appearance.console.fleet_min_rows / 8));
	await expect(page.locator('[data-duration-cohort]')).toContainText(`${count} of ${count + 8} recorded item clocks`);
});
