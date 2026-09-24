import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { readDayShards } from '../src/lib/server/payload';
import {
	DRAWN_BY,
	EVAL_PANELS,
	FLAGS,
	NOT_A_MEASUREMENT,
	RECORDED,
	evalDays,
	flagReadings,
	matchHeadline,
	recordedReadings,
	recordedText,
	widerNote,
	type EvalInput
} from '../src/lib/console/eval-instruments';

/**
 * Every instrument the eval ledger writes, and the panel that answers for it.
 *
 * **The set comparison behind this panel is
 * `backend/tests/contracts/test_frontend_console_lists.py`.** `DRAWN_BY` and
 * `NOT_A_MEASUREMENT` between them must name every column of `EvalRow`, exactly
 * once, and name nothing else, so a column added next month fails there instead
 * of being scored on every summary for a year with nowhere to look at it - which
 * is exactly what happened to `hhem`, the column the pipeline has written since
 * its first published day. It asks that of the contract itself
 * rather than of a generated copy of it, which is why it is not here.
 *
 * What this file holds is what the browser tier alone can say: every drawn
 * figure re-derived from the canary shard the site was built from, by a plain
 * loop that shares nothing with the module under test. An oracle that calls the
 * code it is checking cannot fail.
 */

const REPO = resolve(process.cwd(), '..');
const CANARY_SCORES = resolve(REPO, 'backend', 'var', 'canary', 'state', 'scores');

const CONFIG = JSON.parse(readFileSync(resolve(REPO, 'config', 'idhazh.json'), 'utf8')) as {
	console?: { default_window_days?: number };
};

/** The canary ledger, as rows of strings, exactly as the page's reader sees it.
 *
 * Through `readDayShards` rather than a directory listing here: the store files
 * `<YYYY>/<MM>/<DD>.csv` since 2026-09-13, so a `readdir` of `*.csv` over the
 * root finds nothing and leaves every assertion below passing on an empty set.
 */
function canaryRows(): EvalInput[] {
	if (!existsSync(CANARY_SCORES)) return [];
	return readDayShards(CANARY_SCORES, -1).rows as EvalInput[];
}

/** The value at a fraction of a sorted list, written out rather than imported. */
function nth(values: number[], fraction: number): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	return sorted[Math.min(sorted.length - 1, Math.floor(fraction * sorted.length))];
}

/** A score as a whole percent, or null where there was nothing to score. */
function asPct(value: number | null): number | null {
	return value === null ? null : Math.round(value * 100);
}

/** One day of a shard, counted by hand, sharing nothing with `evalDays`. */
function byHand(rows: readonly EvalInput[], date: string) {
	const match: number[] = [];
	let differs = 0;
	for (const row of rows) {
		if (row.date !== date) continue;
		const hhem = Number(row.hhem);
		if ((row.hhem ?? '') !== '' && Number.isFinite(hhem)) match.push(hhem);
		const delta = Number(row.hhem_delta);
		if ((row.hhem_delta ?? '') !== '' && Number.isFinite(delta) && delta !== 0) differs += 1;
	}
	return {
		checked: match.length,
		mid: asPct(nth(match, 0.5)),
		low: asPct(nth(match, 0.25)),
		high: asPct(nth(match, 0.75)),
		differs
	};
}

/** The columns a reader must never be shown, which is not every column.
 *
 * `band` is a column and also an ordinary English word, so a blanket ban on
 * every column name fails on a sentence that uses it correctly. What has to stay
 * off the page is the pipeline's own spelling - anything holding an underscore,
 * plus the one acronym nobody outside the checker has heard of.
 *
 * Taken from the two maps rather than from a contract file, because
 * `test_frontend_console_lists.py` holds those two to exactly `EvalRow`'s
 * columns - so this is still the contract's list.
 */
function jargonColumns(): string[] {
	return [...Object.keys(DRAWN_BY), ...Object.keys(NOT_A_MEASUREMENT)].filter(
		(column) => column.includes('_') || column === 'hhem'
	);
}

/** Six days covering every state the reduction has to survive.
 *
 * Written out rather than taken from the committed ledger, because three of
 * these have never occurred there and one of them cannot: a scored day where
 * the checker wrote no reading at all, a day where the whole-article score
 * parts from the read-text score on every row, and a day carrying a coherence
 * reading below zero.
 */
