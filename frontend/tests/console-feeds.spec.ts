import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	chronological,
	failing,
	feedDays,
	resting,
	streak,
	type FeedRead
} from '../src/lib/feed-health';
import { axisLabels, denseCellFor, ROW_STRIP_PX } from '../src/lib/charts/run-history';

/**
 * The feed section answers one question: which feed is about to be dropped.
 *
 * It used to answer a different one. It sorted by every failure the ledger ever
 * held, so a feed that failed twelve times last month and answered this morning
 * led a feed one run from being rested - and it printed that same total beside
 * the word "rested", which is a number the pipeline never used to rest anything.
 *
 * So the oracle here is not "does a bar appear". It is that the count on the
 * page equals the run of failures `discover._rests` counts, recomputed here
 * from the same ledger the page read, and that the marker on the bar lands on
 * the quarantine threshold read out of `config/idhazh.json` - the file the
 * pipeline itself reads. A bar drawn to the wrong scale looks perfectly fine.
 */

const repo = resolve(process.cwd(), '..');

/** The tree `build:canary` builds the site from, and the one this suite runs
 * against. Reading `state/` instead would compare the page to a ledger it never
 * saw - which is exactly how this test failed the first time it ran. */
const CANARY = join(repo, 'backend', 'var', 'canary');

/** The threshold, from the file the pipeline reads it from. Not a copy. */
const QUARANTINE_AFTER = (
	JSON.parse(readFileSync(join(repo, 'config', 'idhazh.json'), 'utf8')) as {
		collect: { quarantine_after_failures: number };
	}
).collect.quarantine_after_failures;

/** The ledger the page read, read again independently. Nothing is mocked:
 * these are the CSVs `build_canary_day.py` wrote. */
type LedgerRow = FeedRead & { feedId: string };

function ledger(): LedgerRow[] {
	const dir = join(CANARY, 'state', 'feed-health');
	const rows: LedgerRow[] = [];
	for (const shard of readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.sort()) {
		const lines = readFileSync(join(dir, shard), 'utf8').trim().split(/\r?\n/);
		const head = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cell = line.split(',');
			const row = new Map(head.map((name, index) => [name, cell[index] ?? '']));
			rows.push({
				date: row.get('date') ?? '',
				runId: row.get('run_id') ?? '',
				outcome: row.get('outcome') ?? '',
				items: Number(row.get('items') ?? 0) || 0,
				feedId: row.get('feed_id') ?? ''
			});
		}
	}
	return rows;
}

function byFeed(rows: LedgerRow[]): Map<string, LedgerRow[]> {
	const found = new Map<string, LedgerRow[]>();
	for (const row of rows) {
		found.set(row.feedId, [...(found.get(row.feedId) ?? []), row]);
	}
	return new Map([...found].map(([id, group]) => [id, chronological(group)]));
}

/** Every row the section drew, with the numbers it published about itself. */
async function drawn(page: Page) {
	return page.locator('[data-feed]').evaluateAll((rows) =>
		rows.map((row) => ({
			feedId: row.getAttribute('data-feed') ?? '',
			streak: Number(row.getAttribute('data-feed-streak')),
			failures: Number(row.getAttribute('data-feed-failures')),
			track: Number(row.getAttribute('data-feed-track')),
			resting: row.getAttribute('data-feed-resting') === 'yes',
			rested: row.querySelector('[data-rested]') !== null
		}))
	);
}

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

test('THE ORACLE: the printed count is the run the pipeline rests on', async ({ page }) => {
	await page.goto('/console/');

	const rows = await drawn(page);
	const recomputed = byFeed(ledger());

	// Read against a fact the fixture owns, never against a locator count: a
	// renamed attribute would make the count zero and switch this off silently.
	const troubled = [...recomputed].filter(([, group]) =>
		group.filter((row) => row.outcome !== 'skipped').some(failing)
	);
	expect(
		troubled.length,
		'the ledger holds no failing feed, so this oracle asserts nothing'
	).toBeGreaterThan(0);
	await expect(page.locator('[data-feed]'), 'the section drew no feed').toHaveCount(
		troubled.length
	);

	for (const row of rows) {
		const group = recomputed.get(row.feedId);
		expect(group, `${row.feedId} is on the page and not in the ledger`).toBeTruthy();
		const history = group as LedgerRow[];
		// The pipeline's own loop, run here on the same rows.
		expect(row.streak, `${row.feedId} prints a count the pipeline does not use`).toBe(
			streak(history)
		);
		expect(row.resting, `${row.feedId} disagrees with the pipeline about resting`).toBe(
			resting(history, QUARANTINE_AFTER)
		);
		// The word, not just the colour.
		expect(row.rested, `${row.feedId} is rested and does not say so`).toBe(row.resting);
	}

	// At least one feed must actually be past the threshold, and at least one
	// must be short of it. An oracle that only ever sees one arm is checking half
	// a rule.
	expect(rows.some((row) => row.resting), 'no rested feed is drawn').toBe(true);
	expect(rows.some((row) => !row.resting), 'no healthy feed is drawn').toBe(true);
});

