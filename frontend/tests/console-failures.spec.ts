import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	causeKey,
	datesIn,
	failedRows,
	failureLedger,
	failureRowKey,
	parseTelemetryCsv,
	sourceLosses,
	type TelemetryRow
} from '../src/lib/charts/series';
import { rank, tailSentence, type Rankable, type RankedDisplay } from '../src/lib/charts/rank';
import type { TimeWindow } from '../src/lib/charts/viewport';

/**
 * A ledger that draws a plausible but wrong ranking is the failure worth a
 * test. Every bar looks right, the biggest cause is still at the top, and the
 * only thing wrong is that the counts do not add up to the rows underneath -
 * which nobody checks by eye over eleven causes and a thousand rows.
 *
 * So the partition is proved rather than assumed: the causes' counts sum to the
 * window's failed rows, and selecting each cause in turn yields row sets with
 * no overlap and no remainder. It is proved over rows built to carry the
 * awkward shape - eleven causes running 529 down to 1, fourteen sources against
 * a cap of ten - rather than over the committed projection, which used to be
 * read in full on every run and which answers a question about the news
 * whenever it is asked whether it still holds enough failures to be worth
 * reading.
 *
 * The same shape is proved of the source ranking beside it, and there the
 * dedupe is the thing that can be plausibly wrong: a source's losses are
 * ARTICLES, one per source per day, while the rows under them are one per stage
 * per run. Counting rows would leave every bar in proportion, every name in the
 * right order, and every number too big.
 *
 * The interaction is proved twice over, in two places, because the canary
 * fixture deliberately records no failure at all: `build-canary.mjs` writes
 * dropped items as `ok`, since throwing away a page that is not an article is
 * the job. So the browser half here asserts the shapes and the empty states,
 * and the click-through against real failures is the section-12 smoke against
 * the production build.
 */

const frontend = process.cwd();
const CANARY_TELEMETRY = resolve(frontend, '..', 'backend', 'var', 'canary', 'state', 'telemetry');

/** The cap the source ranking draws with, from the file the page reads it
 * from. Not a copy: a number typed here would pass while the section drew a
 * different one. */
const SOURCE_ROWS =
	(
		JSON.parse(
			readFileSync(resolve(frontend, '..', 'config', 'appearance.json'), 'utf8')
		) as { console?: { source_rows?: number } }
	).console?.source_rows ?? 10;

function shardRows(root: string): TelemetryRow[] {
	if (!existsSync(root)) return [];
	return readdirSync(root)
		.filter((name) => /^\d{4}-\d{2}\.csv$/.test(name))
		.sort()
		.flatMap((name) => parseTelemetryCsv(readFileSync(join(root, name), 'utf8')));
}

/** Rows built to carry the shape a ledger can be plausibly wrong about.
 *
 * This file used to read every published shard, on the argument that a made-up
 * ledger has whatever shape the test wanted while the real one has eleven
 * causes and a 529-to-1 spread. Both halves of that were true and neither was a
 * reason to read the archive: the awkward shape is a thing to BUILD, and a
 * built one also carries cases the archive has never produced - a source
 * sitting exactly on the cap, an article that failed twice in one day - at one
 * parse instead of one per published month (`CLAUDE.md` Rule #12). It also
 * removed the guard that used to ask whether the corpus still held enough
 * failures to prove anything, which was a question about the news.
 *
 * Eleven causes, counts running 529 down to 1. Fourteen sources against a cap
 * of ten. One article failing twice on one day, under two runs.
 */
