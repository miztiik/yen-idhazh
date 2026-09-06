import { expect, test, type Page, type Request } from '@playwright/test';
import { readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deskShortfall, filterNeedle, indexDay, shortlist } from '../src/lib/day-shape';
import type { DigestItem, DigestVerticalRef } from '../src/lib/payload/types';

/**
 * Row #7's oracle: one panel, and the field never pays for the encoder.
 *
 * Four claims, and each one is a way the panel could quietly betray a reader:
 *
 * - **Typing costs nothing.** The archive's search runs on a 43 MB encoder
 *   downloaded to the reader's device. Typing narrows the stories already
 *   fetched and asks for nothing; only the `Search` button spends the download,
 *   so the cost is named before it is paid. The counts are printed, because an
 *   arm that sees zero requests may have been watching nothing at all - which
 *   is why the same test asserts the button DOES fetch the weights, exactly
 *   once.
 * - **With no script the field is not there.** A dead input that swallows
 *   typing is worse than no input, so a `<noscript>` rule hides it and one
 *   sentence takes its place. The day page's pills are prerendered links and
 *   keep working, which is the half that must survive.
 * - **The panel sticks at 1024px and nowhere below it.** A control holding a
 *   third of a phone screen for the whole scroll is screen the reader paid for.
 * - **The filter reads the list it is handed.** A reading route seeds its
 *   document and fetches the rest of the day, so a filter holding a list
 *   captured at mount would narrow the seed for ever. The day's text is now
 *   lowercased once into an index instead of once per keystroke, which is the
 *   same hazard one step earlier: an index built at mount is a captured list.
 *   The rule is pure and is driven in Node, because the canary day publishes 8
 *   stories against a seed of 15 and no reading route in this build ever
 *   fetches (`docs/how-to/run-the-gates.md`). The archive is where a browser
 *   can show it: its stories arrive a month at a time, always after first
 *   paint.
 *
 * Row #11's oracle lives here too, because the sentence a thin desk prints is
 * drawn by this panel. It has two arms and only one of them can be a browser:
 * the canary day has one desk, deliberately starved, so a real page shows the
 * line with the real counts - and a healthy desk needs a second desk the
 * fixture cannot hold, so that arm is driven as a pure function, which is what
 * `frontend/src/lib/day-shape.ts` exists for.
 */

const BUILD = join(dirname(fileURLToPath(import.meta.url)), '..', 'build');

