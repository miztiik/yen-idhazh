import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import { rank, tailSentence, percentOf } from '../src/lib/charts/rank';
import type { RankedDisplay } from '../src/lib/charts/rank';
import { targetBar, targetGeometry, targetMarks } from '../src/lib/charts/targetbar';
import { sparkline, sparklineMarks, sparklineShape } from '../src/lib/charts/sparkline';

/**
 * A ranked list that draws a plausible but wrong bar is the failure worth a
 * test: nothing about it looks broken, and a bar scaled to the wrong divisor
 * still puts the biggest row at the top. So the geometry is recomputed here
 * from the inputs and compared to what the specification says - and then
 * measured again in a real browser, because a percentage that is right in the
 * markup can still lay out wrong.
 *
 * The components are rendered on their own rather than through a page. Nothing
 * on the console renders them yet - the four call sites land in later rows - and
 * a route added only to host a test would ship to a reader.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
const built = path.join(frontend, 'test-results', 'rendered');

type Rendered = { body: string; css: string };

async function renderer(name: string): Promise<(props: Record<string, unknown>) => Rendered> {
	const filename = path.join(frontend, 'src', 'lib', 'components', `${name}.svelte`);
	const source = readFileSync(filename, 'utf8');
	const pre = await preprocess(source, vitePreprocess(), { filename });
	const result = compile(pre.code, { generate: 'server', filename, name });
	mkdirSync(built, { recursive: true });
	const module = path.join(built, `${name}.server.mjs`);
	writeFileSync(module, result.js.code, 'utf8');
	const loaded = await import(pathToFileURL(module).href);
	const css = result.css?.code ?? '';
	return (props) => ({ body: render(loaded.default, { props }).body, css });
}

const tokens = readFileSync(path.join(frontend, 'src', 'styles', 'tokens.css'), 'utf8');

/** The component's own markup and its own stylesheet, in a real browser. The
 * scope hashes come from the same compile, so the two cannot disagree. */
async function show(page: import('@playwright/test').Page, out: Rendered) {
	await page.setContent(
		`<!doctype html><html><head><style>${tokens}</style><style>${out.css}</style>` +
			`<style>body{margin:0}#host{inline-size:1000px}</style></head>` +
			`<body><div id="host">${out.body}</div></body></html>`,
		{ waitUntil: 'domcontentloaded' }
	);
}

function display(label: string, value: string, extra: Partial<RankedDisplay> = {}): RankedDisplay {
	return { label, value, ...extra };
}

