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

import { expect, test, type Page } from './support/browser';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { WATCHED_FLAG } from '../src/lib/server/host-fingerprint';
import { canaryArticleRows, canaryMachineRows, heldRows } from './support/canary-records';

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

/** Every row of one canary record, as the canary packed it.
 *
 * The page's arithmetic is checked against these rows rather than against
 * itself: an oracle that reads the module it is testing proves only that the
 * module agrees with itself. The rows come through the reader the page's server
 * calls, because the packed file is the only copy the canary keeps; everything
 * the panels compute from them is recomputed here.
 */
const records = {
	'host-fingerprint': heldRows(canaryMachineRows),
	'item-health': heldRows(canaryArticleRows)
};

test.beforeAll(async () => {
	await records['host-fingerprint'].load();
	await records['item-health'].load();
});

function canaryRows(ledger: keyof typeof records): Record<string, string>[] {
	return records[ledger].rows();
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
		const shard = held.get(`${row.run_id}/${row.machine_shard}`);
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
	await expect(page.locator('[data-windowed="machine-fleet"]')).toHaveAttribute('data-fleet-state', 'ready');
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

	test('a machine keeps one step, the step follows its speed, and the grey is only an absence', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const marks = await page
			.locator('[data-machine-group], [data-machine-card]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					key: node.getAttribute('data-machine-group') ?? node.getAttribute('data-machine-card') ?? '',
					name: node.getAttribute('data-machine-name') ?? '',
					step: node.getAttribute('data-machine-step'),
					speed: node.getAttribute('data-machine-speed'),
					unrecorded: node.getAttribute('data-machine-unrecorded') === 'yes'
				}))
			);
		expect(marks.length).toBeGreaterThan(0);

		// One machine, one step, on the split and on its card alike.
		const byKey = new Map<string, Set<string | null>>();
		for (const mark of marks) byKey.set(mark.key, (byKey.get(mark.key) ?? new Set()).add(mark.step));
		for (const [key, steps] of byKey) expect(steps.size, `${key} took two steps`).toBe(1);

		// A step is a speed band: a faster machine never sits on a slower step.
		const timed = marks
			.filter((mark) => mark.step !== 'none' && mark.speed !== null && mark.speed !== 'none')
			.map((mark) => ({ step: Number(mark.step), speed: Number(mark.speed) }));
		expect(timed.length, 'the canary names a machine with a speed').toBeGreaterThan(0);
		for (const one of timed) {
			expect(one.step).toBeGreaterThanOrEqual(1);
			expect(one.step).toBeLessThanOrEqual(APPEARANCE.console.machine_colour_stops);
			for (const other of timed) {
				if (one.speed < other.speed) expect(one.step).toBeLessThanOrEqual(other.step);
			}
		}

		for (const mark of marks.filter((one) => one.unrecorded)) {
			expect(mark.step).toBe('none');
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
	test('unchanged machine cards preserve flags, copy speed, clocks, disclosure and L3 ratios', async ({ page }) => {
		await page.goto('/console/machine/');
		await test.step('a card draws every watched flag, and absence is drawn rather than omitted', async () => {
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

		await test.step('a graded copy speed carries its buffer, and an ungraded one is withheld', async () => {
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

		await test.step('each card says what clock it ran at and how long it had been up', async () => {
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

		await test.step('the disclosure is a native details and is closed at rest', async () => {
			const where = page.locator('[data-machine-where]').first();
			if ((await where.count()) === 0) return;
			expect(await where.evaluate((node) => node.tagName)).toBe('DETAILS');
			expect(await where.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
			await expect(where.locator('summary')).toHaveText('Where the platform put this');
		});

		await test.step('two cards with different L3 draw bars in the ratio of their bytes', async () => {
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
 * record answered for - and it is the check that proves the binding.
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

test.describe('which machines ran our jobs, day by day', () => {
	async function openFleet(page: Page): Promise<void> {
		await page.goto('/console/machine/');
		await expect(page.locator('[data-windowed="machine-fleet"]')).toHaveAttribute('data-fleet-state', 'ready');
	}

	test('under the threshold it draws one square a job, over it one bar a day', async ({ page }) => {
		await openFleet(page);
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		await expect(panel).toBeVisible();
		await expect(panel.locator('.panel-title')).toHaveText('Which machines ran our jobs, day by day');
		const body = panel.locator('[data-fleet-shape]');
		await expect(body).toHaveCount(1);
		const placements = Number(await body.getAttribute('data-fleet-placements'));
		const shape = await body.getAttribute('data-fleet-shape');
		expect(shape).toBe(placements < APPEARANCE.console.fleet_min_rows ? 'dots' : 'bars');
		if (shape === 'dots') {
			// The canary is far under the floor on purpose: a square a job, every job.
			await expect(panel.locator('[data-fleet-squares]')).toHaveAttribute('data-fleet-squares', String(placements));
			await expect(panel.locator('[data-fleet-square]')).toHaveCount(placements);
		} else {
			await expect(panel.locator('[data-series-bar]').first()).toBeVisible();
		}
		// Its hover is the strip under the plot, a column a day drawn.
		const days = await body.getAttribute('data-fleet-days');
		await expect(panel.locator('[data-readout-columns]')).toHaveAttribute('data-readout-columns', days ?? '');
		// The three things the sufficiency gates read off it.
		await expect(panel.locator('[data-lede]')).toHaveCount(1);
		await expect(panel.locator('[data-comparison]')).toHaveAttribute('data-comparison', 'composition');
		await expect(panel.locator('[data-model-rule]')).toHaveAttribute('data-model-rule', 'no');
		expect((await panel.locator('[data-model-rule]').getAttribute('data-model-rule-none'))?.split(' ').length).toBeGreaterThanOrEqual(5);
		// No native tooltip on a mark.
		await expect(panel.locator('svg title')).toHaveCount(0);
	});

	test('every row of the strip says the speed its colour stands for, and no machine is last', async ({
		page
	}) => {
		await openFleet(page);
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		const rows = await panel.locator('[data-readout-row]').evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-readout-row') ?? '')
		);
		expect(rows.length).toBeGreaterThan(0);
		for (const row of rows.filter((one) => !one.startsWith('Machine not recorded'))) {
			expect(row, 'a row with no speed').toMatch(/tokens a second\)$|no speed reading\)$/);
		}
		// The canary holds one job the record reached with no machine on it.
		expect(rows.at(-1)).toBe('Machine not recorded');
		await expect(panel.locator('[data-fleet-speed-key]')).toContainText('Slower');
		await expect(panel.locator('[data-fleet-speed-key]')).toContainText('tokens a second');
		// A step no kind of machine lands on names nothing, so the key leaves it out.
		await expect(panel.locator('[data-fleet-speed-key]')).not.toContainText('none');
	});

	test('a click or Enter lists the day and the strip keeps it, Escape or Close shuts the list, and focus comes back', async ({
		page
	}) => {
		await openFleet(page);
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		await panel.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
		const plot = panel.locator('svg[data-chart-name="machine-fleet"]');
		await expect(plot).toBeVisible();
		const jobs = panel.locator('[data-fleet-jobs]');
		await expect(jobs).toHaveCount(0);

		const box = await plot.boundingBox();
		if (box === null) throw new Error('the plot has no box');
		const strip = panel.locator('[data-readout] [data-readout-day]').first();
		const resting = await strip.innerText();
		// The oldest day is the first column; point near the left of the plot, then
		// press there, which is what a click is.
		await page.mouse.move(box.x + 4, box.y + box.height * 0.5);
		await expect(strip).not.toHaveText(resting);
		const pointed = await strip.innerText();
		await page.mouse.down();
		await page.mouse.up();
		await expect(jobs).toHaveCount(1);
		await expect(jobs).toBeFocused();
		// Focus has left the plot for the list, and the strip still reads the day
		// the list is of rather than falling back to the newest.
		await expect(strip).toHaveText(pointed);
		const listed = Number(await body(panel).getAttribute('data-fleet-placements'));
		expect(await jobs.locator('tbody tr').count()).toBeGreaterThan(0);
		expect(await jobs.locator('tbody tr').count()).toBeLessThanOrEqual(listed);
		await page.keyboard.press('Escape');
		await expect(jobs).toHaveCount(0);
		await expect(plot).toBeFocused();

		await page.keyboard.press('Enter');
		await expect(jobs).toHaveCount(1);
		await jobs.locator('button').click();
		await expect(jobs).toHaveCount(0);
	});

	test('nothing in the panel is a share, a rate of a draw or a probability', async ({ page }) => {
		await openFleet(page);
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		const text = await panel.innerText();
		expect(text).not.toMatch(/\d\s*%|percent|probability|chance of/i);
	});

	test('on a phone a listed job takes two lines, and the list never scrolls sideways', async ({ page }) => {
		// Six columns do not fit 390px. A list that scrolled sideways hid the speed,
		// which is what ties a job to its colour.
		await page.setViewportSize({ width: 390, height: 844 });
		await openFleet(page);
		const panel = page.locator('[data-console-panel-id="platform-mix"]');
		await panel.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
		const plot = panel.locator('svg[data-chart-name="machine-fleet"]');
		await expect(plot).toBeVisible();
		await plot.focus();
		await page.keyboard.press('Enter');
		const jobs = panel.locator('[data-fleet-jobs]');
		await expect(jobs).toHaveCount(1);
		expect(await jobs.evaluate((node) => node.scrollWidth - node.clientWidth)).toBeLessThanOrEqual(0);
		const box = await jobs.boundingBox();
		const speed = await jobs.locator('tbody tr').first().locator('td').last().boundingBox();
		if (box === null || speed === null) throw new Error('the list or its speed cell has no box');
		expect(speed.x + speed.width, 'the speed cell runs past the list').toBeLessThanOrEqual(box.x + box.width);
	});
});

function body(panel: import('@playwright/test').Locator) {
	return panel.locator('[data-fleet-shape]');
}

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
		// The other half: a run the ledger timed draws, and the count grain is
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
		// Whichever branch it took, the measurement it took it on is on the page.
		const measured = await board.getAttribute('data-cost-thinnest-pct');
		expect(Number(measured)).toBeGreaterThan(0);
		await expect(board.locator('[data-cost-measured]')).toContainText(measured ?? 'no measurement');
	});
});
