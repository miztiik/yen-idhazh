/** The token layer's oracle: no token is half-declared.
 *
 * Three failures this catches, all of which have shipped in real design
 * systems and none of which is visible in a diff:
 *
 * 1. A token declared in the light theme with no dark override. The page looks
 *    right until someone flips the theme, and then one element keeps a light
 *    colour on a dark ground.
 * 2. A token with no `@theme inline` mirror. `bg-surface` and
 *    `var(--color-surface)` stop resolving to the same value, and the token
 *    file quietly stops being the only place a colour is decided.
 * 3. A token USED by a component that nothing declares. It resolves to nothing
 *    and the property is simply dropped, which reads as "that element has no
 *    background" rather than as an error.
 *
 * These are read off the source files rather than off a rendered page on
 * purpose: a rendered page only proves the tokens on the routes that happened
 * to be visited.
 */

import { expect, test } from '@playwright/test';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, extname, join } from 'node:path';

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const TOKENS = readFileSync(join(FRONTEND, 'src', 'styles', 'tokens.css'), 'utf8');
const APP = readFileSync(join(FRONTEND, 'src', 'styles', 'app.css'), 'utf8');

/** Tokens that are deliberately theme-independent: a scale, not a colour.
 *
 * They are declared in their own `:root` block outside both theme blocks, so a
 * dark override would be a second copy of the same number.
 */
const THEME_INDEPENDENT = /^--(space|text|leading|frame|measure|gutter|radius|dur|ease)/;

/** Tokens with no Tailwind utility, because nothing would ever write one.
 *
 * A gradient is applied by name in a component's own rule; a duration and an
 * easing are consumed by a transition, not by a class; the focus ring is a
 * single global rule; the swatches are indexed at runtime from the payload, so
 * a utility per swatch would be eight classes nobody types. `--series-1`
 * through `--series-4` are aliases of the first four chart stops, kept so no
 * existing chart had to change in the row that widened the ramp - the stop they
 * point at is mirrored, and mirroring the alias too would be a second name for
 * one utility.
 */
const NO_UTILITY =
	/^--(gradient|dur|ease|series|source-swatch|shadow-focus|color-focus|chart-readout|color-surface-raised|color-surface-sunken|color-rule-strong|color-accent-strong|color-on-accent|radius-full)/;

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

const LIGHT = declaredIn(block(TOKENS, ":root,\n[data-theme='light']"));
const DARK = declaredIn(block(TOKENS, "[data-theme='dark']"));

function sourceFiles(dir: string, out: string[] = []): string[] {
	for (const entry of readdirSync(dir)) {
		const path = join(dir, entry);
		if (statSync(path).isDirectory()) {
			sourceFiles(path, out);
		} else if (['.svelte', '.ts', '.css', '.html'].includes(extname(entry))) {
			out.push(path);
		}
	}
	return out;
}

test.describe('the token layer', () => {
	test('every theme colour has a dark override', () => {
		const missing = LIGHT.filter(
			(token) => !THEME_INDEPENDENT.test(token) && !DARK.includes(token)
		);
		expect(missing, `declared in the light theme with no dark value: ${missing.join(', ')}`).toEqual(
			[]
		);
	});

	test('the dark theme invents nothing the light theme does not declare', () => {
		// A dark-only token is a colour that silently disappears in light mode.
		const extra = DARK.filter((token) => !LIGHT.includes(token));
		expect(extra, `declared only in the dark theme: ${extra.join(', ')}`).toEqual([]);
	});

	test('every non-exempt token has an @theme inline mirror', () => {
		const mirrored = new Set(
			[...APP.matchAll(/^\s*--[a-z0-9-]+:\s*var\((--[a-z0-9-]+)\)/gm)].map((m) => m[1])
		);
		const missing = LIGHT.filter(
			(token) => !THEME_INDEPENDENT.test(token) && !NO_UTILITY.test(token) && !mirrored.has(token)
		);
		expect(
			missing,
			`no @theme inline mirror, so a utility and the token can drift: ${missing.join(', ')}`
		).toEqual([]);
	});

	test('nothing uses a token that is never declared', () => {
		const declared = new Set([
			...LIGHT,
			...DARK,
			...declaredIn(TOKENS),
			...declaredIn(APP),
			// Tailwind's own generated custom properties.
			'--tw-content'
		]);
		/** An indexed family, read as `var(--source-swatch-{n})` from the payload.
		 * The stem is what exists; the whole name never appears in source. */
		const indexed = (token: string) =>
			[...declared].some((name) => name.startsWith(token) && name !== token);

		const offenders: string[] = [];
		for (const file of sourceFiles(join(FRONTEND, 'src'))) {
			const text = readFileSync(file, 'utf8');
			for (const match of text.matchAll(/var\((--[a-z0-9-]+)(\s*,)?/g)) {
				const token = match[1];
				if (declared.has(token)) continue;
				// A locally scoped custom property set on the same element is fine.
				if (text.includes(`${token}:`)) continue;
				// A read with a fallback cannot resolve to nothing, so it is a
				// parameter a consumer sets rather than a token that went missing.
				if (match[2]) continue;
				if (indexed(token)) continue;
				offenders.push(`${file.slice(FRONTEND.length + 1)} -> ${token}`);
			}
		}
		expect(offenders, `used but never declared: ${offenders.join('; ')}`).toEqual([]);
	});

	test('the chart ramp holds no confidence hue', () => {
		// A chart that borrowed the band tokens once told a reader the slowest
		// stage was the failing one. The ramp is categorical and carries no
		// word, so it may never reach for green, amber or red.
		for (const theme of [block(TOKENS, ":root,\n[data-theme='light']"), block(TOKENS, "[data-theme='dark']")]) {
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

	test('the committed display face is inside its byte budget', () => {
		// Rule #2: the published site has a 1 GB ceiling. A face that is a
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
		// The whole defect this row exists to prevent. `.frame` is the shell and
		// `.measure` is the text; a shell that carries the measure gives the
		// application a paragraph's width.
		const frame = APP.slice(APP.indexOf('.frame {'), APP.indexOf('.frame-console'));
		expect(frame).toContain('var(--frame-reading)');
		expect(frame, 'the reading measure is on the shell again').not.toContain('var(--measure)');
	});
});
