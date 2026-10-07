import { expect, test, type Page } from './support/browser';

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
 * Two cases, and neither is sufficient alone.
 *
 * The Node case states the arithmetic over rows built here. An oracle that only
 * ever asserted zero would pass against a component that had stopped deriving
 * anything.
 *
 * The browser case keeps to the built page's own contract: a chart that draws a
 * model-change rule publishes its span and its drawn dates, an empty state names
 * the absence, and the keyboard readout reaches exactly the days the plot marked.
 */

/**
 * The boundary dates from the score ledger's stamp alone.
 *
 * A second implementation of the digest fallback, used to cross-check the
 * against rows this test wrote. A check that calls the code it is checking only
 * proves the code is deterministic.
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

const ROUTES = [
	'/console/',
	'/console/model/',
	'/console/machine/',
	'/console/judgement/',
	'/console/voices/'
];

interface Declared {
	route: string;
	name: string;
	rule: string;
	reason: string;
	from: string;
	to: string;
	lines: string[];
	/** What the chart says about a change on a day it drew no column for. */
	unread: string;
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
					unread:
						name === ''
							? ''
							: [...document.querySelectorAll(`[data-model-rule-unread="${name}"]`)]
									.map((one) => one.textContent ?? '')
									.join(' '),
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

	test('the written ledger, read by both implementations, agrees', () => {
		const rows = [
			row('2026-08-01', 'aaa'),
			row('2026-08-02', 'aaa'),
			row('2026-08-03', 'bbb'),
			row('2026-08-04', 'bbb'),
			row('2026-08-05', 'ccc'),
			{ date: '2026-08-06', pipeline_fingerprint: '' }
		];
		// A day that runs a stamp the day before did not is a boundary; a day with no
		// stamp is not a change.
		expect(pipelineChanges(rows)).toEqual(['2026-08-03', '2026-08-05']);
		expect(pipelineChanges(rows)).toEqual(boundariesFrom(rows));
	});
});

/**
 * The half that reads the run record, which is what a day carrying one has.
 *
 * `pipeline_fingerprint` stopped being written on 2026-09-12, so a chart that
 * only read the score ledger would report "nothing moved" for ever. What is
 * compared now is each run's recorded input manifest, and the comparison can say
 * which input moved where a digest could only say that one did.
 *
 * The dates here are arbitrary and consecutive. Nothing in the rule turns on
 * what they are: the eligibility of a day is decided by which record it carries,
 * so a case built on a date would be testing a fact about the calendar.
 */
test.describe('the boundary, after the inputs became a record', () => {
	const [first, second, third] = ['2026-03-01', '2026-03-02', '2026-03-03'];
	const runDay = (date: string, ...inputs: (Record<string, unknown> | null)[]) => ({
		date,
		records: inputs.map((one) => ({ inputs: one }))
	});

	test('a day whose recorded inputs differ from yesterday is a boundary', () => {
		expect(
			pipelineChanges(
				[],
				[
					runDay(first, { prompt_sha256: 'aaa' }),
					runDay(second, { prompt_sha256: 'aaa' }),
					runDay(third, { prompt_sha256: 'bbb' })
				]
			)
		).toEqual([third]);
	});

	test('a run that recorded nothing contributes no identity', () => {
		expect(
			pipelineChanges([], [runDay(first, { prompt_sha256: 'aaa' }), runDay(second, null)])
		).toEqual([]);
	});

	test('a stamped day against a recorded day is never a boundary, whatever the dates are', () => {
		// One day's identity is a digest and the next one's is a named manifest.
		// The two shapes always compare unequal, so a rule there would mark a
		// change nothing caused. It is the records that decide this, so the case
		// holds at the one real changeover and at any other pair.
		expect(
			pipelineChanges(
				[{ date: first, pipeline_fingerprint: 'aaa' }],
				[runDay(second, { prompt_sha256: 'aaa' })]
			)
		).toEqual([]);
	});

	test('a day carrying both records reads the manifest and ignores the digest', () => {
		// What a replay leaves behind: `assemble` rewrites run.json unconditionally,
		// so re-running it over a stamped day gives that day a manifest too. Reading
		// both would compare a digest against a manifest and invent a boundary.
		expect(
			pipelineChanges(
				[
					{ date: first, pipeline_fingerprint: 'aaa' },
					{ date: second, pipeline_fingerprint: 'bbb' }
				],
				[runDay(first, { prompt_sha256: 'x' }), runDay(second, { prompt_sha256: 'x' })]
			)
		).toEqual([]);
	});

	test('a digest that moves under a manifest that does not is still no boundary', () => {
		// The same shape as above with the stamps deliberately disagreeing, so a
		// reader can see the precedence is doing the work rather than the values
		// happening to match.
		expect(
			pipelineChanges(
				[
					{ date: first, pipeline_fingerprint: 'aaa' },
					{ date: second, pipeline_fingerprint: 'zzz' }
				],
				[runDay(first, { prompt_sha256: 'x' }), runDay(second, { prompt_sha256: 'x' })]
			)
		).toEqual([]);
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
	test('a chart that draws the rule draws only days inside its own span', async ({
		page
	}) => {
		let drawing = 0;
		for (const route of ROUTES) {
			for (const chart of await declaredOn(page, route)) {
				if (chart.rule !== 'yes') continue;
				drawing += 1;
				const at = `${route} ${chart.name}`;
				expect(chart.from, `${at} declares a rule and no span it drew`).not.toBe('');
				expect(chart.to, `${at} declares a rule and no span it drew`).not.toBe('');
				expect(chart.to >= chart.from, `${at}: its span ends before it starts`).toBe(true);
				expect(new Set(chart.lines).size, `${at}: drew one boundary twice`).toBe(
					chart.lines.length
				);
				for (const line of chart.lines) {
					expect(
						line > chart.from,
						`${at}: drew a boundary on the first day, where nothing is separated`
					).toBe(true);
					expect(line <= chart.to, `${at}: drew a boundary after its own span`).toBe(true);
				}
			}
		}
		expect(drawing, 'no chart on the console draws the rule at all').toBeGreaterThan(0);
	});

	test('a chart that draws no rule says so, rather than being blank', async ({
		page
	}) => {
		for (const route of ROUTES) {
			for (const chart of await declaredOn(page, route)) {
				if (chart.rule !== 'yes') continue;
				if (chart.lines.length === 0) {
					expect(
						chart.empty,
						`${route} ${chart.name}: no boundary drawn and no sentence about it`
					).toBe(1);
				}
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
		await page.goto('/console/');
		const chart = page.locator('[data-model-rule-name="timings"]');
		await expect(chart).toHaveCount(1);
		const rules = await chart.locator('[data-model-rule-line]').count();

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
			rules
		);
	});
});
