/** What counts as a merge, and what the three states say.
 *
 * The arithmetic is lifted into `$lib/console/merge-line` so it can be driven
 * from a written-down array rather than from a day off the archive. A test that
 * walks the committed day tree costs more every published day (Guardrail #12),
 * and worse, it can only assert what the archive happens to contain today - the
 * two cases below that matter most are ones the pipeline has never produced.
 *
 * No build and no browser: this file is in the `logic` group.
 */

import { expect, test } from '@playwright/test';

import {
	agreementCorridor,
	clampEnvelope,
	clampNote,
	corridorOf,
	countedDays,
	gateNeeds,
	heldInWords,
	heldNote,
	mergeCountsOf,
	mergeNote,
	mergeRate,
	mergeState,
	mergeTotals,
	rateWithDenominator,
	silentTail,
	type JudgeDay,
	type LineDay,
	type MergeDay,
	type MergeItem
} from '../src/lib/console/merge-line';

/** Five stories. Two were folded behind `a`, so one group of three. */
const DAY: MergeItem[] = [
	{ item_id: 'a', same_story_as: null },
	{ item_id: 'b', same_story_as: 'a' },
	{ item_id: 'c', same_story_as: 'a' },
	{ item_id: 'd', same_story_as: null },
	{ item_id: 'e' }
];

function day(date: string, items: MergeItem[]): MergeDay {
	return { date, ...mergeCountsOf(items) };
}

test.describe('the merge count is a read of the day, not an opinion about it', () => {
	test('the merge count is the items that name another item', () => {
		const counts = mergeCountsOf(DAY);

		expect(counts.merges, 'b and c were folded behind a').toBe(2);
		expect(counts.groups, 'both name the same anchor, so it is one group').toBe(1);
		// Three, not two: the story that was kept is in its own group. A reader
		// told "the biggest group held 2" would be told the wrong number of
		// stories are behind that one card.
		expect(counts.largest, 'the kept story counts towards its own group').toBe(3);
		expect(counts.published, 'a folded story is still published').toBe(5);
	});

	test('an item that names itself is not a merge', () => {
		// The bite: the grouping pass has never written one of these and the schema
		// does not allow it. The guard is what keeps a day that did from counting a
		// story as folded behind itself - which would inflate the merges AND the
		// group it is in, from one row of bad data.
		const counts = mergeCountsOf([
			{ item_id: 'a', same_story_as: 'a' },
			{ item_id: 'b', same_story_as: null }
		]);

		expect(counts.merges).toBe(0);
		expect(counts.groups).toBe(0);
		expect(counts.largest, 'nothing was folded, so there is no group to size').toBe(0);
	});

	test('two groups on one day are two groups, and the biggest is the one named', () => {
		const counts = mergeCountsOf([
			{ item_id: 'a', same_story_as: null },
			{ item_id: 'b', same_story_as: 'a' },
			{ item_id: 'c', same_story_as: null },
			{ item_id: 'd', same_story_as: 'c' },
			{ item_id: 'e', same_story_as: 'c' }
		]);

		expect(counts.merges).toBe(3);
		expect(counts.groups).toBe(2);
		expect(counts.largest, 'c holds two others, a holds one').toBe(3);
	});

	test('the window totals add the days and keep the newest biggest group', () => {
		const totals = mergeTotals([
			day('2026-08-01', DAY),
			day('2026-08-02', [{ item_id: 'x', same_story_as: null }]),
			// Ties go to the newest day: an operator reading a date wants the
			// occasion he can still act on.
			day('2026-08-03', DAY)
		]);

		expect(totals.days).toBe(3);
		expect(totals.merges).toBe(4);
		expect(totals.published).toBe(11);
		expect(totals.largest).toBe(3);
		expect(totals.largestOn).toBe('2026-08-03');
	});
});

