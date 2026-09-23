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
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { WATCHED_FLAG } from '../src/lib/server/host-fingerprint';

const REPO = resolve(process.cwd(), '..');

const APPEARANCE = JSON.parse(
	readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
) as { console: { fleet_min_rows: number; machine_colour_stops: number; window_presets: number[] } };

/** The flags a card has to draw a chip for.
 *
 * The one copy, bound to the Python enum by
 * `backend/tests/contracts/test_frontend_vocabularies.py`, so this is the
 * contract's list and not a second one typed here.
 */
const WATCHED: readonly string[] = WATCHED_FLAG;

/** Every row of one canary ledger, read straight off its day tree.
 *
 * The page's arithmetic is checked against this rather than against itself: an
 * oracle that reads the module it is testing proves only that the module agrees
 * with itself.
 */
function canaryRows(ledger: string): Record<string, string>[] {
	const root = join(REPO, 'backend', 'var', 'canary', 'state', ledger);
	const rows: Record<string, string>[] = [];
	for (const relative of readdirSync(root, { recursive: true }) as string[]) {
		if (!relative.endsWith('.csv')) continue;
		const text = readFileSync(join(root, relative), 'utf8').trim();
		if (text === '') continue;
		const [header, ...lines] = text.split('\n');
		const columns = header.split(',');
		for (const line of lines) {
			const cells = line.split(',');
			rows.push(Object.fromEntries(columns.map((name, index) => [name, cells[index] ?? ''])));
		}
	}
	return rows;
}

/** One shard of one run, as the two ledgers together describe it.
 *
 * Reading comes from the machine record and writing from the item ledger,
 * which is the whole point of the panel: neither file can answer both halves,
 * so a page that folded one of them would print a rate nothing measured.
 */
interface CanaryShard {
	runId: string;
	shard: string;
	cpuModel: string;
	promptTokens: number | null;
	promptSeconds: number | null;
	writtenTokens: number | null;
	writeSeconds: number | null;
}

function added(carry: number | null, cell: string, scale = 1): number | null {
	if (cell === '') return carry;
	const value = Number(cell);
	return Number.isFinite(value) ? (carry ?? 0) + value * scale : carry;
}

function canaryShards(): CanaryShard[] {
	const held = new Map<string, CanaryShard>();
	for (const row of canaryRows('host-fingerprint')) {
		if (row.job !== 'work' || row.shard === '') continue;
		const key = `${row.run_id}/${row.shard}`;
		const shard = held.get(key) ?? {
			runId: row.run_id,
			shard: row.shard,
			cpuModel: '',
			promptTokens: null,
			promptSeconds: null,
			writtenTokens: null,
			writeSeconds: null
		};
		if (shard.cpuModel === '') shard.cpuModel = row.cpu_model;
		shard.promptTokens = added(shard.promptTokens, row.server_prompt_tokens);
		shard.promptSeconds = added(shard.promptSeconds, row.server_prompt_seconds);
		held.set(key, shard);
	}
	for (const row of canaryRows('item-health')) {
		const shard = held.get(`${row.run_id}/${row.shard}`);
		if (shard === undefined) continue;
		shard.writtenTokens = added(shard.writtenTokens, row.output_tokens);
		shard.writeSeconds = added(shard.writeSeconds, row.decode_ms, 0.001);
		if (shard.cpuModel === '') shard.cpuModel = row.cpu_model;
	}
	return [...held.values()];
}

