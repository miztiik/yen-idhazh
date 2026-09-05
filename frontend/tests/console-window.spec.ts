import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	monthsInWindow,
	monthsToFetch,
	stepPreset,
	windowOfDays
} from '../src/lib/charts/viewport';
import { readCsv } from '../src/lib/server/payload';

/**
 * One window, and every section that follows it saying the same number.
 *
 * The console used to let each section pick its own span: the viewport opened
 * on whatever fitted the rows, the source table hard-coded seven days, and
 * nothing on the page said either number out loud. Two charts on two windows
 * cannot be compared, which is the question an operator came here to ask.
 *
 * The oracle below is the row's whole point. It drives the control to each
 * preset in turn and asserts that every windowed surface reports that same day
 * count in its own description. A surface that disagrees with the control fails.
 */

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as {
	console?: {
		window_presets?: number[];
		default_window_days?: number;
		max_window_days?: number;
		today_anchor?: 'right' | 'centre';
	};
};

/** The cleanup ages, from the file that sets them. A published shard older than
 * `public_telemetry_keep_months` is deleted by `idhazh prune-state`, so the
 * widest read this control offers has to stay inside what that leaves. */
const APP = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
) as {
	observability?: {
		public_telemetry_keep_months?: number;
		item_health_full_grain_months?: number;
	};
};

const PRESETS = CONFIG.console?.window_presets ?? [7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

/** The tree the site was built from. The suite builds from the canaries. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

/** N days earlier, in UTC, so the suite cannot drift west. */
function minus(date: string, days: number): string {
	const at = new Date(`${date}T00:00:00Z`);
	at.setUTCDate(at.getUTCDate() - days);
	return at.toISOString().slice(0, 10);
}

/** The month stems the cleanup leaves under `frontend/public/telemetry/`.
 *
 * The same arithmetic as `oldest_month_kept` in `backend/idhazh/retention.py`:
 * the month being written counts as one of them, so 14 on any day of August 2026
 * keeps 2025-07 through 2026-08. Restated here on purpose - nothing in a browser
 * can call the writer - so this is the reader's half of the promise and never
 * the authority on it. The writer's half is
 * `backend/tests/test_retention.py::test_the_oracle_fifteen_months_leave_...`,
 * which sweeps the same property through `ledger.shards_in_window`.
 */
function monthsKept(today: string, months: number): string[] {
	const [year, month] = today.split('-').map(Number);
	const newest = year * 12 + (month - 1);
	return Array.from({ length: months }, (_, index) => {
		const total = newest - (months - 1) + index;
		const stem = String(Math.floor(total / 12)).padStart(4, '0');
		return `${stem}-${String((total % 12) + 1).padStart(2, '0')}`;
	});
}

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every day the Pipelines daily table can draw a row for: one per committed
 * run manifest, whatever the visual planner did on it. */
function chartArmDays(): string[] {
	const root = join(CANARY, 'digest');
	const found: string[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(join(root, year))) {
			for (const day of dirs(join(root, year, month))) {
				if (existsSync(join(root, year, month, day, 'run.json'))) {
					found.push(`${year}-${month}-${day}`);
				}
			}
		}
	}
	return found.sort();
}

function csvDates(dir: string, keep: (row: Record<string, string>) => boolean): string[] {
	if (!existsSync(dir)) return [];
	return readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(dir, name)).rows)
		.filter(keep)
		.map((row) => row.date ?? '')
		.filter(Boolean);
}

/** Every day the Summaries daily table can draw a row for, read off the two
 * committed ledgers rather than off the page it is checking. */
function workedDays(): string[] {
	const scored = csvDates(join(CANARY, 'state', 'scores'), () => true);
	const ran = csvDates(
		join(CANARY, 'state', 'item-health'),
		(row) => Number(row.summarize_ms) > 0
	);
	return [...new Set([...scored, ...ran])].sort();
}

/** The span the retirement rule is stated over, from the module that owns it. */
const RULE_DAYS = 14;

