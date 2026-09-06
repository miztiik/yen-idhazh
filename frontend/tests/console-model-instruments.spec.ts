import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	DRAWN_BY,
	EVAL_PANELS,
	FLAGS,
	NOT_A_MEASUREMENT,
	RECORDED,
	evalDays,
	flagReadings,
	leadFloorNote,
	leadHeadline,
	matchHeadline,
	recordedReadings,
	recordedText,
	widerNote,
	type EvalInput
} from '../src/lib/console/eval-instruments';

/**
 * Every instrument the eval ledger writes, and the panel that answers for it.
 *
 * **The oracle is a set comparison, not a number.** `schemas/eval-row.schema.json`
 * is the contract for what the checker writes down. `DRAWN_BY` and
 * `NOT_A_MEASUREMENT` between them must name every column of it, exactly once,
 * and name nothing else. So a column added to `EvalRow` next month fails here,
 * in the ninety-second gate, instead of being scored on every summary for a year
 * with nowhere to look at it - which is exactly what happened to `hhem` and
 * `coverage`, the two the pipeline has written since its first published day.
 *
 * That is the whole reason this file is stronger than a test of the two new
 * charts would be. A chart test proves this panel draws; the set comparison
 * proves the *next* one will have to.
 *
 * The second half re-derives every drawn figure from the canary shard the site
 * was built from, by a plain loop that shares nothing with the module under
 * test. An oracle that calls the code it is checking cannot fail.
 */

const REPO = resolve(process.cwd(), '..');
const SCHEMA = resolve(REPO, 'schemas', 'eval-row.schema.json');
const CANARY_SCORES = resolve(REPO, 'backend', 'var', 'canary', 'state', 'scores');

const CONFIG = JSON.parse(readFileSync(resolve(REPO, 'config', 'idhazh.json'), 'utf8')) as {
	evaluation?: { lead_coverage_min?: number };
	console?: { default_window_days?: number };
};
const LEAD_FLOOR = CONFIG.evaluation?.lead_coverage_min ?? 0.3;

/** Every column the contract says a scored row carries. */
function contractColumns(): string[] {
	const schema = JSON.parse(readFileSync(SCHEMA, 'utf8')) as {
		properties?: Record<string, unknown>;
	};
	return Object.keys(schema.properties ?? {}).sort();
}

/** The canary ledger, as rows of strings, exactly as the page's reader sees it. */
function canaryRows(): EvalInput[] {
	if (!existsSync(CANARY_SCORES)) return [];
	const rows: EvalInput[] = [];
	for (const name of readdirSync(CANARY_SCORES).filter((n) => n.endsWith('.csv')).sort()) {
		const text = readFileSync(join(CANARY_SCORES, name), 'utf8').replace(/\r\n/g, '\n');
		const lines = text.split('\n').filter((line) => line !== '');
		if (lines.length === 0) continue;
		const header = lines[0].split(',');
		for (const line of lines.slice(1)) {
			// The canary writes no quoted comma into a numeric column, and every
			// column this file reads is numeric or a bare flag. A CSV parser here
			// would be a second implementation of a thing already tested.
			const cells = line.split(',');
			const row: Record<string, string> = {};
			header.forEach((column, index) => {
				row[column] = cells[index] ?? '';
			});
			rows.push(row);
		}
	}
	return rows;
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
	const lead: number[] = [];
	let under = 0;
	let differs = 0;
	for (const row of rows) {
		if (row.date !== date) continue;
		const hhem = Number(row.hhem);
		if ((row.hhem ?? '') !== '' && Number.isFinite(hhem)) match.push(hhem);
		const coverage = Number(row.coverage);
		if ((row.coverage ?? '') !== '' && Number.isFinite(coverage)) {
			lead.push(coverage);
			if (coverage < LEAD_FLOOR) under += 1;
		}
		const delta = Number(row.hhem_delta);
		if ((row.hhem_delta ?? '') !== '' && Number.isFinite(delta) && delta !== 0) differs += 1;
	}
	return {
		checked: match.length,
		mid: asPct(nth(match, 0.5)),
		low: asPct(nth(match, 0.25)),
		high: asPct(nth(match, 0.75)),
		led: lead.length,
		leadMid: asPct(nth(lead, 0.5)),
		under,
		underPct: lead.length === 0 ? null : Math.round((under / lead.length) * 100),
		differs
	};
}

