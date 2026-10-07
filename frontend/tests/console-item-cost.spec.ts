import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { windowOfDays } from '../src/lib/charts/viewport';
import { describeHeldPart } from '../src/lib/console/held-part-note';
import { itemCost } from '../src/lib/console/item-cost';
import { describePromptCacheSubtitle } from '../src/lib/console/prompt-cache-subtitle';
import { telemetryRows } from '../src/lib/server/payload';
import { windowDay } from '../src/lib/server/window-day';
import { publishedSite } from './support/published-site';
import { ONE_DAYS, spanSaid } from './support/span-said';

/**
 * What one item cost the model, checked against answers written out here rather
 * than against the label beside the mark.
 *
 * The first half is the reducer as a pure function, over rows written by hand
 * for the states the fixture cannot reach: a cell that is empty rather than
 * zero, a window where the two clocks answer for different numbers of items,
 * and a rate that must be pooled rather than averaged.
 *
 * The oracles are the second half. One is a site the test builds, read the way
 * the console's server reads it, with each window's answer written out. A spec
 * that re-derived each figure from the canary's own rows moved whenever the
 * canary did; one that compared a bar against the number printed under it would
 * pass on any reducer at all, because both come from one call. The other is the
 * note under the share, on rows the test builds, with the words each pair of
 * figures calls for written out in full.
 *
 * The last part is the built console: the window the control set, every counted
 * item in a bar, and the share note, none of them checked against a figure the
 * canary holds.
 */

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

// ---------------------------------------------------------------------------
// The reducer, as arithmetic
// ---------------------------------------------------------------------------

const WINDOW = { start: '2026-08-01', end: '2026-08-31', days: 30 };

/** One projection row. Every cell is a string, because that is what a CSV holds
 * and an empty string is the whole point of these tests. */
function row(cells: Record<string, string>): Record<string, string> {
	return { date: '2026-08-10', run_id: '2026-08-10-1', item_id: 'a-01', ...cells };
}

