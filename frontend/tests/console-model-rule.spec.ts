import { expect, test, type Page } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { modelRules } from '../src/lib/charts/frame';
import { pipelineChanges } from '../src/lib/server/model-work';

/**
 * The model-change rule, and the judgement behind it.
 *
 * A dashed rule down a chart says "everything left of this was written by a
 * different setup". That sentence is true of a chart of writing time and false
 * of a chart of feed outcomes, so the mark is a judgement about the measure and
 * not a decoration. A marker that means nothing on half the page teaches an
 * operator to stop reading it, which costs the half where it did mean
 * something.
 *
 * Two arms, and neither is sufficient alone.
 *
 * The Node arm states the arithmetic over rows built here, because the canary
 * ledger writes ONE `pipeline_fingerprint` for its one scored day and therefore
 * cannot draw a rule at all. An oracle that only ever asserted zero would pass
 * against a component that had stopped deriving anything.
 *
 * The browser arm reads the built canary's own ledger, derives the boundary
 * dates from it without touching the component's code, and holds every drawn
 * chart to that count. On the canary that count is zero - so what it proves
 * there is the other half of the row: the empty case is a named state and not a
 * missing element, and every chart that does not draw says why in words.
 */

const STATE = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

/** The canary's score rows, read as the page's server reads them. */
function canaryScores(): Record<string, string>[] {
	const dir = join(STATE, 'scores');
	const rows: Record<string, string>[] = [];
	for (const name of readdirSync(dir).filter((entry) => entry.endsWith('.csv')).sort()) {
		const lines = readFileSync(join(dir, name), 'utf8').split('\n').filter(Boolean);
		const header = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cells = line.split(',');
			rows.push(Object.fromEntries(header.map((key, at) => [key, cells[at] ?? ''])));
		}
	}
	return rows;
}

/**
 * The boundary dates, derived here rather than imported.
 *
 * The rule, stated in `docs/architecture/publishing/frontend.md`: a day is a
 * boundary when it ran a stamp the previous scored day did not run. This is a
 * second implementation of it on purpose - a check that calls the code it is
 * checking only proves the code is deterministic.
 */
function boundariesFrom(rows: Record<string, string>[]): string[] {
	const seen = new Map<string, string[]>();
	for (const row of rows) {
		if (!row.date || !row.pipeline_fingerprint) continue;
		seen.set(row.date, [...(seen.get(row.date) ?? []), row.pipeline_fingerprint]);
	}
	const dates = [...seen.keys()].sort();
	const found: string[] = [];
	for (let at = 1; at < dates.length; at += 1) {
		const before = seen.get(dates[at - 1]) ?? [];
		const now = seen.get(dates[at]) ?? [];
		if (now.some((stamp) => !before.includes(stamp))) found.push(dates[at]);
	}
	return found;
}

const ROUTES = ['/console/', '/console/model/', '/console/machine/'];

interface Declared {
	route: string;
	name: string;
	rule: string;
	reason: string;
	from: string;
	to: string;
	lines: string[];
	empty: number;
}

/** Every chart on one route that has declared a bucket, and what it drew.
 *
 * The empty state is found by the chart's own name rather than by walking up
 * the tree: the caption a chart writes it into is a sibling of the plot, so a
 * parent-scoped query on Pipelines reaches the next chart down the page and
 * returns two. Scoping by name is exact at any nesting.
 */
async function declaredOn(page: Page, route: string): Promise<Declared[]> {
	await page.goto(route);
	return page.locator('[data-model-rule]').evaluateAll(
		(nodes, at) =>
			nodes.map((node) => {
				const name = node.getAttribute('data-model-rule-name') ?? '';
				return {
					route: at as string,
					name,
					rule: node.getAttribute('data-model-rule') ?? '',
					reason: node.getAttribute('data-model-rule-none') ?? '',
					from: node.getAttribute('data-model-rule-from') ?? '',
					to: node.getAttribute('data-model-rule-to') ?? '',
					lines: [...node.querySelectorAll('[data-model-rule-line]')].map(
						(line) => line.getAttribute('data-model-rule-line') ?? ''
					),
					empty:
						name === ''
							? 0
							: document.querySelectorAll(`[data-model-rule-empty="${name}"]`).length
				};
			}),
		route
	);
}

