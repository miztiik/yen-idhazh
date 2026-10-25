/** The reader's real drawing keeps its text size, marks and geometry across loads. */
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { DigestDay, VisualData } from '../src/lib/payload/types';
import { drawVisual, statedDrawing } from '../src/lib/visual/bar';
import { storyChartGeometryConfig } from '../src/lib/server/config';
import { dayReady } from './support/day-ready';
import { formatNumber } from './support/number-format';
import { CANARY, newestDate, payloadOf } from './support/published';

test.use({ viewport: { width: 390, height: 844 } });
const geometry = storyChartGeometryConfig();

test('reader labels clear the text floor without scaling, and every mark survives navigation and reload', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('response', (response) => {
		if (response.status() === 404) errors.push(response.url());
	});
	const date = newestDate();
	const day = payloadOf(date) as unknown as DigestDay;
	const visuals = day.items.flatMap((item) =>
		item.visual?.state === 'rendered' && item.visual.data_path
			? [{ id: item.item_id, data: JSON.parse(readFileSync(
				join(CANARY, '..', item.visual.data_path), 'utf8'
			)) as VisualData }]
			: []
	);
	expect(visuals.length, 'the fixture must exercise an actual drawing').toBeGreaterThan(0);

	async function drawings(page: Page) {
		await dayReady(page);
		const stories = page.locator('article.item');
		for (let remaining = day.items.length; remaining > 0; remaining--) {
			if (await stories.count() === day.items.length) break;
			const before = await stories.count();
			await page.locator('[data-pager-scripted]').click();
			await expect.poll(() => stories.count()).toBeGreaterThan(before);
		}
		await expect(stories).toHaveCount(day.items.length);
		await page.evaluate(() => document.fonts.ready);
		const snapshots = [];
		for (const { id, data } of visuals) {
			const story = page.locator('article.item').and(page.locator(`[id="${id}"]`));
			await story.scrollIntoViewIfNeeded();
			const figure = story.getByRole('img');
			const svg = figure.locator('svg');
			await expect(svg).toBeVisible();
			// A floored content width may leave less than one CSS pixel unused.
			await expect.poll(() => svg.evaluate((node) => {
				const parent = node.parentElement!;
				const style = getComputedStyle(parent);
				const room = parent.getBoundingClientRect().width -
					parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) -
					parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth);
				return Number(node.getAttribute('width')) === Math.floor(room);
			})).toBe(true);
			const measured = await svg.evaluate((node) => {
				const probe = document.createElement('span');
				probe.style.fontSize = 'var(--text-xs)';
				node.parentElement!.append(probe);
				const floor = parseFloat(getComputedStyle(probe).fontSize);
				probe.remove();
				const svg = node as SVGSVGElement;
				const transform = svg.getScreenCTM()!;
				return {
					width: svg.getBoundingClientRect().width,
					drawnWidth: svg.viewBox.baseVal.width,
					scale: [transform.a, transform.b, transform.c, transform.d],
					floor,
					text: [...svg.querySelectorAll('text')].map((text) => ({
						value: text.textContent,
						size: parseFloat(getComputedStyle(text).fontSize),
						x: text.x.baseVal.getItem(0).value,
						y: text.y.baseVal.getItem(0).value
					})),
					bars: [...svg.querySelectorAll('rect')].map((bar) =>
						['x', 'y', 'width', 'height'].map((key) => Number(bar.getAttribute(key)))
					)
				};
			});
			expect(measured.width).toBe(measured.drawnWidth);
			expect(measured.scale).toEqual([1, 0, 0, 1]);
			expect(measured.floor).toBeGreaterThan(0);
			expect(measured.text.length).toBeGreaterThan(0);
			for (const text of measured.text) {
				expect(text.size, `${id}: ${text.value}`).toBeGreaterThanOrEqual(measured.floor);
			}
			const expected = drawVisual(data, measured.width, formatNumber, geometry);
			const emphasized = svg.locator(
				'rect.bar.emphasized, circle.dot.emphasized, circle.slope-point.emphasized'
			);
			await expect(emphasized).toHaveCount(1);
			const styles = await svg.locator('rect.bar, circle.dot, line.slope-line, circle.slope-point').evaluateAll((marks) => marks.map((mark) => {
				const style = getComputedStyle(mark);
				return {
					selected: mark.classList.contains('emphasized'),
					fill: style.fill,
					stroke: style.stroke,
					dashes: style.strokeDasharray,
					strokeWidth: mark.getAttribute('stroke-width')
				};
			}));
			const selected = styles.find((style) => style.selected)!;
			expect(selected.strokeWidth).toBe(String(geometry.mark_outline_width_px));
			for (const sibling of styles.filter((style) => !style.selected)) {
				expect(selected.fill).not.toBe(sibling.fill);
			}
			const heading = figure.locator('.chart-title');
			const caption = figure.locator('figcaption');
			await expect(heading).toHaveCount(data.title ? 1 : 0);
			await expect(caption).toHaveCount(data.caption ? 1 : 0);
			if (data.title) await expect(heading).toHaveText(data.title);
			if (data.caption) await expect(caption).toHaveText(data.caption);
			if (expected.type === 'bar') {
				expect(measured.text.map((text) => text.value)).toEqual([
					...expected.bars.flatMap((bar) => [bar.name, bar.displayed]),
					...(expected.unit ? [expected.unit] : [])
				]);
				expect(measured.bars).toEqual(expected.bars.map((bar) =>
					[0, bar.y, bar.width, bar.height]
				));
			} else if (expected.type === 'dot') {
				const dots = await svg.locator('circle.dot').evaluateAll((marks) =>
					marks.map((dot) => ['cx', 'cy', 'r'].map((key) => Number(dot.getAttribute(key))))
				);
				expect(dots).toEqual(expected.dots.map((dot) => [dot.x, dot.y, dot.radius]));
				expect(measured.text.map((text) => text.value)).toEqual([
					...expected.dots.flatMap((dot) => [dot.name, dot.displayed]),
					...(expected.unit ? [expected.unit] : [])
				]);
			} else {
				const lines = await svg.locator('line.slope-line').evaluateAll((marks) =>
					marks.map((line) => ['x1', 'y1', 'x2', 'y2'].map((key) => Number(line.getAttribute(key))))
				);
				expect(lines).toEqual(expected.slopes.map((slope) =>
					[slope.left.x, slope.left.y, slope.right.x, slope.right.y]
				));
				expect(measured.text.map((text) => text.value)).toEqual([
					expected.leftLabel,
					expected.rightLabel,
					...expected.slopes.flatMap((slope) => [
						slope.left.displayed,
						slope.right.displayed
					]),
					...(expected.unit ? [expected.unit] : [])
				]);
			}
			await expect(figure).toHaveAccessibleName(statedDrawing(expected));
			await figure.focus();
			await expect(figure).toBeFocused();
			snapshots.push(measured);
		}
		return snapshots;
	}

	await page.goto(`/${date}/`);
	for (const viewport of [
		{ width: 390, height: 844 },
		{ width: 1440, height: 900 }
	]) {
		await page.setViewportSize(viewport);
		await page.goto(`/${date}/`);
		const first = await drawings(page);
		await page.locator('a[href="/archive/"]').first().click();
		await expect(page.locator('main')).toBeVisible();
		await expect(page).toHaveURL(/\/archive\/$/);
		await page.goBack();
		expect(await drawings(page)).toEqual(first);
		await page.reload();
		expect(await drawings(page)).toEqual(first);
	}
	expect(errors).toEqual([]);
});

