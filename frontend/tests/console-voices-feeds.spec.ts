import { expect, test, type Page } from './support/door-page';
import { BY_ROUTE } from './support/console-expect/console';
import { routeHref } from './support/console-window/controls';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	chronological,
	failing,
	feedDays,
	resting,
	reliability,
	resultLabel,
	settled,
	streak,
	type FeedEvent,
	type FeedRecord,
	type FeedRead
} from '../src/lib/feed-health';
import { denseCellFor, ROW_STRIP_PX } from '../src/lib/charts/run-history';

/**
 * Pure producer feed rules remain pinned independently. The approved route
 * draws failed source-days rather than the old quarantine countdown: real
 * feed/article tiles retain nulls, state words, native colours and readouts.
 */

const repo = resolve(process.cwd(), '..');

// These assertions describe the complete feed-only population, not the
// combined list whose older common axis also admits failed articles.
test.describe('the real scriptless feed-only evidence', () => {
test.use({ javaScriptEnabled: false });

test('a listed feed failed at least once, and a feed the pipeline never read is not listed', async ({
	page
}) => {
	// Which reads count as failures is the quarantine rule's, pinned over rows written in
	// `console-voices-feeds.spec.ts`: an answer that carried nothing is one, and a polite
	// refusal is not. What the page owes is to list only feeds that failed, and never one it
	// names as unread.
	await page.goto(routeHref('voices'));

	const listed = await page.locator('[data-feed]').evaluateAll((rows) =>
		rows.map((row) => ({
			id: row.getAttribute('data-feed') ?? '',
			failures: Number(row.getAttribute('data-feed-failures'))
		}))
	);
	expect(listed.length, 'the page lists no failing feed, so this asserts nothing').toBeGreaterThan(0);
	for (const feed of listed) expect(feed.failures, `${feed.id} is listed and never failed`).toBeGreaterThan(0);
	const unread = await page
		.locator('[data-feed-ineligible-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-ineligible-name') ?? ''));
	expect(
		listed.map((feed) => feed.id).filter((id) => unread.includes(id)),
		'a feed the pipeline never read is listed as failing'
	).toEqual([]);
});

test('an answer that carried nothing is labelled as such, and never as ok', () => {
	// The ledger's own word for this read is `ok` - the fetch returned 200. Printed raw it sits on
	// the same row as the failure count and contradicts it, which is how a dead feed reads as a
	// healthy one.
	const read = (outcome: string, items: number) => ({ date: '2030-06-15', runId: '2030-06-15-1', outcome, items });
	expect(resultLabel(read('ok', 0))).toBe('answered with nothing');
	expect(resultLabel(read('ok', 4))).toBe('ok');
	// A feed that really did fail still reports the reason the ledger recorded.
	expect(resultLabel(read('permanent', 0))).toBe('permanent');
});

test('a feed still failing never reports its last result as ok', async ({ page }) => {
	// A streak runs to the newest read, so a feed that has one has not answered since: its last
	// result is a failure or a read that did not ask, never the word ok.
	await page.goto(routeHref('voices'));

	const rows = await page.locator('[data-feed]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			id: node.getAttribute('data-feed') ?? '',
			streak: Number(node.getAttribute('data-feed-streak')),
			result: (node.querySelector('[data-feed-result]')?.textContent ?? '').replace(/\s+/g, ' ').trim()
		}))
	);
	expect(rows.length, 'the page lists no failing feed, so this asserts nothing').toBeGreaterThan(0);
	for (const row of rows) {
		const label = row.result.split(' - ')[0];
		expect(label, `${row.id} prints no last result`).not.toBe('');
		if (row.streak > 0) expect(label, `${row.id} is still failing and reports ok`).not.toBe('ok');
	}
});

/** The independently declared cap the feed list must keep. */
const FEED_ROWS = BY_ROUTE.voices!.feedRows!;

/** The threshold under which this page prints counts and no rate. */
const MIN_ATTEMPTS = BY_ROUTE.voices!.minAttempts!;

/** The feed record the voices page prints in its headline, read off its own attributes.
 *
 * The record behind these numbers is pinned over rows written here (`a record too
 * shallow for a rate says so instead of printing one`, `a record with more failing
 * feeds than the list draws is counted whole`); what the page owes is to print the
 * numbers it publishes, and to list every feed they count.
 */
