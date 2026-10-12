/** The migrated route keeps populated, real-ledger geometry evidence without a cross-route matrix. */
import { expect, test } from './support/door-page';
import { populatedPanels } from './support/panel-drivers/pipelines';
import { judgeSettled, readPanel } from './support/panel-gates';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

for (const width of [390, 1280]) {
	test(`measured native Pipelines panels meet their declared plot gates at ${width}`, async ({ page }, info) => {
		await page.setViewportSize({ width, height: 900 });
		await populatedPanels(page, info.workerIndex);
		await page.goto('/console/');
		await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'ok');
		const appearance = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8'));
		const configured = JSON.parse(readFileSync(resolve('..', 'config', 'console', 'pipelines.json'), 'utf8'));
		const native = ['failure-mix', 'item-time-split', 'slower-on-same-work', 'stage-timings',
			'item-cost', 'run-timeline', 'article-age'];
		for (const id of native) {
			const panel = page.locator(`[data-console-panel-id="${id}"]`);
			const marks = panel.locator(id === 'run-timeline' ? '[data-timeline-bar]' : 'svg');
			await expect(marks).not.toHaveCount(0);
			const box = await marks.first().boundingBox();
			expect(box).not.toBeNull();
			expect(box!.width).toBeGreaterThan(0);
			expect(box!.height).toBeGreaterThan(0);
		}
		const count = 8 * Math.max(8, Math.ceil(appearance.console.fleet_min_rows / 8));
		await expect.soft(page.locator('[data-duration-cohort]')).toContainText(`${count} of ${count + 8} recorded item clocks`);
		for (const id of configured.judged as string[]) {
			const reading = await readPanel(page.locator(`[data-console-panel-id="${id}"]`));
			for (const verdict of judgeSettled(reading, appearance.console.plot_min_fill_share)) {
				expect.soft(verdict.pass, `${id}, gate ${verdict.gate}: ${verdict.says}`).toBe(true);
			}
		}
	});
}
