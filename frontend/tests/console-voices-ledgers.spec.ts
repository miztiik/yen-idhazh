/** Voices reduces native recorded slices, then draws those same records on its real route. */
import { expect, test as routeTest } from './support/door-page';
import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { feedHealthRows } from '../src/lib/server/ledger-rows';
import { windowRange } from '../src/lib/console/queries/window';
import { feedsFailedQuery, fetchTimeQuery, sourceCutsQuery, whyChosenQuery, watchlistQuery } from '../src/lib/console/queries/voices';
import { fetchTime } from '../src/lib/console/voices/fetch-time';
import { whyChosen } from '../src/lib/console/voices/why-chosen';
import { watchlist } from '../src/lib/console/voices/watchlist';
import { sourceCuts } from '../src/lib/console/voices/source-cuts';
import { feedInput, feedsFailed } from '../src/lib/console/voices/feeds-failed';
import { publishVoicesFixture, VOICES_ROWS } from './support/panel-drivers/voices';
import { buildRows, serveToPage } from './support/ledger-lifecycle';
import { judgementRoute } from './support/judgement-route';
import { readPanel, judgeSettled } from './support/panel-gates';
import { consolePanels } from './support/console-panels';

type PrivateRoute = Awaited<ReturnType<typeof judgementRoute>>;
const test = routeTest.extend<object, { populated: PrivateRoute; feedOnly: PrivateRoute }>({
	populated: [async ({}, use, info) => {
		const route = await judgementRoute(join(info.project.outputDir, 'voices-populated', String(info.workerIndex)), {
			voices: publishVoicesFixture
		});
		try { await use(route); } finally { await route.close(); }
	}, { scope: 'worker', timeout: 150_000 }],
	feedOnly: [async ({}, use, info) => {
		const route = await judgementRoute(join(info.project.outputDir, 'voices-feed-only', String(info.workerIndex)), {
			voices: async (state, publicRoot) => {
				await publishVoicesFixture(state, publicRoot);
				rmSync(join(state, 'compact', 'item-health'), { recursive: true });
			}
		});
		try { await use(route); } finally { await route.close(); }
	}, { scope: 'worker', timeout: 150_000 }]
});

