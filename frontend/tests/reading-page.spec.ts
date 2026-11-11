import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { BuildRecord } from '../scripts/build-state';
import { isVisualData } from '../src/lib/payload/drawing';
import { isWhowhatGridData } from '../src/lib/payload/whowhat-grid';
import type { DigestDay, WhowhatGridData } from '../src/lib/payload/types';
import { dayReady } from './support/day-ready';
import { CANARY, newestDate } from './support/published';
import { uiConfig } from '../src/lib/server/config';

/** One reading journey covers the shared shell; never expand it into route or presentation matrices. */
test('a reader can load stories, filter the day and keep the layout usable on a phone', async ({ page }) => {
	const errors: string[] = [];
	const expectedMissing = new Set<string>();
	const missingResponses: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	page.on('console', (message) => {
		if (message.type() === 'error' && !expectedMissing.has(message.location().url)) {
			errors.push(message.text());
		}
	});
	page.on('response', (response) => {
		if (response.status() !== 404) return;
		if (expectedMissing.has(response.url())) missingResponses.push(response.url());
		else errors.push(`404 ${response.url()}`);
	});
	await page.addInitScript(() => {
		window.addEventListener('error', (event) => {
			console.error(`[reader] ${event.message}`);
		});
	});
	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto('/');
	await dayReady(page);
	const stories = page.locator('article.item');
	await expect(stories.first()).toBeVisible();
	await expect(stories.first().locator('[data-item-summary]').first()).not.toBeEmpty();
	const before = await stories.count();
	expect(before).toBeGreaterThan(1);
	const title = await stories.first().getByRole('heading').innerText();
	expect(title.trim()).not.toBe('');
	const widths = await page.evaluate(() => {
		const frame = document.querySelector<HTMLElement>('.frame')!;
		return {
			frame: frame.getBoundingClientRect().width,
			viewport: document.documentElement.clientWidth
		};
	});
	expect(widths.frame).toBeCloseTo(widths.viewport, 0);
	async function expectFullArticleWidth() {
		const geometry = await stories.first().evaluate((article) => {
			const body = article.querySelector<HTMLElement>('.item-body')!;
			const prose = article.querySelector<HTMLElement>('.prose')!;
			const stream = article.closest<HTMLElement>('.day-stream')!;
			const day = article.closest<HTMLElement>('.day')!;
			const style = getComputedStyle(article);
			return {
				day: day.getBoundingClientRect().width,
				stream: stream.getBoundingClientRect().width,
				card: article.getBoundingClientRect().width,
				body: body.getBoundingClientRect().width,
				prose: prose.getBoundingClientRect().width,
				rightInset: article.getBoundingClientRect().right - body.getBoundingClientRect().right,
				expectedInset: Number.parseFloat(style.paddingRight) + Number.parseFloat(style.borderRightWidth)
			};
		});
		expect(Math.abs(geometry.day - geometry.stream)).toBeLessThanOrEqual(1);
		expect(Math.abs(geometry.stream - geometry.card)).toBeLessThanOrEqual(1);
		expect(Math.abs(geometry.body - geometry.prose)).toBeLessThanOrEqual(1);
		expect(Math.abs(geometry.rightInset - geometry.expectedInset)).toBeLessThanOrEqual(1);
	}
	await expectFullArticleWidth();
	await expect(page.locator('[data-time-note]')).toHaveCount(0);
	await expect(stories.locator('[data-item-time]').first()).toContainText('UTC');

	await expect(page.locator('[data-leading]')).toBeVisible();
	const leading = await page.locator('[data-leading]').boundingBox();
	const firstStory = await stories.first().boundingBox();
	expect(leading!.y + leading!.height).toBeLessThanOrEqual(firstStory!.y);
	await page.setViewportSize({ width: 1280, height: 900 });
	await expectFullArticleWidth();
	await page.setViewportSize({ width: 1920, height: 1080 });
	const edition = page.getByRole('region', { name: 'About today' });
	await expect(edition.getByRole('heading', { level: 1 })).toBeVisible();
	await expect(edition).toContainText(/\d+ stories/);
	await expect(edition).toContainText(/Updated \d{2}:\d{2} UTC/);
	await expect(edition).not.toContainText('did not finish');
	await expect(edition).not.toContainText('added after');
	const editionText = await edition.innerText();
	await expect(page.locator('[data-site-tagline]')).toHaveCount(0);
	await expect(page.locator('[data-filter-note]')).toHaveCount(0);
	const searchOtherDays = page.getByRole('button', { name: 'Search other days' });
	await expect(searchOtherDays).toHaveCSS('clip-path', 'inset(50%)');
	const field = page.locator('#page-filter');
	await field.click();
	const original = await field.elementHandle();
	const position = await field.boundingBox();
	async function stableField() {
		await expect(field).toBeFocused();
		expect(await field.evaluate((node, first) => node === first, original)).toBe(true);
		const current = await field.boundingBox();
		expect(current?.x).toBe(position?.x);
		expect(current?.y).toBe(position?.y);
	}
	const prefix = title.slice(0, uiConfig().filter_min_chars + 1);
	for (const [index, character] of [...prefix].entries()) {
		await page.keyboard.insertText(character);
		await stableField();
		if (index === 0) {
			await expect(searchOtherDays).toBeVisible();
			await expect(page.locator('[data-search-block="day"]'))
				.toContainText('Searching other days downloads');
		}
	}
	await expect(page.locator('[data-leading]')).toHaveCount(0);
	await page.keyboard.insertText(title.slice(prefix.length));
	await expect.poll(() => stories.count()).toBeLessThan(before);
	await expect(stories.first().getByRole('heading')).toHaveText(title);
	await expectFullArticleWidth();
	await expect(searchOtherDays).toBeVisible();
	await expect(searchOtherDays).toHaveCSS('clip-path', 'none');
	await expect(page.locator('[data-filter-note]')).not.toContainText('Press Enter');
	await expect(edition).toHaveText(editionText);
	await page.keyboard.press('Home');
	await page.keyboard.press('ArrowRight');
	await page.keyboard.insertText('x');
	await stableField();
	expect(await field.evaluate((node: HTMLInputElement) => node.selectionStart)).toBe(2);
	await page.keyboard.press('Backspace');
	await page.keyboard.press('ControlOrMeta+A');
	await page.keyboard.press('Backspace');
	await stableField();
	await expect(page.locator('[data-leading]')).toBeVisible();
	await expect(stories.first()).toBeVisible();
	await expect(searchOtherDays).toHaveCSS('clip-path', 'inset(50%)');
	await expect(page.locator('[data-filter-note]')).toHaveCount(0);

	const build: BuildRecord = JSON.parse(readFileSync(
		join(process.cwd(), '..', 'backend', 'var', 'checks', 'build.json'), 'utf8'
	));
	let gridCase: {
		date: string; itemId: string; path: string; data: WhowhatGridData; plainItemId: string
	} | null = null;
	if (build.mode === 'canary') {
		const date = newestDate();
		const [year, month, day] = date.split('-');
		const response = await page.request.get(`/digest/${year}/${month}/${day}/digest.json`);
		expect(response.ok()).toBe(true);
		const published: DigestDay = await response.json();
		const chart = published.items.find((item) =>
			item.visual?.kind === 'chart' && item.visual.state === 'rendered'
		);
		const grid = published.items.find((item) =>
			item.visual?.kind === 'whowhat' && item.visual.state === 'rendered'
		);
		const plain = published.items.find((item) => item.visual === null);
		if (!chart?.visual?.data_path || !grid?.visual?.data_path || !plain) {
			throw new Error('the reader canary must carry a published chart, grid and no-visual story');
		}
		const chartResponse = await page.request.get(`/${chart.visual.data_path}`);
		expect(chartResponse.ok()).toBe(true);
		expect(isVisualData(await chartResponse.json())).toBe(true);
		const chartStory = page.locator(`article.item[id="${chart.item_id}"]`);
		await chartStory.scrollIntoViewIfNeeded();
		await expect(chartStory.getByRole('img')).toBeVisible();
		const gridResponse = await page.request.get(`/${grid.visual.data_path}`);
		expect(gridResponse.ok()).toBe(true);
		expect(await gridResponse.body()).toEqual(
			readFileSync(join(CANARY, '..', grid.visual.data_path))
		);
		const gridData: unknown = await gridResponse.json();
		if (!isWhowhatGridData(gridData, grid.item_id)) {
			throw new Error('the published canary grid was refused by the real reader');
		}
		const gridStory = page.locator(`article.item[id="${grid.item_id}"]`);
		await gridStory.scrollIntoViewIfNeeded();
		await expect(gridStory.locator('[data-whowhat-state]')).toHaveAttribute(
			'data-whowhat-state', 'ready'
		);
		await expect(gridStory.getByRole('columnheader')).toHaveText(['Who', 'What']);
		await expect(gridStory.locator('tbody td')).toHaveText(
			gridData.rows.flatMap((row) => [row.actor?.display_text ?? '', row.claim?.span_excerpt ?? ''])
		);
		const shortRow = gridData.rows.find((row) =>
			row.actor && row.actor.display_text === row.actor.span_excerpt
		);
		if (!shortRow?.actor) throw new Error('the canary grid must carry an unclipped actor');
		const fullActor = 'The regional transport committee for the northern district';
		const fullClaim = `${fullActor} said services will resume only after the independent safety review is complete.`;
		const fittedPrefix = 'The regional transport committee...';
		const longGrid: WhowhatGridData = {
			...gridData,
			rows: [{
				actor: {
					kind: 'entity', element_id: `entity-0-${fullActor.length}`,
					sentence_index: 0, span_start: 0, span_end: fullActor.length,
					span_excerpt: fullActor, display_text: fittedPrefix
				},
				claim: {
					kind: 'claim', element_id: `claim-0-${fullClaim.length}`,
					sentence_index: 0, span_start: 0, span_end: fullClaim.length,
					span_excerpt: fullClaim, display_text: fittedPrefix
				}
			}, shortRow, { actor: null, claim: null }]
		};
		expect(isWhowhatGridData(longGrid, grid.item_id)).toBe(true);
		const assetUrl = new URL(`/${grid.visual.data_path}`, page.url()).href;
		await page.route(assetUrl, (route) => route.fulfill({
			contentType: 'application/json', body: JSON.stringify(longGrid)
		}));
		await page.reload();
		await dayReady(page);
		await gridStory.scrollIntoViewIfNeeded();
		const cells = gridStory.locator('tbody tr').first().getByRole('cell');
		await expect(cells.nth(1)).toHaveText(fullClaim);
		await expect(gridStory.getByText(fullClaim, { exact: true })).toBeVisible();
		await expect(cells.nth(1).locator('details, summary, [title]')).toHaveCount(0);
		await expect(cells.nth(1)).not.toHaveAttribute('title');
		const actorDetails = cells.first().locator('details');
		const actorSummary = actorDetails.locator('summary');
		const actorExcerpt = actorDetails.getByText(fullActor, { exact: true });
		await expect(actorSummary).toHaveText(fittedPrefix);
		await expect(actorExcerpt).toBeHidden();
		await actorSummary.focus();
		await expect(actorSummary).toBeFocused();
		await page.keyboard.press('Enter');
		await expect(actorDetails).toHaveAttribute('open', '');
		await expect(actorExcerpt).toBeVisible();
		await page.keyboard.press('Space');
		await expect(actorExcerpt).toBeHidden();
		const shortActor = gridStory.locator('tbody tr').nth(1).getByRole('cell').first();
		await expect(shortActor).toHaveText(shortRow.actor.display_text);
		await expect(shortActor.locator('details')).toHaveCount(0);
		await expect(gridStory.locator('tbody tr').last().getByRole('cell')).toHaveText(['', '']);
		await page.unroute(assetUrl);
		const plainStory = page.locator(`article.item[id="${plain.item_id}"]`);
		await expect(plainStory.locator('[data-item-summary]').first()).not.toBeEmpty();
		await expect(plainStory.locator('figure, [data-whowhat-state], [role="status"]')).toHaveCount(0);
		gridCase = {
			date, itemId: grid.item_id, path: grid.visual.data_path, data: gridData,
			plainItemId: plain.item_id
		};
	}

	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.locator('#page-filter')).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);

	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto('/archive/');
	expect(await page.locator('.frame').evaluate((node) => node.getBoundingClientRect().width))
		.toBe(widths.frame);
	const archiveProse = page.locator('.story-prose').first();
	await expect(archiveProse).toBeVisible();
	expect(await archiveProse.evaluate((node) =>
		node.getBoundingClientRect().width <= Number.parseFloat(getComputedStyle(node).maxWidth) + 1
	)).toBe(true);
	if (gridCase) {
		const { date, itemId, path, data, plainItemId } = gridCase;
		const assetUrl = new URL(`/${path}`, page.url()).href;
		for (const missing of [true, false]) {
			if (missing) expectedMissing.add(assetUrl);
			await page.route(assetUrl, (route) => route.fulfill(missing
				? { status: 404, body: '' }
				: { contentType: 'application/json', body: JSON.stringify({ ...data, rows: [] }) }
			));
			await page.goto('/archive/');
			await page.locator(`a[href="/${date}/#${itemId}"]`).click();
			await dayReady(page);
			const gridStory = page.locator(`article.item[id="${itemId}"]`);
			await gridStory.scrollIntoViewIfNeeded();
			await expect(gridStory.locator('[data-item-summary]').first()).not.toBeEmpty();
			await expect(gridStory.locator('[data-whowhat-state]')).toHaveAttribute(
				'data-whowhat-state', 'failed'
			);
			await expect(gridStory.getByRole('status')).toContainText('could not be loaded');
			await expect(gridStory.getByRole('table')).toHaveCount(0);
			const plain = page.locator(`article.item[id="${plainItemId}"]`);
			await expect(plain.locator('[data-item-summary]').first()).not.toBeEmpty();
			await expect(plain.locator('figure, [role="status"]')).toHaveCount(0);
			await page.unroute(assetUrl);
			const retry = gridStory.getByRole('button', { name: 'Try again' });
			await retry.focus();
			await expect(retry).toBeFocused();
			await page.keyboard.press('Enter');
			await expect(gridStory.locator('[data-whowhat-state]')).toHaveAttribute(
				'data-whowhat-state', 'ready'
			);
			await expect(gridStory.getByRole('table')).toBeVisible();
		}
		expect(missingResponses).toEqual([assetUrl]);
	}
	expect(errors).toEqual([]);
});