async function feedHeadline(page: Page) {
	const headline = page.locator('[data-feed-reliability]');
	await expect(headline, 'the feed section prints no denominator').toHaveCount(1);
	const count = async (name: string) => Number(await headline.getAttribute(name));
	return {
		headline,
		clean: await count('data-feed-clean'),
		checked: await count('data-feed-checked'),
		runs: await count('data-feed-runs')
	};
}

test('THE ORACLE: the feed headline carries its own denominator and span', async ({ page }) => {
	await page.goto(routeHref('voices'));

	const { headline, clean, checked, runs } = await feedHeadline(page);
	// Read against facts the page publishes, never against a locator count alone: a
	// renamed attribute would make every number zero and switch this off.
	expect(checked, 'the page checked no feed at all').toBeGreaterThan(0);
	expect(clean, 'the page has no clean feed to name').toBeGreaterThan(0);
	expect(clean, 'the page has no failing feed, so the list is empty').toBeLessThan(checked);
	await expect(page.locator('[data-feed-clean-name]')).toHaveCount(clean);
	// The numbers in the attributes are also the numbers in the type. An
	// attribute nobody reads and a sentence that says something else is exactly
	// the shape this section had before.
	await expect(headline).toContainText(`${clean} of ${checked} feeds`);
	await expect(headline).toContainText(String(runs));
	// The record's depth decides which of the two sentences prints.
	await expect(headline).toHaveAttribute(
		'data-feed-reliability',
		runs >= MIN_ATTEMPTS ? 'measured' : 'shallow'
	);
});

test('THE ORACLE: the disclosed names are exactly the feeds that did not fail', async ({
	page
}) => {
	await page.goto(routeHref('voices'));

	const { clean } = await feedHeadline(page);
	const named = await page
		.locator('[data-feed-clean-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-clean-name') ?? ''));

	// Every clean feed the headline counts, once each, in name order.
	expect(named).toHaveLength(clean);
	expect(new Set(named).size).toBe(named.length);
	expect(named).toEqual([...named].sort((a, b) => a.localeCompare(b)));
	// And the lists are disjoint: no feed is both clean and listed as broken, or
	// both clean and one the pipeline did not read.
	const listed = await page
		.locator('[data-feed]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-feed') ?? ''));
	expect(named.filter((feedId) => listed.includes(feedId))).toEqual([]);
	const unread = await page
		.locator('[data-feed-ineligible-name]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-ineligible-name') ?? ''));
	expect(named.filter((feedId) => unread.includes(feedId))).toEqual([]);
});

test('THE ORACLE: the failure list is capped and its tail counts the remainder', async ({
	page
}) => {
	await page.goto(routeHref('voices'));

	const { clean, checked } = await feedHeadline(page);
	// A feed the headline checked and did not count clean is a feed that failed.
	const broken = checked - clean;
	const table = page.locator('[data-feeds="table"]');
	const drawn = Number(await table.getAttribute('data-feeds-drawn'));
	const hidden = Number(await table.getAttribute('data-feeds-hidden'));

	// The identity that catches a cap dropping rows without counting them. It
	// holds at zero hidden, which is what makes it worth asserting on a fixture
	// the cap does not bite.
	expect(drawn + hidden, 'the cap lost a feed on the way past it').toBe(broken);
	expect(drawn).toBeLessThanOrEqual(FEED_ROWS);
	expect(drawn).toBe(Math.min(broken, FEED_ROWS));
	await expect(page.locator('[data-feed]')).toHaveCount(drawn);

	const tail = page.locator('[data-feeds-more]');
	if (hidden === 0) {
		// A sentence saying nothing is hidden is a line an operator reads and
		// learns nothing from.
		await expect(tail).toHaveCount(0);
	} else {
		await expect(tail).toContainText(`${hidden} more feed`);
	}
});