const RANGE = windowRange(90, '2030-06-15', '2030-06-14');
let root: string;
test.beforeAll(async ({}, info) => {
	root = info.outputPath('recorded-voices');
	mkdirSync(root, { recursive: true });
	await publishVoicesFixture(root);
});
test('native clocks use common evidence-bearing means and never zero-fill a missing clock', async () => {
	const answer = await sliceFromDisk(root, 'item-health', { columns: fetchTimeQuery.columns, from: RANGE.from, to: RANGE.to });
	expect(answer.state).toBe('ok');
	if (answer.state !== 'ok') throw new Error('The actual clock Parquet did not answer');
	const view = fetchTime(answer.rows, 10);
	expect(view.excluded).toBe(4);
	expect(view.summaries.map((row) => [row.id, row.total, row.count])).toEqual([['beta', 3000, 1], ['alpha', 1500, 2]]);
	expect(view.summaries[0].segments).toBeUndefined();
	expect(view.summaries[0].means[3]).toBeNull();
	expect(view.summaries[1].means).toEqual([150, 100, 150, 100]);
	expect(view.summaries[1].rest).toBe(1000);
	expect(view.summaries[1].segments!.reduce((sum, part) => sum + part.value, 0)).toBe(1500);
	expect(view.summaries[1].retries).toBe(1);
	const overlap = fetchTime([{ source_id: 'bad', fetch_ms: 10, robots_ms: 9, retry_total_ms: 2, fetch_connect_ms: 1, fetch_ttfb_ms: 1, retry_count: 0 }], 10);
	expect(overlap.summaries[0].overlap).toBe(1);
	expect(overlap.summaries[0].segments).toBeUndefined();
});
test("native newest-day selection uses each item's numeric newest run and an honest short threshold", async () => {
	const answer = await sliceFromDisk(root, 'item-health', { columns: whyChosenQuery.columns, from: '2030-06-15', to: '2030-06-15' });
	expect(answer.state).toBe('ok');
	if (answer.state !== 'ok') throw new Error('The actual selection Parquet did not answer');
	const view = whyChosen(answer.rows, 20);
	expect(view.count).toBe(2);
	expect(view.drawn).toBe(2);
	expect(view.geometry?.rows.map((row) => [row.label, row.total])).toEqual([['a', 1.5], ['b', 1]]);
	expect(view.geometry?.rows[0].segments.map((part) => part.label)).toEqual(['Authority', 'Recency', 'Lens', 'Watchlist']);
	expect(view.geometry?.key.map((part) => [part.label, part.token])).toEqual([
		['Authority', '--chart-1'], ['Recency', '--chart-2'], ['Lens', '--chart-4'], ['Watchlist', '--chart-5'], ['Carriage', '--chart-7']
	]);
	expect(view.records).toHaveLength(2);
	for (const [index, record] of view.records.entries()) {
		const score = Number(record.facts.find((fact) => fact.label === 'Selection score')?.value);
		expect(view.geometry!.rows[index].total).toBeCloseTo(score, 6);
		expect(record.facts.filter((fact) => ['Authority', 'Recency', 'Lens', 'Watchlist', 'Carriage'].includes(fact.label))).toHaveLength(5);
	}
	expect(view.records[0].facts.find((fact) => fact.label === 'Newest run')?.value).toBe('2030-06-15-10');
	expect(view.finding).toContain('cannot be established from 2 candidates');
	const wrong = whyChosen([{ ...VOICES_ROWS[5], selection_score: 2 }], 20);
	expect(wrong.drawn).toBe(0);
	expect(wrong.incomplete).toBe(1);
});
test('native cuts keep unknown lengths apart from zero and count URL keys once', async () => {
	const answer = await sliceFromDisk(root, 'item-health', { columns: sourceCutsQuery.columns, from: RANGE.from, to: RANGE.to });
	expect(answer.state).toBe('ok');
	if (answer.state !== 'ok') throw new Error('The actual length Parquet did not answer');
	const view = sourceCuts(answer.rows, RANGE, 10);
	expect(view.rows.map((row) => [row.sourceId, row.cut, row.articles])).toEqual([['alpha', 1, 1], ['beta', 1, 2]]);
	expect(view.rows[0].lengths).toEqual({ min: 4000, median: 4000, max: 4000 });
	expect(view.unknown).toBe(1);
	expect(view.articles).toBe(3);
	expect(view.cost).toEqual({ n: 2, median: 3000, max: 3000 });
});
test('native watchlist counts distinct addresses, not rerun rows, and separates unknown front-page evidence', async () => {
	const answer = await sliceFromDisk(root, 'item-health', { columns: watchlistQuery.columns, from: RANGE.from, to: RANGE.to });
	expect(answer.state).toBe('ok');
	if (answer.state !== 'ok') throw new Error('The actual watchlist Parquet did not answer');
	const view = watchlist(answer.rows, RANGE, 1, 3);
	expect(view.total).toBe(2);
	expect(view.fired).toBe(2);
	expect(view.unknownFront).toBe(1);
	expect(view.geometry?.tiles.map((tile) => [tile.date, tile.state, tile.reading])).toEqual([['2030-06-14', 'fired', 2], ['2030-06-15', 'fired', 1]]);
	expect(view.records.columns).toEqual(['14 Jun 2030', '15 Jun 2030']);
	expect(view.records.events[0].map((line) => [line.label, line.value])).toEqual([
		['UTC day', '2030-06-14'], ['State', 'caught'], ['Catch', '2 distinct addresses'],
		['Front page', '1 recorded true; 1 unknown'], ['Unrecorded hit cells', '0']
	]);
	const absent = watchlist([{ date: '2030-06-15', url_key: 'old', watchlist_hit: null, on_front_page: null }], windowRange(1, '2030-06-15', '2030-06-15'), 1, 3);
	expect(absent.geometry).toBeNull();
	expect(absent.quiet).toBe(false);
	expect(absent.lede).toContain('unknown');
	const quiet = watchlist([{ date: '2030-06-15', url_key: 'old', watchlist_hit: false, on_front_page: false }], windowRange(1, '2030-06-15', '2030-06-15'), 1, 3);
	expect(quiet.quiet).toBe(true);
	const belowMark = watchlist([
		{ date: '2030-06-15', url_key: 'hit', watchlist_hit: true, on_front_page: false },
		{ date: '2030-06-15', url_key: 'hit', watchlist_hit: true, on_front_page: false },
		{ date: '2030-06-14', url_key: 'outside', watchlist_hit: true, on_front_page: true }
	], windowRange(1, '2030-06-15', '2030-06-15'), 2, 3);
	expect([belowMark.total, belowMark.caughtDays, belowMark.fired, belowMark.quiet]).toEqual([1, 1, 0, false]);
	expect(belowMark.lede).toBe('The watchlist caught 1 distinct articles on 1 of 1 days; 0 reached the front page.');
});
test('all five native selection parts add up and a capped newest-day cohort loses no candidate', async ({}, info) => {
	const state = info.outputPath('selection-cohort');
	const rows = [
		{ ...VOICES_ROWS[5], item_id: 'bonus', authority_score: 0.5, feed_weight: 0.5, recency_bonus: 0.5, lens_bonus: 0.2, watchlist_bonus: 0.2, carriage_step: 0.1, selection_score: 1.5 },
		{ ...VOICES_ROWS[6], item_id: 'standing', authority_score: 1, feed_weight: 1, recency_bonus: 0, selection_score: 1 }
	];
	await buildRows(state, 'item-health', [{ covers: RANGE.to, rows }]);
	const answer = await sliceFromDisk(state, 'item-health', { columns: whyChosenQuery.columns, from: RANGE.to, to: RANGE.to });
	if (answer.state !== 'ok') throw new Error('The actual candidate Parquet did not answer');
	const view = whyChosen(answer.rows, 1);
	expect([view.count, view.complete, view.drawn, view.hidden, view.incomplete]).toEqual([2, 2, 1, 1, 0]);
	expect(view.geometry!.rows.map((row) => [row.label, row.total])).toEqual([['bonus', 1.5]]);
	expect(view.geometry!.rows[0].segments.map((part) => [part.label, part.value, part.token])).toEqual([
		['Authority', 0.5, '--chart-1'], ['Recency', 0.5, '--chart-2'], ['Lens', 0.2, '--chart-4'], ['Watchlist', 0.2, '--chart-5'], ['Carriage', 0.1, '--chart-7']
	]);
	expect(view.geometry!.rows[0].segments.reduce((sum, part) => sum + part.value, 0)).toBeCloseTo(1.5, 6);
	expect(view.finding).toContain('the bonuses brought in 1 of the 1');
	expect(view.finding).toContain('Recency added most');
});
test('native 429 and network errors join real feed reads on the older observed row end', async () => {
	const answer = await sliceFromDisk(root, 'item-health', { columns: feedsFailedQuery.columns, from: RANGE.from, to: RANGE.to, where: feedsFailedQuery.where });
	expect(answer.state).toBe('ok');
	if (answer.state !== 'ok') throw new Error('The actual outcome Parquet did not answer');
	const feeds = feedInput(await feedHealthRows({ start: RANGE.from, end: RANGE.to }, root));
	const view = feedsFailed(feeds, answer.rows, RANGE, 10, 1, 3);
	expect(view.feedThrough).toBe('2030-06-15');
	expect(view.articleThrough).toBe('2030-06-14');
	expect(view.through).toBe('2030-06-14');
	expect(view.sources).toHaveLength(1);
	expect(view.sources[0].article?.tiles.map((tile) => tile.reading)).toEqual([2]);
	expect(view.sources[0].feedEnding).toBe('mostly transient, last 2030-06-14');
	expect(view.sources[0].ending).toBe('mostly rate limited, last 2030-06-14');
	const reading = view.sources[0].articleRecords.events[0].map((line) => line.value).join(' ');
	expect(reading).toContain('rate limited, failed, HTTP 429');
	expect(reading).toContain('network error, failed');
	expect(reading).toContain('2 failed of 2 recorded fetches');
	expect(reading).toContain('rate limited (HTTP 429) on 1 of 2 fetches');
	expect(reading).toContain('network error (status not recorded) on 1 of 2 fetches');
});
test('the real independently published route draws native failures and survives both themes at every approved width', async ({ page, populated: published }, info) => {
	{
		const errors: string[] = [];
		page.on('pageerror', (error) => errors.push(error.message));
		page.on('response', (response) => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
		for (const theme of ['light', 'dark']) for (const width of [390, 768, 1440]) {
			await page.setViewportSize({ width, height: 1000 });
			await page.addInitScript((value) => localStorage.setItem('idhazh:theme', value), theme);
			await page.goto(`${published.origin}console/voices/`);
			await expect(page.locator('[data-console-panels="voices"]')).toHaveAttribute('data-route-state', 'ok');
			await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
			await expect(page.locator('[data-console-panel-id]')).toHaveCount(8);
			const panel = page.locator('[data-console-panel-id="feeds-failed"]');
			await expect(panel).toContainText('HTTP 429');
			await expect(panel).toContainText('network error');
			await expect(panel.locator('[data-chart-name="articles-alpha"] [data-tile-state="fired"]')).toHaveCount(1);
			await expect(panel).toContainText('Feed results after 2030-06-14 wait for their article fetches');
			await expect(panel.locator('[data-tile-axis]')).toHaveCount(1);
			const colours = await panel.locator('[data-tile-state="fired"]').evaluateAll((tiles) => tiles.map((tile) => getComputedStyle(tile).backgroundColor));
			expect(colours).toHaveLength(2);
			expect(new Set(colours).size).toBe(1);
			const fetchColour = await panel.evaluate((node) => {
				const probe = document.createElement('span');
				probe.style.backgroundColor = 'var(--chart-1)';
				node.append(probe);
				const colour = getComputedStyle(probe).backgroundColor;
				probe.remove();
				return colour;
			});
			expect(fetchColour).not.toBe('rgba(0, 0, 0, 0)');
			expect(colours).toEqual([fetchColour, fetchColour]);
			for (const id of ['source-health', 'feeds-failed', 'fetch-time', 'retiring', 'source-cuts', 'ranking-discount', 'why-chosen', 'watchlist']) {
				const locator = page.locator(`[data-console-panel-id="${id}"]`);
				await locator.scrollIntoViewIfNeeded();
				for (const verdict of judgeSettled(await readPanel(locator), consolePanels().fillFloor)) expect(verdict.pass, `${width} ${theme}: ${verdict.says}`).toBe(true);
			}
			const timing = page.locator('[data-console-panel-id="fetch-time"]');
			const source = timing.locator('[data-ranked-row="alpha"]');
			await source.locator('[data-readout-at]').hover();
			await expect(timing.locator('[data-readout-subject]')).toHaveText('alpha');
			await source.locator('button').click();
			await expect(timing.locator('[data-readout-subject]')).toHaveText('alpha');
			await timing.locator('[data-readout-records]').focus();
			await page.keyboard.press('Escape');
			await expect(timing.locator('[data-readout-subject]')).toContainText('beta');
			await expect(timing).toContainText('not recorded for every fetch');
			expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
		}
		const context = await page.context().browser()!.newContext({ javaScriptEnabled: false });
		try {
			const noScript = await context.newPage();
			await noScript.goto(`${published.origin}console/voices/`);
			await expect(noScript.locator('[data-console-panels="voices"]')).toHaveAttribute('data-route-state', 'loading');
			const panel = noScript.locator('[data-console-panel-id="feeds-failed"]');
			const scriptlessNote = panel.locator('noscript > p').first();
			await expect(scriptlessNote).toBeVisible();
			await expect(scriptlessNote).toHaveText('Article fetches need JavaScript, so only feed results are drawn.');
			await expect(panel.locator('[data-chart-name="feed-alpha"] [data-tile-state="fired"]')).toHaveCount(2);
			await expect(panel.locator('[data-chart-name^="articles-"]')).toHaveCount(0);
			await expect(panel.locator('.panel-body [data-panel-state="loading"]')).toHaveCount(1);
		} finally { await context.close(); }
		const zeroRoot = info.outputPath('zero-and-partial');
		await buildRows(zeroRoot, 'item-health', [{ covers: RANGE.to, rows: [{
			...VOICES_ROWS[5], authority_score: 0, tier_score: 0, selection_score: 0,
			recency_bonus: 0, lens_bonus: 0, watchlist_bonus: 0, carriage_step: 0,
			watchlist_hit: null, on_front_page: null
		}] }]);
		await serveToPage(page.context(), zeroRoot, 'item-health');
		await page.goto(`${published.origin}console/voices/`);
		await expect(page.locator('[data-console-panels="voices"]')).toHaveAttribute('data-route-state', 'ok');
		const chosen = page.locator('[data-console-panel-id="why-chosen"]');
		await expect(chosen).toContainText('Every recorded selection part is zero');
		await expect(chosen).toContainText('Selection score');
		await expect(chosen.locator('dd')).toHaveCount(8);
		await expect(chosen.locator('[data-empty-state="quiet"]')).toHaveCount(0);
		const catchPanel = page.locator('[data-console-panel-id="watchlist"]');
		await expect(catchPanel).toContainText('Watchlist answers were not recorded completely');
		await expect(catchPanel.locator('[data-tile-state], [data-empty-state="quiet"]')).toHaveCount(0);
		expect(errors).toEqual([]);
	}
});
test('unknown words, zero lengths and incomplete newest-run scores do not invent evidence', () => {
	const range = windowRange(2, '2030-06-15', '2030-06-14');
	const cuts = sourceCuts([
		{ date: range.to, source_id: 'zero', url_key: 'zero', source_words_before_cap: 0, source_words: 0 },
		{ date: range.to, source_id: 'zero', url_key: 'cut', source_words_before_cap: 100, source_words: 0 }
	], range, 10);
	expect(cuts.rows[0].lengths).toEqual({ min: 100, median: 100, max: 100 });
	expect(cuts.rows[0].articles).toBe(2);
	expect(cuts.zeroLengths).toBe(1);
	expect(cuts.zeroCaps).toBe(1);
	expect(cuts.caps).toEqual([]);
	const newest = whyChosen([
		{ ...VOICES_ROWS[5], selection_score: null, authority_score: null },
		VOICES_ROWS[4]
	], 1);
	expect(newest.drawn).toBe(0);
	expect(newest.incomplete).toBe(1);
	const repeatedStage = whyChosen([{ ...VOICES_ROWS[5], selection_score: null }, VOICES_ROWS[5]], 1);
	expect(repeatedStage.drawn).toBe(1);
	const partial = whyChosen([VOICES_ROWS[5], { ...VOICES_ROWS[6], selection_score: null }], 1);
	expect(partial.finding).toContain('cannot be established');
	const unknownIdentity = whyChosen([VOICES_ROWS[5], { ...VOICES_ROWS[6], item_id: null }], 1);
	expect(unknownIdentity.unknownIdentity).toBe(1);
	expect(unknownIdentity.finding).toContain('cannot be established');
	const capped = whyChosen([VOICES_ROWS[5], VOICES_ROWS[6], { ...VOICES_ROWS[4], date: '2030-06-14', item_id: 'older-day' }], 1);
	expect([capped.count, capped.complete, capped.drawn, capped.hidden, capped.incomplete]).toEqual([2, 2, 1, 1, 0]);
	const unknownFactors = whyChosen([{ ...VOICES_ROWS[5], feed_reliability: null }], 1);
	expect(unknownFactors.records[0].facts.find((fact) => fact.label === 'Authority')?.value).toContain('multiplication cannot be checked');
	const feed = { results: [], read: { state: 'read' as const, through: range.to, first: range.from, lastRows: null, lostDays: [], setAside: {} } };
	const errors = feedsFailed(feed, [{ date: range.to, source_id: 'unknown', code: 'network_error', outcome: 'failed', http_status: null, source_form: null, tier: null }], range, 10, 1, 3);
	expect(errors.noCommon).toBe(true);
	expect(errors.lede).toContain('no common observed');
});
test('combined failures include a clean feed with a failed article without changing its feed partition', () => {
	const range = windowRange(2, '2030-06-15', '2030-06-14');
	const input = {
		results: [{ date: range.to, runId: `${range.to}-1`, feedId: 'clean-feed', checkedAt: `${range.to}T12:00:00Z`, outcome: 'ok', status: 200, items: 4, detail: '' }],
		read: { state: 'read' as const, through: range.to, first: range.from, lastRows: null, lostDays: [], setAside: {} }
	};
	const view = feedsFailed(input, [
		{ date: range.from, source_id: 'clean-feed', code: 'network_error', outcome: 'failed' },
		{ date: range.to, source_id: 'clean-feed', code: 'ok', outcome: 'ok' }
	], range, 10, 1, 3);
	expect(view.sources.map((source) => source.sourceId)).toEqual(['clean-feed']);
	expect(view.feedRecord.clean).toEqual(['clean-feed']);
	expect(view.feedRecord.failed).toBe(0);
	expect(view.sources[0].feed?.tiles.map((tile) => tile.state)).toEqual(['absent', 'quiet']);
	expect(view.sources[0].article?.tiles.map((tile) => tile.state)).toEqual(['fired', 'quiet']);
	expect(view.sources[0].fired).toBe(1);
});
test('absent and lost article data retain useful real feed evidence without calling it an article answer', async ({ page, feedOnly: published }) => {
	{
		await page.goto(`${published.origin}console/voices/`);
		await expect(page.locator('[data-console-panels="voices"]')).toHaveAttribute('data-route-state', 'missing');
		const panel = page.locator('[data-console-panel-id="feeds-failed"]');
		await expect(panel).toContainText('the feed record alone is shown');
		await expect(panel.locator('[data-chart-name="feed-alpha"] [data-tile-state="fired"]')).toHaveCount(2);
		await expect(panel.locator('[data-chart-name^="articles-"]')).toHaveCount(0);
		await expect(panel).toContainText('1 answered on every day');
		await expect(panel).not.toContainText('Every feed and article fetch answered');
		const siteState = join(published.staticRoot, 'state');
		await buildRows(siteState, 'item-health', ['2030-06-14', '2030-06-15'].map((covers) => ({
			covers, rows: VOICES_ROWS.filter((row) => row.date === covers)
		})));
		rmSync(join(siteState, 'compact', 'item-health', 'daily', '2030', '06', '14.parquet'));
		await page.reload();
		await expect(page.locator('[data-console-panels="voices"]')).toHaveAttribute('data-route-state', 'unreachable');
		await expect(panel).toContainText('Article fetches did not arrive, so only feed results are drawn.');
		await expect(panel.locator('[data-chart-name="feed-alpha"] [data-tile-state="fired"]')).toHaveCount(2);
		await expect(panel.locator('[data-chart-name^="articles-"]')).toHaveCount(0);
		await expect(panel).toContainText('1 answered on every day');
		await expect(panel).not.toContainText('Every feed and article fetch answered');
	}
});
