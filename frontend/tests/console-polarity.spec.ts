import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import { movementVerdict, type MovementPolarity } from '../src/lib/charts/theme';

/**
 * Row #4's oracle: movement colour reads the polarity of the MEASURE, not the
 * sign of the number.
 *
 * The defect it removes is invisible in a diff and obvious once named. The
 * card painted a rising figure green and a falling one pink, so a fall in
 * `Time to write one` - the machine got faster - read as the bad case, and a
 * fall in `Summaries today` read the same as a fall in `Failed`. One rule,
 * three meanings, and nothing on screen said which.
 *
 * Two halves, and both are needed. The first walks the built pages in both
 * themes and asserts every painted movement agrees with the polarity declared
 * beside it. The second renders `KpiCard` on its own with the two cases the
 * committed data cannot be relied on to hold at once - a FALLING measure that
 * must paint good, and a RISING measure that must paint good - so no constant
 * and no sign rule can satisfy this file.
 *
 * Every colour is resolved through one probe span in the live document. A
 * fixed hex cannot be right in both themes, so the token and the element that
 * claims to use it both have to arrive as `rgb(...)` from the same document -
 * which also means this file never parses a colour.
 */

const ROUTES = ['/console/', '/console/model/', '/console/machine/'] as const;
const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

/** The three colours a movement may take, and nothing else. The neutral is one
 * value across every movement surface, so a grey delta on Pipelines and a grey
 * row on Model are the same statement. */
const PAINT_OF: Record<string, string> = {
	good: 'var(--movement-good)',
	bad: 'var(--movement-bad)',
	neutral: 'var(--color-text-secondary)'
};

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');

async function openAt(page: Page, route: string, theme: Theme) {
	await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);
	await page.goto(route);
	await expect
		.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
		.toBe(theme);
}

/** Resolve a list of CSS colour expressions through one probe span.
 *
 * The probe is a real element in the real document, so `var(--movement-good)`
 * resolves against the theme that is actually on, and the value comes back in
 * the same `rgb(...)` form `getComputedStyle` hands back for a painted node.
 */
async function resolve(page: Page, expressions: string[]): Promise<string[]> {
	return page.evaluate((list: string[]) => {
		const probe = document.createElement('span');
		probe.style.position = 'absolute';
		probe.style.visibility = 'hidden';
		document.body.appendChild(probe);
		const out = list.map((expression) => {
			probe.style.color = '';
			probe.style.color = expression;
			return getComputedStyle(probe).color;
		});
		probe.remove();
		return out;
	}, expressions);
}

interface Painted {
	route: string;
	polarity: string;
	change: number;
	verdict: string;
	/** One entry per node that actually takes a colour from the verdict. A card
	 * paints one span; a swap row paints a track, a dot and an arrowhead. */
	paints: string[];
	/** True where the coloured node IS the text, so the printed sign is the
	 * second signal. A swap row's second signal is the arrowhead instead. */
	printed: boolean;
	text: string;
}

/** Every movement on the page, with what it claims and what it is painted. */
async function painted(page: Page, route: string): Promise<Painted[]> {
	return page.evaluate((where: string) => {
		return [...document.querySelectorAll('[data-movement]')].map((element) => {
			const printed = element.matches('[data-movement-paint="color"]');
			const nodes = element.matches('[data-movement-paint]')
				? [element]
				: [...element.querySelectorAll('[data-movement-paint]')];
			const paints = nodes.map((node) => {
				const property = (node as HTMLElement).dataset.movementPaint as 'color' | 'stroke' | 'fill';
				return getComputedStyle(node).getPropertyValue(property);
			});
			return {
				route: where,
				polarity: element.getAttribute('data-polarity') ?? '',
				change: Number(element.getAttribute('data-movement')),
				verdict: element.getAttribute('data-movement-verdict') ?? '',
				paints,
				printed,
				text: (element.textContent ?? '').trim()
			};
		});
	}, route);
}

