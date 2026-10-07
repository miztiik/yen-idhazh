import { expect, test, type Page } from '@playwright/test';
import { rangeMarks } from '../src/lib/charts/series';
import { sourceCuts, SOURCE_CUT_ROWS } from '../src/lib/server/model-work';

/**
 * Sources cut short, drawn against the cap that cuts them.
 *
 * The section used to be five columns of numbers, and the one number every one
 * of them had to be compared against - where the cut falls - was printed
 * nowhere on the page. It is a rule across every row now, and the distance
 * right of it is the text the machine never read.
 *
 * The reducer cases below write the rows that settle the arithmetic. The browser
 * cases check that the page keeps each printed value in step with the attributes
 * it publishes beside it.
 */

/** The plot's own subtree. The compression scatter above it draws a cap line
 * too, out of the same ledger, so an unscoped `[data-cap-line]` matches both
 * and the oracle would be reading whichever came first. */
const PLOT = '[data-source-cuts="range"]';

/** The window the section is drawing, read off the section. A length chosen
 * here would be an oracle over a plot nobody is being shown. */
async function openWindow(page: Page): Promise<number> {
	const days = Number(
		await page.locator('[data-windowed="source-cuts"]').getAttribute('data-window-days')
	);
	expect(days, 'the section publishes no window, so every oracle below spans nothing').toBeGreaterThan(
		0
	);
	return days;
}

const CUT_WINDOW = { start: '2026-08-01', end: '2026-08-07', days: 7 };

function cutRow(cells: Record<string, string>): Record<string, string> {
	return {
		date: '2026-08-07',
		source_id: 'alpha',
		url_key: 'alpha-1',
		source_words: '',
		source_words_before_cap: '',
		...cells
	};
}

const CUT_ROWS = [
	cutRow({
		date: '2026-08-03',
		source_id: 'alpha',
		url_key: 'alpha-1',
		source_words: '3000',
		source_words_before_cap: '5000'
	}),
	cutRow({
		date: '2026-08-04',
		source_id: 'alpha',
		url_key: 'alpha-2',
		source_words: '3000',
		source_words_before_cap: '7000'
	}),
	cutRow({
		date: '2026-08-05',
		source_id: 'alpha',
		url_key: 'alpha-repeat',
		source_words: '1800',
		source_words_before_cap: '2500'
	}),
	cutRow({
		date: '2026-08-05',
		source_id: 'alpha',
		url_key: 'alpha-repeat',
		source_words: '3000',
		source_words_before_cap: '6500'
	}),
	cutRow({
		date: '2026-08-06',
		source_id: 'alpha',
		url_key: 'alpha-4',
		source_words: '9000',
		source_words_before_cap: '9000'
	}),
	cutRow({
		date: '2026-08-06',
		source_id: 'beta',
		url_key: 'beta-1',
		source_words: '3000',
		source_words_before_cap: '4200'
	}),
	cutRow({
		date: '2026-08-06',
		source_id: 'beta',
		url_key: 'beta-2',
		source_words: '2000',
		source_words_before_cap: '2000'
	}),
	cutRow({
		date: '2026-08-06',
		source_id: 'beta',
		url_key: 'beta-3',
		source_words: '30000',
		source_words_before_cap: ''
	}),
	cutRow({
		date: '2026-08-07',
		source_id: 'gamma',
		url_key: 'gamma-1',
		source_words: '3846',
		source_words_before_cap: '6200'
	}),
	cutRow({
		date: '2026-08-07',
		source_id: 'gamma',
		url_key: 'gamma-2',
		source_words: '1800',
		source_words_before_cap: '1800'
	}),
	cutRow({
		date: '2026-08-02',
		source_id: 'delta',
		url_key: 'delta-1',
		source_words: '1923',
		source_words_before_cap: '4100'
	})
];