async function hydrated(page: Page) {
	// Disabled in the prerendered document and enabled on mount, so waiting for
	// it is waiting for the control to be able to do anything at all.
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	// The label is the target, not the 1px input inside it - that is what a
	// person clicks and what a thumb can hit.
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** Every surface that claims to follow the window, and what it says it shows. */
async function windowed(page: Page) {
	return page.locator('[data-windowed]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			name: node.getAttribute('data-windowed') ?? '',
			days: Number(node.getAttribute('data-window-days')),
			// A label where there is one, and the words on the surface otherwise.
			// Both are what somebody reading the page is given.
			says: `${node.getAttribute('aria-label') ?? ''} ${node.textContent ?? ''}`.replace(
				/\s+/g,
				' '
			)
		}))
	);
}

test('a window of N days is exactly N days, whatever the ledger holds', () => {
	// It used to shrink to the rows it found. That was invisible while nothing
	// named the span and a lie the moment a control does: a page reading 90 while
	// the charts draw 2 cannot be trusted about anything else.
	const short = ['2026-08-27', '2026-08-28'];
	expect(windowOfDays(short, '2026-08-28', 30, 'right')).toEqual({
		start: '2026-07-30',
		end: '2026-08-28'
	});
	expect(windowOfDays(short, '2026-08-28', 7, 'right')).toEqual({
		start: '2026-08-22',
		end: '2026-08-28'
	});
	// With nothing on record at all it hangs off the build clock instead.
	expect(windowOfDays([], '2026-08-28', 7, 'right')).toEqual({
		start: '2026-08-22',
		end: '2026-08-28'
	});
	// Centred pushes the end past the newest day, which is the anchor's whole
	// purpose: room on the right for days that have not happened yet.
	expect(windowOfDays(short, '2026-08-28', 7, 'centre').end).toBe('2026-08-31');
});

test('a step lands on a preset, and stops at the ends rather than wrapping', () => {
	expect(stepPreset(30, PRESETS, 1)).toBe(90);
	expect(stepPreset(30, PRESETS, -1)).toBe(14);
	expect(stepPreset(90, PRESETS, 1)).toBe(90);
	expect(stepPreset(7, PRESETS, -1)).toBe(7);
	// A span that is not a preset still steps to the neighbouring one, so a
	// window left by a pan cannot strand the keys.
	expect(stepPreset(21, PRESETS, 1)).toBe(30);
	expect(stepPreset(21, PRESETS, -1)).toBe(14);
});