for (const theme of THEMES) {
	test(`THE ORACLE: every movement is painted by its measure's polarity, ${theme}`, async ({
		page
	}) => {
		const seen: Painted[] = [];
		let tokens: Record<string, string> = {};

		for (const route of ROUTES) {
			await openAt(page, route, theme);
			const [good, bad, neutral] = await resolve(page, [
				PAINT_OF.good,
				PAINT_OF.bad,
				PAINT_OF.neutral
			]);
			tokens = { good, bad, neutral };
			seen.push(...(await painted(page, route)));
		}

		expect(tokens.good, '--movement-good resolves to nothing').not.toBe('');
		expect(tokens.bad, '--movement-bad resolves to nothing').not.toBe('');
		expect(
			tokens.good,
			'--movement-good and --movement-bad resolve to one colour, so the mapping below is unfalsifiable'
		).not.toBe(tokens.bad);

		expect(seen.length, 'no console surface declares a movement at all').toBeGreaterThan(0);

		for (const item of seen) {
			// The page says which way is better. The test recomputes the verdict
			// from that and the sign, and never trusts the attribute the page
			// wrote - otherwise a component could paint itself right by lying.
			const wanted = movementVerdict(item.change, item.polarity as MovementPolarity);
			expect(
				item.verdict,
				`${item.route} declares ${item.change} on a ${item.polarity} measure and calls it ${item.verdict}`
			).toBe(wanted);
			expect(item.paints.length, `${item.route}: a movement with nothing painted`).toBeGreaterThan(
				0
			);
			for (const paint of item.paints) {
				expect(
					paint,
					`${item.route}: ${item.change} on a ${item.polarity} measure is ${wanted}, so it must be painted ${PAINT_OF[wanted]}`
				).toBe(tokens[wanted]);
			}
			// Colour is one signal, never the only one. Where the coloured node is
			// the number itself, the sign printed in it is the second signal.
			if (item.printed) {
				expect(
					item.text,
					`${item.route}: a movement with no sign beside it, so colour is the only signal`
				).toMatch(/^[+-]/);
			}
		}

		// A polarity nobody declared is the defect coming back under a default.
		// `higher-is-better` is not required here: whether the chart-arm coverage
		// delta draws at all depends on the ledger - a window whose first day
		// published nothing has no ratio to move from - and a test that passes
		// only while today's data cooperates is not a test. The rendered-card
		// cases below carry that direction, and they carry it every run.
		const declared = new Set(seen.map((item) => item.polarity));
		for (const polarity of ['lower-is-better', 'no-agreed-direction']) {
			expect(
				[...declared],
				`no console surface declares a ${polarity} measure any more, so this file stopped testing it`
			).toContain(polarity);
		}
		for (const polarity of declared) {
			expect(
				['lower-is-better', 'higher-is-better', 'no-agreed-direction'],
				`a movement declares ${JSON.stringify(polarity)}, which is not a polarity`
			).toContain(polarity);
		}
	});
}

test('the movement pair is not the confidence ramp, in either theme', async ({ page }) => {
	// Decision #2, made mechanical. Green on the confidence ramp means "it
	// worked"; a summary that got 3 percent slower is not broken, and a pair
	// that resolves to the same bytes as --band-* IS the confidence ramp under
	// a second name.
	for (const theme of THEMES) {
		await openAt(page, '/console/', theme);
		const [good, bad, ...ramp] = await resolve(page, [
			'var(--movement-good)',
			'var(--movement-bad)',
			'var(--band-high)',
			'var(--band-medium)',
			'var(--band-low)',
			'var(--fill-high)',
			'var(--fill-medium)',
			'var(--fill-low)'
		]);
		for (const value of ramp) {
			expect(good, `--movement-good is a confidence-ramp value on ${theme}`).not.toBe(value);
			expect(bad, `--movement-bad is a confidence-ramp value on ${theme}`).not.toBe(value);
		}
	}
});

/** WCAG 2.2 relative luminance, written out rather than imported - audit
 * tooling is a project non-goal (CLAUDE.md section 0a) and this is one row's
 * own oracle over the two tokens that row added. */