test('a failed chart load leaves only the story text without marking chartless stories', async ({ page }) => {
	const errors: string[] = [];
	const failedVisualRequests: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));

	const date = newestDate();
	const day = payloadOf(newestDate()) as unknown as DigestDay;
	const chartStory = day.items.filter((item) =>
		item.visual?.state === 'rendered' && typeof item.visual.data_path === 'string'
	).at(-1);
	const chartlessStory = day.items.find((item) => item.visual === null);
	if (!chartStory?.visual || typeof chartStory.visual.data_path !== 'string') {
		throw new Error('the canary day has no published chart to fail');
	}
	if (!chartlessStory) throw new Error('the canary day has no intentionally chartless story');

	const chartPath = chartStory.visual.data_path;
	page.on('requestfailed', (request) => {
		if (request.url().endsWith(`/${chartPath}`)) failedVisualRequests.push(request.url());
	});
	await page.goto(`/${date}/`);
	await dayReady(page);
	const story = page.locator('article.item').and(page.locator(`[id="${chartStory.item_id}"]`));
	await story.scrollIntoViewIfNeeded();
	await expect(story.getByRole('img')).toBeVisible();

	await page.locator('a[href="/archive/"]').first().click();
	await expect(page).toHaveURL(/\/archive\/$/);
	const session = await page.context().newCDPSession(page);
	await session.send('Network.clearBrowserCache');
	await session.detach();
	await page.context().setOffline(true);
	await page.locator(`a[href="/${date}/"]`).first().click();
	await page.waitForURL(`**/${date}/`);
	await dayReady(page);
	const returningStory = page.locator('article.item').and(
		page.locator(`[id="${chartStory.item_id}"]`)
	);
	await returningStory.scrollIntoViewIfNeeded();
	await expect(returningStory.locator('.title')).toBeVisible();
	await expect(returningStory.locator('.title')).toContainText(chartStory.title);
	await expect(returningStory.locator('figure, [role="status"]')).toHaveCount(0);
	await expect(returningStory.getByRole('button', { name: 'Try again' })).toHaveCount(0);
	await expect.poll(() => failedVisualRequests.length).toBeGreaterThan(0);

	const chartless = page.locator('article.item').and(
		page.locator(`[id="${chartlessStory.item_id}"]`)
	);
	await expect(chartless.locator('.title')).toBeVisible();
	await expect(chartless.locator('.title')).toContainText(chartlessStory.title);
	await expect(chartless.locator('figure, [role="status"]')).toHaveCount(0);
	expect(errors).toEqual([]);
});

test('the reader surface stays still as it loads and gains no page animation under reduced motion', async ({ page }) => {
	const date = newestDate();
	const day = payloadOf(date) as unknown as DigestDay;

	async function runningAnimations(page: Page) {
		await dayReady(page);
		return page.evaluate(() =>
			document.getAnimations().filter((animation) =>
				animation.playState === 'running'
			).length
		);
	}

	await page.goto(`/${date}/`);
	const first = await runningAnimations(page);
	expect(first).toBe(0);
	const stories = page.locator('article.item');
	for (let remaining = day.items.length; remaining > 0; remaining--) {
		if (await stories.count() === day.items.length) break;
		const before = await stories.count();
		await page.locator('[data-pager-scripted]').click();
		await expect.poll(() => stories.count()).toBeGreaterThan(before);
	}
	await expect(stories).toHaveCount(day.items.length);
	expect(await runningAnimations(page)).toBe(0);

	await page.locator('a[href="/archive/"]').first().click();
	await expect(page.locator('main')).toBeVisible();
	await expect(page).toHaveURL(/\/archive\/$/);
	await page.goBack();
	expect(await runningAnimations(page)).toBe(0);

	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.reload();
	expect(await runningAnimations(page)).toBe(0);
});
