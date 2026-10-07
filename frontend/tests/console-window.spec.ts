import { expect, test, type Page } from './support/browser';
import { ONE_DAYS, spanSaid } from './support/span-said';
import { serverCompiler, type Rewrite } from './support/server-render';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import {
	daysInWindow,
	monthsInWindow,
	monthsToFetch,
	stepPreset,
	windowOfDays
} from '../src/lib/charts/viewport';
import type { JudgeDay, LineDay } from '../src/lib/console/merge-line';

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

/** The cleanup ages, from the declaration that sets them. A published shard older
 * than the `public-copy` series is deleted by the gardener's `telemetry-aggregate`
 * task, so the widest read this control offers has to stay inside what that leaves. */
const TELEMETRY = JSON.parse(
	readFileSync(
		resolve(process.cwd(), '..', 'config', 'gardener', 'telemetry-aggregate.json'),
		'utf8'
	)
) as {
	series?: Record<string, { unit: string; value?: number }>;
};

const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 14;

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
 * `backend/tests/gardener/tasks/test_telemetry_aggregate_task.py::test_the_fold_keeps_the_configured_window_at_full_grain`,
 * which runs the task that deletes the months over twenty of them.
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

test('a window of N days is exactly N days, and ends on the day it is handed', () => {
	// It used to shrink to the rows it found. That was invisible while nothing
	// named the span and a lie the moment a control does: a page reading 90 while
	// the charts draw 2 cannot be trusted about anything else. It also used to end
	// on the newest date in the rows it was handed, so a record that stopped moved
	// its window into the past; every route now hands it the newest published day.
	expect(windowOfDays('2026-08-28', 30, 'right')).toEqual({
		start: '2026-07-30',
		end: '2026-08-28'
	});
	expect(windowOfDays('2026-08-28', 7, 'right')).toEqual({
		start: '2026-08-22',
		end: '2026-08-28'
	});
	expect(windowOfDays('2026-08-28', 1, 'right')).toEqual({
		start: '2026-08-28',
		end: '2026-08-28'
	});
	// Centred pushes the end past the day it is handed, which is the anchor's whole
	// purpose: room on the right for days that have not happened yet.
	expect(windowOfDays('2026-08-28', 7, 'centre')).toEqual({
		start: '2026-08-25',
		end: '2026-08-31'
	});
});

test('a step lands on a preset, and stops at the ends rather than wrapping', () => {
	// The ends are read off the list, never written down. Seven was the narrowest
	// preset until a one-day span was added on 2026-09-06, and a literal end
	// stops testing the end the moment the list moves under it.
	const narrowest = Math.min(...PRESETS);
	const widest = Math.max(...PRESETS);

	expect(stepPreset(30, PRESETS, 1)).toBe(90);
	expect(stepPreset(30, PRESETS, -1)).toBe(14);
	expect(stepPreset(widest, PRESETS, 1)).toBe(widest);
	expect(stepPreset(narrowest, PRESETS, -1)).toBe(narrowest);
	expect(stepPreset(7, PRESETS, -1)).toBe(1);
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
	// The gardener's `telemetry-aggregate` task deletes the browser's copy of a
	// month past its `public-copy` series, and that series must equal the ledger's
	// own `full-grain` one. This is the reader's half of the same promise: over
	// every anchor a year can offer, the months the widest read selects are all
	// months the cleanup kept, so widening costs a fetch and never a 404.
	//
	// It reads both windows rather than 366 and 14, because the two configs are
	// where the pair is set and a test that repeated the numbers would agree with
	// itself after an edit moved them.
	const publicCopy = TELEMETRY.series?.['public-copy'];
	expect(publicCopy?.unit, 'the public copy is kept in whole months').toBe('months');
	const keepMonths = publicCopy?.value ?? 0;
	const maxDays = CONFIG.console?.max_window_days ?? 366;
	expect(keepMonths).toBe(TELEMETRY.series?.['full-grain']?.value);

	for (let offset = 0; offset < 366; offset += 1) {
		const today = minus('2026-12-31', offset);
		const kept = monthsKept(today, keepMonths);
		const widest = windowOfDays(today, maxDays, 'right');
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
		'chart-drawing',
		'extraction',
		'failure-rate',
		'item-cost',
		'run-health',
		'site-cost-per-item',
		'telemetry-viewport'
	]);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toMatch(
				spanSaid(preset)
			);
			expect(surface.says, `${surface.name} says "1 days"`).not.toMatch(ONE_DAYS);
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
			expect(surface.says, `${surface.name} never says how many days it is showing`).toMatch(
				spanSaid(preset)
			);
			expect(surface.says, `${surface.name} says "1 days"`).not.toMatch(ONE_DAYS);
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
		'machine-article-cost',
		'machine-context',
		'machine-cost',
		'machine-disk-reads',
		'machine-fleet',
		'machine-latency',
		'machine-processor-lost',
		'machine-prompt-reuse',
		'machine-runs',
		'machine-tokens'
	]);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toMatch(
				spanSaid(preset)
			);
			expect(surface.says, `${surface.name} says "1 days"`).not.toMatch(ONE_DAYS);
		}
	}
});

