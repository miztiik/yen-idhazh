/** Whether the machine took the model's memory back: the fold, then the panel.
 *
 * The fold tests write the rows they read and write out the answers those rows
 * must produce. The browser tests read only the page and the attributes it
 * publishes beside the drawn figures.
 *
 * Pure functions and the rendered page only. No `$app` import and no SvelteKit
 * alias: a spec that reaches one fails the whole file at load instead of
 * failing one test.
 */

import { expect, test, type Page } from './support/browser';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { grouped } from '../src/lib/charts/series';
import { diskReads, type DiskReadMarks } from '../src/lib/console/machine/disk-reads';

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

/** One item row, with only the cells a reading needs. */
function itemRow(cells: Record<string, string | number>): Record<string, string> {
	const row: Record<string, string> = {};
	for (const [key, value] of Object.entries(cells)) row[key] = String(value);
	return row;
}

test.describe('the fold, as arithmetic', () => {
	test('a day counts the articles that were not first on their shard, and only those', () => {
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 0, llama_major_faults: 100 }),
				itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 1, llama_major_faults: 11 }),
				itemRow({ date: '2026-09-02', run_id: 'r1', item_index: 2, llama_major_faults: 22 }),
				itemRow({ date: '2026-09-02', run_id: 'r2', llama_major_faults: 300 })
			],
			marks()
		);
		const day = reading.days[0];
		expect(day.reads, 'the day summed a first or unseated article').toBe(33);
		expect(day.counted, 'the day counted the wrong articles').toBe(2);
		expect(day.excluded, 'the day did not report the articles it left out').toBe(2);
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
				itemRow({ date: '2026-09-02', run_id: 'held', machine_shard: 0, weights_pinned: 'True' }),
				itemRow({ date: '2026-09-02', run_id: 'held', machine_shard: 1, weights_pinned: 'True' }),
				itemRow({ date: '2026-09-02', run_id: 'loose', machine_shard: 0, weights_pinned: 'False' }),
				itemRow({ date: '2026-09-02', run_id: 'quiet-run', machine_shard: 0 })
			],
			marks()
		);
		expect(reading.pinning).toEqual({ held: 1, loose: 1, silent: 1 });
	});

	test('a run whose shards disagree is loose - one of them could be taken from', () => {
		const reading = diskReads(
			[
				itemRow({ date: '2026-09-02', run_id: 'split', machine_shard: 0, weights_pinned: 'True' }),
				itemRow({ date: '2026-09-02', run_id: 'split', machine_shard: 1, weights_pinned: 'False' })
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

	test('the pinning line agrees with the state the page publishes beside it', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);
		await setWindow(page, Math.max(...consoleConfig().window_presets));

		const line = page.locator('[data-disk-read-pinning]');
		const state = await line.getAttribute('data-disk-read-pinning');
		expect(state, 'the pinning line published no state').toMatch(/^(silent|held|loose|mixed)$/);
		const words = await line.innerText();
		if (state === 'silent') {
			expect(words, 'the silent state does not name the missing setting').toContain(
				'No run in these'
			);
			expect(words).toContain('unknown');
		} else if (state === 'held') {
			expect(words, 'the held state does not say the machine was not allowed to take memory').toContain(
				'not allowed'
			);
		} else if (state === 'loose') {
			expect(words, 'the loose state does not say the machine was free to take memory').toContain(
				'free to take'
			);
		} else {
			expect(words, 'the mixed state does not name both run settings').toContain('held');
			expect(words).toContain('did not');
		}
	});

	test('the panel leads with the finding, and the finding follows the published worst day', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await hydrated(page);

		const finding = page.locator('[data-disk-read-finding]');
		const state = await finding.getAttribute('data-disk-read-finding');
		expect(state, 'the finding published no state').toMatch(/^(empty|unrecorded|quiet|fired)$/);
		const words = await finding.innerText();

		if (state === 'fired') {
			const tiles = await page.locator('[data-disk-read-day]').evaluateAll((nodes) =>
				nodes.map((node) => ({
					date: node.getAttribute('data-disk-read-day') ?? '',
					reads: Number(node.getAttribute('data-disk-reads') ?? '0')
				}))
			);
			const worst = tiles.reduce((loudest, tile) =>
				tile.reads >= loudest.reads ? tile : loudest
			);
			expect(words, 'the fired finding does not name the worst published day').toContain(
				worst.date
			);
			expect(words, 'the fired finding does not name the worst published count').toContain(
				grouped(worst.reads)
			);
		} else if (state === 'empty') {
			expect(words, 'the empty finding does not say there is nothing to say').toContain(
				'nothing to say'
			);
		} else if (state === 'unrecorded') {
			expect(words, 'the unrecorded finding does not name the missing instrument').toContain(
				'missing instrument'
			);
		} else {
			expect(words, 'the quiet finding does not say the model never waited').toContain(
				'never once'
			);
		}
	});
});