function luminance([r, g, b]: number[]): number {
	const channel = (value: number) => {
		const s = value / 255;
		return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function rgb(value: string): number[] {
	const parts = /rgba?\(([^)]+)\)/.exec(value);
	if (!parts) throw new Error(`not a resolved colour: ${JSON.stringify(value)}`);
	return parts[1].split(',').slice(0, 3).map((n) => Number(n.trim()));
}

function contrast(a: string, b: string): number {
	const [high, low] = [luminance(rgb(a)), luminance(rgb(b))].sort((x, y) => y - x);
	return Math.round(((high + 0.05) / (low + 0.05)) * 1000) / 1000;
}

test('both movement colours are readable as text, in both themes', async ({ page }) => {
	// They are printed as a percentage in a card foot, so they are type and
	// carry the 4.5:1 that WCAG 2.2 SC 1.4.3 sets for normal text. This is the
	// bound that stops "quieter than the confidence ramp" turning into "grey".
	for (const theme of THEMES) {
		await openAt(page, '/console/', theme);
		const [good, bad, surface] = await resolve(page, [
			'var(--movement-good)',
			'var(--movement-bad)',
			'var(--color-surface)'
		]);
		for (const [name, value] of Object.entries({ good, bad })) {
			const ratio = contrast(value, surface);
			expect(
				ratio,
				`--movement-${name} is ${ratio}:1 on ${theme}, under the 4.5:1 that makes a colour readable as text`
			).toBeGreaterThanOrEqual(4.5);
		}
	}
});

// --- The two cases the committed data cannot be relied on to hold at once ---

type Rendered = { body: string; css: string };

/** A no-op component, as a module the emitted server JS can import.
 *
 * `KpiCard` imports `Chart.svelte` for the one trend shape these cases do not
 * use, and plain Node compiles an imported `.svelte` file without the
 * TypeScript preprocessor - so the import fails on a `type` specifier inside a
 * component this test never renders. Stubbing the child keeps every binding
 * defined and cannot change what is measured: none of the cases below passes a
 * `trendSvg`, so the chart branch is never reached.
 */
const CHILD_STUB = 'data:text/javascript,export default function(){}';

async function renderer(name: string): Promise<(props: Record<string, unknown>) => Rendered> {
	const filename = path.join(frontend, 'src', 'lib', 'components', `${name}.svelte`);
	const source = readFileSync(filename, 'utf8');
	const pre = await preprocess(source, vitePreprocess(), { filename });
	const result = compile(pre.code, { generate: 'server', filename, name });
	const built = path.join(frontend, 'test-results', 'rendered');
	mkdirSync(built, { recursive: true });
	const module = path.join(built, `${name}.polarity.server.mjs`);
	writeFileSync(module, result.js.code.replace(/'[^']*\.svelte'/g, `'${CHILD_STUB}'`), 'utf8');
	const loaded = await import(pathToFileURL(module).href);
	return (props) => ({ body: render(loaded.default, { props }).body, css: result.css?.code ?? '' });
}

const tokens = readFileSync(path.join(frontend, 'src', 'styles', 'tokens.css'), 'utf8');

async function show(page: Page, out: Rendered, theme: Theme) {
	await page.setContent(
		`<!doctype html><html data-theme="${theme}"><head><style>${tokens}</style>` +
			`<style>${out.css}</style><style>body{margin:0}#host{inline-size:400px}</style>` +
			`</head><body><div id="host">${out.body}</div></body></html>`,
		{ waitUntil: 'domcontentloaded' }
	);
}

/** The four cases, and the point of all four together.
 *
 * Rows one and three both paint GOOD and their signs are opposite, so no rule
 * that reads the sign alone can pass. Rows one and two share a sign and differ
 * in verdict, so no rule that ignores the sign can pass either.
 */
const CASES: { label: string; movement: number; polarity: MovementPolarity; wanted: string }[] = [
	{ label: 'Time to write one', movement: -0.12, polarity: 'lower-is-better', wanted: 'good' },
	{ label: 'Failed', movement: -0.12, polarity: 'higher-is-better', wanted: 'bad' },
	{
		label: 'Published items with a chart',
		movement: 0.12,
		polarity: 'higher-is-better',
		wanted: 'good'
	},
	{ label: 'Numbers not in the article', movement: 0.12, polarity: 'lower-is-better', wanted: 'bad' },
	{ label: 'Summary length', movement: 0.12, polarity: 'no-agreed-direction', wanted: 'neutral' },
	{ label: 'Model minutes', movement: 0, polarity: 'lower-is-better', wanted: 'neutral' }
];

test.describe('a card painted from its polarity', () => {
	let draw: (props: Record<string, unknown>) => Rendered;

	test.beforeAll(async () => {
		draw = await renderer('KpiCard');
	});

	test('the cases below hold a falling good and a rising good', () => {
		// The whole reason this block exists. Without both, a rule that read the
		// sign alone would pass every case in the list.
		expect(
			CASES.some((item) => item.movement < 0 && item.wanted === 'good'),
			'no falling measure paints good, so a sign rule would satisfy this file'
		).toBe(true);
		expect(
			CASES.some((item) => item.movement > 0 && item.wanted === 'good'),
			'no rising measure paints good, so a sign rule would satisfy this file'
		).toBe(true);
	});

	for (const theme of THEMES) {
		for (const item of CASES) {
			test(`${item.movement} on a ${item.polarity} measure is ${item.wanted}, ${theme}`, async ({
				page
			}) => {
				await show(
					page,
					draw({
						label: item.label,
						value: '12',
						movement: item.movement,
						polarity: item.polarity
					}),
					theme
				);

				const [wanted] = await resolve(page, [PAINT_OF[item.wanted]]);
				const move = page.locator('[data-movement]');
				await expect(move).toHaveAttribute('data-movement-verdict', item.wanted);
				expect(await move.evaluate((el) => getComputedStyle(el).color)).toBe(wanted);
			});
		}
	}

	test('a measure with no agreed direction says so, and one with a direction does not', async ({
		page
	}) => {
		// Susan, 2026-08-31: a grey number a reader has to interpret is a fact
		// withheld. The card names the reason instead.
		await show(
			page,
			draw({ label: 'Summary length', value: '84', movement: 0.12, polarity: 'no-agreed-direction' }),
			'light'
		);
		await expect(page.locator('[data-movement-note]')).toHaveText('no target');

		await show(
			page,
			draw({ label: 'Failed', value: '2', movement: 0.12, polarity: 'lower-is-better' }),
			'light'
		);
		await expect(page.locator('[data-movement-note]')).toHaveCount(0);
	});

	test('a card with no movement paints nothing and claims nothing', async ({ page }) => {
		await show(page, draw({ label: 'Summaries today', value: '37' }), 'light');
		await expect(page.locator('[data-movement]')).toHaveCount(0);
	});
});