function builtRows(): TelemetryRow[] {
	const COUNTS = [529, 97, 61, 40, 25, 16, 10, 6, 4, 2, 1];
	const STAGES = ['fetch', 'extract', 'summarize'];
	const rows: TelemetryRow[] = [];
	const row = (over: Partial<TelemetryRow> & { item_id: string }): TelemetryRow => ({
		date: '2026-08-20',
		run_id: '1',
		vertical: 'world',
		source_id: 'src-00',
		stage: 'fetch',
		outcome: 'failed',
		code: 'unreachable',
		source_words: null,
		summary_words: null,
		source_words_before_cap: null,
		...over
	});

	let made = 0;
	COUNTS.forEach((count, cause) => {
		for (let index = 0; index < count; index += 1) {
			made += 1;
			rows.push(
				row({
					date: `2026-08-${String(20 + (made % 5)).padStart(2, '0')}`,
					item_id: `world-${String(made).padStart(10, '0')}`,
					source_id: `src-${String(made % 14).padStart(2, '0')}`,
					stage: STAGES[cause % STAGES.length],
					code: `code-${String(cause).padStart(2, '0')}`
				})
			);
		}
	});

	// The dedupe case: one article, one day, two runs. A source's losses are
	// articles; the rows under them are one per stage per run.
	rows.push(row({ item_id: 'world-0000000001', run_id: '2', date: '2026-08-21' }));
	// A row that succeeded, so `failed` is a filter rather than a row count.
	rows.push(row({ item_id: 'world-9999999999', outcome: 'ok', code: '' }));
	return rows;
}

function wholeSpan(rows: TelemetryRow[]): TimeWindow {
	const dates = datesIn(rows);
	return { start: dates[0], end: dates[dates.length - 1] };
}

test.describe('the failure ledger', () => {
	const rows = builtRows();

	test('the counts sum to the failed rows in the window', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const failed = failedRows(rows, window, null);

		const summed = ledger.causes.reduce((total, cause) => total + cause.count, 0);
		expect(summed, 'the ledger and the list disagree about how many items failed').toBe(
			failed.length
		);
		expect(ledger.failed).toBe(failed.length);
	});

	test('selecting each cause in turn partitions the list, with no overlap and no remainder', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const failed = failedRows(rows, window, null);

		// Object identity, not a composed key: two runs write byte-identical rows
		// for one item, and a string key would call that pair an overlap.
		const covered = new Set<TelemetryRow>();
		for (const cause of ledger.causes) {
			const slice = failedRows(rows, window, null, cause.key);
			expect(slice.length, `the ledger's count for ${cause.key} is not its rows`).toBe(
				cause.count
			);
			for (const row of slice) {
				expect(covered.has(row), `a row falls under two causes at ${cause.key}`).toBe(false);
				covered.add(row);
				expect(causeKey(row)).toBe(cause.key);
			}
		}

		expect(covered.size, 'the causes cover fewer rows than the list holds').toBe(failed.length);
		const missed = failed.filter((row) => !covered.has(row));
		expect(missed, 'these failed rows belong to no cause').toEqual([]);
	});

	test('a cause spans no more days than the window, and its trend adds up to its count', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		for (const cause of ledger.causes) {
			const daily = cause.daily.reduce((total, n) => total + n, 0);
			expect(daily, `${cause.key} draws a trend that is not its own count`).toBe(cause.count);
			expect(cause.lastAgo).toBeGreaterThanOrEqual(0);
			expect(cause.last >= window.start && cause.last <= window.end).toBe(true);
		}
	});

	test('breadth is read against the sources the window saw, not against the failures', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const sources = new Set(
			rows
				.filter((row) => row.date >= window.start && row.date <= window.end)
				.map((row) => row.source_id)
				.filter(Boolean)
		);
		expect(ledger.sourcesSeen).toBe(sources.size);
		// The distinction the column exists for: one source changing its markup
		// and the extractor being broken carry the same count and different
		// breadth, so no cause may claim more sources than the window holds.
		for (const cause of ledger.causes) {
			expect(cause.sources).toBeGreaterThan(0);
			expect(cause.sources).toBeLessThanOrEqual(ledger.sourcesSeen);
		}
	});

	test('the ledger is uncapped, and the cap is the list that draws it', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const entries: Rankable<RankedDisplay>[] = ledger.causes.map((cause) => ({
			key: cause.key,
			value: cause.count,
			row: { label: cause.code, value: `${cause.count}` }
		}));

		const capped = rank(entries, 3);
		expect(capped.rows.length).toBe(3);
		expect(capped.hidden).toBe(ledger.causes.length - 3);
		// Uncapped at the source, so the sum above cannot quietly become the sum
		// of whatever the display kept.
		expect(capped.hidden + capped.rows.length).toBe(ledger.causes.length);
		expect(capped.rows.map((row) => row.value)).toEqual(
			[...capped.rows.map((row) => row.value)].sort((a, b) => b - a)
		);
	});

	test('every drawn row has a key of its own, under every cause and under none', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const lists = [
			failedRows(rows, window, null),
			...ledger.causes.map((cause) => failedRows(rows, window, null, cause.key))
		];

		// A repeated key throws inside a keyed each, the update is abandoned
		// part-way, and the rows already on screen stay - so a filter looks like
		// it let foreign causes through. Measured 2026-08-30 against the
		// committed projection before the index was in the key: selecting
		// extract/paywalled left fetch/http_client_error rows in the table.
		for (const list of lists) {
			const keys = new Set(list.map((row, index) => failureRowKey(row, index)));
			expect(keys.size).toBe(list.length);
		}

		// And the reason the index is needed rather than assumed. Run and item
		// together used to repeat in this projection, because two workflow runs
		// computed one run id and the union merge kept both appends. That is
		// fixed at the writer and the committed file was settled with it, so the
		// pair no longer repeats here - which is exactly why the claim is proved
		// against two rows built to collide rather than against today's data. A
		// browser reads whatever is served, including a shard written before the
		// fix.
		const colliding = failedRows(rows, window, null).slice(0, 1);
		expect(colliding.length, 'the projection holds no failed row to build on').toBe(1);
		const twice = [colliding[0], { ...colliding[0] }];
		expect(new Set(twice.map((row) => `${row.run_id}-${row.item_id}`)).size).toBe(1);
		expect(new Set(twice.map((row, index) => failureRowKey(row, index))).size).toBe(2);
	});

	test('a window with no row at all is not a window with no failure', () => {
		const empty = failureLedger(rows, { start: '1999-01-01', end: '1999-01-31' });
		expect(empty.rows).toBe(0);
		expect(empty.causes).toEqual([]);
		expect(empty.failed).toBe(0);
	});
});

