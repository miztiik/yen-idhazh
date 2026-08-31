/**
 * Row #12's oracle: the monogram carries the read state, and it carries it in
 * a way that survives a bad screen.
 *
 * Four claims, and each one fails silently without a test.
 *
 * 1. **Fill present or absent is the signal.** Unread is a filled ring, read is
 *    a hollow one. Dimmer text plus a lighter weight is one signal twice - both
 *    are less ink, so they fail together on a cheap panel, in sunlight and at
 *    arm's length. An area difference does not.
 * 2. **The fill has to be on screen.** Measured here against the live
 *    `--color-surface` rather than restated from the token file, because a
 *    swatch that reads 1.2:1 makes a filled ring and a hollow one the same
 *    ring, and nothing about the markup would say so.
 * 3. **The mark leads the item at every width.** It used to sit in the meta
 *    line, which moves into a 14rem right rail at the side-rail breakpoint, so
 *    on a wide screen the read indicator sat 14rem from the title it
 *    qualifies.
 * 4. **A fill and a font weight are announced to nobody.** The heading opens
 *    with a visually-hidden word, and the mark itself stays hidden - its
 *    letters repeat the source name printed beside it.
 *
 * The overflow assertion at 360px belongs to `layout-overflow.spec.ts`, which
 * row 3 creates. It is repeated inline here rather than left to it: this row
 * puts a new column on the leading edge of every item at the narrowest width,
 * which is exactly the change that pushes a page sideways, and the gate that
 * would catch it does not exist yet.
 */

import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { monogram, swatchIndex } from '../src/lib/format';

const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

const READ_KEY = 'idhazh:read';
const THEME_KEY = 'idhazh:theme';
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

type Item = { item_id: string; source_id: string; source_name: string; title: string };

/** The day this build publishes, discovered rather than hardcoded.
 *
 * The browser suite runs against the canary build, which carries one day. A
 * hardcoded date would pass on an empty 404 page the moment that day moved.
 */
function publishedDay(): { date: string; items: Item[] } {
	const dirs = (at: string) =>
		readdirSync(at, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort();
	const year = dirs(CANARY).at(-1) as string;
	const month = dirs(join(CANARY, year)).at(-1) as string;
	const day = dirs(join(CANARY, year, month)).at(-1) as string;
	const raw = readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8');
	return { date: `${year}-${month}-${day}`, items: (JSON.parse(raw) as { items: Item[] }).items };
}

const { date: DAY, items: ITEMS } = publishedDay();
const BY_ID = new Map(ITEMS.map((item) => [item.item_id, item]));

/** WCAG 2.2 relative luminance. Written out rather than imported: audit tooling
 * is a project non-goal, and this is one surface's oracle over its own tokens. */
function luminance([r, g, b]: number[]): number {
	const channel = (value: number) => {
		const s = value / 255;
		return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: number[], b: number[]): number {
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (high + 0.05) / (low + 0.05);
}

/** A colour as the browser hands it back: `rgb(...)`, `#rrggbb` or `#rgb`. */
function rgb(value: string): number[] {
	const parts = /rgba?\(([^)]+)\)/.exec(value);
	if (parts) {
		return parts[1]
			.split(/[,/\s]+/)
			.filter((part) => part.length > 0)
			.slice(0, 3)
			.map((n) => Number(n));
	}
	const text = value.trim().replace('#', '');
	if (/^[0-9a-f]{6}$/i.test(text)) {
		return [0, 2, 4].map((i) => parseInt(text.slice(i, i + 2), 16));
	}
	if (/^[0-9a-f]{3}$/i.test(text)) {
		return [0, 1, 2].map((i) => parseInt(text[i] + text[i], 16));
	}
	throw new Error(`not a colour: ${JSON.stringify(value)}`);
}

/** Transparent, whichever of the three ways the browser spells it. */
function isTransparent(value: string): boolean {
	const parts = /rgba?\(([^)]+)\)/.exec(value);
	if (!parts) return value.trim() === 'transparent' || value.trim() === 'none';
	const numbers = parts[1].split(/[,/\s]+/).filter((part) => part.length > 0);
	return numbers.length === 4 && Number(numbers[3]) === 0;
}

