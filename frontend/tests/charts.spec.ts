import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chartFunnel } from '../src/lib/charts/chart-funnel';
import { SENTINEL_PATTERN, paint } from '../src/lib/charts/theme';

/**
 * A chart on this site has to be two things at once, and the two pull apart.
 *
 * It has to be complete before any script runs, because the operator opening
 * the console on a blocked or slow connection still needs to see the shape.
 * And it has to be interactive after, because a mark without a readout makes
 * you guess the number.
 *
 * The way both hold is that the server draws the SVG at build time and the
 * engine only ever replaces something already correct. These tests are the two
 * halves of that promise: the marks are in the raw HTML, and the engine that
 * would have drawn them is not on any page that did not ask for one.
 */

const BUILD = resolve(process.cwd(), 'build');

function filesUnder(root: string, ext: string): string[] {
	const out: string[] = [];
	const walk = (at: string) => {
		for (const entry of readdirSync(at, { withFileTypes: true })) {
			const path = join(at, entry.name);
			if (entry.isDirectory()) walk(path);
			else if (entry.name.endsWith(ext)) out.push(path);
		}
	};
	walk(root);
	return out;
}

test.describe('the prerendered chart', () => {
	test('the console carries the funnel as real marks, with no script at all', () => {
		// Read as raw text on purpose. A rendered DOM cannot tell the difference
		// between a mark the server drew and one the engine drew a moment ago,
		// which is exactly the difference this test exists to prove.
		const html = readFileSync(join(BUILD, 'console', 'index.html'), 'utf8');

		expect(html).toContain('data-funnel="chart"');
		// Four stages, four filled bands.
		expect(html.match(/<polygon/g) ?? []).toHaveLength(4);
		for (const label of ['Reached', 'Asked the model', 'Drafted', 'Published']) {
			expect(html).toContain(label);
		}
	});

	test('colour leaves as a token, so both themes work before any script runs', () => {
		const html = readFileSync(join(BUILD, 'console', 'index.html'), 'utf8');
		const funnel = html.slice(html.indexOf('data-funnel="chart"'));

		// Each band names a custom property rather than a hex. This is the whole
		// reason a theme change costs nothing and does not need JavaScript.
		for (const token of ['--chart-1', '--chart-2', '--chart-3', '--chart-4']) {
			expect(funnel).toContain(`var(${token})`);
		}
	});

	test('no sentinel colour reaches a reader on any page', () => {
		// A sentinel is a reserved magenta the server draws with and swaps out.
		// One that survives is a magenta chart, so the check is every built page
		// rather than the one under test.
		const leaked = filesUnder(BUILD, '.html').filter((path) =>
			SENTINEL_PATTERN.test(readFileSync(path, 'utf8'))
		);
		expect(leaked).toEqual([]);
	});
});

test.describe('the engine stays where it was put', () => {
	test('no route preloads the engine, so nothing downloads it to read a page', () => {
		const chunks = filesUnder(join(BUILD, '_app', 'immutable'), '.js');
		const engine = chunks.filter(
			(path) => statSync(path).size > 200_000 && readFileSync(path, 'utf8').includes('funnel')
		);
		expect(engine.length).toBeGreaterThan(0);

		const names = engine.map((path) => path.split(/[\\/]/).pop() as string);
		for (const page of filesUnder(BUILD, '.html')) {
			const html = readFileSync(page, 'utf8');
			for (const name of names) {
				// A `modulepreload` would make the engine part of opening the page.
				// It has to stay a dynamic import that only a live chart triggers.
				expect(html, `${page} preloads ${name}`).not.toContain(name);
			}
		}
	});

	test('the reading routes carry no chart module at all', () => {
		const reading = filesUnder(BUILD, '.html').filter((path) => !path.includes('console'));
		expect(reading.length).toBeGreaterThan(0);
		for (const page of reading) {
			expect(readFileSync(page, 'utf8')).not.toContain('data-funnel');
		}
	});
});

test.describe('the option the engine is given', () => {
	const days = [
		{ reached: 1000, asked: 700, drafted: 100, published: 80 },
		{ reached: 500, asked: 300, drafted: 50, published: 40 }
	];

	test('a band is as wide as its count, and the narrowest one is flat', () => {
		const { option, empty } = chartFunnel(days);
		expect(empty).toBe(false);

		const series = (option.series as Record<string, unknown>[])[0];
		expect(series.min).toBe(120);
		expect(series.max).toBe(1500);
		// The smallest value's own share is its minimum width, which is what makes
		// the mapping exactly proportional and squares off the bottom band.
		expect(series.minSize).toBe(`${(120 / 1500) * 100}%`);
	});

	test('nothing reached is not a funnel of zeros', () => {
		// Zero reached means nothing committed says what the router did. Four
		// zero-width bands draw a rectangle, which reads as a working stage.
		const { empty } = chartFunnel([{ reached: 0, asked: 0, drafted: 0, published: 0 }]);
		expect(empty).toBe(true);
	});

	test('every colour in the option is a sentinel, never a hex somebody typed', () => {
		const { option } = chartFunnel(days);
		const colours: string[] = [];
		const walk = (node: unknown) => {
			if (typeof node === 'string') {
				if (node.startsWith('#')) colours.push(node);
			} else if (Array.isArray(node)) node.forEach(walk);
			else if (node !== null && typeof node === 'object') Object.values(node).forEach(walk);
		};
		walk(option);

		expect(colours.length).toBeGreaterThan(0);
		for (const colour of colours) expect(colour).toMatch(SENTINEL_PATTERN);
	});
});

test.describe('the live chart', () => {
	test('the engine is handed real colours, never the sentinels', async ({ page }) => {
		await page.goto('/console/');
		const resolved = await page.evaluate(() => {
			const el = document.querySelector('[data-funnel="chart"]');
			return el === null ? null : /#ff00[0-9a-f]{2}/i.test(el.innerHTML);
		});
		expect(resolved).toBe(false);
	});

	test('a theme change repaints the marks', async ({ page }) => {
		await page.goto('/console/');
		const fills = await page.evaluate(async () => {
			const read = () =>
				[...document.querySelectorAll('[data-funnel="chart"] svg path, [data-funnel="chart"] svg polygon')]
					.map((node) => node.getAttribute('fill') ?? '')
					.filter((fill) => fill !== '' && fill !== 'none');
			const set = async (theme: string) => {
				document.documentElement.setAttribute('data-theme', theme);
				await new Promise((done) => setTimeout(done, 600));
				return read();
			};
			return { dark: await set('dark'), light: await set('light') };
		});

		expect(fills.dark.length).toBeGreaterThan(0);
		expect(fills.light).not.toEqual(fills.dark);
	});
});

test.describe('the token bridge', () => {
	test('a sentinel maps back to the value the document computes', async ({ page }) => {
		await page.goto('/console/');
		const swapped = await page.evaluate(() => {
			const style = getComputedStyle(document.documentElement);
			return style.getPropertyValue('--chart-1').trim();
		});
		expect(swapped).toMatch(/^#[0-9a-f]{6}$/i);
	});

	test('paint refuses a token the palette does not have', () => {
		// The closed set is the point: a chart cannot invent a colour.
		expect(() => paint('--not-a-token' as never)).toThrow();
	});
});
