import { expect, test, type Page } from '@playwright/test';

/**
 * Row #6's oracle: the run strip is painted at fill weight, and it starts where
 * its grid starts.
 *
 * Two defects sat side by side on this section and neither is visible in a
 * diff. The squares were painted with `--band-high`, `--band-medium` and
 * `--band-low`, which are TEXT colours - measured against the surface the strip
 * sits on they run 5.0:1 to 6.1:1 in the light theme, and at 16px solid they
 * read as olive and brick rather than as a state. And the strip was jammed to
 * the right edge, so a run an operator looked at yesterday moved a column left
 * every time a day published.
 *
 * The contrast numbers below are computed here, from the WCAG 2.2 relative
 * luminance formula written out in this file. That is deliberate: `CLAUDE.md`
 * section 0a makes accessibility AUDIT TOOLING a project non-goal, so this row
 * adds no dependency and gates nothing but itself. It is one row's own oracle,
 * measuring the thing that row changed.
 */

/** The band a fill has to land in, and where each bound comes from.
 *
 * FLOOR, both themes - WCAG 2.2 SC 1.4.11 (non-text contrast). A graphical
 * object that carries meaning has to reach 3:1 against what it sits on, or the
 * shape itself is not distinguishable from the surface.
 *
 * CEILING, light theme - WCAG 2.2 SC 1.4.3 makes 4.5:1 the MINIMUM for normal
 * text, so a colour at or above it is a text-weight colour. That is exactly the
 * defect this row removes.
 *
 * CEILING, dark theme - a fill on a dark ground is lighter than its ground, so
 * it can never become ink and the light ceiling does not apply. What it can do
 * is get as loud as the page's own type, so the ceiling is a tripwire measured
 * rather than borrowed: the loudest dark fill read 7.943:1 on 2026-08-30, and
 * 9.0 leaves it 13 percent of headroom while failing `--color-text` (14.932:1)
 * and pure white (17.619:1) by a wide margin.
 */
const FILL_FLOOR = 3;
const LIGHT_FILL_CEILING = 4.5;
const DARK_FILL_CEILING = 9;

const DESKTOP = { width: 1440, height: 900 };

/** Wide on purpose. `cellFor` caps a day column, so past a frame width the strip
 * cannot fill its room whatever the ledger holds - which is what makes the
 * alignment premise below a property of the layout, not of today's data. */
const UNDERFULL = { width: 1680, height: 900 };
const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

const CEILING: Record<Theme, number> = {
	light: LIGHT_FILL_CEILING,
	dark: DARK_FILL_CEILING
};

/** WCAG 2.2 relative luminance. Written out rather than imported. */
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
	return Math.round(value * 1000) / 1000;
}

async function openConsole(page: Page, theme: Theme, viewport = DESKTOP) {
	await page.setViewportSize(viewport);
	await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);
	await page.goto('/console/');
	await expect
		.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
		.toBe(theme);
}

/** Every colour the assertions below need, read off the live document. */
function paints(page: Page) {
	return page.evaluate(() => {
		const style = getComputedStyle(document.documentElement);
		const token = (name: string) => style.getPropertyValue(name).trim();
		const square = document.querySelector('[data-health]');
		const panel = document.querySelector('[data-console-panel="Run health"]');
		return {
			surface: token('--color-surface'),
			fill: {
				high: token('--fill-high'),
				medium: token('--fill-medium'),
				low: token('--fill-low')
			},
			band: {
				high: token('--band-high'),
				medium: token('--band-medium'),
				low: token('--band-low')
			},
			squarePaint: square ? getComputedStyle(square).backgroundColor : null,
			squareHealth: square ? square.getAttribute('data-health') : null,
			panelPaint: panel ? getComputedStyle(panel).backgroundColor : null
		};
	});
}

for (const theme of THEMES) {
	test(`THE ORACLE: every fill is fill weight on the ${theme} panel`, async ({ page }) => {
		await openConsole(page, theme);
		const seen = await paints(page);

		// The surface the squares are drawn on is the panel's, and the panel takes
		// `--color-surface`. Asserting that first is what makes the ratios below
		// answer the question the row asked: before this row the strip sat on the
		// page background with no panel at all.
		expect(seen.panelPaint, 'the run strip is not inside a panel').not.toBeNull();
		expect(
			rgb(seen.panelPaint as string),
			'the panel is not painted --color-surface, so the ratios below measure the wrong ground'
		).toEqual(rgb(seen.surface));

		const measured: Record<string, number> = {};
		for (const [name, value] of Object.entries(seen.fill)) {
			expect(value, `--fill-${name} is not declared in the ${theme} theme`).not.toBe('');
			measured[name] = round(contrast(rgb(value), rgb(seen.surface)));
		}

		for (const [name, ratio] of Object.entries(measured)) {
			expect(
				ratio,
				`--fill-${name} is ${ratio}:1 on ${theme}; under ${FILL_FLOOR}:1 the square is not distinguishable from the surface`
			).toBeGreaterThanOrEqual(FILL_FLOOR);
			expect(
				ratio,
				`--fill-${name} is ${ratio}:1 on ${theme}; at or over ${CEILING[theme]}:1 it is a text-weight colour, not a fill`
			).toBeLessThan(CEILING[theme]);
		}
	});

	test(`the square on the page is painted with the fill ramp, ${theme}`, async ({ page }) => {
		// A token in the band is worth nothing if the markup still reads the other
		// ramp. This is the half that catches that.
		await openConsole(page, theme);
		const seen = await paints(page);

		expect(seen.squareHealth, 'no run square on the page').not.toBeNull();
		const wanted = { green: seen.fill.high, amber: seen.fill.medium, red: seen.fill.low }[
			seen.squareHealth as 'green' | 'amber' | 'red'
		];
		expect(
			rgb(seen.squarePaint as string),
			`a ${seen.squareHealth} square is painted ${seen.squarePaint}, not the fill token ${wanted}`
		).toEqual(rgb(wanted));
	});
}