test('THE ORACLE: the Voices route obeys the same control over its own surfaces', async ({
	page
}) => {
	// The four feed and source panels left /console/ for /console/voices/ on
	// 2026-09-14, and two of the four follow the control. They arrived on a route
	// that had none, so this is the pair the move could most easily have stranded:
	// a surface that still declares a day count while nothing on the page can
	// change it. Same oracle, same loop, fourth route.
	await page.goto('/console/voices/');
	await hydrated(page);

	const found = await windowed(page);
	expect(
		found.map((surface) => surface.name).sort(),
		'the voices route publishes no windowed surfaces, so the oracle asserts nothing'
	).toEqual(['feed-outcomes', 'source-cuts']);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toMatch(
				spanSaid(preset)
			);
			expect(surface.says, `${surface.name} says "1 days"`).not.toMatch(ONE_DAYS);
		}
	}
});

test('THE ORACLE: the Judgement route obeys the same control over its own surfaces', async ({
	page
}) => {
	// Four panels on Judgement follow the control. Three of them named no span:
	// the judge's agreement with itself never did, the record's needs only once a
	// line was fitted, and the merge line only once a fitted day was in the
	// window. Same oracle, same loop, fifth route. It reaches only the states the
	// canary draws; the cases below draw each of the three in the states that
	// named no span, from days the test builds.
	await page.goto('/console/judgement/');
	await hydrated(page);

	const found = await windowed(page);
	expect(
		found.map((surface) => surface.name).sort(),
		'the judgement route publishes no windowed surfaces, so the oracle asserts nothing'
	).toEqual(['judge-agreement', 'merge-line', 'merged-stories', 'record-gates']);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toMatch(
				spanSaid(preset)
			);
			expect(surface.says, `${surface.name} says "1 days"`).not.toMatch(ONE_DAYS);
		}
	}
});

/** The newest published day every case below is drawn on. Each window ends on it. */
const JUDGED_THROUGH = '2030-06-15';

/** The three gates, the two limits and the share floor the cases hand the
 * panels. Written here, so every number in a sentence below is one this file chose. */
const GATES = { minimumNegatives: 200, minimumDays: 10, minimumAboveLine: 30 };
const LIMITS = { disagreementMax: 0.15, unclearMax: 0.35 };
const SHARE_FLOOR = 5;

/** The size a panel is drawn at moves no word, so every case draws at one size. */
const DRAWN_AT = { height: 220, width: 760, tickDensity: 6, readoutMaxShare: 1 };

/** A record holding all three counts the gates ask for, and one short of all three. */
const FILLED = { negativesOnRecord: 250, daysOnRecord: 12, aboveLineOnRecord: 40 };
const FILLING = {
	negativesOnRecord: 120,
	daysOnRecord: 6,
	aboveLineOnRecord: 12,
	heldReason: 'sheet_too_small'
};

/** One day of the judge's record: nothing read and nothing held, unless a case says so. */
function judgeDay(date: string, over: Partial<JudgeDay> = {}): JudgeDay {
	return {
		date,
		disagreementRate: 0,
		unclearRate: 0,
		pairsJudged: 0,
		negativesOnRecord: 0,
		aboveLineOnRecord: 0,
		daysOnRecord: 0,
		heldReason: 'none',
		...over
	};
}

/** One fitted day of the merge line. */
function lineDay(date: string): LineDay {
	return {
		date,
		previous: 0.94,
		proposed: 0.95,
		applied: 0.943,
		clampKind: 'none',
		heldReason: 'none',
		maxDownStep: 0.01,
		maxUpStep: 0.003
	};
}