test('the cost of widening is the months not already in hand, and never a 404', () => {
	const available = ['2026-06', '2026-07', '2026-08'];
	expect(
		monthsToFetch({ start: '2026-08-01', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual([]);
	expect(
		monthsToFetch({ start: '2026-06-15', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual(['2026-06', '2026-07']);
	// A month the pipeline never published is not a cost. Asking for it would
	// only produce a 404 and a gap the charts already draw.
	expect(
		monthsToFetch({ start: '2026-04-01', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual(['2026-06', '2026-07']);
});

test('the widest window this control offers never names a shard the cleanup age took', () => {
	// `retention.prune_telemetry` deletes the browser's copy of a month past
	// `observability.public_telemetry_keep_months`, and that knob must equal the
	// ledger's own window. This is the reader's half of the same promise: over
	// every anchor a year can offer, the months the widest read selects are all
	// months the cleanup kept, so widening costs a fetch and never a 404.
	//
	// It reads both knobs rather than 366 and 14, because the two configs are
	// where the pair is set and a test that repeated the numbers would agree with
	// itself after an edit moved them.
	const keepMonths = APP.observability?.public_telemetry_keep_months ?? 14;
	const maxDays = CONFIG.console?.max_window_days ?? 366;
	expect(keepMonths).toBe(APP.observability?.item_health_full_grain_months ?? 14);

	for (let offset = 0; offset < 366; offset += 1) {
		const today = minus('2026-12-31', offset);
		const kept = monthsKept(today, keepMonths);
		const widest = windowOfDays([today], today, maxDays, 'right');
		expect(
			monthsToFetch(widest, kept, []),
			`a ${maxDays}-day read on ${today} wants a month ${keepMonths} months of cleanup removed`
		).toEqual(monthsInWindow(widest));
	}
});

test('THE ORACLE: every windowed surface reports the day count the control does', async ({
	page
}) => {
	await page.goto('/console/');
	await hydrated(page);

	// Four presets and at least four surfaces, or the loop below is a formality.
	expect(PRESETS.length, 'a control with one option cannot disagree with anything').toBeGreaterThan(
		1
	);
	const found = await windowed(page);
	expect(
		found.map((surface) => surface.name).sort(),
		'the page publishes no windowed surfaces, so the oracle asserts nothing'
	).toEqual([
		'band-distance',
		'chart-arm',
		'failure-rate',
		'feed-outcomes',
		'run-health',
		'site-cost-per-item',
		'source-cuts',
		'telemetry-viewport'
	]);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toContain(
				`${preset} days`
			);
		}
	}
});

test('THE ORACLE: the Model route obeys the same control over its own surfaces', async ({
	page
}) => {
	// The measure cards left /console/ for /console/model/ on 2026-08-30, and a
	// windowed surface on a route with its own copy of the control is exactly
	// where two windows start to disagree. Same oracle, same loop, other route.
	await page.goto('/console/model/');
	await hydrated(page);

	const found = await windowed(page);
	expect(
		found.map((surface) => surface.name).sort(),
		'the model route publishes no windowed surfaces, so the oracle asserts nothing'
	).toEqual(['daily-figures', 'model-cards']);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		for (const surface of await windowed(page)) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toContain(
				`${preset} days`
			);
		}
	}
});

test('THE ORACLE: the Machine route obeys the same control over its own surfaces', async ({
	page
}) => {
	// It was the one console route with no control at all, so an operator who
	// picked 7 days on Pipelines lost it the moment he asked what the machine
	// was doing. Same oracle, same loop, third route.
	await page.goto('/console/machine/');
	await hydrated(page);

	const found = await windowed(page);
	expect(
		found.map((surface) => surface.name).sort(),
		'the machine route publishes no windowed surfaces, so the oracle asserts nothing'
	).toEqual([
		'machine-cache',
		'machine-context',
		'machine-cost',
		'machine-host',
		'machine-latency',
		'machine-runs',
		'machine-tokens'
	]);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toContain(
				`${preset} days`
			);
		}
	}
});

/** The first day the Machine route says it is showing, at the open preset. */
async function machineSpan(page: Page) {
	const said = (await page.locator('[data-windowed="machine-runs"]').innerText())
		.replace(/\s+/g, ' ')
		.trim();
	const dates = /(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})/.exec(said);
	return {
		runs: Number(/^(\d+) runs? in these/.exec(said)?.[1] ?? 0),
		start: dates?.[1] ?? '',
		end: dates?.[2] ?? '',
		bars: await page.locator('[data-context-run]').count()
	};
}

test('the Machine route draws the narrower span, not only the narrower label', async ({ page }) => {
	// A route that wired the day count onto its surfaces and drew the same runs
	// at every preset would pass the oracle above. The canary puts one run forty
	// days back, so only the widest preset reaches it: the counts are read off
	// the page rather than typed here, because a number written in a test goes
	// stale the day the fixture grows a row, and it goes stale silently.
	await page.goto('/console/machine/');
	await hydrated(page);

	await setWindow(page, 90);
	const wide = await machineSpan(page);
	await setWindow(page, 7);
	const narrow = await machineSpan(page);

	expect(narrow.end, 'the two spans end on different days').toBe(wide.end);
	expect(narrow.start > wide.start, 'narrowing did not move the first day').toBe(true);
	expect(wide.runs, 'the widest span reached no further run').toBeGreaterThan(narrow.runs);
	expect(wide.bars, 'the context panel drew the same bars at both spans').toBeGreaterThan(
		narrow.bars
	);
});

test('the panels about one run say so, and hold still while the window moves', async ({ page }) => {
	// Decision #2 of the row: a window is a span, and a span cannot narrow a
	// single run. The shard board, the split, the clock check and the latency
	// curves are snapshots, so they name the run they are about rather than
	// emptying out when an operator picks seven days.
	await page.goto('/console/machine/');
	await hydrated(page);

	const exempt = page.locator('[data-window-exempt="newest-run"]');
	await expect(exempt).toContainText('do not follow the window');
	await expect(exempt).not.toHaveAttribute('data-window-days', /.*/);

	const board = page.locator('[data-shard-board]');
	const before = await board.innerText();
	await setWindow(page, 7);
	expect(await board.innerText(), 'the shard board followed the window').toBe(before);
	await setWindow(page, 90);
	expect(await board.innerText(), 'the shard board followed the window').toBe(before);
});

test('THE ORACLE: the span picked on one console route is the span the next one opens on', async ({
	page
}) => {
	// The three routes share `idhazh:console-window`, which is the whole reason
	// the key exists: an operator comparing a slow day across Pipelines and
	// Hardware cannot do it if the two are on different spans. Bite-proofed both
	// ways round, because a route that only writes the key and never reads it
	// passes a one-way check.
	await page.goto('/console/');
	await hydrated(page);
	await setWindow(page, 7);
	expect(await page.evaluate(() => localStorage.getItem('idhazh:console-window'))).toBe('7');

	await page.goto('/console/machine/');
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await expect(page.locator('[data-window-preset="7"]')).toHaveAttribute('data-selected', 'true');
	const carried = await machineSpan(page);

	// And it is the span the route draws, not only the span it prints.
	await setWindow(page, 90);
	const widened = await machineSpan(page);
	expect(widened.runs, 'the carried span drew everything the widest one did').toBeGreaterThan(
		carried.runs
	);

	// Back the other way: Hardware writes the key and Pipelines reads it.
	await setWindow(page, 14);
	await page.goto('/console/');
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '14');
	for (const surface of await windowed(page)) {
		expect(surface.days, `${surface.name} ignored the span carried from Hardware`).toBe(14);
	}
});

/** The three numbers the source section prints about its own window. */
async function cutFacts(page: Page) {
	// Named, not positional. The cost sentence sits above this one now, and a
	// `p` picked by order silently reads whichever paragraph moved into first
	// place rather than failing.
	const intro = (
		await page.locator('[data-source-cuts-intro]').innerText()
	).replace(/\s+/g, ' ');
	const more = (await page.locator('[data-source-cuts-more]').innerText()).replace(/\s+/g, ' ');
	const cost = (await page.locator('[data-source-cuts-cost]').innerText()).replace(/\s+/g, ' ');
	return {
		// Thousands are grouped in the sentence, so the comma is stripped rather
		// than the digits before it being read as the whole count.
		articles: Number(/, ([\d,]+) articles between them/.exec(intro)?.[1]?.replace(/,/g, '')),
		tailSources: Number(/(\d+) more sources/.exec(more)?.[1]),
		cut: Number(/(\d+) articles were cut short/.exec(cost)?.[1])
	};
}

test('the source table follows the window, and drops what falls outside it', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	// The canary writes one cut ten days back, under a source with a single cut.
	// Seven days cannot reach it and every wider preset can, so the section's own
	// counts move with the control rather than only its heading. They are read
	// rather than typed: a number written here goes stale the day the fixture
	// grows a row, and it goes stale silently.
	await setWindow(page, 7);
	const narrow = await cutFacts(page);
	await setWindow(page, 90);
	const wide = await cutFacts(page);

	expect(narrow.articles, 'the section prints no denominator').toBeGreaterThan(0);
	expect(wide.articles, 'widening reached no further article').toBeGreaterThan(narrow.articles);
	expect(wide.cut, 'widening reached no further cut').toBeGreaterThan(narrow.cut);
	// The older cut belongs to a source with one cut, so it lands in the tail
	// rather than the printed ten. The tail is where it has to show up.
	expect(wide.tailSources, 'the tail did not gain the older source').toBeGreaterThan(
		narrow.tailSources
	);

	// And the denominator is on the page, because at seven days it runs as low
	// as six articles and a share over six is not a rate. `\s+` rather than a
	// space: the sentence wraps in the template, and a regex reads the raw text.
	await expect(page.locator('[data-windowed="source-cuts"]')).toContainText(
		/[\d,]+\s+articles between/
	);
});

