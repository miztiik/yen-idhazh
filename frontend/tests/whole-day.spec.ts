import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { orderByTime } from '../src/lib/day-shape';
import { publicFiles } from '../src/lib/server/publication';
import type { DigestDay, DigestItem, VisualData } from '../src/lib/payload/types';
import { canarySeedItems } from './support/canary-config';
import { dayReady } from './support/day-ready';

const ROOT = resolve(process.cwd(), '..');
const CANARY_ROOT = resolve(ROOT, 'backend', 'var', 'canary');
const CANARY_DAY = '2026-08-20';
const DAY_FILE = `digest/${CANARY_DAY.replaceAll('-', '/')}/digest.json`;
const WIDTHS = [390, 1440];
const THEMES = ['dark', 'light'] as const;
const SEED = canarySeedItems();

const INVENTORY_FILES = new Set(publicFiles(CANARY_ROOT));
if (!INVENTORY_FILES.has(DAY_FILE)) {
	throw new Error(`the canary publication inventory does not name ${DAY_FILE}`);
}
const DAY = JSON.parse(readFileSync(join(CANARY_ROOT, DAY_FILE), 'utf8')) as DigestDay;
const ITEMS: DigestItem[] = orderByTime(DAY.items);
const LAST = ITEMS[ITEMS.length - 1]?.item_id;
const DRAWN = ITEMS.filter(
	(item) => item.visual?.state === 'rendered' && typeof item.visual.data_path === 'string'
);
const DRAWN_AFTER_SEED = ITEMS.slice(SEED).filter(
	(item) => item.visual?.state === 'rendered' && typeof item.visual.data_path === 'string'
);
function visualFor(item: DigestItem): VisualData {
	const path = item.visual?.data_path;
	if (!path || !INVENTORY_FILES.has(path)) {
		throw new Error(`the canary inventory does not name visual ${String(path)}`);
	}
	return JSON.parse(readFileSync(join(CANARY_ROOT, path), 'utf8')) as VisualData;
}
const HAS_CHART = DRAWN.some((item) => visualFor(item).type === 'bar');

interface Repaint {
	part: string;
	selector: string;
	property: 'fill' | 'stroke';
	token: string;
}

const REPAINTS: Repaint[] = [
	{ part: 'bars', selector: 'rect.bar', property: 'fill', token: '--chart-1' },
	{ part: 'bar names', selector: 'text.name', property: 'fill', token: '--color-text-secondary' },
	{ part: 'bar values', selector: 'text.figure', property: 'fill', token: '--color-text' },
	{ part: 'axes', selector: 'line.axis', property: 'stroke', token: '--chart-axis' }
];

interface Faults {
	errors: string[];
	failed: string[];
	notOk: string[];
}

function watch(page: Page): Faults {
	const faults: Faults = { errors: [], failed: [], notOk: [] };
	page.on('console', (message) => {
		if (message.type() === 'error' && !message.text().includes('Failed to load resource')) {
			faults.errors.push(message.text());
		}
	});
	page.on('pageerror', (error) => faults.errors.push(error.message));
	page.on('requestfailed', (request) => {
		const reason = request.failure()?.errorText ?? 'no reason given';
		if (request.resourceType() === 'document' && reason === 'net::ERR_ABORTED') return;
		faults.failed.push(`${request.url()} (${reason})`);
	});
	page.on('response', (response) => {
		if (response.status() >= 400) faults.notOk.push(`${response.status()} ${response.url()}`);
	});
	return faults;
}

async function stepDown(page: Page): Promise<number> {
	return page.evaluate(async () => {
		const settle = () =>
			new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done())));
		const step = Math.max(window.innerHeight, 1);
		window.scrollTo(0, 0);
		await settle();
		let at = 0;
		let steps = 0;
		while (at < document.documentElement.scrollHeight && steps < 2000) {
			at += step;
			steps += 1;
			window.scrollTo(0, at);
			await settle();
		}
		window.scrollTo(0, 0);
		await settle();
		return steps;
	});
}

async function openWholeDay(page: Page, width: number): Promise<void> {
	expect(ITEMS.length, `the named canary day has no item after its ${SEED}-item seed`)
		.toBeGreaterThan(SEED);
	expect(DRAWN.length, 'the named canary day carries no published visuals').toBeGreaterThan(0);
	expect(DRAWN_AFTER_SEED.length, 'no visual follows the seed, so lazy drawing is not exercised')
		.toBeGreaterThan(0);
	expect(HAS_CHART, 'the named canary day carries no chart').toBe(true);
	expect(LAST, 'the named canary day has no last story to address').toBeTruthy();

	await page.setViewportSize({ width, height: 900 });
	await page.goto(`/${CANARY_DAY}/#${LAST}`);
	await dayReady(page, `${CANARY_DAY} never finished arriving`);
	await expect(page.locator('article.item')).toHaveCount(ITEMS.length);
}