test.describe('the ranking', () => {
	test('orders by magnitude, and never by the order it arrived in', () => {
		// Deliberately handed over newest-first, which is what five of the six
		// console tables used to do.
		const r = rank(
			[
				{ key: 'wed', value: 3, row: display('wed', '3') },
				{ key: 'tue', value: 17, row: display('tue', '17') },
				{ key: 'mon', value: 9, row: display('mon', '9') }
			],
			10
		);
		expect(r.rows.map((x) => x.key)).toEqual(['tue', 'mon', 'wed']);
	});

	test('every bar is the value over the printed maximum', () => {
		const magnitudes = [
			{ key: 'a', value: 38 },
			{ key: 'b', value: 17 },
			{ key: 'c', value: 6 },
			{ key: 'd', value: 1 }
		];
		const r = rank(
			magnitudes.map((m) => ({ ...m, row: display(m.key, String(m.value)) })),
			10
		);

		// The divisor is recomputed from the rendered set, not read back out.
		const divisor = Math.max(...r.rows.map((x) => x.value));
		expect(r.max).toBe(divisor);
		expect(divisor).toBe(38);

		for (const row of r.rows) {
			expect(row.fraction).toBeCloseTo(row.value / divisor, 10);
			expect(row.percent).toBe(percentOf(row.value / divisor));
		}
		expect(r.rows[0].percent).toBe('100.0000%');
	});

	test('the cap hides the tail and counts what it hid', () => {
		const r = rank(
			[9, 8, 7, 6, 5].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })),
			3
		);
		expect(r.rows.map((x) => x.value)).toEqual([9, 8, 7]);
		expect(r.hidden).toBe(2);
		expect(r.hiddenValue).toBe(11);
		// The maximum is the rendered set's own, which is what the bars are drawn
		// against and what the list prints.
		expect(r.max).toBe(9);
	});

	test('a tie lands the same way whichever order it arrived in', () => {
		const rows = (order: string[]) =>
			rank(
				order.map((k) => ({ key: k, value: 5, row: display(k, '5') })),
				10
			).rows.map((x) => x.key);
		expect(rows(['b', 'a', 'c'])).toEqual(['a', 'b', 'c']);
		expect(rows(['c', 'b', 'a'])).toEqual(['a', 'b', 'c']);
	});

	test('a tiebreak outranks the key, and the magnitude outranks both', () => {
		const r = rank(
			[
				{ key: 'a', value: 5, tiebreak: 1, row: display('a', '5') },
				{ key: 'b', value: 5, tiebreak: 9, row: display('b', '5') },
				{ key: 'c', value: 6, tiebreak: 0, row: display('c', '6') }
			],
			10
		);
		expect(r.rows.map((x) => x.key)).toEqual(['c', 'b', 'a']);
	});

	test('a value nobody measured is dropped, not ranked as zero', () => {
		const r = rank(
			[
				{ key: 'a', value: Number.NaN, row: display('a', '-') },
				{ key: 'b', value: 4, row: display('b', '4') }
			],
			10
		);
		expect(r.rows.map((x) => x.key)).toEqual(['b']);
		expect(r.hidden).toBe(0);
	});

	test('a list of zeros draws no bar rather than a NaN one', () => {
		const r = rank(
			[
				{ key: 'a', value: 0, row: display('a', '0') },
				{ key: 'b', value: 0, row: display('b', '0') }
			],
			10
		);
		expect(r.max).toBe(0);
		for (const row of r.rows) {
			expect(Number.isFinite(row.fraction)).toBe(true);
			expect(row.percent).toBe('0.0000%');
		}
	});

	test('nothing to rank is empty', () => {
		const r = rank([], 10);
		expect(r.empty).toBe(true);
		expect(r.max).toBe(0);
	});

	test('a percentage cannot run negative or past the end of its track', () => {
		expect(percentOf(-0.4)).toBe('0.0000%');
		expect(percentOf(1.7)).toBe('100.0000%');
		expect(percentOf(Number.NaN)).toBe('0%');
	});
});

test.describe('the tail sentence', () => {
	const nouns = { one: 'source', many: 'sources', unitOne: 'cut', unitMany: 'cuts' };

	test('says how many rows are missing and what they cost', () => {
		const r = rank(
			[9, 8, 7, 6, 5].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })),
			3
		);
		expect(tailSentence(r, nouns)).toBe('2 more sources had 11 cuts between them.');
	});

	test('one hidden row is one source, not one sources', () => {
		const r = rank(
			[4, 3].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })),
			1
		);
		expect(tailSentence(r, nouns)).toBe('1 more source had 3 cuts.');
	});

	test('a sum that means nothing is left out of the sentence', () => {
		const r = rank(
			[9, 8, 7].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })),
			1
		);
		expect(tailSentence(r, { one: 'item', many: 'items' })).toBe('2 more items are not shown.');
	});

	test('nothing hidden is no sentence at all', () => {
		const r = rank([{ key: 'a', value: 1, row: display('a', '1') }], 10);
		expect(tailSentence(r, nouns)).toBeNull();
	});
});

