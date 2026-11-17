/** What share of a call's prompt tokens the model server already had cached, per UTC day.
 *
 * The share is pooled - the day's cached tokens over the day's prompt tokens -
 * because a median of per-article shares is not stable here: a day on which
 * most articles cached nothing has a median of zero while about a quarter of
 * its prompt tokens were cached.
 */
import type { Row } from '../../data/ledger';
import { finiteCell } from '../rates';

export type ReuseCall = 'label' | 'summary';

export interface ReuseDay {
	/** The UTC day, `YYYY-MM-DD`. */
	date: string;
	/** Prompt tokens summed over the day's complete readings. */
	input: number;
	/** Cached tokens summed over those same readings. */
	cached: number;
	/** How many article readings were complete. */
	articles: number;
	/** `100 * cached / input` from the two sums, 0 to 100. */
	share: number;
}

/** Each day that holds a complete reading of one call, oldest first.
 *
 * A reading is complete when its prompt and cached cells are both recorded and
 * finite, the prompt is positive and the cache is neither negative nor above
 * the prompt. A day with no complete reading is absent, never a zero: no
 * measurement is not a measurement of nothing cached.
 */
export function reuseDays(rows: readonly Row[], call: ReuseCall): ReuseDay[] {
	const days = new Map<string, { input: number; cached: number; articles: number }>();
	for (const row of rows) {
		const input = finiteCell(row[`${call}_input_tokens`]);
		const cached = finiteCell(row[`${call}_cached_tokens`]);
		if (typeof row.date !== 'string' || input === null || cached === null ||
			input <= 0 || cached < 0 || cached > input) continue;
		const day = days.get(row.date) ?? { input: 0, cached: 0, articles: 0 };
		days.set(row.date, { input: day.input + input, cached: day.cached + cached, articles: day.articles + 1 });
	}
	return [...days].sort(([a], [b]) => a.localeCompare(b))
		.map(([date, day]) => ({ date, ...day, share: 100 * day.cached / day.input }));
}