const FIXTURE: EvalInput[] = [
	// Out of order, so the sort is asserted rather than assumed.
	{ date: '2026-04-02', hhem: '0.90', hhem_delta: '0', compression: '0.20', coherence: '0.10' },
	{ date: '2026-04-02', hhem: '0.80', hhem_delta: '0', compression: '0.40', coherence: '-0.30' },
	{ date: '2026-04-01', hhem: '0.50', hhem_delta: '0.10', compression: '0.10' },
	{ date: '2026-04-01', hhem: '0.60', hhem_delta: '-0.20', compression: '0.30' },
	{ date: '2026-04-01', hhem: '0.70', hhem_delta: '0', compression: '0.50' },
	{ date: '2026-04-01', hhem: '0.90', hhem_delta: '0', compression: '0.70' },
	// A scored day the checker wrote no reading on. Not a day nothing ran.
	{ date: '2026-04-03', hhem: '', compression: '' },
	// A row with no day at all. Broken, and drawing it would draw the break.
	{ date: '', hhem: '0.99' },
	// A cell that is present and is not a number.
	{ date: '2026-04-04', hhem: 'n/a', extraction_suspect: 'true' },
	{ date: '2026-04-04', hhem: '0.85', determinism_violation: 'True' }
];

test.describe('the map', () => {
	test('every panel a column is assigned to is a declared panel', () => {
		const ids = EVAL_PANELS.map((panel) => panel.id);
		expect(new Set(ids).size, 'two panels share an id').toBe(ids.length);
		for (const [column, panel] of Object.entries(DRAWN_BY)) {
			expect(ids, `${column} is assigned to a panel that is not declared`).toContain(panel);
		}
		// A panel nobody is assigned to is a panel that has stopped answering for
		// anything, which is how a heading outlives the number under it.
		for (const panel of EVAL_PANELS) {
			expect(
				Object.values(DRAWN_BY),
				`the ${panel.id} panel answers for no column`
			).toContain(panel.id);
		}
	});

	test('every excluded column says why, in a sentence', () => {
		for (const [column, reason] of Object.entries(NOT_A_MEASUREMENT)) {
			expect(reason.length, `${column} has no reason written down`).toBeGreaterThan(20);
			expect(reason.endsWith('.'), `${column}'s reason is not a sentence`).toBe(true);
		}
	});

	test('the two instrument lists are columns of the ledger, and are drawn apart', () => {
		for (const instrument of [...RECORDED, ...FLAGS]) {
			expect(DRAWN_BY[instrument.id], `${instrument.id} is listed but not assigned`).toBe(
				'recorded-only'
			);
			expect(instrument.label, `${instrument.id} is labelled with its own column name`).not.toContain(
				'_'
			);
		}
		const ids = [...RECORDED, ...FLAGS].map((instrument) => instrument.id);
		expect(new Set(ids).size, 'an instrument is in both lists').toBe(ids.length);
	});
});

