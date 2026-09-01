import { expect, test, type Page } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { grouped } from '../src/lib/charts/series';
import { doubted, sourceDoubts, type DayWindow } from '../src/lib/server/model-work';

/**
 * Which sources the checker doubts, and the rule the ranking is made of.
 *
 * The signal is three counts and never one blended score. A low band is the
 * grader's own confidence, an unsupported number is a fabrication, and a
 * dropped hedge is a certainty the article did not have; they have different
 * causes and different fixes, so a single figure would hide the only part an
 * operator can act on.
 *
 * Two arms, and neither is sufficient alone.
 *
 * The Node arm states the ranking over rows built here, where a tie, a share
 * floor and a cap can each be made to bite on purpose. The committed canary
 * cannot produce those states: it scores eight summaries from ONE source, so a
 * ranking over it is a list of one and every ordering question is vacuous.
 *
 * The browser arm reads the built canary's own two ledgers, joins them the way
 * the page joins them, and holds the drawn rows to what that join says - the
 * counts, the denominator, the three signals, and the sentence covering what
 * the cap left out. What it proves there is that the page is deriving rather
 * than printing, which is the half the Node arm cannot reach.
 */

const STATE = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

/** A ledger directory, read the way the page's server reads it. */
function shards(dir: string): Record<string, string>[] {
	const rows: Record<string, string>[] = [];
	for (const name of readdirSync(dir).filter((entry) => entry.endsWith('.csv')).sort()) {
		const lines = readFileSync(join(dir, name), 'utf8').split('\n').filter(Boolean);
		const header = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cells = line.split(',');
			rows.push(Object.fromEntries(header.map((key, at) => [key, cells[at] ?? ''])));
		}
	}
	return rows;
}

/** How deep the list goes, off the committed config rather than a literal. */
function doubtRows(): number {
	const read = (name: string) =>
		JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', name), 'utf8')) as {
			console?: { doubt_rows?: number; min_attempts_for_rate?: number };
		};
	const appearance = read('appearance.json').console ?? {};
	const app = read('idhazh.json').console ?? {};
	return appearance.doubt_rows ?? app.doubt_rows ?? 10;
}

function minForShare(): number {
	const read = (name: string) =>
		JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', name), 'utf8')) as {
			console?: { min_attempts_for_rate?: number };
		};
	return read('appearance.json').console?.min_attempts_for_rate ?? 5;
}

/**
 * The ranking, derived here without touching the module under test.
 *
 * The rule, as the page states it: a summary is doubted when the checker marked
 * it "not sure", when it carried a figure the article did not, or when it told
 * a "maybe" as fact. Sources are ordered by that COUNT, ties by name, and a
 * source with nothing doubted is left out.
 */
function rankedFrom(
	scores: Record<string, string>[],
	health: Record<string, string>[],
	window: { from: string; to: string }
) {
	const sourceOf = new Map<string, string>();
	for (const row of health) {
		if (row.url_key && row.source_id) sourceOf.set(row.url_key, row.source_id);
	}
	const inWindow = scores.filter((row) => row.date >= window.from && row.date <= window.to);
	const per = new Map<
		string,
		{ doubted: number; notSure: number; numbers: number; hedge: number; summaries: number }
	>();
	let unattributed = 0;
	for (const row of inWindow) {
		const id = sourceOf.get(row.url_key ?? '');
		if (id === undefined) {
			unattributed += 1;
			continue;
		}
		const at = per.get(id) ?? { doubted: 0, notSure: 0, numbers: 0, hedge: 0, summaries: 0 };
		at.summaries += 1;
		const low = row.band === 'low';
		const numbers = Number(row.unsupported_numbers || '0') > 0;
		const hedge = row.hedge_dropped === 'True' || row.hedge_dropped === 'true';
		if (low) at.notSure += 1;
		if (numbers) at.numbers += 1;
		if (hedge) at.hedge += 1;
		if (low || numbers || hedge) at.doubted += 1;
		per.set(id, at);
	}
	const rows = [...per.entries()]
		.map(([sourceId, counts]) => ({ sourceId, ...counts }))
		.filter((source) => source.doubted > 0)
		.sort((a, b) => b.doubted - a.doubted || a.sourceId.localeCompare(b.sourceId));
	return { rows, unattributed, scored: inWindow.length };
}