test('a rule stated over 14 days prints no median in a 7-day window', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	const section = page.locator('[data-windowed="chart-arm"]');
	await setWindow(page, RULE_DAYS);
	await expect(section.locator('[data-window-too-narrow="chart-arm"]')).toHaveCount(0);

	await setWindow(page, 7);
	// The exact sentence, because a median of the wrong span is the same figure
	// with a different meaning and nothing on the page to say which one it is.
	await expect(section.locator('[data-window-too-narrow="chart-arm"]')).toHaveText(
		'The rule reads 14 days. Widen the window to see it.'
	);
	await expect(section.locator('[data-charts-verdict]')).toHaveCount(0);
});

test('two surfaces do not follow the window, and each says so', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	// A windowed quarantine count would disagree with the resting the pipeline
	// actually performed, so the feed count reads every run and states it. The
	// strip of days beside it does follow the window, and is a separate node -
	// which is why this locator is the paragraph and not the section.
	const feeds = page.locator('[data-window-exempt="feeds"]');
	await expect(feeds).toContainText('does not follow the window');
	await expect(feeds).not.toHaveAttribute('data-window-days', /.*/);

	// The site size is a level, not a rate, and since 2026-08-30 it is in the
	// standing band - which is not windowed at all, because that band stands on
	// all three console routes and a figure that moved with a control on one of
	// them would read as three different sites. So the whole sentence holds at
	// every preset, not only the number in it.
	const size = page.locator('[data-band-size]');
	const before = ((await size.textContent()) ?? '').trim();
	await setWindow(page, 7);
	await expect(size).toHaveText(before);
	await expect(size).toContainText(/of the 1 GB limit/);
});

