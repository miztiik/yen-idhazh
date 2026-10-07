import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import type { Manifest } from 'vite';
import { iconsConfig } from '../src/lib/server/config';
import { serverCompiler } from './support/server-render';

/**
 * The Data explorer's column rail, ledger rail and answer header, drawn by the
 * real components from columns and ledgers this spec writes itself, under the
 * stylesheet the site ships, in a real browser. Every expected value is a
 * literal here: nothing the canary or the committed state holds decides one.
 */

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const THEMES = ['dark', 'light'] as const;
type Theme = (typeof THEMES)[number];

/** A ledger's columns as the page names them: one of each kind of type, and one name long enough to wrap in the rail. */
const LONG = 'item-health.a_column_name_long_enough_to_wrap_onto_several_lines';
const LEDGER_COLUMNS = [
	{ name: LONG, type: 'VARCHAR', paint: 'var(--type-text)' },
	{ name: 'item-health.http_status', type: 'BIGINT', paint: 'var(--type-number)' },
	{ name: 'item-health.mean_ms', type: 'DECIMAL(18,4)', paint: 'var(--type-number)' },
	{ name: 'item-health.fetched_at', type: 'TIMESTAMP WITH TIME ZONE', paint: 'var(--type-time)' },
	{ name: 'item-health.ok', type: 'BOOLEAN', paint: 'var(--type-truth)' },
	{ name: 'item-health.codes', type: 'VARCHAR[]', paint: 'var(--color-text-tertiary)' }
] as const;
const ANSWER_COLUMNS = LEDGER_COLUMNS.map((column) => ({ ...column, name: column.name.slice('item-health.'.length) }));
const ANSWER_ROW = { [ANSWER_COLUMNS[0].name]: 'a', http_status: '200', mean_ms: '1.5', fetched_at: '2026-08-20 12:00:00+00', ok: 'true', codes: '[ok]' };

/** Four ledgers: two chosen, one of them read only up to a day before the span starts, and one not on this site. */
const LEDGER_RAIL = {
	ledgers: [
		{ name: 'seen', grain: 'raw-and-compact' },
		{ name: 'item-health', grain: 'raw-and-compact' },
		{ name: 'host-fingerprint', grain: 'raw-and-compact' },
		{ name: 'feed-health', grain: 'raw-and-compact' }
	],
	selected: ['item-health', 'host-fingerprint'],
	published: ['seen', 'item-health', 'host-fingerprint'],
	through: { seen: '2026-10-03', 'item-health': '2026-10-03', 'host-fingerprint': '2026-09-01' },
	spanFrom: '2026-09-22',
	filter: '',
	onToggle: () => {},
	onFilter: () => {},
	onRefresh: () => {}
};

type Rgba = [number, number, number, number];
let draw: Record<'ColumnList' | 'LedgerList' | 'AnswerTable', (props: Record<string, unknown>) => string>;
let styles = '';

test.beforeAll(async ({}, testInfo) => {
	// The build defines the icon line weight from config (`vite.config.ts`); a component rendered outside the build needs the same global.
	Object.assign(globalThis, { __ICON_STROKE_PX__: iconsConfig().stroke_px });
	// One directory a worker: a module rewritten while another worker imports it is read half-written.
	const compiled = serverCompiler(path.join(frontend, 'test-results', 'explorer-rails', String(testInfo.workerIndex)));
	await compiled('src/lib/icons/Icon.svelte', 'Icon', [['./generated', '$lib/icons/generated']]);
	await compiled('src/lib/console/explorer/ColumnType.svelte', 'ColumnType', []);
	const toColumnType = ['$lib/console/explorer/ColumnType.svelte', './ColumnType.server.mjs'] as const;
	const toIcon = ['$lib/icons/Icon.svelte', './Icon.server.mjs'] as const;
	const modules = {
		ColumnList: await compiled('src/lib/console/explorer/ColumnList.svelte', 'ColumnList', [toColumnType]),
		LedgerList: await compiled('src/lib/console/explorer/LedgerList.svelte', 'LedgerList', [toIcon]),
		AnswerTable: await compiled('src/lib/console/explorer/AnswerTable.svelte', 'AnswerTable', [toColumnType, toIcon, ['./answer', '$lib/console/explorer/answer']])
	};
	draw = Object.fromEntries(await Promise.all(Object.entries(modules).map(async ([name, module]) => {
		const component = (await import(pathToFileURL(module).href)).default;
		return [name, (props: Record<string, unknown>) => render(component, { props }).body];
	}))) as typeof draw;
	// The stylesheet the site ships - the tokens, the focus ring and the screen-reader utility - then each component's own.
	const client = path.join(frontend, '.svelte-kit', 'output', 'client');
	const manifest = JSON.parse(readFileSync(path.join(client, '.vite', 'manifest.json'), 'utf8')) as Manifest;
	styles = [...new Set(Object.values(manifest).flatMap((entry) => entry.css ?? []))]
		.map((file) => readFileSync(path.join(client, file), 'utf8'))
		.concat([...compiled.css.values()])
		.join('\n');
});