test.describe('the boundary, as arithmetic', () => {
	const row = (date: string, stamp: string) => ({ date, pipeline_fingerprint: stamp });

	test('a day running a stamp yesterday did not run is a boundary', () => {
		expect(
			pipelineChanges([row('2026-08-01', 'aaa'), row('2026-08-02', 'aaa'), row('2026-08-03', 'bbb')])
		).toEqual(['2026-08-03']);
	});

	test('the first scored day is never a boundary - there is nothing before it', () => {
		expect(pipelineChanges([row('2026-08-01', 'aaa'), row('2026-08-02', 'aaa')])).toEqual([]);
	});

	test('a day that only stopped using one of yesterday stamps changed nothing', () => {
		// The measured shape: 2026-08-29 ran two stamps and 2026-08-30 ran one of
		// them. Nothing new started on the 30th, so nothing is drawn on it.
		expect(
			pipelineChanges([
				row('2026-08-29', 'old'),
				row('2026-08-29', 'new'),
				row('2026-08-30', 'new')
			])
		).toEqual([]);
	});

	test('a day carrying several stamps is one boundary, because a day is one column', () => {
		expect(
			pipelineChanges([
				row('2026-08-25', 'aaa'),
				row('2026-08-26', 'aaa'),
				row('2026-08-26', 'bbb'),
				row('2026-08-26', 'ccc')
			])
		).toEqual(['2026-08-26']);
	});

	test('a row with no stamp is not a change', () => {
		expect(
			pipelineChanges([
				row('2026-08-01', 'aaa'),
				{ date: '2026-08-02', pipeline_fingerprint: '' },
				row('2026-08-02', 'aaa')
			])
		).toEqual([]);
	});

	test('the committed ledger, read by both implementations, agrees', () => {
		const rows = canaryScores();
		expect(rows.length, 'the canary ledger is empty - the read is broken').toBeGreaterThan(0);
		expect(pipelineChanges(rows)).toEqual(boundariesFrom(rows));
	});
});

test.describe('the rule, as geometry', () => {
	const dates = ['2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04'];
	const columns = [100, 200, 300, 400];

	test('a rule sits on the leading edge of the day that changed', () => {
		expect(modelRules(['2026-08-03'], dates, columns)).toEqual([{ date: '2026-08-03', x: 250 }]);
	});

	test('every boundary in the span is drawn, not only the newest', () => {
		// A ninety-day window can hold two, and hiding the older one makes the
		// older half of the chart unattributable.
		expect(modelRules(['2026-08-02', '2026-08-04'], dates, columns).map((r) => r.date)).toEqual([
			'2026-08-02',
			'2026-08-04'
		]);
	});

	test('a change outside the drawn days draws nothing', () => {
		expect(modelRules(['2026-07-30'], dates, columns)).toEqual([]);
	});

	test('a change on the first drawn day draws nothing - it separates nothing', () => {
		expect(modelRules(['2026-08-01'], dates, columns)).toEqual([]);
	});

	test('the rule follows uneven columns, not an assumed step', () => {
		expect(modelRules(['2026-08-02'], dates, [0, 10, 300, 400])).toEqual([
			{ date: '2026-08-02', x: 5 }
		]);
	});
});