/** One source's articles lost, computed here and owing nothing to the module.
 *
 * Dedupe is `date` plus `item_id`, the rule `compressionView` reads the same
 * ledger by, so an article a second run failed again on the same day is one
 * article and not two.
 */
interface HandLoss {
	key: string;
	lost: number;
	articles: number;
}

function lossesByHand(rows: TelemetryRow[], window: TimeWindow): HandLoss[] {
	const lost = new Map<string, Set<string>>();
	const seen = new Map<string, Set<string>>();
	for (const row of rows) {
		if (row.date < window.start || row.date > window.end) continue;
		if (!row.source_id) continue;
		// A separator no id can hold, so `a-1` + `b` and `a` + `1-b` stay apart.
		const article = `${row.date}\u0000${row.item_id}`;
		seen.set(row.source_id, (seen.get(row.source_id) ?? new Set<string>()).add(article));
		if (row.outcome !== 'failed') continue;
		lost.set(row.source_id, (lost.get(row.source_id) ?? new Set<string>()).add(article));
	}
	return [...lost].map(([key, articles]) => ({
		key,
		lost: articles.size,
		articles: (seen.get(key) as Set<string>).size
	}));
}

/** What the component builds the ranking from, restated once. */
function sourceEntries(rows: TelemetryRow[], window: TimeWindow): Rankable<RankedDisplay>[] {
	return sourceLosses(rows, window).sources.map((source) => ({
		key: source.key,
		value: source.lost,
		tiebreak: -source.lastAgo,
		row: { label: source.key, value: `${source.lost} of ${source.articles} articles` }
	}));
}