test.describe('the three states', () => {
	test('the two empty states say different things', () => {
		// No day tree to read at all.
		const nothing = mergeTotals([]);
		// A day tree that answered, and the answer was none.
		const quiet = mergeTotals([day('2026-08-01', [{ item_id: 'a', same_story_as: null }])]);

		expect(mergeState(nothing)).toBe('no-days');
		expect(mergeState(quiet)).toBe('no-merges');

		const first = mergeNote(nothing, 30);
		const second = mergeNote(quiet, 30);
		// Reading the first as the second is reading a null as a zero: one says the
		// record cannot answer, the other says it answered no.
		expect(first, 'the two empty states print the same sentence').not.toBe(second);
		expect(first).toContain('nothing here can be counted');
		expect(second).toContain('Every one ran on its own');
		expect(second, 'the window span is in the sentence').toContain('30 days');
	});

	test('the healthy state names the count, the biggest group and its day', () => {
		const note = mergeNote(mergeTotals([day('2026-08-03', DAY)]), 30);

		expect(note).toContain('2 stories were folded into another over these 30 days');
		expect(note).toContain('The biggest group held 3 stories');
		expect(note, 'the day is printed for a reader, not as a key').toContain('3 Aug');
	});

	test('one fold is written in the singular', () => {
		// `1 stories were folded` is what a template with no singular prints, and
		// it is the sentence a reader meets on a quiet day rather than a busy one.
		const note = mergeNote(
			mergeTotals([
				day('2026-08-03', [
					{ item_id: 'a', same_story_as: null },
					{ item_id: 'b', same_story_as: 'a' }
				])
			]),
			7
		);

		expect(note).toContain('1 story was folded into another over these 7 days');
	});

	test('the one-day span is written as one day', () => {
		// `1` is one of the presets, so `these 1 days` is a sentence the control can
		// actually produce rather than a hypothetical.
		const quiet = mergeTotals([day('2026-08-01', [{ item_id: 'a', same_story_as: null }])]);

		expect(mergeNote(quiet, 1)).toContain('No story in this one day');
		expect(mergeNote(quiet, 1)).not.toContain('1 days');
	});
});

test.describe('where the merge line sits', () => {
	/** Four days, and every case the chart has to draw: a rise the daily cap held,
	 * a fall the daily cap held, a day the guard held, and a day nothing was fitted. */
	const LINE: LineDay[] = [
		{
			date: '2026-09-15',
			previous: 0.94,
			proposed: 0.941,
			applied: 0.941,
			clampKind: 'none',
			heldReason: 'none',
			maxDownStep: 0.01,
			maxUpStep: 0.003
		},
		{
			date: '2026-09-16',
			previous: 0.941,
			proposed: 0.9,
			applied: 0.931,
			clampKind: 'step',
			heldReason: 'none',
			maxDownStep: 0.01,
			maxUpStep: 0.003
		},
		{
			date: '2026-09-17',
			previous: 0.931,
			proposed: 0.99,
			applied: 0.931,
			clampKind: 'guard',
			heldReason: 'none',
			maxDownStep: 0.01,
			maxUpStep: 0.003
		},
		{
			date: '2026-09-18',
			previous: 0.931,
			proposed: null,
			applied: 0.931,
			clampKind: 'none',
			heldReason: 'sheet_too_small',
			maxDownStep: 0.01,
			maxUpStep: 0.003
		}
	];

	test('the corridor is the config band whatever the data did', () => {
		// Every fitted value above sits between 0.9 and 0.99, and the axis still
		// covers the whole range a line MAY take. An axis fitted to the data would
		// make one 0.005 clamp fill the panel and a normal day read as an incident.
		expect(corridorOf({ band_low: 0.88, band_high: 1 })).toEqual([0.88, 1]);
	});

	test('the clamp band is taller below the line than above it', () => {
		// Both directions are capped and the fall cap is the wider of the two, so
		// the envelope is lopsided on purpose. A band drawn evenly either side would
		// say a rise and a fall were limited by the same amount, and they are not.
		const [band] = clampEnvelope(LINE.slice(0, 1));

		expect(band.high).toBeCloseTo(0.943, 6);
		expect(band.low).toBeCloseTo(0.93, 6);
		expect(0.94 - band.low).toBeGreaterThan(band.high - 0.94);
	});

	test('the clamp sentence counts the days a clamp fired and no others', () => {
		// Two of the four: the daily step and the guard. The day that took its
		// proposal whole and the day nothing was fitted are not clamps.
		expect(clampNote(LINE, 30)).toBe('The clamp held the line back on 2 of the last 30 days.');
	});

	test('a window where the clamp never fired says so rather than printing a zero', () => {
		expect(clampNote(LINE.slice(0, 1), 7)).toBe(
			'The clamp has not held the line back on any of the last 7 days.'
		);
	});

	test('a held day is counted and a window with none says nothing at all', () => {
		// Null rather than "0 days were held": a sentence a reader has to parse to
		// learn that nothing happened is a sentence that should not be there.
		expect(heldNote(LINE, 30)).toBe('Nothing was fitted on 1 of these 30 days.');
		expect(heldNote(LINE.slice(0, 3), 30)).toBeNull();
	});
});