test.describe('the target geometry', () => {
	test('the marker sits at the target fraction of the track', () => {
		const g = targetGeometry(4.1, 6, 'lower-is-better');
		expect(g.empty).toBe(false);
		// Track is the larger end plus 15 percent headroom: max(4.1, 6) * 1.15.
		expect(g.markerFraction).toBeCloseTo(6 / (6 * 1.15), 10);
		expect(g.valueFraction).toBeCloseTo(4.1 / (6 * 1.15), 10);
		expect(g.band).toBe('good');
	});

	test('a value past its target is drawn past the marker, not clipped at it', () => {
		const g = targetGeometry(7.2, 6, 'lower-is-better');
		expect(g.valueFraction).toBeGreaterThan(g.markerFraction);
		expect(g.valueFraction).toBeLessThanOrEqual(1);
		expect(g.band).toBe('past');
	});

	test('a value nobody measured draws nothing', () => {
		const g = targetGeometry(null, 5, 'lower-is-better');
		expect(g.empty).toBe(true);
		expect(targetMarks(null, 5, 'lower-is-better').valuePercent).toBe('0.0000%');
	});

	test('the markup bar and the chart bar cannot drift apart', () => {
		for (const [value, target] of [
			[4.1, 6],
			[7.2, 6],
			[5.6, 6],
			[0.03, 0.05]
		] as const) {
			const chart = targetBar(value, target, 'lower-is-better', 'x');
			const markup = targetGeometry(value, target, 'lower-is-better');
			expect(markup.markerFraction).toBeCloseTo(chart.markerFraction, 12);
			expect(markup.band).toBe(chart.band);
		}
	});
});

test.describe('the sparkline shape', () => {
	test('the points fill the drawn extent, not a domain anchored at zero', () => {
		const s = sparklineMarks([980, 1000, 990]);
		expect(s.empty).toBe(false);
		expect(s.min).toBe(980);
		expect(s.max).toBe(1000);
		expect(s.points.map((p) => p.x)).toEqual([0, 0.5, 1]);
		// y runs downward, so the highest value is at the top of the box.
		expect(s.points[0].y).toBeCloseTo(1, 10);
		expect(s.points[1].y).toBeCloseTo(0, 10);
		expect(s.points[2].y).toBeCloseTo(0.5, 10);
	});

	test('a flat series sits on the middle line, not on an edge', () => {
		const s = sparklineMarks([7, 7, 7]);
		expect(s.points.every((p) => p.y === 0.5)).toBe(true);
		expect(s.movement).toBeCloseTo(0, 10);
	});

	test('one point has no direction', () => {
		expect(sparklineShape([5]).empty).toBe(true);
		expect(sparklineMarks([]).points).toEqual([]);
	});

	test('the markup line and the chart line report the same movement', () => {
		for (const series of [[100, 110, 130], [200, 150], [0, 5]]) {
			const chart = sparkline(series);
			const markup = sparklineShape(series);
			expect(markup.movement).toBe(chart.movement);
			expect(markup.rising).toBe(chart.rising);
			expect(markup.empty).toBe(chart.empty);
		}
	});
});

