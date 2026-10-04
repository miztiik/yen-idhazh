/** What one day's model rows count, and which measurements stay unknown. */
import { expect, test } from '@playwright/test';
import { CUT_FLAG_MEANS_A_CUT_FROM, modelWork } from '../src/lib/server/model-work';

test('a model change is one divider row, under the days that ran on it', () => {
	// The fixture ran one model, so the swap is asserted over the function that
	// places it. A divider drawn from a fixture that cannot change models would
	// only prove the fixture.
	const scored = (date: string, model: string) => ({
		date,
		model_id: model,
		band: 'high',
		extractiveness: '0.2',
		verbatim_run: '0.1',
		unsupported_numbers: '0',
		hedge_dropped: 'False',
		truncation_flagged: 'False'
	});

	const rows = modelWork(
		[scored('2026-08-26', 'new'), scored('2026-08-25', 'new'), scored('2026-08-24', 'old')],
		[]
	);

	expect(
		rows.map((row) => (row.kind === 'swap' ? `swap ${row.date} ${row.model}` : row.day.date))
	).toEqual(['2026-08-26', '2026-08-25', 'swap 2026-08-25 new', '2026-08-24']);

	// One model over every day is no divider at all.
	expect(
		modelWork([scored('2026-08-26', 'one'), scored('2026-08-25', 'one')], []).filter(
			(row) => row.kind === 'swap'
		)
	).toEqual([]);
});

test('a day with no summaries gets no row, and a day with no health row gets no failure count', () => {
	const health = (date: string, ms: string, outcome: string) => ({
		date,
		summarize_ms: ms,
		outcome
	});

	const rows = modelWork(
		[{ date: '2026-08-26', model_id: 'one', band: 'low' }],
		[
			health('2026-08-26', '2000', 'failed'),
			health('2026-08-25', '1500', 'ok'),
			// Fetched and thrown away before the model saw it. No summary, no row.
			health('2026-08-24', '', 'failed')
		]
	);

	const days = rows.filter((row) => row.kind === 'day').map((row) => row.day);
	expect(days.map((day) => day.date)).toEqual(['2026-08-26', '2026-08-25']);
	expect(days[0].failed).toBe(1);
	expect(days[0].notSure).toBe(1);
	// Model work, no score row: every quality figure is unknown, not zero.
	expect(days[1].summaries).toBeNull();
	expect(days[1].notSure).toBeNull();
	expect(days[1].copiedPct).toBeNull();
	expect(days[1].totalMs).toBe(1500);

	// A day with score rows and no health row cannot count failures.
	const scoredOnly = modelWork([{ date: '2026-08-26', model_id: 'one', band: 'high' }], []);
	expect(scoredOnly).toHaveLength(1);
	expect(scoredOnly[0].kind === 'day' && scoredOnly[0].day.failed).toBeNull();
	expect(scoredOnly[0].kind === 'day' && scoredOnly[0].day.perItemMs).toBeNull();
});

test('the cut flag is counted only over rows that carry the meaning it has now', () => {
	// `truncation_flagged` changed meaning at `CUT_FLAG_MEANS_A_CUT_FROM`. Before
	// that stamp the cell held the gap between two faithfulness scores; from it,
	// the cell says extract cut the article body. Two rows on one day, one either
	// side of the stamp, are what tell a reader of the new meaning apart from a
	// reader that just counts the column.
	const row = (version: string, flagged: string) => ({
		date: '2026-08-28',
		version,
		model_id: 'one',
		band: 'high',
		truncation_flagged: flagged
	});

	// `2026-08-27T20:30` is the newest stamp the committed ledger actually
	// carries. The date-stamp format is ASCII-sortable on purpose, so a stamp
	// carrying a time orders before the bare date that follows it - which is the
	// whole reason a plain string compare is enough here.
	const before = '2026-08-27T20:30';
	const after = CUT_FLAG_MEANS_A_CUT_FROM;
	expect(before < after, 'a stamp carrying a time must order before the bare date').toBe(true);

	const readInPart = (rows: Record<string, string>[]): number | null => {
		const days = modelWork(rows, []).filter((entry) => entry.kind === 'day');
		expect(days).toHaveLength(1);
		// Throws rather than falling back to a number: a silent 0 here would be
		// indistinguishable from the answer one of the assertions below expects.
		if (days[0].kind !== 'day') throw new Error('the filter above kept a divider row');
		return days[0].day.readInPart;
	};

	// One direction: the older row is flagged, the newer one is not. A reader that
	// counted the whole column would print 1. Only the newer row carries the
	// meaning, so the answer is 0 - a real number, and not the flagged row's.
	expect(readInPart([row(before, 'True'), row(after, 'False')])).toBe(0);

	// The other direction, the same pair with the flags swapped. The answer is 1,
	// which is what stops this passing on a reader that always returns null.
	expect(readInPart([row(before, 'False'), row(after, 'True')])).toBe(1);

	// A day made only of older rows holds no answer at all. Zero would say the
	// pipeline cut nothing, which those rows never measured.
	expect(readInPart([row(before, 'True'), row(before, 'True')])).toBeNull();

	// A stamp carrying a time on the boundary day is on the new side of it.
	expect(readInPart([row('2026-08-28T09:00', 'True')])).toBe(1);

	// An unstamped row reads as older. Unknown is the safe direction.
	expect(
		readInPart([{ date: '2026-08-28', model_id: 'one', truncation_flagged: 'True' }])
	).toBeNull();

	// The gate is on the one column whose meaning moved. Every other figure still
	// counts every row the day holds.
	const mixed = modelWork([row(before, 'True'), row(after, 'False')], [])[0];
	expect(mixed.kind === 'day' && mixed.day.summaries).toBe(2);
});

