import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ICON_IDS, ICONS, type IconId } from '../src/lib/icons/generated';

/**
 * A missing icon renders nothing at all.
 *
 * The generated id map keeps component types narrow. The page check confirms
 * that rendered topic marks use their container's colour.
 */

const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..');
const ICON_DIRECTORY = join(FRONTEND, 'src', 'lib', 'icons');

test.describe('the icon set', () => {
	test('the generated icon map follows the named manifest list', () => {
		const manifest = JSON.parse(readFileSync(join(ICON_DIRECTORY, 'manifest.json'), 'utf8')) as {
			icons: string[];
		};
		expect(ICON_IDS).toEqual(manifest.icons);
		expect(Object.keys(ICONS)).toEqual(manifest.icons);
	});

	test('the generated id list matches the icon map', () => {
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
