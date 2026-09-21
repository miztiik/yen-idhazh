/** Whether the machine took the model's memory back: the fold, then the panel.
 *
 * Every figure below is recomputed here from the fixture's own item rows, never
 * read back off the module's output - an assertion against a module's own
 * answer only proves the module agrees with itself.
 *
 * Two fixtures, because neither alone states every case. The canary carries the
 * three days this panel exists to tell apart - a day that waited while the
 * machine's disk copies collapsed, a day that waited while they held steady,
 * and a day that counted and found nothing - and it is what the page under the
 * browser was built from. The rows written here carry the cases the canary
 * cannot hold at all: a day where every count sits on the first article of a
 * shard, and a run whose shards disagree about holding the memory down.
 *
 * Pure functions and the committed canary only, except where a test names a
 * page. No `$app` import and no SvelteKit alias: a spec that reaches one fails
 * the whole file at load instead of failing one test.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { diskReads, type DiskReadMarks } from '../src/lib/console/machine/disk-reads';
import { readDayShards } from '../src/lib/server/payload';

/** The canary tree the browser suite is built from. The page under the browser
 * was built from this tree, so reading the committed one would compare a
 * drawing of one ledger against the arithmetic of another. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

/** The two marks and the presets, off the committed config rather than typed
 * here - a threshold written into a test stops checking the shipped one. */
function consoleConfig(): {
	model_disk_reads_marked: number;
	model_disk_reads_named: number;
	window_presets: number[];
	default_window_days: number;
} {
	return (
		JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
		) as {
			console: {
				model_disk_reads_marked: number;
				model_disk_reads_named: number;
				window_presets: number[];
				default_window_days: number;
			};
		}
	).console;
}

function marks(): DiskReadMarks {
	const config = consoleConfig();
	return { marked: config.model_disk_reads_marked, named: config.model_disk_reads_named };
}

function canaryHealth(): Record<string, string>[] {
	return readDayShards(join(CANARY, 'item-health'), -1).rows;
}

/** One item row, with only the cells a reading needs. */
function itemRow(cells: Record<string, string | number>): Record<string, string> {
	const row: Record<string, string> = {};
	for (const [key, value] of Object.entries(cells)) row[key] = String(value);
	return row;
}

const dayOf = (health: readonly Record<string, string>[], date: string) =>
	health.filter((row) => (row.date ?? '') === date);

