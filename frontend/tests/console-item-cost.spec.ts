import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { itemCost } from '../src/lib/console/item-cost';

/**
 * What one item cost the model, checked against the file the page was drawn
 * from rather than against the label beside the mark.
 *
 * The oracle is the second half of this file. Every figure the section draws is
 * re-derived here from the committed projection - a second implementation, with
 * its own loops and its own arithmetic, that never calls the reducer the page
 * uses. A spec that compared a bar against the number printed under it would
 * pass on any reducer at all, because both come from one call.
 *
 * The first half is the reducer as a pure function, over rows written by hand
 * for the states the fixture cannot reach: a cell that is empty rather than
 * zero, a window where the two clocks answer for different numbers of items,
 * and a rate that must be pooled rather than averaged.
 */

/** The tree the site was built from. The suite builds from the canaries. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [7, 14, 30, 90];
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

/** The projection the built tree published, read cell by cell.
 *
 * The canary's own copy, written by `idhazh publish_telemetry` from the canary
 * ledger - the same producer and the same shape as the committed months, over a
 * fixture a test may read (`backend/tests/test_archive_readers.py`).
 */
function projection(): Record<string, string>[] {
	const dir = join(CANARY, 'state', 'telemetry');
	if (!existsSync(dir)) return [];
	const rows: Record<string, string>[] = [];
	for (const name of readdirSync(dir).filter((file) => file.endsWith('.csv'))) {
		const lines = readFileSync(join(dir, name), 'utf8').split('\n').filter(Boolean);
		const columns = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cells = line.split(',');
			const found: Record<string, string> = {};
			columns.forEach((column, at) => (found[column] = cells[at] ?? ''));
			rows.push(found);
		}
	}
	return rows;
}

/** A number, or null for an empty cell. Written out rather than imported: the
 * oracle may share no arithmetic with the thing it checks. */
