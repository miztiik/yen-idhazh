/** Do the three machine panels draw what the ruling requires, in a browser?
 *
 * The assertions here are the ones a unit test cannot make: that the colour a
 * machine takes is the same at every window preset, that no two named machines
 * share a stop, that the name is on the row as TEXT in both themes, and that a
 * card really draws the flags a machine does not have rather than omitting them.
 *
 * **The canary is the fixture, and it was built for exactly two of these.** One
 * machine reports none of the watched AVX-512 entries and one reports every
 * watched flag; one probe used a buffer under its own L3. Neither state is one
 * the committed archive can be relied on to hold.
 *
 * `frontend/scripts/build-canary.mjs` writes the machine record this reads, so
 * the numbers below are recomputed from that file rather than from the page.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const REPO = resolve(process.cwd(), '..');

const APPEARANCE = JSON.parse(
	readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
) as { console: { fleet_min_rows: number; machine_colour_stops: number; window_presets: number[] } };

const WATCHED = (
	JSON.parse(readFileSync(join(REPO, 'schemas', 'machine-panels.schema.json'), 'utf8')) as {
		$defs: { WatchedFlag: { enum: string[] } };
	}
).$defs.WatchedFlag.enum;

/** The canary's own counters ledger, read straight off disk.
 *
 * The page's arithmetic is checked against this rather than against itself: an
 * oracle that reads the module it is testing proves only that the module agrees
 * with itself.
 */
function canaryCounters(): Record<string, string>[] {
	const text = readFileSync(join(REPO, 'backend', 'var', 'canary', 'state', 'runtime-counters.csv'), 'utf8');
	const [header, ...lines] = text.trim().split('\n');
	const columns = header.split(',');
	return lines.map((line) => {
		const cells = line.split(',');
		return Object.fromEntries(columns.map((name, index) => [name, cells[index] ?? '']));
	});
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', String(days));
}

test.describe('reading against writing, machine by machine', () => {
	test('one group a machine, and no element carries a rate pooled over all shards', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel="Reading against writing, machine by machine"]');
		await expect(panel).toBeVisible();

		const rows = canaryCounters();
		const newest = rows
			.filter((row) => row.prompt_seconds_total !== '' && row.tokens_predicted_seconds_total !== '')
			.sort((a, b) => b.run_id.localeCompare(a.run_id))[0];
		const ofRun = rows.filter(
			(row) =>
				row.run_id === newest.run_id &&
				row.prompt_tokens_total !== '' &&
				row.prompt_seconds_total !== '' &&
				row.tokens_predicted_total !== '' &&
				row.tokens_predicted_seconds_total !== ''
		);
		const kinds = new Set(ofRun.map((row) => row.cpu_model));
		expect(kinds.size, 'the canary run must draw more than one kind').toBeGreaterThan(1);

		const groups = panel.locator('[data-machine-group]');
		await expect(groups).toHaveCount(kinds.size);

		// The headline names a machine. Nothing on the panel offers a rate over
		// every shard of the run.
		const headline = panel.locator('[data-machine-split-headline]');
		if ((await headline.count()) > 0) {
			const named = await headline.getAttribute('data-machine-split-headline');
			const keys = await groups.evaluateAll((nodes) =>
				nodes.map((node) => node.getAttribute('data-machine-group'))
			);
			expect(keys).toContain(named);
		}
		await expect(panel.locator('[data-reading-writing-sentence]')).toHaveCount(0);
		await expect(panel.locator('[data-reading-writing]')).toHaveCount(0);
	});

	test('every rate in a group recomputes from that machine shards alone', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel="Reading against writing, machine by machine"]');
		const rows = canaryCounters();
		const newestRun = await panel.evaluate(
			(node) => node.closest('[data-machine-split]')?.getAttribute('data-machine-split') ?? ''
		);
		expect(newestRun).not.toBe('');

		const byName = new Map<string, { tokens: number; seconds: number }>();
		for (const row of rows) {
			if (row.run_id !== newestRun) continue;
			if (row.prompt_tokens_total === '' || row.prompt_seconds_total === '') continue;
			if (row.tokens_predicted_total === '' || row.tokens_predicted_seconds_total === '') continue;
			const held = byName.get(row.cpu_model) ?? { tokens: 0, seconds: 0 };
			held.tokens += Number(row.prompt_tokens_total);
			held.seconds += Number(row.prompt_seconds_total);
			byName.set(row.cpu_model, held);
		}

		const printed = await panel.locator('[data-machine-rates]').allInnerTexts();
		for (const [model, sums] of byName) {
			if (sums.seconds === 0) continue;
			const expected = (sums.tokens / sums.seconds).toFixed(2);
			expect(
				printed.some((text) => text.includes(`${expected} tokens a second`)),
				`no group printed ${expected} for ${model || 'the unrecorded machine'}`
			).toBe(true);
		}
	});
});

