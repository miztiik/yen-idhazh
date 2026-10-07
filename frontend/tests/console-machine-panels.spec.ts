/** Do the three machine panels draw what the ruling requires?
 *
 * Each panel is worked out first on shard rows and host records this file
 * writes, with every figure written out: one group a machine, rates that pool
 * only that machine's shards, and cards that draw the flags a machine does not
 * have rather than omitting them. The built page is then held to what a unit
 * test cannot see: that the colour a machine takes is the same at every window
 * preset, that no two named machines share a stop, that the name is on the row
 * as TEXT in both themes, and that what it draws keeps the shape of the figures
 * it was handed, whatever run it drew.
 */

import { expect, test, type Page } from './support/browser';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { WATCHED_FLAG, type HostFingerprint } from '../src/lib/server/host-fingerprint';
import { machineCounters, type MachineLimits, type MachineRun } from '../src/lib/server/machine-counters';
import { copySpeedSentence, clockSentence, machineCards, uptimeSentence } from '../src/lib/charts/machine-cards';
import { splitByMachine } from '../src/lib/charts/machine-split';
import { ledgers, plan, type ShardReading } from './support/machine-rows';

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

const DATE = '2026-09-18';
const RUN = '2026-09-18-1';
const MIB = 1024 * 1024;

const TEST_LIMITS: MachineLimits = {
	contextWindow: 8192,
	jobTimeoutSeconds: 3600
};

function foldedRun(readings: ShardReading[], shards = readings.length): MachineRun {
	const stamped = readings.map((reading) => ({ date: DATE, runId: RUN, ...reading }));
	const { hosts, health } = ledgers(stamped);
	const { runs, refused } = machineCounters(hosts, health, plan([RUN, shards]), TEST_LIMITS);
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs, 'the fixture folded into no run').toHaveLength(1);
	return runs[0];
}

function machineShard(over: ShardReading): ShardReading {
	return {
		cachedTokens: 0,
		jobSeconds: 100,
		longestSequence: 1_000,
		...over
	};
}

function host(over: Partial<HostFingerprint>): HostFingerprint {
	return {
		version: '2026-09-18',
		date: DATE,
		run_id: RUN,
		job: 'work',
		shard: 0,
		fingerprint: 'machine-a',
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		cpu_vendor: 'AuthenticAMD',
		cpu_family: 25,
		cpu_model_number: 1,
		cpu_stepping: 1,
		microcode: '0x1',
		cores: 4,
		threads: 8,
		l3_cache_bytes: 32 * MIB,
		mhz_max: null,
		mhz_at_probe: 2800,
		flags: '',
		boot_seconds: 125,
		memcpy_gib_s: 10,
		memcpy_probe_mib: 128,
		vm_size: 'Standard_D4s_v5',
		vm_location: 'eastus',
		vm_zone: '1',
		vm_fault_domain: '0',
		runner_name: 'runner-a',
		measured_at: `${DATE}T00:00:00Z`,
		model_load_ms: 400,
		job_seconds: 100,
		server_prompt_tokens: 200,
		server_prompt_seconds: 10,
		...over
	};
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', String(days));
	await expect(page.locator('[data-windowed="machine-fleet"]')).toHaveAttribute('data-fleet-state', 'ready');
}

