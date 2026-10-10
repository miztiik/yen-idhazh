/** The token layer's named-file checks: no theme token is half-declared.
 *
 * Three failures this catches, all of which have shipped in real design
 * systems and none of which is visible in a diff:
 *
 * 1. A token declared in the base theme with no light override. The page looks
 *    right until someone flips the theme, and then one element keeps a dark
 *    colour on a light ground.
 * 2. A token with no `@theme inline` mirror. `bg-surface` and
 *    `var(--color-surface)` stop resolving to the same value, and the token
 *    file quietly stops being the only place a colour is decided.
 * These checks read the two named stylesheet inputs. They do not scan source
 * files or judge the current published pages.
 */

import { expect, test } from '@playwright/test';
import { readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const TOKENS = readFileSync(join(FRONTEND, 'src', 'styles', 'tokens.css'), 'utf8');
const APP = readFileSync(join(FRONTEND, 'src', 'styles', 'app.css'), 'utf8');

/** Tokens that are deliberately theme-independent: a scale, not a colour.
 *
 * They are declared in their own `:root` block outside both theme blocks, so a
 * dark override would be a second copy of the same number.
 */
const THEME_INDEPENDENT = /^--(space|text|leading|frame|measure|gutter|radius|dur|ease|zone|workbench|tracking)/;

/** Tokens with no Tailwind utility, because nothing would ever write one.
 *
 * A gradient is applied by name in a component's own rule; a duration and an
 * easing are consumed by a transition, not by a class; the focus ring is a
 * single global rule; the swatches are indexed at runtime from the payload, so
 * a utility per swatch would be eight classes nobody types. `--series-1`
 * through `--series-4` are aliases of the first four chart stops, kept so no
 * existing chart had to change in the row that widened the ramp - the stop they
 * point at is mirrored, and mirroring the alias too would be a second name for
 * one utility. The type colours are applied by one component from a column's
 * type family, never by a class. `--chart-spread-mix` is a fraction consumed
 * by `color-mix`, not a colour or a utility.
 */
const NO_UTILITY =
	/^--(gradient|dur|ease|series|type-|source-swatch|shadow-focus|color-focus|chart-readout|chart-spread-mix$|route-line-reserve$|color-surface-raised|color-surface-sunken|color-rule-strong|color-accent-strong|color-on-accent|radius-full)/;

function block(css: string, selector: string): string {
	const start = css.indexOf(selector);
	expect(start, `tokens.css no longer has a ${selector} block`).toBeGreaterThan(-1);
	const open = css.indexOf('{', start);
	const close = css.indexOf('\n}', open);
	return css.slice(open, close);
}

function declaredIn(css: string): string[] {
	return [...css.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]);
}

/** The value of one token in one theme block, and only where it is a plain hex. */
function valueOf(css: string, token: string): string {
	const match = new RegExp(`^\\s*${token}\\s*:\\s*(#[0-9a-f]{6})`, 'm').exec(css);
	expect(match, `${token} is no longer a plain hex value in this theme`).not.toBeNull();
	return match![1];
}

/** The hex one token resolves to in one theme block, following `var(--other)` aliases there. */
function resolvedIn(css: string, token: string): string {
	const alias = new RegExp(`^\\s*${token}\\s*:\\s*var\\((--[a-z0-9-]+)\\)\\s*;`, 'm').exec(css);
	return alias === null ? valueOf(css, token) : resolvedIn(css, alias[1]);
}

/** WCAG 2.2 relative luminance, written out rather than imported.
 *
 * Audit tooling is a project non-goal (CLAUDE.md section 0a). This is one
 * surface's oracle over the tokens that surface uses, and it adds no
 * dependency. `item-card.spec.ts` carries the same eight lines for the same
 * reason.
 */
function luminance(hex: string): number {
	const channel = (value: number) => {
		const s = value / 255;
		return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
	};
	const [r, g, b] = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16));
	return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: string, b: string): number {
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (high + 0.05) / (low + 0.05);
}

/** The base theme is dark and carries `:root`; light is the override. */
const BASE_SELECTOR = ":root,\n[data-theme='dark']";
const OVERRIDE_SELECTOR = "[data-theme='light']";

const DARK = declaredIn(block(TOKENS, BASE_SELECTOR));
const LIGHT = declaredIn(block(TOKENS, OVERRIDE_SELECTOR));

