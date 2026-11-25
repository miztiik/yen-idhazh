/** The reader's real drawing keeps its text size, marks and geometry across loads. */
import { expect, test, type Locator, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { DigestDay, VisualData } from '../src/lib/payload/types';
import { drawVisual, statedDrawing } from '../src/lib/visual/bar';
import { chartConfig, storyChartGeometryConfig } from '../src/lib/server/config';
import { fitChartGeometry, fitChartTicks } from '../src/lib/visual/viewport';
import { isChartKind } from '../src/lib/payload/project';
import { dayReady } from './support/day-ready';
import { formatNumber, numberFormat } from './support/number-format';
import { CANARY, newestDate, payloadOf } from './support/published';

test.use({ viewport: { width: 390, height: 844 } });
const geometry = storyChartGeometryConfig();

async function checkComparison(figure: Locator, data: VisualData) {
	const held = new Map(data.marks.map((mark) => [mark.mark_id, mark]));
	const readings = data.encoding.quantity.map((id, index) => {
		const quantity = held.get(id)!;
		const category = held.get(data.encoding.category[index])!.text!;
		const series = held.get(data.encoding.series[index])?.text;
		return {
			name: series && series !== category ? `${category} (${series})` : category,
			stated: quantity.value!,
			unit: quantity.unit
		};
	});
	if (data.type === 'bar') readings.sort((a, b) => Number(b.stated) - Number(a.stated));
	const groups = figure.locator('.comparison-row');
	await expect(groups).toHaveCount(readings.length);
	await expect(figure.locator('.chart-title dl')).toHaveCount(0);
	if (new Set(data.encoding.series.map((id) => held.get(id)!.text)).size <= 1) {
		await expect(figure.locator('ul')).toHaveCount(0);
	}
	for (const [index, { name, stated, unit }] of readings.entries()) {
		const group = groups.nth(index);
		const value = unit ? `${stated} ${unit}` : stated;
		await expect(group.locator('.name')).toHaveText(name);
		await expect(group.locator('.figure')).toHaveText(value);
		await expect(group.locator('rect.bar title, circle.dot title')).toContainText(`${name} ${value}`);
	}

	const result = await figure.evaluate((node) => {
		const plot = node.querySelector<SVGSVGElement>('svg')!;
		const separated = (first: DOMRect, second: DOMRect) =>
			first.right <= second.left || second.right <= first.left ||
			first.bottom <= second.top || second.bottom <= first.top;
		return {
			noOverlap: [...plot.querySelectorAll('.comparison-row')].every((row) => {
				const name = row.querySelector('.name')!.getBoundingClientRect();
				const reading = row.querySelector('.figure')!.getBoundingClientRect();
				const mark = row.querySelector('rect.bar, circle.dot')!.getBoundingClientRect();
				return separated(name, reading) && separated(name, mark) && separated(reading, mark);
			}),
			labelsFit: [...plot.querySelectorAll<SVGTextElement>('text')].every((text) => {
				const { x, y, width, height } = text.getBBox();
				return x >= 0 && x + width <= plot.viewBox.baseVal.width &&
					y >= 0 && y + height <= plot.viewBox.baseVal.height;
			}),
			noOverflow: node.scrollWidth <= node.clientWidth &&
				document.documentElement.scrollWidth <= document.documentElement.clientWidth
		};
	});
	expect(result).toEqual({ noOverlap: true, labelsFit: true, noOverflow: true });
}

test('reader labels clear the text floor without scaling, and every mark survives navigation and reload', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('response', (response) => {
		if (response.status() === 404) errors.push(response.url());
	});
	await page.addInitScript(() => {
		window.addEventListener('error', (event) => {
			console.error(`[reader] ${event.message}`);
		});
	});
	const date = newestDate();
	const day = payloadOf(date) as unknown as DigestDay;
	const visuals = day.items.flatMap((item) =>
		item.visual?.state === 'rendered' && isChartKind(item.visual.kind) && item.visual.data_path
			? [{ id: item.item_id, path: item.visual.data_path, data: JSON.parse(readFileSync(
				join(CANARY, '..', item.visual.data_path), 'utf8'
			)) as VisualData }]
			: []
	);
	expect(visuals.length, 'the fixture must exercise an actual drawing').toBeGreaterThan(0);
	const axisCharts = visuals.filter(({ data }) => data.type !== 'stacked_bar');
	const comparisonId = axisCharts.find(({ data }) =>
		data.type === 'bar' && data.marks.some((mark) => mark.unit)
	)?.id;
	if (!comparisonId) throw new Error('the canary must include a bar comparison with a reported unit');
	const relationshipTitles = { x: 'Installed wind capacity', y: 'Annual electricity output' };
	for (const { id, path, data } of axisCharts) {
		const axis_titles = id === comparisonId
			? { x: 'Country', y: 'Reported wind capacity' }
			: data.type === 'bubble' ? relationshipTitles : null;
		if (axis_titles) {
			await page.route((url) => url.pathname.endsWith(`/${path}`), (route) =>
				route.fulfill({ json: { ...data, axis_titles } }));
		}
	}

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
		for (const { id, data } of axisCharts) {
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
					drawnHeight: svg.viewBox.baseVal.height,
					scale: [transform.a, transform.b, transform.c, transform.d],
					floor,
					plotRoom: (() => {
						const figure = svg.parentElement!;
						const style = getComputedStyle(figure);
						const shell = document.querySelector('[data-filter-bar]');
						const shellStyle = shell ? getComputedStyle(shell) : null;
						const occlusion = shell && shellStyle?.position === 'sticky'
							? shell.getBoundingClientRect().height + (parseFloat(shellStyle.top) || 0) : 0;
						const furniture = figure.getBoundingClientRect().height - svg.getBoundingClientRect().height +
							parseFloat(style.marginTop) + parseFloat(style.marginBottom);
						return {
							height: Math.max(0, (window.visualViewport?.height ?? window.innerHeight) - occlusion - furniture),
							textHeight: svg.querySelector<SVGTextElement>('text')!.getBBox().height
						};
					})(),
					text: [...svg.querySelectorAll('text')].map((text) => ({
						value: text.textContent,
						size: parseFloat(getComputedStyle(text).fontSize),
						x: text.x.baseVal.getItem(0).value,
						y: text.y.baseVal.getItem(0).value
					})),
					valueTickBounds: [...svg.querySelectorAll<SVGTextElement>('text.value-tick')].map((text) => {
						const { x, y, width, height } = text.getBBox();
						return { x, y, width, height };
					}),
					bars: [...svg.querySelectorAll('rect')].map((bar) =>
						['x', 'y', 'width', 'height'].map((key) => Number(bar.getAttribute(key)))
					),
					lines: [...svg.querySelectorAll('path.series-line')].map((line) => ({
						path: line.getAttribute('d'),
						dasharray: line.getAttribute('stroke-dasharray')
					})),
					points: [...svg.querySelectorAll('circle.line-point')].map((point) =>
						['cx', 'cy'].map((key) => Number(point.getAttribute(key)))
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
			for (const bounds of measured.valueTickBounds) {
				expect(bounds.x, `${id}: value tick clears the left edge`).toBeGreaterThanOrEqual(0);
				expect(bounds.x + bounds.width, `${id}: value tick clears the right edge`)
					.toBeLessThanOrEqual(measured.drawnWidth);
				expect(bounds.y, `${id}: value tick clears the top edge`).toBeGreaterThanOrEqual(0);
				expect(bounds.y + bounds.height, `${id}: value tick clears the bottom edge`)
					.toBeLessThanOrEqual(measured.drawnHeight);
			}
			const fittedGeometry = fitChartGeometry(data, geometry, measured.plotRoom);
			const expected = drawVisual(
				data,
				measured.width,
				formatNumber,
				numberFormat,
				fitChartTicks(data, fittedGeometry, measured.plotRoom.textHeight, chartConfig().tick_density),
				fittedGeometry
			);
			if (expected.type !== 'bar' && expected.type !== 'dot') {
				const emphasized = svg.locator(
					'circle.slope-point.emphasized, circle.line-point.emphasized, circle.scatter-point.emphasized, circle.bubble-point.emphasized'
				);
				await expect(emphasized).toHaveCount(1);
				const styles = await svg.locator('line.slope-line, circle.slope-point, path.series-line, circle.line-point, circle.scatter-point, circle.bubble-point').evaluateAll((marks) => marks.map((mark) => {
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
			}
			const heading = figure.locator('.chart-title');
			const caption = figure.locator('figcaption');
			await expect(heading).toHaveCount(data.title ? 1 : 0);
			await expect(caption).toHaveCount(data.caption ? 1 : 0);
			if (data.title) await expect(heading).toHaveText(data.title);
			if (data.caption) await expect(caption).toHaveText(data.caption);
			await expect(figure.getByText(/^(Horizontal|Vertical):$/)).toHaveCount(0);
			if (expected.type === 'bar' || expected.type === 'dot') {
				await checkComparison(figure, data);
				if (id === comparisonId) {
					const narrow = page.viewportSize()!.width === 390;
					await expect(svg.locator('[data-comparison-orientation]'))
						.toHaveAttribute('data-comparison-orientation', narrow ? 'horizontal' : 'vertical');
					if (!narrow) await expect(svg.locator('.tick')).toHaveCount(await svg.locator('.guide').count());
					const lengths = measured.bars.map(([, , width, height]) => narrow ? width : height);
					expect(new Set(lengths).size).toBeGreaterThan(1);
					const origins = measured.bars.map(([x, y, , height]) => narrow ? x : y + height);
					for (const origin of origins) expect(origin).toBeCloseTo(origins[0]);
				}
			} else if (expected.type === 'slope') {
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
			} else if (expected.type === 'bubble') {
				const points = await svg.locator('circle.bubble-point').evaluateAll((marks) =>
					marks.map((point) => ['cx', 'cy', 'r'].map((key) => Number(point.getAttribute(key))))
				);
				expect(points).toEqual(expected.points.map((point) => [point.cx, point.cy, point.radius]));
				await expect(svg.locator('xpath=preceding-sibling::*[1][@data-scale="y"]'))
					.toContainText(relationshipTitles.y);
				await expect(svg.locator('xpath=following-sibling::*[1][@data-scale="x"]'))
					.toContainText(relationshipTitles.x);
				await expect(figure.locator('.bubble-size-key')).toContainText(
					`Circle area represents ${expected.sizeUnit}`
				);
				for (const point of expected.points) {
					await expect(figure.locator('.bubble-readings')).toContainText(point.label);
					await expect(figure.locator('.bubble-readings')).toContainText(`x ${point.displayedX}`);
					await expect(figure.locator('.bubble-readings')).toContainText(`y ${point.displayedY}`);
					await expect(figure.locator('.bubble-readings')).toContainText(`area ${point.displayedSize}`);
				}
			} else if (expected.type === 'scatter') {
				const points = await svg.locator('circle.scatter-point').evaluateAll((marks) =>
					marks.map((point) => ['cx', 'cy'].map((key) => Number(point.getAttribute(key))))
				);
				expect(points).toEqual(expected.points.map((point) => [point.cx, point.cy]));
				for (const point of expected.points) {
					await expect(figure.locator('.scatter-readings')).toContainText(point.label);
					await expect(figure.locator('.scatter-readings')).toContainText(`x ${point.displayedX}`);
					await expect(figure.locator('.scatter-readings')).toContainText(`y ${point.displayedY}`);
				}
			} else if (expected.type === 'line') {
				expect(measured.valueTickBounds.length).toBeGreaterThan(0);
				expect(measured.lines).toEqual(expected.lines.map((line) => ({
					path: line.path,
					dasharray: line.dasharray
				})));
				expect(measured.points).toEqual(expected.lines.flatMap((line) =>
					line.points.map((point) => [point.x, point.y])
				));
				if (expected.lines.length > 1) {
					const legend = await svg.locator('.line-legend-mark line').evaluateAll((marks) =>
						marks.map((line) => line.getAttribute('stroke-dasharray'))
					);
					expect(legend).toEqual(expected.lines.map((line) => line.dasharray));
				}
				expect(measured.text.map((text) => text.value)).toEqual([
					...expected.axis.ticks
						.filter((tick) => tick.text !== '')
						.map((tick) => tick.text),
					...expected.ticks.map((tick) => tick.text),
					...(expected.unit ? [expected.unit] : [])
				]);
			}
			const stated = statedDrawing(expected);
			await expect(figure).toHaveAccessibleName(expected.type === 'bubble'
				? `${stated} x: ${relationshipTitles.x}. y: ${relationshipTitles.y}.`
				: stated);
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
	const relationship = page.locator('figure.visual').filter({
		has: page.locator('circle.scatter-point, circle.bubble-point')
	});
	const relationshipData = axisCharts.find(({ data }) =>
		data.type === 'scatter' || data.type === 'bubble'
	)?.data;
	if (!relationshipData) throw new Error('the fixture must include a relationship drawing');
	const relationshipSvg = relationship.locator(':scope > svg');

	async function waitForFittedRelationship() {
		await expect.poll(async () => {
			const measured = await relationshipSvg.evaluate((node) => {
				const svg = node as SVGSVGElement;
				const figure = svg.parentElement!;
				const style = getComputedStyle(figure);
				const shell = document.querySelector('[data-filter-bar]');
				const shellStyle = shell ? getComputedStyle(shell) : null;
				const occlusion = shell && shellStyle?.position === 'sticky'
					? shell.getBoundingClientRect().height + (parseFloat(shellStyle.top) || 0) : 0;
				const furniture = figure.getBoundingClientRect().height - svg.getBoundingClientRect().height +
					parseFloat(style.marginTop) + parseFloat(style.marginBottom);
				const text = svg.querySelector('text');
				return {
					height: Number(svg.getAttribute('height')),
					room: {
						height: Math.max(0, (window.visualViewport?.height ?? window.innerHeight) - occlusion - furniture),
						textHeight: text ? text.getBBox().height : parseFloat(style.fontSize)
					}
				};
			});
			return measured.height === fitChartGeometry(relationshipData!, geometry, measured.room).scatter_height_px;
		}).toBe(true);
	}

	await relationship.scrollIntoViewIfNeeded();
	await waitForFittedRelationship();
	const accessible = await relationship.getAttribute('aria-label');
	const before = await relationshipSvg.getAttribute('height');
	await page.setViewportSize({ width: 1440, height: 360 });
	await expect.poll(() => relationshipSvg.getAttribute('height')).not.toBe(before);
	await waitForFittedRelationship();
	await expect(relationship).toHaveAttribute('aria-label', accessible!);
	const shortHeight = await relationshipSvg.getAttribute('height');
	await page.evaluate(() => window.scrollTo(0, 0));
	await expect(relationshipSvg).toHaveAttribute('height', shortHeight!);
	expect(await relationship.evaluate((node) => node.scrollHeight <= node.clientHeight)).toBe(true);
	await page.setViewportSize({ width: 1440, height: 900 });
	await waitForFittedRelationship();
	await expect(relationshipSvg).toHaveAttribute('height', before!);
	const wideWidth = Number(await relationshipSvg.getAttribute('width'));
	const pointCount = await relationship.locator('circle.scatter-point, circle.bubble-point').count();
	await page.setViewportSize({ width: 390, height: 900 });
	await expect.poll(async () => Number(await relationshipSvg.getAttribute('width')))
		.toBeLessThan(wideWidth);
	await expect(relationship.locator('circle.scatter-point, circle.bubble-point'))
		.toHaveCount(pointCount);
	expect(errors).toEqual([]);
});

test('a failed chart load leaves only the story text without marking chartless stories', async ({ page }) => {
	const errors: string[] = [];
	const failedVisualRequests: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));

	const date = newestDate();
	const day = payloadOf(newestDate()) as unknown as DigestDay;
	const chartStory = day.items.filter((item) =>
		item.visual?.state === 'rendered' &&
		isChartKind(item.visual.kind) &&
		typeof item.visual.data_path === 'string'
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
	await page.locator('.dates > summary').click();
	await page.getByLabel('From (UTC)').fill(date);
	await page.getByLabel('To (UTC)').fill(date);
	await page.getByRole('button', { name: 'Search', exact: true }).click();
	const dayLink = page.locator(`[data-story-list="rows"] a[href^="/${date}/#"]`).first();
	await expect(dayLink).toBeVisible();
	const session = await page.context().newCDPSession(page);
	await session.send('Network.clearBrowserCache');
	await session.detach();
	await page.context().setOffline(true);
	await dayLink.click();
	await page.waitForURL((url) => url.pathname === `/${date}/`);
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
				animation instanceof CSSAnimation && animation.playState === 'running'
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

test('the published stacked bar stays readable inside a short, narrow story card', async ({ page }) => {
	const date = newestDate();
	const day = payloadOf(date) as unknown as DigestDay;
	const item = day.items.find((entry) => {
		if (
			entry.visual?.state !== 'rendered' ||
			!isChartKind(entry.visual.kind) ||
			!entry.visual.data_path
		) return false;
		const data = JSON.parse(readFileSync(join(CANARY, '..', entry.visual.data_path), 'utf8')) as VisualData;
		return data.type === 'stacked_bar';
	});
	if (!item?.visual?.data_path) throw new Error('the canary day has no published stacked bar');
	const data = JSON.parse(readFileSync(join(CANARY, '..', item.visual.data_path), 'utf8')) as VisualData;
	if (data.type !== 'stacked_bar') throw new Error('the canary stack has the wrong chart family');
	const labels = data.encoding.series.map((id) => {
		const text = data.marks.find((mark) => mark.mark_id === id)?.text;
		if (!text) throw new Error(`stacked-bar series ${id} has no source label`);
		return text;
	});
	const expectedSegments = data.encoding.quantity.map((id, index) => {
		const mark = data.marks.find((candidate) => candidate.mark_id === id);
		if (mark?.value === null || mark?.value === undefined) {
			throw new Error(`stacked-bar quantity ${id} has no source value`);
		}
		return `${labels[index]}: ${mark.value}`;
	});

	for (const viewport of [
		{ width: 390, height: 360 },
		{ width: 1440, height: 360 }
	]) {
		await page.setViewportSize(viewport);
		await page.goto(`/${date}/`);
		await dayReady(page);
		await page.evaluate(() => document.fonts.ready);
		const stories = page.locator('article.item');
		for (let remaining = day.items.length; remaining > 0; remaining--) {
			if (await stories.count() === day.items.length) break;
			const before = await stories.count();
			await page.locator('[data-pager-scripted]').click();
			await expect.poll(() => stories.count()).toBeGreaterThan(before);
		}
		await expect(stories).toHaveCount(day.items.length);
		const story = page.locator('article.item').and(page.locator(`[id="${item.item_id}"]`));
		await story.scrollIntoViewIfNeeded();
		const figure = story.getByRole('img');
		await expect(figure).toBeVisible();
		await expect(figure.locator('.parts-rows > li')).toHaveCount(1);
		await expect(figure.locator('.parts-segment')).toHaveCount(data.encoding.quantity.length);
		await expect(figure.locator('.parts-total')).toHaveCount(0);
		expect(await figure.locator('.parts-segment').evaluateAll((segments) =>
			segments.map((segment) => segment.getAttribute('aria-label'))
		)).toEqual(expectedSegments);
		expect(await figure.locator('.parts-segment.emphasized').count()).toBe(1);
		for (const part of labels) {
			await expect(figure.locator(`[data-readout-row="${part}"]`)).toContainText(/10 MW/);
		}
		const label = await figure.getAttribute('aria-label');
		expect(label).toBeTruthy();
		for (const part of labels) expect(label).toContain(part);
		const measured = await figure.evaluate((node) => {
			const probe = document.createElement('span');
			probe.style.fontSize = 'var(--text-xs)';
			node.append(probe);
			const floor = parseFloat(getComputedStyle(probe).fontSize);
			probe.remove();
			const track = node.querySelector('.parts-track')!.getBoundingClientRect();
			const text = [...node.querySelectorAll('.parts-name, .readout-label, .readout-value')];
			return {
				floor,
				textSizes: text.map((part) => parseFloat(getComputedStyle(part).fontSize)),
				segmentsFit: [...node.querySelectorAll<HTMLElement>('.parts-segment')].map((part) => {
					const bounds = part.getBoundingClientRect();
					return bounds.left >= track.left && bounds.right <= track.right;
				}),
				segmentBoundaries: [...node.querySelectorAll<HTMLElement>('.parts-segment')].map((part) => ({
					width: getComputedStyle(part).borderInlineEndWidth,
					style: getComputedStyle(part).borderInlineEndStyle
				})),
				widthFits: node.scrollWidth <= node.clientWidth,
				heightFits: node.scrollHeight <= node.clientHeight
			};
		});
		expect(measured.textSizes.length).toBeGreaterThan(0);
		expect(measured.textSizes.every((size) => size >= measured.floor)).toBe(true);
		expect(measured.segmentsFit).toEqual([true, true, true]);
		expect(measured.segmentBoundaries).toEqual([
			{ width: '1px', style: 'solid' },
			{ width: '1px', style: 'solid' },
			{ width: '1px', style: 'solid' }
		]);
		expect(measured.widthFits).toBe(true);
		expect(measured.heightFits).toBe(true);
	}
});