test('a record too shallow for a rate says so instead of printing one', () => {
	// The canary is deep enough, so the third state is driven here rather than
	// left to a sentence that never prints. Two runs deep, "did not fail" means
	// "did not fail twice", and the page has to say which it means.
	const shallow: FeedRecord[] = [
		{ feedId: 'a-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'ok', items: 9 },
		{ feedId: 'a-wire', date: '2026-08-02', runId: '2026-08-02-1', outcome: 'ok', items: 9 },
		{ feedId: 'b-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'transient', items: 0 }
	];
	const shallowRecord = reliability(shallow);
	expect(shallowRecord.runs).toBe(2);
	expect(shallowRecord.runs).toBeLessThan(MIN_ATTEMPTS);
	expect(shallowRecord.clean).toEqual(['a-wire']);
	expect(shallowRecord.checked).toBe(2);
	expect(shallowRecord.failed).toBe(1);

	// A feed nobody has asked is neither clean nor broken, so it is in neither
	// number. Counting a rest as a clean read is how a dead feed joins the
	// reliable list.
	const rested: FeedRecord[] = [
		...shallow,
		{ feedId: 'c-wire', date: '2026-08-01', runId: '2026-08-01-1', outcome: 'skipped', items: 0 }
	];
	const withRest = reliability(rested);
	expect(withRest.checked).toBe(2);
	expect(withRest.clean).toEqual(['a-wire']);
	// The run count is every run the rows hold, rest or no rest.
	expect(withRest.runs).toBe(2);
	// And the partition holds, always.
	expect(withRest.clean.length + withRest.failed).toBe(withRest.checked);
});

test('a record with more failing feeds than the list draws is counted whole', () => {
	// The canary cannot show a capped list, so a record deeper than the cap is
	// written here, over five runs: twelve feeds that each failed once, in each of
	// the four ways a read fails, two that never failed, one only ever rested and
	// one only ever refused by its robots file. The page draws `feed_rows` of the
	// twelve and counts the rest in its tail sentence; the count behind both is
	// never capped.
	const runs = ['2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14', '2030-06-15'];
	const record = (feedId: string, last: { outcome: string; items: number }): FeedRecord[] =>
		runs.map((date, at) => ({
			feedId,
			date,
			runId: `${date}-1`,
			...(at === runs.length - 1 ? last : { outcome: 'ok', items: 9 })
		}));
	const failures = [
		{ outcome: 'transient', items: 0 },
		{ outcome: 'permanent', items: 0 },
		{ outcome: 'blocked', items: 0 },
		{ outcome: 'ok', items: 0 }
	];
	const failed = Array.from({ length: 12 }, (_, at) =>
		record(`failing-${String(at + 1).padStart(2, '0')}`, failures[at % failures.length])
	);
	const rows: FeedRecord[] = [
		...failed.flat(),
		...record('clean-a', { outcome: 'ok', items: 9 }),
		...record('clean-b', { outcome: 'ok', items: 4 }),
		...runs.map((date) => ({ feedId: 'rested', date, runId: `${date}-1`, outcome: 'skipped', items: 0 })),
		...runs.map((date) => ({ feedId: 'refused', date, runId: `${date}-1`, outcome: 'robots_denied', items: 0 }))
	];
	expect(FEED_ROWS, 'the cap reaches past this record, so it hides nothing').toBeLessThan(12);

	const measured = reliability(rows);
	expect(measured.runs).toBe(5);
	expect(measured.checked).toBe(14);
	expect(measured.failed).toBe(12);
	expect(measured.clean).toEqual(['clean-a', 'clean-b']);
	expect(measured.ineligible).toEqual(['refused', 'rested']);
});
});

/** The threshold, from the file the pipeline reads it from. Not a copy. */
const QUARANTINE_AFTER = (
	JSON.parse(readFileSync(join(repo, 'config', 'idhazh.json'), 'utf8')) as {
		collect: { availability_strikes_before_rest: number };
	}
).collect.availability_strikes_before_rest;