/** Both daily tables, and what each says about the span it is drawn over. */
async function disclosures(page: Page) {
	return page.locator('[data-daily-figures]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			name: node.getAttribute('data-daily-figures') ?? '',
			summary: (node.querySelector(':scope > summary')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
			dates: [...node.querySelectorAll('[data-chart-day], [data-model-day]')].map(
				(row) =>
					row.getAttribute('data-chart-day') ?? row.getAttribute('data-model-day') ?? ''
			)
		}))
	);
}

/** The day the open window ends on, taken from the page rather than the clock.
 *
 * `windowOfDays` anchors on the newest date it is handed, not on today, and the
 * two routes hand it different arrays - Pipelines the telemetry dates and
 * Summaries the days the model worked. The run strip draws one column per day
 * of the window, so its last column IS the end; on Summaries the table's own
 * widest reading is, because the same array anchors both.
 */
async function endOfWindow(page: Page, route: string, widest: string[]): Promise<string> {
	if (route !== '/console/') return [...widest].sort().at(-1) as string;
	const days = await page
		.locator('[data-grid="days"] [data-day]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-day') ?? ''));
	return [...days].sort().at(-1) as string;
}

test('THE ORACLE: a daily table drawn under the control is drawn over the control span', async ({
	page
}) => {
	// The two tables ignored the preset above them until 2026-08-31, so the cards
	// on Summaries said 7 days while the rows under them held every day the
	// ledger ever wrote. Two answers to one question on one page is exactly what
	// the shared control was built to remove.
	//
	// Every date is read off the page and checked against a second reading of the
	// committed fixture, never typed: a number written into a test goes stale the
	// day the fixture grows a row, and it goes stale silently.
	const widest = Math.max(...PRESETS);
	for (const [route, committed] of [
		['/console/', chartArmDays()],
		['/console/model/', workedDays()]
	] as const) {
		await page.goto(route);
		await hydrated(page);

		expect((await disclosures(page)).length, `${route} publishes no daily table`).toBe(1);
		expect(committed.length, `${route} has no committed day to window`).toBeGreaterThan(0);

		// The widest preset reaches every day the fixture wrote, which is what makes
		// a narrower one a cut rather than a coincidence.
		await setWindow(page, widest);
		const [wide] = await disclosures(page);
		expect(
			[...wide.dates].sort(),
			`${route} does not draw every committed day at ${widest} days`
		).toEqual(committed);
		const end = await endOfWindow(page, route, wide.dates);

		const counts = new Set<number>();
		for (const preset of PRESETS) {
			await setWindow(page, preset);
			const [table] = await disclosures(page);
			// The name is one string on both routes and it says the span out loud.
			expect(table.summary, `${route} renamed its daily table`).toContain(
				'Show these figures day by day'
			);
			expect(
				table.summary,
				`${route} opens a table without saying how many days are in it`
			).toContain(`${preset} days`);

			const first = minus(end, preset - 1);
			const inside = committed.filter((date) => date >= first && date <= end);
			expect(
				[...table.dates].sort(),
				`${route} at ${preset} days drew ${table.dates.length} rows where ${inside.length} days of the window carry data`
			).toEqual(inside);
			counts.add(table.dates.length);
		}
		// A table that returned the same rows at every preset would satisfy every
		// assertion above on a fixture narrower than the narrowest window.
		expect(
			counts.size,
			`${route} drew the same row count at all four presets`
		).toBeGreaterThan(1);
	}
});