test.describe('the fold, as arithmetic', () => {
	test('a day counts the articles that were not first on their shard, and only those', () => {
		// The exclusion is the whole reason this reading is about the machine and
		// not about a server starting up, so it is checked against the canary's own
		// rows rather than against a number written here: the total is summed in
		// this test from the cells, and the rows sitting first are summed
		// separately so a fold that quietly included them cannot pass.
		const health = canaryHealth();
		const loud = health
			.map((row) => (row.date ?? ''))
			.filter((date, at, all) => all.indexOf(date) === at)
			.sort()
			.at(-1) as string;

		const rows = dayOf(health, loud).filter((row) => (row.llama_major_faults ?? '') !== '');
		expect(rows.length, 'the canary day carries no count to fold').toBeGreaterThan(0);

		const away = rows.filter((row) => Number(row.item_index ?? '0') !== 0);
		const first = rows.filter((row) => Number(row.item_index ?? '0') === 0);
		expect(first.length, 'nothing sits first on a shard, so the exclusion is untested').toBeGreaterThan(0);
		const expected = away.reduce((total, row) => total + Number(row.llama_major_faults), 0);
		const everything = rows.reduce((total, row) => total + Number(row.llama_major_faults), 0);

		const day = diskReads(dayOf(health, loud), marks()).days[0];
		expect(day.reads, 'the day does not sum the articles it counted').toBe(expected);
		expect(day.counted).toBe(away.length);
		expect(day.excluded).toBe(first.length);
		// The two answers are genuinely different numbers here, so a fold that
		// forgot the exclusion would be caught rather than coincidentally right.
		expect(everything).not.toBe(expected);
	});

	test('a row that never said where in its shard it sat is excluded, not counted as second', () => {
		// A count with no seat cannot be placed either side of the rule, and
		// guessing would put a starting server's own reads into the total.
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-02', run_id: 'r1', llama_major_faults: 4000 }),
				itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 11 })
			],
			marks()
		);
		expect(reading.days[0].reads).toBe(11);
		expect(reading.days[0].excluded).toBe(1);
	});

	test('a day nothing counted is unrecorded, and unrecorded is not a zero', () => {
		const reading = diskReads(
			[itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1 })],
			marks()
		);
		expect(reading.days[0].reads).toBeNull();
		expect(reading.days[0].state).toBe('unrecorded');
		expect(reading.recorded).toBe(0);
	});

	test('a day that counted and found nothing is quiet, which is the opposite fact', () => {
		const reading = diskReads(
			[itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 0 })],
			marks()
		);
		expect(reading.days[0].reads).toBe(0);
		expect(reading.days[0].state).toBe('quiet');
		expect(reading.recorded).toBe(1);
	});

	test('a day only fires once it reaches the mark the config sets', () => {
		const { marked } = marks();
		const at = (waits: number) =>
			diskReads(
				[itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: waits })],
				{ marked, named: marked }
			).days[0].state;
		expect(at(marked - 1)).toBe('quiet');
		expect(at(marked)).toBe('fired');
	});

	test('the disk copies fall as a share of that day\'s own high, not of the machine', () => {
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, os_mem_cached_bytes: 8_000_000_000 }),
				itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 2, os_mem_cached_bytes: 2_000_000_000 })
			],
			marks()
		);
		expect(reading.days[0].copiesHigh).toBe(8_000_000_000);
		expect(reading.days[0].copiesLow).toBe(2_000_000_000);
		expect(reading.days[0].copiesFell).toBeCloseTo(0.75, 6);
	});

	test('a day that recorded no copies at all reports null, which draws no mark', () => {
		const reading = diskReads(
			[itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 9 })],
			marks()
		);
		expect(reading.days[0].copiesFell).toBeNull();
	});

	test('the setting is counted once a run, and a run that said nothing is silent', () => {
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-02', run_id: 'held', shard: 0, weights_pinned: 'True' }),
				itemRow({ date: '2026-09-02', run_id: 'held', shard: 1, weights_pinned: 'True' }),
				itemRow({ date: '2026-09-02', run_id: 'loose', shard: 0, weights_pinned: 'False' }),
				itemRow({ date: '2026-09-02', run_id: 'quiet-run', shard: 0 })
			],
			marks()
		);
		expect(reading.pinning).toEqual({ held: 1, loose: 1, silent: 1 });
	});

	test('a run whose shards disagree is loose - one of them could be taken from', () => {
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-02', run_id: 'split', shard: 0, weights_pinned: 'True' }),
				itemRow({ date: '2026-09-02', run_id: 'split', shard: 1, weights_pinned: 'False' })
			],
			marks()
		);
		expect(reading.pinning).toEqual({ held: 0, loose: 1, silent: 0 });
	});

	test('the worst day is the loudest one that reached the naming mark, not the newest', () => {
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-01', run_id: 'r1', item_index: 1, llama_major_faults: 900 }),
				itemRow({ date: '2026-09-02', run_id: 'r2', item_index: 1, llama_major_faults: 5 })
			],
			{ marked: 1, named: 100 }
		);
		expect(reading.worst?.date).toBe('2026-09-01');
		expect(reading.reads).toBe(905);
		expect(reading.fired).toBe(2);
	});

	test('no day reaching the naming mark leaves the panel with no day to name', () => {
		const reading = diskReads(
			[itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 5 })],
			{ marked: 1, named: 100 }
		);
		expect(reading.worst).toBeNull();
		expect(reading.days[0].state).toBe('fired');
	});
});

const DESKTOP = { width: 1280, height: 900 };

async function hydrated(page: Page) {
	await expect(
		page.locator(`[data-window-preset="${consoleConfig().default_window_days}"] input`)
	).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** Every tile of the upper strip, as the reader is given it. */
async function readTiles(page: Page) {
	return page.locator('[data-disk-read-day]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			date: node.getAttribute('data-disk-read-day') ?? '',
			state: node.getAttribute('data-disk-read-state') ?? '',
			reads: node.getAttribute('data-disk-reads') ?? '',
			mark: (node.querySelector('span') as HTMLElement | null)?.getBoundingClientRect().height ?? 0,
			dashed: getComputedStyle(node).borderTopStyle,
			fill: getComputedStyle(node.querySelector('span') as HTMLElement).backgroundColor
		}))
	);
}