test.describe('the colour a machine takes', () => {
	test('is the same at every window preset', async ({ page }) => {
		await page.goto('/console/machine/');
		const read = async () =>
			page.locator('[data-machine-group]').evaluateAll((nodes) =>
				nodes.map(
					(node) =>
						`${node.getAttribute('data-machine-group')}:${getComputedStyle(node).borderInlineStartColor}`
				)
			);
		const first = await read();
		expect(first.length).toBeGreaterThan(0);
		for (const preset of APPEARANCE.console.window_presets) {
			await setWindow(page, preset);
			expect(await read(), `the edge moved at ${preset} days`).toEqual(first);
		}
	});

	test('no two named machines share a stop, and the grey is only an absence', async ({ page }) => {
		await page.goto('/console/machine/');
		const marks = await page
			.locator('[data-machine-group], [data-machine-card]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					name: node.getAttribute('data-machine-name') ?? '',
					stop: Number(node.getAttribute('data-machine-stop')),
					unrecorded: node.getAttribute('data-machine-unrecorded') === 'yes'
				}))
			);
		expect(marks.length).toBeGreaterThan(0);

		const named = marks.filter((mark) => !mark.unrecorded);
		const byName = new Map<string, Set<number>>();
		for (const mark of named) {
			expect(mark.stop, 'a named machine took the reserved grey').toBeLessThan(8);
			expect(mark.stop).toBeLessThanOrEqual(APPEARANCE.console.machine_colour_stops);
			byName.set(mark.name, (byName.get(mark.name) ?? new Set()).add(mark.stop));
		}
		// One name, one stop - and one stop, one name.
		for (const [name, stops] of byName) {
			expect(stops.size, `${name} took two stops`).toBe(1);
		}
		const stops = [...byName.values()].map((set) => [...set][0]);
		expect(new Set(stops).size, 'two named machines share a stop').toBe(stops.length);

		for (const mark of marks.filter((one) => one.unrecorded)) {
			expect(mark.stop).toBe(8);
			expect(mark.name).toBe('Machine not recorded');
		}
	});

	test('every mark carries its machine name as text, in both themes', async ({ page }) => {
		for (const theme of ['light', 'dark']) {
			await page.goto('/console/machine/');
			await page.evaluate((mode) => document.documentElement.setAttribute('data-theme', mode), theme);
			const named = await page
				.locator('[data-machine-group], [data-machine-card]')
				.evaluateAll((nodes) =>
					nodes.map((node) => ({
						attribute: node.getAttribute('data-machine-name') ?? '',
						text: (node.textContent ?? '').replace(/\s+/g, ' ').trim()
					}))
				);
			expect(named.length).toBeGreaterThan(0);
			for (const mark of named) {
				expect(mark.attribute, `a mark carried no name in ${theme}`).not.toBe('');
				expect(mark.text, `${mark.attribute} is not in words in ${theme}`).toContain(
					mark.attribute
				);
			}
		}
	});
});

test.describe('the machines this run drew', () => {
	test('a card draws every watched flag, and absence is drawn rather than omitted', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel="The machines this run drew"]');
		await expect(panel).toBeVisible();
		const cards = panel.locator('[data-machine-card]');
		const count = await cards.count();
		expect(count).toBeGreaterThan(0);

		let sawAnAbsence = false;
		for (let index = 0; index < count; index += 1) {
			const card = cards.nth(index);
			const chips = card.locator('[data-machine-flag]');
			const drawn = await chips.count();
			if (drawn === 0) {
				// A card off the counters alone says so instead of drawing twelve
				// outlines, which would read as a machine with no flags at all.
				await expect(card.locator('[data-machine-flags="none"]')).toBeVisible();
				continue;
			}
			expect(drawn, 'a card drew some of the watched flags').toBe(WATCHED.length);
			expect(
				await chips.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-machine-flag')))
			).toEqual(WATCHED);
			const absent = await card.locator('[data-machine-flag-present="no"]').count();
			if (absent > 0) sawAnAbsence = true;
		}
		expect(sawAnAbsence, 'no card drew an absent flag - the fixture is wrong').toBe(true);
	});

	test('the bandwidth reading and its buffer are one element, and cache is called out', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel="The machines this run drew"]');
		const readings = panel.locator('[data-machine-bandwidth]');
		const count = await readings.count();
		expect(count).toBeGreaterThan(0);
		let sawCacheWarning = false;
		for (let index = 0; index < count; index += 1) {
			const text = (await readings.nth(index).innerText()).trim();
			if (text.startsWith('Bandwidth was not measured')) continue;
			expect(text, 'the rate and its buffer are not in one element').toMatch(
				/GiB\/s.*MiB buffer/
			);
			if (text.includes('this measured cache, not memory')) sawCacheWarning = true;
		}
		expect(sawCacheWarning, 'no card warned that the probe measured cache').toBe(true);
	});

	test('the disclosure is a native details and is closed at rest', async ({ page }) => {
		await page.goto('/console/machine/');
		const where = page.locator('[data-machine-where]').first();
		if ((await where.count()) === 0) return;
		expect(await where.evaluate((node) => node.tagName)).toBe('DETAILS');
		expect(await where.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
		await expect(where.locator('summary')).toHaveText('Where the platform put this');
	});
});

test.describe('what the platform has been giving us', () => {
	test('under the threshold it lists the counts and draws no bar', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel="What the platform has been giving us"]');
		await expect(panel).toBeVisible();
		const list = panel.locator('[data-fleet-list]');
		if ((await list.count()) === 0) {
			// At or above the threshold the panel draws bars instead, which is the
			// other arm and is asserted over built rows in `console-fleet.spec.ts`.
			await expect(panel.locator('[data-ranked="rows"]')).toBeVisible();
			return;
		}
		const placements = Number(await list.getAttribute('data-fleet-list'));
		expect(placements).toBeLessThan(APPEARANCE.console.fleet_min_rows);
		await expect(panel.locator('[data-ranked-cell="bar"]')).toHaveCount(0);
		await expect(panel.locator('[data-fleet-under]')).toContainText(
			String(APPEARANCE.console.fleet_min_rows)
		);
	});

	test('nothing in the panel is a share, a rate or a probability', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel="What the platform has been giving us"]');
		const text = await panel.innerText();
		expect(text).not.toMatch(/\d\s*%|percent|probability|chance of/i);
	});
});
