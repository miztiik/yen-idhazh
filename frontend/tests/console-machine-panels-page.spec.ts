import { expect, test } from './support/door-page';
import { WATCHED_FLAG } from '../src/lib/console/machine/host-types';

const WATCHED: readonly string[] = WATCHED_FLAG;

test.describe('the machines this run drew', () => {
	test('the built cards draw every watched flag, and their sentences keep the shapes the cards make', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		await expect(panel).toBeVisible();
		const cards = panel.locator('[data-machine-card]');
		const count = await cards.count();
		expect(count, 'the panel drew no machine card').toBeGreaterThan(0);

		for (let index = 0; index < count; index += 1) {
			const card = cards.nth(index);
			const chips = card.locator('[data-machine-flag]');
			if ((await chips.count()) === 0) {
				await expect(card.locator('[data-machine-flags="none"]')).toBeVisible();
			} else {
				expect(
					await chips.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-machine-flag'))),
					'a card drew some of the watched flags and left the rest out'
				).toEqual(WATCHED);
			}
			for (const text of await card.locator('[data-machine-copy-speed]').allInnerTexts()) {
				const said = text.trim();
				if (said.startsWith('No copy speed')) {
					expect(said, 'a withheld reading still printed a rate').not.toContain('GiB/s');
				} else if (!said.startsWith('Copy speed was not measured')) {
					expect(said, 'the rate and its buffer are not in one element').toMatch(/GiB\/s.*MiB buffer/);
				}
			}
			for (const text of await card.locator('[data-machine-clock]').allInnerTexts()) {
				expect(text, 'a clock was drawn as a share of something').not.toContain('%');
			}
			for (const text of await card.locator('[data-machine-uptime]').allInnerTexts()) {
				expect(text.trim()).toMatch(/^(Up .+ when we measured it\.|Uptime was not recorded on this job\.)$/);
			}
		}

		const drawn = await panel
			.locator('[data-machine-bar="l3"][data-machine-bar-state="drawn"]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					bytes: Number(node.querySelector('[data-machine-cache]')?.getAttribute('data-machine-cache')),
					fraction: Number(
						node.querySelector('[data-machine-bar-cell="track"]')?.getAttribute('data-machine-bar-fraction')
					)
				}))
			);
		for (const bar of drawn) {
			expect(bar.fraction / drawn[0].fraction, `a ${bar.bytes}-byte cache`).toBeCloseTo(
				bar.bytes / drawn[0].bytes,
				4
			);
		}
	});

	test('the machine location disclosure is native and closed at rest', async ({ page }) => {
		await page.goto('/console/machine/');
		const where = page.locator('[data-machine-where]');
		const count = await where.count();
		expect(count, 'no machine card carried a location disclosure').toBeGreaterThan(0);
		for (let index = 0; index < count; index += 1) {
			const disclosure = where.nth(index);
			expect(await disclosure.evaluate((node) => node.tagName)).toBe('DETAILS');
			expect(await disclosure.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
			await expect(disclosure.locator('summary')).toHaveText('Where the platform put this');
		}
	});

	test('a reading with nothing to draw names its state and draws no track', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		const bars = panel.locator('[data-machine-bar]');
		const count = await bars.count();
		expect(count).toBeGreaterThan(0);

		const states = new Set<string>();
		for (let index = 0; index < count; index += 1) {
			const bar = bars.nth(index);
			const state = (await bar.getAttribute('data-machine-bar-state')) ?? '';
			states.add(state);
			const tracks = await bar.locator('[data-machine-bar-cell="track"]').count();
			expect(tracks, `state ${state} drew ${tracks} tracks`).toBe(state === 'drawn' ? 1 : 0);
			if (state !== 'drawn') {
				await expect(bar.locator('[data-machine-bar-why]')).toHaveCount(
					state === 'absent' ? 0 : 1
				);
			}
		}
		expect([...states].sort()).toEqual(['alone', 'drawn', 'ungraded']);
	});
});