/** The columns a reader must never be shown, which is not every column.
 *
 * `band` is a column and also an ordinary English word, so a blanket ban on
 * every column name fails on a sentence that uses it correctly. What has to stay
 * off the page is the pipeline's own spelling - anything holding an underscore,
 * plus the one acronym nobody outside the checker has heard of.
 */
function jargonColumns(): string[] {
	return contractColumns().filter((column) => column.includes('_') || column === 'hhem');
}

/** Six days covering every state the reduction has to survive.
 *
 * Written out rather than taken from the committed ledger, because three of
 * these have never occurred there and one of them cannot: a scored day where
 * the checker wrote no reading at all, a day where the whole-article score
 * parts from the read-text score on every row, and a day whose lead coverage is
 * entirely under the floor.
 */
const FIXTURE: EvalInput[] = [
	// Out of order, so the sort is asserted rather than assumed.
	{ date: '2026-04-02', hhem: '0.90', hhem_delta: '0', coverage: '0.10', compression: '0.20' },
	{ date: '2026-04-02', hhem: '0.80', hhem_delta: '0', coverage: '0.20', compression: '0.40' },
	{ date: '2026-04-01', hhem: '0.50', hhem_delta: '0.10', coverage: '0.60', compression: '0.10' },
	{ date: '2026-04-01', hhem: '0.60', hhem_delta: '-0.20', coverage: '0.70', compression: '0.30' },
	{ date: '2026-04-01', hhem: '0.70', hhem_delta: '0', coverage: '0.80', compression: '0.50' },
	{ date: '2026-04-01', hhem: '0.90', hhem_delta: '0', coverage: '0.90', compression: '0.70' },
	// A scored day the checker wrote no reading on. Not a day nothing ran.
	{ date: '2026-04-03', hhem: '', coverage: '', compression: '' },
	// A row with no day at all. Broken, and drawing it would draw the break.
	{ date: '', hhem: '0.99', coverage: '0.99' },
	// A cell that is present and is not a number.
	{ date: '2026-04-04', hhem: 'n/a', coverage: '0.55', extraction_suspect: 'true' },
	{ date: '2026-04-04', hhem: '0.85', coverage: '0.45', determinism_violation: 'True' }
];

