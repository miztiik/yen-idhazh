/** Does the real Judgement route preserve read evidence and null denominators through rendering? */
import { expect, test } from './support/browser';
import { cpSync, writeFileSync } from 'node:fs';
import { judgementRoute } from './support/judgement-route';

for (const evidence of ['empty', 'unknown-denominators', 'missing-gate'] as const) {
	test(`the reader, page and panels keep ${evidence} truthful in both themes`, async ({ browser }, info) => {
		test.setTimeout(180_000);
		const server = await judgementRoute(info.outputPath('route'), {
			evidence, ...(evidence === 'unknown-denominators' ? { scoreRecord: 'populated' as const } : {})
		});
		const checks: object[] = [];
		try {
			for (const width of [390, 768, 1440]) {
				for (const theme of ['light', 'dark']) {
					const context = await browser.newContext({ serviceWorkers: 'block', viewport: { width, height: 1000 } });
					try {
						await context.addInitScript(({ theme }) => {
							localStorage.setItem('idhazh:theme', theme);
							localStorage.setItem('idhazh:console-window', '7');
						}, { theme });
						const page = await context.newPage();
						const errors: string[] = [];
						page.on('pageerror', (error) => errors.push(error.message));
						page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
						page.on('response', (response) => { if (response.status() === 404) errors.push(response.url()); });
						await page.goto(`${server.origin}console/judgement/`);
						await expect(page.locator('[data-window-preset="7"] input')).toBeEnabled();
						await expect(page.locator('[data-console-panel-id]')).toHaveCount(6);
						await expect(page.locator('[data-lede]')).toHaveCount(6);
						const judge = page.locator('[data-console-panel-id="judge-agreement"]');
						const gates = page.locator('[data-console-panel-id="record-gates"]');
						if (evidence === 'empty') {
							await expect(judge.locator('[data-lede]')).toHaveText('No judge readings were returned for this window.');
							await expect(judge.locator('[data-empty="missing"]')).toHaveCount(0);
							await expect(gates.locator('[data-target-cell="track"]')).toHaveCount(0);
							await expect(page.locator('[data-line-state]')).toHaveText(
								'No calculated line was returned for these 7 days. The rule is the line the newest day was built with, and the scale is the whole range a fitted line may take.'
							);
						} else if (evidence === 'unknown-denominators') {
							await expect(judge.locator('[data-lede]')).toHaveText('The count of pairs read twice is unavailable for this window.');
							await expect(judge.locator('[data-agreement-day="2030-06-14"] circle')).toHaveCount(1);
							await expect(judge.locator('[data-agreement-state="unavailable-count"]')).toHaveText(
								'In these 7 days, disagreed with the second reading: the count of pairs read twice is unavailable. Could not tell: 0% of the 10 that agreed. Known daily counts remain in the readout.'
							);
							await expect(gates.locator('[data-target-cell="track"]')).toHaveCount(3);
							await expect(page.locator('[data-verdict-cell]')).toHaveCount(4);
							await expect(page.locator('[data-verdict-figure="judged"]')).toContainText('-');
							await expect(page.locator('[data-holdout-weights]')).toContainText('the weight in the committed config');
							await expect(judge.locator('[data-evidence-note]')).toContainText([
								'The judge record starts on 14 Jun 2030.',
								'The judge record is packed through 14 Jun 2030. Later days have no packed reading here.',
								'The last packed period with rows in the judge record is 14 Jun 2030 to 14 Jun 2030. This is a period, not the date of the last run.'
							]);
						} else {
							await expect(judge.locator('[data-lede]')).toHaveText("50% of 10 pairs disagreed with the judge's own second reading");
							await expect(judge.locator('[data-agreement-day="2030-06-14"] circle')).toHaveCount(2);
							await expect(judge).toContainText('50% of 10 pairs');
							await expect(judge).not.toContainText('Both rates are inside the marks.');
							await expect(judge.locator('[data-evidence-note]').last()).toHaveText(
								'The calculated-line or gate readings on 2030-06-14 are unavailable. Valid judge-rate readings remain visible.'
							);
							await expect(gates.locator('[data-target-cell="track"]')).toHaveCount(0);
						}
						await expect(page.locator('[data-console-panels="judgement"]')).not.toContainText(/No run has recorded|No day has fitted|has not been scored|No pair has been marked by hand/);
						expect(errors).toEqual([]);
						checks.push({ width, theme, evidence, panels: 6, ledes: 6, errors });
					} finally {
						await context.close();
					}
				}
			}
			cpSync(server.staticRoot, info.outputPath('verified-static'), { recursive: true });
			writeFileSync(info.outputPath('smoke.json'), JSON.stringify({ inputs: server.inputs, checks }, null, 2));
		} finally {
			await server.close();
		}
	});
}