function group(value: number): string {
	return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

test('cut points come from the rows that were cut, not from the setting', () => {
	const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 2 });

	expect(cuts.caps).toEqual([
		{ words: 1923, first: '2026-08-02', last: '2026-08-02' },
		{ words: 3000, first: '2026-08-03', last: '2026-08-06' },
		{ words: 3846, first: '2026-08-07', last: '2026-08-07' }
	]);
	expect(cuts.measured).toBe(true);
});

test('the drawn rule agrees with the cap values the page publishes', async ({ page }) => {
	await page.goto('/console/voices/');
	await openWindow(page);

	if ((await page.locator(PLOT).count()) === 0) {
		await expect(page.locator('[data-source-cuts="unmeasured"], [data-source-cuts="none"]')).toHaveCount(
			1
		);
		await expect(page.locator(`${PLOT} [data-cap-line]`)).toHaveCount(0);
		return;
	}

	const lines = await page
		.locator(`${PLOT} [data-cap-line]`)
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				words: Number(node.getAttribute('data-cap-line')),
				x1: Number(node.getAttribute('x1')),
				x2: Number(node.getAttribute('x2'))
			}))
		);
	const labels = await page
		.locator(`${PLOT} [data-cap-label]`)
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				words: Number(node.getAttribute('data-cap-label')),
				text: node.textContent ?? ''
			}))
		);

	expect(labels.map((label) => label.words)).toEqual(lines.map((line) => line.words));
	for (const line of lines) {
		expect(line.x1, `cap ${line.words} is not a vertical rule`).toBe(line.x2);
		const label = labels.find((entry) => entry.words === line.words);
		expect(label?.text, `cap ${line.words} has no label`).toContain(`cut at ${group(line.words)} words`);
	}

	// And it is where a reader would put it: right of every article shorter than
	// the cut point, left of every article longer than it. A rule carrying the
	// right number at the wrong x answers nothing.
	const drawn = await page
		.locator('[data-source-cut]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				id: node.getAttribute('data-source-cut') ?? '',
				min: Number(node.getAttribute('data-range-min')),
				max: Number(node.getAttribute('data-range-max')),
				past: node.getAttribute('data-range-past'),
				x0: Number(node.querySelector('[data-range-cell="track"]')?.getAttribute('x1')),
				x1: Number(node.querySelector('[data-range-cell="track"]')?.getAttribute('x2'))
			}))
		);
	for (const row of drawn) expect(row.x1, `${row.id} draws its track backwards`).toBeGreaterThanOrEqual(row.x0);
	for (const line of lines) {
		for (const row of drawn.filter((entry) => entry.min < line.words && entry.max > line.words)) {
			expect(row.x0, `${row.id} starts right of cap ${line.words}`).toBeLessThan(line.x1);
			expect(row.x1, `${row.id} ends left of cap ${line.words}`).toBeGreaterThan(line.x1);
		}
	}
});

test('sources cut by the cap are ranked worst first, with the tail counted', () => {
	const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 2 });

	expect(cuts.rows).toEqual([
		{
			sourceId: 'alpha',
			cut: 3,
			articles: 4,
			lengths: { min: 5000, median: 6750, max: 9000 }
		},
		{
			sourceId: 'beta',
			cut: 1,
			articles: 3,
			lengths: { min: 2000, median: 3100, max: 4200 }
		}
	]);
	expect(cuts.moreSources).toBe(2);
	expect(cuts.moreCuts).toBe(2);
	expect(cuts.articles).toBe(10);
});