/** One panel in one state at one window, and every word it owes about its days. */
type SpanCase =
	| {
			surface: 'judge-agreement' | 'record-gates';
			preset: number;
			state: string;
			days: JudgeDay[];
			words: string;
	  }
	| {
			surface: 'merge-line';
			preset: number;
			state: string;
			days: LineDay[];
			words: string;
			/** The dashed rule's label. */
			label: string;
	  };

/** Where each panel prints its sentences about its own days. */
const SAID = {
	'judge-agreement': '[data-agreement-state]',
	'record-gates': '[data-gates-note]',
	'merge-line': '[data-line-state]'
} as const;

/** The words are Reader's, written out whole, one case a state and a window. */
const SPAN_CASES: SpanCase[] = [
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'no pair was read twice',
		days: [],
		words: 'No pair was read twice in these 7 days, so there is nothing to compare.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'no pair was read twice in it, though some were the day before',
		days: [judgeDay('2030-06-14', { pairsJudged: 40, disagreementRate: 0.05 })],
		words: 'No pair was read twice in this one day, so there is nothing to compare.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'three pairs were read twice, too few for a share',
		days: [judgeDay('2030-06-12', { pairsJudged: 2 }), judgeDay('2030-06-15', { pairsJudged: 1 })],
		words:
			'3 pairs were read twice in these 7 days. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'one pair was read twice',
		days: [judgeDay('2030-06-15', { pairsJudged: 1 })],
		words:
			'1 pair was read twice in these 7 days. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'three pairs were read twice, too few for a share',
		days: [judgeDay('2030-06-15', { pairsJudged: 3 })],
		words:
			'3 pairs were read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'one pair was read twice',
		days: [judgeDay('2030-06-15', { pairsJudged: 1 })],
		words:
			'1 pair was read twice in this one day. That is too few to report a share, so the counts are above.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'two days were held because the judge was unreliable',
		days: [
			judgeDay('2030-06-13', { pairsJudged: 40, disagreementRate: 0.2, heldReason: 'judge_unstable' }),
			judgeDay('2030-06-15', {
				pairsJudged: 60,
				disagreementRate: 0.05,
				unclearRate: 0.4,
				heldReason: 'judge_uncertain'
			})
		],
		words:
			'The two readings disagreed on 11% of 100 pairs in these 7 days. No line was fitted on 2 of 7 days, because a rate was past its mark on those days.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'one day was held because the judge was unreliable',
		days: [
			judgeDay('2030-06-14', { pairsJudged: 50, disagreementRate: 0.04 }),
			judgeDay('2030-06-15', { pairsJudged: 50, disagreementRate: 0.3, heldReason: 'judge_unstable' })
		],
		words:
			'The two readings disagreed on 17% of 100 pairs in these 7 days. No line was fitted on 1 of 7 days, because a rate was past its mark on that day.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'its day was held because the judge was unreliable',
		days: [judgeDay('2030-06-15', { pairsJudged: 40, disagreementRate: 0.25, heldReason: 'judge_unstable' })],
		words:
			'The two readings disagreed on 25% of 40 pairs in this one day. No line was fitted on 1 of 1 day, because a rate was past its mark on that day.'
	},
	{
		surface: 'judge-agreement',
		preset: 7,
		state: 'both rates are inside the marks',
		days: [
			judgeDay('2030-06-10', { pairsJudged: 200, disagreementRate: 0.03, unclearRate: 0.01 }),
			judgeDay('2030-06-15', { pairsJudged: 200, disagreementRate: 0.03, unclearRate: 0.01 })
		],
		words:
			'In these 7 days, 3% of 400 pairs disagreed with their own second reading, and 1% of 400 pairs could not tell. Both rates are inside the marks.'
	},
	{
		surface: 'judge-agreement',
		preset: 1,
		state: 'both rates are inside the marks',
		days: [judgeDay('2030-06-15', { pairsJudged: 40, disagreementRate: 0.05, unclearRate: 0.1 })],
		words:
			'In this one day, 5% of 40 pairs disagreed with their own second reading, and 10% of 40 pairs could not tell. Both rates are inside the marks.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'nothing was judged',
		days: [],
		words:
			'Nothing was judged in these 7 days. The three bars are what the record needs before a line may be fitted at all.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'nothing was judged in it, though the record has a row the day before',
		days: [judgeDay('2030-06-14', FILLING)],
		words:
			'Nothing was judged in this one day. The three bars are what the record needs before a line may be fitted at all.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the record is still filling and no line was fitted',
		days: [judgeDay('2030-06-12', { ...FILLING, negativesOnRecord: 100 }), judgeDay('2030-06-15', FILLING)],
		words:
			'The record has 120 of the 200 readings it needs, 6 of 10 days, and 12 of 30 pairs above the line. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'the record is still filling and no line was fitted',
		days: [judgeDay('2030-06-15', FILLING)],
		words:
			'The record has 120 of the 200 readings it needs, 6 of 10 days, and 12 of 30 pairs above the line. No line was fitted in this one day.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the newest four days counted nothing and no line was fitted',
		days: [judgeDay('2030-06-11', { ...FILLED, heldReason: 'judge_unstable' })],
		words: 'Nothing has been counted for 4 days. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the newest day counted nothing and no line was fitted',
		days: [judgeDay('2030-06-14', { ...FILLED, heldReason: 'judge_uncertain' })],
		words: 'Nothing has been counted for 1 day. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 7,
		state: 'the record has what it needs and every day was held',
		days: [
			judgeDay('2030-06-13', { ...FILLED, heldReason: 'judge_unstable' }),
			judgeDay('2030-06-15', { ...FILLED, heldReason: 'shards_missing' })
		],
		words:
			'The record has what it needs. These three bars stay so a record that empties is visible. No line was fitted in these 7 days.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'the record has what it needs and its day was held',
		days: [judgeDay('2030-06-15', { ...FILLED, heldReason: 'judge_uncertain' })],
		words:
			'The record has what it needs. These three bars stay so a record that empties is visible. No line was fitted in this one day.'
	},
	{
		// The other side of the same choice: a fitted day replaces the sentence
		// that says none was, rather than standing beside it.
		surface: 'record-gates',
		preset: 7,
		state: 'a line was fitted on one day',
		days: [
			judgeDay('2030-06-14', FILLED),
			judgeDay('2030-06-15', { ...FILLED, heldReason: 'judge_unstable' })
		],
		words:
			'The record has what it needs. These three bars stay so a record that empties is visible. A line was fitted on 1 of 7 days.'
	},
	{
		surface: 'merge-line',
		preset: 7,
		state: 'no line was ever fitted',
		days: [],
		words:
			'No line was fitted in these 7 days. The rule is the line the newest day was built with, and the scale is the whole range a fitted line may take.',
		label: 'The line the newest day was built with'
	},
	{
		surface: 'merge-line',
		preset: 1,
		state: 'no line was fitted in it, though one was the day before',
		days: [lineDay('2030-06-14')],
		words:
			'No line was fitted in this one day. The rule is the line this one day was built with, and the scale is the whole range a fitted line may take.',
		label: 'The line this one day was built with'
	}
];

