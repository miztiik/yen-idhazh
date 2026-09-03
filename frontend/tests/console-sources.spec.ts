import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { rangeMarks } from '../src/lib/charts/series';
import { sourceCuts, SOURCE_CUT_ROWS } from '../src/lib/server/model-work';
import { readCsv } from '../src/lib/server/payload';

/**
 * Sources cut short, drawn against the cap that cuts them.
 *
 * The section used to be five columns of numbers, and the one number every one
 * of them had to be compared against - where the cut falls - was printed
 * nowhere on the page. It is a rule across every row now, and the distance
 * right of it is the text the machine never read.
 *
 * The oracle below is the row's whole point: the drawn rule has to land on the
 * cut point the ledger itself records, never on the setting behind it. A rule
 * drawn from `extract.truncation_cap_tokens` would draw even in a window where
 * nothing was cut, and a ninety-day window can span a change to that setting.
 *
 * It runs against the canary build. See `frontend/scripts/build-canary.mjs` for
 * the source rows and `backend/utilities/build_canary_day.py` for the rest.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

/** The plot's own subtree. The compression scatter above it draws a cap line
 * too, out of the same ledger, so an unscoped `[data-cap-line]` matches both
 * and the oracle would be reading whichever came first. */
const PLOT = '[data-source-cuts="range"]';

/** Every item-health row the canary wrote. */
function ledger(): Record<string, string>[] {
	const dir = join(CANARY, 'state', 'item-health');
	return readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(dir, name)).rows);
}

interface Article {
	source: string;
	before: number | null;
	after: number | null;
}

/** The window's articles, recomputed from the CSV rather than from the module
 * the page uses. The oracle is that a drawn mark equals what a second,
 * independent reading of the ledger produces.
 *
 * One entry per article, never per row: a run writes a row for every item it
 * plans, so counting rows counts a re-run twice. The window ends on the newest
 * day the ledger holds, so a fixture that grows a day moves this with it
 * instead of going stale.
 */
function windowArticles(days: number): Article[] {
	const all = ledger();
	const newest = all
		.map((row) => row.date)
		.sort()
		.at(-1) as string;
	const first = new Date(new Date(`${newest}T00:00:00Z`).getTime() - (days - 1) * 86_400_000)
		.toISOString()
		.slice(0, 10);

	const held = new Map<string, Article>();
	for (const row of all) {
		if (row.date < first || row.date > newest) continue;
		const cell = (name: string) => (row[name] === '' ? null : Number(row[name]));
		const key = `${row.source_id}/${row.url_key}`;
		const before = cell('source_words_before_cap');
		const seen = held.get(key);
		if (seen === undefined) {
			held.set(key, { source: row.source_id, before, after: cell('source_words') });
		} else if (before !== null && (seen.before === null || before > seen.before)) {
			seen.before = before;
			seen.after = cell('source_words');
		}
	}
	return [...held.values()];
}

function wasCut(article: Article): boolean {
	return article.before !== null && article.after !== null && article.before > article.after;
}

/** Every cut point in the window, over the window's own articles.
 *
 * One entry per distinct post-cap length among the articles that were cut,
 * because a window can span a change to the pipeline's cap and one rule cannot
 * be right for both. Nothing here reads the pipeline's setting, which is what
 * makes it an oracle over the page rather than a second copy of its arithmetic.
 */
function cutPoints(days: number): number[] {
	return [
		...new Set(
			windowArticles(days)
				.filter(wasCut)
				.map((article) => article.after as number)
		)
	].sort((a, b) => a - b);
}

interface Row {
	sourceId: string;
	cut: number;
	articles: number;
	min: number;
	median: number;
	max: number;
}

/** What the plot has to draw, in the order it has to draw it. */
function expectedRows(days: number): { rows: Row[]; tail: { sources: number; cuts: number } } {
	const bySource = new Map<string, Article[]>();
	for (const article of windowArticles(days)) {
		bySource.set(article.source, [...(bySource.get(article.source) ?? []), article]);
	}

	const found: Row[] = [];
	for (const [sourceId, group] of bySource) {
		const cut = group.filter(wasCut);
		if (cut.length === 0) continue;
		const lengths = group
			.map((article) => article.before)
			.filter((words): words is number => words !== null)
			.sort((a, b) => a - b);
		const middle = Math.floor(lengths.length / 2);
		found.push({
			sourceId,
			cut: cut.length,
			articles: group.length,
			min: lengths[0],
			median: Math.round(
				lengths.length % 2 ? lengths[middle] : (lengths[middle - 1] + lengths[middle]) / 2
			),
			max: lengths[lengths.length - 1]
		});
	}
	found.sort((a, b) => b.cut - a.cut || a.sourceId.localeCompare(b.sourceId));
	const rest = found.slice(SOURCE_CUT_ROWS);
	return {
		rows: found.slice(0, SOURCE_CUT_ROWS),
		tail: {
			sources: rest.length,
			cuts: rest.reduce((total, source) => total + source.cut, 0)
		}
	};
}

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