function tokenColour(page: Page, token: string): Promise<string> {
	return page.evaluate((name) => {
		const probe = document.createElement('div');
		probe.style.backgroundColor = `var(${name})`;
		document.body.append(probe);
		const colour = getComputedStyle(probe).backgroundColor;
		probe.remove();
		return colour;
	}, token);
}

function painted(page: Page, selector: string, property: 'fill' | 'stroke'): Promise<string[]> {
	return page.evaluate(
		({ selector: query, property: name }) =>
			Array.from(document.querySelectorAll(`main figure ${query}`)).map((node) =>
				getComputedStyle(node).getPropertyValue(name)
			),
		{ selector, property }
	);
}

async function wearing(page: Page, theme: string): Promise<void> {
	await page.evaluate((chosen) => document.documentElement.setAttribute('data-theme', chosen), theme);
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

for (const width of WIDTHS) {
	test(`the whole canary day renders every story and drawing at ${width}px`, async ({ page }) => {
		const faults = watch(page);
		const requests: string[] = [];
		page.on('request', (request) => requests.push(new URL(request.url()).pathname));

		await openWholeDay(page, width);
		const steps = await stepDown(page);
		await expect(page.locator('main figure svg')).toHaveCount(DRAWN.length);

		const requestedLateDrawing = DRAWN_AFTER_SEED.some((item) =>
			requests.some((path) => path.endsWith(`/${item.visual!.data_path}`))
		);
		expect(
			requestedLateDrawing,
			`no visual past the ${SEED}-item seed was fetched over ${steps} screens`
		).toBe(true);

		const shape = await page.evaluate(() => ({
			figures: document.querySelectorAll('main figure').length,
			svgs: document.querySelectorAll('main figure svg').length,
			images: document.querySelectorAll('main img').length,
			stories: document.querySelectorAll('article.item').length,
			scrollWidth: document.documentElement.scrollWidth,
			clientWidth: document.documentElement.clientWidth
		}));
		expect(shape.figures, 'a figure holds none or more than one drawing').toBe(shape.svgs);
		expect(shape.images, 'a story is still carried by an image').toBe(0);
		expect(shape.stories).toBe(ITEMS.length);
		expect(
			shape.scrollWidth,
			`the ${ITEMS.length}-story page scrolls sideways by ` +
				`${shape.scrollWidth - shape.clientWidth}px at ${width}px`
		).toBeLessThanOrEqual(shape.clientWidth);
		expect(faults.errors, `browser errors:\n${faults.errors.join('\n')}`).toEqual([]);
		expect(faults.failed, `failed requests:\n${faults.failed.join('\n')}`).toEqual([]);
		expect(faults.notOk, `error responses:\n${faults.notOk.join('\n')}`).toEqual([]);
	});

	test(`the whole canary day uses theme tokens for every drawing at ${width}px`, async ({
		page
	}) => {
		await openWholeDay(page, width);
		await stepDown(page);
		await expect(page.locator('main figure svg')).toHaveCount(DRAWN.length);

		const themeValues: Record<string, string> = {};
		for (const theme of THEMES) {
			await wearing(page, theme);
			const values: string[] = [];
			for (const rule of REPAINTS) {
				const token = await tokenColour(page, rule.token);
				values.push(token);
				const actual = await painted(page, rule.selector, rule.property);
				expect(actual.length, `no ${rule.part} were drawn to check`).toBeGreaterThan(0);
				expect(
					actual.filter((value) => value !== token),
					`${theme} ${rule.part} do not use ${rule.token}`
				).toEqual([]);
			}

			const ink = await tokenColour(page, '--color-text');
			values.push(ink);
			const inks = await page.locator('main figure svg').evaluateAll((nodes) =>
				nodes.map((node) => getComputedStyle(node).color)
			);
			expect(inks.filter((value) => value !== ink), `${theme} drawings do not inherit page ink`)
				.toEqual([]);
			themeValues[theme] = values.join('|');
		}

		expect(themeValues.light, 'the two themes paint every drawing the same').not.toBe(
			themeValues.dark
		);
	});
}
