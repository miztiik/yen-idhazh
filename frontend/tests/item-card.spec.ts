/**
 * Row #8's oracle: the item is a surface that separates, and never one that
 * floats or moves.
 *
 * Three claims, and each one fails silently without a test.
 *
 * 1. **No shadow at rest, `--shadow-md` on hover and on focus.** A resting
 *    shadow is seventeen boxes floating over a page whose product is prose;
 *    a hover with no shadow is a card that never answers the pointer. Both
 *    look fine in a screenshot of the state somebody happened to capture.
 * 2. **No transform, ever.** The title is a heading rather than a link, so a
 *    2px rise promises a click the card does not answer - repeated on every
 *    row of a day that has published up to 621 items. `prefers-reduced-motion`
 *    zeroes durations, which turns a rise into a jump rather than removing it,
 *    so the reduced-motion arm measures the box rather than the duration.
 * 3. **The edge is visible on the ground it sits on.** Measured by the WCAG
 *    relative-luminance formula over the tokens the live document resolves,
 *    because a hairline that reads 1.36:1 on the dark ground is not an edge.
 *
 * The overflow assertions belong to `layout-overflow.spec.ts`, which row 3
 * creates. They are repeated inline here rather than left to it: this row gives
 * the item a border, a radius and padding on both axes, which is exactly the
 * change that pushes a page sideways, and the gate that would have caught it
 * does not exist yet.
 */

import { expect, test, type Page } from '@playwright/test';

const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

/** The reading route this row's two files reach with an item on it. `/archive/`
 * renders one too, but only for a search result, which needs a 43 MB encoder.
 *
 * `/archive/` is also out of the overflow check below for a reason worth
 * writing down: measured 2026-08-31 at 360px in both themes, its own day list
 * pushes the document to 368px through `li.border-b border-rule py-3`, with no
 * item on the page at all. That defect is row 3's and row 13's, not this one's,
 * and asserting it here would fail this row for someone else's file. */
const ROUTES = ['/'];

/** A phone, the side-rail breakpoint, and a wide desktop. `frame.breakpoints_px`
 * in `config/appearance.json` is [640, 1024, 1400]; 801 sits between two of them,
 * which is where a layout that only ever gets tested at a breakpoint breaks. */
const WIDTHS = [360, 801, 1536];

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
	if (parts) return parts[1].split(',').slice(0, 3).map((n) => Number(n.trim()));
	const text = value.trim().replace('#', '');
	if (/^[0-9a-f]{6}$/i.test(text)) {
		return [0, 2, 4].map((i) => parseInt(text.slice(i, i + 2), 16));
	}
	if (/^[0-9a-f]{3}$/i.test(text)) {
		return [0, 1, 2].map((i) => parseInt(text[i] + text[i], 16));
	}
	throw new Error(`not a colour: ${JSON.stringify(value)}`);
}

function round(value: number): number {
	return Math.round(value * 100) / 100;
}

async function open(page: Page, theme: Theme, route = '/', width = 1280) {
	await page.setViewportSize({ width, height: 900 });
	await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);
	await page.goto(route);
	await expect
		.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
		.toBe(theme);
}

/** The item's painted state, at rest and with the pointer on it.
 *
 * The hover read waits for the value the transition is going TO. Read in the
 * same task it returns the value it is leaving, and read one frame later it
 * returns an interpolation - either of which makes an exact comparison against
 * `--shadow-md` fail for a reason that is not the code under test.
 */
async function paints(page: Page) {
	const item = page.locator('article.item').first();
	await expect(item, 'no item on the page to measure').toBeVisible();
	// `hover()` scrolls the element into view, so the rest read has to happen
	// from where the hover read will happen or the card looks like it moved.
	await item.scrollIntoViewIfNeeded();

	/** `--shadow-md` as the browser computes it, so a hand-written shadow that
	 * merely looks similar does not pass. */
	const shadowMd = await page.evaluate(() => {
		const probe = document.createElement('div');
		probe.style.boxShadow = getComputedStyle(document.documentElement)
			.getPropertyValue('--shadow-md')
			.trim();
		document.body.appendChild(probe);
		const value = getComputedStyle(probe).boxShadow;
		probe.remove();
		return value;
	});

	const read = () =>
		page.evaluate(() => {
			const el = document.querySelector('article.item');
			if (!el) throw new Error('article.item disappeared');
			const style = getComputedStyle(el);
			const box = el.getBoundingClientRect();
			const root = getComputedStyle(document.documentElement);
			return {
				shadow: style.boxShadow,
				border: style.borderTopColor,
				borderWidth: style.borderTopWidth,
				radius: parseFloat(style.borderTopLeftRadius),
				background: style.backgroundColor,
				transform: style.transform,
				// Document-relative, so a scroll between two reads is not a move.
				top: Math.round(box.top + window.scrollY),
				left: Math.round(box.left + window.scrollX),
				height: Math.round(box.height),
				rem: parseFloat(root.fontSize),
				tokens: {
					bg: root.getPropertyValue('--color-bg').trim(),
					surface: root.getPropertyValue('--color-surface').trim(),
					rule: root.getPropertyValue('--color-rule').trim(),
					ruleStrong: root.getPropertyValue('--color-rule-strong').trim(),
					accent: root.getPropertyValue('--color-accent').trim(),
					radiusLg: parseFloat(root.getPropertyValue('--radius-lg'))
				}
			};
		});

	const rest = await read();
	await item.hover();
	await expect
		.poll(
			() =>
				page.evaluate(
					() => getComputedStyle(document.querySelector('article.item')!).boxShadow
				),
			{ message: 'the hover shadow never settled on --shadow-md' }
		)
		.toBe(shadowMd);
	const hover = await read();
	// Leave the pointer off the card so the next read starts from rest.
	await page.mouse.move(0, 0);
	return { rest, hover, shadowMd };
}