test.describe('the panel', () => {
	test('THE ORACLE: three states draw three marks a reader can tell apart', async ({ page }) => {
		// The finding this closes is a strip where a day nobody measured and a day
		// that measured nothing look identical, which would have an operator close
		// a console that never had an instrument. Read off the drawn box and the
		// drawn colour rather than off the class, because a class nothing styles
		// passes an assertion and still draws one grey strip.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);
		await setWindow(page, Math.max(...consoleConfig().window_presets));

		const tiles = await readTiles(page);
		const byState = new Map(tiles.map((tile) => [tile.state, tile]));
		expect(
			[...byState.keys()].sort(),
			'the fixture no longer reaches all three states, so this oracle asserts nothing'
		).toEqual(['fired', 'quiet', 'unrecorded']);

		const unrecorded = byState.get('unrecorded');
		const quiet = byState.get('quiet');
		const fired = byState.get('fired');
		expect(unrecorded?.reads, 'an unrecorded day is printing a number').toBe('');
		expect(unrecorded?.dashed, 'an unrecorded day draws no outline of its own').toBe('dashed');
		expect(quiet?.fill, 'a quiet day and a loud one draw the same colour').not.toBe(fired?.fill);
		expect(fired?.mark, 'a loud day does not draw a taller mark than a quiet one').toBeGreaterThan(
			quiet?.mark ?? 0
		);
	});

	test('THE ORACLE: two days that both fired are told apart by the strip underneath', async ({
		page
	}) => {
		// Susan's ruling: the copies reading is drawn BESIDE the count and never
		// instead of it, because the same count means two different things over a
		// machine that emptied its copies and one that did not - and the two have
		// different fixes. A panel that drew only the count would pass every
		// assertion above and leave an operator tuning the wrong thing.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);

		const fired = (await readTiles(page)).filter((tile) => tile.state === 'fired');
		expect(fired.length, 'the fixture no longer has two days that both fired').toBeGreaterThan(1);

		const copies = await page.locator('[data-disk-copies-day]').evaluateAll((nodes) =>
			nodes.map((node) => ({
				date: node.getAttribute('data-disk-copies-day') ?? '',
				fell: node.getAttribute('data-disk-copies-fell') ?? '',
				mark:
					(node.querySelector('span') as HTMLElement | null)?.getBoundingClientRect().height ?? 0
			}))
		);
		const beside = fired.map(
			(tile) => copies.find((copy) => copy.date === tile.date) as (typeof copies)[number]
		);
		expect(
			beside.every((copy) => copy !== undefined),
			'a day on the upper strip has no day under it, so the axes have drifted'
		).toBe(true);

		const falls = beside.map((copy) => Number(copy.fell));
		expect(Math.max(...falls), 'no day the machine emptied, so the pair is untested').toBeGreaterThan(
			0.1
		);
		expect(Math.min(...falls), 'no steady day, so the pair is untested').toBeLessThan(0.01);
		// Same state above, different drawing below: that is the whole claim.
		const tall = beside.find((copy) => Number(copy.fell) > 0.1);
		const flat = beside.find((copy) => Number(copy.fell) < 0.01);
		expect(tall?.mark ?? 0, 'the two days draw the same mark under them').toBeGreaterThan(
			flat?.mark ?? 0
		);
	});

	test('THE ORACLE: the strip keeps its height when what it holds changes', async ({ page }) => {
		// A panel that grew a block of red the first time something went wrong
		// would move every panel under it down the page on the worst morning of
		// the year. Measured across two spans that hold different marks, because
		// a height read once says nothing about whether it is fixed.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);

		const presets = consoleConfig().window_presets;
		const heightAt = async (days: number) => {
			await setWindow(page, days);
			const box = await page.locator('[data-disk-read-track]').boundingBox();
			return { height: box?.height ?? 0, tiles: await page.locator('[data-disk-read-day]').count() };
		};

		const narrow = await heightAt(Math.min(...presets));
		const wide = await heightAt(Math.max(...presets));
		expect(wide.tiles, 'both spans hold the same days, so nothing changed').toBeGreaterThan(
			narrow.tiles
		);
		expect(wide.height, 'the strip changed height when its marks changed').toBe(narrow.height);
	});

	test('the pinning line is read off the runs, not written into the panel', async ({ page }) => {
		// Decision 1 of this row: the setting is printed from the run's own record.
		// A panel that printed what it expected would go on saying it the morning
		// after somebody changed the model. Checked against the ledger rather than
		// against the words, so it fails when the fixture changes and the page
		// does not.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);
		await setWindow(page, Math.max(...consoleConfig().window_presets));

		const said = new Set(
			canaryHealth()
				.map((row) => row.weights_pinned ?? '')
				.filter((value) => value !== '')
		);
		expect(said, 'the canary records no setting, so this oracle asserts nothing').toEqual(
			new Set(['True', 'False'])
		);

		const line = page.locator('[data-disk-read-pinning]');
		await expect(line).toHaveAttribute('data-disk-read-pinning', 'mixed');
		await expect(line).toContainText('held the model');
	});

	test('the panel leads with the finding, and the finding names the worst day', async ({
		page
	}) => {
		// Decision 5 of this row: the panel says what it found, and the strip under
		// it is the evidence. The day it names is recomputed here off the days the
		// page actually drew, so the assertion follows the fixture instead of
		// pinning a date that goes stale the next time the canary moves.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);

		const drawn = await page.locator('[data-disk-read-day]').evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-disk-read-day') ?? '')
		);
		expect(drawn.length, 'the panel drew no days to read').toBeGreaterThan(0);
		const worst = diskReads(
			canaryHealth().filter((row) => drawn.includes(row.date ?? '')),
			marks()
		).worst;
		expect(worst, 'no day reached the naming mark on the default span').not.toBeNull();

		const finding = page.locator('[data-disk-read-finding]');
		await expect(finding).toHaveAttribute('data-disk-read-finding', 'fired');
		await expect(finding).toContainText(String(worst?.date));
	});
});