test.describe('the ranked list, rendered', () => {
	let draw: (props: Record<string, unknown>) => Rendered;

	test.beforeAll(async () => {
		draw = await renderer('RankedList');
	});

	const magnitudes = [
		{ key: 'alpha', value: 38 },
		{ key: 'bravo', value: 17 },
		{ key: 'charlie', value: 6 },
		{ key: 'delta', value: 1 }
	];

	function list() {
		return rank(
			magnitudes.map((m) => ({
				key: m.key,
				value: m.value,
				row: display(m.key, `${m.value} cuts`, { context: `of 40 articles` })
			})),
			10
		);
	}

	test('every drawn bar is the value over the printed maximum', async ({ page }) => {
		const ranked = list();
		await show(page, draw({ caption: 'cuts by source', ranked, maxText: '38 cuts', unmeasuredNote: 'x', emptyNote: 'y' }));

		const printed = await page.locator('[data-ranked-max]').getAttribute('data-ranked-max');
		const divisor = Math.max(...magnitudes.map((m) => m.value));
		expect(Number(printed)).toBe(divisor);
		await expect(
			page.locator('[data-ranked-max]'),
			'the divisor must be readable as words, not only as an attribute'
		).toHaveText(`A full bar is 38 cuts.`);

		const measured = await page.evaluate(() =>
			[...document.querySelectorAll('[data-ranked-row]')].map((row) => {
				const track = row.querySelector('[data-ranked-cell="track"]') as HTMLElement;
				const bar = row.querySelector('[data-ranked-cell="bar"]') as HTMLElement;
				const trackPx = track.getBoundingClientRect().width;
				return {
					key: row.getAttribute('data-ranked-row') as string,
					trackPx,
					ratio: bar.getBoundingClientRect().width / trackPx
				};
			})
		);

		expect(measured.map((m) => m.key)).toEqual(['alpha', 'bravo', 'charlie', 'delta']);
		for (const row of measured) {
			const value = magnitudes.find((m) => m.key === row.key)?.value as number;
			// Laid out, in pixels, against the divisor the page printed.
			expect(Math.abs(row.ratio - value / divisor), `${row.key} is drawn to the wrong scale`).toBeLessThan(0.002);
		}

		// Every fraction can be right and the picture still wrong. A row that
		// sized its own columns gave a two-digit value a narrower track than a
		// one-digit one, so two bars of the same fraction came out different
		// lengths and the list could not be read by eye.
		const tracks = new Set(measured.map((m) => Math.round(m.trackPx * 100)));
		expect(tracks.size, 'the rows do not share one track, so their bars are not comparable').toBe(1);
	});

	test('nothing recorded and nothing found say different things', async ({ page }) => {
		const notes = {
			unmeasuredNote: 'Nothing has recorded an article length yet.',
			emptyNote: 'No article was cut short in these 7 days.'
		};

		await show(page, draw({ caption: 'c', ranked: rank([], 10), maxText: '-', measured: false, ...notes }));
		await expect(page.locator('[data-ranked="unmeasured"]')).toHaveText(notes.unmeasuredNote);
		await expect(page.locator('[data-ranked="none"]')).toHaveCount(0);
		await expect(page.locator('[data-ranked="rows"]')).toHaveCount(0);

		await show(page, draw({ caption: 'c', ranked: rank([], 10), maxText: '-', measured: true, ...notes }));
		await expect(page.locator('[data-ranked="none"]')).toHaveText(notes.emptyNote);
		await expect(page.locator('[data-ranked="unmeasured"]')).toHaveCount(0);
	});

	test('the tail sentence is printed where the cap hid something', async ({ page }) => {
		const ranked = rank(
			[9, 8, 7, 6, 5].map((v, i) => ({ key: `k${i}`, value: v, row: display(`k${i}`, `${v}`) })),
			3
		);
		const tail = tailSentence(ranked, { one: 'source', many: 'sources', unitOne: 'cut', unitMany: 'cuts' });
		await show(page, draw({ caption: 'c', ranked, maxText: '9 cuts', unmeasuredNote: 'x', emptyNote: 'y', tail }));
		await expect(page.locator('[data-ranked="tail"]')).toHaveText('2 more sources had 11 cuts between them.');
		await expect(page.locator('[data-ranked-row]')).toHaveCount(3);
	});

	test('a selectable row is a real button that reports whether it is on', async ({ page }) => {
		const ranked = list();
		await show(
			page,
			draw({
				caption: 'c',
				ranked,
				maxText: '38 cuts',
				unmeasuredNote: 'x',
				emptyNote: 'y',
				onSelect: () => {},
				selectedKey: 'bravo'
			})
		);
		const picks = page.locator('[data-ranked-row] button');
		await expect(picks).toHaveCount(4);
		await expect(page.locator('[data-ranked-row="bravo"] button')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.locator('[data-ranked-row="alpha"] button')).toHaveAttribute('aria-pressed', 'false');
	});

	test('with no onSelect there is no control to reach', async ({ page }) => {
		await show(page, draw({ caption: 'c', ranked: list(), maxText: '38 cuts', unmeasuredNote: 'x', emptyNote: 'y' }));
		await expect(page.locator('[data-ranked-row] button')).toHaveCount(0);
	});
});