/** The shards of the newest run both halves of the board can draw. */
function newestDrawnRun(): CanaryShard[] {
	const drawn = canaryShards().filter(
		(shard) =>
			shard.promptTokens !== null &&
			shard.promptSeconds !== null &&
			shard.writtenTokens !== null &&
			shard.writeSeconds !== null
	);
	const newest = drawn.map((shard) => shard.runId).sort((a, b) => b.localeCompare(a))[0];
	return drawn.filter((shard) => shard.runId === newest);
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
		const panel = page.locator('[data-console-panel-id="reading-against-writing"]');
		await expect(panel).toBeVisible();

		const rows = newestDrawnRun();
		const kinds = new Set(rows.map((shard) => shard.cpuModel));
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
		const panel = page.locator('[data-console-panel-id="reading-against-writing"]');
		const shards = canaryShards();
		const newestRun = await panel.evaluate(
			(node) => node.closest('[data-machine-split]')?.getAttribute('data-machine-split') ?? ''
		);
		expect(newestRun).not.toBe('');

		const byName = new Map<string, { tokens: number; seconds: number }>();
		for (const shard of shards) {
			if (shard.runId !== newestRun) continue;
			if (shard.promptTokens === null || shard.promptSeconds === null) continue;
			if (shard.writtenTokens === null || shard.writeSeconds === null) continue;
			const held = byName.get(shard.cpuModel) ?? { tokens: 0, seconds: 0 };
			held.tokens += shard.promptTokens;
			held.seconds += shard.promptSeconds;
			byName.set(shard.cpuModel, held);
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
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
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

	test('a graded copy speed carries its buffer, and an ungraded one is withheld', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		const readings = panel.locator('[data-machine-copy-speed]');
		const count = await readings.count();
		expect(count).toBeGreaterThan(0);
		let sawWithheld = false;
		for (let index = 0; index < count; index += 1) {
			const text = (await readings.nth(index).innerText()).trim();
			if (text.startsWith('Copy speed was not measured')) continue;
			if (text.startsWith('No copy speed')) {
				// The refused figure is not on the page at all, in any form.
				expect(text, 'a withheld reading still printed a rate').not.toContain('GiB/s');
				expect(text, 'a withheld reading did not say what it fell short of').toMatch(
					/times it, and a reading has to clear \d+ times/
				);
				sawWithheld = true;
				continue;
			}
			expect(text, 'the rate and its buffer are not in one element').toMatch(
				/GiB\/s.*MiB buffer/
			);
		}
		expect(sawWithheld, 'no card withheld a copy speed the probe could not grade').toBe(true);
	});

	test('each card says what clock it ran at and how long it had been up', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		const clocks = panel.locator('[data-machine-clock]');
		const uptimes = panel.locator('[data-machine-uptime]');
		const count = await clocks.count();
		expect(count, 'no card carried a clock reading').toBeGreaterThan(0);
		expect(await uptimes.count(), 'a card carried a clock and no uptime').toBe(count);

		// The ledger's own cells, so the assertion is the fixture's rather than the
		// page agreeing with itself.
		const recorded = canaryRows('host-fingerprint').filter((row) => row.mhz_at_probe !== '');
		expect(recorded.length, 'the canary recorded no clock at all').toBeGreaterThan(0);
		const clockValues = new Set(recorded.map((row) => String(Math.round(Number(row.mhz_at_probe)))));

		for (let index = 0; index < count; index += 1) {
			const said = (await clocks.nth(index).innerText()).trim();
			// A ceiling nothing writes is a column the page may not divide by.
			expect(said, 'a clock was drawn as a share of something').not.toContain('%');
			if (said.startsWith('Clock speed was not recorded')) continue;
			const mhz = said.split(' ')[0];
			expect(clockValues.has(mhz), `${mhz} MHz is not a clock the ledger holds`).toBe(true);
		}
		for (let index = 0; index < count; index += 1) {
			const said = (await uptimes.nth(index).innerText()).trim();
			expect(said).toMatch(/^(Up .+ when we measured it\.|Uptime was not recorded on this job\.)$/);
		}
	});

	test('the disclosure is a native details and is closed at rest', async ({ page }) => {
		await page.goto('/console/machine/');
		const where = page.locator('[data-machine-where]').first();
		if ((await where.count()) === 0) return;
		expect(await where.evaluate((node) => node.tagName)).toBe('DETAILS');
		expect(await where.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
		await expect(where.locator('summary')).toHaveText('Where the platform put this');
	});

	test('two cards with different L3 draw bars in the ratio of their bytes', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		const bars = panel.locator('[data-machine-bar="l3"]');
		const count = await bars.count();
		expect(count, 'the fixture drew fewer than two machines').toBeGreaterThan(1);

		const drawn: { bytes: number; fraction: number }[] = [];
		for (let index = 0; index < count; index += 1) {
			const bar = bars.nth(index);
			if ((await bar.getAttribute('data-machine-bar-state')) !== 'drawn') continue;
			const bytes = Number(
				await bar.locator('[data-machine-cache]').getAttribute('data-machine-cache')
			);
			const fraction = Number(
				await bar
					.locator('[data-machine-bar-cell="track"]')
					.getAttribute('data-machine-bar-fraction')
			);
			drawn.push({ bytes, fraction });
		}
		expect(drawn.length, 'fewer than two L3 bars were drawn').toBeGreaterThan(1);

		// The bytes the page drew are the ledger's, so the ratio below is the
		// fixture's rather than the panel's own arithmetic restated.
		const ledger = new Set(
			canaryRows('host-fingerprint')
				.map((row) => Number(row.l3_cache_bytes))
				.filter((bytes) => Number.isFinite(bytes) && bytes > 0)
		);
		for (const { bytes } of drawn) expect(ledger.has(bytes)).toBe(true);

		const [low, high] = [...drawn].sort((a, b) => a.bytes - b.bytes);
		expect(high.bytes, 'both machines report the same L3').toBeGreaterThan(low.bytes);
		// One zero-anchored domain over both cards, so two lengths are two
		// readings. Whatever the track runs to divides out of this.
		expect(high.fraction / low.fraction).toBeCloseTo(high.bytes / low.bytes, 4);
	});

	test('a reading with nothing to draw names its state and draws no track', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		const bars = panel.locator('[data-machine-bar]');
		const count = await bars.count();
		expect(count).toBeGreaterThan(0);

		const states = new Set<string>();
		for (let index = 0; index < count; index += 1) {
			const bar = bars.nth(index);
			const state = (await bar.getAttribute('data-machine-bar-state')) ?? '';
			states.add(state);
			const tracks = await bar.locator('[data-machine-bar-cell="track"]').count();
			// An empty track reads as a reading of zero. A bar with nothing to
			// draw, or nothing to draw against, says which and draws nothing.
			expect(tracks, `state ${state} drew ${tracks} tracks`).toBe(state === 'drawn' ? 1 : 0);
			if (state !== 'drawn') {
				await expect(bar.locator('[data-machine-bar-why]')).toHaveCount(
					state === 'absent' ? 0 : 1
				);
			}
		}
		// The canary's second machine probed a buffer 1.97 times its own L3, under
		// the margin that proves the copy left the cache, so its rate is withheld
		// and shares no track with the graded one.
		expect([...states].sort()).toEqual(['alone', 'drawn', 'ungraded']);
	});
});

