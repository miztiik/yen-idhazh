import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { ICON_IDS, ICONS, type IconId } from '../src/lib/icons/generated';

/**
 * An icon set rots in two directions, and both are silent.
 *
 * A glyph nobody references keeps shipping its bytes and its licence
 * obligation. A reference to a glyph that does not exist renders nothing at
 * all, and an empty 16 px box beside a label looks like a rendering quirk
 * rather than a bug. The bijection below is what makes each one loud.
 */

const SRC = resolve(process.cwd(), 'src');
const SVG = join(SRC, 'lib', 'icons', 'svg');

/** The 40 KB the row that added the set budgeted for. */
const BYTE_BUDGET = 40 * 1024;

function sourceFiles(): string[] {
	const out: string[] = [];
	const walk = (at: string) => {
		for (const entry of readdirSync(at, { withFileTypes: true })) {
			const path = join(at, entry.name);
			if (entry.isDirectory()) walk(path);
			else if (/\.(svelte|ts)$/.test(entry.name)) out.push(path);
		}
	};
	walk(SRC);
	return out;
}

/** Every `id="..."` handed to an Icon, plus the ids a component holds in a
 * typed map and passes dynamically.
 *
 * The literal scan is scoped to files that import `IconId`, because an id used
 * dynamically has to be typed for the compiler to check it. Scanning every file
 * instead reads any string that happens to look like an id - `'theme-color'` in
 * the theme module was matched that way, and reported as an invented icon.
 */
function referenced(): Set<string> {
	const used = new Set<string>();
	for (const path of sourceFiles()) {
		if (path.includes(join('lib', 'icons'))) continue;
		const text = readFileSync(path, 'utf8');
		for (const m of text.matchAll(/<Icon[^>]*\bid=(?:"([a-z0-9-]+)"|\{([^}]*)\})/g)) {
			if (m[1]) used.add(m[1]);
		}
		if (!/\bIconId\b/.test(text)) continue;
		for (const m of text.matchAll(/'(band-[a-z]+|topic-[a-z0-9-]+|theme-[a-z]+)'/g)) {
			used.add(m[1]);
		}
	}
	return used;
}

test.describe('the icon set', () => {
	test('every icon is used, and every use exists', () => {
		const used = referenced();
		expect(used.size, 'no icon reference found - the scan is broken').toBeGreaterThan(0);

		// A topic pill builds its id from a config-declared vertical, so those are
		// resolved against the taxonomy rather than found as a literal.
		const taxonomy = JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'config', 'taxonomy.json'), 'utf8')
		);
		for (const vertical of taxonomy.verticals) used.add(`topic-${vertical.id}`);

		const unused = ICON_IDS.filter((id) => !used.has(id));
		expect(unused, 'these icons ship and nothing draws them').toEqual([]);

		const invented = [...used].filter((id) => !(id in ICONS));
		expect(invented, 'these ids are referenced and do not exist').toEqual([]);
	});

	test('no component holds a path of its own', () => {
		// The point of the set is that geometry lives in one place. A component
		// that draws its own is how the surface ended up with two icons and no
		// system. Charts are exempt: their marks are data, not iconography.
		const offenders = sourceFiles()
			.filter((path) => !path.includes(join('lib', 'icons')))
			.filter((path) => !path.includes(join('lib', 'charts')))
			.filter((path) => !/Scatter|Timings|Trend|Panels|Viewport|Histogram/.test(path))
			.filter((path) => /<path\s/.test(readFileSync(path, 'utf8')));
		expect(offenders).toEqual([]);
	});

	test('the set stays inside its byte budget', () => {
		const bytes = readdirSync(SVG)
			.filter((n) => n.endsWith('.svg'))
			.reduce((sum, n) => sum + statSync(join(SVG, n)).size, 0);
		expect(bytes).toBeLessThanOrEqual(BYTE_BUDGET);
	});

	test('the generated module is generated, not written', () => {
		const before = readFileSync(join(SRC, 'lib', 'icons', 'generated.ts'), 'utf8');
		execFileSync('node', ['scripts/build-icons.mjs'], { cwd: process.cwd() });
		const after = readFileSync(join(SRC, 'lib', 'icons', 'generated.ts'), 'utf8');
		expect(after).toBe(before);
	});

	test('an id that does not exist is a type error, not a blank box', () => {
		// Guards the mechanism the compiler enforces: IconId is the key union, so
		// a typo at a call site fails `npm run check` rather than rendering
		// nothing. This asserts the union is not widened to string.
		const id: IconId = 'band-high';
		expect(ICON_IDS).toContain(id);
		expect(Object.keys(ICONS).sort()).toEqual([...ICON_IDS].sort());
	});
});

test.describe('icons on the page', () => {
	test('a topic pill carries its mark, in both themes', async ({ page }) => {
		await page.goto('/');
		const marks = await page.evaluate(() => {
			const pills = [...document.querySelectorAll('[data-topic-row] a')];
			return pills.map((p) => ({
				text: (p.textContent ?? '').trim().slice(0, 24),
				hasIcon: p.querySelector('svg.icon') !== null
			}));
		});
		expect(marks.length).toBeGreaterThan(1);
		// "All N" is not a topic and gets no mark; every named vertical does.
		expect(marks.slice(1).every((m) => m.hasIcon)).toBe(true);
	});

	test('a mark takes its colour from the thing it sits in', async ({ page }) => {
		await page.goto('/');
		const colours = await page.evaluate(async () => {
			const read = () => {
				const icon = document.querySelector('[data-band] svg.icon');
				return icon === null ? null : getComputedStyle(icon).color;
			};
			const dark = (document.documentElement.setAttribute('data-theme', 'dark'), read());
			await new Promise((done) => setTimeout(done, 250));
			document.documentElement.setAttribute('data-theme', 'light');
			await new Promise((done) => setTimeout(done, 250));
			return { dark, light: read() };
		});
		expect(colours.dark).not.toBeNull();
		expect(colours.light).not.toBe(colours.dark);
	});
});