test('the band ramp is text weight, which is the whole reason the fill ramp exists', async ({
	page
}) => {
	// The negative control. Point --fill-* back at --band-* and the light-theme
	// oracle above fails; this test is what says why, and it fails too if someone
	// "fixes" that by lightening the band tokens, which are read as type on four
	// other surfaces.
	await openConsole(page, 'light');
	const seen = await paints(page);

	for (const [name, value] of Object.entries(seen.band)) {
		const ratio = round(contrast(rgb(value), rgb(seen.surface)));
		expect(
			ratio,
			`--band-${name} is ${ratio}:1, under the ${LIGHT_FILL_CEILING}:1 that makes a colour text weight - it is a text colour and has to stay one`
		).toBeGreaterThanOrEqual(LIGHT_FILL_CEILING);
	}
});

test('THE ORACLE: a strip with room to spare starts at the left edge of its grid', async ({
	page
}) => {
	await openConsole(page, 'light', UNDERFULL);

	const geometry = await page.evaluate(() => {
		const box = (node: Element | null) => {
			if (!node) return null;
			const rect = node.getBoundingClientRect();
			return { x: rect.x, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width };
		};
		const days = [...document.querySelectorAll('[data-day]')];
		return {
			strip: box(document.querySelector('[data-run-history]')),
			grid: box(document.querySelector('[data-grid="days"]')),
			first: box(days[0]),
			last: box(days[days.length - 1]),
			count: days.length
		};
	});

	expect(geometry.count, 'the strip drew no day, so alignment asserts nothing').toBeGreaterThan(1);
	const drawn = (geometry.last as { right: number }).right - (geometry.first as { x: number }).x;
	const room = (geometry.strip as { width: number }).width;
	// The premise. On a full strip left and right alignment are the same picture,
	// so without this the test passes on a strip that proves nothing.
	expect(drawn, `the strip is full at ${UNDERFULL.width}px, so alignment cannot be told apart`).toBeLessThan(room - 2);

	expect(
		Math.abs((geometry.first as { x: number }).x - (geometry.grid as { x: number }).x),
		'the oldest day does not start at the left edge of the grid'
	).toBeLessThan(2);
	expect(
		Math.abs((geometry.first as { x: number }).x - (geometry.strip as { x: number }).x),
		'the grid does not start at the left edge of the strip'
	).toBeLessThan(2);
	// And the spare room is on the right, where the days that have not happened
	// yet belong. `today_anchor` still governs where an overflowing strip opens;
	// that is a scroll position, and this is an alignment.
	expect(
		(geometry.strip as { right: number }).right - (geometry.last as { right: number }).right,
		'there is no room left on the newest side, so nothing was actually anchored'
	).toBeGreaterThan(1);
});

test('the dates label the axis from below the grid', async ({ page }) => {
	await openConsole(page, 'light');

	const placed = await page.evaluate(() => {
		const bottom = (selector: string) =>
			Math.max(
				...[...document.querySelectorAll(selector)].map((n) => n.getBoundingClientRect().bottom)
			);
		const labels = [...document.querySelectorAll('[data-axis-label]')];
		return {
			labels: labels.length,
			labelTop: Math.min(...labels.map((n) => n.getBoundingClientRect().top)),
			squareBottom: bottom('[data-health]')
		};
	});

	expect(placed.labels, 'the axis carries no date at all').toBeGreaterThan(0);
	expect(
		placed.labelTop,
		'a date label overlaps the squares, so it reads as a row heading rather than an axis'
	).toBeGreaterThanOrEqual(placed.squareBottom - 1);
});

test('the strip says which window it is drawing', async ({ page }) => {
	await openConsole(page, 'light');

	// The section joined the shared window in this row, so it owes row #1's
	// contract: the attribute AND the sentence, because an attribute nobody
	// renders is a promise to a test rather than to an operator.
	const section = page.locator('[data-windowed="run-health"]');
	await expect(section).toHaveCount(1);
	const days = await section.getAttribute('data-window-days');
	expect(Number(days)).toBeGreaterThan(0);
	await expect(section).toContainText(`${days} days`);
});