function subdirectories(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** The newest published day in the built tree. Never a date written here. */
const DAY = subdirectories(BUILD).filter((name) => /^\d{4}-\d{2}-\d{2}$/.test(name)).at(-1) as string;

/** Anything under the on-device model's own directory. */
const MODEL_DIR = /\/assist\/models\//;
/** The encoder weights themselves - most of what the 43 MB actually is. */
const WEIGHTS = /\/assist\/models\/.*\.onnx$/;
const MONTH = /\/index\/\d{4}-\d{2}\.json$/;

function item(id: string, title: string, summary = '', points: string[] = []): DigestItem {
	return {
		item_id: id,
		vertical: 'ai',
		title,
		source_url: `https://example.test/${id}`,
		source_id: 'test',
		source_name: 'Test',
		source_kind: 'reporting',
		published_at: null,
		summary,
		key_points: points,
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

/** The stories a needle keeps, as `DigestList` asks for them. */
function kept(items: DigestItem[], needle: string | null): DigestItem[] {
	return shortlist(indexDay(items), needle, null, new Set<string>(), '').visible;
}

test.describe('the filter rule', () => {
	test('a field narrows nothing until it holds enough to narrow by', () => {
		expect(filterNeedle('', 2)).toBeNull();
		expect(filterNeedle('a', 2)).toBeNull();
		// Whitespace is not typing. A box holding one space is an empty box.
		expect(filterNeedle('  a  ', 2)).toBeNull();
		expect(filterNeedle('AI', 2)).toBe('ai');
		expect(filterNeedle('  Reactor ', 2)).toBe('reactor');
		// The floor: a zero would turn an empty box into a filter that matches
		// everything and prints a count, which reads as a filter that is on.
		expect(filterNeedle('', 0)).toBeNull();
		expect(filterNeedle('a', 1)).toBe('a');
	});

	test('the needle reads the title, the summary and the key points', () => {
		const items = [
			item('one', 'A reactor in Kerala'),
			item('two', 'Something else', 'the reactor is cooled by seawater'),
			item('three', 'Another thing', 'no match here', ['a second reactor is planned']),
			item('four', 'Nothing to do with it')
		];

		expect(kept(items, 'reactor').map((story) => story.item_id)).toEqual([
			'one',
			'two',
			'three'
		]);
		// A null needle is the whole list, never an empty one.
		expect(kept(items, null)).toEqual(items);
	});

	test('the filter reads the list it is handed, never one captured earlier', () => {
		// The seed a reading route prerenders, and the day that arrives after it.
		const seed = [item('one', 'A reactor in Kerala')];
		const whole = [...seed, item('two', 'A second reactor'), item('three', 'A pumpjack')];

		expect(kept(seed, 'reactor')).toHaveLength(1);
		expect(
			kept(whole, 'reactor'),
			'the filter narrowed the seed rather than the day that arrived'
		).toHaveLength(2);

		// And the index the filter reads is the day's, not the seed's. This is the
		// same hazard one step earlier: an index is lowercased text plus a position
		// per story, so one built over the seed answers every later question about
		// a day that is no longer the day in hand.
		const index = indexDay(whole);
		expect(index.fields).toHaveLength(3);
		expect(index.at.get('three'), 'the index does not know where the day ends').toBe(2);
	});
});

function desk(count: number, overrides: Partial<DigestVerticalRef> = {}): DigestVerticalRef {
	return {
		id: 'ai',
		display_name: 'AI',
		count,
		considered: 40,
		too_old: 31,
		below_feed_floor: false,
		...overrides
	};
}

test.describe('the thin-desk rule', () => {
	test('a thin desk with a reason names both numbers', () => {
		expect(deskShortfall(desk(3), 12)).toEqual({ offered: 40, tooOld: 31 });
		// The floor is inclusive: a desk exactly at it is still a desk a reader
		// sees the whole of at once.
		expect(deskShortfall(desk(12), 12)).toEqual({ offered: 40, tooOld: 31 });
	});

	test('a healthy desk says nothing at all', () => {
		expect(deskShortfall(desk(13), 12)).toBeNull();
		expect(deskShortfall(desk(216), 12)).toBeNull();
	});

	test('a day published before the counts existed says nothing', () => {
		// Absent is unknown, never zero - zero would claim our sources offered
		// this desk nothing on a day it published three stories.
		expect(
			deskShortfall({ id: 'ai', display_name: 'AI', count: 3 }, 12),
			'a day with no counts on it printed a sentence anyway'
		).toBeNull();
		expect(deskShortfall(desk(3, { considered: null, too_old: null }), 12)).toBeNull();
	});

	test('a thin desk that dropped nothing has no reason to give', () => {
		// Three offered and three published is a quiet day, not a shortfall. A
		// sentence here would be a fact with no explanation attached to it.
		expect(deskShortfall(desk(3, { considered: 3, too_old: 0 }), 12)).toBeNull();
	});

	test('the sentence never claims fewer stories than the page is showing', () => {
		// `considered` is counted per run and the day's stories accumulate across
		// runs, so it is not an upper bound on `count`. Without this clause a page
		// showing eight stories could say the sources offered five.
		expect(deskShortfall(desk(8, { considered: 5, too_old: 4 }), 12)).toBeNull();
		expect(deskShortfall(desk(8, { considered: 8, too_old: 4 }), 12)).toBeNull();
	});

	test('a desk that is not on the day says nothing', () => {
		expect(deskShortfall(undefined, 12)).toBeNull();
	});
});

test('the starved desk on the canary day says why it is thin', async ({ page }) => {
	// The fixture's one desk published 8 stories against 40 its sources offered,
	// 31 of them a back catalogue. Both numbers are read off the page rather
	// than written here, so the arm fails if the payload stops carrying them.
	await page.goto(`/${DAY}/ai/`);
	const line = page.locator('[data-desk-shortfall]');
	await expect(line, 'the starved desk drew no sentence').toHaveCount(1);
	const said = (await line.innerText()).replace(/\s+/g, ' ').trim();
	console.log(`[filter-bar] thin desk says: ${said}`);
	expect(said).toBe(
		"Today our sources offered 40 stories on this topic. 31 were too old for today's page."
	);
});

test('the all-topics page and the archive draw no shortfall sentence', async ({ page }) => {
	// One desk being read is one sentence. On a view with no desk being read it
	// would be one per desk, which is a column of absences rather than
	// information - so there is no line here even though the day's one desk is
	// thin and carries the counts.
	await page.goto(`/${DAY}/`);
	await expect(page.locator('[data-topic-row]').first()).toBeVisible();
	await expect(
		page.locator('[data-desk-shortfall]'),
		'the all-topics page explained a desk nobody had opened'
	).toHaveCount(0);

	// The archive's counts are sums over every published day, so a shortfall
	// taken from one day's run would be a number about nothing on the page.
	await page.goto('/archive/');
	await expect(page.locator('[data-topic-row] .pill').first()).toBeVisible();
	await page.locator('[data-topic-row] .pill').nth(1).click();
	await expect(page.locator('[data-desk-shortfall]')).toHaveCount(0);
});

/** Every request the page made, kept whole so a count can be printed. */
class Watched {
	readonly urls: string[] = [];

	take(request: Request): void {
		this.urls.push(new URL(request.url()).pathname);
	}

	count(pattern: RegExp): number {
		return this.urls.filter((url) => pattern.test(url)).length;
	}

	distinct(pattern: RegExp): number {
		return new Set(this.urls.filter((url) => pattern.test(url))).size;
	}
}

/** The story titles in the archive's one list, in the order they are rendered. */
async function titles(page: Page): Promise<string[]> {
	return page.locator('[data-story-list="rows"] li a').allInnerTexts();
}

test('typing filters the archive and downloads nothing; the button downloads once', async ({
	page
}) => {
	const asked = new Watched();
	page.on('request', (request) => asked.take(request));

	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	// Everything fetched is on screen, so a count taken off the page counts the
	// same set the filter reads.
	await expect(page.locator('[data-story-more]')).toHaveCount(0);
	const browsed = await titles(page);
	expect(browsed.length, 'no story reached the list, so there is nothing to filter').toBeGreaterThan(
		1
	);

	// A word off the page rather than one written here, chosen because it
	// actually narrows: a needle matching every title would prove nothing.
	const hits = (needle: string) =>
		browsed.filter((title) => title.toLowerCase().includes(needle)).length;
	const words = [
		...new Set(
			browsed.flatMap((title) =>
				title
					.split(/\s+/)
					.map((part) => part.replace(/[^A-Za-z]/g, '').toLowerCase())
					.filter((part) => part.length > 4)
			)
		)
	];
	const word = words.find((candidate) => hits(candidate) >= 1 && hits(candidate) < browsed.length);
	expect(word, `no word in the canary titles narrows the list: ${browsed.join(' | ')}`).toBeTruthy();

	await page.fill('#archive-query', word as string);
	await expect(page.locator('[data-story-list="rows"] li')).toHaveCount(hits(word as string));
	for (const shown of await titles(page)) {
		expect(shown.toLowerCase(), 'a story the field does not match stayed on the page').toContain(
			word
		);
	}

	// The whole claim. Printed, because a zero that was never watched is not a
	// pass - the positive arm below is what proves this counter was watching.
	const beforeClick = asked.count(MODEL_DIR);
	console.log(`[filter-bar] model-directory requests while typing: ${beforeClick}`);
	expect(beforeClick, 'typing started the on-device encoder download').toBe(0);

	await page.getByRole('button', { name: 'Search', exact: true }).click();
	await expect(page.locator('[data-search-state]')).toContainText('The download is done', {
		timeout: 180_000
	});

	const weights = asked.count(WEIGHTS);
	console.log(
		`[filter-bar] after Search - model-directory requests: ${asked.count(MODEL_DIR)},` +
			` encoder weights: ${weights}, distinct weight files: ${asked.distinct(WEIGHTS)}`
	);
	expect(weights, 'the click did not fetch the encoder, so the counter was watching nothing').toBe(
		1
	);
	expect(asked.distinct(WEIGHTS), 'the encoder was fetched from more than one address').toBe(1);
});

test('a topic pill narrows the archive and downloads nothing', async ({ page }) => {
	const asked = new Watched();
	page.on('request', (request) => asked.take(request));

	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();

	// The pills are visible at rest, never behind the field and never collapsed
	// as a set.
	const pills = page.locator('[data-topic-row] .pill');
	await expect(pills.first()).toBeVisible();
	expect(await pills.count(), 'the archive drew no topic pills').toBeGreaterThan(1);

	await pills.nth(1).click();
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();

	const clicked = asked.count(MODEL_DIR);
	console.log(`[filter-bar] model-directory requests after a topic pill: ${clicked}`);
	expect(clicked, 'a topic pill started the on-device encoder download').toBe(0);
});

test('the archive filter narrows the stories that arrive after it was typed', async ({ page }) => {
	// Sixty stories, half of them matching, held back long enough that the field
	// is filled before a single one exists. A filter holding what it saw at mount
	// would leave every one of them on the page.
	const entries = Array.from({ length: 60 }, (_, at) => ({
		date: at < 30 ? '2026-08-19' : '2026-08-18',
		item_id: `ai-${at + 1}`,
		title: `${at % 2 === 0 ? 'Reactor' : 'Pumpjack'} story ${at + 1}`,
		vertical: 'ai',
		vector: null
	}));

	let started = () => {};
	const asked = new Promise<void>((resolve) => (started = resolve));
	await page.route(MONTH, async (route) => {
		started();
		await new Promise((wake) => setTimeout(wake, 1_500));
		await route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				version: '2026-08-26',
				month: '2026-08',
				model_id: 'all-minilm-l6-v2-quantized',
				dimensions: 384,
				dtype: 'int8',
				scale: 1 / 127,
				entries
			})
		});
	});

	await page.goto('/archive/');
	// The month is asked for on mount, so this also proves the page has hydrated
	// and the field below is live rather than prerendered markup.
	await asked;
	await expect(page.locator('[data-story-list="rows"] li')).toHaveCount(0);

	await page.fill('#archive-query', 'reactor');
	const rows = page.locator('[data-story-list="rows"] li');
	await expect(rows).toHaveCount(25);
	for (const shown of await titles(page)) {
		expect(shown.toLowerCase()).toContain('reactor');
	}
	// Thirty match and twenty-five are drawn - a count over what was read, never
	// over an archive this page never opened.
	await expect(page.locator('[data-story-scope]')).toHaveText('Showing 25 of 30, newest first.');

	await page.locator('[data-story-more]').click();
	await expect(rows).toHaveCount(30);
	await expect(page.locator('[data-story-more]')).toHaveCount(0);
});