test('source cut rows are ordered by their published counts, and the tail sentence matches its numbers', async ({
	page
}) => {
	await page.goto('/console/voices/');
	await openWindow(page);

	const named = await page
		.locator('[data-source-cut]')
		.evaluateAll((nodes) =>
			nodes.map((node) => {
				const count = node.querySelector('[data-source-cell="count"]')?.textContent ?? '';
				return {
					id: node.getAttribute('data-source-cut') ?? '',
					cut: Number(/^(\d+) of /.exec(count)?.[1] ?? NaN),
					articles: Number(/ of (\d+) cut$/.exec(count)?.[1] ?? NaN)
				};
			})
		);
	for (let index = 1; index < named.length; index += 1) {
		expect(
			named[index - 1].cut,
			`${named[index].id} is ranked above a source it cut more often`
		).toBeGreaterThanOrEqual(named[index].cut);
		if (named[index - 1].cut === named[index].cut) {
			expect(named[index - 1].id.localeCompare(named[index].id)).toBeLessThanOrEqual(0);
		}
	}
	for (const row of named) {
		expect(row.cut, `${row.id} has no cut count`).toBeGreaterThanOrEqual(0);
		expect(row.articles, `${row.id} has fewer articles than cuts`).toBeGreaterThanOrEqual(row.cut);
	}

	const more = page.locator('[data-source-cuts-more]');
	if ((await more.count()) > 0) {
		expect(((await more.textContent()) ?? '').trim()).toMatch(/^\d+ more sources had \d+ cuts between them\.$/);
	}
});

test('article counts collapse reruns, and ranges use measured article length', () => {
	const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 4 });
	const alpha = cuts.rows.find((row) => row.sourceId === 'alpha');
	const beta = cuts.rows.find((row) => row.sourceId === 'beta');

	expect(alpha?.articles, 'five rows of alpha collapse to four articles').toBe(4);
	expect(alpha?.cut).toBe(3);
	expect(alpha?.lengths).toEqual({ min: 5000, median: 6750, max: 9000 });
	expect(beta?.articles, 'a row without a before length is still an article').toBe(3);
	expect(beta?.lengths.max, 'the surviving 30,000-word cell is not a pre-cut length').toBe(4200);
});

test('each source cut row reads its own label and range cells', async ({ page }) => {
	await page.goto('/console/voices/');
	await openWindow(page);

	const rows = await page.locator('[data-source-cut]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			id: node.getAttribute('data-source-cut') ?? '',
			name: node.querySelector('[data-source-cell="name"]')?.textContent?.trim() ?? '',
			count: node.querySelector('[data-source-cell="count"]')?.textContent?.trim() ?? '',
			min: node.getAttribute('data-range-min') ?? '',
			median: node.getAttribute('data-range-median') ?? '',
			max: node.getAttribute('data-range-max') ?? '',
			label: node.getAttribute('aria-label') ?? ''
		}))
	);
	for (const row of rows) {
		expect(row.name, `${row.id} prints a different name`).toBe(row.id);
		expect(row.count, `${row.id} count has no article denominator`).toMatch(/^\d+ of \d+ cut$/);
		expect(row.label, `${row.id} label lost its count`).toContain(`${row.count.replace(' cut', ' articles cut')}`);
		expect(row.label, `${row.id} label lost its shortest length`).toContain(
			`Shortest article ${group(Number(row.min))} words`
		);
		expect(row.label, `${row.id} label lost its middle length`).toContain(`middle ${group(Number(row.median))}`);
		expect(row.label, `${row.id} label lost its longest length`).toContain(`longest ${group(Number(row.max))}`);
	}
});