test.describe('the quarantine rule, without a browser', () => {
	test('a failure count is a run of failures, not a lifetime total', () => {
		// Twelve failures a month ago and an answer this morning. The pipeline
		// rests nothing here, and a total would have printed 12 against a five
		// failure rule. This is the case the canary cannot reach on its own, and
		// it is the whole reason the count changed.
		const cameBack: FeedRead[] = [
			...Array.from({ length: 12 }, (_, n) => ({
				date: '2026-07-01',
				runId: `2026-07-01-${n + 1}`,
				outcome: 'transient',
				items: 0
			})),
			{ date: '2026-08-01', runId: '2026-08-01-1', outcome: 'ok', items: 9 }
		];
		expect(streak(cameBack)).toBe(0);
		expect(cameBack.filter(failing)).toHaveLength(12);
		expect(resting(cameBack, QUARANTINE_AFTER)).toBe(false);

		// And the other way round: four in a row against a five-failure rule is
		// one run from a rest, and a lifetime total would have said four as well.
		// The two only disagree when a feed recovers, which is exactly when the
		// operator must not be told it is nearly dead.
		const dying: FeedRead[] = Array.from({ length: 4 }, (_, n) => ({
			date: '2026-08-01',
			runId: `2026-08-01-${n + 1}`,
			outcome: 'permanent',
			items: 0
		}));
		expect(streak(dying)).toBe(4);
		expect(resting(dying, QUARANTINE_AFTER)).toBe(false);
	});

	test('a rest is transparent to the count, and lifts itself', () => {
		const struck: FeedRead[] = Array.from({ length: QUARANTINE_AFTER }, (_, n) => ({
			date: '2026-08-01',
			runId: `2026-08-01-${n + 1}`,
			outcome: 'transient',
			items: 0
		}));
		expect(resting(struck, QUARANTINE_AFTER)).toBe(true);

		// A skipped run neither adds a strike nor clears one: it never asked.
		const oneSkip = [...struck, { date: '2026-08-02', runId: '2026-08-02-1', outcome: 'skipped', items: 0 }];
		expect(streak(oneSkip)).toBe(QUARANTINE_AFTER);
		expect(resting(oneSkip, QUARANTINE_AFTER)).toBe(true);

		// Rested as many times as it was struck, and it is asked again regardless.
		// Without this a bad afternoon is a permanent removal nobody voted for.
		const served = [
			...struck,
			...Array.from({ length: QUARANTINE_AFTER }, (_, n) => ({
				date: '2026-08-02',
				runId: `2026-08-02-${n + 1}`,
				outcome: 'skipped',
				items: 0
			}))
		];
		expect(resting(served, QUARANTINE_AFTER)).toBe(false);
	});

	test('an answer that carried nothing is a failure, and a polite refusal is not', () => {
		const empty: FeedRead = { date: '2026-08-01', runId: 'r1', outcome: 'ok', items: 0 };
		const polite: FeedRead = { date: '2026-08-01', runId: 'r2', outcome: 'robots_denied', items: 0 };
		expect(failing(empty)).toBe(true);
		expect(failing(polite)).toBe(false);
		expect(streak([polite, polite])).toBe(0);
	});

	test('a day is drawn by its worst outcome and labelled by all of them', () => {
		const mixed: FeedRead[] = [
			{ date: '2026-08-01', runId: 'a', outcome: 'ok', items: 5 },
			{ date: '2026-08-01', runId: 'b', outcome: 'ok', items: 5 },
			{ date: '2026-08-01', runId: 'c', outcome: 'transient', items: 0 }
		];
		const [day] = feedDays(mixed);
		expect(day.outcome).toBe('failed');
		// The colour says the day needs a look. The sentence says two of the three
		// runs were fine, so the square is never read as a whole day lost.
		expect(day.label).toBe('1 Aug 2026, 3 runs: 2 answered, 1 failed.');

		const clean = feedDays([{ date: '2026-08-02', runId: 'a', outcome: 'ok', items: 5 }]);
		expect(clean[0].outcome).toBe('answered');
		expect(clean[0].label).toBe('2 Aug 2026, 1 run: 1 answered.');
	});
});

/** The eight kinds of evidence a feed-health row can carry, and what each does
 * to a streak of two. Three effects: add one, leave it alone, end it.
 *
 * The two robots rows are both written as `robots_denied`, because that is what
 * the ledger records for a refusal and for a robots.txt we could not read. The
 * difference is in `robots_outcome`, and availability does not care which it
 * was - so both appear here and both preserve.
 */
const EVIDENCE: { name: string; row: FeedRead; after: number }[] = [
	{ name: 'a success carrying entries', row: { ...at(9), outcome: 'ok', items: 3 }, after: 0 },
	{ name: 'a success carrying nothing', row: { ...at(9), outcome: 'ok', items: 0 }, after: 3 },
	{ name: 'blocked', row: { ...at(9), outcome: 'blocked', items: 0 }, after: 3 },
	{ name: 'permanent', row: { ...at(9), outcome: 'permanent', items: 0 }, after: 3 },
	{ name: 'transient', row: { ...at(9), outcome: 'transient', items: 0 }, after: 3 },
	{ name: 'robots denied', row: { ...at(9), outcome: 'robots_denied', items: 0 }, after: 2 },
	{ name: 'robots unknown', row: { ...at(9), outcome: 'robots_denied', items: 0 }, after: 2 },
	{ name: 'a rest', row: { ...at(9), outcome: 'skipped', items: 0 }, after: 2 }
];