/** Which of the record's states the page is in, said in an attribute.
 *
 * **The assertion may not be a negative one about prose.** "The page contains
 * no sentence claiming the record starts later" passes the day somebody renames
 * that sentence, while the page goes on printing the lie - so the state is an
 * attribute that is always set, and every sentence the panel can print is tied
 * to the value it belongs to. A state that stops being set takes this red with
 * it.
 *
 * The three states themselves are asserted over built rows in
 * `console-machine-cards.spec.ts`. The canary holds one of them - a day the
 * record answered for - and it is the arm that proves the binding.
 */
test.describe('the machine record names which state it is in', () => {
	const STATES = ['recorded', 'off', 'lost', 'none'];

	test('the panel carries one of the four names, and its note matches it', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-machine-record]');
		await expect(panel).toHaveCount(1);
		const state = await panel.getAttribute('data-machine-record');
		expect(STATES, 'the panel named a state nobody declared').toContain(state);

		// Every sentence the panel can print, tied to the state that owns it. A
		// note printed under the wrong state is the defect this exists to catch,
		// in either direction.
		const lostNotes = await panel.locator('[data-machine-panel-empty="machines-lost"], [data-machine-panel-note="machines-lost"]').count();
		const offNotes = await panel.locator('[data-machine-panel-empty="machines-off"], [data-machine-panel-note="machines-off"]').count();
		const quietNotes = await panel.locator('[data-machine-panel-empty="machines-none"]').count();
		expect(lostNotes > 0, `state ${state} printed the loss note`).toBe(state === 'lost');
		expect(offNotes > 0, `state ${state} printed the switched-off note`).toBe(state === 'off');
		if (state !== 'none') expect(quietNotes).toBe(0);

		// A card with no instruction set says WHICH of the two reasons it is, and
		// the reason agrees with the panel.
		const why = await page
			.locator('[data-machine-flags-why]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-machine-flags-why')));
		for (const reason of why) expect(reason).toBe(state === 'lost' ? 'lost' : 'not-started');
	});

	test('the canary is a day the record answered for, so a loss is never claimed', async ({
		page
	}) => {
		// The control. The canary's newest run recorded its machines, and one of
		// its earlier days has a record file with a header and no rows on a day
		// that published nothing - a quiet day, not an incident. Neither may
		// reach the reader as a loss.
		await page.goto('/console/machine/');
		await expect(page.locator('[data-machine-record]')).toHaveAttribute(
			'data-machine-record',
			'recorded'
		);
		await expect(page.locator('[data-recording="machine-destroyed"]')).toHaveCount(0);
		await expect(page.locator('[data-machine-panel-empty="fleet-lost"]')).toHaveCount(0);
	});
});

