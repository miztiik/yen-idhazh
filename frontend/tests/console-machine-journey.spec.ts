/** One shipped Hardware journey and its independent native transport/publication boundaries. */
import { expect, test, type Page } from './support/browser';
import { renderFrameCss } from '../scripts/build-frame-css.mjs';
import { WINDOW_PREFERENCE_KEY } from '../src/lib/console/window-preference';

const PANELS = [
	'two-clocks', 'slower-machines',
	'platform-mix', 'tail-trend', 'closest-to-memory', 'memory-held',
	'context-headroom', 'article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost'
];
const NATIVE = /\/state\/(?:compact|raw)\/(?:item-health|host-fingerprint|run-shards)\//;

async function settled(page: Page): Promise<void> {
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'ok');
}

test('Hardware reads native files, opens a dated answer and carries its window across a real tab', async ({ page }) => {
	const arrived: string[] = [];
	const privateRequests: string[] = [];
	const errors: string[] = [];
	const storageWarnings: string[] = [];
	const nativeRequests: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'warning' && message.text().includes('Window preference could not')) storageWarnings.push(message.text());
	});
	await page.addInitScript((key) => {
		const read = Storage.prototype.getItem;
		const write = Storage.prototype.setItem;
		Storage.prototype.getItem = function (name) {
			if (name === key) throw new DOMException('Storage read denied.', 'SecurityError');
			return read.call(this, name);
		};
		Storage.prototype.setItem = function (name, value) {
			if (name === key) throw new DOMException('Storage write denied.', 'QuotaExceededError');
			return write.call(this, name, value);
		};
	}, WINDOW_PREFERENCE_KEY);
	page.on('response', (response) => {
		if (NATIVE.test(response.url()) && response.status() === 200) arrived.push(response.url());
		if (response.status() === 404) errors.push(`404: ${new URL(response.url()).pathname}`);
	});
	page.on('request', (request) => {
		if (NATIVE.test(request.url())) nativeRequests.push(request.url());
		if (/\/(?:run|plan)\.json|\/state\/.*(?:run-plan|prompt)/.test(request.url())) privateRequests.push(request.url());
	});
	page.on('pageerror', (error) => errors.push(error.message));
	page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
	await page.setViewportSize({ width: 1920, height: 900 });
	await page.goto('/console/machine/');
	await settled(page);
	await expect(page.locator('#console-route-title')).toHaveText('Hardware');
	await expect(page.locator('[data-window-status]')).toContainText('20 Aug 2026');
	await expect(page.locator('[data-console-rail]')).toHaveCSS('position', 'sticky');
	const shellWidth = await page.locator('.frame').evaluate((node) => {
		const shell = node.querySelector('.console-shell')!;
		const rail = node.querySelector('[data-console-rail]')!;
		const frame = node.getBoundingClientRect();
		return {
			viewport: innerWidth, frame: frame.width,
			content: node.querySelector('.console-main')!.getBoundingClientRect().width,
			available: frame.width - 2 * parseFloat(getComputedStyle(node).paddingInlineStart) -
				rail.getBoundingClientRect().width - parseFloat(getComputedStyle(shell).columnGap)
		};
	});
	expect(shellWidth.frame, 'the default console must not keep its former centered cap').toBe(shellWidth.viewport);
	expect(shellWidth.content).toBeCloseTo(shellWidth.available, 1);
	await expect(page.locator('[data-site-header] [data-theme-toggle]')).toHaveCount(0);
	await expect(page.locator('[data-site-footer] [data-theme-toggle]')).toHaveCount(1);
	await expect(page.locator('[data-console-nav] small')).toHaveCount(0);
	const selectedGlyph = page.locator('[data-console-tab="machine"] [data-route-glyph]');
	await expect(page.locator('#console-route-title [data-route-glyph]')).toHaveAttribute(
		'data-route-glyph', (await selectedGlyph.getAttribute('data-route-glyph'))!);
	expect((await page.locator('#console-route-title svg').boundingBox())!.width).toBeGreaterThan(
		(await selectedGlyph.locator('svg').boundingBox())!.width);
	await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#191917');
	const firstComparison = page.locator('[data-console-panel-id="two-clocks"] [data-lede]');
	await expect(firstComparison).toBeVisible();
	await expect(firstComparison).toContainText('max gap;');
	expect(await firstComparison.evaluate((node) => node.getBoundingClientRect().bottom)).toBeLessThan(900);
	await page.screenshot({ path: test.info().outputPath('hardware-wide-dark.png') });
	const rankedRow = page.locator('[data-console-panel-id="two-clocks"] [data-ranked-row]').first();
	await rankedRow.hover();
	await expect(page.locator('[data-chart-tooltip]')).toContainText(
		(await rankedRow.locator('[data-ranked-cell="value"]').textContent())!);
	await page.locator('#console-route-title').hover();
	await expect(page.locator('[data-chart-tooltip]')).toHaveCount(0);
	const evidence = page.locator('[data-machine-evidence]');
	await expect(evidence.locator('summary')).toContainText('3 runs excluded from run count. Their articles still count.');
	await expect(page.locator('[data-machine-refused]')).not.toBeVisible();
	await evidence.locator('summary').focus();
	await page.keyboard.press('Enter');
	await expect(page.locator('[data-machine-refused]')).toBeVisible();
	await expect(page.locator('[data-refused-run]')).toHaveCount(3);
	await page.keyboard.press('Enter');
	await expect(page.locator('[data-machine-refused]')).not.toBeVisible();
	expect(await page.locator('[data-console-panel-id]').evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-console-panel-id')))).toEqual(PANELS);
	await expect(page.locator('[data-console-panel-id] > header > h3')).toHaveCount(PANELS.length);
	for (const id of ['machine-cards', 'processor-lost', 'disk-reads', 'slowest-articles']) {
		await expect(page.locator(`[data-console-panel-id="${id}"], a[href$="#${id}"]`)).toHaveCount(0);
	}
	for (const ledger of ['item-health', 'host-fingerprint', 'run-shards']) {
		expect(arrived.some((url) => url.includes(`/${ledger}/index/`)), `${ledger} index arrived`).toBe(true);
		expect(arrived.some((url) => url.includes(`/${ledger}/`) && new URL(url).pathname.endsWith('.parquet')),
			`${ledger} native rows arrived`).toBe(true);
	}
	expect(await page.locator('[data-clock-pair]').count(), 'the independent clocks arrived').toBeGreaterThan(0);
	const fleet = page.locator('[data-fleet-shape]');
	await expect(fleet).toHaveCount(1);
	expect(Number(await fleet.getAttribute('data-fleet-placements'))).toBeGreaterThan(0);
	const history = page.locator('[data-console-panel-id="platform-mix"]');
	const square = history.locator('[data-fleet-square]:not([data-fleet-square="unrecorded"])').first();
	await square.scrollIntoViewIfNeeded();
	await square.hover();
	const machineHover = page.locator('[data-chart-tooltip="machine-fleet"]');
	await expect(machineHover).toBeVisible();
	await expect(machineHover.locator('strong')).toHaveText(/\d{4}-\d{2}-\d{2} UTC/);
	await expect(machineHover.locator('dl > div')).toHaveCount(1);
	await expect(machineHover).toContainText(/\d+ of \d+ recorded jobs/);
	await expect(machineHover).not.toContainText('tokens a second');
	await expect(machineHover.locator('p')).toHaveCount(0);
	expect(await square.evaluate((node) => {
		if (!(node instanceof SVGElement)) throw new Error('Expected the actual job square.');
		const id = /^url\(["']?#([^"')]+)["']?\)/.exec(node.style.fill)?.[1];
		const gradient = id === undefined ? null : document.getElementById(id);
		return gradient instanceof SVGLinearGradientElement &&
			new Set([...gradient.querySelectorAll('stop')].map((stop) => getComputedStyle(stop).stopColor)).size > 1;
	}), 'the actual job square resolves to a gradient with distinct rendered stops').toBe(true);
	const day = (await machineHover.locator('strong').textContent())!.replace(' UTC', '');
	const machineCount = (await machineHover.locator('dd').textContent())!.split(' of ')[0];
	const machineName = (await machineHover.locator('dt').textContent())!.trim();
	await square.click();
	const dayDetails = history.locator(`[data-fleet-jobs="${day}"]`);
	await expect(dayDetails).toBeVisible();
	await expect(dayDetails.locator('[data-readout-row]').filter({ hasText: machineName })).toContainText(machineCount);
	expect(await dayDetails.locator('[data-fleet-job]').count()).toBeGreaterThan(0);
	await expect(dayDetails).toContainText('tokens a second');
	await dayDetails.getByRole('button', { name: 'Close the list' }).click();
	const tokens = page.locator('[data-console-panel-id="read-against-written"]');
	const plot = tokens.locator('[data-chart-type="runSeries"]');
	await expect(plot).toBeVisible();
	await expect.poll(() => plot.evaluate((node) => {
		if (!(node instanceof SVGSVGElement)) throw new Error('Expected the actual run drawing.');
		return Math.abs(node.getBoundingClientRect().width - node.viewBox.baseVal.width);
	}), 'the chart must redraw in CSS pixels, not stretch its old coordinate frame').toBeLessThan(1);
	const readout = tokens.locator('[data-readout]');
	const heading = readout.locator('[data-readout-day]');
	const newestRun = await heading.textContent();
	const newestSelected = newestRun!.replace(/, the newest run$/, '');
	await plot.focus();
	expect(await plot.evaluate((node) => {
		const caption = node.closest('[data-console-panel-id]')!.querySelector('[data-token-unit]')!;
		const style = getComputedStyle(node);
		return node.getBoundingClientRect().top - parseFloat(style.outlineWidth) -
			parseFloat(style.outlineOffset) - caption.getBoundingClientRect().bottom;
	}), 'the focused plot must not overlap its unit caption').toBeGreaterThanOrEqual(0);
	await expect(heading).toHaveText(newestRun!);
	await page.keyboard.press('Home');
	const firstRun = await heading.textContent();
	expect(firstRun).not.toBe(newestRun);
	await page.keyboard.press('ArrowRight');
	await expect(heading).not.toHaveText(firstRun!);
	await page.keyboard.press('End');
	await expect(heading).toHaveText(newestSelected);
	await page.keyboard.press('ArrowLeft');
	await expect(heading).not.toHaveText(newestSelected);
	await page.keyboard.press('Escape');
	await expect(heading).toHaveText(newestRun!);
	await page.keyboard.press('ArrowLeft');
	await expect(heading).not.toHaveText(newestSelected);
	await page.keyboard.press('Escape');
	const axisStart = Number(await plot.locator('line[stroke="var(--chart-axis)"]').first().getAttribute('x1'));
	await plot.hover({ position: { x: axisStart, y: 80 } });
	await expect(heading).toHaveText(firstRun!);
	const tooltip = page.locator('[data-chart-tooltip="read-against-written"]');
	await expect(tooltip).toBeVisible();
	await expect(tooltip.locator('strong')).toHaveText(firstRun!);
	const stripFacts = await readout.locator('[data-readout-row]').evaluateAll((rows) => rows.map((row) => ({
		label: row.querySelector('.readout-label')!.textContent!.trim(),
		value: row.querySelector('.readout-value')?.textContent?.trim() ?? ''
	})));
	expect(await tooltip.locator('dl > div').evaluateAll((rows) => rows.map((row) => ({
		label: row.querySelector('dt')!.textContent!.trim(),
		value: row.querySelector('dd')?.textContent?.trim() ?? ''
	})))).toEqual(stripFacts);
	await page.screenshot({ path: test.info().outputPath('run-hover-wide-dark.png') });
	await plot.click({ position: { x: axisStart, y: 80 } });
	await expect(heading).toHaveText(firstRun!);
	await page.keyboard.press('Escape');
	await expect(page.locator('[data-chart-tooltip]')).toHaveCount(0);
	await expect(heading).toHaveText(newestRun!);
	await expect(readout).toContainText('Read (solid)');
	await expect(readout).toContainText('Written (dashed)');
	await expect(readout).toContainText('2026-08-20 UTC');
	await expect(readout).toContainText('Measured articles');
	await expect(readout).not.toContainText('Not recorded');
	await expect(tokens.getByRole('radio', { name: 'Run total', exact: true })).toBeChecked();
	const totals = await readout.textContent();
	const beforeMetric = [...nativeRequests];
	await tokens.locator('[data-token-measure="median"]').click();
	await expect(tokens.getByRole('radio', { name: 'Median per article', exact: true })).toBeChecked();
	await expect(tokens.locator('[data-token-unit]')).toContainText('Median tokens per article');
	await expect(heading).toHaveText(newestRun!);
	await expect(readout).not.toHaveText(totals!);
	await tokens.locator('[data-token-measure="total"]').click();
	await expect(tokens.getByRole('radio', { name: 'Run total', exact: true })).toBeChecked();
	await expect(readout).toHaveText(totals!);
	expect(nativeRequests).toEqual(beforeMetric);
	await tokens.screenshot({ path: test.info().outputPath('run-token-lines-wide.png') });
	const routeStart = await page.locator('.console-shell').evaluate((node) =>
		node.getBoundingClientRect().top + window.scrollY);
	await page.locator('[data-console-group-top]').last().click();
	await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThanOrEqual(routeStart);
	await tokens.scrollIntoViewIfNeeded();
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.locator('[data-console-top]').focus();
	await page.keyboard.press('Enter');
	await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
	await expect(page.locator('#console-route-title')).toBeFocused();
	await page.emulateMedia({ reducedMotion: 'no-preference' });

	const context = page.locator('[data-console-panel-id="context-headroom"]');
	await expect(context.locator('svg[data-chart-type="distribution"]')).toHaveCount(2);
	for (const name of ['context-label', 'context-summary']) {
		expect(Number(await context.locator(`[data-chart-name="${name}"]`).locator('..').getAttribute('data-readout-records')),
			`${name} has a populated distribution`).toBeGreaterThan(0);
	}
	const contextFits = () => context.locator('svg[data-chart-type="distribution"]').evaluateAll((plots) =>
		plots.every((plot) => {
			const bounds = plot.getBoundingClientRect();
			const cell = plot.parentElement!.parentElement!.getBoundingClientRect();
			return bounds.left >= cell.left && bounds.right <= cell.right + 1;
		}));
	const clockLabels = page.locator('[data-console-panel-id="two-clocks"] .ranked-rule-label');
	await expect(clockLabels).toHaveCount(2);
	await expect(clockLabels.first()).toHaveText('Allowed disagreement');
	const clockRulesFit = () => clockLabels.evaluateAll((labels) => labels.every((label) => {
		const bounds = label.getBoundingClientRect();
		const track = label.parentElement!.getBoundingClientRect();
		return bounds.left >= track.left && bounds.right <= track.right + 1;
	}));
	await expect.poll(contextFits).toBe(true);
	await expect.poll(clockRulesFit).toBe(true);
	await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
	await page.setViewportSize({ width: 390, height: 844 });
	await page.evaluate(() => window.scrollTo(0, 0));
	await expect(page.getByText('Console menu', { exact: true })).toBeVisible();
	await expect(page.locator('[data-console-nav]')).not.toBeVisible();
	await page.getByRole('button', { name: 'Switch to the light theme' }).click();
	await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(242, 241, 237)');
	await expect(page.locator('[data-site-footer] [data-theme-toggle]')).toBeVisible();
	await page.screenshot({ path: test.info().outputPath('console-footer-narrow-light.png') });
	await page.locator('[data-console-top]').click();
	await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
	await page.evaluate(() => Promise.allSettled(document.getAnimations().map((animation) => animation.finished)));
	expect(await firstComparison.evaluate((node) => node.getBoundingClientRect().bottom)).toBeLessThan(844);
	expect(await page.locator('[data-console-panel-id="two-clocks"] [data-ranked-cell="value"]').first()
		.evaluate((node) => node.getBoundingClientRect().bottom)).toBeLessThan(844);
	expect(await clockLabels.first().evaluate((label) => {
		const context = label.closest('[data-ranked-row]')!.querySelector('[data-ranked-cell="context"]')!;
		return label.getBoundingClientRect().top - context.getBoundingClientRect().bottom;
	}), 'the threshold label must not overlap the source readings on a phone').toBeGreaterThanOrEqual(0);
	await page.screenshot({ path: test.info().outputPath('hardware-narrow-light.png') });
	await tokens.screenshot({ path: test.info().outputPath('run-token-lines-narrow.png') });
	await expect.poll(contextFits).toBe(true);
	await expect.poll(clockRulesFit).toBe(true);
	await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

	await page.locator('[data-window-select]').selectOption('7');
	await settled(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await tokens.scrollIntoViewIfNeeded();
	await expect(page.locator('.console-toolbar')).toBeInViewport();
	expect((await page.locator('.console-toolbar').boundingBox())!.y).toBeCloseTo(0, 0);
	const dates = page.locator('[data-console-data-dates] > summary');
	await expect(dates).toBeInViewport();
	await dates.focus();
	await page.keyboard.press('Enter');
	await expect(page.locator('[data-window-status]')).toBeInViewport();
	await page.keyboard.press('Enter');
	await expect(page.locator('[data-console-data-dates]')).not.toHaveAttribute('open', '');
	await page.screenshot({ path: test.info().outputPath('console-sticky-narrow-light.png') });
	await page.locator('[data-console-top]').click();
	await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
	await page.getByText('Console menu', { exact: true }).click();
	await page.locator('[data-console-tab="pipelines"]').click();
	await expect(page.locator('[data-console-panels="pipelines"]')).toBeVisible();
	await expect(page.locator('[data-console-panel-id="slowest-articles"]')).toHaveCount(1);
	await expect(page.locator('[data-slowest-run]')).toBeVisible();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await page.getByText('Console menu', { exact: true }).click();
	await page.locator('[data-console-tab="machine"]').click();
	await settled(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await expect(page).toHaveTitle(/Hardware/);
	expect(storageWarnings.some((message) => message.includes('could not be read'))).toBe(true);
	expect(storageWarnings.some((message) => message.includes('could not be saved'))).toBe(true);

	const before = Number(await plot.locator('line[stroke="var(--chart-grid)"]').first().getAttribute('x1'));
	const substitution = await page.addStyleTag({ content: await renderFrameCss({
		console_style: {
			colors: { light: { canvas: '#eef2ef' }, dark: { canvas: '#202522' } },
			typography: { small: { size_rem: 1, leading_rem: 1.25 } }
		}
	}) });
	await substitution.evaluate((node) => {
		if (!(node instanceof HTMLStyleElement)) throw new Error('The substituted stylesheet did not mount.');
		node.setAttribute('data-console-style-substitution', '');
	});
	await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(238, 242, 239)');
	await expect(plot.locator('text').first()).toHaveAttribute('font-size', '16');
	await expect(plot.locator('text').first()).toHaveCSS('font-size', '16px');
	await expect.poll(async () => Number(await plot.locator('line[stroke="var(--chart-grid)"]').first().getAttribute('x1'))).toBeGreaterThan(before);
	await page.locator('.wordmark').click();
	await expect(page.locator('[data-surface="operator"]')).toHaveCount(0);
	await expect(page.locator('[data-console-style-substitution]')).toHaveCount(1);
	await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(244, 246, 251)');
	await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#f4f6fb');
	expect(privateRequests).toEqual([]);
	expect(errors).toEqual([]);
});

test('a failed host index alone is retried while successful article and count files stay held', async ({ page }) => {
	const successfulRequests: string[] = [];
	page.on('request', (request) => {
		if (/\/state\/(?:compact|raw)\/(?:item-health|run-shards)\//.test(request.url())) {
			successfulRequests.push(request.url());
		}
	});
	await page.route(/\/state\/compact\/host-fingerprint\/index\/[^/]+\.json/,
		(route) => route.abort('failed'));
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'unreachable');
	await expect(page.locator('[data-panel-query="memory-held"]')).toHaveAttribute('data-machine-panel-state', 'ok');
	await expect(page.locator('[data-console-retry]')).toBeVisible();
	const before = [...successfulRequests];
	expect(before.some((url) => url.includes('/run-shards/') && new URL(url).pathname.endsWith('.parquet'))).toBe(true);
	expect(before.some((url) => url.includes('/item-health/') && new URL(url).pathname.endsWith('.parquet'))).toBe(true);
	await page.unroute(/\/state\/compact\/host-fingerprint\/index\/[^/]+\.json/);
	await page.locator('[data-console-retry]').click();
	await settled(page);
	expect(await page.locator('[data-clock-pair]').count()).toBeGreaterThan(0);
	expect(successfulRequests).toEqual(before);
	await expect(page.locator('[data-console-retry]')).toHaveCount(0);
});