function value(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const parsed = Number(raw);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The window the section says it is drawing, from the days the page says it
 * drew. It ends on the newest day the projection holds and runs back N days. */
function span(days: number): { start: string; end: string } {
	const dates = [...new Set(projection().map((row) => row.date))].filter(Boolean).sort();
	const end = dates[dates.length - 1];
	const at = new Date(`${end}T00:00:00Z`);
	at.setUTCDate(at.getUTCDate() - (days - 1));
	return { start: at.toISOString().slice(0, 10), end };
}

/** Every doubling bar a set of millisecond values falls into, counted by hand.
 *
 * A deliberately clumsy second implementation: it walks the edges rather than
 * generating them, and it counts with a loop rather than a filter. If it agreed
 * with the page by sharing an expression it would not be an oracle.
 */
function barsOf(values: number[]): Map<number, number> {
	const found = new Map<number, number>();
	for (const ms of values) {
		const seconds = ms / 1000;
		let from = 0;
		let to = 1;
		while (seconds >= to) {
			from = to;
			to = to * 2;
		}
		found.set(from, (found.get(from) ?? 0) + 1);
	}
	return found;
}

function sorted(values: number[]): number[] {
	return [...values].sort((a, b) => a - b);
}

/** The value at a fraction of the way through, interpolated. */
function at(values: number[], fraction: number): number {
	const list = sorted(values);
	if (list.length === 1) return list[0];
	const position = (list.length - 1) * fraction;
	const below = Math.floor(position);
	const above = Math.ceil(position);
	return list[below] + (list[above] - list[below]) * (position - below);
}

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

/** Every number the section drew, as attributes rather than as prose. */
async function drawn(page: Page) {
	return page.locator('[data-windowed="item-cost"]').evaluate((node) => {
		const attr = (name: string): string | null => {
			const held = node.querySelector(`[${name}]`);
			return held === null ? null : held.getAttribute(name);
		};
		const histogram = (name: string) => {
			const chart = node.querySelector(`[data-histogram="${name}"]`);
			if (chart === null) return null;
			return {
				n: Number(chart.getAttribute('data-histogram-n')),
				bins: [...chart.querySelectorAll('[data-hist-bin]')].map((bin) => ({
					from: Number(bin.getAttribute('data-hist-bin')),
					n: Number(bin.getAttribute('data-hist-bin-n'))
				})),
				rules: Object.fromEntries(
					[...chart.querySelectorAll('[data-hist-rule]')].map((rule) => [
						rule.getAttribute('data-hist-rule') ?? '',
						Number(rule.getAttribute('data-hist-rule-seconds'))
					])
				)
			};
		};
		return {
			days: Number(node.getAttribute('data-window-days')),
			says: (node.textContent ?? '').replace(/\s+/g, ' ').trim(),
			reading: histogram('reading-the-prompt'),
			writing: histogram('writing-the-summary'),
			rows: attr('data-item-cost-rows'),
			promptTokens: attr('data-item-cost-prompt-tokens'),
			writtenTokens: attr('data-item-cost-written-tokens'),
			itemReusedPct: attr('data-item-cost-item-reused-pct'),
			readWhole: attr('data-item-cost-read-whole'),
			readTokens: attr('data-item-cost-read-tokens'),
			reusedTokens: attr('data-item-cost-reused-tokens'),
			reusedPct: attr('data-item-cost-reused-pct'),
			msPerReadToken: attr('data-item-cost-ms-per-read-token'),
			msPerWrittenToken: attr('data-item-cost-ms-per-written-token'),
			writeRatio: attr('data-item-cost-write-ratio')
		};
	});
}

test.describe('the section on the built console', () => {
	test('THE ORACLE: every bar and every rule is the projection, re-derived', async ({ page }) => {
		const rows = projection();
		expect(rows.length, 'the canary projection is empty - the read is broken').toBeGreaterThan(0);

		await page.goto('/console/');
		await hydrated(page);

		for (const preset of PRESETS) {
			await setWindow(page, preset);
			const window = span(preset);
			const inWindow = rows.filter((row) => row.date >= window.start && row.date <= window.end);

			const readMs: number[] = [];
			const writeMs: number[] = [];
			for (const row of inWindow) {
				const prefill = value(row, 'prefill_ms');
				const decode = value(row, 'decode_ms');
				if (prefill !== null) readMs.push(prefill);
				if (decode !== null) writeMs.push(decode);
			}

			const marks = await drawn(page);
			expect(marks.days, `the section is drawing a window the control did not set`).toBe(preset);
			// The window really narrows the rows rather than only the label. The canary
			// holds days at 7, 30 and 90 days out, so the three presets read three
			// different counts and a section that filtered nothing would fail here.
			expect(
				Number(marks.rows),
				`the section at ${preset} days counted rows the window does not hold`
			).toBe(inWindow.length);

			for (const [name, values, shown] of [
				['reading', readMs, marks.reading],
				['writing', writeMs, marks.writing]
			] as const) {
				if (shown === null) continue;
				expect(shown.n, `${name} at ${preset} days drew a count the projection does not hold`).toBe(
					values.length
				);
				const expected = barsOf(values);
				for (const bin of shown.bins) {
					expect(
						bin.n,
						`${name} at ${preset} days: the bar from ${bin.from} s holds the wrong count`
					).toBe(expected.get(bin.from) ?? 0);
				}
				// Every value has to land in a drawn bar, or the chart is quietly
				// showing fewer items than it says it counted.
				const drawnTotal = shown.bins.reduce((total, bin) => total + bin.n, 0);
				expect(drawnTotal, `${name} at ${preset} days: bars do not sum to the count`).toBe(
					values.length
				);
				expect(
					shown.rules.median,
					`${name} at ${preset} days: the median rule is not the median of the values`
				).toBe(Math.round(at(values, 0.5) / 1000));
				expect(
					shown.rules.p95,
					`${name} at ${preset} days: the 95th rule is not the 95th of the values`
				).toBe(Math.round(at(values, 0.95) / 1000));
			}
		}
	});

	test('THE ORACLE: every token figure is the projection, re-derived', async ({ page }) => {
		const rows = projection();
		await page.goto('/console/');
		await hydrated(page);

		for (const preset of PRESETS) {
			await setWindow(page, preset);
			const window = span(preset);
			const inWindow = rows.filter((row) => row.date >= window.start && row.date <= window.end);

			const prompts: number[] = [];
			const written: number[] = [];
			const shares: number[] = [];
			let read = 0;
			let reused = 0;
			let whole = 0;
			let readMs = 0;
			let writeMs = 0;
			let writtenTokens = 0;
			for (const line of inWindow) {
				const input = value(line, 'input_tokens');
				const output = value(line, 'output_tokens');
				const cached = value(line, 'cached_tokens');
				const prefill = value(line, 'prefill_ms');
				const decode = value(line, 'decode_ms');
				if (input !== null) {
					prompts.push(input);
					read = read + input - (cached ?? 0);
					if (cached !== null) {
						reused = reused + cached;
						if (cached === 0) whole = whole + 1;
						shares.push(Math.round((cached / input) * 100));
					}
					if (prefill !== null) readMs = readMs + prefill;
				}
				if (output !== null) {
					written.push(output);
					if (decode !== null) {
						writeMs = writeMs + decode;
						writtenTokens = writtenTokens + output;
					}
				}
			}
			if (prompts.length === 0) continue;

			const marks = await drawn(page);
			const say = (what: string) => `${what} at ${preset} days`;
			expect(Number(marks.promptTokens), say('the middle prompt')).toBe(at(prompts, 0.5));
			expect(Number(marks.writtenTokens), say('the middle summary')).toBe(at(written, 0.5));
			expect(Number(marks.readTokens), say('prompt tokens read')).toBe(read);
			expect(Number(marks.reusedTokens), say('prompt tokens already in memory')).toBe(reused);
			expect(Number(marks.reusedPct), say("the window's share")).toBe(
				Math.round((reused / (read + reused)) * 100)
			);
			expect(Number(marks.itemReusedPct), say("the middle item's share")).toBe(at(shares, 0.5));
			expect(Number(marks.readWhole), say('items read whole')).toBe(whole);
			expect(Number(marks.msPerReadToken), say('milliseconds a read token costs')).toBe(
				Math.round(readMs / read)
			);
			expect(Number(marks.msPerWrittenToken), say('milliseconds a written token costs')).toBe(
				Math.round(writeMs / writtenTokens)
			);
			expect(marks.writeRatio, say('the ratio between them')).toBe(
				(writeMs / writtenTokens / (readMs / read)).toFixed(1)
			);
		}
	});

	test('the section names the window it drew, at every preset', async ({ page }) => {
		// It honours the shared control without claiming a pan it does not follow,
		// so the day count it prints has to be the one the control set.
		await page.goto('/console/');
		await hydrated(page);
		for (const preset of PRESETS) {
			await setWindow(page, preset);
			const marks = await drawn(page);
			expect(marks.says, `the section never says it is showing ${preset} days`).toContain(
				`${preset} days`
			);
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

	test('the share is printed and never drawn as a trend, and the page says why', async ({
		page
	}) => {
		// The held part is nearly fixed and the prompt is not, so a falling line
		// would read as the cache getting worse when the articles merely got
		// longer. That is the one wrong action this panel could cause.
		await page.goto('/console/');
		const note = page.locator('[data-item-cost-share-note]');
		await expect(note).toHaveCount(1);
		await expect(note).toContainText('follows the article');

		const rows = projection().filter((row) => value(row, 'cached_tokens') !== null);
		const held = rows.map((row) => value(row, 'cached_tokens') as number);
		const widest = Math.max(...held);
		const middle = at(held, 0.5);
		expect(
			widest - middle,
			'the held part has started moving, so this panel needs re-deciding'
		).toBeLessThan(middle);
		await expect(note).toContainText(String(Math.round(middle)));
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