const WEEK: DayWindow = { start: '2026-08-15', end: '2026-08-21', days: 7 };

function score(
	date: string,
	urlKey: string,
	extra: Record<string, string> = {}
): Record<string, string> {
	return { date, url_key: urlKey, band: 'high', ...extra };
}

function published(urlKey: string, sourceId: string): Record<string, string> {
	return { date: '2026-08-20', url_key: urlKey, source_id: sourceId };
}

test.describe('the doubt signal, as arithmetic', () => {
	test('a summary is doubted by any one of the three, and never by a blend', () => {
		expect(doubted({ band: 'high' })).toBe(false);
		expect(doubted({ band: 'low' })).toBe(true);
		expect(doubted({ band: 'high', unsupported_numbers: '1' })).toBe(true);
		expect(doubted({ band: 'high', unsupported_numbers: '0' })).toBe(false);
		expect(doubted({ band: 'high', hedge_dropped: 'True' })).toBe(true);
		expect(doubted({ band: 'high', hedge_dropped: 'False' })).toBe(false);
	});

	test('a summary carrying two signals is one doubt, counted in both columns', () => {
		const doubts = sourceDoubts(
			[score('2026-08-20', 'a', { band: 'low', hedge_dropped: 'True' })],
			[published('a', 'one')],
			WEEK,
			{ limit: 10, minForShare: 5 }
		);
		expect(doubts.rows[0].doubted).toBe(1);
		expect(doubts.rows[0].notSure).toBe(1);
		expect(doubts.rows[0].hedgeDropped).toBe(1);
		// The three do not add up to the count, which is why they are never
		// stacked into one bar.
		expect(doubts.rows[0].notSure + doubts.rows[0].hedgeDropped).toBeGreaterThan(
			doubts.rows[0].doubted
		);
	});

	test('THE ORACLE: the order is the count, so a big denominator cannot be demoted', () => {
		// The case the plan names: 2 doubted of 3 must not outrank 40 of 400. A
		// share sort would put the small source first, and it is the forty that
		// reached a reader.
		const scores = [
			...Array.from({ length: 2 }, (_, at) => score('2026-08-20', `small-${at}`, { band: 'low' })),
			score('2026-08-20', 'small-2'),
			...Array.from({ length: 40 }, (_, at) => score('2026-08-20', `big-${at}`, { band: 'low' })),
			...Array.from({ length: 360 }, (_, at) => score('2026-08-20', `big-${at + 40}`))
		];
		const health = [
			...Array.from({ length: 3 }, (_, at) => published(`small-${at}`, 'small')),
			...Array.from({ length: 400 }, (_, at) => published(`big-${at}`, 'big'))
		];
		const doubts = sourceDoubts(scores, health, WEEK, { limit: 10, minForShare: 5 });
		expect(doubts.rows.map((row) => row.sourceId)).toEqual(['big', 'small']);
		expect(doubts.rows[0].doubted).toBe(40);
		expect(doubts.rows[0].summaries).toBe(400);
		expect(doubts.rows[1].doubted).toBe(2);
		expect(doubts.rows[1].summaries).toBe(3);
		// And the denominator is carried, because 2 of 3 and 40 of 400 are
		// different facts that one count cannot tell apart.
		expect(doubts.rows[1].sharePct, 'a share over three summaries is the second one').toBeNull();
		expect(doubts.rows[0].sharePct).toBe(10);
	});

	test('a tie goes to the name, so the page does not move between builds', () => {
		const doubts = sourceDoubts(
			[
				score('2026-08-20', 'z', { band: 'low' }),
				score('2026-08-20', 'a', { band: 'low' }),
				score('2026-08-20', 'm', { band: 'low' })
			],
			[published('z', 'zulu'), published('a', 'alpha'), published('m', 'mike')],
			WEEK,
			{ limit: 10, minForShare: 5 }
		);
		expect(doubts.rows.map((row) => row.sourceId)).toEqual(['alpha', 'mike', 'zulu']);
	});

	test('a source with nothing doubted is left out, not ranked at zero', () => {
		const doubts = sourceDoubts(
			[score('2026-08-20', 'a'), score('2026-08-20', 'b', { band: 'low' })],
			[published('a', 'clean'), published('b', 'doubted')],
			WEEK,
			{ limit: 10, minForShare: 5 }
		);
		expect(doubts.rows.map((row) => row.sourceId)).toEqual(['doubted']);
		// It is still counted as a source the window scored, so the denominators
		// under the list stay honest.
		expect(doubts.sources).toBe(2);
		expect(doubts.summaries).toBe(2);
	});

	test('the cap states its own tail, in sources and in doubts', () => {
		const scores = Array.from({ length: 6 }, (_, at) =>
			score('2026-08-20', `s${at}`, { band: 'low' })
		);
		const health = scores.map((row, at) => published(`s${at}`, `source-${at}`));
		const doubts = sourceDoubts(scores, health, WEEK, { limit: 2, minForShare: 5 });
		expect(doubts.rows).toHaveLength(2);
		expect(doubts.moreSources).toBe(4);
		expect(doubts.moreDoubted).toBe(4);
		expect(doubts.doubted).toBe(6);
	});

	test('a summary no ledger can place is counted as that, never dropped quietly', () => {
		const doubts = sourceDoubts(
			[score('2026-08-20', 'known', { band: 'low' }), score('2026-08-20', 'orphan')],
			[published('known', 'one')],
			WEEK,
			{ limit: 10, minForShare: 5 }
		);
		expect(doubts.unattributed).toBe(1);
		expect(doubts.summaries).toBe(2);
		expect(doubts.rows[0].summaries).toBe(1);
	});

	test('a window is a filter on the rows and a day outside it is not counted', () => {
		const scores = [
			score('2026-08-14', 'a', { band: 'low' }),
			score('2026-08-20', 'b', { band: 'low' })
		];
		const health = [published('a', 'one'), published('b', 'one')];
		expect(sourceDoubts(scores, health, WEEK, { limit: 10, minForShare: 5 }).doubted).toBe(1);
		expect(
			sourceDoubts(scores, health, { start: '2026-08-08', end: '2026-08-21', days: 14 }, {
				limit: 10,
				minForShare: 5
			}).doubted
		).toBe(2);
	});
});