async function attr(page: Page, selector: string, name: string): Promise<number> {
	return Number(await page.locator(selector).getAttribute(name));
}

test('THE ORACLE: the drawn rule stands where the ledger says the cut fell', async ({ page }) => {
	await page.goto('/console/');
	const days = await openWindow(page);

	const points = cutPoints(days);
	expect(points.length, 'nothing in the fixture window was cut, so the rule is untested').toBeGreaterThan(
		0
	);
	const cap = points[points.length - 1];

	// The values the page drew, against the values a second reading of the ledger
	// produces. Both come off `source_words` on a row whose two lengths differ -
	// the same cell the pipeline wrote after the cap fired - and neither reads the
	// setting behind it.
	const drew = await page
		.locator(`${PLOT} [data-cap-line]`)
		.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('data-cap-line'))));
	expect(drew.slice().sort((a, b) => a - b)).toEqual(points);
	await expect(page.locator(`${PLOT} [data-cap-label]`)).toHaveCount(points.length);
	await expect(page.locator(`${PLOT} [data-cap-label="${cap}"]`)).toContainText(
		`cut at ${String(cap).replace(/\B(?=(\d{3})+(?!\d))/g, ',')} words`
	);

	// And it is where a reader would put it: right of every article shorter than
	// the cut point, left of every article longer than it. A rule carrying the
	// right number at the wrong x answers nothing.
	const ruleX = await attr(page, `${PLOT} [data-cap-line="${cap}"]`, 'x1');
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
	expect(drawn.length, 'the plot drew no source').toBeGreaterThan(0);
	const shorter = drawn.filter((row) => row.min < cap);
	expect(shorter.length, 'every source starts past the cut point, so the rule sits at the left edge and is untested').toBeGreaterThan(0);
	for (const row of shorter) expect(row.x0, `${row.id} starts right of the rule`).toBeLessThan(ruleX);
	for (const row of drawn) {
		// `past` is the claim the emphasised span makes, so it says what it means:
		// this source published an article the widest cut point could not hold.
		expect(row.past, `${row.id} disagrees with its own longest article`).toBe(
			row.max > cap ? 'yes' : 'no'
		);
		expect(row.max, `${row.id} is on the plot without an article past the cut point`).toBeGreaterThan(
			cap
		);
		expect(row.x1, `${row.id} ends left of the rule`).toBeGreaterThan(ruleX);
	}

	// The claim the plot makes spatially, checked against the ledger: text drawn
	// right of the rule is text a cut removed. The fixture carries the one row
	// that separates that from "long", a 9,000-word article of `cut-a` nothing
	// cut, so the exception is named here rather than absorbed silently.
	const longButWhole = windowArticles(days).filter(
		(article) => article.before !== null && article.before > cap && !wasCut(article)
	);
	expect(
		longButWhole.map((article) => `${article.source} ${article.before}`),
		'an article longer than the cut point survived it, and the fixture does not say which'
	).toEqual(['cut-a 9000']);
});

test('one row per source the cap cut, worst first, with the count in the label', async ({
	page
}) => {
	await page.goto('/console/');
	const days = await openWindow(page);
	const { rows, tail } = expectedRows(days);

	// The fixture has to hold more than the plot draws, or the sort and the
	// sentence under it are both asserted against nothing.
	expect(rows.length, 'the fixture cuts fewer sources than the plot draws').toBe(SOURCE_CUT_ROWS);
	expect(tail.sources, 'the fixture never overflows, so the tail is untested').toBeGreaterThan(0);

	const named = await page
		.locator('[data-source-cut]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-source-cut') ?? ''));
	expect(named).toEqual(rows.map((source) => source.sourceId));
	// A source whose lengths were never recorded cannot be ranked and is absent
	// rather than drawn at zero.
	expect(named).not.toContain('no-length');

	for (const source of rows) {
		const row = page.locator(`[data-source-cut="${source.sourceId}"]`);
		await expect(row.locator('[data-source-cell="name"]')).toHaveText(source.sourceId);
		// The count and its denominator, beside the track they describe. The old
		// table had them in two columns and the share in a third.
		await expect(row.locator('[data-source-cell="count"]')).toHaveText(
			`${source.cut} of ${source.articles} cut`
		);
		await expect(row).toHaveAttribute('data-range-min', String(source.min));
		await expect(row).toHaveAttribute('data-range-median', String(source.median));
		await expect(row).toHaveAttribute('data-range-max', String(source.max));
	}

	await expect(page.locator('[data-source-cuts-more]')).toHaveText(
		`${tail.sources} more sources had ${tail.cuts} cuts between them.`
	);
});

