/** Does the real private builder retain absent, quiet and populated evidence? */
import { expect, test } from './support/door-page';
import { modelRoute } from './support/model-route';

for (const evidence of ['missing', 'quiet', 'populated'] as const) {
	test(`the real private Summaries builder preserves ${evidence} records`, async ({ page }, info) => {
		const fixture = await modelRoute(info.outputPath(`private-${evidence}`), evidence);
		try {
			await page.goto(`${fixture.origin}/console/model/`);
			if (evidence !== 'populated') {
				await expect(page.locator('[data-model-cards-empty]')).toHaveAttribute('data-model-cards-empty', evidence);
				await expect(page.locator('[data-doubt-reasons-empty]')).toHaveAttribute('data-doubt-reasons-empty', evidence);
				await expect(page.locator('[data-model-cards] [data-kpi]')).toHaveCount(0);
			} else {
				// Two score measurements of one published summary remain one distinct card count.
				await expect(page.locator('[data-kpi="Summaries today"] [data-kpi-value]')).toHaveText('1');
				await expect(page.locator('[data-instrument-slot="model-cards"] [data-kpi-value]')).toHaveText('1');
				await page.locator('[data-model-table-control] > summary').click();
				await expect(page.locator('[data-instrument="coherence"]').first()).toHaveText('-0.25');
				await expect(page.locator('[data-instrument="self_repetition"]').first()).toHaveText('0%');
			}
		} finally { await fixture.close(); }
	});
}