/** One run of the fixture day, so a case names its evidence and nothing else. */
function at(run: number): { date: string; runId: string } {
	return { date: '2026-08-30', runId: `2026-08-30-${run}` };
}

test.describe('the evidence table, without a browser', () => {
	const twoStrikes: FeedRead[] = [
		{ ...at(1), outcome: 'transient', items: 0 },
		{ ...at(2), outcome: 'transient', items: 0 }
	];

	for (const { name, row, after } of EVIDENCE) {
		test(`${name} leaves the streak at ${after}`, () => {
			expect(streak(twoStrikes)).toBe(2);
			expect(streak([...twoStrikes, row])).toBe(after);
		});
	}

	test('a refusal never launders a record', () => {
		// The half of the robots rule that is not "no strike". A refusal used to
		// end the streak, so a dead address behind a site that says no would have
		// had its record wiped after every failure and could never reach a rest.
		const struck: FeedRead[] = Array.from({ length: QUARANTINE_AFTER }, (_, n) => ({
			...at(n + 1),
			outcome: 'transient',
			items: 0
		}));
		const refused = [...struck, { ...at(9), outcome: 'robots_denied', items: 0 }];
		expect(streak(refused)).toBe(QUARANTINE_AFTER);
		expect(resting(refused, QUARANTINE_AFTER)).toBe(true);
	});
});

test.describe('THE ORACLE: one result per feed per run, in both languages', () => {
	/** The fixture both reducers read. `backend/tests/test_discover.py` opens the
	 * same file and asserts the same three numbers, which is the only way to
	 * show the page and the pipeline agree rather than merely claiming it. */
	const FIXTURE = join(repo, 'tests', 'fixtures', 'feed-health', 'one-result-per-run.csv');

	function fixtureRows(): FeedEvent[] {
		const lines = readFileSync(FIXTURE, 'utf8').trim().split(/\r?\n/);
		const head = lines[0].split(',');
		return lines.slice(1).map((line) => {
			const cell = line.split(',');
			const row = new Map(head.map((name, index) => [name, cell[index] ?? '']));
			return {
				date: row.get('date') ?? '',
				runId: row.get('run_id') ?? '',
				checkedAt: row.get('checked_at') ?? '',
				outcome: row.get('outcome') ?? '',
				items: Number(row.get('items') ?? 0) || 0,
				feedId: row.get('feed_id') ?? ''
			};
		});
	}

	test('nine rows are seven events, and each distinct run is counted once', () => {
		const rows = fixtureRows();
		expect(rows).toHaveLength(9);
		const effective = chronological(settled(rows));
		expect(effective).toHaveLength(7);
		expect(new Set(effective.map((row) => row.runId)).size).toBe(7);
		// The two accounts of run 3 are one event, and the one that carried
		// articles is the one kept - however late the empty retry ran.
		const third = effective.find((row) => row.runId === '2026-08-30-3') as FeedEvent;
		expect(third.items).toBe(6);
	});

	test('the strike count is one, and it is two if nothing settles the rows', () => {
		const rows = fixtureRows();
		// Counted row by row, the empty retry of run 3 is a second strike that no
		// run ever suffered.
		expect(streak(chronological(rows))).toBe(2);
		expect(streak(chronological(settled(rows)))).toBe(1);
		expect(resting(chronological(settled(rows)), QUARANTINE_AFTER)).toBe(false);
	});
});

test.describe('the strip geometry, without a browser', () => {
	test('a strip shrinks to fit its row instead of scrolling', () => {
		// The page strip grows into a page-wide frame and never goes below 16px.
		// A strip in a list row has to fit whatever it is given, because twenty
		// scrollbars in one column is not a list.
		const week = denseCellFor(ROW_STRIP_PX, 7);
		const quarter = denseCellFor(ROW_STRIP_PX, 90);
		expect(week.cell).toBeGreaterThan(quarter.cell);
		expect(week.width).toBeLessThanOrEqual(ROW_STRIP_PX);
		// Ninety days cannot fit at a readable size, so the square wins and the
		// strip overflows rather than drawing a row of invisible ticks.
		expect(quarter.cell).toBeGreaterThanOrEqual(3);
		// Never taller than the target bar it sits beside.
		expect(week.cell).toBeLessThanOrEqual(14);
		// The width is what the grid really occupies: n squares and n-1 gaps. A
		// trailing gap would put the date axis one gap right of its own columns.
		expect(week.width).toBe(7 * week.cell + 6 * week.gap);
		expect(denseCellFor(ROW_STRIP_PX, 0).width).toBe(0);
	});
});