test.describe('what one item cost, as arithmetic', () => {
	test('an instrument that did not run is absent, and never a zero', () => {
		// The row that matters most: an item that failed before the model saw it.
		// Counted as a zero it would say the model read a prompt instantly, which
		// is the one reading nobody would question on a chart.
		const cost = itemCost(
			[
				row({ prefill_ms: '4000', decode_ms: '2000', input_tokens: '100', output_tokens: '10' }),
				row({ item_id: 'a-02', prefill_ms: '', decode_ms: '', input_tokens: '', output_tokens: '' })
			],
			WINDOW
		);
		expect(cost.rows, 'both rows are in the window').toBe(2);
		expect(cost.timed, 'only one row carries both clocks').toBe(1);
		expect(cost.reading?.n).toBe(1);
		expect(cost.reading?.fastest, 'the empty cell became a zero').toBe(4000);
		expect(cost.counted, 'only one row carries a token count').toBe(1);
	});

	test('a zero IS a measurement, and it is counted', () => {
		// Zero reuse is a real answer: the server cached nothing for that item.
		// Measured 2026-09-05 over the committed projection, 667 of 6,104 items
		// are in exactly this state, so dropping them would overstate the share.
		const cost = itemCost(
			[
				row({ input_tokens: '1000', cached_tokens: '0' }),
				row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '500' })
			],
			WINDOW
		);
		expect(cost.readWhole, 'an item that reused nothing is not an item nobody measured').toBe(1);
		expect(cost.counted).toBe(2);
		expect(cost.reusedTokens).toBe(500);
		expect(cost.readTokens, '1000 read whole, plus the 500 the other one still read').toBe(1500);
		// 500 of the 2000 tokens the two prompts needed.
		expect(cost.reusedPct).toBe(25);
		// The middle of [0%, 50%], which is not the same question as the line above.
		expect(cost.itemReusedPct).toBe(25);
	});

	test('a share of a window and the middle item are two different numbers', () => {
		// One very long prompt that reused nothing drags the window's share down
		// while the middle item is untouched. A panel printing one of them and
		// calling it the other is why both are computed.
		const cost = itemCost(
			[
				row({ input_tokens: '90000', cached_tokens: '0' }),
				row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '900' }),
				row({ item_id: 'a-03', input_tokens: '1000', cached_tokens: '900' })
			],
			WINDOW
		);
		expect(cost.reusedPct, '1800 of the 91,800 tokens the window needed').toBe(2);
		expect(cost.itemReusedPct, 'the middle item reused 90 percent of its own prompt').toBe(90);
	});

	test('a rate is summed and then divided, never averaged over items', () => {
		// Averaging per-item rates weighs a 10-token item like a 1,000-token one.
		// Here the mean of the two rates is 55 ms and the pooled answer is 20.
		const cost = itemCost(
			[
				row({ prefill_ms: '1000', input_tokens: '10', cached_tokens: '0' }),
				row({ item_id: 'a-02', prefill_ms: '1000', input_tokens: '100', cached_tokens: '0' })
			],
			WINDOW
		);
		expect(cost.msPerReadToken, '2000 ms over 110 tokens').toBeCloseTo(2000 / 110, 6);
	});

	test('cached tokens are taken out of the read count', () => {
		// The model did not read them, so a rate that counted them reports a speed
		// the machine never ran at. This is the failure the runtime audit exists
		// to catch, held here on the reader's side of the same ledger.
		const cost = itemCost(
			[row({ prefill_ms: '1000', input_tokens: '1000', cached_tokens: '900' })],
			WINDOW
		);
		expect(cost.readTokens).toBe(100);
		expect(cost.msPerReadToken, '1000 ms over the 100 it actually read').toBe(10);
	});

	test('whether the cache answered is a question about one call, not about the item', () => {
		// An item read by two calls always has a non-zero total, because the second
		// call replays the first call's prompt and is answered for it. Read off the
		// total, "items whose prompt was read whole" counts nothing for ever - a
		// live figure that becomes a constant with no code change, which is the one
		// failure a chart cannot show. The numbers are the two-call measurement of
		// 2026-09-12: a first call that read 1,497 tokens cold, and a second that
		// asked for 2,389 and was given 1,493 of them.
		const twoCalls = row({
			prefill_ms: '400872',
			input_tokens: '3886',
			cached_tokens: '1493',
			model_calls: '2',
			label_kind: 'label',
			label_prefill_ms: '214122',
			label_decode_ms: '88795',
			label_input_tokens: '1497',
			label_output_tokens: '205',
			label_cached_tokens: '0'
		});
		const oneCall = row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '0' });

		const cost = itemCost([twoCalls, oneCall], WINDOW);

		expect(cost.perCall, 'one of the two rows published a split').toBe(1);
		expect(cost.readWhole, 'both first calls read their prompt whole').toBe(2);
		expect(cost.reusedMedian, 'the middle of the two first calls, not of the totals').toBe(0);
		expect(cost.itemReusedPct, 'neither first call reused anything').toBe(0);
		// The pooled figures still read the totals, and they are meant to: a sum
		// over both calls is what the item cost, and every rate here is pooled.
		expect(cost.reusedTokens).toBe(1493);
		expect(cost.readTokens, '2,393 the split item read, plus the 1,000 the other did').toBe(3393);
	});

	test('a row with no split still answers from the item total', () => {
		// Every row published before 2026-09-12, and every row a one-call run
		// writes. An empty cell is absent, so the older reading stands rather than
		// dropping out of the denominator.
		const cost = itemCost(
			[
				row({ input_tokens: '1000', cached_tokens: '0', label_cached_tokens: '' }),
				row({ item_id: 'a-02', input_tokens: '1000', cached_tokens: '400' })
			],
			WINDOW
		);
		expect(cost.perCall).toBe(0);
		expect(cost.readWhole).toBe(1);
		expect(cost.reusedMedian).toBe(200);
	});

	test('a middle taken over an even number of items is still a whole number', () => {
		// The canary holds an odd number of timed items, so no browser case can reach
		// this. The committed projection holds 6,104 and reached it on the first
		// real build: the middle prompt printed 1,687.5 tokens.
		const cost = itemCost(
			[
				row({ input_tokens: '1687', output_tokens: '10', cached_tokens: '843' }),
				row({ item_id: 'a-02', input_tokens: '1688', output_tokens: '11', cached_tokens: '845' })
			],
			WINDOW
		);
		expect(cost.promptTokens).toBe(1688);
		expect(cost.writtenTokens).toBe(11);
		expect(cost.itemReusedPct).toBe(50);
		expect(cost.reusedMedian).toBe(844);
	});

	test('a window with nothing in it draws nothing, rather than a chart of zeroes', () => {
		const cost = itemCost([row({ date: '2026-07-01', prefill_ms: '4000' })], WINDOW);
		expect(cost.rows).toBe(0);
		expect(cost.reading).toBeNull();
		expect(cost.writing).toBeNull();
		expect(cost.msPerReadToken).toBeNull();
		expect(cost.writeCostRatio).toBeNull();
	});

	test('a ratio against an absent rate is not a ratio', () => {
		const cost = itemCost(
			[row({ prefill_ms: '1000', input_tokens: '100', cached_tokens: '0' })],
			WINDOW
		);
		expect(cost.msPerReadToken).not.toBeNull();
		expect(cost.msPerWrittenToken, 'nothing recorded a written token').toBeNull();
		expect(cost.writeCostRatio).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// The oracle
// ---------------------------------------------------------------------------

/** One projection row for `item`: a prompt of `tokens` tokens that the model
 * read whole in one second, and a ten-token summary written in half of one. */
function dated(date: string, item: string, tokens: number): Record<string, string> {
	return {
		date,
		run_id: `${date}-1`,
		item_id: item,
		prefill_ms: '1000',
		decode_ms: '500',
		input_tokens: String(tokens),
		output_tokens: '10',
		cached_tokens: '0'
	};
}

test("THE ORACLE: each window counts its own days, and they end on the site's newest published day", () => {
	// Published on 14 and 15 Jun 2030. The projection holds a row on each window's
	// first day and on the day before it, and one on 16 Jun, the day after the
	// newest published day: a projection can run a day past the digest, as the
	// canary's does. Each prompt is a different power of two, so the tokens a
	// window read name exactly the rows it counted.
	const { digest, telemetry } = publishedSite(test.info().outputPath('site'), {
		published: ['2030-06-14', '2030-06-15'],
		telemetry: {
			// Filed under February and dated inside every window, as a misfiled row
			// is. A read that opened a month no window touches would count it.
			'2030-02': [dated('2030-06-15', 'misfiled', 2048)],
			'2030-03': [dated('2030-03-17', 'before-90', 1), dated('2030-03-18', 'first-of-90', 2)],
			'2030-05': [dated('2030-05-16', 'before-30', 4), dated('2030-05-17', 'first-of-30', 8)],
			'2030-06': [
				dated('2030-06-01', 'before-14', 16),
				dated('2030-06-02', 'first-of-14', 32),
				dated('2030-06-08', 'before-7', 64),
				dated('2030-06-09', 'first-of-7', 128),
				dated('2030-06-14', 'before-1', 256),
				dated('2030-06-15', 'newest', 512),
				dated('2030-06-16', 'after', 1024)
			]
		}
	});

	const day = windowDay(digest);
	expect(day).toBe('2030-06-15');
	const windows = [1, 7, 14, 30, 90].map((days) => ({ days, ...windowOfDays(day, days, 'right') }));
	expect(windows.map(({ start, end }) => `${start} to ${end}`)).toEqual([
		'2030-06-15 to 2030-06-15',
		'2030-06-09 to 2030-06-15',
		'2030-06-02 to 2030-06-15',
		'2030-05-17 to 2030-06-15',
		'2030-03-18 to 2030-06-15'
	]);

	// Read once, over the widest window, as the console's server reads it.
	const read = telemetryRows(telemetry, windows[windows.length - 1]).rows;
	expect(read.map((row) => row.item_id)).toEqual([
		'first-of-90',
		'before-30',
		'first-of-30',
		'before-14',
		'first-of-14',
		'before-7',
		'first-of-7',
		'before-1',
		'newest'
	]);

	const counted = windows.map((offered) => {
		const cost = itemCost(read, offered);
		return { days: cost.days, rows: cost.rows, timed: cost.timed, readTokens: cost.readTokens };
	});
	expect(counted).toEqual([
		{ days: 1, rows: 1, timed: 1, readTokens: 512 },
		{ days: 7, rows: 3, timed: 3, readTokens: 896 },
		{ days: 14, rows: 5, timed: 5, readTokens: 992 },
		{ days: 30, rows: 7, timed: 7, readTokens: 1016 },
		{ days: 90, rows: 9, timed: 9, readTokens: 1022 }
	]);
});

// ---------------------------------------------------------------------------
// The note under the share
// ---------------------------------------------------------------------------

/** One projection row for `item`: a 4,000-token prompt with `tokens` of it
 * already in memory. */
function held(date: string, item: string, tokens: number): Record<string, string> {
	return {
		date,
		run_id: `${date}-1`,
		item_id: item,
		input_tokens: '4000',
		cached_tokens: String(tokens)
	};
}

/** Windows that end on 6 Oct 2026, as the readings behind the note did. */
const NINETY_DAYS = { start: '2026-07-09', end: '2026-10-06', days: 90 };
const THIRTY_DAYS = { start: '2026-09-07', end: '2026-10-06', days: 30 };
const ONE_DAY = { start: '2026-10-06', end: '2026-10-06', days: 1 };

test.describe('THE ORACLE: the note under the share says what its own two figures show', () => {
	test('a window whose middle item had 922 tokens in memory and whose largest had 2,219 says the amount changed a lot', () => {
		// The step the note missed: 922 tokens on every day up to 12 Sep 2026, and
		// about 1,900 from 14 Sep, so the largest is more than twice the middle.
		const cost = itemCost(
			[
				held('2026-07-10', 'a-01', 922),
				held('2026-08-10', 'a-02', 922),
				held('2026-09-12', 'a-03', 922),
				held('2026-09-14', 'a-04', 1905),
				held('2026-10-06', 'a-05', 2219)
			],
			NINETY_DAYS
		);
		expect([cost.reusedMedian, cost.reusedWidest]).toEqual([922, 2219]);
		expect(describeHeldPart(cost)).toBe(
			'In these 90 days, the amount already in memory changed a lot. The middle item had 922 tokens in memory, and the most any item had was 2,219 tokens. So here a lower percentage can mean less in memory, not only a longer article. Read the token counts, not the rise or fall of the percentages.'
		);
	});

	test('a window whose largest is under twice its middle states the two figures and claims nothing about change', () => {
		// These 30 days start before the step, so their first day held 922, and
		// they still pass on their two figures. That is why the passing words say
		// nothing about how much the amount in memory changed.
		const cost = itemCost(
			[
				held('2026-09-07', 'a-01', 922),
				held('2026-09-20', 'a-02', 1849),
				held('2026-10-06', 'a-03', 2219)
			],
			THIRTY_DAYS
		);
		expect([cost.reusedMedian, cost.reusedWidest]).toEqual([1849, 2219]);
		expect(describeHeldPart(cost)).toBe(
			'In these 30 days, the middle item had 1,849 tokens already in memory, and the most any item had was 2,219 tokens. A longer article makes the percentage lower, even if the amount in memory does not change. Read the token counts, not the rise or fall of the percentages.'
		);
	});

	test('twice the middle has changed a lot, and one token under it has not', () => {
		const note = (largest: number) =>
			describeHeldPart(
				itemCost(
					[
						held('2026-09-20', 'a-01', 1000),
						held('2026-09-21', 'a-02', 1000),
						held('2026-09-22', 'a-03', largest)
					],
					THIRTY_DAYS
				)
			);
		expect(note(2000)).toBe(
			'In these 30 days, the amount already in memory changed a lot. The middle item had 1,000 tokens in memory, and the most any item had was 2,000 tokens. So here a lower percentage can mean less in memory, not only a longer article. Read the token counts, not the rise or fall of the percentages.'
		);
		expect(note(1999)).toBe(
			'In these 30 days, the middle item had 1,000 tokens already in memory, and the most any item had was 1,999 tokens. A longer article makes the percentage lower, even if the amount in memory does not change. Read the token counts, not the rise or fall of the percentages.'
		);
	});

	test('one day where most items had nothing in memory says the amount changed a lot', () => {
		// A spread between items, not a step over time: two prompts read whole and
		// one with 922 tokens in memory, on one day. The words are true of this too.
		const cost = itemCost(
			[held('2026-10-06', 'a-01', 0), held('2026-10-06', 'a-02', 0), held('2026-10-06', 'a-03', 922)],
			ONE_DAY
		);
		expect(describeHeldPart(cost)).toBe(
			'In this one day, the amount already in memory changed a lot. The middle item had 0 tokens in memory, and the most any item had was 922 tokens. So here a lower percentage can mean less in memory, not only a longer article. Read the token counts, not the rise or fall of the percentages.'
		);
	});

	test('a window where no item had anything in memory, or none recorded a count, prints no note', () => {
		// Every prompt read whole is 0 percent at any article length, so there is
		// nothing to explain; and a note that names two figures needs both.
		const readWhole = itemCost([held('2026-10-06', 'a-01', 0), held('2026-10-06', 'a-02', 0)], ONE_DAY);
		expect([readWhole.reusedMedian, readWhole.reusedWidest]).toEqual([0, 0]);
		expect(describeHeldPart(readWhole)).toBeNull();

		const uncounted = itemCost(
			[{ date: '2026-10-06', run_id: '2026-10-06-1', item_id: 'a-01', input_tokens: '4000' }],
			ONE_DAY
		);
		expect(uncounted.counted).toBe(1);
		expect(describeHeldPart(uncounted)).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// The subtitle over the share
// ---------------------------------------------------------------------------

test.describe('THE ORACLE: the subtitle over the share says what its own two figures show', () => {
	test('a window where 1 of 4 items read its prompt whole names that item and says the rest reused', () => {
		const cost = itemCost(
			[
				held('2026-10-06', 'a-01', 0),
				held('2026-10-06', 'a-02', 100),
				held('2026-10-06', 'a-03', 200),
				held('2026-10-06', 'a-04', 300)
			],
			ONE_DAY
		);
		expect([cost.counted, cost.readWhole]).toEqual([4, 1]);
		expect(describePromptCacheSubtitle(cost)).toBe(
			'Over this one day, 1 of 4 items had to read its prompt whole, with nothing saved from before. The rest reused part of an earlier prompt instead.'
		);
	});

	test('a window where no item read its prompt whole says every item reused part of an earlier prompt', () => {
		const cost = itemCost(
			[held('2026-10-06', 'a-01', 100), held('2026-10-06', 'a-02', 200)],
			ONE_DAY
		);
		expect([cost.counted, cost.readWhole]).toEqual([2, 0]);
		expect(describePromptCacheSubtitle(cost)).toBe(
			'Over this one day, every one of the 2 items reused part of an earlier prompt - none had to start from scratch.'
		);
	});

	test('a window where every item read its prompt whole says all of them did, with nothing saved', () => {
		const cost = itemCost(
			[held('2026-10-06', 'a-01', 0), held('2026-10-06', 'a-02', 0)],
			ONE_DAY
		);
		expect([cost.counted, cost.readWhole]).toEqual([2, 2]);
		expect(describePromptCacheSubtitle(cost)).toBe(
			'Over this one day, all 2 items had to read their prompts whole, with nothing saved from before.'
		);
	});

	test('a window with one item that reused part of an earlier prompt names the one item, not "1 items"', () => {
		const cost = itemCost([held('2026-10-06', 'a-01', 100)], ONE_DAY);
		expect([cost.counted, cost.readWhole]).toEqual([1, 0]);
		expect(describePromptCacheSubtitle(cost)).toBe(
			'Over this one day, the one item reused part of an earlier prompt - it did not start from scratch.'
		);
	});

	test('a window with one item that read its prompt whole names the one item, not "1 items"', () => {
		const cost = itemCost([held('2026-10-06', 'a-01', 0)], ONE_DAY);
		expect([cost.counted, cost.readWhole]).toEqual([1, 1]);
		expect(describePromptCacheSubtitle(cost)).toBe(
			'Over this one day, the one item had to read its prompt whole, with nothing saved from before.'
		);
	});
});

// ---------------------------------------------------------------------------
// The built console
// ---------------------------------------------------------------------------

async function hydrated(page: Page) {
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** The window the section drew, its words, and the two charts' counts and bars,
 * as attributes rather than as prose. */
async function drawn(page: Page) {
	return page.locator('[data-windowed="item-cost"]').evaluate((node) => {
		const histogram = (name: string) => {
			const chart = node.querySelector(`[data-histogram="${name}"]`);
			if (chart === null) return null;
			return {
				n: Number(chart.getAttribute('data-histogram-n')),
				bars: [...chart.querySelectorAll('[data-hist-bin]')].map((bin) =>
					Number(bin.getAttribute('data-hist-bin-n'))
				)
			};
		};
		return {
			days: Number(node.getAttribute('data-window-days')),
			says: (node.textContent ?? '').replace(/\s+/g, ' ').trim(),
			reading: histogram('reading-the-prompt'),
			writing: histogram('writing-the-summary')
		};
	});
}

test.describe('the section on the built console', () => {
	test('THE ORACLE: the share is carried by figures, and no track is drawn', async ({ page }) => {
		// The two-segment track that used to draw this share was one flat bar on
		// no time axis, and the note under it told the reader not to read its
		// direction. It is asserted gone through the named state that replaced it
		// rather than through a sentence: a panel holds exactly one carrier for
		// this share, and a rebuilt track either takes that name - and fails the
		// value - or stands beside it and fails the count.
		await page.goto('/console/');
		const panel = page.locator('[data-console-panel="How much of each prompt was already in memory"]');
		await expect(panel).toBeVisible();

		const carrier = panel.locator('[data-item-cost-share]');
		await expect(carrier, 'the share has no carrier, or has grown a second one').toHaveCount(1);
		await expect(carrier).toHaveAttribute('data-item-cost-share', 'figures');

		// The counts the row kept. Each is a printed figure inside that carrier.
		for (const name of [
			'data-item-cost-read-tokens',
			'data-item-cost-reused-tokens',
			'data-item-cost-reused-pct'
		]) {
			await expect(carrier.locator(`[${name}]`), `${name} left the panel`).toHaveCount(1);
		}
	});

	test('the section draws the window the control set, and every item it counted is in a bar', async ({
		page
	}) => {
		// It honours the shared control without claiming a pan it does not follow,
		// so the day count it prints has to be the one the control set. Which rows
		// each window counts is the oracle above, on a site the test builds; what is
		// left on the built console is that the page draws what it was handed.
		await page.goto('/console/');
		await hydrated(page);
		for (const preset of PRESETS) {
			await setWindow(page, preset);
			const marks = await drawn(page);
			expect(marks.days, 'the section is drawing a window the control did not set').toBe(preset);
			expect(marks.says, `the section never says it is showing ${preset} days`).toMatch(
				spanSaid(preset)
			);
			expect(marks.says, 'the section says "1 days"').not.toMatch(ONE_DAYS);
			for (const [name, shown] of [
				['reading', marks.reading],
				['writing', marks.writing]
			] as const) {
				if (shown === null) continue;
				// A count outside every bar is a chart quietly showing fewer items than
				// it says it counted.
				const barred = shown.bars.reduce((total, n) => total + n, 0);
				expect(barred, `${name} at ${preset} days: the bars do not sum to the count`).toBe(shown.n);
			}
		}
	});

	test('the two clocks are drawn apart, and no chart pools them', async ({ page }) => {
		// Reading and writing cost different amounts per token and are acted on
		// differently. One "model seconds" chart would hide which of them moved,
		// so the section carries two charts or it carries none.
		await page.goto('/console/');
		const section = page.locator('[data-windowed="item-cost"]');
		await expect(
			section.locator('[data-histogram="reading-the-prompt"]'),
			'the reading clock lost its own chart'
		).toHaveCount(1);
		await expect(
			section.locator('[data-histogram="writing-the-summary"]'),
			'the writing clock lost its own chart'
		).toHaveCount(1);
		// `data-histogram-n` and not `data-histogram`: the component writes the
		// second name onto the cumulative curve inside the plot as well, so counting
		// it finds two elements per chart and a section with one chart would pass.
		await expect(section.locator('[data-histogram-n]')).toHaveCount(2);
	});

	test('the reading chart counts prompts, and never calls one a summary', async ({ page }) => {
		// The histogram was written for one route and spelled its noun into three
		// strings: the bar titles, the description a screen reader is read, and the
		// cumulative axis title. The model reads the ARTICLE and writes the
		// summary, so "5 summaries read in 32 to 64 seconds" names the wrong thing.
		// Two of the three were caught by reading the built page; the third was
		// only visible in a screenshot.
		await page.goto('/console/');
		const chart = page.locator('[data-histogram="reading-the-prompt"]');
		const label = (await chart.locator('svg').getAttribute('aria-label')) ?? '';
		const said = `${await chart.innerText()} ${label}`.toLowerCase();
		expect(said, 'the reading chart never says what it is counting').toContain('prompt');
		expect(said, 'the reading chart still calls a prompt a summary').not.toContain('summar');
	});

	test('the share is printed and never drawn as a trend, and the page says why', async ({
		page
	}) => {
		// A longer article lowers the share while the part already in memory stays
		// put, so a falling line would read as the cache getting worse when the
		// articles merely got longer. The note says so only where its own two
		// figures bear it out, and the oracle above holds which words each pair of
		// figures gets. Left here is the page against itself: in every window the
		// control offers, the note names that window and is the note its own two
		// figures call for, whatever the canary holds.
		await page.goto('/console/');
		await hydrated(page);
		const note = page.locator('[data-item-cost-share-note]');
		for (const preset of PRESETS) {
			await setWindow(page, preset);
			await expect(note, `no note under the share at ${preset} days`).toHaveCount(1);
			const said = (await note.innerText()).replace(/\s+/g, ' ').trim();
			const named =
				/middle item had ([\d,]+) tokens (?:already )?in memory, and the most any item had was ([\d,]+) tokens/.exec(
					said
				);
			expect(named, `the note names no middle and largest item: ${said}`).not.toBeNull();
			const [middle, largest] = [named?.[1], named?.[2]].map((figure) =>
				Number((figure ?? '').replace(/,/g, ''))
			);
			expect(said, `the note at ${preset} days is not the one its two figures call for`).toBe(
				describeHeldPart({ days: preset, reusedMedian: middle, reusedWidest: largest })
			);
		}
	});

	test('a figure the ledger cannot answer prints a dash, never a zero', async ({ page }) => {
		// Every figure in this section is a count or a whole percent, and a zero
		// standing in for an absence is the one number nobody checks.
		await page.goto('/console/');
		const values = await page
			.locator('[data-windowed="item-cost"] .cost-figure-value')
			.allInnerTexts();
		expect(values.length, 'the figures are gone - the scan is broken').toBeGreaterThan(3);
		for (const text of values) {
			expect(text.trim(), `"${text}" is neither a count, a percent nor a dash`).toMatch(
				/^(-|\d[\d,]*%?)$/
			);
		}
	});
});