/** One rail box on the workbench surface: the width and height are this spec's own, so the rail has to wrap and scroll. */
async function mount(page: Page, theme: Theme, width: string, height: string, markup: string) {
	await page.setContent(
		`<!doctype html><html data-theme="${theme}"><head><meta charset="utf-8"><style>${styles}</style></head>` +
			`<body><main style="inline-size: ${width}; block-size: ${height}; box-sizing: border-box; padding: var(--space-3); background: var(--color-surface)">${markup}</main></body></html>`,
		{ waitUntil: 'domcontentloaded' }
	);
	await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--type-text').trim())).not.toBe('');
}

/** Resolve CSS colour expressions through one probe in the mounted document, so a token resolves in the theme that is on. */
async function resolve(page: Page, property: 'color' | 'backgroundColor', expressions: readonly string[]): Promise<string[]> {
	return page.evaluate(({ property, expressions }) => {
		const probe = document.createElement('span');
		document.body.appendChild(probe);
		const out = expressions.map((expression) => {
			probe.style[property] = '';
			probe.style[property] = expression;
			return getComputedStyle(probe)[property];
		});
		probe.remove();
		return out;
	}, { property, expressions });
}

function rgba(css: string): Rgba {
	const parts = css.match(/[\d.]+/g)?.map(Number) ?? [];
	expect(parts.length, `${css} is not an rgb() or rgba() colour`).toBeGreaterThanOrEqual(3);
	return [parts[0], parts[1], parts[2], parts[3] ?? 1];
}

/** A translucent paint laid over an opaque ground, as the screen shows it. */
function over(paint: Rgba, ground: Rgba): Rgba {
	return [0, 1, 2].map((at) => paint[3] * paint[at] + (1 - paint[3]) * ground[at]).concat(1) as Rgba;
}

/** WCAG 2.2 contrast between two opaque colours, written out as tokens.spec.ts does. */
function contrast(a: Rgba, b: Rgba): number {
	const luminance = ([r, g, bl]: Rgba) => {
		const channel = (value: number) => {
			const s = value / 255;
			return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
		};
		return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(bl);
	};
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (high + 0.05) / (low + 0.05);
}