test.describe('THE ORACLE: sources ranked by the articles their failures cost', () => {
	const rows = builtRows();

	test('the rows carry more sources than the cap draws', () => {
		// Everything below passes trivially on a ledger the cap never bites, so
		// the built shape is asserted before anything leans on it.
		const window = wholeSpan(rows);
		const byHand = lossesByHand(rows, window);
		expect(byHand.length, 'no source carries a loss').toBeGreaterThan(SOURCE_ROWS);
		expect(
			byHand.reduce((total, source) => total + source.lost, 0),
			'no article was lost, so a ranking of losses says nothing'
		).toBeGreaterThan(0);
	});

	test('the ledger names the same sources and the same losses as a hand count', () => {
		const window = wholeSpan(rows);
		const measured = sourceLosses(rows, window);
		const byHand = new Map(lossesByHand(rows, window).map((source) => [source.key, source]));

		expect(new Set(measured.sources.map((source) => source.key))).toEqual(
			new Set(byHand.keys())
		);
		for (const source of measured.sources) {
			const hand = byHand.get(source.key) as HandLoss;
			expect(source.lost, `${source.key} lost a different number of articles`).toBe(hand.lost);
			expect(source.articles, `${source.key} saw a different number of articles`).toBe(
				hand.articles
			);
			// The denominator is the point of the second number: a source cannot
			// lose more articles than the window saw from it.
			expect(source.lost).toBeLessThanOrEqual(source.articles);
			expect(source.causes).toBeGreaterThan(0);
			// The cause is named only while naming it is a fact. Ten rows each
			// printing `1 cause` is a column that says nothing.
			expect(source.cause === null, `${source.key} names a cause it does not have`).toBe(
				source.causes !== 1
			);
			if (source.cause !== null) {
				const seen = new Set(
					failedRows(rows, window, null, null, source.key).map((row) => causeKey(row))
				);
				expect(seen).toEqual(new Set([source.cause]));
			}
		}
		expect(measured.lost).toBe(
			[...byHand.values()].reduce((total, source) => total + source.lost, 0)
		);
	});

	test('an article a second run failed again on the same day is one article', () => {
		// The dedupe rule, proved on two rows built to collide rather than on
		// whatever the committed ledger happens to hold today.
		const window = { start: '2026-08-01', end: '2026-08-01' };
		const row: TelemetryRow = {
			date: '2026-08-01',
			run_id: '2026-08-01-1',
			item_id: 'ai-1234567890',
			vertical: 'ai',
			source_id: 'a-wire',
			stage: 'fetch',
			outcome: 'failed',
			code: 'http_client_error',
			source_words: null,
			summary_words: null,
			source_words_before_cap: null,
			fetch_ms: null,
			extract_ms: null,
			summarize_ms: null,
			prefill_ms: null,
			decode_ms: null,
			input_tokens: null,
			output_tokens: null,
			cached_tokens: null
		};
		const twice = [row, { ...row, run_id: '2026-08-01-2' }];
		expect(failedRows(twice, window, null)).toHaveLength(2);
		expect(sourceLosses(twice, window).sources[0].lost).toBe(1);
		expect(sourceLosses(twice, window).lost).toBe(1);
	});

	test('the drawn rows are the top of the ranking, in that order', () => {
		const window = wholeSpan(rows);
		const drawn = rank(sourceEntries(rows, window), SOURCE_ROWS);
		const byHand = [...lossesByHand(rows, window)].sort(
			(a, b) => b.lost - a.lost || a.key.localeCompare(b.key)
		);

		expect(drawn.rows).toHaveLength(SOURCE_ROWS);
		// Order first, then the magnitudes: a list that holds the right names in
		// the wrong order draws a plausible and wrong picture.
		for (const [index, row] of drawn.rows.entries()) {
			expect(row.value, `row ${index} is not the ${index + 1}th largest loss`).toBe(
				byHand[index].lost
			);
		}
		expect(drawn.rows.map((row) => row.value)).toEqual(
			[...drawn.rows.map((row) => row.value)].sort((a, b) => b - a)
		);
		expect(drawn.max).toBe(byHand[0].lost);
	});

	test('the tail sentence counts and sums exactly what the cap left out', () => {
		const window = wholeSpan(rows);
		const drawn = rank(sourceEntries(rows, window), SOURCE_ROWS);
		const byHand = [...lossesByHand(rows, window)].sort(
			(a, b) => b.lost - a.lost || a.key.localeCompare(b.key)
		);
		const rest = byHand.slice(SOURCE_ROWS);

		expect(drawn.hidden).toBe(rest.length);
		expect(drawn.hiddenValue).toBe(rest.reduce((total, source) => total + source.lost, 0));
		// Nothing falls between the drawn rows and the tail.
		expect(drawn.rows.length + drawn.hidden).toBe(byHand.length);

		const sentence = tailSentence(drawn, {
			one: 'source',
			many: 'sources',
			unitOne: 'lost article',
			unitMany: 'lost articles'
		});
		expect(sentence).toBe(
			`${drawn.hidden} more sources had ${drawn.hiddenValue} lost articles between them.`
		);
	});

	test('selecting a source narrows the rows to exactly the matching set', () => {
		const window = wholeSpan(rows);
		const measured = sourceLosses(rows, window);
		const failed = failedRows(rows, window, null);

		// Object identity, not a composed key: two runs write byte-identical rows
		// for one item, and a string key would call that pair an overlap.
		const covered = new Set<TelemetryRow>();
		for (const source of measured.sources) {
			const slice = failedRows(rows, window, null, null, source.key);
			expect(slice.length, `${source.key} draws no row for a loss it claims`).toBeGreaterThan(0);
			// The rows are per stage per run; the ranking counts articles, so the
			// row count is never smaller than the article count.
			expect(new Set(slice.map((row) => `${row.date}\u0000${row.item_id}`)).size).toBe(
				source.lost
			);
			for (const row of slice) {
				expect(row.source_id, `a foreign source is in ${source.key}'s rows`).toBe(source.key);
				expect(covered.has(row), `a row falls under two sources at ${source.key}`).toBe(false);
				covered.add(row);
			}
		}

		// Every failed row with a source is under exactly one of them.
		const named = failed.filter((row) => row.source_id);
		expect(covered.size, 'the sources cover fewer rows than the list holds').toBe(named.length);
	});

	test('a code chip and a source narrow together, not instead of each other', () => {
		const window = wholeSpan(rows);
		const measured = sourceLosses(rows, window);
		const source = measured.sources[0].key;
		const code = failedRows(rows, window, null, null, source)[0].code;

		const both = failedRows(rows, window, code, null, source);
		expect(both.length).toBeGreaterThan(0);
		for (const row of both) {
			expect(row.source_id).toBe(source);
			expect(row.code).toBe(code);
		}
		expect(both.length).toBeLessThanOrEqual(
			failedRows(rows, window, null, null, source).length
		);
	});

	test('a window with no row at all is not a window with no loss', () => {
		const empty = sourceLosses(rows, { start: '1999-01-01', end: '1999-01-31' });
		expect(empty.rows).toBe(0);
		expect(empty.sources).toEqual([]);
		expect(empty.lost).toBe(0);
	});
});