test.describe('the target bar, rendered', () => {
	let draw: (props: Record<string, unknown>) => Rendered;

	test.beforeAll(async () => {
		draw = await renderer('TargetBar');
	});

	const common = {
		label: 'Failures before it is rested',
		targetText: 'rested at 5 failures',
		emptyNote: 'This feed has not run yet.'
	};

	test('the marker lands on the threshold and the fill lands on the value', async ({ page }) => {
		const marks = targetMarks(4, 5, 'lower-is-better');
		await show(page, draw({ ...common, marks, valueText: '4 failures' }));

		const measured = await page.evaluate(() => {
			const track = document.querySelector('[data-target-cell="track"]') as HTMLElement;
			const fill = document.querySelector('[data-target-cell="fill"]') as HTMLElement;
			const marker = document.querySelector('[data-target-cell="marker"]') as HTMLElement;
			const box = track.getBoundingClientRect();
			return {
				fill: fill.getBoundingClientRect().width / box.width,
				marker: (marker.getBoundingClientRect().left + 1 - box.left) / box.width
			};
		});

		expect(Math.abs(measured.fill - marks.valueFraction), 'the fill is drawn to the wrong scale').toBeLessThan(0.003);
		expect(Math.abs(measured.marker - marks.markerFraction), 'the marker is off its threshold').toBeLessThan(0.003);
	});

	test('a value nobody measured prints a dash and no track', async ({ page }) => {
		await show(page, draw({ ...common, marks: targetMarks(null, 5, 'lower-is-better'), valueText: '-' }));
		await expect(page.locator('[data-target-cell="empty"]')).toHaveText(common.emptyNote);
		await expect(page.locator('[data-target-cell="value"]')).toHaveText('-');
		await expect(page.locator('[data-target-cell="track"]')).toHaveCount(0);
	});

	test('the accessible name is a sentence, not a column heading', async ({ page }) => {
		await show(page, draw({ ...common, marks: targetMarks(4, 5, 'lower-is-better'), valueText: '4 failures' }));
		await expect(page.locator('[data-target-cell="track"]')).toHaveAttribute(
			'aria-label',
			'Failures before it is rested: 4 failures, rested at 5 failures.'
		);
	});

	test('a policy threshold takes no health colour, and quarantine does', async ({ page }) => {
		const past = targetMarks(7, 5, 'lower-is-better');
		await show(page, draw({ ...common, marks: past, valueText: '7 failures', tone: 'policy' }));
		const policy = await page.locator('[data-target-cell="fill"]').evaluate((el) => getComputedStyle(el).backgroundColor);

		await show(page, draw({ ...common, marks: past, valueText: '7 failures', tone: 'health' }));
		const health = await page.locator('[data-target-cell="fill"]').evaluate((el) => getComputedStyle(el).backgroundColor);

		expect(policy).not.toBe(health);
	});
});

test.describe('the sparkline, rendered', () => {
	let draw: (props: Record<string, unknown>) => Rendered;

	test.beforeAll(async () => {
		draw = await renderer('Sparkline');
	});

	test('one drawn point for every day in the series', async ({ page }) => {
		const series = [3, 1, 8, 8, 2, 5, 9];
		await show(page, draw({ marks: sparklineMarks(series), label: 'extract timeout, daily count' }));
		const points = await page.locator('polyline').getAttribute('points');
		expect((points ?? '').trim().split(/\s+/)).toHaveLength(series.length);
		await expect(page.locator('[data-sparkline="line"]')).toHaveAttribute('aria-label', 'extract timeout, daily count');
	});

	test('nothing to draw keeps the row height and draws no line', async ({ page }) => {
		await show(page, draw({ marks: sparklineMarks([4]), label: 'x' }));
		await expect(page.locator('polyline')).toHaveCount(0);
		const box = await page.locator('[data-sparkline="empty"]').boundingBox();
		expect(box?.width).toBe(96);
		expect(box?.height).toBe(22);
	});
});