test.describe('the arithmetic', () => {
	test('a day is reduced by position, and a missing reading never enters as a zero', () => {
		const days = evalDays(FIXTURE);
		expect(days.map((day) => day.date)).toEqual([
			'2026-04-01',
			'2026-04-02',
			'2026-04-03',
			'2026-04-04'
		]);

		const first = days[0];
		// Four readings: 0.50 0.60 0.70 0.90. Nearest rank at a quarter, a half
		// and three quarters is the 2nd, 3rd and 4th of them.
		expect(first.matchLow).toBe(60);
		expect(first.matchMid).toBe(70);
		expect(first.matchHigh).toBe(90);
		expect(first.matched).toBe(4);
		expect(first.widerDiffers).toBe(2);
		expect(first.widestGap).toBe(20);

		// The day with no readings is a day, and it draws nothing.
		const blank = days[2];
		expect(blank.scored).toBe(1);
		expect(blank.matched).toBe(0);
		expect(blank.matchMid).toBeNull();
		expect(blank.recorded.compression).toBeNull();

		// A cell that is present and is not a number is a missing reading, not a
		// zero: one of the two rows scores, and the other is left out of both the
		// count and the median.
		const bad = days[3];
		expect(bad.scored).toBe(2);
		expect(bad.matched).toBe(1);
		expect(bad.matchMid).toBe(85);
		expect(bad.fired.extraction_suspect).toBe(1);
		expect(bad.fired.determinism_violation).toBe(1);
	});

	test('a cosine keeps its own scale and its sign, and is never read as a percent', () => {
		// -0.30 and 0.10 on one day. Nearest rank at a half is the second of them,
		// kept to two places rather than multiplied by a hundred.
		const days = evalDays(FIXTURE);
		expect(days[1].recorded.coherence).toBe(0.1);
		const reading = recordedReadings(days).find((entry) => entry.id === 'coherence');
		expect(reading?.days).toBe(1);
		expect(reading?.low).toBe(0.1);
		expect(recordedText(reading!, -0.3)).toBe('-0.30');
		expect(recordedText(reading!, null)).toBe('-');
	});

	test('a row with no day is dropped rather than pooled into an empty one', () => {
		const days = evalDays(FIXTURE);
		expect(days.some((day) => day.date === '')).toBe(false);
		expect(days.reduce((sum, day) => sum + day.scored, 0)).toBe(FIXTURE.length - 1);
	});

	test('the sentences say what the numbers mean, and say nothing when there is nothing', () => {
		const days = evalDays(FIXTURE);
		const head = matchHeadline(days, 30) ?? '';
		expect(head).toContain('percent');
		expect(head).not.toMatch(/\b[01]\.\d/);
		expect(widerNote(days, 30) ?? '').toContain('whole article');

		// Nothing to report is silence, not a zero dressed as a reading.
		expect(matchHeadline([], 30)).toBeNull();
		expect(widerNote([], 30)).toBeNull();
	});

	test('a day with no faithfulness gap is said in words, not left blank', () => {
		const clean = evalDays([{ date: '2026-04-01', hhem: '0.9', hhem_delta: '0' }]);
		expect(widerNote(clean, 7) ?? '').toContain('scores the same');
	});

	test('a recorded reading carries its unit, and an absent one is a dash', () => {
		const days = evalDays(FIXTURE);
		const readings = recordedReadings(days);
		const compression = readings.find((reading) => reading.id === 'compression');
		expect(compression, 'the compression instrument left the list').toBeTruthy();
		// Two days carry a reading: 40 percent and 50 percent. The other two carry
		// none, and a day with no reading is not a day that read zero.
		expect(compression?.days).toBe(2);
		expect(compression?.low).toBe(40);
		expect(compression?.high).toBe(50);
		expect(recordedText(compression!, compression!.mid)).toMatch(/^\d+%$/);
		expect(recordedText(compression!, null)).toBe('-');
		const density = readings.find((reading) => reading.id === 'speculative_density');
		expect(recordedText(density!, 3.4)).toBe('3.4 per 1,000 words');
	});

	test('a flag that never fired is counted, not omitted', () => {
		const readings = flagReadings(evalDays(FIXTURE));
		expect(readings.map((reading) => reading.id)).toEqual(FLAGS.map((flag) => flag.id));
		for (const reading of readings) {
			expect(reading.fired).toBe(1);
			expect(reading.of).toBe(FIXTURE.length - 1);
		}
	});

	test('no panel title and no instrument label is the name of the column behind it', () => {
		const words = [
			...EVAL_PANELS.map((panel) => panel.title),
			...RECORDED.map((instrument) => `${instrument.label} ${instrument.note}`),
			...FLAGS.map((instrument) => `${instrument.label} ${instrument.note}`)
		]
			.join(' ')
			.toLowerCase();
		for (const column of jargonColumns()) {
			expect(words, `${column} is printed at a reader as its own column name`).not.toContain(
				column
			);
		}
	});
});