test.describe('the failure section on the page', () => {
	test('the two rankings sit above the rows they explain', async ({ page }) => {
		await page.goto('/console/');

		const order = await page.evaluate(() => {
			const seen = ['[data-failure-ledger]', '[data-source-losses]', '[data-failure-list]'].map(
				(selector) => document.querySelector(selector)
			);
			if (seen.some((node) => node === null)) return null;
			const nodes = seen as Element[];
			// 4 is DOCUMENT_POSITION_FOLLOWING: each one comes after the last.
			return nodes.every(
				(node, index) => index === 0 || (nodes[index - 1].compareDocumentPosition(node) & 4) > 0
			)
				? 'ranked-first'
				: 'out-of-order';
		});
		expect(order, 'the failure section is missing one of its three parts').toBe('ranked-first');
	});

	test('the item rows start shut, and the summary says how many are behind it', async ({
		page
	}) => {
		await page.goto('/console/');

		// The rows are the only child of this page that can outgrow the screen.
		// Uncapped and open they measured 7,824px against 800 rows and put the
		// chart above them at document y=9,105.
		const rows = page.locator('details[data-failure-rows]');
		await expect(rows, 'the item rows are not behind a disclosure').toHaveCount(1);
		expect(await rows.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
		await expect(page.locator('[data-failure-toggle]')).toContainText('failed item');
	});

	test('the three empty states say different things', async ({ page }) => {
		await page.goto('/console/');

		const ledger = page.locator('[data-failure-ledger]');
		const sources = page.locator('[data-source-losses]');
		await expect(ledger, 'the ledger must be on the page in every state').toHaveCount(1);
		await expect(sources, 'the source ranking must be on the page in every state').toHaveCount(1);

		// The canary fixture records no failure, so this is both rankings
		// answering no. A renamed attribute fails here rather than switching the
		// test off.
		const canary = shardRows(CANARY_TELEMETRY);
		const start = await page.locator('[data-viewport-control]').getAttribute('data-window-start');
		const end = await page.locator('[data-viewport-control]').getAttribute('data-window-end');
		expect(start, 'the viewport publishes no window').not.toBeNull();
		const window = { start: start as string, end: end as string };
		const failed = failedRows(canary, window, null).length;

		if (failed === 0) {
			await expect(sources.locator('[data-ranked="none"]')).toHaveText(
				'No source lost an article in this window.'
			);
		} else {
			await expect(sources.locator('[data-ranked="rows"]')).toHaveCount(1);
		}

		// Pan back past every row the fixture holds. Now neither ranking can
		// answer, and that is a different sentence from answering no.
		const viewport = page.locator('[data-viewport-control]');
		await viewport.focus();
		for (let index = 0; index < 8; index += 1) {
			await page.keyboard.press('ArrowLeft');
		}
		await expect(viewport).toContainText('0 rows in view');
		await expect(sources.locator('[data-ranked="unmeasured"]')).toHaveText(
			'Nothing was recorded in this window.'
		);
	});

	test('the two empty states say different things', async ({ page }) => {
		await page.goto('/console/');

		const ledger = page.locator('[data-failure-ledger]');
		await expect(ledger, 'the ledger must be on the page in every state').toHaveCount(1);

		// The canary fixture records no failure, so this is the ledger answering
		// no. A renamed attribute fails here rather than switching the test off.
		const canary = shardRows(CANARY_TELEMETRY);
		const start = await page.locator('[data-viewport-control]').getAttribute('data-window-start');
		const end = await page.locator('[data-viewport-control]').getAttribute('data-window-end');
		expect(start, 'the viewport publishes no window').not.toBeNull();
		const window = { start: start as string, end: end as string };
		const failed = failedRows(canary, window, null).length;

		if (failed === 0) {
			await expect(ledger.locator('[data-ranked="none"]')).toHaveText(
				'No item failed in this window.'
			);
		} else {
			await expect(ledger.locator('[data-ranked="rows"]')).toHaveCount(1);
		}

		// Pan back past every row the fixture holds. Now the ledger cannot answer,
		// and that is a different sentence from answering no.
		const viewport = page.locator('[data-viewport-control]');
		await viewport.focus();
		for (let index = 0; index < 8; index += 1) {
			await page.keyboard.press('ArrowLeft');
		}
		await expect(viewport).toContainText('0 rows in view');
		await expect(ledger.locator('[data-ranked="unmeasured"]')).toHaveText(
			'Nothing was recorded in this window.'
		);
	});

	test('the rows carry the item id without spending a column on it', async ({ page }) => {
		await page.goto('/console/');

		const canary = shardRows(CANARY_TELEMETRY);
		const start = await page.locator('[data-viewport-control]').getAttribute('data-window-start');
		const end = await page.locator('[data-viewport-control]').getAttribute('data-window-end');
		const window = { start: start as string, end: end as string };
		const failed = failedRows(canary, window, null);

		// Both arms assert. Which one runs is decided by the fixture, never by a
		// locator that returns zero because an attribute was renamed.
		if (failed.length === 0) {
			await expect(page.locator('[data-failure-list="empty"]')).toHaveText(
				'No failed item is in this window.'
			);
			return;
		}

		const headers = await page
			.locator('[data-failure-list="rows"] thead th')
			.allTextContents();
		expect(headers.map((text) => text.trim())).toEqual(['Day', 'Source', 'Stage', 'Code']);

		const first = page.locator('[data-failure-list="rows"] tbody tr').first();
		await expect(first).toHaveAttribute('title', failed[0].item_id);
	});
});