test('the approved redraw is a tile record, not a second quarantine decision', async ({ page }) => {
	await page.goto('/console/voices/');
	const panel = page.locator('[data-console-panel-id="feeds-failed"]');
	await expect(panel.locator('[data-feeds="table"]')).toHaveCount(1);
	await expect(panel.locator('[data-target-cell]')).toHaveCount(0);
	const tiles = panel.locator('[data-tile-state]');
	expect(await tiles.count()).toBeGreaterThan(0);
	const labels = await tiles.evaluateAll((nodes) => nodes.map((node) => ({ state: node.getAttribute('data-tile-state'), label: node.getAttribute('aria-label') })));
	expect(labels.some((tile) => tile.state === 'fired')).toBe(true);
	for (const tile of labels) {
		expect(['absent', 'quiet', 'fired']).toContain(tile.state);
		expect(tile.label).toMatch(/^\d{4}-\d{2}-\d{2}: /);
	}
});
test('feed-only counts retain the native reliability partition without counting refused asks as clean', async ({ page }) => {
	await page.goto('/console/voices/');
	const panel = page.locator('[data-console-panel-id="feeds-failed"]');
	const headline = panel.locator('[data-feed-reliability]');
	await expect(headline).toHaveCount(1);
	const clean = Number(await headline.getAttribute('data-feed-clean'));
	const failed = Number(await headline.getAttribute('data-feed-failed'));
	const checked = Number(await headline.getAttribute('data-feed-checked'));
	const unread = Number(await headline.getAttribute('data-feed-ineligible'));
	expect(clean + failed).toBe(checked);
	const names = await panel.locator('[data-feed-ineligible-name]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-ineligible-name')!));
	expect(names.length).toBe(unread);
	expect(unread).toBeGreaterThan(0);
	expect(new Set(names).size).toBe(unread);
	expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)));
	const cleanNames = await panel.locator('[data-feed-clean-name]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-clean-name')!));
	expect(names.filter((id) => cleanNames.includes(id))).toEqual([]);
});
for (const theme of ['light', 'dark']) {
	test(`three tile states use the chart token and real border geometry, ${theme}`, async ({ page }) => {
		await page.addInitScript((value) => localStorage.setItem('idhazh:theme', value), theme);
		await page.goto('/console/voices/');
		const panel = page.locator('[data-console-panel-id="feeds-failed"]');
		await expect(panel.locator('[data-tile-state="fired"]').first()).toBeVisible();
		const reading = await panel.evaluate((root) => {
			const probe = document.createElement('span');
			probe.style.backgroundColor = 'var(--chart-1)';
			document.body.append(probe);
			const token = getComputedStyle(probe).backgroundColor;
			probe.remove();
			return { token, tiles: [...root.querySelectorAll('[data-tile-state]')].map((tile) => ({
				state: tile.getAttribute('data-tile-state'), fill: getComputedStyle(tile).backgroundColor,
				border: getComputedStyle(tile).borderTopStyle
			})) };
		});
		for (const tile of reading.tiles) {
			if (tile.state === 'fired') expect(tile.fill).toBe(reading.token);
			else expect(tile.border).toBe(tile.state === 'quiet' ? 'solid' : 'dashed');
		}
	});
}
test('the actual feed row retains pointer, click, keyboard and Escape readings', async ({ page }) => {
	await page.goto('/console/voices/');
	const panel = page.locator('[data-console-panel-id="feeds-failed"]');
	const plot = panel.locator('ol[data-chart-type="tileStrip"]').first();
	await expect(plot).toBeVisible();
	const strip = plot.locator('..').locator('[data-readout-day]');
	const resting = await strip.innerText();
	await plot.focus();
	await plot.press('Home');
	const first = await strip.innerText();
	await plot.press('End');
	await plot.press('Escape');
	await expect(strip).toHaveText(resting);
	const tile = plot.locator('[data-readout-at]').first();
	await tile.hover();
	await expect(strip).toHaveText(first);
	await tile.click();
	await expect(strip).toHaveText(first);
});