function round(value: number): number {
	return Math.round(value * 100) / 100;
}

/** The item's own heading. An attribute selector rather than `#id`, because the
 * ids come from the payload and nothing here should have to escape one. */
function heading(page: Page, itemId: string) {
	return page.locator(`article[id="${itemId}"] :is(h1, h2, h3)`).first();
}

async function open(
	page: Page,
	theme: Theme,
	{ read = [] as string[], route = `/${DAY}/`, width = 1280 } = {}
) {
	await page.setViewportSize({ width, height: 900 });
	await page.addInitScript(
		(given: { themeKey: string; theme: string; readKey: string; marks: unknown }) => {
			localStorage.setItem(given.themeKey, given.theme);
			localStorage.setItem(given.readKey, JSON.stringify(given.marks));
		},
		{ themeKey: THEME_KEY, theme, readKey: READ_KEY, marks: { [DAY]: read } }
	);
	await page.goto(route);
	await expect
		.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
		.toBe(theme);
	// Read marks are applied on hydration, so the prerendered document says
	// `data-read="false"` for a moment on every item. Measuring before that
	// lands reports an unread page and reads exactly like a broken mark.
	for (const itemId of read) {
		await expect(
			page.locator(`article[id="${itemId}"]`),
			'the seeded read mark never reached the page'
		).toHaveAttribute('data-read', 'true');
	}
}

/** What every mark on the page is painted as, keyed by the item it marks. */
async function marks(page: Page) {
	const item = page.locator('article.item').first();
	await expect(item, 'no item on the page to measure').toBeVisible();
	return page.evaluate(() => {
		const root = getComputedStyle(document.documentElement);
		const swatches = Array.from({ length: 8 }, (_, n) =>
			root.getPropertyValue(`--source-swatch-${n}`).trim()
		);
		return {
			tokens: {
				surface: root.getPropertyValue('--color-surface').trim(),
				rule: root.getPropertyValue('--color-rule').trim(),
				ruleStrong: root.getPropertyValue('--color-rule-strong').trim(),
				radiusFull: root.getPropertyValue('--radius-full').trim(),
				swatches
			},
			rem: parseFloat(root.fontSize),
			items: [...document.querySelectorAll('article.item')].map((article) => {
				const mark = article.querySelector<HTMLElement>('.source-mark');
				const title = article.querySelector<HTMLElement>('h1, h2, h3');
				const markBox = mark?.getBoundingClientRect();
				const titleBox = title?.getBoundingClientRect();
				const style = mark ? getComputedStyle(mark) : null;
				return {
					id: article.id,
					read: article.getAttribute('data-read'),
					hasMark: Boolean(mark),
					markRead: mark?.getAttribute('data-read') ?? null,
					hidden: mark?.getAttribute('aria-hidden') ?? null,
					letters: (mark?.textContent ?? '').trim(),
					background: style?.backgroundColor ?? '',
					border: style?.borderTopColor ?? '',
					borderWidth: style?.borderTopWidth ?? '',
					radius: style?.borderTopLeftRadius ?? '',
					width: markBox ? Math.round(markBox.width * 100) / 100 : 0,
					height: markBox ? Math.round(markBox.height * 100) / 100 : 0,
					// Document-relative, so a scroll between two reads is not a move.
					markRight: markBox ? markBox.right + window.scrollX : 0,
					titleLeft: titleBox ? titleBox.left + window.scrollX : 0,
					markTop: markBox ? markBox.top + window.scrollY : 0,
					titleTop: titleBox ? titleBox.top + window.scrollY : 0
				};
			})
		};
	});
}