test('a long column name wraps inside its row and never reaches the next one, and the whole name reaches a screen reader and a hover', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	for (const width of ['14rem', '22rem']) {
		await mount(page, 'dark', width, '12rem', draw.ColumnList({ columns: LEDGER_COLUMNS, label: 'Ledger columns' }));
		const rail = await page.locator('[data-explorer-columns]').evaluate((root) => {
			const box = root.querySelector('[data-explorer-column-box]') as HTMLElement;
			const rows = [...root.querySelectorAll('li')].map((row) => {
				const rect = row.getBoundingClientRect();
				const inside = [...row.children].every((child) => {
					const part = child.getBoundingClientRect();
					return part.top >= rect.top - 0.5 && part.bottom <= rect.bottom + 0.5 && part.left >= rect.left - 0.5 && part.right <= rect.right + 0.5;
				});
				const hidden = row.querySelector('code > .sr-only') as HTMLElement | null;
				return {
					top: rect.top,
					bottom: rect.bottom,
					height: rect.height,
					inside,
					name: row.querySelector('code')?.textContent ?? '',
					title: row.getAttribute('title'),
					hidden: hidden?.textContent ?? '',
					hiddenWidth: hidden?.getBoundingClientRect().width ?? -1
				};
			});
			const heading = root.querySelector('h4') as HTMLElement;
			box.scrollTop = box.scrollHeight;
			return {
				rows,
				headings: [...root.querySelectorAll('h4')].map((node) => node.textContent),
				scrolls: box.scrollHeight > box.clientHeight,
				sideways: box.scrollWidth > box.clientWidth,
				headingAtTop: Math.abs(heading.getBoundingClientRect().top - box.getBoundingClientRect().top)
			};
		});
		expect(rail.rows.map((row) => row.name), `${width}: the rail does not print every column's whole name`).toEqual(LEDGER_COLUMNS.map((column) => column.name));
		expect(rail.headings, `${width}: the ledger is not named once`).toEqual(['item-health']);
		expect(rail.rows[0].height, `${width}: the long name did not wrap, so this check proved nothing`).toBeGreaterThanOrEqual(48);
		expect(rail.sideways, `${width}: the rail scrolls sideways`).toBe(false);
		expect(rail.scrolls, `${width}: the rail is too short to scroll, so the heading check proved nothing`).toBe(true);
		expect(rail.headingAtTop, `${width}: the ledger heading scrolled away from the top of its list`).toBeLessThan(1);
		for (const [at, row] of rail.rows.entries()) {
			expect(row.inside, `${width}: ${row.name} spills out of its row`).toBe(true);
			expect(row.title, `${width}: hovering ${row.name} does not give the whole name`).toBe(row.name);
			expect(row.hidden, `${width}: ${row.name} keeps no ledger prefix for a screen reader`).toBe('item-health.');
			expect(row.hiddenWidth, `${width}: the ledger prefix of ${row.name} is on screen`).toBeLessThanOrEqual(1);
			if (at > 0) expect(row.top, `${width}: ${row.name} overlaps the row above it`).toBeGreaterThanOrEqual(rail.rows[at - 1].bottom - 0.5);
		}
	}
});

