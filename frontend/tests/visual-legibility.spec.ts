/** The reader's real drawing keeps its text size, marks and geometry across loads. */
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { DigestDay, VisualData } from '../src/lib/payload/types';
import { drawBars, statedBars } from '../src/lib/visual/bar';
import { dayReady } from './support/day-ready';
import { formatNumber } from './support/number-format';
import { CANARY, newestDate, payloadOf } from './support/published';

test.use({ viewport: { width: 390, height: 844 } });

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
			const expected = drawBars(data, measured.width, formatNumber);
			const emphasized = svg.locator('rect.emphasized');
			await expect(emphasized).toHaveCount(1);
			const styles = await svg.locator('rect').evaluateAll((bars) => bars.map((bar) => {
				const style = getComputedStyle(bar);
				return {
					selected: bar.classList.contains('emphasized'),
					fill: style.fill,
					stroke: style.stroke,
					dashes: style.strokeDasharray
				};
			}));
			const selected = styles.find((style) => style.selected)!;
			for (const sibling of styles.filter((style) => !style.selected)) {
				expect(selected.fill).not.toBe(sibling.fill);
				expect(selected.stroke).not.toBe(sibling.stroke);
				expect(selected.dashes).not.toBe(sibling.dashes);
			}
			const heading = figure.locator('.chart-title');
			const caption = figure.locator('figcaption');
			await expect(heading).toHaveCount(data.title ? 1 : 0);
			await expect(caption).toHaveCount(data.caption ? 1 : 0);
			if (data.title) await expect(heading).toHaveText(data.title);
			if (data.caption) await expect(caption).toHaveText(data.caption);
			expect(measured.text.map((text) => text.value)).toEqual([
				...expected.bars.flatMap((bar) => [bar.name, bar.displayed]),
				...(expected.unit ? [expected.unit] : [])
			]);
			expect(measured.bars).toEqual(expected.bars.map((bar) =>
				[0, bar.y, bar.width, bar.height]
			));
			await expect(figure).toHaveAccessibleName(statedBars(expected));
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