test.describe('reading against writing, machine by machine', () => {
	test('one group a machine, and no element carries a rate pooled over all shards', () => {
		const run = foldedRun([
			machineShard({
				shard: 0,
				cpuModel: 'AMD EPYC 7763 64-Core Processor',
				fingerprint: 'epyc-a',
				serverPromptTokens: 100,
				serverPromptSeconds: 10,
				writtenTokens: 40,
				writeSeconds: 20
			}),
			machineShard({
				shard: 1,
				cpuModel: 'Intel Xeon Platinum 8370C CPU @ 2.80GHz',
				fingerprint: 'xeon-b',
				serverPromptTokens: 120,
				serverPromptSeconds: 20,
				writtenTokens: 80,
				writeSeconds: 10
			})
		]);
		const split = splitByMachine(run, { colour: { stops: 4, floor: 0.35 } });

		expect(split.empty).toBe(false);
		expect(split.groups.map((group) => group.identity.name).sort()).toEqual([
			'AMD EPYC 7763',
			'Intel Xeon Platinum 8370C'
		]);
		expect(split.groups.map((group) => group.readTokensPerSecond).sort((a, b) => (a ?? 0) - (b ?? 0))).toEqual([
			6,
			10
		]);
		expect(
			split.groups.some((group) => group.readTokensPerSecond === 220 / 30),
			'the split kept a pooled run rate'
		).toBe(false);
	});

	test('every rate in a group recomputes from that machine shards alone', () => {
		const run = foldedRun([
			machineShard({
				shard: 0,
				cpuModel: 'AMD EPYC 7763 64-Core Processor',
				fingerprint: 'epyc-a',
				serverPromptTokens: 120,
				serverPromptSeconds: 6,
				writtenTokens: 90,
				writeSeconds: 9
			}),
			machineShard({
				shard: 1,
				cpuModel: 'AMD EPYC 7763 64-Core Processor',
				fingerprint: 'epyc-a',
				serverPromptTokens: 180,
				serverPromptSeconds: 9,
				writtenTokens: 60,
				writeSeconds: 6
			}),
			machineShard({
				shard: 2,
				cpuModel: 'Intel Xeon Platinum 8370C CPU @ 2.80GHz',
				fingerprint: 'xeon-b',
				serverPromptTokens: 50,
				serverPromptSeconds: 10,
				writtenTokens: 100,
				writeSeconds: 25
			})
		]);
		const split = splitByMachine(run, { colour: { stops: 4, floor: 0.35 } });
		const byName = new Map(split.groups.map((group) => [group.identity.name, group]));

		expect(byName.get('AMD EPYC 7763')?.shards).toBe(2);
		expect(byName.get('AMD EPYC 7763')?.readTokensPerSecond).toBe(20);
		expect(byName.get('AMD EPYC 7763')?.writeTokensPerSecond).toBe(10);
		expect(byName.get('AMD EPYC 7763')?.rows[0]).toMatchObject({
			label: 'Seconds',
			readValue: 15,
			writeValue: 15,
			readPct: 50
		});
		expect(byName.get('AMD EPYC 7763')?.rows[1]).toMatchObject({
			label: 'Tokens',
			readValue: 300,
			writeValue: 150,
			readPct: 67
		});
		expect(byName.get('Intel Xeon Platinum 8370C')?.readTokensPerSecond).toBe(5);
		expect(byName.get('Intel Xeon Platinum 8370C')?.writeTokensPerSecond).toBe(4);
	});

	test('the built panel draws one group a machine, names one of them, and draws no pooled rate', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="reading-against-writing"]');
		await expect(panel).toBeVisible();

		const keys = await panel
			.locator('[data-machine-group]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-machine-group') ?? ''));
		expect(keys.length, 'the panel drew no machine group').toBeGreaterThan(0);
		expect(new Set(keys).size, 'two groups share one machine').toBe(keys.length);

		// The headline names a machine, never the run as a whole.
		const headline = panel.locator('[data-machine-split-headline]');
		if ((await headline.count()) > 0) {
			expect(keys).toContain(await headline.getAttribute('data-machine-split-headline'));
		}
		// Nothing on the panel offers a rate over every shard of the run.
		await expect(panel.locator('[data-reading-writing-sentence]')).toHaveCount(0);
		await expect(panel.locator('[data-reading-writing]')).toHaveCount(0);
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
	test('machine cards preserve flags, copy speed, clocks and L3 ratios on written rows', () => {
		const run = foldedRun([
			machineShard({
				shard: 0,
				cpuModel: 'AMD EPYC 7763 64-Core Processor',
				fingerprint: 'full',
				serverPromptTokens: 200,
				serverPromptSeconds: 10,
				writtenTokens: 90,
				writeSeconds: 9
			}),
			machineShard({
				shard: 1,
				cpuModel: 'Intel Xeon Platinum 8370C CPU @ 2.80GHz',
				fingerprint: 'empty',
				serverPromptTokens: 50,
				serverPromptSeconds: 10,
				writtenTokens: 100,
				writeSeconds: 25
			})
		]);
		const cards = machineCards(
			run,
			[
				host({
					fingerprint: 'full',
					shard: 0,
					cpu_model: 'AMD EPYC 7763 64-Core Processor',
					flags: WATCHED.join(' '),
					l3_cache_bytes: 64 * MIB,
					memcpy_gib_s: 12,
					memcpy_probe_mib: 256,
					mhz_at_probe: 2750,
					boot_seconds: 125
				}),
				host({
					fingerprint: 'empty',
					shard: 1,
					cpu_model: 'Intel Xeon Platinum 8370C CPU @ 2.80GHz',
					flags: '',
					l3_cache_bytes: 32 * MIB,
					memcpy_gib_s: 6,
					memcpy_probe_mib: 32,
					mhz_at_probe: null,
					boot_seconds: null
				})
			],
			{
				watchedFlags: WATCHED,
				colour: { stops: 4, floor: 0.35 },
				recording: true,
				cacheMargin: 2
			}
		);

		expect(cards.record).toBe('recorded');
		expect(cards.cards).toHaveLength(2);
		const byName = new Map(cards.cards.map((card) => [card.identity.name, card]));
		const full = byName.get('AMD EPYC 7763');
		const empty = byName.get('Intel Xeon Platinum 8370C');
		expect(full?.flags).toEqual(WATCHED.map((name) => ({ name, present: true })));
		expect(empty?.flags).toEqual(WATCHED.map((name) => ({ name, present: false })));
		expect(full?.l3Bar.state).toBe('drawn');
		expect(empty?.l3Bar.state).toBe('drawn');
		expect((full?.l3Bar.fraction ?? 0) / (empty?.l3Bar.fraction ?? 1)).toBeCloseTo(2, 4);
		expect(copySpeedSentence(full!)).toBe(
			'12.0 GiB/s, over a 256 MiB buffer against 64 MiB of L3 - 4.00 times it.'
		);
		expect(copySpeedSentence(empty!)).toBe(
			'No copy speed: the probe used a 32 MiB buffer against 32 MiB of L3, 1.00 times it, and a reading has to clear 2 times to be sure the copy left the cache.'
		);
		expect(clockSentence(full!)).toBe(
			"2750 MHz when the probe ran, before the job's heaviest step."
		);
		expect(clockSentence(empty!)).toBe('Clock speed was not recorded on this job.');
		expect(uptimeSentence(full!)).toBe('Up 2 m 5 s when we measured it.');
		expect(uptimeSentence(empty!)).toBe('Uptime was not recorded on this job.');
	});

	test('the built cards draw every watched flag, and their sentences keep the shapes the cards make', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		const panel = page.locator('[data-console-panel-id="machine-cards"]');
		await expect(panel).toBeVisible();
		const cards = panel.locator('[data-machine-card]');
		const count = await cards.count();
		expect(count, 'the panel drew no machine card').toBeGreaterThan(0);

		for (let index = 0; index < count; index += 1) {
			const card = cards.nth(index);
			const chips = card.locator('[data-machine-flag]');
			if ((await chips.count()) === 0) {
				// A card off the counters alone says so, instead of drawing every chip as
				// an outline, which would read as a machine with no flags at all.
				await expect(card.locator('[data-machine-flags="none"]')).toBeVisible();
			} else {
				expect(
					await chips.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-machine-flag'))),
					'a card drew some of the watched flags and left the rest out'
				).toEqual(WATCHED);
			}
			for (const text of await card.locator('[data-machine-copy-speed]').allInnerTexts()) {
				const said = text.trim();
				if (said.startsWith('No copy speed')) {
					expect(said, 'a withheld reading still printed a rate').not.toContain('GiB/s');
				} else if (!said.startsWith('Copy speed was not measured')) {
					expect(said, 'the rate and its buffer are not in one element').toMatch(/GiB\/s.*MiB buffer/);
				}
			}
			for (const text of await card.locator('[data-machine-clock]').allInnerTexts()) {
				expect(text, 'a clock was drawn as a share of something').not.toContain('%');
			}
			for (const text of await card.locator('[data-machine-uptime]').allInnerTexts()) {
				expect(text.trim()).toMatch(/^(Up .+ when we measured it\.|Uptime was not recorded on this job\.)$/);
			}
		}

		// One zero-anchored domain over every card, so two bar lengths are in the
		// ratio of the two caches they draw.
		const drawn = await panel
			.locator('[data-machine-bar="l3"][data-machine-bar-state="drawn"]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					bytes: Number(node.querySelector('[data-machine-cache]')?.getAttribute('data-machine-cache')),
					fraction: Number(
						node.querySelector('[data-machine-bar-cell="track"]')?.getAttribute('data-machine-bar-fraction')
					)
				}))
			);
		for (const bar of drawn) {
			expect(bar.fraction / drawn[0].fraction, `a ${bar.bytes}-byte cache`).toBeCloseTo(
				bar.bytes / drawn[0].bytes,
				4
			);
		}
	});

	test('the machine location disclosure is native and closed at rest', async ({ page }) => {
		await page.goto('/console/machine/');
		const where = page.locator('[data-machine-where]');
		const count = await where.count();
		expect(count, 'no machine card carried a location disclosure').toBeGreaterThan(0);
		for (let index = 0; index < count; index += 1) {
			const disclosure = where.nth(index);
			expect(await disclosure.evaluate((node) => node.tagName)).toBe('DETAILS');
			expect(await disclosure.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
			await expect(disclosure.locator('summary')).toHaveText('Where the platform put this');
		}
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

	test('a recorded row names the record state, so a loss is never claimed', () => {
		const run = foldedRun([
			machineShard({
				shard: 0,
				cpuModel: 'AMD EPYC 7763 64-Core Processor',
				fingerprint: 'recorded',
				serverPromptTokens: 200,
				serverPromptSeconds: 10,
				writtenTokens: 90,
				writeSeconds: 9
			})
		]);
		const cards = machineCards(
			run,
			[
				host({
					fingerprint: 'recorded',
					shard: 0,
					cpu_model: 'AMD EPYC 7763 64-Core Processor',
					flags: WATCHED.join(' ')
				})
			],
			{
				watchedFlags: WATCHED,
				colour: { stops: 4, floor: 0.35 },
				recording: true,
				cacheMargin: 2
			}
		);

		expect(cards.record).toBe('recorded');
		expect(cards.lost).toBeNull();
		expect(cards.lostNote).toBeNull();
		expect(cards.nothing).toBeNull();
		expect(cards.cards).toHaveLength(1);
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
