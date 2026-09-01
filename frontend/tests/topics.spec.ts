import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { leadingStories, splitPills } from '../src/lib/day-shape';
import type { DigestItem, DigestLead, DigestVerticalRef } from '../src/lib/payload/types';

/**
 * The day page's shape.
 *
 * The arithmetic runs without a browser, the way the run strip's axis does.
 * The browser half asserts what the canary fixture can show: a day that ran to
 * a single topic draws its stories flat, and the canary suite depends on every
 * planted item being on that page.
 *
 * The three-per-topic sections are gone. They drew three stories under each
 * desk and put the rest behind five links - 15 shown and 416 hidden on the
 * 431-story day of 2026-08-30 - and the flat stream now carries the whole day
 * with a leading block above it.
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
		title: `Story ${id}`,
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

function lead(id: string, reason: string): DigestLead {
	return { item_id: id, reason };
}

test('the leading block draws the day payload in the order it was given', () => {
	const items = [item('ai-1', 'ai'), item('world-1', 'world'), item('ai-2', 'ai')];
	const leads = [
		lead('ai-2', "Four of today's stories are about Nvidia."),
		lead('world-1', 'The lead story on our World desk.')
	];

	const stories = leadingStories(leads, items);

	// The pipeline decided the order. Re-ranking here would make a shared link
	// show the recipient a different page from the one the sender saw.
	expect(stories.map((story) => story.item_id)).toEqual(['ai-2', 'world-1']);
	expect(stories[0].title).toBe('Story ai-2');
	expect(stories[0].reason).toBe("Four of today's stories are about Nvidia.");
});

test('a lead the page cannot reach is dropped, and the rest of the block still draws', () => {
	// Every entry is an anchor into the stream, so a lead whose story is not on
	// the page is a link to nothing. Degrade, do not fail.
	const stories = leadingStories(
		[lead('ai-1', 'A reason.'), lead('ai-9', 'Another.')],
		[item('ai-1', 'ai')]
	);

	expect(stories.map((story) => story.item_id)).toEqual(['ai-1']);
});

test('a day with no block asks for nothing to be drawn', () => {
	expect(leadingStories([], [item('ai-1', 'ai')])).toEqual([]);
});

test('the topic pills fold by story count, and the active topic always stays out', () => {
	const verticals = [ref('ai', 9), ref('world', 4), ref('energy', 1)];

	const split = splitPills(verticals, 'energy', 2);

	expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'world', 'energy']);
	expect(split.folded).toEqual([]);
	expect(splitPills(verticals, null, 2).folded.map((vertical) => vertical.id)).toEqual(['energy']);
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