test('the label counts articles, not rows, and the track reads the right cell', async ({ page }) => {
	await page.goto('/console/');
	await openWindow(page);

	// One of this source's articles was written by two runs. A row count says
	// eight; the label says articles, and it published seven.
	const rows = ledger().filter((row) => row.source_id === 'cut-a');
	expect(rows.length, 'no article is written twice, so the count below proves nothing').toBe(8);
	await expect(page.locator('[data-source-cut="cut-a"] [data-source-cell="count"]')).toHaveText(
		'6 of 7 cut'
	);

	// Its longest article was never cut. A track drawn over the cut articles
	// alone would end at 6,123 here, and the source's real reach would be off
	// the plot.
	await expect(page.locator('[data-source-cut="cut-a"]')).toHaveAttribute(
		'data-range-max',
		'9000'
	);

	// And this one's longest surviving body sits on a row that recorded no
	// length before the cut. Reading `source_words` would reach 30,000; the
	// question is how long the article was, and that row never answered it.
	await expect(page.locator('[data-source-cut="cut-b"]')).toHaveAttribute(
		'data-range-max',
		'5423'
	);
});

test('the marks are the three lengths, in the order a length axis puts them', async ({ page }) => {
	await page.goto('/console/');
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

test('what the cut cost is the first sentence of the section, with its n', async ({ page }) => {
	await page.goto('/console/');
	const days = await openWindow(page);

	const losses = windowArticles(days)
		.filter(wasCut)
		.map((article) => (article.before as number) - (article.after as number))
		.sort((a, b) => a - b);
	const median = losses[Math.floor(losses.length / 2)];
	const max = losses[losses.length - 1];
	// A median equal to its own maximum is one number printed twice. The fixture
	// loses a different amount from every article, so the two are two facts.
	expect(median).toBeLessThan(max);

	const group = (value: number) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
	await expect(page.locator('[data-source-cuts-cost]')).toHaveText(
		`${losses.length} articles were cut short. Half of them lost more than ${group(median)} words each, and the longest lost ${group(max)}.`
	);

	// It leads the section now. It is the most useful line on it and it used to
	// be the smallest type, printed under the table.
	const order = await page
		.locator('[data-windowed="source-cuts"] p')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-source-cuts-cost') === ''));
	expect(order[0], 'the cost sentence is no longer the first line of the section').toBe(true);
});

test('a window with no cut renders its own empty state, and absence is not zero', () => {
	// Driven at the module, because the canary cuts something in every preset it
	// offers and a fixture that reached this state would stop testing the plot.
	const migrated = (source: string, index: number) => ({
		date: '2026-08-28',
		source_id: source,
		url_key: `${source}-${index}`,
		source_words: '5000',
		source_words_before_cap: ''
	});

	// Seven days here is this test's own window, not the page's. The function
	// takes the span it is given, and these rows all sit on one day.
	const nothing = sourceCuts([migrated('a', 0), migrated('a', 1)], {
		days: 7,
		limit: SOURCE_CUT_ROWS
	});
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
		{ days: 7, limit: SOURCE_CUT_ROWS }
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
			{ days: 7, limit: SOURCE_CUT_ROWS }
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
		sourceCuts(rows, { days: 30, limit: SOURCE_CUT_ROWS }).caps;

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
		{ days: 7, limit: SOURCE_CUT_ROWS }
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

/**
 * The source-health scorecard: four facts, kept apart.
 *
 * The oracle reads `backend/var/canary/source-health.json` - the projection the
 * pipeline wrote and the page rendered - rather than re-deriving permission,
 * availability or retirement in the test. Re-deriving them here would be a
 * third reducer over the same evidence, and the row's whole argument is that
 * two are already one too many.
 */
interface ViewRow {
	source_id: string;
	title: string;
	vertical: string;
	permission: string;
	availability: string;
	retired: boolean;
	retired_on: string | null;
	opportunities: number;
	publications: number;
	source_failures: number;
}

interface View {
	min_complete_days: number;
	complete_dates: number;
	yield_readable: boolean;
	first_date: string | null;
	last_date: string | null;
	sources: ViewRow[];
}

function view(): View {
	return JSON.parse(readFileSync(join(CANARY, 'source-health.json'), 'utf8')) as View;
}

function tallyOf(rows: ViewRow[], of: (row: ViewRow) => string): Map<string, number> {
	const found = new Map<string, number>();
	for (const row of rows) found.set(of(row), (found.get(of(row)) ?? 0) + 1);
	return found;
}

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

test('THE ORACLE: every state the view holds is drawn, and the states sum to the census', async ({
	page
}) => {
	const published = view();
	expect(published.sources.length, 'the canary view names no source').toBeGreaterThan(0);
	await page.goto('/console/');

	for (const [prefix, of] of [
		['permission', (row: ViewRow) => row.permission],
		['availability', (row: ViewRow) => row.availability]
	] as const) {
		const expected = tallyOf(published.sources, of);
		const drawn = await counts(page, prefix);
		// Every state the fixture reaches is on the page with the count the file
		// gives it. A state the fixture cannot reach is still drawn, at zero,
		// because a census that hides its empty states is a sample.
		for (const [state, count] of expected) {
			expect(drawn.get(state), `${prefix} ${state} is not drawn`).toBe(count);
		}
		const total = [...drawn.values()].reduce((sum, count) => sum + count, 0);
		expect(total, `the ${prefix} states do not sum to the census`).toBe(
			published.sources.length
		);
		expect(expected.size, `the fixture reaches only one ${prefix} state`).toBeGreaterThan(1);
	}

	const lead = page.locator('[data-source-health-lead]');
	await expect(lead).toHaveAttribute('data-source-health-sources', String(published.sources.length));
	const retired = await counts(page, 'retirement');
	expect(retired.get('retired')).toBe(published.sources.filter((row) => row.retired).length);
});

test('THE ORACLE: every source held back is named, with what it withholds', async ({ page }) => {
	const published = view();
	const held = published.sources.filter(
		(row) =>
			row.retired ||
			row.permission === 'denied' ||
			row.permission === 'unreachable' ||
			row.availability !== 'answering'
	);
	expect(held.length, 'the canary holds nothing back, so this asserts nothing').toBeGreaterThan(0);

	await page.goto('/console/');
	await expect(page.locator('[data-source-health-lead]')).toHaveAttribute(
		'data-source-health-withheld',
		String(held.length)
	);

	const drawn = await page
		.locator('[data-source-note]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				id: node.getAttribute('data-source-note') ?? '',
				withheld: (node.querySelector('[data-source-note-withheld]')?.textContent ?? '').trim()
			}))
		);
	const table = page.locator('[data-source-health="notes"]');
	const cap = Number(await table.getAttribute('data-source-health-drawn'));
	expect(drawn.length).toBe(cap);
	expect(new Set(drawn.map((row) => row.id)).size).toBe(drawn.length);
	for (const row of drawn) {
		expect(held.map((entry) => entry.source_id)).toContain(row.id);
		// Every automatic state says what the reader loses while it holds. A
		// state named and not costed is a state nobody can weigh.
		expect(row.withheld.length, `${row.id} names no cost`).toBeGreaterThan(10);
	}
	// The loudest state leads, because a rest lifts itself and a retirement
	// never does.
	const retiredAt = drawn.findIndex((row) =>
		published.sources.some((entry) => entry.source_id === row.id && entry.retired)
	);
	if (retiredAt >= 0) expect(retiredAt).toBe(0);
});

test('THE ORACLE: the publishing record prints counts, and says when it is too short', async ({
	page
}) => {
	const published = view();
	const offered = published.sources.reduce((sum, row) => sum + row.opportunities, 0);
	const won = published.sources.reduce((sum, row) => sum + row.publications, 0);
	// The identity a rate can break and a pair of counts cannot.
	expect(won, 'a yield numerator beat its own denominator').toBeLessThanOrEqual(offered);
	for (const row of published.sources) {
		expect(row.publications).toBeLessThanOrEqual(row.opportunities);
		expect(row.source_failures).toBeLessThanOrEqual(row.opportunities);
	}

	await page.goto('/console/');
	const record = page.locator('[data-source-health-record]');
	await expect(record).toHaveAttribute(
		'data-source-health-days',
		String(published.complete_dates)
	);
	await expect(record).toHaveAttribute(
		'data-source-health-record',
		published.yield_readable ? 'measured' : 'short'
	);
	const text = (await record.innerText()).replace(/\s+/g, ' ');
	expect(text).toContain(String(published.first_date));
	expect(text).toContain(String(published.last_date));
	// No rate anywhere in the sentence while the record is short. A share over
	// nine days presented as a yield is an estimate wearing a measurement's
	// clothes.
	if (!published.yield_readable) {
		expect(text).toContain('counts and not a rate');
		expect(text).not.toMatch(/\d%/);
	}
});

test('the scorecard fits a phone without pushing the page sideways', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/console/');
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
