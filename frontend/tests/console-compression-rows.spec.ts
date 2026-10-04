/** Which article rows a compression plot places or counts as unplotted. */
import { expect, test } from '@playwright/test';
import { compressionView, placeRow, type TelemetryRow } from '../src/lib/charts/series';
import { telemetryRow } from './support/telemetry-row';

test('an unplaceable row is counted and never silently dropped', () => {
	// The browser case above cannot reach this state on the committed fixture, so
	// the decision is driven here instead of left to a sentence that never
	// prints. Three rows, one of each outcome, and the two outputs come out of
	// one pass - a plot and a sentence that disagree about the same row is the
	// failure this shape exists to prevent.
	const row = (over: Partial<TelemetryRow>): TelemetryRow =>
		telemetryRow({
			date: '2026-08-28',
			run_id: '2026-08-28-1',
			source_words: 1923,
			summary_words: 205,
			source_words_before_cap: 4200,
			...over
		});

	const view = compressionView([
		row({ item_id: 'ai-cut' }),
		row({ item_id: 'ai-whole', source_words: 880, source_words_before_cap: null }),
		row({ item_id: 'ai-nolength', source_words: 0, source_words_before_cap: null }),
		row({ item_id: 'ai-nosummary', summary_words: null }),
		// A failure never had an article, so it is neither a point nor a row the
		// sentence should count. Without the predicate it lands in the sentence and
		// tells the operator articles went missing that never existed.
		row({ item_id: 'ai-failed', stage: 'fetch', outcome: 'failed', code: 'http_error' }),
		row({
			item_id: 'ai-dropped',
			stage: 'extract',
			source_words: 0,
			summary_words: null,
			source_words_before_cap: null
		}),
		// The same article, written again by a second run of the same day. One
		// article is one mark: drawing it twice draws one measurement twice, and
		// the run that read the most of it is the one that counts.
		row({ item_id: 'ai-whole', run_id: '2026-08-28-2', source_words: 300, source_words_before_cap: null })
	]);

	expect(view.points.map((point) => point.item_id)).toEqual(['ai-cut', 'ai-whole']);
	expect(view.points.find((point) => point.item_id === 'ai-whole')?.source_words).toBe(880);
	expect(view.unplotted).toEqual([{ date: '2026-08-28', n: 1 }]);

	// The cut is the two lengths and nothing else, and the second one is carried
	// only where it says something the first does not.
	const [cut, whole] = view.points;
	expect(cut.source_words).toBe(4200);
	expect(cut.source_seen_words).toBe(1923);
	expect(cut.truncation_flagged).toBe(true);
	expect(whole.source_words).toBe(880);
	expect('source_seen_words' in whole).toBe(false);
	expect(whole.truncation_flagged).toBe(false);

	// The three outcomes, asserted on the one decision the view folds.
	expect(placeRow(row({ source_words: 0, source_words_before_cap: null }))).toEqual({
		kind: 'no-length',
		date: '2026-08-28'
	});
	expect(placeRow(row({ summary_words: null })).kind).toBe('no-summary');
	expect(placeRow(row({})).kind).toBe('point');
});

test('the plot reads the cut off two lengths, so no ledger stamp can change what it means', () => {
	// This used to assert a gate on the score ledger's `truncation_flagged`,
	// which changed meaning at `CUT_FLAG_MEANS_A_CUT_FROM`: the plot read the
	// column raw while the day's count in the table read it only over the rows
	// stamped with its current meaning, so one page made two claims about one
	// column. The projection ends the argument. A pre-cap length standing above
	// a post-cap one has meant exactly one thing on every row ever written, so
	// there is no stamp to read and no second meaning to gate.
	const row = (before: number | null, after: number | null): TelemetryRow =>
		telemetryRow({
			date: '2026-08-28',
			run_id: '2026-08-28-1',
			source_words: after,
			summary_words: 205,
			source_words_before_cap: before
		});

	const marked = (before: number | null, after: number | null): boolean => {
		const placed = placeRow(row(before, after));
		if (placed.kind !== 'point') throw new Error('the fixture row is placeable');
		return placed.point.truncation_flagged;
	};

	// Cut, and drawn at the length the article actually was.
	expect(marked(4200, 1923)).toBe(true);
	// Nothing was cut, on the two shapes a run can write: the cap did not fire,
	// and the run predates the column that records what it did.
	expect(marked(2000, 2000)).toBe(false);
	expect(marked(null, 880)).toBe(false);

	// A row written before 2026-08-28 records no pre-cap length, so it is drawn
	// at the length that survived. That is the honest reading: the ledger holds
	// no answer to what the article was, and inventing a diamond on it would
	// claim a cut nobody measured.
	const older = placeRow(row(null, 880));
	expect(older.kind === 'point' && older.point.source_words).toBe(880);
	expect(older.kind === 'point' && 'source_seen_words' in older.point).toBe(false);
});