test('the marks are the three lengths, in the order a length axis puts them', async ({ page }) => {
	await page.goto('/console/voices/');
	await openWindow(page);

	// A track running the wrong way, or a middle mark outside its own range,
	// would still carry the right numbers in its attributes. This is the check
	// that the geometry agrees with them.
	const geometry = await page.locator('[data-source-cut]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			id: node.getAttribute('data-source-cut') ?? '',
			min: Number(node.getAttribute('data-range-min')),
			max: Number(node.getAttribute('data-range-max')),
			x0: Number(node.querySelector('[data-range-cell="track"]')?.getAttribute('x1')),
			x1: Number(node.querySelector('[data-range-cell="track"]')?.getAttribute('x2')),
			mid: Number(node.querySelector('[data-range-cell="median"]')?.getAttribute('cx')),
			pastFrom: Number(node.querySelector('[data-range-cell="past"]')?.getAttribute('x1')),
			pastTo: Number(node.querySelector('[data-range-cell="past"]')?.getAttribute('x2'))
		}))
	);

	const wide = geometry.filter((row) => row.max > row.min);
	expect(wide.length, 'every source published one length, so the tracks have no direction').toBeGreaterThan(0);
	for (const row of wide) expect(row.x1, `${row.id} draws backwards`).toBeGreaterThan(row.x0);
	for (const row of geometry) {
		expect(row.mid, `${row.id} puts its middle article outside its own range`).toBeGreaterThanOrEqual(
			row.x0
		);
		expect(row.mid).toBeLessThanOrEqual(row.x1);
	}

	// The emphasised segment is the part of the track past the rule, so it can
	// never start before the track it belongs to or run past its end.
	const emphasised = geometry.filter((row) => Number.isFinite(row.pastFrom));
	expect(emphasised.length, 'no row draws the part past the cut point').toBeGreaterThan(0);
	for (const row of emphasised) {
		expect(row.pastFrom, `${row.id} starts its lost span outside its track`).toBeGreaterThanOrEqual(
			row.x0
		);
		expect(row.pastTo).toBe(row.x1);
	}

	// The axis is a log one, and it says so: decade labels, in order.
	const ticks = await page
		.locator('[data-source-cuts="range"] [data-tick="x"]')
		.evaluateAll((nodes) => nodes.map((node) => Number((node.textContent ?? '').replace(/,/g, ''))));
	expect(ticks.length, 'the length axis carries no labels').toBeGreaterThan(1);
	for (let index = 1; index < ticks.length; index += 1) {
		expect(ticks[index] / ticks[index - 1], 'the axis is not stepping by decades').toBe(10);
	}
});

test('cut cost is counted as article losses with n, median and max', () => {
	const cuts = sourceCuts(CUT_ROWS, CUT_WINDOW, { limit: 2 });

	expect(cuts.cost).toEqual({ n: 6, median: 2354, max: 4000 });
});

test('the source cut cost sentence leads the section and agrees with its own numbers', async ({ page }) => {
	await page.goto('/console/voices/');
	await openWindow(page);

	const cost = page.locator('[data-source-cuts-cost]');
	if ((await cost.count()) === 0) {
		await expect(page.locator('[data-windowed="source-cuts"]')).toContainText(/No article was cut short|Nothing has recorded/);
		return;
	}
	const text = ((await cost.textContent()) ?? '').replace(/\s+/g, ' ').trim();
	const match =
		/^(\d+) articles were cut short\. Half of them lost more than ([\d,]+) words each, and the longest lost ([\d,]+)\.$/.exec(
			text
		);
	expect(match, 'the cost sentence stopped printing n, median and max').not.toBeNull();
	const [, n, median, max] = match as RegExpExecArray;
	expect(Number(n), 'the cost sentence printed no cut article count').toBeGreaterThan(0);
	expect(Number(median.replace(/,/g, '')), 'the median loss exceeds the maximum loss').toBeLessThanOrEqual(
		Number(max.replace(/,/g, ''))
	);

	// It leads the section now. It is the most useful line on it and it used to
	// be the smallest type, printed under the table.
	const order = await page
		.locator('[data-windowed="source-cuts"] p')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-source-cuts-cost') === ''));
	expect(order[0], 'the cost sentence is no longer the first line of the section').toBe(true);
});

/** The seven days the unit cases below read, ending on the day their rows sit on. */
const WEEK = { start: '2026-08-22', end: '2026-08-28', days: 7 };