test.describe('the monogram carries the read state', () => {
	for (const theme of THEMES) {
		test(`${theme}: an unread mark is filled and a read one is hollow`, async ({ page }) => {
			// Decision 1, measured as paint rather than as markup. The first item
			// is read and the rest are not, so both states are on one page in one
			// build and a rule that painted every ring the same would fail.
			const first = ITEMS[0].item_id;
			await open(page, theme, { read: [first] });
			const { items, tokens } = await marks(page);
			expect(items.length, 'no items rendered').toBeGreaterThan(1);

			const read = items.find((item) => item.id === first);
			const unread = items.filter((item) => item.id !== first);
			expect(read, 'the seeded item is not on the page').toBeTruthy();
			expect(read!.read, 'the seeded item did not come back read').toBe('true');
			expect(read!.markRead, 'the mark does not know the item is read').toBe('true');

			expect(
				isTransparent(read!.background),
				`${theme} a read mark is still filled: ${read!.background}`
			).toBe(true);
			expect(rgb(read!.border), `${theme} a read mark is not on --color-rule`).toEqual(
				rgb(tokens.rule)
			);

			for (const item of unread) {
				expect(
					isTransparent(item.background),
					`${theme} an unread mark has no fill: ${item.id}`
				).toBe(false);
				expect(
					rgb(item.border),
					`${theme} an unread mark is not on --color-rule-strong: ${item.id}`
				).toEqual(rgb(tokens.ruleStrong));
			}

			// Decision 2: a hairline in BOTH states, so what changed is the area
			// and not the weight of the edge.
			for (const item of items) {
				expect(item.borderWidth, `${theme} the ring is not a hairline: ${item.id}`).toBe('1px');
			}
		});

		test(`${theme}: the fill is the item's own swatch, and it is on screen`, async ({ page }) => {
			await open(page, theme);
			const { items, tokens } = await marks(page);
			const surface = rgb(tokens.surface);

			// Every swatch, recomputed against the surface the card is painted on.
			// Below this the two rings are one ring and the whole ruling collapses
			// back onto brightness.
			for (const [index, swatch] of tokens.swatches.entries()) {
				const ratio = contrast(rgb(swatch), surface);
				console.log(
					`${theme} --source-swatch-${index} ${swatch} on ${tokens.surface}: ${round(ratio)}:1`
				);
				expect(
					ratio,
					`${theme} --source-swatch-${index} reads ${round(ratio)}:1 on the card`
				).toBeGreaterThanOrEqual(1.5);
			}

			// And the fill an item gets is the one its own source id indexes.
			// Read through the published payload rather than off a fixed list, so
			// a mark that stopped following the source would fail here.
			for (const item of items) {
				const payload = BY_ID.get(item.id);
				expect(payload, `no payload item for ${item.id}`).toBeTruthy();
				expect(rgb(item.background), `${theme} wrong swatch on ${item.id}`).toEqual(
					rgb(tokens.swatches[swatchIndex(payload!.source_id)])
				);
				expect(item.letters, `${theme} wrong monogram on ${item.id}`).toBe(
					monogram(payload!.source_name)
				);
			}
		});

		test(`${theme}: the ring is a circle that grows with the reader's text`, async ({ page }) => {
			// Decision 2, and owner decision 13. A pixel count would leave the
			// mark behind the words beside it the moment a reader raises their
			// browser's font size, which is the reason the size is in rem.
			await open(page, theme);
			const before = await marks(page);
			const ring = before.items[0];

			expect(ring.width, `${theme} the ring is not 1.75rem wide`).toBeCloseTo(
				1.75 * before.rem,
				1
			);
			expect(ring.height, `${theme} the ring is not square`).toBeCloseTo(ring.width, 1);
			// --radius-full is a large constant rather than a percentage, so the
			// painted radius clamps to half the box. Either spelling is a circle.
			expect(
				parseFloat(ring.radius),
				`${theme} the ring is not round: ${ring.radius}`
			).toBeGreaterThanOrEqual(ring.width / 2 - 0.5);

			await page.evaluate(() => {
				document.documentElement.style.fontSize = '24px';
			});
			const after = await marks(page);
			expect(after.rem, 'the root font size did not move').toBeCloseTo(24, 1);
			expect(
				after.items[0].width,
				`${theme} the ring did not follow the root font size`
			).toBeCloseTo(1.75 * 24, 1);
		});

		for (const width of [360, 1536]) {
			test(`${theme}: at ${width}px the mark leads the item`, async ({ page }) => {
				// Decision 3. On a wide screen the meta line moves into a 14rem
				// right rail, so a mark left in it sits 14rem from the title it
				// qualifies - which is paired with nothing.
				await open(page, theme, { read: [ITEMS[0].item_id], width });
				const { items } = await marks(page);
				for (const item of items) {
					expect(item.hasMark, `no mark on ${item.id} at ${width}px`).toBe(true);
					expect(
						item.markRight,
						`${theme} at ${width}px the mark is not left of the title on ${item.id}`
					).toBeLessThanOrEqual(item.titleLeft);
					// And it leads rather than trails: the mark starts no lower
					// than the title it belongs to.
					expect(
						item.markTop,
						`${theme} at ${width}px the mark sits below its title on ${item.id}`
					).toBeLessThanOrEqual(item.titleTop);
				}
			});
		}

		test(`${theme}: the read state is a word, not only a colour`, async ({ page }) => {
			// Decision 5. A fill and a font weight are announced to nobody, so the
			// heading carries the state in text - and the mark stays hidden,
			// because its letters repeat the source name printed beside it.
			const read = ITEMS[0];
			const unread = ITEMS.find((item) => item.item_id !== read.item_id)!;
			await open(page, theme, { read: [read.item_id] });

			// The name is asserted whole rather than by prefix. That is also what
			// proves the monogram never reached the tree: two letters appearing in
			// the name would make this fail.
			await expect(
				heading(page, read.item_id),
				'a read item does not say so in its accessible name'
			).toHaveAccessibleName(`Read. ${read.title}`);
			await expect(
				heading(page, unread.item_id),
				'an unread item claims to have been read'
			).toHaveAccessibleName(unread.title);

			const mark = page.locator(`article[id="${read.item_id}"] .source-mark`);
			await expect(mark, 'the mark is no longer hidden').toHaveAttribute('aria-hidden', 'true');

			const tree = await page.locator(`article[id="${read.item_id}"]`).ariaSnapshot();
			console.log(`${theme} read item accessibility tree:\n${tree}`);
			expect(tree, 'the read state is missing from the tree').toContain('Read.');
		});
	}

	test('the leading column never pushes a reading route sideways', async ({ page }) => {
		// Row 3 owns `layout-overflow.spec.ts` and has not landed. This is the
		// same property, on the routes this row's files reach: a new column at
		// the narrowest width is exactly the change that pushes a page sideways.
		//
		// `/archive/` is out for a reason worth writing down: measured
		// 2026-08-31 at 360px, its own day list already pushes the document to
		// 368px with no item on the page at all. That defect belongs to rows 3
		// and 13, and asserting it here would fail this row for someone else's
		// file.
		for (const theme of THEMES) {
			for (const route of ['/', `/${DAY}/`]) {
				await open(page, theme, { read: [ITEMS[0].item_id], route, width: 360 });
				const sizes = await page.evaluate(() => ({
					scrollWidth: document.documentElement.scrollWidth,
					clientWidth: document.documentElement.clientWidth
				}));
				expect(
					sizes.scrollWidth,
					`${theme} ${route} scrolls sideways: ${sizes.scrollWidth} > ${sizes.clientWidth}`
				).toBeLessThanOrEqual(sizes.clientWidth);
			}
		}
	});
});