test.describe('the map', () => {
	test('THE ORACLE: every column the ledger writes is on exactly one panel', () => {
		const columns = contractColumns();
		expect(columns.length, 'the eval-row contract lost its properties').toBeGreaterThan(20);

		const drawn = Object.keys(DRAWN_BY);
		const excluded = Object.keys(NOT_A_MEASUREMENT);
		const both = drawn.filter((column) => excluded.includes(column));
		expect(both, 'a column is both drawn and declared not a measurement').toEqual([]);

		const claimed = [...drawn, ...excluded].sort();
		// Said as two directed comparisons rather than one equality, because the
		// two failures need different fixes and a set equality names neither.
		const undeclared = columns.filter((column) => !claimed.includes(column));
		expect(
			undeclared,
			'a column the checker writes reaches no console panel and is not declared as identity. ' +
				'Give it a panel in DRAWN_BY, or a one-line reason in NOT_A_MEASUREMENT.'
		).toEqual([]);
		const invented = claimed.filter((column) => !columns.includes(column));
		expect(invented, 'a map names a column the eval-row contract does not have').toEqual([]);
	});

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
		const days = evalDays(FIXTURE, LEAD_FLOOR);
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
		expect(blank.leadMid).toBeNull();
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

	test('the floor is counted against the configured share, never against a literal', () => {
		const days = evalDays(FIXTURE, LEAD_FLOOR);
		// 0.10 and 0.20 are both under 0.3; 0.60 to 0.90 are all over it.
		expect(days[1].leadUnder).toBe(2);
		expect(days[1].leadUnderPct).toBe(100);
		expect(days[0].leadUnder).toBe(0);
		expect(days[0].leadUnderPct).toBe(0);
		// Handed a different floor, the same rows count differently. A literal in
		// the reduction would make this pass on the wrong number.
		const strict = evalDays(FIXTURE, 0.75);
		expect(strict[0].leadUnder).toBe(2);
	});

	test('a row with no day is dropped rather than pooled into an empty one', () => {
		const days = evalDays(FIXTURE, LEAD_FLOOR);
		expect(days.some((day) => day.date === '')).toBe(false);
		expect(days.reduce((sum, day) => sum + day.scored, 0)).toBe(FIXTURE.length - 1);
	});

	test('the sentences say what the numbers mean, and say nothing when there is nothing', () => {
		const days = evalDays(FIXTURE, LEAD_FLOOR);
		const head = matchHeadline(days, 30) ?? '';
		expect(head).toContain('percent');
		expect(head).not.toMatch(/\b[01]\.\d/);
		expect(widerNote(days, 30) ?? '').toContain('whole article');
		expect(leadHeadline(days, 30) ?? '').toContain('opening lines');
		expect(leadFloorNote(days, 30, LEAD_FLOOR)).toContain(`${Math.round(LEAD_FLOOR * 100)} percent`);

		// Nothing to report is silence, not a zero dressed as a reading.
		expect(matchHeadline([], 30)).toBeNull();
		expect(widerNote([], 30)).toBeNull();
		expect(leadHeadline([], 30)).toBeNull();
		expect(leadFloorNote([], 30, LEAD_FLOOR)).toBeNull();
	});

	test('a day with no faithfulness gap is said in words, not left blank', () => {
		const clean = evalDays(
			[{ date: '2026-04-01', hhem: '0.9', hhem_delta: '0', coverage: '0.6' }],
			LEAD_FLOOR
		);
		expect(widerNote(clean, 7) ?? '').toContain('scores the same');
	});

	test('a recorded reading carries its unit, and an absent one is a dash', () => {
		const days = evalDays(FIXTURE, LEAD_FLOOR);
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
		const readings = flagReadings(evalDays(FIXTURE, LEAD_FLOOR));
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

			const lead = page.locator(`[data-lead-day="${date}"]`);
			await expect(lead, `${date} is in the ledger and not on the coverage panel`).toHaveCount(1);
			await expect(lead).toHaveAttribute('data-lead-under', String(want.under));
			await expect(lead).toHaveAttribute('data-lead-under-pct', String(want.underPct));
			await expect(lead).toHaveAttribute('data-lead-mid', String(want.leadMid));
			await expect(lead).toHaveAttribute('data-lead-checked', String(want.led));
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
		await expect(page.locator('[data-model-lead-rule]')).toHaveCount(1);
		await expect(page.locator('[data-model-recorded-rule]')).toHaveCount(1);
		// Decision 2 of the row: every alarm ships in record-only mode until a
		// corpus month exists to set it from. A tint here would be that alarm.
		const tinted = await page
			.locator(
				'[data-eval-panel="faithfulness"] [data-band], [data-eval-panel="lead-coverage"] [data-band]'
			)
			.count();
		expect(tinted, 'a new panel colours a reading against a threshold nobody set').toBe(0);
	});

	test('a reading is a percentage or a rate, never the score the checker wrote', async ({
		page
	}) => {
		await page.goto('/console/model/');
		for (const id of ['faithfulness', 'lead-coverage', 'recorded-only']) {
			const text = (await page.locator(`[data-eval-panel="${id}"]`).innerText()).toLowerCase();
			for (const column of jargonColumns()) {
				expect(text, `the ${id} panel prints ${column} at a reader`).not.toContain(column);
			}
		}
		// Every figure on the two score panels is a whole percent, so a decimal
		// point on either of them is the checker's own unit having leaked out.
		for (const id of ['faithfulness', 'lead-coverage']) {
			const text = await page.locator(`[data-eval-panel="${id}"]`).innerText();
			expect(text, `the ${id} panel prints a raw score between zero and one`).not.toMatch(/\d\.\d/);
		}
		// The recorded table carries two units and says which is which on every
		// cell. A bare number in a table of mixed units is a number nobody can read.
		const cells = await page
			.locator('[data-model-recorded-table] [data-recorded-mid]')
			.allInnerTexts();
		expect(cells.length, 'the recorded table drew no reading').toBe(RECORDED.length);
		for (const cell of cells) {
			expect(cell.trim(), 'a recorded reading carries no unit').toMatch(
				/^(-|\d+%|\d+\.\d per 1,000 words)$/
			);
		}
	});

	test('the panels follow the one window control, without declaring a new windowed surface', async ({
		page
	}) => {
		await page.goto('/console/model/');
		const before = await page.locator('[data-match-day]').count();
		expect(before, 'the faithfulness panel drew no day').toBeGreaterThan(0);
		for (const id of ['faithfulness', 'lead-coverage', 'recorded-only']) {
			// `console-window.spec.ts` pins the exact list of windowed surfaces. These
			// three honour the control and never claim to be one, for the same reason
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