test('a window with no cut renders its own empty state, and absence is not zero', () => {
	// Driven at the module, because the page only draws the state the current
	// build holds. The reducer still has to keep absence and zero apart.
	const migrated = (source: string, index: number) => ({
		date: '2026-08-28',
		source_id: source,
		url_key: `${source}-${index}`,
		source_words: '5000',
		source_words_before_cap: ''
	});

	// Seven days here is this test's own window, not the page's. The function
	// takes the span it is given, and these rows all sit on one day.
	const nothing = sourceCuts([migrated('a', 0), migrated('a', 1)], WEEK, { limit: SOURCE_CUT_ROWS });
	// Not listed with a zero. Zero cuts and no measurement are different facts,
	// and the zero is the one nobody checks.
	expect(nothing.rows).toEqual([]);
	// And the page says which of the two it is: nothing recorded a length here,
	// so the section is not empty - it cannot answer yet.
	expect(nothing.measured).toBe(false);
	expect(nothing.cost).toBeNull();
	// No cut, so no rule. A rule read off the setting would draw here anyway,
	// across a plot with nothing on it.
	expect(nothing.caps).toEqual([]);

	// A length on record, and the cap fired on it. The source arrives with a
	// range, and the rule arrives with it.
	const some = sourceCuts(
		[
			migrated('a', 0),
			{
				date: '2026-08-28',
				source_id: 'a',
				url_key: 'a-1',
				source_words: '1923',
				source_words_before_cap: '2612'
			}
		],
		WEEK,
		{ limit: SOURCE_CUT_ROWS }
	);
	expect(some.measured).toBe(true);
	expect(some.rows).toHaveLength(1);
	expect(some.rows[0].cut).toBe(1);
	expect(some.rows[0].articles).toBe(2);
	// One measured length, so the three marks are the same article. The other
	// article recorded no length before the cut and is a denominator, never a
	// point on the axis.
	expect(some.rows[0].lengths).toEqual({ min: 2612, median: 2612, max: 2612 });
	expect(some.caps).toEqual([{ words: 1923, first: '2026-08-28', last: '2026-08-28' }]);
	expect(some.cost).toEqual({ n: 1, median: 689, max: 689 });

	// Empty is not zero on the other cell either: a row with no surviving length
	// is not an article cut to nothing.
	expect(
		sourceCuts(
			[
				{
					date: '2026-08-28',
					source_id: 'a',
					url_key: 'a-0',
					source_words: '',
					source_words_before_cap: '2612'
				}
			],
			WEEK,
			{ limit: SOURCE_CUT_ROWS }
		).rows
	).toEqual([]);
});

test('a cut point per length the cap left, oldest first, read off the rows', () => {
	const row = (index: number, date: string, before: string, after: string) => ({
		date,
		source_id: 'a',
		url_key: `a-${index}`,
		source_words: after,
		source_words_before_cap: before
	});
	const capsOf = (rows: Record<string, string>[]) =>
		sourceCuts(rows, { start: '2026-08-01', end: '2026-08-30', days: 30 }, { limit: SOURCE_CUT_ROWS }).caps;

	// One cut point, over the days it was in force. A lone cap needs no dates on
	// its label, and they are here so the next case can have them.
	expect(capsOf([row(0, '2026-08-20', '4000', '1923'), row(1, '2026-08-22', '9000', '1923')])).toEqual(
		[{ words: 1923, first: '2026-08-20', last: '2026-08-22' }]
	);

	// The cap moved inside the window. Two rules, oldest first, each dated by the
	// rows it was the cut on - which is the state the committed ledger is in.
	expect(
		capsOf([row(0, '2026-08-20', '4000', '1923'), row(1, '2026-08-29', '9000', '3846')])
	).toEqual([
		{ words: 1923, first: '2026-08-20', last: '2026-08-20' },
		{ words: 3846, first: '2026-08-29', last: '2026-08-29' }
	]);

	// The same call over rows cut somewhere else answers somewhere else. This is
	// the pair that says the rule is read off the rows: no value taken from
	// `extract.truncation_cap_tokens`, or from any other setting, can satisfy
	// both lines at once. A window can hold rows a run wrote under an older cap,
	// and the rule has to agree with the rows under it rather than with the file.
	expect(capsOf([row(0, '2026-08-20', '4000', '1877')])[0].words).toBe(1877);

	// A source the list never reached still puts a rule on the plot. The cut
	// point is a fact about the window, not about the ten rows drawn from it.
	const many = sourceCuts(
		[
			...Array.from({ length: 12 }, (_, index) => ({
				date: '2026-08-28',
				source_id: `s${index}`,
				url_key: `s${index}-0`,
				source_words: '1900',
				source_words_before_cap: '4000'
			})),
			{
				date: '2026-08-28',
				source_id: 'tail',
				url_key: 'tail-0',
				source_words: '1923',
				source_words_before_cap: '5000'
			}
		],
		WEEK,
		{ limit: SOURCE_CUT_ROWS }
	);
	expect(many.rows).toHaveLength(SOURCE_CUT_ROWS);
	expect(many.moreSources).toBe(3);
	expect(many.caps.map((cap) => cap.words)).toEqual([1900, 1923]);
});