test('with no script the field is gone, one sentence replaces it, and a pill still navigates', async ({
	browser
}) => {
	const context = await browser.newContext({ javaScriptEnabled: false });
	const page = await context.newPage();
	try {
		await page.goto(`/${DAY}/`);

		// The input is in the prerendered document, so hydration has nothing to
		// reconcile - and the `<noscript>` rule is what takes it off the page.
		await expect(page.locator('#page-filter'), 'a dead input was left on the page').toBeHidden();
		await expect(page.locator('[data-filter-noscript]')).toBeVisible();
		await expect(page.locator('[data-filter-noscript]')).toHaveText(
			'Filtering needs JavaScript. Every topic above is a link and still works.'
		);

		// And the half that must survive: the pills are links to prerendered
		// routes, so a topic is still one click away.
		const topic = page.locator('[data-topic-row] a').nth(1);
		await expect(topic).toBeVisible();
		expect(await topic.getAttribute('href'), 'a topic pill is not a link to a route').toMatch(
			/\/[a-z0-9-]+\/$/
		);
		await topic.click();
		await expect(page).toHaveURL(new RegExp(`/${DAY}/[a-z0-9-]+/$`));
		await expect(page.locator('article').first()).toBeVisible();
	} finally {
		await context.close();
	}
});

test('the panel sticks at the wide breakpoint and nowhere below it', async ({ page }) => {
	// `frame.breakpoints_px[1]` is 1024, where the pills and the field share one
	// band. Below it the panel can run to several wrapped lines, and a control
	// holding a third of a phone screen for the whole scroll is screen the
	// reader paid for.
	await page.goto(`/${DAY}/`);
	const panel = page.locator('[data-filter-bar]');
	await expect(panel).toHaveCount(1);

	for (const [width, wanted] of [
		[360, 'static'],
		[801, 'static'],
		[1024, 'sticky'],
		[1536, 'sticky']
	] as const) {
		await page.setViewportSize({ width, height: 900 });
		await expect(panel, `the panel is not ${wanted} at ${width}px`).toHaveCSS('position', wanted);
	}
});