test.describe('the judge, and what the record still needs', () => {
	function judgeDay(date: string, over: Partial<JudgeDay> = {}): JudgeDay {
		return {
			date,
			disagreementRate: 0.05,
			unclearRate: 0.1,
			pairsJudged: 20,
			negativesOnRecord: 40,
			aboveLineOnRecord: 6,
			daysOnRecord: 3,
			heldReason: 'sheet_too_small',
			...over
		};
	}

	test('the agreement axis is zero to the looser of the two limits', () => {
		// Not 0 to 1: neither rate can reach 1 without the run holding first, so
		// half the plot would be a region the data cannot enter. Not fitted to the
		// data either - a healthy two percent drawn full height says the judge is
		// in trouble when it is not.
		expect(agreementCorridor({ disagreementMax: 0.15, unclearMax: 0.35 })).toEqual([0, 0.35]);
		expect(agreementCorridor({ disagreementMax: 0.4, unclearMax: 0.35 })).toEqual([0, 0.4]);
	});

	test('a record with nothing in it still draws three bars at zero', () => {
		// The panel's best day, not its worst. A panel that waits for data before
		// it draws anything teaches an operator the measurement does not exist.
		const needs = gateNeeds(null, {
			minimumNegatives: 200,
			minimumDays: 10,
			minimumAboveLine: 30
		});

		expect(needs).toHaveLength(3);
		expect(needs.map((need) => need.value)).toEqual([0, 0, 0]);
		expect(needs.map((need) => need.target)).toEqual([200, 10, 30]);
		for (const need of needs) {
			expect(need.targetText, 'a bar was drawn with no words under its marker').not.toBe('');
		}
	});

	test('a held day while the gates are unfilled is not a warning', () => {
		// Ten amber squares on the panel's first fortnight would burn the colour
		// before it ever meant anything.
		const dates = ['2026-09-16', '2026-09-17', '2026-09-18'];
		const filling = countedDays(dates, [judgeDay('2026-09-17')], false);
		const settled = countedDays(dates, [judgeDay('2026-09-17')], true);

		expect(filling.map((square) => square.state)).toEqual(['silent', 'filling', 'silent']);
		expect(settled.map((square) => square.state)).toEqual(['silent', 'held', 'silent']);
		// And every square says what it is, so the hue is never the only signal.
		for (const square of filling) expect(square.title).toContain(square.date);
	});

	test('a fitted day is fitted whether or not the gates are met', () => {
		const square = countedDays(['2026-09-17'], [judgeDay('2026-09-17', { heldReason: 'none' })], false);

		expect(square[0].state).toBe('fitted');
		expect(square[0].title).toContain('a line was fitted');
	});

	test('the strip counts only the silent days at its newest end', () => {
		// Staleness is about the tail. A gap in the middle is a day that went
		// missing; a gap at the end is a record that has stopped filling.
		const squares = countedDays(
			['2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18'],
			[judgeDay('2026-09-15'), judgeDay('2026-09-16')],
			false
		);

		expect(silentTail(squares)).toBe(2);
		expect(silentTail(squares.slice(0, 2))).toBe(0);
	});

	test('no hold reason reaches a page in the ledger own word', () => {
		for (const reason of [
			'sheet_too_small',
			'inputs_changed',
			'judge_unstable',
			'judge_uncertain',
			'shards_missing'
		]) {
			expect(heldInWords(reason), `${reason} reached a page as itself`).not.toContain('_');
		}
	});

	test('a share under the attempts floor is not a share at all', () => {
		// A share over four pairs is not a measurement, and printing one invites a
		// decision the evidence cannot carry. The counts still print elsewhere.
		expect(rateWithDenominator(1, 4, 5)).toBeNull();
		expect(rateWithDenominator(1, 20, 5)).toBe('5% of 20 pairs');
	});
});

test.describe('the share, with the denominator it is a share of', () => {
	test('a share that rounds away prints under one rather than zero', () => {
		// 2 of 1,000 is 0.2 percent. A zero here would say nothing was folded, and
		// two stories were.
		const items: MergeItem[] = [
			{ item_id: 'a', same_story_as: null },
			{ item_id: 'b', same_story_as: 'a' },
			{ item_id: 'c', same_story_as: 'a' },
			...Array.from({ length: 997 }, (_, n) => ({ item_id: `n${n}`, same_story_as: null }))
		];
		const rate = mergeRate(mergeTotals([day('2026-08-03', items)]), 30);

		expect(rate).toContain('<1%');
		// Thousands separated, because a five-figure denominator read as `10122` is
		// a number a person has to count the digits of.
		expect(rate, 'a share with no denominator is not a share').toContain('1,000 stories');
	});

	test('there is no share to print when nothing was folded', () => {
		expect(mergeRate(mergeTotals([]), 30)).toBeNull();
		expect(mergeRate(mergeTotals([day('2026-08-01', [{ item_id: 'a' }])]), 30)).toBeNull();
	});
});