test.describe('what the platform has been giving us', () => {
	test('under the threshold it lists the counts and draws no bar', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		await expect(panel).toBeVisible();
		const list = panel.locator('[data-fleet-list]');
		if ((await list.count()) === 0) {
			// At or above the threshold the panel draws a trend instead. The fold
			// arithmetic is asserted over built rows in `console-fleet.spec.ts`;
			// what is asserted here is that the drawn bar and the counts it was
			// folded from are the same figure.
			const board = panel.locator('[data-fleet-series]');
			await expect(board).toBeVisible();
			await expect(panel.locator('[data-chart]')).toHaveCount(1);
			await expect(board).toHaveAttribute('data-panel-question', 'is it working');
			const kept = Number(await board.getAttribute('data-fleet-top-kinds'));
			const drawn = Number(await board.getAttribute('data-fleet-series'));
			expect(drawn).toBeLessThanOrEqual(kept + 1);
			expect(await board.getAttribute('data-fleet-other')).toBe(
				await board.getAttribute('data-fleet-outside-top')
			);
			return;
		}
		const placements = Number(await list.getAttribute('data-fleet-list'));
		expect(placements).toBeLessThan(APPEARANCE.console.fleet_min_rows);
		await expect(panel.locator('[data-chart]')).toHaveCount(0);
		await expect(panel.locator('[data-fleet-under]')).toContainText(
			String(APPEARANCE.console.fleet_min_rows)
		);
	});

	test('nothing in the panel is a share, a rate or a probability', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		const text = await panel.innerText();
		expect(text).not.toMatch(/\d\s*%|percent|probability|chance of/i);
	});
});

test.describe('what a run reads against what it writes', () => {
	const PANEL = '[data-console-panel-id="read-against-written"]';

	test('one chart, two series, and one axis per unit', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator(PANEL);
		await expect(panel).toBeVisible();
		// One drawing, not two panes. The predecessor drew a chart each for the
		// two series and neither could be compared to the other.
		await expect(panel.locator('[data-chart]')).toHaveCount(1);
		const board = panel.locator('[data-read-write-unit]');
		await expect(board).toHaveAttribute('data-panel-question', 'is it working');
		// The shape is picked from a measurement, and the measurement is printed.
		await expect(board).toHaveAttribute('data-read-write-split', 'no');
		await expect(panel.locator('[data-read-write-measured]')).toContainText(
			(await board.getAttribute('data-read-write-ratio')) ?? 'no ratio'
		);
	});

	test('the switch moves the unit, and both units read the same runs', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator(PANEL).locator('[data-read-write-unit]');
		await expect(board).toBeVisible();
		// The server drew one unit and the radio for it is already checked, so the
		// first paint and the control agree before a script has run.
		const opened = await board.getAttribute('data-read-write-unit');
		await expect(page.locator('[data-shape-switch="work-unit"]')).toHaveAttribute(
			'data-shape',
			opened ?? ''
		);

		const runs = await board.getAttribute('data-read-write-runs');
		const other = opened === 'seconds' ? 'tokens' : 'seconds';
		await page.locator(`[data-shape-switch="work-unit"] [data-shape-option="${other}"]`).click();
		await expect(board).toHaveAttribute('data-read-write-unit', other);
		// One row set answers both units, so the run count cannot move with the
		// switch. A count that moved would mean the two grains covered different
		// runs, and nothing on the page could say which.
		await expect(board).toHaveAttribute('data-read-write-runs', runs ?? '');
	});

	test('the seconds grain states its absence rather than drawing an empty chart', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator(PANEL).locator('[data-read-write-unit]');
		const units = page.locator('[data-shape-switch="work-unit"]');
		await units.locator('[data-shape-option="seconds"]').click();
		await expect(board).toHaveAttribute('data-read-write-unit', 'seconds');
		const timed = Number(await board.getAttribute('data-read-write-timed-runs'));
		if (timed === 0) {
			await expect(board.locator('[data-work-absent="seconds"]')).toBeVisible();
			await expect(board.locator('[data-chart]')).toHaveCount(0);
			return;
		}
		// The other arm: a run the ledger timed draws, and the count grain is
		// never taken down with the clock.
		await expect(board.locator('[data-work-absent="seconds"]')).toHaveCount(0);
		await expect(board.locator('[data-chart]')).toHaveCount(1);
		await units.locator('[data-shape-option="tokens"]').click();
		await expect(board.locator('[data-chart]')).toHaveCount(1);
	});
});