test('a shut daily table is a line of prose, not a card', async ({ page }) => {
	// Shut, it was a bordered, shadowed, rounded card wrapped around one line of
	// link text - the visual weight of a section with the content of a footnote,
	// which is what made it read as something hanging off the page. An eye cannot
	// check a box-shadow, so this reads the computed values against the prose
	// beside it rather than against a hard-coded string.
	for (const route of ['/console/', '/console/model/']) {
		await page.goto(route);
		const shut = await page.locator('[data-daily-figures]').evaluate((node) => {
			const details = node as HTMLDetailsElement;
			details.open = false;
			const style = getComputedStyle(details);
			return {
				open: details.open,
				border: style.borderTopWidth,
				shadow: style.boxShadow,
				background: style.backgroundColor,
				padding: style.paddingTop
			};
		});
		expect(shut.open, `${route} opens its daily table on arrival`).toBe(false);
		expect(shut.border, `${route} keeps a border on a shut disclosure`).toBe('0px');
		expect(shut.shadow, `${route} keeps a shadow on a shut disclosure`).toBe('none');
		expect(shut.padding, `${route} keeps a card's padding on a shut disclosure`).toBe('0px');
		expect(
			['rgba(0, 0, 0, 0)', 'transparent'],
			`${route} keeps a card background on a shut disclosure: ${shut.background}`
		).toContain(shut.background);

		// And open it is a panel again, because then it holds one.
		const opened = await page.locator('[data-daily-figures]').evaluate((node) => {
			(node as HTMLDetailsElement).open = true;
			const style = getComputedStyle(node);
			return { border: style.borderTopWidth, shadow: style.boxShadow };
		});
		expect(opened.border, `${route} draws no frame around an open table`).not.toBe('0px');
		expect(opened.shadow, `${route} draws no elevation on an open table`).not.toBe('none');
	}
});

test('the prerendered page opens on the configured window, whatever was stored', async ({
	page
}) => {
	await page.goto('/console/');
	await hydrated(page);
	await setWindow(page, PRESETS.at(-1) as number);

	// Read on mount and never during prerender: the document a browser is handed
	// is always the window the server drew, so first paint cannot flicker.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('data-window-control');
	expect(document).toContain(`data-window-days="${DEFAULT_DAYS}"`);

	await page.reload();
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(PRESETS.at(-1))
	);
});

test('the control names the window it is holding, and is inert before a script runs', async ({
	page
}) => {
	await page.goto('/console/');

	const status = page.locator('[data-window-status]');
	await hydrated(page);
	await expect(status).toContainText(`showing ${DEFAULT_DAYS} days`);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');

	// Every preset is on the page at once. A menu would hide the wide one, which
	// is the one with a cost worth reading before it is paid.
	for (const preset of PRESETS) {
		await expect(page.locator(`[data-window-preset="${preset}"]`)).toBeVisible();
	}

	// And the prerendered document says it needs a script rather than offering a
	// control that would do nothing when clicked.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('This control needs JavaScript');
	expect(document).toMatch(/<input[^>]*name="console-window"[^>]*disabled/);
});