for (const theme of THEMES) {
	test(`in ${theme}, each type in the column rail and the answer header wears its family's token`, async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		const markup = draw.ColumnList({ columns: ANSWER_COLUMNS, label: 'Answer columns' }) +
			draw.AnswerTable({ columns: ANSWER_COLUMNS, rows: [ANSWER_ROW], maxRows: 1000, pageSize: 50, cellMaxCh: 40, barSpreadShare: 0.5 });
		await mount(page, theme, '60rem', '40rem', markup);
		const paints = [...new Set(LEDGER_COLUMNS.map((column) => column.paint))];
		const resolved = Object.fromEntries((await resolve(page, 'color', paints)).map((colour, at) => [paints[at], colour]));
		expect(new Set(Object.values(resolved)).size, `${theme}: two type tokens resolve to one colour, so the check cannot fail`).toBe(paints.length);
		const [surface] = await resolve(page, 'backgroundColor', ['var(--color-surface)']);
		for (const root of ['[data-explorer-columns]', '[data-explorer-answer] thead']) {
			const labels = await page.locator(`${root} [data-column-type]`).evaluateAll((nodes) =>
				nodes.map((node) => ({ text: node.textContent, paint: (node as HTMLElement).style.color, color: getComputedStyle(node).color }))
			);
			expect(labels.map((label) => label.text), `${theme} ${root}: the types are not printed in lower case`).toEqual(ANSWER_COLUMNS.map((column) => column.type.toLowerCase()));
			for (const [at, label] of labels.entries()) {
				const wanted = ANSWER_COLUMNS[at].paint;
				expect(label.paint, `${theme} ${root}: ${label.text} is painted with the wrong token`).toBe(wanted);
				expect(label.color, `${theme} ${root}: ${label.text} does not resolve to ${wanted}`).toBe(resolved[wanted]);
				const ratio = contrast(rgba(label.color), rgba(surface));
				expect(ratio, `${theme} ${root}: ${label.text} reads ${ratio.toFixed(2)}:1 on the surface`).toBeGreaterThanOrEqual(4.5);
			}
		}
		const notes = await page.locator('[data-explorer-answer] thead th small').evaluateAll((nodes) => nodes.map((node) => getComputedStyle(node).color));
		expect(new Set(notes), `${theme}: the note under a column header is not tertiary`).toEqual(new Set([resolved['var(--color-text-tertiary)']]));
	});

	test(`in ${theme}, a chosen ledger's row is tinted with an accent edge, its words stay readable, and its focus ring shows`, async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 });
		await mount(page, theme, '14rem', '30rem', draw.LedgerList(LEDGER_RAIL));
		const [tint, surface, transparent] = await resolve(page, 'backgroundColor', ['var(--tint-accent)', 'var(--color-surface)', 'transparent']);
		const [accent, focus, text, secondary] = await resolve(page, 'color', ['var(--color-accent)', 'var(--color-focus)', 'var(--color-text)', 'var(--color-text-secondary)']);
		const rows = Object.fromEntries(await page.locator('[data-ledger-name]').evaluateAll((nodes) => nodes.map((node) => {
			const style = getComputedStyle(node);
			const name = node.querySelector('span') as HTMLElement;
			const line = node.querySelector('small') as HTMLElement;
			return [node.getAttribute('data-ledger-name'), {
				chosen: node.getAttribute('data-chosen'),
				background: style.backgroundColor,
				edge: style.borderLeftColor,
				edgeWidth: style.borderLeftWidth,
				opacity: style.opacity,
				weight: getComputedStyle(name).fontWeight,
				name: getComputedStyle(name).color,
				line: getComputedStyle(line).color
			}];
		})));
		expect(Object.keys(rows)).toEqual(['seen', 'item-health', 'host-fingerprint', 'feed-health']);
		const chosenGround = over(rgba(tint), rgba(surface));
		for (const ledger of ['item-health', 'host-fingerprint']) {
			const row = rows[ledger];
			expect(row.chosen, `${theme}: ${ledger} is chosen and not marked so`).toBe('yes');
			expect(row.background, `${theme}: ${ledger} is chosen and not tinted`).toBe(tint);
			expect(row.edge, `${theme}: ${ledger} is chosen and has no accent edge`).toBe(accent);
			expect(row.edgeWidth).toBe('3px');
			expect(row.weight, `${theme}: ${ledger} is chosen and its name is not heavier`).toBe('600');
			for (const [part, colour] of [['name', row.name], ['second line', row.line]] as const) {
				const ratio = contrast(rgba(colour), chosenGround);
				expect(ratio, `${theme}: ${ledger}'s ${part} reads ${ratio.toFixed(2)}:1 on the chosen tint`).toBeGreaterThanOrEqual(4.5);
			}
		}
		expect(rows['item-health'].line, `${theme}: a chosen row's second line is not secondary`).toBe(secondary);
		expect(rows['host-fingerprint'].line, `${theme}: a chosen row lost the warning colour of a date before the span`).toBe(text);
		for (const ledger of ['seen', 'feed-health']) {
			const row = rows[ledger];
			expect(row.chosen, `${theme}: ${ledger} is not chosen and is marked so`).toBe('no');
			expect(row.edge, `${theme}: ${ledger} is not chosen and shows an edge`).toBe(transparent);
			expect(row.edgeWidth, `${theme}: ${ledger} reserves no edge, so choosing it would move its row`).toBe('3px');
			expect(row.weight).toBe('400');
			expect(row.opacity, `${theme}: ${ledger} is dimmed with opacity`).toBe('1');
		}
		expect(rows['feed-health'].name, `${theme}: a ledger not on this site is not one step quieter`).toBe(secondary);
		const unpublished = contrast(rgba(rows['feed-health'].line), rgba(surface));
		expect(unpublished, `${theme}: feed-health's second line reads ${unpublished.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);

		await page.locator('[data-ledger-name="seen"] input').focus();
		await page.keyboard.press('Tab');
		const box = page.locator('[data-ledger-name="item-health"] input');
		await expect(box).toBeFocused();
		const ring = await box.evaluate((node) => {
			const style = getComputedStyle(node);
			return { style: style.outlineStyle, width: style.outlineWidth, color: style.outlineColor };
		});
		expect(ring, `${theme}: the chosen row's checkbox shows no focus ring`).toEqual({ style: 'solid', width: '2px', color: focus });
		const ringRatio = contrast(rgba(ring.color), chosenGround);
		expect(ringRatio, `${theme}: the focus ring reads ${ringRatio.toFixed(2)}:1 on the chosen tint`).toBeGreaterThanOrEqual(3);
	});
}
