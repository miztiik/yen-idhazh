import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chartFlow } from '../src/lib/charts/chart-flow';
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
	test('the console carries the flow as real marks, with no script at all', () => {
		// Read as raw text on purpose. A rendered DOM cannot tell the difference
		// between a mark the server drew and one the engine drew a moment ago,
		// which is exactly the difference this test exists to prove.
		const html = readFileSync(join(BUILD, 'console', 'index.html'), 'utf8');

		expect(html).toContain('data-flow="chart"');
		for (const label of ['Reached', 'Asked the model', 'Drafted', 'Published']) {
			expect(html).toContain(label);
		}
		// Every drop is named. A taper says an item was lost; these say how.
		for (const loss of ['Answered without a visual', 'The model drew nothing']) {
			expect(html).toContain(loss);
		}
	});

	test('colour leaves as a token, so both themes work before any script runs', () => {
		const html = readFileSync(join(BUILD, 'console', 'index.html'), 'utf8');
		const flow = html.slice(html.indexOf('data-flow="chart"'));

		// Each stage names a custom property rather than a hex. This is the whole
		// reason a theme change costs nothing and does not need JavaScript.
		for (const token of ['--chart-1', '--chart-2', '--chart-3', '--chart-4']) {
			expect(flow).toContain(`var(${token})`);
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
			(path) => statSync(path).size > 200_000 && readFileSync(path, 'utf8').includes('sankey')
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
			expect(readFileSync(page, 'utf8')).not.toContain('data-flow');
		}
	});
});

test.describe('the option the engine is given', () => {
	const days = [
		{ reached: 1000, asked: 700, drafted: 100, published: 80 },
		{ reached: 500, asked: 300, drafted: 50, published: 40 }
	];
	/** The four stage totals the fixture adds up to, computed here rather than
	 * read back off the option - otherwise the assertion below only proves the
	 * option agrees with itself. */
	const TOTAL = { reached: 1500, asked: 1000, drafted: 150, published: 120 };

	type Link = { source: string; target: string; value: number };
	type Node = { name: string; value: number; depth: number };
	const sankey = (option: Record<string, unknown>) => {
		const series = (option.series as Record<string, unknown>[])[0];
		return { nodes: series.data as Node[], links: series.links as Link[] };
	};

	test('what leaves a stage is what arrived at it', () => {
		// The whole reason this is a flow and not a picture. Every stage sends its
		// items on or loses them, and the two branches have to add back up to the
		// count the stage started with. A width that does not conserve is drawing
		// a shape, not the data.
		const { option, empty } = chartFlow(days);
		expect(empty).toBe(false);
		const { nodes, links } = sankey(option as Record<string, unknown>);

		const out = (name: string) =>
			links.filter((link) => link.source === name).reduce((sum, link) => sum + link.value, 0);
		const value = (name: string) => (nodes.find((node) => node.name === name) as Node).value;

		const stages: [string, number, number][] = [
			['Reached', TOTAL.reached, TOTAL.asked],
			['Asked the model', TOTAL.asked, TOTAL.drafted],
			['Drafted', TOTAL.drafted, TOTAL.published]
		];
		for (const [name, arrived, onward] of stages) {
			expect(value(name), `${name} draws its own count`).toBe(arrived);
			expect(out(name), `${name} sends on everything it took in`).toBe(arrived);
			expect(
				links.find((link) => link.source === name && link.value === onward),
				`${name} carries ${onward} forward`
			).toBeTruthy();
			expect(
				links.find((link) => link.source === name && link.value === arrived - onward),
				`${name} loses ${arrived - onward} on a named branch`
			).toBeTruthy();
		}
		// The last stage is where items stop, so nothing leaves it.
		expect(value('Published')).toBe(TOTAL.published);
		expect(out('Published')).toBe(0);
		// A loss is a dead end that holds exactly what reached it.
		for (const loss of ['Answered without a visual', 'The model drew nothing', 'Did not survive the checks']) {
			expect(out(loss), `${loss} is where those items stop`).toBe(0);
			expect(
				links.filter((link) => link.target === loss).reduce((sum, link) => sum + link.value, 0),
				`${loss} holds what arrived at it`
			).toBe(value(loss));
		}
	});

	test('a loss sits in the column of the stage it left, not at the far edge', () => {
		// An inferred layout justifies every dead end to the right, which would
		// draw the first stage's loss beside the last stage's.
		const { nodes } = sankey(chartFlow(days).option as Record<string, unknown>);
		const depth = (name: string) => (nodes.find((node) => node.name === name) as Node).depth;
		expect(depth('Answered without a visual')).toBe(depth('Asked the model'));
		expect(depth('The model drew nothing')).toBe(depth('Drafted'));
		expect(depth('Did not survive the checks')).toBe(depth('Published'));
	});

	test('nothing reached says so, rather than drawing four zeros', () => {
		// Zero reached means nothing committed says what the visual planner did.
		const { empty, reason } = chartFlow([{ reached: 0, asked: 0, drafted: 0, published: 0 }]);
		expect(empty).toBe(true);
		expect(reason).toContain('Nothing committed says what the visual planner did');
	});

	test('a stage that counts more than the one before it is refused, in words', () => {
		// A visual published inside the window can have been drafted before it
		// opened, and that drop is negative. A negative branch cannot be drawn, so
		// the diagram steps aside and names what it saw.
		const { empty, option, reason } = chartFlow([
			{ reached: 100, asked: 60, drafted: 5, published: 9 }
		]);
		expect(empty).toBe(true);
		expect(option.series).toBeUndefined();
		expect(reason).toContain('published');
		expect(reason).toContain('drafted');
	});

	test('a drop of zero draws no branch at all', () => {
		// A stage that lost nothing has no loss to show, and a zero-width branch
		// with a label beside it reads as a loss too small to see.
		const { option } = chartFlow([{ reached: 10, asked: 10, drafted: 4, published: 4 }]);
		const { nodes, links } = sankey(option as Record<string, unknown>);
		expect(nodes.map((node) => node.name)).not.toContain('Answered without a visual');
		expect(nodes.map((node) => node.name)).not.toContain('Did not survive the checks');
		expect(links.every((link) => link.value > 0)).toBe(true);
	});

	test('every colour in the option is a sentinel, never a hex somebody typed', () => {
		const { option } = chartFlow(days);
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
			const el = document.querySelector('[data-flow="chart"]');
			return el === null ? null : /#ff00[0-9a-f]{2}/i.test(el.innerHTML);
		});
		expect(resolved).toBe(false);
	});

	test('a theme change repaints the marks', async ({ page }) => {
		await page.goto('/console/');
		const fills = await page.evaluate(async () => {
			const read = () =>
				[
					...document.querySelectorAll(
						'[data-flow="chart"] svg path, [data-flow="chart"] svg rect, [data-flow="chart"] svg polygon'
					)
				]
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