/** What a panel is handed around the days a case builds, as the route hands it. */
function propsOf(one: SpanCase): Record<string, unknown> {
	const viewport = windowOfDays(JUDGED_THROUGH, one.preset, 'right');
	switch (one.surface) {
		case 'judge-agreement':
			return { days: one.days, limits: LIMITS, attemptsFloor: SHARE_FLOOR, viewport, ...DRAWN_AT };
		case 'record-gates':
			return {
				days: one.days,
				dates: daysInWindow(viewport),
				gates: GATES,
				viewport,
				readoutMaxShare: DRAWN_AT.readoutMaxShare
			};
		case 'merge-line':
			return {
				days: one.days,
				knobs: { band_low: 0.88, band_high: 1 },
				configuredLine: 0.94,
				markedApart: null,
				viewport,
				...DRAWN_AT
			};
	}
}

/** The text of the one node a selector names, as a reader is given it. */
async function said(page: Page, selector: string): Promise<string> {
	const node = page.locator(selector);
	await expect(node, `nothing on the panel matches ${selector}`).toHaveCount(1);
	return ((await node.textContent()) ?? '').replace(/\s+/g, ' ').trim();
}

test.describe('the Judgement panels name their span in every state, on days the test builds', () => {
	/** Each panel rendered on the server with its real children, never a stub. */
	const drawn = {} as Record<SpanCase['surface'], (props: Record<string, unknown>) => string>;

	test.beforeAll(async ({}, testInfo) => {
		// One directory a worker: a module rewritten while another worker imports
		// it is read half-written.
		const compiled = serverCompiler(
			resolve(process.cwd(), 'test-results', 'judgement-spans', String(testInfo.workerIndex))
		);
		const children: Rewrite[] = [
			['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs'],
			['$lib/components/Panel.svelte', './Panel.server.mjs'],
			['$lib/components/TargetBar.svelte', './TargetBar.server.mjs']
		];
		for (const child of ['ChartReadout', 'Panel', 'TargetBar']) {
			await compiled(`src/lib/components/${child}.svelte`, child, []);
		}
		for (const [surface, file] of [
			['judge-agreement', 'JudgeAgreement'],
			['record-gates', 'RecordGates'],
			['merge-line', 'MergeLinePlot']
		] as const) {
			const module = await compiled(`src/routes/console/judgement/${file}.svelte`, file, children);
			const component = (await import(pathToFileURL(module).href)).default;
			drawn[surface] = (props) => render(component, { props }).body;
		}
	});

	for (const one of SPAN_CASES) {
		test(`THE ORACLE: ${one.surface} names the ${one.preset}-day window when ${one.state}`, async ({
			page
		}) => {
			await page.setContent(`<main>${drawn[one.surface](propsOf(one))}</main>`);

			const [surface] = await windowed(page);
			expect(surface.name, 'the case drew a different panel').toBe(one.surface);
			expect(surface.days, `${one.surface} is drawing a different window`).toBe(one.preset);
			expect(surface.says, `${one.surface} never says how many days it is showing`).toMatch(
				spanSaid(one.preset)
			);
			expect(surface.says, `${one.surface} says "1 days"`).not.toMatch(ONE_DAYS);
			expect(await said(page, SAID[one.surface])).toBe(one.words);
			if (one.surface === 'merge-line') {
				expect(await said(page, '[data-line-rule-label]')).toBe(one.label);
			}
		});
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
	// emptying out when an operator picks seven days. Since 2026-09-20 each says
	// it in its own subtitle instead of in a paragraph above all of them: the
	// groups name a decision now, so one group holds a snapshot beside a reading
	// over the span and no heading can carry the grain for its panels.
	await page.goto('/console/machine/');
	await hydrated(page);

	const exempt = page.locator('[data-window-exempt="newest-run"]');
	await expect(exempt).toContainText('newest run');
	await expect(exempt).not.toHaveAttribute('data-window-days', /.*/);
	await expect(page.locator('[data-console-panel-id="shard-board"] > header > p')).toContainText(
		'the newest run'
	);

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
		articles: Number(/ held ([\d,]+) articles?/.exec(intro)?.[1]?.replace(/,/g, '')),
		tailSources: Number(/(\d+) more sources/.exec(more)?.[1]),
		cut: Number(/(\d+) articles were cut short/.exec(cost)?.[1])
	};
}

test('the source table follows the window, and drops what falls outside it', async ({ page }) => {
	await page.goto('/console/voices/');
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
		/held\s+[\d,]+\s+articles/
	);
});

