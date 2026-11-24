import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { BuildRecord } from '../scripts/build-state';
import { isVisualData } from '../src/lib/payload/drawing';
import type { DigestDay, VisualData } from '../src/lib/payload/types';
import { dayReady } from './support/day-ready';
import { CANARY, newestDate, publishedDates } from './support/published';
import { uiConfig } from '../src/lib/server/config';

/** One reading journey covers the shared shell; never expand it into route or presentation matrices. */
const journey = process.env.IDHAZH_TEST_BUILD === 'real'
	? 'a reader opens a dated story from the built archive'
	: 'a reader can load stories, filter the day and keep the layout usable on a phone';

test(journey, async ({ page }) => {
	const build: BuildRecord = JSON.parse(readFileSync(
		join(process.cwd(), '..', 'backend', 'var', 'checks', 'build.json'), 'utf8'
	));
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
	const footer = page.getByRole('contentinfo');
	const archive = footer.getByRole('link', { name: 'Archive & search', exact: true });
	const continuation = page.locator('[data-continuation]');
	await expect(footer.getByRole('heading', { name: 'More editions' })).toBeVisible();
	await expect(footer.getByRole('heading', { name: 'Project' })).toBeVisible();
	await expect(stories.first()).toBeVisible();
	await expect(stories.first().locator('[data-item-summary]').first()).not.toBeEmpty();
	if (build.mode === 'real') {
		const status = await continuation.getByRole('status').innerText();
		const progress = status.match(/^Showing (\d+) of (\d+) stor(?:y|ies)$/);
		const more = continuation.getByRole('button', { name: 'Show more stories', exact: true });
		if (progress) {
			const [, displayed, reachable] = progress.map(Number);
			expect(displayed).toBe(await stories.count());
			expect(displayed).toBeLessThan(reachable);
			await more.click();
			await expect(stories.nth(displayed)).toBeFocused();
		} else {
			expect(status).toMatch(/^(End of this edition|All stories in this view shown)$/);
			await expect(more).toHaveCount(0);
		}
		const editionDate = await page.locator('h1 time').getAttribute('datetime');
		if (!editionDate) throw new Error('the home edition must name its date');
		const dayAsset = new URL(`/digest/${editionDate.replaceAll('-', '/')}/digest.json`, page.url()).href;
		// Check the dated route fetches and renders without depending on the day's
		// topic counts, edition status or charts.
		await archive.click();
		await expect(page).toHaveURL(new URL('/archive/', page.url()).href);
		const link = page.locator('[data-story-list="rows"]').getByRole('link').first();
		await link.click();
		await dayReady(page);
		const id = decodeURIComponent(new URL(page.url()).hash.slice(1));
		const story = page.locator(`article.item[id=${JSON.stringify(id)}]`);
		await expect(story).toBeVisible();
		await expect(story.locator('[data-item-summary]').first()).not.toBeEmpty();

		// Home already holds a seed, so a missing full payload is not a missing edition.
		expectedMissing.add(dayAsset);
		await page.route(dayAsset, (route) => route.fulfill({ status: 404, body: '' }), { times: 1 });
		await page.goto('/');
		const retry = page.getByRole('button', { name: 'Try again', exact: true });
		await expect(retry).toBeVisible();
		await expect(stories.first()).toBeVisible();
		await expect(archive).toBeVisible();
		await expect(more).toHaveCount(0);
		await expect(continuation.getByRole('status')).not.toHaveText('End of this edition');
		await retry.click();
		await dayReady(page);
		expect(missingResponses).toEqual([dayAsset]);
		expect(errors).toEqual([]);
		return;
	}
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
			const rail = article.querySelector<HTMLElement>('.item-rail')!;
			const stream = article.closest<HTMLElement>('.day-stream')!;
			const day = article.closest<HTMLElement>('.day')!;
			const style = getComputedStyle(article);
			return {
				day: day.getBoundingClientRect().width,
				stream: stream.getBoundingClientRect().width,
				card: article.getBoundingClientRect().width,
				body: body.getBoundingClientRect().width,
				prose: prose.getBoundingClientRect().width,
				bodyBottom: body.getBoundingClientRect().bottom,
				footerTop: rail.getBoundingClientRect().top,
				rightInset: article.getBoundingClientRect().right - body.getBoundingClientRect().right,
				expectedInset: Number.parseFloat(style.paddingRight) + Number.parseFloat(style.borderRightWidth)
			};
		});
		expect(Math.abs(geometry.day - geometry.stream)).toBeLessThanOrEqual(1);
		expect(Math.abs(geometry.stream - geometry.card)).toBeLessThanOrEqual(1);
		expect(Math.abs(geometry.body - geometry.prose)).toBeLessThanOrEqual(1);
		expect(Math.abs(geometry.rightInset - geometry.expectedInset)).toBeLessThanOrEqual(1);
		expect(geometry.footerTop).toBeGreaterThanOrEqual(geometry.bodyBottom);
	}
	await expectFullArticleWidth();
	await expect(page.locator('[data-time-note]')).toHaveCount(0);
	await expect(stories.locator('[data-item-time]').first()).toContainText('UTC');
	await expect(stories.locator('time[data-item-time]').first())
		.toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}T.+Z$/);
	await expect(stories.locator('[data-band], [data-band-reason]')).toHaveCount(0);

	await expect(page.locator('[data-leading]')).toBeVisible();
	const leading = await page.locator('[data-leading]').boundingBox();
	const firstStory = await stories.first().boundingBox();
	expect(leading!.y + leading!.height).toBeLessThanOrEqual(firstStory!.y);
	await page.setViewportSize({ width: 1280, height: 900 });
	await expectFullArticleWidth();
	await page.setViewportSize({ width: 1920, height: 1080 });
	const edition = page.getByRole('region', { name: 'About today' });
	await expect(edition.getByRole('heading', { level: 1 })).toBeVisible();
	await expect(edition.getByRole('heading', { level: 1 }).locator('time')).toHaveAttribute('datetime', newestDate());
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
	await expect(continuation.getByRole('status')).toHaveText('All matching stories shown');
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

	// Topic and All links change selection, not the reading shell.
	const topic = page.locator('[data-topic-row] a').nth(1);
	const topicHref = await topic.getAttribute('href');
	await topic.click();
	await expect(page).toHaveURL(new URL(topicHref!, page.url()).href);
	await dayReady(page);
	await expectFullArticleWidth();
	const all = page.getByRole('link', { name: /^All \d+/ });
	const allHref = await all.getAttribute('href');
	await all.click();
	await expect(page).toHaveURL(new URL(allHref!, page.url()).href);
	await dayReady(page);
	await expectFullArticleWidth();
	const datedLeading = await page.locator('[data-leading]').boundingBox();
	const datedFirst = await stories.first().boundingBox();
	expect(datedLeading!.y + datedLeading!.height).toBeLessThanOrEqual(datedFirst!.y);
	const deepId = await stories.last().getAttribute('id');
	await page.goto(`${new URL(page.url()).pathname}#${deepId}`);
	await expect(page.locator(`article[id="${deepId}"]`)).toBeFocused();
	await expectFullArticleWidth();
	await page.goto('/');
	await dayReady(page);
	const originalLink = stories.first().getByRole('link', { name: 'Read the original' });
	const marked = page.locator(`article.item[id=${JSON.stringify(await stories.first().getAttribute('id'))}]`);
	// Exercise the real read handler without leaving the local published fixture.
	await originalLink.evaluate((link) => link.addEventListener('click', (event) => event.preventDefault(), { once: true }));
	await originalLink.click();
	const options = page.getByText('Reading options', { exact: true });
	const readingControls = page.locator('details').filter({ has: options });
	const unreadOnly = readingControls.getByLabel('Unread only');
	const lastStory = (await stories.last().boundingBox())!;
	await expect(options).toBeVisible();
	expect((await options.boundingBox())!.y).toBeGreaterThanOrEqual(lastStory.y + lastStory.height);
	await expect(unreadOnly).toBeHidden();
	await options.press('Enter');
	await unreadOnly.check();
	await expect(marked).toHaveCount(0);
	const clear = readingControls.getByRole('button', { name: "Clear this edition's read marks" });
	await clear.press('Enter');
	await expect(clear).toBeFocused();
	await expect(clear).toBeDisabled();
	await expect(unreadOnly).not.toBeChecked();
	await expect(marked).toBeVisible();
	await expect(readingControls).toContainText('Read marks cleared for this edition.');
	await page.emulateMedia({ reducedMotion: 'reduce' });
	const backToTop = page.getByRole('button', { name: 'Back to top' });
	await page.locator('[data-site-header]').evaluate((header) =>
		window.scrollTo(0, scrollY + header.getBoundingClientRect().bottom + 1));
	await expect(backToTop).toHaveCSS('position', 'fixed');
	await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
	await expect(continuation.getByRole('button', { name: 'Back to top' })).toHaveCSS('position', 'static');
	await expect(backToTop).toHaveText('');
	await backToTop.focus();
	await page.keyboard.press('Enter');
	await expect(page.getByRole('region', { name: 'About today' }).getByRole('heading', { level: 1 })).toBeFocused();
	await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
	await expect(page.locator('[data-reader-top]')).toHaveCount(0);
	await page.emulateMedia({ reducedMotion: 'no-preference' });

	let chartCase: {
		date: string; itemId: string; path: string; data: VisualData; plainItemId: string
	} | null = null;
	if (build.mode === 'canary') {
		const date = newestDate();
		const [year, month, day] = date.split('-');
		const response = await page.request.get(`/digest/${year}/${month}/${day}/digest.json`);
		expect(response.ok()).toBe(true);
		const published: DigestDay = await response.json();
		const visibleIds = new Set(await stories.evaluateAll((nodes) => nodes.map((node) => node.id)));
		const flagged = published.items.find((item) =>
			visibleIds.has(item.item_id) && item.band !== 'high' && item.band_reason !== null
		);
		if (!flagged) throw new Error('the reader canary must display a recorded confidence concern');
		const flaggedStory = page.locator(`article.item[id="${flagged.item_id}"]`);
		await expect(flaggedStory.locator('[data-band], [data-band-reason]')).toHaveCount(0);
		await expect(flaggedStory.locator('[data-item-foot]')).not.toContainText(
			/Parts of our summary|We could not check this summary|Our summary leaves out|Automated check found/
		);
		await expect(flaggedStory.getByRole('link', { name: 'Read the original' }))
			.toHaveAttribute('href', flagged.source_url);
		const chart = published.items.find((item) =>
			item.visual?.kind === 'chart' && item.visual.state === 'rendered'
		);
		const plain = published.items.find((item) => item.visual === null);
		if (!chart?.visual?.data_path || !plain) {
			throw new Error('the reader canary must carry a published numeric chart and no-visual story');
		}
		const chartResponse = await page.request.get(`/${chart.visual.data_path}`);
		expect(chartResponse.ok()).toBe(true);
		expect(await chartResponse.body()).toEqual(
			readFileSync(join(CANARY, '..', chart.visual.data_path))
		);
		const chartData: unknown = await chartResponse.json();
		if (!isVisualData(chartData)) {
			throw new Error('the published canary chart was refused by the real reader');
		}
		await page.setViewportSize({ width: 390, height: 844 });
		const chartStory = page.locator(`article.item[id="${chart.item_id}"]`);
		await chartStory.scrollIntoViewIfNeeded();
		await expect(chartStory.getByRole('img')).toBeVisible();
		const plainStory = page.locator(`article.item[id="${plain.item_id}"]`);
		await expect(plainStory.locator('[data-item-summary]').first()).not.toBeEmpty();
		await expect(plainStory.locator('figure, [role="status"]')).toHaveCount(0);
		chartCase = {
			date, itemId: chart.item_id, path: chart.visual.data_path, data: chartData,
			plainItemId: plain.item_id
		};
	}

	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.locator('#page-filter')).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);
	const previous = footer.getByRole('link', { name: 'Previous edition' });
	const previousDate = publishedDates().at(-2);
	if (!previousDate) throw new Error('the reader canary must publish a previous edition');
	await previous.click();
	await expect(page).toHaveURL(new URL(`/${previousDate}/`, page.url()).href);
	await dayReady(page);

	await page.setViewportSize({ width: 1920, height: 1080 });
	await page.goto('/archive/');
	expect(await page.locator('.frame').evaluate((node) => node.getBoundingClientRect().width))
		.toBe(widths.frame);
	const archiveProse = page.locator('.story-prose').first();
	await expect(archiveProse).toBeVisible();
	expect(await archiveProse.evaluate((node) =>
		Math.abs(node.getBoundingClientRect().width -
			node.closest('.story-row')!.getBoundingClientRect().width) <= 1
	)).toBe(true);
	if (chartCase) {
		await page.setViewportSize({ width: 390, height: 844 });
		const { date, itemId, path, data, plainItemId } = chartCase;
		const assetUrl = new URL(`/${path}`, page.url()).href;
		for (const missing of [true, false]) {
			if (missing) expectedMissing.add(assetUrl);
			await page.route(assetUrl, (route) => route.fulfill(missing
				? { status: 404, body: '' }
				: { contentType: 'application/json', body: JSON.stringify({ ...data, marks: [] }) }
			));
			const refusal = page.waitForEvent('console', (message) =>
				message.type() === 'warning' && message.text().includes(path)
			);
			await page.goto('/archive/');
			await page.locator(`a[href="/${date}/#${itemId}"]`).click();
			await dayReady(page);
			const chartStory = page.locator(`article.item[id="${itemId}"]`);
			await chartStory.scrollIntoViewIfNeeded();
			await refusal;
			await expect(chartStory.locator('[data-item-summary]').first()).not.toBeEmpty();
			await expect(chartStory.getByRole('img')).toHaveCount(0);
			const plain = page.locator(`article.item[id="${plainItemId}"]`);
			await expect(plain.locator('[data-item-summary]').first()).not.toBeEmpty();
			await expect(plain.locator('figure, [role="status"]')).toHaveCount(0);
			await page.unroute(assetUrl);
			await page.reload();
			await dayReady(page);
			await chartStory.scrollIntoViewIfNeeded();
			await expect(chartStory.getByRole('img')).toBeVisible();
		}
		expect(missingResponses).toEqual([assetUrl]);
	}
	expect(errors).toEqual([]);
});
