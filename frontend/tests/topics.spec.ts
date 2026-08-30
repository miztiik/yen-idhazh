import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { shouldGroup, topicSlices } from '../src/lib/day-shape';
import type { DigestItem, DigestVerticalRef } from '../src/lib/payload/types';

/**
 * The day page's shape.
 *
 * The arithmetic runs without a browser, the way the run strip's axis does.
 * The browser half asserts the one case the canary fixture can show: a day
 * that ran to a single topic must stay flat, because grouping it would put
 * items behind a link that leads back to the same list - and the canary suite
 * depends on every planted item being on that page.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

function publishedDay(): string {
	const year = dirs(CANARY).at(-1) as string;
	const month = dirs(join(CANARY, year)).at(-1) as string;
	const day = dirs(join(CANARY, year, month)).at(-1) as string;
	return `${year}-${month}-${day}`;
}

const DAY = publishedDay();

function ref(id: string, count: number): DigestVerticalRef {
	return { id, display_name: id.toUpperCase(), count };
}

function item(id: string, vertical: string): DigestItem {
	return {
		item_id: id,
		vertical,
		title: id,
		source_url: `https://example.test/${id}`,
		source_id: 'test',
		source_name: 'Test',
		source_kind: 'reporting',
		published_at: null,
		summary: id,
		key_points: [],
		lenses: [],
		events: [],
		entities: [],
		band: 'high',
		band_reason: null,
		source_form: 'article',
		reader_note: null,
		truncated: false,
		visual: null,
		introduced_by_run: 1,
		updated_at: null
	};
}

test('a day with more than one topic gets sections; every other view stays flat', () => {
	const many = [ref('ai', 4), ref('world', 2)];

	expect(shouldGroup(null, '', many)).toBe(true);
	// A topic route already has a subject.
	expect(shouldGroup('ai', '', many)).toBe(false);
	// So does a filter, and its results cross topics.
	expect(shouldGroup(null, 'reactor', many)).toBe(false);
	// One topic is already the shape of the page.
	expect(shouldGroup(null, '', [ref('ai', 8)])).toBe(false);
	expect(shouldGroup(null, '', [])).toBe(false);
});

test('a slice is the head of the published order, and the topic count decides the link', () => {
	const verticals = [ref('ai', 4), ref('world', 2)];
	const items = [
		item('ai-1', 'ai'),
		item('ai-2', 'ai'),
		item('ai-3', 'ai'),
		item('ai-4', 'ai'),
		item('world-1', 'world'),
		item('world-2', 'world')
	];

	const slices = topicSlices(verticals, items, 3);

	// Payload topic order, which is the order the pills already use.
	expect(slices.map((slice) => slice.vertical.id)).toEqual(['ai', 'world']);
	// The head of the published order, never a re-rank.
	expect(slices[0].items.map((entry) => entry.item_id)).toEqual(['ai-1', 'ai-2', 'ai-3']);
	expect(slices[0].hasMore).toBe(true);
	// A topic that fits offers no link, because the link leads to what is shown.
	expect(slices[1].items.map((entry) => entry.item_id)).toEqual(['world-1', 'world-2']);
	expect(slices[1].hasMore).toBe(false);
});

test('a topic emptied by hide-read renders no section, and the rest still link', () => {
	const verticals = [ref('ai', 4), ref('world', 2)];
	// What a reader sees after hiding the two world stories they have read.
	const visible = [item('ai-1', 'ai'), item('ai-2', 'ai')];

	const slices = topicSlices(verticals, visible, 3);

	// A heading over nothing reads as broken software.
	expect(slices.map((slice) => slice.vertical.id)).toEqual(['ai']);
	// Hiding what you have read does not make the rest of the topic stop
	// existing, so the link is measured against the day, not against the view.
	expect(slices[0].hasMore).toBe(true);
});

test('a single-topic day renders flat, with every item on the page', async ({ page }) => {
	await page.goto(`/${DAY}/`);

	await expect(page.locator('[data-topic]')).toHaveCount(0);
	const items = await page.locator('article').count();
	expect(items).toBeGreaterThan(3);
});

test('a topic route lists the topic whole, and never groups itself', async ({ page }) => {
	await page.goto(`/${DAY}/ai/`);

	await expect(page.locator('[data-topic]')).toHaveCount(0);
	await expect(page.locator('article').first()).toBeVisible();
});

test('the day page carries no client-side sort or rank', () => {
	// The published order is global and identical for every reader. A control
	// that re-orders it makes a shared link show the recipient a different page.
	const source = readFileSync(
		resolve(process.cwd(), 'src', 'lib', 'components', 'DigestList.svelte'),
		'utf8'
	);

	expect(source).not.toContain('.sort(');
});