test.describe('the token layer', () => {
	test('the base theme is dark, and light only overrides it', () => {
		// The whole of "dark by default". A document with no `data-theme` - no
		// script yet, or no script at all - matches `:root` and nothing else, so
		// whatever `:root` holds is the first painted frame.
		expect(block(TOKENS, BASE_SELECTOR), 'the base theme stopped being dark').toContain(
			'--color-bg: #0b0e14;'
		);
		expect(block(TOKENS, OVERRIDE_SELECTOR), 'the override stopped being light').toContain(
			'--color-bg: #f4f6fb;'
		);
		// Both selectors match at the same specificity, so source order is the
		// only thing making a chosen light theme win. Put the override first and
		// a reader who asked for light silently gets dark.
		expect(
			TOKENS.indexOf(OVERRIDE_SELECTOR),
			'the light override sits above the base, so it loses the cascade'
		).toBeGreaterThan(TOKENS.indexOf(BASE_SELECTOR));
	});


	test('code colours clear 4.5 to 1 against their ground in both themes', () => {
		for (const [name, css] of [['dark', block(TOKENS, BASE_SELECTOR)], ['light', block(TOKENS, OVERRIDE_SELECTOR)]] as const) {
			const ground = valueOf(css, '--code-ground');
			for (const token of ['--code-text', '--code-keyword', '--code-string', '--code-number', '--code-comment']) {
				expect(contrast(valueOf(css, token), ground), `${name} ${token} does not clear 4.5:1`).toBeGreaterThanOrEqual(4.5);
			}
		}
	});

	test('every type colour clears 4.5 to 1 on the surface it is printed on, in both themes', () => {
		// The Data explorer prints a column's type on --color-surface in its
		// family's colour, and a type in no family in the tertiary text colour.
		// Two of the four are aliases of the editor's colours, so the check
		// follows an alias to the hex it ends at in the same theme block.
		for (const [name, css] of [['dark', block(TOKENS, BASE_SELECTOR)], ['light', block(TOKENS, OVERRIDE_SELECTOR)]] as const) {
			const ground = valueOf(css, '--color-surface');
			const types = declaredIn(css).filter((token) => token.startsWith('--type-'));
			expect(types, `${name} no longer declares the four type colours`).toEqual(['--type-text', '--type-number', '--type-time', '--type-truth']);
			for (const token of [...types, '--color-text-tertiary']) {
				const ratio = contrast(resolvedIn(css, token), ground);
				expect(ratio, `${name} ${token} reads ${ratio.toFixed(2)}:1 on ${ground}`).toBeGreaterThanOrEqual(4.5);
			}
		}
	});

	test('every theme colour has a light override', () => {
		const missing = DARK.filter(
			(token) => !THEME_INDEPENDENT.test(token) && !LIGHT.includes(token)
		);
		expect(
			missing,
			`declared in the base theme with no light value: ${missing.join(', ')}`
		).toEqual([]);
	});

	test('the light theme invents nothing the base theme does not declare', () => {
		// A light-only token is a colour that silently disappears in dark mode,
		// which is now what almost every reader sees.
		const extra = LIGHT.filter((token) => !DARK.includes(token));
		expect(extra, `declared only in the light theme: ${extra.join(', ')}`).toEqual([]);
	});

	test('every non-exempt token has an @theme inline mirror', () => {
		const mirrored = new Set(
			[...APP.matchAll(/^\s*--[a-z0-9-]+:\s*var\((--[a-z0-9-]+)\)/gm)].map((m) => m[1])
		);
		const missing = DARK.filter(
			(token) => !THEME_INDEPENDENT.test(token) && !NO_UTILITY.test(token) && !mirrored.has(token)
		);
		expect(
			missing,
			`no @theme inline mirror, so a utility and the token can drift: ${missing.join(', ')}`
		).toEqual([]);
	});

	test('the chart ramp holds no confidence hue', () => {
		// A chart that borrowed the band tokens once told a reader the slowest
		// stage was the failing one. The ramp is categorical and carries no
		// word, so it may never reach for green, amber or red.
		for (const theme of [block(TOKENS, BASE_SELECTOR), block(TOKENS, OVERRIDE_SELECTOR)]) {
			const bands = [...theme.matchAll(/^\s*--band-(high|medium|low):\s*(#[0-9a-f]{6})/gm)].map(
				(m) => m[2]
			);
			expect(bands.length, 'the confidence ramp is no longer three tokens').toBe(3);
			const ramp = [...theme.matchAll(/^\s*--chart-[1-8]:\s*(#[0-9a-f]{6})/gm)].map((m) => m[1]);
			expect(ramp.length, 'the chart ramp is no longer eight stops').toBe(8);
			for (const stop of ramp) {
				expect(bands, `chart ramp stop ${stop} is a confidence hue`).not.toContain(stop);
			}
		}
	});

	test('every source swatch is a fill a reader can see on the card', () => {
		// The mark's fill IS the read state: filled means unread, hollow means
		// read. Below a floor the two rings are one ring, and the whole signal
		// falls back on dimmer text and a lighter weight - which is the thing the
		// fill was added to replace, because both of those are less ink and they
		// fail together on a cheap panel and in sunlight.
		//
		// The floor is 1.5:1 and not the 3:1 that binds a fill carrying meaning:
		// the hue here says nothing, because the publication is named in words on
		// the same line. What carries meaning is whether there is a fill at all,
		// and that is an area rather than a colour (design-system.md).
		//
		// Arithmetic over the committed hex values, so the spread is zero by
		// construction and the same two colours give the same number everywhere.
		const format = readFileSync(join(FRONTEND, 'src', 'lib', 'format.ts'), 'utf8');
		const modulus = Number(/return hash % (\d+);/.exec(format)?.[1]);
		expect(
			modulus,
			'swatchIndex no longer picks a swatch by a fixed modulus'
		).toBeGreaterThan(0);

		for (const [theme, selector] of [
			['dark', BASE_SELECTOR],
			['light', OVERRIDE_SELECTOR]
		] as const) {
			const css = block(TOKENS, selector);
			const surface = valueOf(css, '--color-surface');
			const swatches = [
				...css.matchAll(/^\s*(--source-swatch-\d+)\s*:\s*(#[0-9a-f]{6})/gm)
			].map((m) => [m[1], m[2]] as const);

			// A shrunken set would pass every assertion under it, and an index the
			// payload can produce with no swatch behind it resolves to no fill at
			// all - which reads as "this item is read".
			expect(
				swatches.length,
				`${theme} declares ${swatches.length} swatches and swatchIndex asks for ${modulus}`
			).toBe(modulus);

			for (const [name, value] of swatches) {
				const ratio = contrast(value, surface);
				console.log(`${theme} ${name} ${value} on ${surface}: ${ratio.toFixed(4)}:1`);
				expect(
					ratio,
					`${theme} ${name} ${value} reads ${ratio.toFixed(4)}:1 on ${surface}`
				).toBeGreaterThanOrEqual(1.5);
			}
		}
	});

	test('every wordmark gradient stop is readable on the ground it sits on', () => {
		// The wordmark is the site's name, so it is read as type even though the
		// gradient under it encodes nothing. Decorative colour is unconstrained
		// (design-system.md); decorative colour that spells a word is not, and
		// 4.5:1 is what WCAG 2.2 SC 1.4.3 sets for normal text.
		//
		// This is the one thing about the wordmark that cannot be seen in a
		// screenshot of the theme somebody happened to open: the light set that
		// served here until 2026-08-31 read 3.9803:1, 4.0195:1 and 2.9318:1, and
		// nothing had ever asked.
		//
		// Arithmetic over the committed hex values, so the same two colours give
		// the same number on every machine and the spread is zero by
		// construction.
		for (const [theme, selector] of [
			['dark', BASE_SELECTOR],
			['light', OVERRIDE_SELECTOR]
		] as const) {
			const css = block(TOKENS, selector);
			const bg = valueOf(css, '--color-bg');
			const declared = /^\s*--gradient-wordmark:\s*([^;]+);/m.exec(css);
			expect(
				declared,
				`--gradient-wordmark is not declared in the ${theme} theme`
			).not.toBeNull();

			const stops = [...declared![1].matchAll(/#[0-9a-f]{6}/g)].map((m) => m[0]);
			// Five, and the count is asserted: a set trimmed to two would pass
			// every ratio below and lose the sweep the row was for.
			expect(stops.length, `the ${theme} wordmark is no longer five stops`).toBe(5);

			for (const stop of stops) {
				const ratio = contrast(stop, bg);
				console.log(`${theme} --gradient-wordmark ${stop} on ${bg}: ${ratio.toFixed(4)}:1`);
				expect(
					ratio,
					`${theme} wordmark stop ${stop} reads ${ratio.toFixed(4)}:1 on ${bg}`
				).toBeGreaterThanOrEqual(4.5);
			}
		}
	});

	test('the wordmark scale is a scale, and it is relative', () => {
		// A scale is not a colour, so it is declared once outside both theme
		// blocks. Left inside one, it reads as something a theme could change and
		// the next theme has to restate it or lose it.
		//
		// And a size is relative, never a hard pixel count (owner, 2026-08-31): a
		// px wordmark ignores a reader who set their browser text larger, and
		// this is the first thing on every route.
		const scale = ['--wordmark-size', '--wordmark-leading', '--wordmark-tracking'];
		for (const token of scale) {
			expect(declaredIn(TOKENS), `${token} is not declared`).toContain(token);
			expect(DARK, `${token} is inside the base theme block`).not.toContain(token);
			expect(LIGHT, `${token} is inside the light theme block`).not.toContain(token);
		}
		const size = /^\s*--wordmark-size:\s*([^;]+);/m.exec(TOKENS)![1];
		expect(size, 'the wordmark size stopped being fluid').toContain('clamp(');
		expect(size, 'the wordmark size is a hard pixel count').not.toMatch(/\dpx/);
		expect(
			/^\s*--wordmark-tracking:\s*([^;]+);/m.exec(TOKENS)![1],
			'the tracking is a pixel count, so it does not hold at both ends of the clamp'
		).toMatch(/em\s*$/);
	});

	test('the committed display face is inside its byte budget', () => {
		// Guardrail #2: the published site has a 1 GB ceiling. A face that is a
		// meaningful fraction of a day's growth has to argue for itself; this
		// one is about three tenths of one percent of it.
		const bytes = statSync(join(FRONTEND, 'static', 'fonts', 'inter-latin-variable.woff2')).size;
		expect(bytes).toBeLessThanOrEqual(120_000);
	});

	test('the font is self-hosted, preloaded, and swapped', () => {
		const html = readFileSync(join(FRONTEND, 'src', 'app.html'), 'utf8');
		// The preload has to be in the head to start the fetch early.
		expect(html).toContain('rel="preload"');
		expect(html).toContain('fonts/inter-latin-variable.woff2');
		// The @font-face RULE is not in the head: inlined there it is bytes in
		// every prerendered page instead of in one cached stylesheet, and the
		// bundle gate charges for it on every route. Matched as a rule rather
		// than as the bare word, so the comment explaining this does not trip
		// its own assertion.
		expect(html, 'the font-face rule is inline in app.html again').not.toMatch(
			/@font-face\s*\{/
		);
		expect(APP).toContain('font-display: swap');
		// Same-origin only: default-src is 'self', and widening the policy for
		// one file is the cost self-hosting avoids.
		expect(APP).not.toMatch(/@font-face[\s\S]*?src:\s*url\(['"]?https?:/);
	});

	test('the measure is not on the shell', () => {
		// The whole defect this plan exists to prevent. `.frame` is the shell and
		// `.measure` is the text; a shell that carries the measure gives the
		// application a paragraph's width.
		const frame = APP.slice(APP.indexOf('.frame {'), APP.indexOf('.measure {'));
		expect(frame).toContain('var(--frame-reading)');
		expect(frame, 'the reading measure is on the shell again').not.toContain('var(--measure)');
	});

	test('the frame values are generated at build time, not injected at runtime', () => {
		// Injecting them from the layout head was measured on 2026-08-29 at 397
		// to 700 gzipped bytes of JavaScript on every route, including two that
		// render nothing, to get one config value into CSS.
		expect(APP).toContain("@import './frame.generated.css'");
		const generated = readFileSync(join(FRONTEND, 'src', 'styles', 'frame.generated.css'), 'utf8');
		for (const token of [
			'--frame-reading',
			'--frame-console',
			'--measure',
			'--gutter-min',
			'--zone-mark',
			'--zone-rail',
			'--zone-aside'
		]) {
			expect(generated, `${token} missing from the generated frame css`).toContain(token);
		}
		const layout = readFileSync(join(FRONTEND, 'src', 'routes', '+layout.svelte'), 'utf8');
		expect(layout, 'the frame is being injected from the layout again').not.toContain('svelte:head');
	});

});
