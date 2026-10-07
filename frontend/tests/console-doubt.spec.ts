import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

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
 * Two cases, and neither is sufficient alone.
 *
 * The Node case states the ranking over rows built here, where a tie, a share
 * floor and a cap can each be made to bite on purpose, with every answer
 * written out.
 *
 * The browser case keeps only what the built page can prove about itself: every
 * drawn row prints a count over its own denominator, its three signals fit that
 * count, the order is the count with ties by name, a share appears only at the
 * configured floor and is the row's own count over its denominator, and the
 * source-join note is a named note when the page draws one.
 */

/** The fewest summaries a row needs before it prints a share, from the file the page reads it from. */
const MIN_FOR_SHARE =
	(
		JSON.parse(readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')) as {
			console?: { min_attempts_for_rate?: number };
		}
	).console?.min_attempts_for_rate ?? 5;

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
		// Two doubted summaries out of three must not outrank forty out of four
		// hundred. A share sort would put the small source first, and it is the
		// forty that reached a reader.
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

	test('THE ORACLE: the ranked rows are the values written in this spec', () => {
		const scores = [
			score('2026-08-20', 'beta-1', { band: 'low', unsupported_numbers: '2' }),
			score('2026-08-20', 'beta-2', { band: 'low' }),
			score('2026-08-20', 'beta-3', { hedge_dropped: 'True' }),
			score('2026-08-20', 'alpha-1', { unsupported_numbers: '1' }),
			score('2026-08-20', 'alpha-2', { hedge_dropped: 'true' }),
			score('2026-08-20', 'alpha-3'),
			score('2026-08-20', 'clean-1'),
			score('2026-08-13', 'outside', { band: 'low' })
		];
		const health = [
			published('beta-1', 'beta'),
			published('beta-2', 'beta'),
			published('beta-3', 'beta'),
			published('alpha-1', 'alpha'),
			published('alpha-2', 'alpha'),
			published('alpha-3', 'alpha'),
			published('clean-1', 'clean'),
			published('outside', 'outside')
		];

		const doubts = sourceDoubts(scores, health, WEEK, { limit: 10, minForShare: 3 });

		expect(doubts.rows.map((row) => row.sourceId)).toEqual(['beta', 'alpha']);
		expect(doubts.rows.map((row) => row.doubted)).toEqual([3, 2]);
		expect(doubts.rows.map((row) => row.summaries)).toEqual([3, 3]);
		expect(doubts.rows.map((row) => row.notSure)).toEqual([2, 0]);
		expect(doubts.rows.map((row) => row.unsupportedNumbers)).toEqual([1, 1]);
		expect(doubts.rows.map((row) => row.hedgeDropped)).toEqual([1, 1]);
		expect(doubts.rows.map((row) => row.sharePct)).toEqual([100, 67]);
		expect(doubts.sources).toBe(3);
		expect(doubts.summaries).toBe(7);
		expect(doubts.doubted).toBe(5);
		expect(doubts.unattributed).toBe(0);
	});

	test('THE ORACLE: an unattributed summary is counted in totals and no source row', () => {
		const doubts = sourceDoubts(
			[
				score('2026-08-20', 'known', { band: 'low' }),
				score('2026-08-20', 'orphan', { band: 'low' })
			],
			[published('known', 'known-source')],
			WEEK,
			{ limit: 10, minForShare: 5 }
		);

		expect(doubts.rows.map((row) => row.sourceId)).toEqual(['known-source']);
		expect(doubts.rows[0].doubted).toBe(1);
		expect(doubts.rows[0].summaries).toBe(1);
		expect(doubts.unattributed).toBe(1);
		expect(doubts.summaries).toBe(2);
		expect(doubts.doubted).toBe(1);
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
	test('the drawn rows publish the same counts they print', async ({ page }) => {
		await page.goto('/console/model/');

		const section = page.locator('[data-model-doubt]');
		await expect(section, 'the Summaries route names no doubted source at all').toHaveCount(1);
		await expect(section, 'the section draws a window it does not name').toHaveAttribute(
			'data-model-doubt-from',
			/\d{4}-\d{2}-\d{2}/
		);

		const rows = await drawn(page);
		expect(rows.length, 'the page drew no doubted source row to check').toBeGreaterThan(0);
		expect(
			new Set(rows.map((row) => row.key)).size,
			'two drawn rows carry the same source key'
		).toBe(rows.length);

		const counts: number[] = [];
		for (const [at, row] of rows.entries()) {
			const counted = row.value.match(/([\d,]+) of ([\d,]+)/);
			expect(counted, `${row.key} printed no count out of a denominator`).not.toBeNull();
			const doubtedCount = Number((counted?.[1] ?? '').replaceAll(',', ''));
			const summaries = Number((counted?.[2] ?? '').replaceAll(',', ''));
			expect(summaries, `${row.key} printed an empty denominator`).toBeGreaterThan(0);
			expect(doubtedCount, `${row.key} printed a row with no doubts`).toBeGreaterThan(0);
			expect(doubtedCount, `${row.key} doubts more summaries than it has`).toBeLessThanOrEqual(summaries);
			counts.push(doubtedCount);
			// Each signal counts doubted summaries, and every doubted summary carries
			// at least one of the three.
			const signals = ['not-sure', 'unsupported', 'hedge'].map((signal) => row.signals[signal]);
			for (const [index, n] of signals.entries()) {
				expect(n, `${row.key} signal ${index} is missing`).toBeGreaterThanOrEqual(0);
				expect(n, `${row.key} signal ${index} counts more than the row's doubts`).toBeLessThanOrEqual(
					doubtedCount
				);
			}
			expect(
				signals.reduce((total, n) => total + n, 0),
				`${row.key} counts a doubt that carries no signal`
			).toBeGreaterThanOrEqual(doubtedCount);
			// The order is the count, and a tie goes to the name.
			if (at > 0) {
				expect(doubtedCount, `${row.key} is ranked above a larger count`).toBeLessThanOrEqual(
					counts[at - 1]
				);
				if (doubtedCount === counts[at - 1]) {
					expect(
						rows[at - 1].key.localeCompare(row.key),
						`${row.key} ties with ${rows[at - 1].key} and sorts before it`
					).toBeLessThan(0);
				}
			}
			// A share only where the denominator reaches the configured floor, and
			// then the count over it, rounded.
			if (summaries < MIN_FOR_SHARE) {
				expect(row.context, `${row.key} gave a share over ${summaries} summaries`).toContain('no share');
			} else {
				expect(row.context, `${row.key} printed a share that is not its own count over its denominator`).toContain(
					`${Math.round((doubtedCount / summaries) * 100)}%`
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

	test('a source-join note is named when the page draws one', async ({ page }) => {
		await page.goto('/console/model/');
		const note = page.locator('[data-model-doubt-unattributed]');
		const count = await note.count();
		expect(count, 'the page drew more than one source-join note').toBeLessThanOrEqual(1);
		if (count === 1) {
			await expect(note).toContainText(/\d/);
			await expect(note).toContainText('could not be traced to a source');
			await expect(note).toContainText('counted in neither list');
		}
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
		// it here instead, which is the precedent the other panels set.
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
			await expect(page.locator('[data-model-doubt-intro]')).toContainText(
				preset === 1 ? 'over this one day' : `over these ${preset} days`
			);
		}
	});
});