test('THE ORACLE: the marker sits on the quarantine threshold', async ({ page }) => {
	await page.goto('/console/');

	const rows = await drawn(page);
	expect(rows.length, 'nothing to measure').toBeGreaterThan(0);

	const measured = await page.locator('[data-feed]').evaluateAll((nodes) =>
		nodes.map((node) => {
			const track = node.querySelector('[data-target-cell="track"]') as HTMLElement;
			const marker = node.querySelector('[data-target-cell="marker"]') as HTMLElement;
			const fill = node.querySelector('[data-target-cell="fill"]') as HTMLElement;
			const box = track.getBoundingClientRect();
			return {
				feedId: node.getAttribute('data-feed') ?? '',
				// The marker is 2px wide with a -1px start margin, so its centre is
				// one pixel right of its own left edge.
				marker: (marker.getBoundingClientRect().left + 1 - box.left) / box.width,
				fill: fill.getBoundingClientRect().width / box.width
			};
		})
	);

	for (const seen of measured) {
		const row = rows.find((candidate) => candidate.feedId === seen.feedId);
		expect(row, `${seen.feedId} drew a bar and published no numbers`).toBeTruthy();
		const published = row as NonNullable<typeof row>;
		// Where the marker lands, back in failures. A bar scaled to anything else
		// puts this number somewhere other than the rule.
		const atMarker = seen.marker * published.track;
		expect(
			Math.abs(atMarker - QUARANTINE_AFTER),
			`${seen.feedId} draws its rest at ${atMarker.toFixed(2)} failures, not ${QUARANTINE_AFTER}`
		).toBeLessThan(0.05);
		// And the fill is the count, on the same track.
		const atFill = seen.fill * published.track;
		expect(
			Math.abs(atFill - published.streak),
			`${seen.feedId} fills to ${atFill.toFixed(2)} against a count of ${published.streak}`
		).toBeLessThan(0.05);
	}
});

test('the list is ranked by nearness to a rest, then by how much went wrong', async ({ page }) => {
	await page.goto('/console/');

	const rows = await drawn(page);
	expect(rows.length, 'nothing to rank').toBeGreaterThan(1);

	// Read off the page rather than typed here, so the rule is what is asserted
	// and not one fixture's answer to it.
	for (let index = 1; index < rows.length; index += 1) {
		const above = rows[index - 1];
		const below = rows[index];
		const ordered =
			above.streak > below.streak ||
			(above.streak === below.streak &&
				(above.failures > below.failures ||
					(above.failures === below.failures && above.feedId <= below.feedId)));
		expect(
			ordered,
			`${below.feedId} (${below.streak} in a row, ${below.failures} in total) sorts below ` +
				`${above.feedId} (${above.streak} in a row, ${above.failures} in total)`
		).toBe(true);
	}
});

test('the strip follows the window while the count does not', async ({ page }) => {
	await page.goto('/console/');
	const control = page.locator('[data-window-control] [data-window-preset="7"] input');
	await expect(control).toBeEnabled();

	const section = page.locator('[data-windowed="feed-outcomes"]');
	const squares = () => page.locator('[data-feed-strip] [data-feed-day]');

	const wideDays = await page.locator('[data-feed-axis]').count();
	expect(wideDays, 'the strip drew no date axis').toBeGreaterThan(0);
	const wideSquares = await squares().count();
	const wideCounts = (await drawn(page)).map((row) => row.streak);

	// The label is the target, not the 1px input inside it.
	await page.locator('[data-window-preset="7"]').click();
	await expect(section).toHaveAttribute('data-window-days', '7');

	const narrowSquares = await squares().count();
	expect(narrowSquares, 'the strip ignored the window').toBeLessThanOrEqual(wideSquares);
	// The count is the pipeline's decision and cannot move with a control.
	expect((await drawn(page)).map((row) => row.streak)).toEqual(wideCounts);
});

test('every square carries a sentence, not only a colour', async ({ page }) => {
	await page.goto('/console/');

	const squares = page.locator('[data-feed-strip] [data-feed-day]');
	const count = await squares.count();
	expect(count, 'no square was drawn').toBeGreaterThan(0);

	const labels = await squares.evaluateAll((nodes) =>
		nodes.map((node) => ({
			outcome: node.getAttribute('data-feed-outcome') ?? '',
			label: node.getAttribute('aria-label') ?? ''
		}))
	);
	for (const square of labels) {
		expect(square.label.length, `a ${square.outcome} square says nothing`).toBeGreaterThan(0);
	}
	// The four states the ledger can produce, and no fifth invented one.
	const seen = new Set(labels.map((square) => square.outcome));
	for (const outcome of seen) {
		expect(['answered', 'failed', 'refused', 'resting', 'none']).toContain(outcome);
	}
	expect(seen.has('failed'), 'the fixture drew no failed day').toBe(true);
});

test('the date axis labels the same columns the squares sit in', async ({ page }) => {
	await page.goto('/console/');

	const columns = await page
		.locator('[data-feed-strip]')
		.first()
		.locator('[data-feed-day]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-feed-day') ?? ''));
	expect(columns.length, 'the strip drew no day').toBeGreaterThan(0);

	// The axis is computed from the same dates the squares are, so an axis that
	// drifted a column would show up as a label pointing at the wrong day.
	const expected = axisLabels(columns);
	const drawnAxis = await page
		.locator('[data-feed-axis]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				column: Number(node.getAttribute('data-feed-axis')),
				text: (node.textContent ?? '').trim()
			}))
		);
	expect(drawnAxis).toEqual(expected.map(({ column, text }) => ({ column, text })));
});