test.describe('the panels, in a browser', () => {
	test('every declared panel is on the page it declares', async ({ page }) => {
		await page.goto('/console/model/');
		for (const panel of EVAL_PANELS) {
			expect(panel.route, 'a panel declares a route this test does not visit').toBe(
				'/console/model/'
			);
			await expect(
				page.locator(`[data-eval-panel="${panel.id}"]`),
				`the ${panel.id} panel is declared and is not on the page`
			).toHaveCount(1);
		}
		// Nothing marks itself a panel without being in the map.
		const marked = await page.locator('[data-eval-panel]').evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-eval-panel') ?? '')
		);
		expect(marked.slice().sort()).toEqual(EVAL_PANELS.map((panel) => panel.id).sort());
	});

	test('THE ORACLE: what the page drew is what the built ledger holds', async ({ page }) => {
		const rows = canaryRows();
		expect(
			rows.length,
			'the canary score ledger is missing. Build it: python backend/utilities/build_canary_day.py'
		).toBeGreaterThan(0);
		const dates = [...new Set(rows.map((row) => row.date ?? ''))].filter((date) => date !== '');

		await page.goto('/console/model/');
		for (const date of dates) {
			const want = byHand(rows, date);
			const match = page.locator(`[data-match-day="${date}"]`);
			await expect(match, `${date} is in the ledger and not on the faithfulness panel`).toHaveCount(
				1
			);
			await expect(match).toHaveAttribute('data-match-mid', String(want.mid));
			await expect(match).toHaveAttribute('data-match-low', String(want.low));
			await expect(match).toHaveAttribute('data-match-high', String(want.high));
			await expect(match).toHaveAttribute('data-match-checked', String(want.checked));
		}
	});

	test('the recorded table draws every instrument, and neither list is silently short', async ({
		page
	}) => {
		await page.goto('/console/model/');
		for (const instrument of RECORDED) {
			const row = page.locator(`[data-recorded-row="${instrument.id}"]`);
			await expect(row, `${instrument.id} is recorded and is not on the page`).toHaveCount(1);
			await expect(row.locator('[data-recorded-mid]')).not.toBeEmpty();
		}
		for (const instrument of FLAGS) {
			const row = page.locator(`[data-flag-row="${instrument.id}"]`);
			await expect(row, `${instrument.id} is recorded and is not on the page`).toHaveCount(1);
			// The canary sets neither flag, and a flag that never fired has to say so
			// rather than leave a blank a reader reads as "not measured".
			await expect(row.locator('[data-flag-fired]')).toContainText('Never');
		}
	});

	test('the two panels state what they count, and set no bar', async ({ page }) => {
		await page.goto('/console/model/');
		await expect(page.locator('[data-model-match-rule]')).toContainText('Nothing here sets a bar');
		await expect(page.locator('[data-model-recorded-rule]')).toHaveCount(1);
		// Decision 2 of the row: every alarm ships in record-only mode until a
		// corpus month exists to set it from. A tint here would be that alarm.
		const tinted = await page.locator('[data-eval-panel="faithfulness"] [data-band]').count();
		expect(tinted, 'a new panel colours a reading against a threshold nobody set').toBe(0);
	});

	test('a reading is a percentage or a rate, never the score the checker wrote', async ({
		page
	}) => {
		await page.goto('/console/model/');
		for (const id of ['faithfulness', 'recorded-only']) {
			const text = (await page.locator(`[data-eval-panel="${id}"]`).innerText()).toLowerCase();
			for (const column of jargonColumns()) {
				expect(text, `the ${id} panel prints ${column} at a reader`).not.toContain(column);
			}
		}
		// Every figure on the score panel is a whole percent, so a decimal point on
		// it is the checker's own unit having leaked out.
		const text = await page.locator('[data-eval-panel="faithfulness"]').innerText();
		expect(text, 'the faithfulness panel prints a raw score between zero and one').not.toMatch(
			/\d\.\d/
		);
		// The recorded table carries three units and says which is which on every
		// cell. A bare number in a table of mixed units is a number nobody can read -
		// except a cosine, which IS its own number and carries a sign instead.
		const cells = await page
			.locator('[data-model-recorded-table] [data-recorded-mid]')
			.allInnerTexts();
		expect(cells.length, 'the recorded table drew no reading').toBe(RECORDED.length);
		for (const cell of cells) {
			expect(cell.trim(), 'a recorded reading carries no unit').toMatch(
				/^(-|\d+%|-?\d\.\d{2}|\d+\.\d per 1,000 words)$/
			);
		}
	});

	test('the panels follow the one window control, without declaring a new windowed surface', async ({
		page
	}) => {
		await page.goto('/console/model/');
		const before = await page.locator('[data-match-day]').count();
		expect(before, 'the faithfulness panel drew no day').toBeGreaterThan(0);
		for (const id of ['faithfulness', 'recorded-only']) {
			// `console-window.spec.ts` pins the exact list of windowed surfaces. These
			// two honour the control and never claim to be one, for the same reason
			// the doubt-reason panel does not: the list is the contract with the
			// control, not a list of everything the control moves.
			await expect(page.locator(`[data-eval-panel="${id}"][data-windowed]`)).toHaveCount(0);
		}
		await expect(page.locator('[data-model-match-days]')).toHaveAttribute(
			'data-model-match-days',
			String(CONFIG.console?.default_window_days ?? 30)
		);
	});
});
