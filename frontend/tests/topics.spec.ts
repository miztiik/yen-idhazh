import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { leadingStories, splitPills } from '../src/lib/day-shape';
import { AUTO_DISCOVERED_DESKS } from '../src/lib/payload/desks';
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

/** `digest.pill_move_min` as `config/appearance.json` commits it. Named once so
 * a test says which margin it is asserting rather than carrying a bare 2. */
const MOVE_MIN = 2;

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

test('the topic row reads biggest first, and the active topic never folds away', () => {
	const verticals = [ref('ai', 9), ref('world', 4), ref('energy', 1)];
	const auto = new Set(['energy']);

	const split = splitPills(verticals, 'energy', 2, MOVE_MIN, auto);

	expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'world', 'energy']);
	expect(split.folded).toEqual([]);
	expect(
		splitPills(verticals, null, 2, MOVE_MIN, auto).folded.map((vertical) => vertical.id)
	).toEqual(['energy']);
});

/** Row #6's oracle. The fixture carries a PREVIOUS ORDER no committed day does:
 * `ai` sits ahead of `business-economy` and holds one story FEWER, so the three
 * candidate answers are all different and no accident passes this.
 *
 *   the payload order   ai, business-economy, energy, india, world
 *   raw count order     world, energy, business-economy, ai, india
 *   the margin rule     world, energy, ai, business-economy, india
 *
 * Built rather than read off `frontend/public/digest/`, which is a collection
 * every run appends to (`CLAUDE.md` section 13, Guardrail #12) and which has
 * never once published a day shaped like this.
 */
const PREVIOUS_ORDER = [
	ref('ai', 9),
	ref('business-economy', 10),
	ref('energy', 30),
	ref('india', 8),
	ref('world', 40)
];

test('the topic row is a pure function of the payload', () => {
	// The same day rendered twice. A row that disagreed with itself would make a
	// shared link show the recipient a different page from the one the sender saw.
	const once = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN);
	const twice = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN);

	expect(once.shown.map((vertical) => vertical.id)).toEqual(
		twice.shown.map((vertical) => vertical.id)
	);
	expect(once.shown.map((vertical) => vertical.id)[0]).toBe('world');
});

test('a desk ahead by the margin takes the front of the row', () => {
	const shown = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN).shown;

	// world 40 then energy 30: both leads are far past the margin, so the row
	// leads with the desk holding most of the day.
	expect(shown.slice(0, 2).map((vertical) => vertical.id)).toEqual(['world', 'energy']);
});

test('a lead under the margin moves nothing, and that is the whole rule', () => {
	const shown = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN).shown;

	// `business-economy` holds 10 against `ai`'s 9. One story is under the margin
	// of two, so it does not take the place in front of it - and a raw count sort
	// would have put it there. That inversion is the price of the rule and the
	// counts on the pills are what make it readable.
	expect(shown.map((vertical) => vertical.id)).toEqual([
		'world',
		'energy',
		'ai',
		'business-economy',
		'india'
	]);
	// And a margin of one is strict count order, which is the setting that says
	// the margin is doing the work rather than the alphabet.
	expect(splitPills(PREVIOUS_ORDER, null, 5, 1).shown.map((vertical) => vertical.id)).toEqual([
		'world',
		'energy',
		'business-economy',
		'ai',
		'india'
	]);
});

test('a curated desk is never folded away, and an auto-created one may be', () => {
	// Auto-created verticals do not exist today,
	// so the branch is driven here. `energy` holds more of the day than `india`
	// and folds anyway, which is the rule: the fold asks who put the desk there,
	// the order asks how much it holds.
	const verticals = [ref('ai', 40), ref('energy', 20), ref('india', 6), ref('world', 30)];

	const split = splitPills(verticals, null, 2, MOVE_MIN, new Set(['energy']));

	expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'world', 'india']);
	expect(split.folded.map((vertical) => vertical.id)).toEqual(['energy']);
	// The limit is a SOFT cap. Three curated desks sit on a row capped at two,
	// because hiding a desk a person declared costs the reader the whole desk.
	expect(split.shown.length).toBeGreaterThan(2);
});

test('the desk the reader is on stays on the row even when it was proposed', () => {
	const verticals = [ref('ai', 40), ref('energy', 1)];

	const split = splitPills(verticals, 'energy', 1, MOVE_MIN, new Set(['energy']));

	expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'energy']);
	expect(split.folded).toEqual([]);
});

test('the frontend names every auto-discovered desk the vocabulary declares', () => {
	// The handoff to whatever proposes an auto-discovered desk, as a failing
	// check rather than a note nobody will open. It reads one fixed-size config file
	// and no collection a run appends to (`CLAUDE.md` section 13), and it is the same
	// shape as the lens drift test `lenses.ts` cites.
	const taxonomy = JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'taxonomy.json'), 'utf8')
	) as { verticals: { id: string; is_auto_discovered?: boolean }[] };

	const declared = taxonomy.verticals
		.filter((vertical) => vertical.is_auto_discovered === true)
		.map((vertical) => vertical.id)
		.sort();

	expect([...AUTO_DISCOVERED_DESKS].sort()).toEqual(declared);
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