test('unpublished native indexes keep a named absence, not a lost record or invented drawing', async ({ page }) => {
	await page.route(/\/state\/compact\/(?:host-fingerprint|item-health|run-shards)\/index\/[^/]+\.json/,
		(route) => route.fulfill({ status: 404, body: '' }));
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'missing');
	await expect(page.locator('[data-panel-query][data-machine-panel-state="missing"]')).toHaveCount(PANELS.length);
	await expect(page.locator('[data-panel-query="two-clocks"]')).toContainText('Not published yet.');
	await expect(page.locator('[data-clock-pair], [data-machine-refused], [data-recording="machine-destroyed"]')).toHaveCount(0);
	await expect(page.locator('[data-console-retry]')).toHaveCount(0);
	await expect(page.locator('#console-route-title')).toHaveText('Hardware');
	await expect(page.locator('[data-console-nav]')).toBeVisible();
	await page.locator('[data-panel-query="two-clocks"]').hover();
	await expect(page.locator('[data-chart-tooltip]')).toHaveCount(0);
});

test('actual prerendered Hardware contains words and reserved frames, never ledger values', async ({ browser }) => {
	const context = await browser.newContext({ javaScriptEnabled: false });
	try {
		const page = await context.newPage();
		const response = await page.goto('/console/machine/');
		expect(response?.status()).toBe(200);
		await expect(page.locator('[data-console-panel-id]')).toHaveCount(PANELS.length);
		await expect(page.locator('[data-console-panel-id] > header > h3')).toHaveCount(PANELS.length);
		await expect(page.locator('[data-panel-query][data-machine-panel-state="loading"]')).toHaveCount(PANELS.length);
		await expect(page.locator('[data-panel-query] svg')).toHaveCount(PANELS.length);
		await expect(page.locator('[data-panel-query] svg rect:not([data-reserved-ground]), [data-panel-query] svg path')).toHaveCount(0);
		await expect(page.locator('[data-console-standing]')).toHaveText('');
		await expect(page.locator('[data-machine-refused], [data-cost-figures], [data-clock-pair], [data-fleet-job]')).toHaveCount(0);
		const html = await response!.text();
		expect(html).not.toMatch(/machineCounters:|machineRuns:|runShards:|RunManifest|RunPlan/);
	} finally {
		await context.close();
	}
});
