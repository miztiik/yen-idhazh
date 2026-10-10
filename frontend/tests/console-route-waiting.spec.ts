/** Does the real shared frame stay honest and still through its normal states? */
import { expect, test } from './support/door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { clientCode, drawClient } from './support/console-window/client-render';

test.use({ baseURL: 'http://127.0.0.1:4173', serviceWorkers: 'block' });

let code: string;
test.beforeAll(async () => {
	code = await clientCode([['RouteWaiting', './tests/fixtures/panels/RouteWaiting.svelte']]);
});

for (const width of [320, 390, 1440]) {
	for (const theme of ['dark', 'light']) {
		test(`${theme}, ${width}px: one delayed shimmer, no fabricated values, and a fixed standing`, async ({ page }) => {
			const knobs = JSON.parse(readFileSync(resolve('../config/appearance.json'), 'utf8')).console;
			await page.setViewportSize({ width, height: 1000 });
			await page.clock.install({ time: new Date('2026-10-10T00:00:00Z') });
			await page.clock.pauseAt(new Date('2026-10-10T00:00:01Z'));
			await drawClient(page, code, 'RouteWaiting', {
				initialAnswers: ['pending', 'pending'], days: 14, through: '2026-10-09',
				shimmerAfterMs: knobs.shimmer_after_ms, height: knobs.chart_height, width: knobs.chart_width
			});
			await page.addStyleTag({ content: readFileSync(resolve('src/styles/tokens.css'), 'utf8') });
			await page.addStyleTag({ content: readFileSync(resolve('src/styles/app.css'), 'utf8').replace(/^@import .*;$/gm, '') });
			await page.addStyleTag({ content: 'body { margin: 0; padding: var(--space-4); font-family: var(--font-sans); }' });
			await page.locator('html').evaluate((node, theme) => node.setAttribute('data-theme', theme), theme);
			const frame = page.locator('[data-console-panels="machine"]');
			const standing = frame.locator('[data-console-standing]');
			const before = await page.locator('[data-after-box]').boundingBox();
			expect(before).not.toBeNull();
			await expect(frame).toHaveAttribute('data-route-state', 'loading');
			await expect(frame).toHaveAttribute('data-shimmer', 'off');
			await expect(standing).toHaveText('');
			await expect(page.locator('[data-real-count]')).toHaveCount(0);
			await expect(page.locator('.reserved-bar')).toHaveCount(0);
			const reserved = page.locator('[data-reserved="waiting-fixture"]');
			await expect(reserved).toHaveClass(/loading/);
			await expect(reserved).toHaveCSS('animation-name', 'none');
			await page.clock.runFor(knobs.shimmer_after_ms / 2);
			await page.locator('[data-partly-settled]').click();
			await page.clock.runFor(knobs.shimmer_after_ms / 2);
			await expect(frame).toHaveAttribute('data-shimmer', 'on');
			await expect(standing).toHaveText('Fetching the record.');
			await expect(reserved).toHaveCSS('animation-name', 'shimmer');
			await page.emulateMedia({ reducedMotion: 'reduce' });
			await expect(reserved).toHaveCSS('animation-name', 'none');
			await expect(reserved).toHaveCSS('background-image', 'none');
			await page.emulateMedia({ reducedMotion: 'no-preference' });
			for (const state of ['quiet', 'missing', 'unreachable', 'ok'] as const) {
				await page.locator(`[data-settle="${state}"]`).click();
				await expect(frame).toHaveAttribute('data-route-state', state);
				await expect(frame).toHaveAttribute('data-shimmer', 'off');
				const after = await page.locator('[data-after-box]').boundingBox();
				expect(after).not.toBeNull();
				expect(after!.y, `${state}: content below the frame moved`).toBeCloseTo(before!.y, 1);
				const size = await standing.evaluate((node) => ({
					height: node.getBoundingClientRect().height,
					reserve: Number.parseFloat(getComputedStyle(node).minBlockSize)
				}));
				expect(size.height, `${state}: standing exceeded its reserved height`).toBeLessThanOrEqual(size.reserve + 0.5);
				if (state === 'unreachable') await expect(page.locator('[data-console-retry]')).toHaveCount(1);
				else await expect(page.locator('[data-console-retry]')).toHaveCount(0);
				if (state === 'ok') await expect(page.locator('[data-real-count]')).toHaveText('0');
			}
			await page.locator('[data-settle="unreachable"]').click();
			await page.locator('[data-console-retry]').click();
			await expect(frame).toHaveAttribute('data-route-state', 'loading');
			await expect(frame).toHaveAttribute('data-shimmer', 'off');
			await expect(standing).toHaveText('');
			await page.clock.runFor(knobs.shimmer_after_ms);
			await expect(frame).toHaveAttribute('data-shimmer', 'on');
		});
	}
}