/** Every drawn row, with the three signals it printed. */
async function drawn(page: Page) {
	return page.locator('[data-model-doubt-list] [data-ranked-row]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			key: node.getAttribute('data-ranked-row') ?? '',
			value: node.querySelector('[data-ranked-cell="value"]')?.textContent?.trim() ?? '',
			context: node.querySelector('[data-ranked-cell="context"]')?.textContent?.trim() ?? '',
			signals: Object.fromEntries(
				[...node.querySelectorAll('[data-doubt-count]')].map((signal) => [
					signal.getAttribute('data-doubt-count') ?? '',
					Number(signal.getAttribute('data-doubt-n'))
				])
			) as Record<string, number>
		}))
	);
}

test.describe('the ranked list, on the built console', () => {
	test('THE ORACLE: the drawn rows are what the two ledgers say', async ({ page }) => {
		await page.goto('/console/model/');

		const section = page.locator('[data-model-doubt]');
		await expect(section, 'the Summaries route names no doubted source at all').toHaveCount(1);
		const window = {
			from: (await section.getAttribute('data-model-doubt-from')) ?? '',
			to: (await section.getAttribute('data-model-doubt-to')) ?? ''
		};
		expect(window.from, 'the section draws a window it does not name').not.toBe('');

		const expected = rankedFrom(shards(join(STATE, 'scores')), shards(join(STATE, 'item-health')), window);
		expect(expected.scored, 'the canary ledger scored nothing in the open window').toBeGreaterThan(0);

		const rows = await drawn(page);
		const cap = doubtRows();
		expect(
			rows.map((row) => row.key),
			'the drawn order is not the ranking the ledger gives'
		).toEqual(expected.rows.slice(0, cap).map((row) => row.sourceId));

		for (const [at, row] of rows.entries()) {
			const source = expected.rows[at];
			// The count and the denominator, both, on every row.
			expect(row.value, `${row.key} printed no count out of a denominator`).toContain(
				`${grouped(source.doubted)} of ${grouped(source.summaries)}`
			);
			// The three signals, apart, each equal to the independent count.
			expect(row.signals['not-sure'], `${row.key} not-sure`).toBe(source.notSure);
			expect(row.signals.unsupported, `${row.key} unsupported numbers`).toBe(source.numbers);
			expect(row.signals.hedge, `${row.key} dropped hedges`).toBe(source.hedge);
			// A share only where the denominator carries one.
			const floor = minForShare();
			if (source.summaries < floor) {
				expect(row.context, `${row.key} gave a share over ${source.summaries} summaries`).toContain(
					'no share'
				);
			} else {
				expect(row.context, `${row.key} printed no share`).toContain(
					`${Math.round((source.doubted / source.summaries) * 100)}%`
				);
			}
		}
	});

	test('the rule the order is made of is on the page, not only in the code', async ({ page }) => {
		// A ranking whose rule is not stated can only be read for order. This one
		// is ordered by count, which is the thing a reader would otherwise assume
		// was a rate.
		await page.goto('/console/model/');
		await expect(page.locator('[data-model-doubt-rule]')).toContainText(
			'The order is the count and never the share'
		);
		await expect(page.locator('[data-model-doubt-intro]')).toContainText('2 doubted of 3');
	});

	test('a summary no source could be found for is named, not dropped', async ({ page }) => {
		await page.goto('/console/model/');
		const section = page.locator('[data-model-doubt]');
		const window = {
			from: (await section.getAttribute('data-model-doubt-from')) ?? '',
			to: (await section.getAttribute('data-model-doubt-to')) ?? ''
		};
		const expected = rankedFrom(
			shards(join(STATE, 'scores')),
			shards(join(STATE, 'item-health')),
			window
		);
		const note = page.locator('[data-model-doubt-unattributed]');
		if (expected.unattributed === 0) {
			await expect(note, 'a note about nothing').toHaveCount(0);
			return;
		}
		await expect(note).toContainText(`${grouped(expected.unattributed)} of`);
	});

	test('no source is tinted, because the checker is still being calibrated', async ({ page }) => {
		// Decision 4: the grader has a known length bias, so a colour here would
		// publish a verdict about a publisher off an instrument nobody has
		// finished measuring.
		await page.goto('/console/model/');
		await expect(page.locator('[data-model-doubt-list] [data-movement]')).toHaveCount(0);
		await expect(page.locator('[data-model-doubt-list] [data-band]')).toHaveCount(0);
	});

	test('the list follows the window without claiming to be a windowed surface', async ({
		page
	}) => {
		// `console-window.spec.ts` holds an exact sorted list of every surface
		// that declares `data-windowed`. This one honours the control and asserts
		// it here instead, which is the precedent row #4 set.
		await page.goto('/console/model/');
		const fallback = Number(
			(await page.locator('[data-window-control]').getAttribute('data-window-days')) ?? 30
		);
		await expect(page.locator(`[data-window-preset="${fallback}"] input`)).toBeEnabled();

		const presets = await page
			.locator('[data-window-preset]')
			.evaluateAll((nodes) =>
				nodes.map((node) => Number(node.getAttribute('data-window-preset')))
			);
		expect(presets.length, 'a control with one option cannot disagree with anything').toBeGreaterThan(
			1
		);

		for (const preset of presets) {
			await page.locator(`[data-window-preset="${preset}"]`).click();
			await expect(page.locator('[data-model-doubt]')).toHaveAttribute(
				'data-model-doubt-days',
				String(preset)
			);
			await expect(page.locator('[data-model-doubt-intro]')).toContainText(`${preset} days`);
		}
	});
});