test('the cut share divides by the rows its own flag answers for', () => {
	const score = (version: string, flagged: string) => ({
		date: '2026-08-28',
		version,
		model_id: 'one',
		band: 'high',
		truncation_flagged: flagged
	});

	const only = (rows: Record<string, string>[]) => {
		const day = modelWork(rows, [])[0];
		if (day.kind !== 'day') throw new Error('the fixture is one day');
		return day.day;
	};

	// Four rows, one cut, and all four carry the flag's current meaning: 25
	// percent. A share over the day's whole ledger would print the same here,
	// which is why the row below is the one that separates them.
	const clean = only([
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'True'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False')
	]);
	expect(clean.readInPart).toBe(1);
	expect(clean.readInPartPct).toBe(25);

	// The same four, plus four older rows the flag no longer answers for. The
	// count is still 1 and the share is still 25 percent: dividing by eight
	// would print 13, and that 13 is a fact about the migration rather than
	// about the articles.
	const mixed = only([
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'True'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score(CUT_FLAG_MEANS_A_CUT_FROM, 'False'),
		score('2026-08-27T20:30', 'True'),
		score('2026-08-27T20:30', 'True'),
		score('2026-08-27T20:30', 'False'),
		score('2026-08-27T20:30', 'False')
	]);
	expect(mixed.summaries).toBe(8);
	expect(mixed.readInPart).toBe(1);
	expect(mixed.readInPartPct).toBe(25);

	// A day with nothing the flag answers for holds no share either. Zero
	// percent would say the cap took nothing, which those rows never measured.
	expect(only([score('2026-08-27T20:30', 'True')]).readInPartPct).toBeNull();
});

test('the day splits its writing time by the articles it read only the start of', () => {
	const health = (ms: string, before: string, after: string, code = '') => ({
		date: '2026-08-28',
		summarize_ms: ms,
		outcome: 'ok',
		code,
		source_words: after,
		source_words_before_cap: before
	});

	const only = (rows: Record<string, string>[]) => {
		const day = modelWork([], rows)[0];
		if (day.kind !== 'day') throw new Error('the fixture is one day');
		return day.day;
	};

	// Two whole articles and two the cap cut. The day's median is over all four
	// and the split is over the two, so a split that quietly reported the day
	// again would print 1500 twice.
	const split = only([
		health('1000', '400', '400'),
		health('1200', '', '380'),
		health('4000', '2612', '1923'),
		health('6000', '9000', '1923')
	]);
	expect(split.perItemMs).toBe(2600);
	expect(split.perItemCutMs).toBe(5000);

	// A day that cut nothing has no second figure. Zero would say the machine
	// wrote those summaries for free.
	expect(only([health('1000', '400', '400'), health('1200', '', '380')]).perItemCutMs).toBeNull();

	// An empty cell is not a zero: a row that recorded no length before the cut
	// is not an article cut from nothing to 380 words.
	expect(only([health('1200', '', '380')]).perItemCutMs).toBeNull();

	// Refused for length is a count of the day's own rows, and zero is a real
	// answer. Null is kept for a day with no health row at all.
	expect(
		only([health('1000', '400', '400'), health('', '', '', 'context_exceeded')]).refusedForLength
	).toBe(1);
	expect(only([health('1000', '400', '400')]).refusedForLength).toBe(0);
	const scoredOnly = modelWork([{ date: '2026-08-28', model_id: 'one', band: 'high' }], [])[0];
	expect(scoredOnly.kind === 'day' && scoredOnly.day.refusedForLength).toBeNull();
});