test.describe('the rule, on the built console', () => {
	test('a chart that draws the rule draws one per boundary inside its own span', async ({
		page
	}) => {
		const boundaries = boundariesFrom(canaryScores());
		let drawing = 0;
		for (const route of ROUTES) {
			for (const chart of await declaredOn(page, route)) {
				if (chart.rule !== 'yes') continue;
				drawing += 1;
				const at = `${route} ${chart.name}`;
				expect(chart.from, `${at} declares a rule and no span it drew`).not.toBe('');
				expect(chart.to, `${at} declares a rule and no span it drew`).not.toBe('');
				// Strictly inside: the oldest drawn day has nothing to its left, so a
				// change on it separates nothing and is not drawn.
				const inside = boundaries.filter((date) => date > chart.from && date <= chart.to);
				expect(
					chart.lines.sort(),
					`${at}: rules drawn between ${chart.from} and ${chart.to}`
				).toEqual(inside.sort());
			}
		}
		expect(drawing, 'no chart on the console draws the rule at all').toBeGreaterThan(0);
	});

	test('a chart that draws no rule in its span says so, rather than being blank', async ({
		page
	}) => {
		const boundaries = boundariesFrom(canaryScores());
		for (const route of ROUTES) {
			for (const chart of await declaredOn(page, route)) {
				if (chart.rule !== 'yes') continue;
				const inside = boundaries.filter((date) => date > chart.from && date <= chart.to);
				if (inside.length > 0) continue;
				expect(
					chart.empty,
					`${route} ${chart.name}: no boundary in its span and no sentence about it`
				).toBe(1);
			}
		}
	});

	test('a chart that does not draw the rule names why, in words', async ({ page }) => {
		let refusing = 0;
		for (const route of ROUTES) {
			for (const chart of await declaredOn(page, route)) {
				if (chart.rule === 'yes') continue;
				refusing += 1;
				const at = `${route} ${chart.name}`;
				expect(chart.rule, `${at}: a bucket that is neither yes nor no`).toBe('no');
				// Five words is a decision. Nothing is an omission, and the two are
				// indistinguishable on a page.
				expect(
					chart.reason.trim().split(/\s+/).length,
					`${at}: "${chart.reason}" is not a reason`
				).toBeGreaterThanOrEqual(5);
				expect(chart.lines, `${at}: declares no rule and draws one`).toEqual([]);
			}
		}
		expect(
			refusing,
			'nothing on the console declines the rule - the judgement is not being made'
		).toBeGreaterThan(0);
	});

	test('every declaring chart is named, and no two share a name', async ({ page }) => {
		const names: string[] = [];
		for (const route of ROUTES) {
			for (const chart of await declaredOn(page, route)) {
				expect(chart.name, `${route}: a chart declares a bucket and no name`).not.toBe('');
				names.push(`${route}${chart.name}`);
			}
		}
		expect([...new Set(names)].sort()).toEqual(names.sort());
	});

	test('the boundary reaches the readout on the days it happened, and no others', async ({
		page
	}) => {
		// The rule is a mark on the plot AND a line in the strip, so a reader who
		// steps the days with an arrow key meets it without a pointer. Stepping
		// every column and counting is what stops the line being a constant: a row
		// printed on every column would say the pipeline changed every day.
		const boundaries = boundariesFrom(canaryScores());
		await page.goto('/console/');
		const chart = page.locator('[data-model-rule-name="timings"]');
		await expect(chart).toHaveCount(1);
		const from = (await chart.getAttribute('data-model-rule-from')) ?? '';
		const to = (await chart.getAttribute('data-model-rule-to')) ?? '';
		const inside = boundaries.filter((date) => date > from && date <= to);

		const plot = chart.locator('svg');
		await plot.focus();
		await page.keyboard.press('Home');
		const columns = Number(await chart.getAttribute('data-readout-columns'));
		expect(columns, 'the timings chart drew no columns to step through').toBeGreaterThan(0);

		let printed = 0;
		for (let at = 0; at < columns; at += 1) {
			printed += await chart
				.locator('[data-readout-row="How summaries are written"]')
				.count();
			await page.keyboard.press('ArrowRight');
		}
		expect(printed, 'the strip and the plot disagree about which days changed').toBe(
			inside.length
		);
	});
});