test('a row is placed on the axis, and the lost span is held inside it', () => {
	// An identity scale, so the arithmetic is readable: one word is one pixel.
	const identity = (words: number) => words;

	// The ordinary shape: short articles left of the cut point, long ones right
	// of it, and the emphasised span starting exactly on the rule.
	expect(rangeMarks({ min: 400, median: 2600, max: 9000 }, 1923, identity)).toEqual({
		x0: 400,
		xMid: 2600,
		x1: 9000,
		xCut: 1923,
		past: true
	});

	// Every article past the cut point. The span is the whole track, which is
	// the true reading: this source loses text on everything it publishes.
	expect(rangeMarks({ min: 2623, median: 4723, max: 9000 }, 1923, identity).xCut).toBe(2623);

	// Nothing past it. The span has no length rather than a negative one, so the
	// plot draws no emphasis on a source the cap never reached.
	const untouched = rangeMarks({ min: 100, median: 200, max: 900 }, 1923, identity);
	expect(untouched.past).toBe(false);
	expect(untouched.xCut).toBe(untouched.x1);

	// No cut in the window at all. Same answer, and no rule to clamp against.
	expect(rangeMarks({ min: 100, median: 200, max: 900 }, null, identity).past).toBe(false);
});

async function counts(page: Page, prefix: string): Promise<Map<string, number>> {
	const cells = await page
		.locator(`[data-source-state^="${prefix}-"]`)
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				state: node.getAttribute('data-source-state') ?? '',
				count: Number(node.querySelector('[data-source-state-count]')?.textContent ?? 'x')
			}))
		);
	return new Map(cells.map(({ state, count }) => [state.slice(prefix.length + 1), count]));
}

test('source health state rows sum to the census the page publishes', async ({
	page
}) => {
	await page.goto('/console/voices/');

	const lead = page.locator('[data-source-health-lead]');
	if ((await lead.count()) === 0) {
		await expect(page.locator('[data-source-health="absent"]')).toHaveCount(1);
		await expect(page.locator('[data-source-state]')).toHaveCount(0);
		return;
	}
	const sources = Number(await lead.getAttribute('data-source-health-sources'));

	for (const prefix of ['permission', 'availability'] as const) {
		const drawn = await counts(page, prefix);
		const total = [...drawn.values()].reduce((sum, count) => sum + count, 0);
		expect(total, `the ${prefix} states do not sum to the census`).toBe(sources);
		expect(drawn.size, `the ${prefix} table has no state rows`).toBeGreaterThan(0);
	}

	const retired = await counts(page, 'retirement');
	expect(retired.get('retired') ?? 0, 'retired sources exceed the census').toBeLessThanOrEqual(
		sources
	);
});