/** A box that resolves `--shadow-md` to something, in either theme. */
function shadowIsSet(value: string): boolean {
	return value !== 'none' && value.trim() !== '';
}

test.describe('the item is a low-chrome card', () => {
	for (const theme of THEMES) {
		test(`${theme}: no shadow at rest, --shadow-md on hover, and no lift`, async ({ page }) => {
			await open(page, theme);
			const { rest, hover, shadowMd } = await paints(page);

			// The whole of decision 1. A resting shadow makes every item float.
			expect(rest.shadow, `${theme} rest carries a shadow: ${rest.shadow}`).toBe('none');
			expect(hover.shadow, `${theme} hover shadow is not --shadow-md`).toBe(shadowMd);
			expect(shadowIsSet(shadowMd), `${theme} --shadow-md resolves to nothing`).toBe(true);

			// Decision 2: no lift, in either state, and the box does not move.
			expect(rest.transform, `${theme} rest carries a transform`).toBe('none');
			expect(hover.transform, `${theme} hover carries a transform`).toBe('none');
			expect(
				[hover.top, hover.left, hover.height],
				`${theme} the card moved on hover`
			).toEqual([rest.top, rest.left, rest.height]);
		});

		test(`${theme}: the edge warms on hover and on keyboard focus`, async ({ page }) => {
			await open(page, theme);
			const { rest, hover } = await paints(page);

			expect(rest.border, `${theme} the edge did not change on hover`).not.toBe(hover.border);
			expect(rgb(hover.border), `${theme} hover border is not the accent`).toEqual(
				rgb(hover.tokens.accent)
			);

			// :focus-within earns the same state for a reader who never uses a
			// pointer.
			const focused = await page.evaluate(() => {
				const card = document.querySelector('article.item');
				const target = card?.querySelector<HTMLElement>('a[href], button');
				target?.focus();
				return Boolean(target && card?.contains(document.activeElement));
			});
			expect(focused, 'the first card holds nothing focusable').toBe(true);
			// The edge is transitioned, so a read taken now returns an
			// interpolation between the two colours rather than either of them.
			await expect
				.poll(
					() =>
						page.evaluate(
							() => getComputedStyle(document.querySelector('article.item')!).borderTopColor
						),
					{ message: `${theme} focus-within did not warm the edge` }
				)
				.toBe(hover.border);
			const onFocusShadow = await page.evaluate(
				() => getComputedStyle(document.querySelector('article.item')!).boxShadow
			);
			expect(shadowIsSet(onFocusShadow), `${theme} focus-within carries no shadow`).toBe(true);
		});

		test(`${theme}: the edge is visible on the ground it sits on`, async ({ page }) => {
			await open(page, theme);
			const { rest } = await paints(page);
			const t = rest.tokens;

			// Decision 6, recomputed rather than restated. On dark the surface
			// lift alone is about 1.10:1, so the hairline is the separation.
			const edgeOnGround = contrast(rgb(rest.border), rgb(t.bg));
			const weakOnGround = contrast(rgb(t.rule), rgb(t.bg));
			const strongOnGround = contrast(rgb(t.ruleStrong), rgb(t.bg));
			const lift = contrast(rgb(t.surface), rgb(t.bg));

			// Printed so the number a commit message quotes came from this run.
			console.log(
				`${theme}: edge ${round(edgeOnGround)}:1, --color-rule ${round(weakOnGround)}:1, ` +
					`--color-rule-strong ${round(strongOnGround)}:1, surface lift ${round(lift)}:1`
			);

			expect(
				strongOnGround,
				`--color-rule-strong is not the stronger edge in ${theme}`
			).toBeGreaterThan(weakOnGround);
			expect(edgeOnGround, `${theme} the edge is weaker than --color-rule`).toBeGreaterThanOrEqual(
				weakOnGround
			);

			if (theme === 'dark') {
				// The weaker rule is not an edge on this ground, and the card
				// must not be taking it.
				expect(round(weakOnGround), 'dark --color-rule on --color-bg moved').toBe(1.36);
				expect(round(strongOnGround), 'dark --color-rule-strong on --color-bg moved').toBe(1.77);
				expect(rgb(rest.border), 'the dark card is on the weaker rule').toEqual(rgb(t.ruleStrong));
			} else {
				expect(rgb(rest.border), 'the light card is not on --color-rule').toEqual(rgb(t.rule));
			}

			// The rest of decision 1: a surface, a radius and a hairline.
			expect(rgb(rest.background), `${theme} the card is not on --color-surface`).toEqual(
				rgb(t.surface)
			);
			expect(rest.radius, `${theme} the card radius is not --radius-lg`).toBeCloseTo(
				t.radiusLg * rest.rem,
				1
			);
			expect(rest.borderWidth, `${theme} the hairline is not 1px`).toBe('1px');
		});

		test(`${theme}: reduced motion leaves the card exactly where it was`, async ({ page }) => {
			// Decision 3. A zeroed transition-duration makes a rise instant; it
			// does not remove one. So this measures the box, not the duration.
			await page.emulateMedia({ reducedMotion: 'reduce' });
			await open(page, theme);
			const { rest, hover } = await paints(page);

			expect(rest.transform, `${theme} rest transform under reduced motion`).toBe('none');
			expect(hover.transform, `${theme} hover transform under reduced motion`).toBe('none');
			expect(
				[hover.top, hover.left, hover.height],
				`${theme} the card moved under reduced motion`
			).toEqual([rest.top, rest.left, rest.height]);
			// The state still arrives - stillness is not the same as no feedback.
			expect(shadowIsSet(hover.shadow), `${theme} reduced motion removed the hover state`).toBe(
				true
			);
		});
	}

	test('the card never pushes a reading route sideways', async ({ page }) => {
		// Row 3 owns `layout-overflow.spec.ts` and has not landed. This is the
		// same property, asserted on the routes this row's files reach: a border,
		// a radius and padding on both axes is exactly the change that pushes a
		// page sideways, and the gate that would catch it does not exist yet.
		await open(page, 'light');
		// The day route for the day the home page is showing. The previous-day
		// list points at days the fixture publishes nothing for, so a link taken
		// from there reaches an empty page and proves nothing about a card.
		const day = await page.evaluate(() => {
			const link = document.querySelector<HTMLAnchorElement>('nav[aria-label="Topics"] a[href]');
			return link ? new URL(link.href).pathname : '';
		});
		expect(day, 'no topic-pill link on the home page to take a day route from').toMatch(
			/\/\d{4}-\d{2}-\d{2}\/$/
		);

		for (const theme of THEMES) {
			for (const route of [...ROUTES, day]) {
				for (const width of WIDTHS) {
					await open(page, theme, route, width);
					const scroll = await page.evaluate(() => ({
						scrollWidth: document.documentElement.scrollWidth,
						clientWidth: document.documentElement.clientWidth,
						items: document.querySelectorAll('article.item').length
					}));
					expect(scroll.items, `${theme} ${route} at ${width}px renders no item`).toBeGreaterThan(
						0
					);
					expect(
						scroll.scrollWidth,
						`${theme} ${route} at ${width}px scrolls sideways: ${scroll.scrollWidth} > ${scroll.clientWidth}`
					).toBeLessThanOrEqual(scroll.clientWidth);
				}
			}
		}
	});

	test('the title is the step the eye lands on, and the summary is not', async ({ page }) => {
		// Decision 4. The contrast is what matters, so both are read off one
		// card rather than checked against a number written here twice.
		await open(page, 'dark');
		const sizes = await page.evaluate(() => {
			const card = document.querySelector('article.item');
			if (!card) throw new Error('no item');
			const heading = card.querySelector('h2, h3');
			const summary = card.querySelector('p.measure');
			const eyebrow = card.querySelector('p.uppercase');
			const px = (el: Element | null) => (el ? parseFloat(getComputedStyle(el).fontSize) : 0);
			const root = getComputedStyle(document.documentElement);
			return {
				title: px(heading),
				summary: px(summary),
				eyebrow: px(eyebrow),
				text2xl: root.getPropertyValue('--text-2xl').trim(),
				textLg: root.getPropertyValue('--text-lg').trim(),
				textXs: root.getPropertyValue('--text-xs').trim(),
				rem: parseFloat(getComputedStyle(document.documentElement).fontSize)
			};
		});
		const step = (token: string, rem: number) => parseFloat(token) * rem;

		expect(sizes.title, 'the title is not --text-2xl').toBeCloseTo(
			step(sizes.text2xl, sizes.rem),
			1
		);
		expect(sizes.summary, 'the summary left the reading step').toBeCloseTo(
			step(sizes.textLg, sizes.rem),
			1
		);
		expect(sizes.eyebrow, 'the item meta is not --text-xs').toBeCloseTo(
			step(sizes.textXs, sizes.rem),
			1
		);
		expect(sizes.title, 'the title does not lead the summary').toBeGreaterThan(sizes.summary);
	});
});