test('a rule stated over 14 days prints no median in a 7-day window', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	const section = page.locator('[data-windowed="chart-drawing"]');
	await setWindow(page, RULE_DAYS);
	await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveCount(0);

	await setWindow(page, 7);
	// The exact sentence, because a median of the wrong span is the same figure
	// with a different meaning and nothing on the page to say which one it is.
	await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveText(
		'The rule reads 14 days. Widen the window to see it.'
	);
	await expect(section.locator('[data-charts-verdict]')).toHaveCount(0);
});

test('three surfaces do not follow the window, and each says so', async ({ page }) => {
	// The site size is a level, not a rate, and since 2026-08-30 it is in the
	// standing band - which is not windowed at all, because that band stands on
	// every console route and a figure that moved with a control on one of them
	// would read as five different sites. So the whole sentence holds at every
	// preset, not only the number in it.
	await page.goto('/console/');
	await hydrated(page);

	const size = page.locator('[data-band-size]');
	const before = ((await size.textContent()) ?? '').trim();
	await setWindow(page, 7);
	await expect(size).toHaveText(before);
	await expect(size).toContainText(/of the 1 GB limit/);

	// The other two are on Voices, which is where the feed and source panels went
	// on 2026-09-14. They arrived on a route with no control and left with one
	// above them, so the sentence that says they ignore it is load-bearing now in
	// a way it was not before the move.
	await page.goto('/console/voices/');
	await hydrated(page);

	// A windowed quarantine count would disagree with the resting the pipeline
	// actually performed, so the feed count reads every run and states it. The
	// strip of days beside it does follow the window, and is a separate node -
	// which is why this locator is the paragraph and not the section.
	const feeds = page.locator('[data-window-exempt="feeds"]');
	await expect(feeds).toContainText('does not follow the window');
	await expect(feeds).not.toHaveAttribute('data-window-days', /.*/);

	// And the ranking weight, which the run reduced over its own span when it
	// ran. Redrawing it over seven days would print a number no run applied.
	const weight = page.locator('[data-window-exempt="reliability"]');
	await expect(weight).toContainText('does not follow the window control');
	await expect(weight).not.toHaveAttribute('data-window-days', /.*/);
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

test('a daily table drawn under the control stays inside the control span', async ({
	page
}) => {
	// The two tables ignored the preset above them until 2026-08-31, so the cards
	// on Summaries said 7 days while the rows under them held every day the
	// ledger ever wrote. Two answers to one question on one page is exactly what
	// the shared control was built to remove.
	//
	// The reducer tests own which dates have rows. This browser check keeps only
	// the route contract: the open control names the span, the disclosure says
	// the same span, and every row the table does draw fits inside it.
	for (const route of ['/console/', '/console/model/'] as const) {
		await page.goto(route);
		await hydrated(page);

		expect((await disclosures(page)).length, `${route} publishes no daily table`).toBe(1);

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
			).toMatch(spanSaid(preset));
			expect(table.summary, `${route} says "1 days"`).not.toMatch(ONE_DAYS);

			const sorted = [...table.dates].sort();
			expect(new Set(sorted).size, `${route} repeated a daily row at ${preset} days`).toBe(
				sorted.length
			);
			expect(sorted.length, `${route} drew more rows than days in the control span`).toBeLessThanOrEqual(
				preset
			);
			if (sorted.length > 1) {
				const span =
					Math.round(
						(Date.parse(`${sorted[sorted.length - 1]}T00:00:00Z`) -
							Date.parse(`${sorted[0]}T00:00:00Z`)) /
							86_400_000
					) + 1;
				expect(span, `${route} drew rows outside the ${preset}-day span`).toBeLessThanOrEqual(
					preset
				);
			}
		}
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
	// control that would do nothing when clicked. It says the same of the panels
	// it governs: they hold their reserved shape with no script and nothing else,
	// because the rows they draw arrive by fetch. The sentence names the control
	// it means, because since 2026-09-27 the control is on the strip above and
	// the sentence is under the band.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('The days control above needs JavaScript');
	expect(document).toContain('they draw rows a browser fetches');
	expect(
		document,
		'the prerendered control still claims the sections below are showing data'
	).not.toContain('needs JavaScript. Every windowed section below is showing');
	expect(document).toMatch(/<input[^>]*name="console-window"[^>]*disabled/);
});

test('one day is one day, in the sentence and to a screen reader', async ({ page }) => {
	// The one-day preset read "1 days" on its tile and in the sentence under the
	// band. The tile shows `1D` now, and still says its unit to a screen reader,
	// in the singular - and the `D` is hidden from that reader, so it is never
	// heard as "1D day".
	await page.goto('/console/');
	await hydrated(page);
	const narrowest = Math.min(...PRESETS);
	expect(narrowest, 'the presets no longer offer a single day, so this proves nothing').toBe(1);
	await setWindow(page, narrowest);
	await expect(page.locator('[data-window-status]')).toContainText('showing 1 day.');
	await expect(page.locator('[data-window-preset="1"] [aria-hidden="true"]')).toHaveText('1D');
	await expect(page.getByRole('radio', { name: '1 day', exact: true })).toHaveCount(1);
	await expect(page.getByRole('radio', { name: '14 days', exact: true })).toHaveCount(1);
});

/** The control and the strip it stands on, in viewport coordinates. */
async function controlBox(page: Page) {
	return page.evaluate(() => {
		const strip = (document.querySelector('[data-console-strip]') as HTMLElement).getBoundingClientRect();
		const control = (document.querySelector('[data-window-control]') as HTMLElement).getBoundingClientRect();
		const tabs = (document.querySelector('[data-console-nav]') as HTMLElement).getBoundingClientRect();
		return {
			innerWidth: window.innerWidth,
			width: Math.round(control.width),
			height: Math.round(control.height),
			left: Math.round(control.left),
			right: Math.round(control.right),
			top: Math.round(control.top),
			stripLeft: Math.round(strip.left),
			stripRight: Math.round(strip.right),
			tabsBottom: Math.round(tabs.bottom),
			shown: [...document.querySelectorAll('[data-window-preset] [aria-hidden="true"]')].map(
				(node) => (node.textContent ?? '').trim()
			)
		};
	});
}

for (const width of [390, 768, 1440]) {
	test(`THE ORACLE: the days control is five short tiles, 236 by 44, at ${width}`, async ({
		page
	}) => {
		// Five tiles at the 2.75rem touch floor both ways, 4px apart, and nothing
		// beside them: no label and no room kept for a price. Below the wide
		// breakpoint the control starts its own row under the tabs; from it, the
		// control ends the one-row strip.
		await page.setViewportSize({ width, height: 900 });
		await page.goto('/console/');
		await hydrated(page);
		const at = await controlBox(page);
		console.log(
			`[control] asked ${width} -> innerWidth ${at.innerWidth}, ${at.width}x${at.height} ` +
				`at ${at.left}-${at.right}, strip ${at.stripLeft}-${at.stripRight}, tabs end ${at.tabsBottom}, ` +
				`control top ${at.top}`
		);
		expect(at.shown).toEqual(PRESETS.map((preset) => `${preset}D`));
		expect(Math.abs(at.width - 236), `the control is ${at.width}px wide`).toBeLessThanOrEqual(1);
		expect(Math.abs(at.height - 44), `the control is ${at.height}px tall`).toBeLessThanOrEqual(1);
		if (width < 1024) {
			expect(Math.abs(at.left - at.stripLeft), 'the control does not start its row').toBeLessThanOrEqual(1);
			expect(at.top, 'the control is not on a row of its own under the tabs').toBeGreaterThanOrEqual(
				at.tabsBottom
			);
		} else {
			expect(Math.abs(at.right - at.stripRight), 'the control left the end of the strip').toBeLessThanOrEqual(1);
		}
	});
}

/** The top of everything between the strip and the first panel, and of that
 * panel - in page coordinates, so a scroll cannot read as a move. */
async function belowTheStrip(page: Page): Promise<Record<string, number>> {
	return page.evaluate(() => {
		const tops: Record<string, number> = {};
		for (const selector of [
			'[data-console-completeness]',
			'[data-console-band]',
			'[data-window-status]',
			'[data-console-panel]'
		]) {
			const node = document.querySelector(selector);
			if (node !== null) tops[selector] = node.getBoundingClientRect().top + window.scrollY;
		}
		return tops;
	});
}

for (const width of [390, 768, 1440]) {
	test(`THE ORACLE: picking each preset moves nothing below the strip, at ${width}`, async ({
		page
	}) => {
		// The tiles once kept a second line for a price whether or not one was
		// due, because a price that landed or cleared moved seven panels. The
		// price is in the sentence under the band now, and that sentence keeps the
		// room of its longest form - so this is the property a smaller control
		// could silently lose. It starts on one day, where every wider preset that
		// reaches the canary's older month is priced.
		await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '1'));
		await page.setViewportSize({ width, height: 900 });
		await page.goto('/console/');
		await expect(page.locator('[data-window-preset="1"] input')).toBeEnabled();
		await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '1');
		await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
		// The canary keeps two telemetry months, so the widest presets reach one
		// the one-day window never fetched. Without a price this proves nothing.
		await expect(page.locator('[data-window-status]')).toContainText('would fetch');
		const before = await belowTheStrip(page);
		expect(Object.keys(before), 'a block below the strip is missing').toHaveLength(4);

		for (const preset of PRESETS.filter((days) => days > 1)) {
			await setWindow(page, preset);
			await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
			const after = await belowTheStrip(page);
			const moved = Object.keys(before)
				.filter((name) => Math.abs(after[name] - before[name]) > 1)
				.map((name) => `${name}: ${Math.round(before[name])} -> ${Math.round(after[name])}`);
			expect(moved, `picking ${preset} days moved the page at ${width}:\n${moved.join('\n')}`).toEqual([]);
		}
	});
}
