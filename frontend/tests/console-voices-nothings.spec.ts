/** Real fixture-root publication distinguishes all four native Voices nothings. */
import { expect, test } from './support/door-page';
import { DRIVERS } from './support/panel-drivers/voices';
const PANELS = ['feeds-failed', 'fetch-time', 'source-cuts', 'why-chosen', 'watchlist'] as const;
for (const state of ['loading', 'quiet', 'missing', 'unreachable'] as const) {
	test(`the genuine ${state} record has no fabricated dates or values`, async ({ page }) => {
		const prepared = await DRIVERS['fetch-time'][state](page);
		try {
			await prepared?.afterOpen?.();
			for (const id of PANELS) {
				const panel = page.locator(`[data-console-panel-id="${id}"] .panel-body`);
				await expect(panel).toHaveCount(1);
				if (state === 'loading') {
					await expect(panel.locator('[data-panel-state="loading"]')).toHaveCount(1);
					await expect(panel).toHaveText('');
					await expect(panel.locator('[data-chart-type]')).toHaveCount(0);
				} else {
					const sentence = state === 'quiet' ? 'Nothing recorded.' : state === 'missing' ? 'Not published yet.' : 'Did not arrive.';
					const empty = panel.locator(`[data-empty-state="${state}"]`);
					await expect(empty).toHaveCount(1);
					await expect(empty).toHaveText(sentence);
					const feedNote = id === 'feeds-failed' && state === 'missing'
						? ' Not published yet. No feed record was included in this build, so a common feed-and-article count cannot be stated.' : '';
					await expect(panel).toHaveText(`${sentence}${feedNote}`);
				}
				await expect(panel.locator('[data-ranked-row], [data-tile-state], [data-source-cut]')).toHaveCount(0);
			}
			if (state === 'quiet' || state === 'missing') {
				for (const id of ['source-health', 'retiring', 'ranking-discount']) {
					const panel = page.locator(`[data-console-panel-id="${id}"] .panel-body`);
					await expect(panel.locator(`[data-empty-state="${state}"]`)).toHaveCount(1);
					await expect(panel).toContainText(state === 'quiet' ? 'Nothing recorded.' : 'Not published yet.');
					await expect(panel.locator('[data-ranked-row], [data-retiring-day], [data-source-state]')).toHaveCount(0);
				}
			}
		} finally { await prepared?.afterRead?.(); }
	});
}