test('held-back source notes match the withheld count the page publishes', async ({ page }) => {
	await page.goto('/console/voices/');
	const lead = page.locator('[data-source-health-lead]');
	if ((await lead.count()) === 0) {
		await expect(page.locator('[data-source-health="absent"]')).toHaveCount(1);
		return;
	}
	const withheld = Number(await lead.getAttribute('data-source-health-withheld'));

	const drawn = await page
		.locator('[data-source-note]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				id: node.getAttribute('data-source-note') ?? '',
				withheld: (node.querySelector('[data-source-note-withheld]')?.textContent ?? '').trim()
			}))
		);
	const table = page.locator('[data-source-health="notes"]');
	const drawnCount = (await table.count()) === 0 ? 0 : Number(await table.getAttribute('data-source-health-drawn'));
	const more = page.locator('[data-source-health-more]');
	const hidden =
		(await more.count()) === 0
			? 0
			: Number(/^(\d+) more /.exec(((await more.textContent()) ?? '').trim())?.[1] ?? 'NaN');
	expect(drawn.length).toBe(drawnCount);
	expect(drawn.length + hidden, 'the notes and hidden count do not match withheld').toBe(withheld);
	expect(new Set(drawn.map((row) => row.id)).size).toBe(drawn.length);
	for (const row of drawn) {
		// Every automatic state says what the reader loses while it holds. A
		// state named and not costed is a state nobody can weigh.
		expect(row.withheld.length, `${row.id} names no cost`).toBeGreaterThan(10);
	}
	if (withheld === 0) await expect(page.locator('[data-source-health="clear"]')).toHaveCount(1);
});

test('the publishing record prints its own counts, and says when it is too short', async ({
	page
}) => {
	await page.goto('/console/voices/');
	const record = page.locator('[data-source-health-record]');
	if ((await record.count()) === 0) {
		await expect(page.locator('[data-source-health="absent"]')).toHaveCount(1);
		return;
	}
	const days = Number(await record.getAttribute('data-source-health-days'));
	const state = await record.getAttribute('data-source-health-record');
	const text = (await record.innerText()).replace(/\s+/g, ' ');
	if (days === 0) {
		expect(text).toContain('No day has finished');
		return;
	}
	expect(text).toContain(`Over ${days} complete ${days === 1 ? 'day' : 'days'}`);
	const yieldCounts = /were offered ([\d,]+) addresses and published ([\d,]+)/.exec(text);
	expect(yieldCounts, 'the record prints no offered and published counts').not.toBeNull();
	const [offered, won] = [yieldCounts?.[1], yieldCounts?.[2]].map((figure) => Number((figure ?? '').replace(/,/g, '')));
	// The identity a rate can break and a pair of counts cannot.
	expect(won, 'the record published more than it was offered').toBeLessThanOrEqual(offered);
	// No rate anywhere in the sentence while the record is short. A share over
	// nine days presented as a yield is an estimate wearing a measurement's
	// clothes.
	if (state === 'short') {
		expect(text).toContain('counts and not a rate');
		expect(text).not.toMatch(/\d%/);
	}
});

test('the scorecard fits a phone without pushing the page sideways', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/console/voices/');
	const overflow = await page
		.locator('[data-source-health="states"], [data-source-health="notes"]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				scroll: node.scrollWidth,
				client: node.clientWidth,
				right: node.getBoundingClientRect().right
			}))
		);
	expect(overflow.length, 'the scorecard drew no table at all').toBeGreaterThan(0);
	for (const box of overflow) {
		// A framed table may scroll inside its own frame; what it may not do is
		// push the document sideways, which is what makes every other section
		// unreadable on the same screen.
		expect(box.right).toBeLessThanOrEqual(391);
	}
	const document = await page.evaluate(() => ({
		scroll: window.document.documentElement.scrollWidth,
		width: window.innerWidth
	}));
	expect(document.scroll).toBeLessThanOrEqual(document.width + 1);
});