test.describe('what this would have cost somewhere else', () => {
	const PANEL = '[data-console-panel-id="counterfactual-cost"]';

	test('one chart beside the four numbers, and the switch opens where the server drew', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator(PANEL);
		await expect(panel).toBeVisible();
		const board = panel.locator('[data-cost-shape]');
		await expect(board).toHaveAttribute('data-panel-question', 'is it working');
		await expect(panel.locator('[data-chart]')).toHaveCount(1);
		// The four figures stay. A chart that replaced them would have taken the
		// per-article reading, which no shape of the chart carries.
		expect(
			await panel.locator('[data-cost-figures] [data-cost]').evaluateAll((nodes) =>
				nodes.map((node) => node.getAttribute('data-cost') ?? '').sort()
			)
		).toEqual(['input', 'output', 'per-article', 'total']);
		// The server drew one shape and the radio for it is already checked, so
		// the first paint and the control agree before a script has run.
		const opened = await board.getAttribute('data-cost-shape');
		await expect(page.locator('[data-shape-switch="cost-shape"]')).toHaveAttribute(
			'data-shape',
			opened ?? ''
		);
	});

	test('the switch moves the shape and never the days it was taken over', async ({ page }) => {
		await page.goto('/console/machine/');
		const board = page.locator(PANEL).locator('[data-cost-shape]');
		await expect(board).toBeVisible();
		const days = await board.getAttribute('data-cost-days');
		const total = await board.getAttribute('data-cost-running-total');
		expect(Number(days)).toBeGreaterThan(0);

		const opened = await board.getAttribute('data-cost-shape');
		const other = opened === 'running' ? 'daily' : 'running';
		await page.locator(`[data-shape-switch="cost-shape"] [data-shape-option="${other}"]`).click();
		await expect(board).toHaveAttribute('data-cost-shape', other);
		// One builder call answers both shapes, so neither the day count nor the
		// total can move with the switch. A total that moved would mean two
		// derivations of one quantity, with nothing on screen saying which to
		// believe.
		await expect(board).toHaveAttribute('data-cost-days', days ?? '');
		await expect(board).toHaveAttribute('data-cost-running-total', total ?? '');
	});

	test('the line ends where the four numbers above it say it should', async ({ page }) => {
		await page.goto('/console/machine/');
		const panel = page.locator(PANEL);
		const board = panel.locator('[data-cost-shape]');
		// A typed rate, because the committed one puts the window total under the
		// two decimals the headline figure prints, and a comparison taken across
		// that floor would be decided by the rounding.
		for (const [which, value] of [
			['input', '100'],
			['output', '300']
		] as const) {
			const field = page.locator(`[data-rate-input="${which}"]`);
			await expect(field).toBeEnabled();
			await field.fill(value);
			await field.blur();
		}
		await expect(panel.locator('[data-cost-figures]')).toHaveAttribute('data-cost-source', 'yours');

		const running = Number(await board.getAttribute('data-cost-running-total'));
		const printed = Number(
			(await panel.locator('[data-cost="total"] dd').innerText()).replace(/[^0-9.]/g, '')
		);
		expect(running).toBeGreaterThan(0.1);
		// The sum of the bars and the sum of the tokens are the same arithmetic,
		// reached two ways. The printed figure carries two decimals, so that is
		// the precision the comparison is owed.
		expect(running).toBeCloseTo(printed, 2);
	});

	test('the split is drawn as bands or printed as a figure, and the panel says which', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const board = page.locator(PANEL).locator('[data-cost-shape]');
		const split = await board.getAttribute('data-cost-split');
		expect(['drawn', 'printed']).toContain(split);
		// Whichever arm it took, the measurement it took it on is on the page.
		const measured = await board.getAttribute('data-cost-thinnest-pct');
		expect(Number(measured)).toBeGreaterThan(0);
		await expect(board.locator('[data-cost-measured]')).toContainText(measured ?? 'no measurement');
	});
});
